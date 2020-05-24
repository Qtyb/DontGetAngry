from logger_conf import logger


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
            player.id = "{}-{}".format(player.name, player.color)
            self.players.append(player.id)
            # set player number
            player.no = len(self.players) - 1
            # register player start pos
            self.players_start_pos.append(self.next_start_index)
            # increase start index for next player to register
            self.next_start_index += int(self.field_amount / self.player_amount)
            logger.info("registered player {}".format(player.id))
