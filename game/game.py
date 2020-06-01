import random
from game.board import Board
from game.player import Player
from game.logger_conf import logger, reveal_name


class Game:

    def __init__(self, field_amount, player_names):
        self.player_names = player_names
        self.field_amount = field_amount
        self.game_board = Board(player_names.count(), field_amount)
        self.players = []
        self.no_winner = True

    def __game_flow_demo(self):
        self.start_game()
        while self.no_winner:
            for player in self.players:
                self.start_player_turn(player)
                if player.has_figures_on_board(self.game_board):
                    
                    roll = self.roll_d6()
                    if roll == 6 and len(player.start_figures) != 0:
                        ### PLAYER CAN DECIDE HERE
                        player_wants_moving = True
                        if player_wants_moving:
                            player.move_figure(self.game_board, roll)
                        else:
                            player.place_figure(self.game_board)
                    else:
                        player.move_figure(self.game_board, roll)

                # player has no figure on board
                else:
                    # three chances to roll a 6
                    for i in range(3):
                        if self.try_place_figure(player):
                            break
                        
                if(self.is_player_winner(player)):
                    logger.info("Player {} won the game after {} turns!".format(player.name, player.turns))
                    break

                logger.debug("Player data after turn: start figures: {}, finished figures: {}".format(
                    reveal_name(player.start_figures), reveal_name(player.finished_figures)))
                # debug output of board fields
                logger.debug("Board fields after turn: {}".format(reveal_name(self.game_board.fields)))

    def is_player_winner(self, player):
        finished_figures = [figure for figure in player.finished_figures if hasattr(figure, "name")]
        if len(finished_figures) == 4:
            return True
        return False

    def roll_d6(self):
        """
        method to roll 6 sided dice, returns the dice eye
        """
        self.roll = random.randint(1, 6)
        return self.roll

    def try_place_figure(self, player):
        if self.roll_d6() == 6:
            # place new figure
            player.place_figure(self.game_board)
            # move figure
            #player.move_figure(self.game_board, self.roll)
            logger.info("Player {} placed new figure".format(player.name))
            return True;
        return False;

    def start_player_turn(self, player):
        player.turns += 1
        logger.info("Player {}, Turn {}:".format(player.name, player.turns))
        logger.debug("Player data before turn: start figures: {},  finished figures: {}".format(reveal_name(player.start_figures), reveal_name(player.finished_figures)))
        logger.info(self.game_board.display_board())
        # grab players figures from cemetery
        player.grab_figures_from_cemetery(self.game_board)


    def start_game(self):
        for i in range(self.player_names):
            player = Player("P-{}".format(i), "Color-{}".format(i))
            self.game_board.register_player(player)
            self.players.append(player)

        # game loop
        logger.info("Starting new game")
