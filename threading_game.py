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
        self.roll = None

        self.next_player = 0
        self.current_player = None

        player_names = []
        self.player_name_to_connection = {}
        index = 0
        for i in connections:
            player_names.append(i.cli.name) 
            self.player_name_to_connection[i.cli.name] = index
            index += 1

        print("player_names: {}".format(player_names))
        self.game = Game(player_names, 24) #Board should scale but will not, because it is not important :)
        # print(self.game.game_board.display_board())

    def run(self):
        try:
            self.running = True
            self.snd_msg_to_all(self.get_game_status())
            self.game.start_game()
            # self.create()
            while self.running:
                for player in self.game.players:
                    self.clear_before_turn()
                    self.current_player = player
                    self.send_new_turn_started(player.name)
                    self.game.start_player_turn(player)
                    self.snd_player_status(player)

                    roll = self.wait_dice_message()
                    # refactoring
                    if self.skip_turn:  # player cannot move
                        continue
                    # -----------------
                    print("Player {} rolled {}".format(self.current_player.name, roll))
                    player_wants_place_figure = self.wait_want_place_figure()
                    if player_wants_place_figure:
                        print("Player {} chose to PLACE figure: {}".format(self.current_player.name, self.place_figure))
                    else:
                        print("Player {} chose to MOVE figure: {}".format(self.current_player.name, self.move_figure))

                    # if player.has_figures_on_board(self.game.game_board):
                    # print("Player {} has figures on board".format(player.name))
                    if roll == 6 and len(player.start_figures) != 0:
                        if player_wants_place_figure:
                            print("Player {} wants to place new figure".format(player.name))
                            player.place_figure(self.game.game_board)
                        else:
                            print("Player {} wants to move figure {}".format(player.name, self.move_figure))
                            player.move_figure(self.game.game_board, roll, self.move_figure)
                    else:
                        print("Player {} wants to move figure {}".format(player.name, self.move_figure))
                        player.move_figure(self.game.game_board, roll, self.move_figure)

                    # player has no figure on board
                    # else:
                    #     # three chances to roll a 6
                    #     print("Player {} has no figures".format(player.name))
                    #     for i in range(3):
                    #         if self.game.try_place_figure(player):
                    #             break
                            
                if(self.game.is_player_winner(player)):
                    logger.info("Player {} won the game after {} turns!".format(player.name, player.turns))
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
            print("[ERROR] Unknown tag received: {}".format(e))

    def wait_want_place_figure(self):
        print("Wait for place figure")
        while self.running:
            self.wait_for_message()
            if self.place_figure is not None:
                print("Place figure: true")
                return True
            print("Place figure: false")
            if self.move_figure is not None:
                return False

    def wait_dice_message(self):
        while self.running:
            self.wait_for_message()
            if self.roll is not None:
                rolled_value = self.roll
                self.roll = None
                return rolled_value

    def wait_for_message(self):
        connection_list = [conn.sock for conn in self.connections]
        read_sockets, _, _ = select.select(connection_list, [], [])  # !TODO change to poll()

        for sock in read_sockets:
            self.handle_msg(sock)

    def rcv_place_figure(self):
        self.place_figure = self.received_tlv[TLV_PLACEFIGURE_TAG]
        print("place figure received with data {}".format(self.place_figure))

    def rcv_move_figure(self):
        self.move_figure = self.received_tlv[TLV_MOVEFIGURE_TAG]
        print("move figure received with figure {}".format(self.move_figure))

    def rcv_rol_dice(self):
        print("rcv_rol_dice invoked")
        self.roll = self.game.roll_d6()
        print("player roll: {}".format(self.roll))

        print("rcv roll dice response to {}".format(self.current_player.name))
        connection_index = self.player_name_to_connection[self.current_player.name]
        print("rcv roll dice connection index is {}".format(connection_index))
        # self.connections[connection_index].snd_ack_notification(TLV_ROLLDICERESULT_TAG, str(self.roll))

        # refactoring
        tags_dict = self.get_roll_options_dict(self.roll, self.current_player)
        tags_dict[TLV_ROLLDICERESULT_TAG] = str(self.roll)
        self.connections[connection_index].snd_ack_dict_notification(tags_dict) # OK, ROLLDICERESULT, and options

        #for conn in self.connections:
        #    conn.snd_ack_notification(TLV_ROLLDICERESULT_TAG, str(self.roll))

        #self.send(self.player_name_to_connection[self.current_player.name].sock, TLV_ROLLDICERESULT_TAG, str(self.roll))
        # update game status

    def snd_msg_to_all(self, msg):
        """Send message to all connected players"""
        print("[SEND ALL] msg: {}".format(msg))
        for conn in self.connections:
            tlv = add_tlv_tag(TLV_INFO_TAG, msg)
            sendTlv(conn.sock, tlv)

    def snd_player_status(self, player):
        conn = self.connections[self.player_name_to_connection[player.name]]
        conn.snd_notification(TLV_INFO_TAG, self.game.get_player_status(player))
        logger.debug("Send player status notification")

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
            conn.snd_notification(TLV_NEWTURN_TAG, player_name) #{}\n".format(self.game.game_board.display_board()))

    def send_game_started(self):
        for conn in self.connections:
            conn.snd_notification(TLV_STARTED_TAG, "\n*****Game Started*****\n")

    def clear_before_turn(self):
        self.place_figure = None
        self.move_figure = None
        self.roll = None
        self.received_tlv = None

    def send(self, sock, tag, msg=""):       # handle OSError on higher level!
        """Send message that contains control message"""
        tlv = add_tlv_tag(tag, msg)
        sendTlv(sock, tlv)
        # print("message has been sent")

    def handle_msg(self, sock):
        if self.connections[self.next_player].sock == sock:
            print("[GAME] player {} move".format(self.next_player))
        else:
            print("[GAME] Special msg")
        self.received_tlv = recvTlv(sock)
        # print(self.received_tlv)
        msg_types = get_types(self.received_tlv)
        for type in msg_types:
            try:
                self.msg_handlers[type]()
            except KeyError as e:
                print("[ERROR] cannot parse {}: {}".format(type, e))

    def get_roll_options_dict(self, roll, player):
        """
        Based on roll and player game state returns dictionary of tags, that indicate
        player possible options. Values are the player figures associated with options.
        If option is SKIP then value is negligible.
        @param roll:        (int)       : d6 roll number
        @param player:      (Player)    : player instance
        @return:            (dict)      : option: figures
        """
        msg_tags = {}
        self.skip_turn = False
        if roll == 6:
            if player.has_figures_on_board(self.game.game_board):
                msg_tags[TLV_OPTION_MOVE] = player.get_figures_on_board()
            if player.has_starting_figure():
                msg_tags[TLV_OPTION_PUT] = player.get_starting_figures()
        else:
            if player.has_figures_on_board(self.game.game_board):
                msg_tags[TLV_OPTION_MOVE] = player.get_figures_on_board()
            else:
                msg_tags[TLV_OPTION_SKIP] = "."
                self.skip_turn = True

        return msg_tags