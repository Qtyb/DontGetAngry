import socket
import sys
from common import *
from settings import *
import select
from exceptions import *
from rooms import RoomManager
from game.logger_conf import server_logger
import daemon


connection_list = {}   # all sockets handled by server


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


def get_all_nicknames():
    print(connection_list.values())
    nicknames = [conn.cli.name for conn in connection_list.values() if isinstance(conn, Connection)]
    print(nicknames)
    return nicknames


class DontGetAngryServer:

    def __init__(self, host, port):
        self.HOST = host
        self.PORT = port
        self.room_manager = RoomManager()
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
            server_logger.error(f"Wrong host address {self.HOST}")
            sys.exit(1)

        try:
            self.srv_socket = socket.socket(family, socket.SOCK_STREAM)
            self.srv_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.srv_socket.setblocking(False)
        except OSError as e:
            server_logger.error(f"Socket creation error: {str(e)}")
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
            server_logger.error(f"Bind socket error: {str(e)}")
            self.close_server()

    def listen_server(self):
        self.srv_socket.listen(BACKLOG)
        sockinfo = self.srv_socket.getsockname()
        server_logger.info(f"Listinig on {sockinfo} ...")

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
                            server_logger.error(f"Error while handling message: {str(e)}")
                            self.client_disconnect(sock)
                        except ValueError as e:
                            server_logger.error(f"Unknown tag received")
                        except UnsubscribeException:
                            server_logger.debug(f"Received Clear Client Exception")
                            unsubscribe_client(sock)

        except KeyboardInterrupt:
            self.close_server()

    def client_disconnect(self, sock):
        server_logger.info(f"Client {connection_list[sock].cli} disconnected")
        self.room_manager.disconnect_client(connection_list[sock])
        del connection_list[sock]
        sock.close()

    def close_server(self):
        """ Close all open sockets """
        server_logger.info("Closing...")
        for sock in connection_list.keys():
            sock.close()
        # self.srv_socket.close()
        sys.exit(1)

    def accept_connection(self):
        """ Accept new connection. Create new Connection and add it to connection list."""
        csock, addr = self.srv_socket.accept()
        cli = Client(csock, addr)
        conn = Connection(cli, csock)
        connection_list[csock] = conn        # change cli -> cli_conn
        server_logger.info(f"Connection from: {addr}")

    def send_welcome_msg(self, sock):
        welcome_msg = "***Welcome to the server!***\n" +\
                        self.room_manager.get_rooms_description() +\
                        "\nYou can join or create room within the range 0 .. 9"
        sendText(sock, welcome_msg)  # TODO handle socket broken


def unsubscribe_client(sock):
    """ Remove sock descriptor from connection list. Select will not be longer waiting for the events on that socket """
    del connection_list[sock]


class Client:

    def __init__(self, conn, addr):
        self.sd = conn          # socket
        self.addr = addr        # (ip_addr, port)
        self.name = "Unknown"   # nickname
        self.rnum = -1          # room number

    def set_nickname(self, nickname):
        self.name = nickname

    def set_rnumber(self, rnum):
        self.rnum = rnum

    def __repr__(self):
        return self.name + " " + str(self.addr) + " room: " + str(self.rnum)

    def __str__(self):
        return f"\nNickname: {self.name}\nConnected to the room: {self.rnum}"


class Connection:
    """
    Represents connection between server and client. Handles communication between server and client.
    """

    def __init__(self, cli, cli_sock):
        self.cli = cli
        self.sock = cli_sock
        self.room_manager = RoomManager()
        self.state = INIT
        self.received_tlv = None
        self.msg_handlers = {
            TLV_NICKNAME_TAG: self.recv_nickname,
            TLV_ROOM_TAG: self.recv_room,
            TLV_GET_ROOMS: self.send_room_info,
            TLV_START_MSG: self.recv_start,
            TLV_ROLLDICE_TAG: self.recv_roll,
            TLV_GET_USERINFO: self.send_userinfo
        }

    def handle_msg2(self):
        """Reads next TTL message from the socket and saves TTL value that indicate type of message to
        internal variable. Next it calls handler for every TLL in message in order to handle the messages"""
        self.received_tlv = recvTlv(self.sock)
        server_logger.debug(f"Received TTL: {self.received_tlv}")
        msg_types = get_types(self.received_tlv)
        for type in msg_types:
            try:
                self.msg_handlers[type]()
            except KeyError as e:
                server_logger.error("Cannot parse {}: {}".format(type, e))

    def recv_nickname(self):
        """Receive nickname from client, raise OSError if error occurs"""
        nickname = remove_tlv_padding(self.received_tlv[TLV_NICKNAME_TAG])
        if nickname in get_all_nicknames():
            server_logger.debug(f"Nickname already exists: {nickname}")
            self.snd_notification(TLV_FAIL_TAG, "Nickname already exists")
            return

        server_logger.debug(f"Nickname received: {nickname}")
        self.cli.set_nickname(nickname)
        self.snd_notification(TLV_OK_TAG, self.get_welcome_message())

    def recv_room(self):
        """
        Try to join or create an room. Returns msg that should be send to the client.
        """
        rnum = remove_tlv_padding(self.received_tlv[TLV_ROOM_TAG])
        # check if number is an integer greater than 0
        try:
            rnum = int(rnum)
            if rnum < 1:
                raise ValueError()
        except ValueError:
            server_logger.warning("Wrong room number: {}".format(rnum))
            self.snd_notification(TLV_FAIL_TAG, "You can join/create a room only with positive number!")
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
        server_logger.debug("Msg from {} : {}".format(repr(self.cli), msg))
        return msg

    def recv_start(self):
        room = self.room_manager.rooms[self.cli.rnum]
        if not room.start_game():
            self.snd_notification(TLV_INFO_TAG, "\nCannot start a game\n")
            return

        for conn in room.room_members:
            server_logger.info(f"Client {repr(conn.cli)} unsubscribed")
            unsubscribe_client(conn.sock)

    def recv_roll(self):    # !TODO connection reset handling
        """Can raise ValueError"""
        roll = remove_tlv_padding(self.received_tlv[TLV_ROLLDICE_TAG])
        return int(roll)

    def snd_notification(self, flag, msg=""):       # handle OSError on higher level!
        """Send message that contains control message"""
        tlv = add_tlv_tag(flag, msg)
        sendTlv(self.sock, tlv)

    def send_room_info(self):
        tlv = add_tlv_tag(TLV_INFO_TAG, self.room_manager.get_rooms_description())
        sendTlv(self.sock, tlv)

    def send_userinfo(self):
        tlv = add_tlv_tag(TLV_INFO_TAG, str(self.cli))
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
            server_logger.error(f"Wrong port: {port}")
            sys.exit(1)
        port = int(port)

    elif len(sys.argv) == 2:
        addr = sys.argv[1]

    # with daemon.DaemonContext():
    serverDGA = DontGetAngryServer(addr, port)
