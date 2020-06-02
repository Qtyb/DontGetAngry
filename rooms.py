from settings import *
from exceptions import *
from threading_game import GameThread
from game.logger_conf import server_logger


class Room:

    def __init__(self, rnum):
        self.rnum = rnum
        self.room_members = []      # <Connection>
        self.game = None            # game instance
        self.lock = False

    def join(self, conn):        # CHANGE: raise Exception if room is full (previous: no check)
        """
        Add client to the room members list. Raise exception fi room is full.
        :param cli:     (Client)    : client
        :return:        (None)
        """
        if len(self) >= MAX_CLIENTS_PER_ROOM:
            raise MaxReachedException()

        self.room_members.append(conn)
        conn.cli.set_rnumber(self.rnum)
        server_logger.info(f"Client joined room: {str(conn.cli)}")

    def remove(self, conn):
        """  Tries to remove client from room """
        try:
            self.room_members.remove(conn)
        except ValueError:
            server_logger.warning("Client {} is not connected to the room nr: {}".format(str(conn.cli), self.rnum))

    def get_room_members(self):
        """ Returns list of room members """
        return self.room_members

    def is_empty(self):
        if not len(self):
            return True
        return False

    def start_game(self):
        if self.game is not None:
            server_logger.warning("Game already running")
            return False

        if len(self) < 2:
            server_logger.warning("Cannot create a game, need 2 or more players")
            return False

        server_logger.info("Starting game...")

        game = GameThread(self.room_members, self.rnum)    # !TODO player number exception
        game.start()
        return True



    def __len__(self):
        return len(self.room_members)

    def __str__(self):
        return "Room {}: {} / {} clients".format(self.rnum, len(self), MAX_CLIENTS_PER_ROOM)


class RoomManager:
    # !TODO setitem, getitem

    class __RoomManager:
        def __init__(self):     # init() is not a constructor
            self.rooms = {}     # rnum: Room

        def join_client(self, conn, rnum):
            """
            Handles both changing the room or creating a new one. Client that want to join/create a room should call it.
            :param conn:        (Connection)    : client connection with the server
            :param rnum:        (int)           : number of room
            :return:            (bool)          : True if operation was successful
            """
            # check if client had joined any room before
            if conn.cli.rnum > 0:
                self.rooms[conn.cli.rnum].remove(conn)

            # check if room exists
            if rnum in self.rooms.keys():
                try:
                    self.rooms[rnum].join(conn)      # change cli -> conn
                    return True
                except MaxReachedException:
                    server_logger.info("Room {} is full".format(rnum))
                    return False

            # if room of number rnum doesn't exist create a new one
            else:
                self.create_room(conn, rnum)     # join call create
                return True

        def create_room(self, conn, rnum):
            """
            Try to create a room. If max number of rooms reached than raise an Exception.
            If room already exist, return False
            :param conn:     (Connection)    : client connection
            :param rnum:    (int)       : room number
            :return:        (bool)      : True if creation was successful
            """
            if len(self.rooms) >= MAX_ROOMS:
                raise MaxReachedException()

            if rnum in self.rooms.keys():
                server_logger.warning("Room of the number {} already exists.".format(rnum))
                # self.join_client(cli, rnum)
                return False

            room = Room(rnum)
            room.join(conn)
            self.rooms[rnum] = room

        def close_room(self, rnum):
            if rnum not in self.rooms.keys():
                raise WrongRNumException()

            del self.rooms[rnum]

        def disconnect_client(self, conn):
            try:
                server_logger.debug(f"RM: Disconnect connection {repr(conn.cli)}")
                self.rooms[conn.cli.rnum].remove(conn)
                if self.rooms[conn.cli.rnum].is_empty():
                    server_logger.info("Close room {}".format(conn.cli.rnum))
                    del self.rooms[conn.cli.rnum]
            except KeyError:
                pass

        def get_all_cli_joined(self):
            """
            Get list of all the clients that joined room.
            :return:    (list)  : list of Client(s)
            """
            clients = [conn.cli for room in self.rooms.values() for conn in room.room_members]
            return clients

        def get_all_nicknames(self):
            nicknames = [conn.cli.name for room in self.rooms.values() for conn in room.room_members]
            return nicknames

        def get_rooms_description(self):
            """
            Returns string that describes number of game rooms and number of players
            in each room.
            """
            msg = "number of rooms created: {}".format(len(self.rooms))

            for rnum, room in self.rooms.items():
                msg += "\n"
                msg += str(room)
                msg += "\n"

            return msg

        # creates multiple instances - why?
        # def __len__(self):
        #     return len(self.rooms)

        def __str__(self):
            return self.get_rooms_description()

    instance = None

    def __new__(cls):  # constructor
        if not RoomManager.instance:
            RoomManager.instance = RoomManager.__RoomManager()
        return RoomManager.instance