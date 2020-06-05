import errno
from socket import socket, AF_INET, SOCK_STREAM, timeout, error
import time
from common import *
from random import randint
from exceptions import *
import signal
import sys
import select
import threading
import os
from pytlv.TLV import *
from game.logger_conf import client_logger


def sig_alarm_handler(signum, stack):
    print("Received SIGALRM: ", signum, " ", stack)
    raise ChangeStateException()


class ClientDGA:

    def __init__(self):
        self.sock = None
        self.state = None
        self.running = False
        self.read_sockets = []
        self.close_flag = False
        self.nickname = ""
        self.game_started = False
        self.game_client_turn = False
        self.game_roll = None
        self.game_rolled = False

    def init(self):
        try:
            self.sock = socket(AF_INET, SOCK_STREAM)
            self.read_sockets.append(self.sock)
            self.read_sockets.append(sys.stdin)
        except OSError as e:
            client_logger.error("socket error: {}".format(str(e)))

    def connect(self, addr, port):
        try:
            self.sock.connect((addr, port))
        except OSError as e:
            client_logger.error("connect error: {}".format(str(e)))
            sys.exit()

    def close(self):
        self.sock.close()
        sys.exit(-1)

    def run(self):
        event = threading.Event()
        read_thread = threading.Thread(target=self.read_loop, args=(event,), daemon=True)  # daemon will be closed with the main thread
        try:
            self.nickname = self.set_nickname()
            print("My nickname is ", self.nickname)
            self.set_room()
            self.running = True
            read_thread.start()
            self.print_options()
            while self.running and not event.is_set():
                if self.game_started:
                    print("GAME flag is set") # !TODO handle game
                    if self.game_client_turn:
                        print("GAME client turn flag is set")
                        self.send_roll_command()
                        if self.game_roll is not None:
                            print("GAME roll is not null")
                            self.send_place_or_move_command()
                            self.game_roll = None
                            self.game_client_turn = False
                            print("Player {} turn ended".format(self.nickname))
                else:
                    msg = input("Press enter to refresh: ")
                    if event.is_set():  # server error
                        break

                    if self.game_started:   # game started
                        client_logger.debug("Game started, ignore input")
                        continue

                    if not msg:   # enter pressed
                        continue
                    self.handle_options_input(msg)
            # self.close()  # sys.exit() raises SystemExit so finally will be executed
            raise Exception()
        except KeyboardInterrupt:
            client_logger.error("Keyboard interrupt")
        except (OSError, EOFError) as e:
            print("Server error")
            client_logger.error("Server error: " + str(e))
        except Exception as e:
            print("Server error")
            client_logger.error("Exception: " + str(e))
        finally:
            print("Closing...")
            self.running = False
            self.close()
            sys.exit(-1)

    def read_loop(self, event):        # !TODO timeout to signal
        """ Thread that reads messages sent by the server. """
        while True:
            try:
                server_ans = recvTlv(self.sock)
                self.handle_answer(server_ans)
            except (OSError, EOFError, ChangeStateException) as e:
                client_logger.error("Error while reading data: " + str(e))
                event.set()  # alarm main thread that program should exit
                return
            except Exception as e:
                client_logger.error("Other error while reading data: " + str(e))
                event.set()  # alarm main thread that program should exit
                return

    def handle_answer(self, ans):
        """
        Handle response from the server. It can change state of the client e.g. game started or
        just print received information.
        ans     (dict)  : TLV: str
        """
        if TLV_STARTED_TAG in ans:
            self.game_started = True

        if TLV_FINISHED_TAG in ans:
            self.game_started = False

        if TLV_NEWTURN_TAG in ans:
            print("TLV_NEWTURN_TAG received msg: {}, tag value: {}".format(ans, ans[TLV_NEWTURN_TAG]))
            if self.nickname.upper() == ans[TLV_NEWTURN_TAG].upper():
                print("FINALLY MY TURN")
                self.game_client_turn = True

        if TLV_INFO_TAG in ans:
            print("\n" + remove_tlv_padding(ans[TLV_INFO_TAG]))

        #TODO remove
        if TLV_MOVEORPLACE_TAG in ans:
            print("TLV_MOVEORPLACE_TAG received")

        if TLV_ROLLDICERESULT_TAG in ans:
            self.game_roll = ans[TLV_ROLLDICERESULT_TAG]
            self.game_rolled = True

    def move_or_place(self):
        while True:
            nickname = input("Your nickname: ")
            tlv = add_tlv_tag(TLV_NICKNAME_TAG, nickname)
            sendTlv(self.sock, tlv)
            server_ans = recvTlv(self.sock)        # maybe each header of server response should contain OK/FAIL
            if TLV_OK_TAG in server_ans:
                print(remove_tlv_padding(server_ans[TLV_OK_TAG]))
                break
            elif TLV_FAIL_TAG in server_ans:
                print(remove_tlv_padding(server_ans[TLV_FAIL_TAG]))

    def send_place_or_move_command(self):
        """Send place figure command to the server and anticipate positive response"""
        while True:
            self.print_ingame_options()
            msg = input(">> ")
            tlv_tag = self.handle_ingame_options_input(msg)

            self.print_ingame_figure_choice()
            msg = input(">> ")
            figure = self.handle_ingame_figure_choice_input(msg)
            
            tlv = add_tlv_tag(tlv_tag, figure)
            sendTlv(self.sock, tlv)
            server_ans = recvTlv(self.sock)        # maybe each header of server response should contain OK/FAIL
            if TLV_OK_TAG in server_ans:
                print(server_ans[TLV_OK_TAG])
                break
    
    def send_roll_command(self):
        """Send roll dice command to the server and anticipate positive response with roll result"""
        while True:
            tlv = add_tlv_tag(TLV_ROLLDICE_TAG, self.nickname)
            sendTlv(self.sock, tlv)
            server_ans = recvTlv(self.sock)        # maybe each header of server response should contain OK/FAIL
            if TLV_OK_TAG in server_ans:
                print("You rolled {}".format(server_ans[TLV_OK_TAG]))
                return server_ans[TLV_OK_TAG]    

    def set_nickname(self):
        """Send nickname to the sever and anticipate positive response"""
        while True:
            nickname = input("Your nickname: ")
            if not nickname:
                continue
            tlv = add_tlv_tag(TLV_NICKNAME_TAG, nickname)
            sendTlv(self.sock, tlv)
            server_ans = recvTlv(self.sock)        # maybe each header of server response should contain OK/FAIL
            if TLV_OK_TAG in server_ans:
                print(server_ans[TLV_OK_TAG])
                return nickname

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
                server_ans = recvTlv(self.sock)

                if TLV_OK_TAG in server_ans:    # positive response
                    client_logger.debug(server_ans[TLV_OK_TAG])
                    print("Server answer: ", server_ans[TLV_OK_TAG])
                    break
                if TLV_FAIL_TAG in server_ans:
                    client_logger.debug(server_ans[TLV_FAIL_TAG])
                    print("Server answer: ", server_ans[TLV_FAIL_TAG])

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

    def print_options(self):
        interface_msg = """
        1. GET_ROOMS : get information about room status
        2. GET_USER_INFO : get information about your status
        3. START : start a game, available only if you joined a room with at least other player
        4. HELP : print options
        """
        print(interface_msg)

    def handle_ingame_options_input(self, msg):
        if msg.upper().strip() in ["1", "MOVE_FIGURE"]:
            return TLV_MOVEFIGURE_TAG
        elif msg.upper().strip() in ["2", "PLACE_FIGURE"]:
            return TLV_PLACEFIGURE_TAG
        elif msg.upper().strip() in ["0", "EXIT"]:
            self.handle_exit_command()

    def print_ingame_options(self):
        interface_msg = """
        1. MOVE_FIGURE : move figure
        2. PLACE_FIGURE : place figure
        0. EXIT : leave game
        """
        print(interface_msg)

    def handle_ingame_figure_choice_input(self, msg):
        if msg.upper().strip() in ["1"]:
            return "1"
        elif msg.upper().strip() in ["2"]:
            return "2"
        elif msg.upper().strip() in ["3"]:
            return "3"
        elif msg.upper().strip() in ["4"]:
            return "4"
        elif msg.upper().strip() in ["0", "EXIT"]:
            self.handle_exit_command()

    def print_ingame_figure_choice(self):
        interface_msg = """
        1. Figure 1
        2. Figure 2
        3. Figure 3
        4. Figure 4
        0. EXIT : leave game
        """
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


def rcv_response(validate):
    def recv(s):
        msg = recvText(s)
        if validate(msg):
            pass

    return recv


if __name__ == "__main__":
    # remote server address
    HOST = '127.0.0.1'
    PORT = 65432

    MAXLINE = 1024
    cli = ClientDGA()
    cli.init()
    cli.connect(HOST, PORT)
    cli.run()