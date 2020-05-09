import socket
import sys
from common import *
from settings import *
import select
from exceptions import *
from rooms import RoomManager


def is_ipv4(addr):
    """ Checks if address is ipv4 """
    try:
        socket.inet_pton(socket.AF_INET, addr)
    except OSError:
        return False
    return True


def is_ipv6( addr):
    """ Checks if address is ipv6 """
    try:
        socket.inet_pton(socket.AF_INET6, addr)
    except OSError:
        return False
    return True


def is_valid_port(port):
    if 0 < int(port) < 65536:
        return True
    return False


class DontGetAngryServer:

    def __init__(self, host, port):
        self.HOST = host
        self.PORT = port
        self.connection_list = {}   # all sockets handled by server
        # self.rooms = {}
        # self.nrooms = 0
        self.room_manager = RoomManager()
        print(id(self.room_manager))
        # self.next_room_number = 0
        self.init_server()
        self.bind_server()
        self.listen_server()
        self.run()

    def init_server(self):
        """ Create server socket. """

        if self.HOST == "":
            family = socket.AF_INET6
        elif is_ipv4(self.HOST):
            family = socket.AF_INET
        elif is_ipv6(self.HOST):
            family = socket.AF_INET6
        else:
            print(f"[ERROR] Wrong host address {self.HOST}")
            sys.exit(1)

        try:
            self.srv_socket = socket.socket(family, socket.SOCK_STREAM)
            self.srv_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.srv_socket.setblocking(False)
        except OSError as e:
            print(f"[ERROR] Socket creation error: {str(e)}")
            sys.exit(1)

    def bind_server(self):
        """
        Bind (ip_addr, port) to server socket. If you do not specify a host address then
        server will bind to all ip addresses.
        """
        try:
            self.srv_socket.bind((self.HOST, self.PORT))
            self.connection_list[self.srv_socket] = SERVER_FLAG
        except OSError as e:
            print(f"[ERROR] Bind socket error: {str(e)}")
            self.close_server()

    def listen_server(self):
        self.srv_socket.listen(BACKLOG)
        sockinfo = self.srv_socket.getsockname()
        print(f"Listinig on {sockinfo} ...")

    def run(self):
        try:
            while True:
                connection_list = list(self.connection_list.keys())
                # print(connection_list)
                read_sockets, write_sockets, error_sockets = select.select(connection_list, [], [])     # !TODO change to poll()
                # print("READ SOCKETS: ", read_sockets)
                for sock in read_sockets:
                    if sock is self.srv_socket:
                        # accept new connection
                        self.accept_connection()
                    else:
                        # !TODO handle client msg (if msg_type == CREATE_ROOM ...)
                        try:
                            self.connection_list[sock].handle_msg()
                            # print("AFTER HANDLING MSG: ", self.room_manager)
                            # print("[MSG] From {} : {}".format(str(self.connection_list[sock]), recvText(sock)))
                        except EOFError:
                            self.client_disconnect(sock)
                        except ClearClientException:
                            print("[ERROR] Received Clear Client Exception")
                            self.client_disconnect(sock)

        except KeyboardInterrupt:
            self.close_server()

    def client_disconnect(self, sock):
        print(f"[INFO] Client {self.connection_list[sock].cli} disconnected")
        del self.connection_list[sock]
        sock.close()

    def close_server(self):
        """ Close all open sockets """
        print("Clossing...")
        for sock in self.connection_list.keys():
            sock.close()
        # self.srv_socket.close()
        sys.exit(1)

    def accept_connection(self):
        csock, addr = self.srv_socket.accept()
        cli = Client(csock, addr)
        conn = Connection(cli, csock)
        self.connection_list[csock] = conn        # change cli -> cli_conn
        print(f"Connection from: {addr}")
        self.send_welcome_msg(csock)

    def send_welcome_msg(self, sock):
        welcome_msg = "***Welcome to the server!***\n" +\
                        self.room_manager.get_rooms_description() +\
                        "\nYou can join or create room within the range 0 .. 9"
        sendText(sock, welcome_msg)  # TODO handle socket broken


class Client:

    def __init__(self, conn, addr):
        self.sd = conn
        self.addr = addr
        self.name = "Unknown"
        self.rnum = -1

    def set_nickname(self, nickname):
        self.name = nickname

    def set_rnumber(self, rnum):
        self.rnum = rnum

    def __str__(self):
        return self.name + " " + str(self.addr) + " room: " + str(self.rnum)


class Connection:
    """
    Controls connection state. Created in order to save the state of the initialization process
    (i.e. first few messages: nickname, join/create room)
    """

    def __init__(self, cli, cli_sock):
        """"""
        self.cli = cli
        self.sock = cli_sock
        self.room_manager = RoomManager()       # singleton
        self.state = INIT

    def handle_msg(self):
        print("[DEBUG] state: {}".format(self.state))
        if self.state == INIT:
            if not self.recv_nickname():
                raise ClearClientException()

        elif self.state == NICKNAME_RECEIVED:
            if not self.recv_room():
                raise ClearClientException()

        elif self.state == ROOM_JOINED:
            if not self.recv_msg():
                raise ClearClientException()
        else:
            self.recv_err()

    def recv_nickname(self):
        received_tlv = recvTlv(self.sock)
        nickname = remove_tlv_padding(received_tlv[TLV_NICKNAME_TAG])
        print("[INFO] Nickname received:", nickname)
        self.cli.set_nickname(nickname)
        self.state = NICKNAME_RECEIVED
        return True

    def recv_room(self):
        """
        Try to join or create an room. Returns msg that should be send to the client.
        :return:    (str)   : msg that describe if operation was successful
        """
        rnum = int(recvText(self.sock))
        if self.room_manager.join_client(self.cli, rnum):
            # print("[RECV_ROOM]", self.room_manager.get_rooms_description())
            self.state = ROOM_JOINED
            # return "You have joined room nr {} ".format(rnum)       # !TODO enum class with all of the messages
            return True
        else:
            # return "Error occurs while joining the room number {}. Try again".format(rnum)
            return False

    def recv_msg(self):
        msg = recvText(self.sock)
        if not msg: # client closed connection
            self.room_manager.disconnect_client(self.cli)
            return False
        print("[MSG] From {} : {}".format(str(self.cli), msg))
        return True

    def recv_err(self):
        pass


if __name__ == "__main__":
    addr = INADDR_ANY
    port = DEFAULT_PORT

    if len(sys.argv) == 3:
        addr = sys.argv[1]

        if addr in ["*", "-", "::", ""]:
            addr = INADDR_ANY
        port = sys.argv[2]

        if not is_valid_port(port):
            print(f"[ERROR] Wrong port: {port}")
            sys.exit(1)
        port = int(port)

    elif len(sys.argv) == 2:
        addr = sys.argv[1]


    serverDGA = DontGetAngryServer(addr, port)
