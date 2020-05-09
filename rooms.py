from settings import *
from exceptions import *

class Room:

    def __init__(self, rnum):
        self.rnum = rnum
        self.room_members = []

    def join(self, cli):        # CHANGE: raise Exception if room is full (previous: no check)
        """
        Add client to the room members list. Raise exception fi room is full.
        :param cli:     (Client)    : client
        :return:        (None)
        """
        if len(self) >= MAX_CLIENTS_PER_ROOM:
            raise MaxReachedException()

        self.room_members.append(cli)
        cli.set_rnumber(self.rnum)
        print(f"[INFO] Client joined room: {str(cli)}")

    def remove(self, cli):
        """  Tries to remove client from room """
        try:
            self.room_members.remove(cli)
        except ValueError:
            print("[WARNING] Client {} is not connected to the room nr: {}".format(str(cli), self.rnum))

    def get_room_members(self):
        """ Returns list of room members """
        return self.room_members

    def is_empty(self):
        if not len(self):
            return True
        return False

    def __len__(self):
        return len(self.room_members)

    def __str__(self):
        return "Room {}: {} / {} clients".format(self.rnum, len(self), MAX_CLIENTS_PER_ROOM)


class RoomManager:
    # !TODO setitem, getitem

    class __RoomManager:
        def __init__(self):     # init() is not a constructor
            self.rooms = {}     # rnum: Room

        def join_client(self, cli, rnum):
            """
            Handles both changing the room or creating a new one. Client that want to join/create a room should call it.
            :param cli:         (Client)    : client that wants to join/create room
            :param rnum:        (int)       : number of room
            :return:            (bool)      : True if operation was successful
            """
            # check if client had joined any room before
            if cli.rnum > 0:
                self.rooms[cli.rnum].remove(cli)

            # check if room exists
            if rnum in self.rooms.keys():
                try:
                    self.rooms[rnum].join(cli)
                    return True
                except MaxReachedException:
                    print("[ROOM MANAGER] Room {} is full".format(rnum))
                    return False

            # if room of number rnum doesn't exist create a new one
            else:
                self.create_room(cli, rnum)     # join call create
                return True

        def create_room(self, cli, rnum):
            """
            Try to create a room. If max number of rooms reached than raise an Exception.
            If room already exist, return False
            :param cli:     (Client)    : client
            :param rnum:    (int)       : room number
            :return:        (bool)      : True if creation was successful
            """
            if len(self.rooms) >= MAX_ROOMS:
                raise MaxReachedException()

            if rnum in self.rooms.keys():
                print("[WARNING] Room of the number {} already exists.".format(rnum))
                # self.join_client(cli, rnum)
                return False

            room = Room(rnum)
            room.join(cli)
            self.rooms[rnum] = room

        def close_room(self, rnum):
            if rnum not in self.rooms.values():
                raise WrongRNumException()

            room = self.rooms[rnum]
            if not room.is_empty():     # !TODO disconnect all clients and close room
                print("[WARNING] Cannot close room if clients are connected")

            del self.rooms[rnum]

        def disconnect_client(self, cli):
            self.rooms[cli.rnum].remove(cli)

        def get_all_cli_joined(self):
            """
            Get list of all the clients that joined room.
            :return:    (list)  : list of Client(s)
            """
            clients = [member for room in self.rooms.values() for member in room]
            return clients

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

    # Singleton pattern
    instance = None

    def __new__(cls):  # constructor
        if not RoomManager.instance:
            RoomManager.instance = RoomManager.__RoomManager()
        return RoomManager.instance