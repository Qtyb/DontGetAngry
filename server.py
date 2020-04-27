import socket
import sys
from settings import *
import select


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

def mysend(sock, msg):
    msg = msg.encode("utf-8")
    msg_len = len(msg)
    totalsent = 0
    while totalsent < msg_len:
        sent = sock.send(msg[totalsent:])
        if sent == 0:   # socket has been closed
            raise RuntimeError("socket connection broken")
        totalsent += sent

def myrecv(sock):
    # msg_type = recvall(sock, TYPE_LEN).decode("utf-8")
    msg_len = int(recvall(sock, LENGTH_LEN).decode("utf-8"))
    # TODO handle different types of msgs
    return recvall(sock, msg_len).decode("utf-8")

def recvall(sock, n):
    """Read n bytes from socket. Returns binary message."""
    msg = b''
    while len(msg) < n:
        try:
            chunk = sock.recv(n - len(msg))
        except BlockingIOError:
            print("BlockingIO Exception")
            return b""
        if not chunk:
            raise EOFError("[ERROR] socket closed while reading data")
        msg += chunk

    return msg

class DontGetAngryServer:

    def __init__(self, host, port):
        self.HOST = host
        self.PORT = port
        self.connection_list = {}   # all sockets handled by server
        self.rooms = {}
        self.nrooms = 0
        self.next_room_number = 0
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
            self.srv_socket.setblocking(0)
        except OSError as e:
            print(f"[ERROR] Socket cretion error: {srt(e)}")
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
                read_sockets, write_sockets, error_sockets = select.select(connection_list, [], [])
                # print("READ SOCKETS: ", read_sockets)
                for sock in read_sockets:
                    if sock is self.srv_socket:
                        # accept new connection
                        self.accept_connection()
                    else:
                        # !TODO handle client msg (if msg_type == CREATE_ROOM ...)
                        try:
                            print("[MSG] From {} : {}".format(str(self.connection_list[sock]), myrecv(sock)))
                        except EOFError:
                            self.client_disconnect(sock)

        except KeyboardInterrupt:
            self.close_server()

    def client_disconnect(self, sock):
        print(f"[INFO] Client {self.connection_list[sock]} disconnected")
        cli = self.connection_list[sock]

        # remove client from rooms he joined
        for rnum, room in self.rooms.items():
            if cli in room.get_room_members():
                room.remove_member(cli)
                # if room.is_empty():
                #     print("[INFO] Remove empty room")
                #     del self.rooms[rnum]

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
        conn, addr = self.srv_socket.accept()
        cli = Client(conn, addr)
        self.connection_list[conn] = cli
        print(f"Connection from: {addr}")
        self.send_welcome_msg(conn)
        # !TODO check for duplicates, maybe create interface class to communicate with client
        # get nickname
        nickname = myrecv(conn)
        cli.set_nickname(nickname)

        # get room number from the client
        rnum = int(myrecv(conn))
        if rnum in self.rooms.keys():   # room already exists
            self.rooms[rnum].join(cli)
        else:
            self.create_room(rnum)
            self.rooms[rnum].join(cli)

    def send_welcome_msg(self, sock):
        welcome_msg = "***Welcome to the server!***\n" +\
                        self.get_room_information() +\
                        "\nYou can join or create room within the range 0 .. 9"
        mysend(sock, welcome_msg)  # TODO handle socket broken

    def get_room_information(self):
        """
        Returns string that decribes number of game rooms and number of players
        in each room.
        """
        msg = "number of rooms created: {}".format(self.nrooms)

        for rnum, room in self.rooms.items():
            msg += "\n"
            msg += str(room)
            msg += "\n"

        return msg

    def create_room(self, rnum):
        """ Create new room for a game. Returns False if max number of rooms reached """
        # !TODO MAX ROOM reached handler

        r = Room(rnum)
        self.rooms[rnum] = r
        print(f"[INFO] Room {rnum} created!")

    def clear_empty_rooms(self):
        """ Delete rooms with 0 memebrs """
        pass


class Client:

    def __init__(self, conn, addr):
        self.sd = conn
        self.addr = addr
        self.name = "Unknown"
        self.rnumber = -1

    def set_nickname(self, nickname):
        self.name = nickname

    def set_rnumber(self, rnum):
        self.rnumber = rnum

    def __str__(self):
        return self.name + ", " + str(self.addr)

class Room:

    def __init__(self, room_number):
        """"""
        self.rnumber = room_number
        self.room_members = []

    def join(self, cli):
        self.room_members.append(cli)
        cli.set_rnumber(self.rnumber)
        print(f"Client {str(cli)} has joined room nr {self.rnumber}")

    def remove_member(self, cli):
        self.room_members.remove(cli)

    def get_room_members(self):
        return self.room_members

    def is_empty(self):
        if not len(self):
            return True
        return False

    def __len__(self):
        return len(self.room_members)

    def __str__(self):
        return "Room {}: {} / {} clients".format(self.rnumber, len(self), MAX_CLIENTS_PER_ROOM)



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
