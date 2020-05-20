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


connection_list = {}   # all sockets handled by server


class DontGetAngryServer:

    def __init__(self, host, port):
        self.HOST = host
        self.PORT = port
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
            connection_list[self.srv_socket] = SERVER_FLAG
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
                # print(connection_list)
                read_sockets, _, _ = select.select(list(connection_list.keys()), [], [])     # !TODO change to poll()
                # print("READ SOCKETS: ", read_sockets)
                for sock in read_sockets:
                    if sock is self.srv_socket:
                        # accept new connection
                        self.accept_connection()
                    else:
                        try:
                            connection_list[sock].handle_msg2()
                            # print("AFTER HANDLING MSG: ", self.room_manager)
                            # print("[MSG] From {} : {}".format(str(self.connection_list[sock]), recvText(sock)))
                        except (EOFError, OSError, ClearClientException) as e:
                            print("[ERROR] Error while handling message: ", str(e))
                            self.client_disconnect(sock)
                        except ValueError as e:
                            print("[ERROR] Unknown tag received")
                        except UnsubscribeException:
                            print("[ERROR] Received Clear Client Exception")
                            unsubscribe_client(sock)

        except KeyboardInterrupt:
            self.close_server()

    def client_disconnect(self, sock):
        print(f"[INFO] Client {connection_list[sock].cli} disconnected")
        self.room_manager.disconnect_client(connection_list[sock])
        del connection_list[sock]
        sock.close()

    def close_server(self):
        """ Close all open sockets """
        print("Clossing...")
        for sock in connection_list.keys():
            sock.close()
        # self.srv_socket.close()
        sys.exit(1)

    def accept_connection(self):
        csock, addr = self.srv_socket.accept()
        cli = Client(csock, addr)
        conn = Connection(cli, csock)
        connection_list[csock] = conn        # change cli -> cli_conn
        print(f"Connection from: {addr}")
        # self.send_welcome_msg(csock)

    def send_welcome_msg(self, sock):
        welcome_msg = "***Welcome to the server!***\n" +\
                        self.room_manager.get_rooms_description() +\
                        "\nYou can join or create room within the range 0 .. 9"
        sendText(sock, welcome_msg)  # TODO handle socket broken


def unsubscribe_client(sock):
    del connection_list[sock]


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
        self.cli = cli
        self.sock = cli_sock
        self.room_manager = RoomManager()       # singleton
        self.state = INIT
        self.received_tlv = None
        self.msg_handlers = {
            TLV_NICKNAME_TAG: self.recv_nickname,
            TLV_ROOM_TAG: self.recv_room,
            TLV_GET_ROOMS: self.send_room_info,
            TLV_START_MSG: self.recv_start,
            TLV_ROLLDICE_TAG: self.recv_roll
        }

    def handle_msg2(self):
        self.received_tlv = recvTlv(self.sock)
        print(self.received_tlv)
        msg_types = get_types(self.received_tlv)
        for type in msg_types:
            try:
                self.msg_handlers[type]()
            except KeyError as e:
                print("[ERROR] cannot parse {}: {}".format(type, e))

    def recv_nickname(self):
        """Receive nickname from client, raise OSError if error occurs"""
        nickname = remove_tlv_padding(self.received_tlv[TLV_NICKNAME_TAG])
        print("[INFO] Nickname received:", nickname)
        self.cli.set_nickname(nickname)
        self.snd_notification(TLV_OK_TAG, self.get_welcome_message())

    def recv_room(self):
        """
        Try to join or create an room. Returns msg that should be send to the client.
        :return:    (str)   : msg that describe if operation was successful
        """
        rnum = remove_tlv_padding(self.received_tlv[TLV_ROOM_TAG])
        try:
            rnum = int(rnum)
        except ValueError:
            print("[ERROR] Wrong room number: {}".format(rnum))
            self.snd_notification(TLV_FAIL_TAG)
            return

        if self.room_manager.join_client(self, rnum):
            self.snd_notification(TLV_OK_TAG, "You have joined room {}".format(rnum))
        else:
            self.snd_notification(TLV_FAIL_TAG, "Error while joining the room {}".format(rnum))

    def recv_msg(self):
        """ Receive text message from a client """
        msg = recvText(self.sock)
        if not msg:     # client closed connection
            self.room_manager.disconnect_client(self)
            raise ClearClientException()
        print("[MSG] From {} : {}".format(str(self.cli), msg))
        return msg

    def recv_start(self):
        room = self.room_manager.rooms[self.cli.rnum]
        if not room.start_game():
            self.snd_notification(TLV_INFO_TAG, "SERVER: Cannot start a game\n")
            return
        # !TODO check for bug when client is handled by a thread and server has not unsubribed yet
        for conn in room.room_members:
            print(f"[INFO] Client {str(conn.cli)} unsubscribed")
            unsubscribe_client(conn.sock)

    def recv_roll(self):    # !TODO connection reset handling
        """Can raise ValueError"""
        roll = remove_tlv_padding(self.received_tlv[TLV_ROLLDICE_TAG])
        return int(roll)

    def recv_err(self):
        pass

    def snd_notification(self, flag, msg=""):       # handle OSError on higher level!
        """Send message that contains control message"""
        tlv = add_tlv_tag(flag, msg)
        sendTlv(self.sock, tlv)

    def send_room_info(self):
        tlv = add_tlv_tag(TLV_INFO_TAG, self.room_manager.get_rooms_description())
        sendTlv(self.sock, tlv)

    def get_welcome_message(self):
        msg = "\n****Welcome, you have connected to the server****\n" + self.room_manager.get_rooms_description()
        return msg


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
