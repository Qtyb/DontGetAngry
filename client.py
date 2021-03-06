# from socket import socket, AF_INET, SOCK_STREAM, timeout, error
from common import *
import signal
import sys
import select
import threading
import queue
import os
from settings import CONNECT_TIMEOUT
from game.logger_conf import client_logger


# check if it matches print_options
options_mapping = {
    TLV_OPTION_MOVE: "1",
    TLV_OPTION_PUT: "2",
}


def option_parsing(tlv_msg):
    """
    Gets tlv message and returns dictionary {TLV: number} of player possible options.
    """
    return {tag: options_mapping[tag] for tag in tlv_msg if tag in options_mapping}


def flush_input():
    try:
        import msvcrt
        while msvcrt.kbhit():
            msvcrt.getch()
    except ImportError:
        import sys, termios    #for linux/unix
        termios.tcflush(sys.stdin, termios.TCIOFLUSH)


class ClientDGA:

    def __init__(self, is_ipv6=False):
        self.sock = None
        self.is_ipv6 = is_ipv6
        self.running = False
        self.nickname = ""
        self.game_started = False
        self.game_client_turn = False
        self.game_roll = None
        self.game_rolled = False
        self.roll_command_requested = False
        self.pipeline = queue.Queue(maxsize=50)     # queue to exchange packets between threads
        self.current_msg = None                     # the msg to be handled (check wait_for_ack)
        self.log_counter = 999
        self.player_options = {}        # tlv message that indicates player possible options
        self.option_chosen = None       # tlv tag that indicates player's choice
        self.skip_turn = False

    def init(self):
        try:
            if self.is_ipv6:
                self.sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            else:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except OSError as e:
            client_logger.error("socket error: {}".format(str(e)))

    def connect(self, addr, port):
        """
        Try to connect to the server. Exit on failure.
        @param addr:    (string)    : IPv4 or IPv6 address, dotted form
        @param port:    (int)       : port number
        @return:        (None)
        """
        try:
            self.sock.settimeout(CONNECT_TIMEOUT)
            if self.is_ipv6:
                self.sock.connect((addr, port, 0, 0))
            else:
                self.sock.connect((addr, port))
            self.sock.settimeout(None)
        except OSError as e:
            print("Cannot connect to the server: {}".format(str(e)))
            client_logger.error("connect error: {}".format(str(e)))
            self.close()
        except KeyboardInterrupt as e:
            client_logger.error("keyboard interrupt while connecting: {}".format(str(e)))
            self.close()
        except Exception as e:
            print("Error while connecting: {}".format(str(e)))
            client_logger.error("connect other error: {}".format(str(e)))
            self.close()

    def close(self):
        """
        Close client socket, flush input buffer and close program.
        Reading thread is a daemon so it should close with the main thread.
        """
        self.sock.close()
        flush_input()
        sys.exit(-1)

    def run(self):
        event = threading.Event()
        read_thread = threading.Thread(target=self.read_loop, args=(event,), daemon=True)  # daemon will be closed with the main thread
        try:
            read_thread.start()
            self.set_nickname()
            client_logger.info("My nickname is {}".format(self.nickname))
            self.set_room()
            self.running = True
            self.print_options()

            while self.running and not event.is_set():
                if self.game_started:
                    self.reset_vars()

                    if self.game_client_turn:
                        input("Press enter to roll a dice")
                        self.send_roll_command()    # blocks
                        if self.skip_turn:
                            client_logger.info("Skipping turn")
                        else:
                            self.send_place_or_move_command()
                        # if self.game_roll is not None:      # can be?
                        # print("GAME roll is not null")

                        self.game_roll = None
                        self.game_client_turn = False
                        self.roll_command_requested = False
                        client_logger.info("Player {} turn ended".format(self.nickname))

                    else:
                        self.wait_for_turn()
                else:
                    rs, _, _ = select.select([sys.stdin], [], [], 1)

                    if event.is_set():  # server error
                        break

                    if self.game_started:   # game started
                        client_logger.debug("Game started, ignore input")
                        continue

                    if not rs:          # timeout with no input
                        continue

                    msg = sys.stdin.readline()

                    if msg[-1] == '\n':     # remove newline character
                        msg = msg[:-1]

                    if not msg:             # enter pressed
                        print("Press enter to refresh: ", end="", flush=True)      # terminal is waiting for new line
                        continue

                    self.handle_options_input(msg)
            # self.close()  # sys.exit() raises SystemExit so finally will be executed
            raise Exception()
        except KeyboardInterrupt:
            client_logger.warning("Keyboard interrupt")
            print("Closing...\n")
            self.running = False
            self.close()
        except (OSError, EOFError) as e:
            print("Server error")
            client_logger.error("Server error: " + str(e))
            self.running = False
            self.close()
        except Exception as e:
            print("Server error")
            client_logger.error("Exception: " + str(e))
            self.running = False
            self.close()

    def read_loop(self, event):        # !TODO timeout to signal
        """ Thread that reads messages sent by the server. """

        while True:
            try:
                server_ans = recvTlv(self.sock)

                if TLV_OK_TAG in server_ans or TLV_FAIL_TAG in server_ans:    # ACK / NACK response - main thread is awaiting for it
                    # print("Message {} has ACK/NACK tag => saving to pipeline for future processing".format(server_ans))
                    self.pipeline.put(server_ans)
                    continue

                if TLV_NEWTURN_TAG in server_ans:
                    client_logger.debug("Put TLV_NEWTURN_TAG msg into the pipeline")
                    self.pipeline.put(server_ans)
                    continue
                
                # print("Message {} is a request from the server".format(server_ans))
                self.handle_answer(server_ans)      # received msg is not a control msg
            except (OSError, EOFError) as e:
                print("\nServer error\n")
                client_logger.error("Error while reading data: " + str(e))
                os.kill(os.getpid(), signal.SIGINT)     # should raise Keyboard interrupt in the main thread
                event.set()  # alarm main thread that program should exit
                return
            except Exception as e:
                client_logger.error("Other error while reading data: " + str(e))
                os.kill(os.getpid(), signal.SIGINT)
                event.set()  # alarm main thread that program should exit
                return

    def handle_answer(self, ans):
        """
        Handle response from the server. It can change state of the client e.g. game started or
        just print received information.
        ans     (dict)  : TLV: str
        """

        if TLV_STARTED_TAG in ans:
            client_logger.debug("Game started tag received")
            # print("Press enter to start a game")
            self.game_started = True

        if TLV_FINISHED_TAG in ans:
            self.game_started = False

        if TLV_INFO_TAG in ans:     # information message -> print it
            print("\n" + remove_tlv_padding(ans[TLV_INFO_TAG]))

        if TLV_MOVEORPLACE_TAG in ans:
            client_logger.debug("TLV_MOVEORPLACE_TAG received")

        if TLV_ROLLDICERESULT_TAG in ans:
            client_logger.debug("Roll dice result tag received")
            self.game_roll = ans[TLV_ROLLDICERESULT_TAG]
            self.game_rolled = True

    def get_ingame_options_tag(self):
        while True:
            self.print_ingame_options()

            msg = input(">> ")
            client_logger.debug("Player input: " + msg)
            if msg not in ('0', '1', '2'):
                print("Input {} is invalid".format(msg))
                continue

            client_logger.debug("Player options: " + str(self.player_options))
            if msg not in self.player_options.values():
                print("You cannot do that!")        # !TODO print description
                continue

            tlv_tag = self.handle_ingame_options_input(msg)
            client_logger.debug("Return ingame option: "+  str(tlv_tag))
            return tlv_tag

    def get_ingame_figure(self):
        """ Should be called only if player chooses MOVE option """
        while True:
            figures = self.current_msg[TLV_OPTION_MOVE]  # only MOVE allowed
            client_logger.debug("Figures before deserialization: " + str(figures))
            figures = deserialize_list(figures)
            client_logger.debug("Figures after deserialization: " + str(figures))
            figures = {str(num + 1): fig for num, fig in enumerate(figures)}     # num: fig_name dict
            # client_logger.debug("Figures dict: " + str(figures))
            self.print_ingame_figure_choice(figures)
            
            msg = input(">> ")
            msg = msg.strip()
            # client_logger.debug(f"Input: {msg}")
            client_logger.debug(f"figures: {str(figures)}")
            # client_logger.debug(f"true/false: {msg not in figures}")
            if msg == "0":
                self.close()

            if msg not in figures:
                print("Input {} is invalid".format(msg))
                continue
            figure = figures[msg]
            # figure = self.handle_ingame_figure_choice_input(msg)
            return figure

    def send_place_or_move_command(self):
        """Send place figure command to the server and anticipate positive response"""
        tlv_tag = self.get_ingame_options_tag()
        self.option_chosen = tlv_tag
        figure = "0"        # default value, if player wants to put figure we do not need information about figure number
        client_logger.debug("Options chosen: " + tlv_tag)
        if tlv_tag == TLV_MOVEFIGURE_TAG:
            figure = self.get_ingame_figure()
        
        data_dict = {
            tlv_tag: figure
        }

        client_logger.debug("Place or Move command options chosen {}".format(data_dict))
        tlv = build_tlv_with_tags(data_dict)
        sendTlv(self.sock, tlv)
    
    def send_roll_command(self):
        """Send roll dice command to the server and anticipate positive response with roll result"""
        while True:
            client_logger.debug("Sending roll command")
            tlv = add_tlv_tag(TLV_ROLLDICE_TAG, self.nickname)
            sendTlv(self.sock, tlv)

            if self.wait_for_ack() and TLV_ROLLDICERESULT_TAG in self.current_msg:
                client_logger.debug("ROLLDICE result: " + str(self.current_msg))
                print('Roll command successfully requested. Server returned {}'.format(self.current_msg[TLV_ROLLDICERESULT_TAG]))
                if TLV_OPTION_SKIP in self.current_msg:
                    self.skip_turn = True
                    return
                self.player_options = option_parsing(self.current_msg)
                return
            else:
                if TLV_FAIL_TAG in self.current_msg:
                    print(self.current_msg[TLV_FAIL_TAG])       # print error message

                client_logger.warning("Message did not have {}".format(TLV_ROLLDICERESULT_TAG))

    def set_nickname(self):
        """Send nickname to the sever and anticipate positive response"""
        while True:
            nickname = input("Your nickname: ")
            if not nickname:
                continue

            tlv = add_tlv_tag(TLV_NICKNAME_TAG, nickname)
            sendTlv(self.sock, tlv)

            if self.wait_for_ack():
                self.nickname = nickname
                print(self.current_msg[TLV_OK_TAG])
                return
            else:
                print(self.current_msg[TLV_FAIL_TAG])       # print error message

    def set_room(self):
        """
        Set room number in a loop. If non-int is passed from stdin or server send negative response then try again.
        If server sends back positive response then break and return None.
        """
        while True:
            room = input("Create or select existing channel\n> ")
            try:
                int(room)
                tlv = add_tlv_tag(TLV_ROOM_TAG, room)
                sendTlv(self.sock, tlv)

                if self.wait_for_ack():     # positive answer
                    print("Server answer: ", self.current_msg[TLV_OK_TAG])  # new msg is saved after wait_for_ack call
                    client_logger.debug("Joined room number {}".format(room))
                    return

                print("Server answer: ", self.current_msg[TLV_FAIL_TAG])      # fail msg info

            except ValueError:
                client_logger.info("Try again")

    def handle_options_input(self, msg):
        if msg.upper().strip() in ["1", "GET_ROOMS"]:
            self.get_server_rooms()
        elif msg.upper().strip() in ["2", "GET_USER_INFO"]:
            self.get_user_info()
        elif msg.upper().strip() in ["3", "START"]:
            self.send_start_msg()
        elif msg.upper().strip() in ["4", "HELP", "INFO"]:
            self.print_options()
        elif msg.upper().strip() in ["5", "EXIT"]:
            self.close()

    def wait_for_ack(self):
        """
        Blocks until new msg is put into the Queue. Returns True if msg contains OK_TAG. Otherwise, if msg contains
        FAIL_TAG or any doesn't contain any control tag (OK/FAIL) it returns False.
        @return:    (bool)  : indicates status of the control msg
        """
        msg = self.pipeline.get()       # blocks here
        self.current_msg = msg          # msg can be read from outside of this method while it returns control information

        if TLV_OK_TAG in msg:
            client_logger.debug("Received OK_TAG")
            return True

        elif TLV_FAIL_TAG in msg:
            client_logger.debug("Received FAIL_TAG")
            return False

        else:
            client_logger.debug("Received unknown tags: {}".format(get_types(msg)))
            raise OSError("Unknown tag received, while waiting for control tag")

    def wait_for_turn(self):        # !TODO check collision with ack/nack tags
        """ Waiting for NEWTURN tag and returns true if it is this player turn """
        try:
            msg = self.pipeline.get(timeout=1)      # timeout allows to close main thread when exception occurs in readloop
        except queue.Empty:
            return False

        if TLV_NEWTURN_TAG in msg:
            # print("TLV_NEWTURN_TAG received msg: {}, tag value: {}".format(msg, msg[TLV_NEWTURN_TAG]))
            rcvd_nickname = msg[TLV_NEWTURN_TAG]
            if self.nickname.upper() == rcvd_nickname.upper():
                self.game_client_turn = True
                flush_input()
                return True
            else:
                print(f"Player {rcvd_nickname} turn")
        else:
            client_logger.error("Received wrong tag: {}".format(msg))

    def print_options(self):
        interface_msg = """
        1. GET_ROOMS : get information about room status
        2. GET_USER_INFO : get information about your status
        3. START : start a game, available only if you joined a room with at least other player
        4. HELP : print options
        5. EXIT : shutdown program
        """
        print(interface_msg)

    def handle_ingame_options_input(self, msg):
        if msg.upper().strip() in [options_mapping[TLV_OPTION_PUT], "PLACE_FIGURE"]:
            client_logger.debug("PLACE FIGURE CHOSEN")
            return TLV_PLACEFIGURE_TAG

        elif msg.upper().strip() in [options_mapping[TLV_OPTION_MOVE], "MOVE_FIGURE"]:
            client_logger.debug("MOVE FIGURE CHOSEN")
            return TLV_MOVEFIGURE_TAG

        elif msg.upper().strip() in ["0", "EXIT"]:
            client_logger.debug("EXIT CHOSEN")
            self.handle_exit_command()

    def print_ingame_options(self):
        """ Print player options based on msg received from the server"""
        interface_msg = ""

        if TLV_OPTION_MOVE in self.player_options:
            interface_msg += f"{options_mapping[TLV_OPTION_MOVE]}. MOVE FIGURE\n"

        if TLV_OPTION_PUT in self.player_options:
            interface_msg += f"{options_mapping[TLV_OPTION_PUT]}. PLACE FIGURE\n"

        interface_msg += "0. EXIT : leave game"
        print(interface_msg)

    def handle_ingame_figure_choice_input(self, msg):
        if msg.upper().strip() in ["1"]:
            print("Figure 1 chosen")
            return "1"
        elif msg.upper().strip() in ["2"]:
            print("Figure 2 chosen")
            return "2"
        elif msg.upper().strip() in ["3"]:
            print("Figure 3 chosen")
            return "3"
        elif msg.upper().strip() in ["4"]:
            print("Figure 4 chosen")
            return "4"
        elif msg.upper().strip() in ["0", "EXIT"]:
            print("Exit chosen")
            self.handle_exit_command()

    def print_ingame_figure_choice(self, figures):
        """ Print figures that can be moved by the player
        @param figures:     (dict)  : num: figure_name
        """
        interface_msg = ""
        client_logger.debug(f"Figures: {str(figures)}")
        for num, figure in figures.items():
            interface_msg += f"{num}. : {figure}\n"     # !TODO handle select
        interface_msg += "0. EXIT : leave game\n"

        print(interface_msg)

    def handle_exit_command(self):
        sys.exit()
    
    def send_reset_msg(self):
        pass

    def get_server_rooms(self):
        """Server should response with rooms stats e.g. room 2: 1/4 players status: WAITING FOR PLAYERS"""
        tlv = add_tlv_tag(TLV_GET_ROOMS, "-")
        sendTlv(self.sock, tlv)

    def get_user_info(self):
        tlv = add_tlv_tag(TLV_GET_USERINFO, "-")
        sendTlv(self.sock, tlv)

    def get_server_my_room(self):
        """Server should response with client's room stats"""
        pass

    def get_server_game_status(self):
        pass

    def send_start_msg(self):
        tlv = add_tlv_tag(TLV_START_MSG, "-")
        sendTlv(self.sock, tlv)

    def reset_vars(self):
        """ For the debug purpose reset all variables to init values """
        self.current_msg = None
        self.skip_turn = False
        self.player_options = {}
        self.option_chosen = None


if __name__ == "__main__":
    # remote server address
    LOOPBACK = '127.0.0.1'
    PORT = 65432

    addr = LOOPBACK
    port = PORT

    if len(sys.argv) == 3:
        addr = sys.argv[1]
        port = sys.argv[2]

        if not is_valid_port(port):     # checks if port is int and in scope of valid port numbers
            print(f"Wrong port: {port}")
            sys.exit(1)
        port = int(port)

    elif len(sys.argv) == 2:
        if sys.argv[1] in ["-h", "--help", "-help", "?"]:
            print("""
            Usage: python3 client.py [address] [port]
            Default address: {}
            Default port: {}
            """.format(LOOPBACK, PORT))
            sys.exit()
        addr = sys.argv[1]

    is_ipv6 = is_ipv6(addr)
    cli = ClientDGA(is_ipv6)
    cli.init()
    cli.connect(addr, port)
    cli.run()
