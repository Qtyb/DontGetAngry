import threading
import select
from settings import *
from common import *
from game.game import Game
from game.logger_conf import logger, reveal_name


NROLLS = 3


class GameThread(threading.Thread):

    def __init__(self, connections, rnum):
        threading.Thread.__init__(self)
        self.connections = connections      # clients Connection
        self.rnum = rnum     # we need it to close the room
        self.nplayers = len(connections)
        self.running = False
        self.sorted_rolls = None
        self.received_tlv = None
        self.send_game_started()
        self.msg_handlers = {
            TLV_ROLLDICE_TAG: self.rcv_rol_dice,
            TLV_PLACEFIGURE_TAG: self.rcv_place_figure,
            TLV_MOVEFIGURE_TAG: self.rcv_move_figure
        }
        self.place_figure = None
        self.move_figure = None
        self.roll_command = None
        self.roll = None

        self.next_player = 0
        player_names = []
        for i in connections:
            player_names.append(i.cli.name) 

        print("player_names: {}".format(player_names))
        self.game = Game(player_names, 24) #Board should scale but will not, because it is not important :)

    def run(self):
        try:
            self.running = True
            self.snd_msg_to_all(self.get_game_status())
            self.game.start_game()
            # self.create()
            while self.running:
                for player in self.game.players:
                    self.clear_before_turn()
                    self.send_new_turn_started(player.name)
                    self.game.start_player_turn(player)
                    roll = self.wait_dice_message()
                    if player.has_figures_on_board(self.game.game_board):
                        if roll == 6 and len(player.start_figures) != 0:
                            ### PLAYER CAN DECIDE HERE
                            player_wants_moving = self.wait_move_or_place_figure()
                            if player_wants_moving:
                                player.move_figure(self.game.game_board, roll)
                            else:
                                player.place_figure(self.game.game_board)
                        else:
                            player.move_figure(self.game.game_board, roll)

                    # player has no figure on board
                    else:
                        # three chances to roll a 6
                        for i in range(3):
                            if self.game.try_place_figure(player):
                                break
                            
                if(self.game.is_player_winner(player)):
                    logger.info("Player {} wdevon the game after {} turns!".format(player.name, player.turns))
                    break

                logger.debug("Player data after turn: start figures: {}, finished figures: {}".format(
                    reveal_name(player.start_figures), reveal_name(player.finished_figures)))
                # debug output of board fields
                logger.debug("Board fields after turn: {}".format(reveal_name(self.game.game_board.fields)))

        except (EOFError, OSError) as e:
            print("[ERROR-GAME] Error while handling message: ", str(e))
            self.close_all()
            return
        except ValueError as e:
            print("[ERROR] Unknown tag received")
     
    def wait_move_or_place_figure(self):
        while self.running:
            self.wait_for_message()
            if self.place_figure is not None:
                return True
            if self.move_figure is not None:
                return False
    
    def wait_dice_message(self):
        while self.running:
            self.wait_for_message()
            if self.roll is not None:
                self.roll = None
                return self.roll

    def wait_for_message(self):
        connection_list = [conn.sock for conn in self.connections]
        read_sockets, _, _ = select.select(connection_list, [], [])  # !TODO change to poll()

        for sock in read_sockets:
            self.handle_msg(sock)

    def rcv_place_figure(self):
        print("place figure received")

    def rcv_move_figure(self):
        print("move figure received")

    def rcv_rol_dice(self):
        print("rcv_rol_dice invoked")
        self.roll = self.game.roll_d6()
        print("player roll: {}".format(self.roll))
        # update game status

    def snd_msg_to_all(self, msg):
        """Send message to all connected players"""
        print("[SEND ALL] msg: {}".format(msg))
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

    def send_new_turn_started(self, player_name):
        print("send_new_turn_started for player {}".format(player_name))
        for conn in self.connections:
            conn.snd_notification(TLV_NEWTURN_TAG, player_name)#{}\n".format(self.game.game_board.display_board()))

    def send_game_started(self):
        for conn in self.connections:
            conn.snd_notification(TLV_STARTED_TAG, "\n*****Game Started*****\n")

    def clear_before_turn(self):
        self.place_figure = None
        self.move_figure = None

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