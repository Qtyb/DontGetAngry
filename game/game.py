from classes import Board, Player
from logger_conf import logger, reveal_name


def game(player_amount, field_amount):
    # game init
    no_winner = True

    game_board = Board(player_amount, field_amount)
    players = []
    for i in range(player_amount):
        player = Player("Player-{}".format(i), "Color-{}".format(i))
        game_board.register_player(player)
        players.append(player)

    # game loop
    logger.info("Starting new game")
    while no_winner:
        for player in players:

            # increment player turns
            player.turns += 1
            logger.info("Player {}, Turn {}:".format(player.name, player.turns))
            logger.debug("Player data before turn: start figures: {}, finished figures: {}".format(reveal_name(player.start_figures), reveal_name(player.finished_figures)))
            # grab players figures from cemetery
            player.grab_figures_from_cemetery(game_board)
            # check for player's figures on board
            if player.has_figures_on_board(game_board):
                if player.roll == 6 and len(player.start_figures) != 0:
                    player.place_figure(game_board)
                player.move_figure(game_board, player.roll)
            # player has no figure on board
            else:
                # three chances to roll a 6
                for i in range(3):
                    if player.roll == 6:
                        # place new figure
                        player.place_figure(game_board)
                        # move figure
                        player.move_figure(game_board, player.roll)
                        break
            # count finished figures to evaluate win condition
            finished_figures = [figure for figure in player.finished_figures if hasattr(figure, "name")]
            if len(finished_figures) == 4:
                no_winner = False
                logger.info("Player {} won the game after {} turns!".format(player.name, player.turns))
                break

            logger.debug("Player data after turn: start figures: {}, finished figures: {}".format(reveal_name(player.start_figures), reveal_name(player.finished_figures)))
            # debug output of board fields
            logger.debug("Board fields after turn: {}".format(reveal_name(game_board.fields)))



game(player_input, field_input)
