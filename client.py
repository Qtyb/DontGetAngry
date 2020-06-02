from socket import socket, AF_INET, SOCK_STREAM, timeout
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
        sys.exit()

    def run(self):
        try:
            self.set_nickname()
            self.set_room()
            self.running = True
            read_thread = threading.Thread(target=self.read_loop)
            read_thread.daemon = True
            read_thread.start()
            self.print_options()
            while self.running:
                if self.game_started:
                    print("GAME flag is set") # !TODO handle game
                msg = input(">> ")
                if not msg:   # enter pressed
                    continue
                self.handle_input(msg)
        except KeyboardInterrupt:
            client_logger.error("Keyboard interrupt")
        except OSError as e:
            client_logger.error("Server error: " + str(e))
        except Exception as e:
            client_logger.error("Exception: " + str(e))
        finally:
            self.running = False
            self.close_flag = True
            self.close()
            sys.exit(-1)

    def read_loop(self):        # !TODO timeout to signal
        """ Thread that reads messages sending by the server. """
        self.sock.settimeout(1)
        while True:
            try:
                server_ans = recvTlv(self.sock)
                self.handle_answer(server_ans)
                # if not server_ans:
                #     print("[ERROR] Server error")
            except timeout:
                if self.close_flag:
                    client_logger.debug("Close flag")
                    return
            except (OSError, EOFError, KeyboardInterrupt, ChangeStateException) as e:
                client_logger.error("Error while reading data: " + str(e))
                return

    def handle_answer(self, ans):
        """
        Handle response from the server. It can change state of the client e.g. game started or
        just print received information.
        ans     (dict)  : TLV: str
        """
        if TLV_STARTED_TAG in ans:
            self.game_started = True

        if TLV_INFO_TAG in ans:
            print("\n" + remove_tlv_padding(ans[TLV_INFO_TAG]))

    def set_nickname(self):
        """Send nickname to the server and anticipate positive response"""
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

    def handle_input(self, msg):
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