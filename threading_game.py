import threading
from settings import *
from common import *
import select

NROLLS = 3


class GameThread(threading.Thread):

    def __init__(self, connections, rnum):
        threading.Thread.__init__(self)
        self.connections = connections      # clients Connection
        self.rnum = rnum     # we need it to close the room
        self.nplayers = len(connections)
        self.running = False
        self.current_player = None
        self.sorted_rolls = None
        self.received_tlv = None
        self.send_game_started()
        self.msg_handlers = {
            TLV_ROLLDICE_TAG: self.rcv_rol_dice
        }
        self.next_player = 0

    def run(self):
        try:
            self.running = True
            self.snd_msg_to_all(self.get_game_status())
            # self.create()
            while self.running:
                # print(self.connections)
                connection_list = [conn.sock for conn in self.connections]
                # print(connection_list)
                read_sockets, _, _ = select.select(connection_list, [], [])  # !TODO change to poll()

                for sock in read_sockets:
                    self.handle_msg(sock)
        except (EOFError, OSError) as e:
            print("[ERROR-GAME] Error while handling message: ", str(e))
            self.close_all()
            return
        except ValueError as e:
            print("[ERROR] Unknown tag received")


    def rcv_rol_dice(self):
        roll = int(self.received_tlv[TLV_ROLLDICE_TAG])
        print("player roll: {}".format(roll))
        # update game status

    def snd_msg_to_all(self, msg):
        """Send message to all connected players"""
        print("[SEND ALL]")
        for conn in self.connections:
            tlv = add_tlv_tag(TLV_INFO_TAG, msg)
            sendTlv(conn.sock, tlv)

    def get_game_status(self):
        running = "YES" if self.running else "NO"
        msg = """
            Game running: {}
            Number of players: {}
            """.format(running, self.nplayers)
        return msg

    def close_all(self):  # !TODO clear room
        """Close all the sockets"""
        print(self.connections)

        # conns = self.connections        # manager removes connections from room
        for conn in self.connections:       # !TODO wtf
            conn.sock.close()
        conn = self.connections[0]
        conn.room_manager.close_room(conn.cli.rnum)

    def send_game_started(self):
        for conn in self.connections:
            conn.snd_notification(TLV_STARTED_TAG, "\n*****Game Started*****\n")

    def handle_msg(self, sock):
        if self.connections[self.next_player].sock == sock:
            print("[GAME] player {} move".format(self.next_player))
        else:
            print("[GAME] Special msg")
        self.received_tlv = recvTlv(sock)
        print(self.received_tlv)
        msg_types = get_types(self.received_tlv)
        for type in msg_types:
            try:
                self.msg_handlers[type]()
            except KeyError as e:
                print("[ERROR] cannot parse {}: {}".format(type, e))