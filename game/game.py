import random
from classes import Board, Player
from logger_conf import logger, reveal_name


class Game:

    def __init__(self, player_amount, field_amount):
        self.field_amount = field_amount
        self.player_amount = player_amount
        self.game_board = Board(player_amount, field_amount)

    def roll(self):
        """
        method to roll the dice, returns the dice eye
        """
        return random.randint(1, 6)

    def start_game(self):
        no_winner = True
        players = []
        for i in range(self.player_amount):
            player = Player("Player-{}".format(i), "Color-{}".format(i))
            self.game_board.register_player(player)
            players.append(player)

        # game loop
        logger.info("Starting new game")
        while no_winner:
            for player in players:
                # increment player turns
                player.turns += 1
                logger.info("Player {}, Turn {}:".format(player.name, player.turns))
                logger.debug("Player data before turn: start figures: {},  finished figures: {}".format(
                    reveal_name(player.start_figures), reveal_name(player.finished_figures)))
                # grab players figures from cemetery
                player.grab_figures_from_cemetery(self.game_board)
                # check for player's figures on board
                if player.has_figures_on_board(self.game_board):
                    if self.roll() == 6 and len(player.start_figures) != 0:
                        player.place_figure(self.game_board)
                    player.move_figure(self.game_board, self.roll())
                # player has no figure on board
                else:
                    # three chances to roll a 6
                    for i in range(3):

                        if self.roll() == 6:
                            # place new figure
                            player.place_figure(self.game_board)
                            # move figure
                            player.move_figure(self.game_board, self.roll())
                            break
                # count finished figures to evaluate win condition
                finished_figures = [figure for figure in player.finished_figures if hasattr(figure, "name")]
                if len(finished_figures) == 4:
                    no_winner = False
                    logger.info("Player {} won the game after {} turns!".format(player.name, player.turns))
                    break

                logger.debug("Player data after turn: start figures: {}, finished figures: {}".format(
                    reveal_name(player.start_figures), reveal_name(player.finished_figures)))
                # debug output of board fields
                logger.debug("Board fields after turn: {}".format(reveal_name(self.game_board.fields)))


game = Game(4, 40)
game.start_game()
