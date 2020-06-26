from game.logger_conf import logger, reveal_name
from game.figure import Figure


class Board:
    """
    a class that represents the Game board
    recommended player_amount is 4-6
    field_amount needs to be an even number, original game amount for 4 players is 40
    """

    def __init__(self, player_amount, field_amount):
        self.field_amount = field_amount
        self.fields = ["0"] * field_amount
        self.player_amount = player_amount
        self.players = []
        self.players_start_pos = []
        self.next_start_index = 0
        self.figure_cemetery = []

    def register_player(self, player):
        """
        method to register a new player
        """
        # only register unknown players
        if player.id not in self.players:
            # register player id
            player.id = player.name
            self.players.append(player.id)
            # set player number
            player.no = len(self.players) - 1
            # register player start pos
            self.players_start_pos.append(self.next_start_index)
            # increase start index for next player to register
            self.next_start_index += int(self.field_amount / self.player_amount)
            logger.info("registered player {}".format(player.id))

    def display_starting_position(self):
            position_view = "\n"
            index = 0
            #print("###################### display_starting_position: players: [{}], start_pos: [{}]  ##################".format(self.players, self.players_start_pos))
            for p in self.players:
                 position_view += "Player {} starting position: {} \n".format(p ,self.players_start_pos[index])
                 index += 1
            
            return position_view

    # !TODO all board fields should be numbered 0 .. len(board), pass starting position to the player
    def display_board(self):
        board_view = "\n"
        #print("Display board: " + str(self.fields))
        # for f in self.fields:
        #     if isinstance(f, Figure):
        #         f = str(f)
        #     else:
        #         f += '0'
        #
        #     board_view += "|{}".format(f)
        # board_view += "|\n"
        
        i = 0
        for f in self.fields:
            if isinstance(f, Figure):
                board_view += "|{}".format(str(f))
            elif i < 10:
                board_view += "|0{}".format(i)
            else:
                board_view += "|{}".format(i)
            i+=1
        board_view += "|\n"

        return board_view



