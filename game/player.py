from game.figure import Figure
from game.logger_conf import logger


class Player:
    """a class that represents a Player of the Board Game"""

    def __init__(self, name):
        self.name = name
        self.id = "undefined"
        self.figure_amount = 4
        self.figures = []
        self.start_figures = []
        self.finished_figures = ["0"] * 4
        self.turns = 0
        self.roll_turns = 0
        self.no = "undefined"
        self.amount_of_six = 0
        self.total_roll = 0
        self.real_playtime = 0

        # create start figures for player
        for x in range(4):
            figure = Figure("{}-{}".format(self.name, x))
            self.start_figures.append(figure)
            self.figures.append(figure)

    def has_figures_on_board(self, board):
        """
        method to check if player has figures on the board, returns boolean
        """
        for figure in self.figures:
            if figure in board.fields:
                return True

    def has_starting_figure(self):
        """ Returns True if player has figure to place onto the board """
        if len(self.start_figures) > 0:
            return True
        return False

    def get_figures_on_board(self):
        """ Returns list of figures names that are on game board """
        board_figures = []
        for figure in self.figures:
            if figure not in self.start_figures and figure not in self.finished_figures:
                board_figures.append(str(figure))
        return board_figures

    def get_starting_figures(self):
        """ Returns list of figures names that are at the starting position """
        return [str(fig) for fig in self.start_figures]


    def grab_figures_from_cemetery(self, board):
        """
        grab players figure(s) from the boards figure cemetery and reset them to figure start pit
        """
        # identify player's banned figures
        player_banned_figures = [figure for figure in board.figure_cemetery if self.name in figure.name]
        # in case there are any banned figures
        if len(player_banned_figures) != 0:
            for figure in player_banned_figures:
                # remove figure(s) from cemetery
                board.figure_cemetery.remove(figure)
                figure.ban()
                # reset figure(s) to start pit
                self.start_figures.append(figure)

    def place_figure(self, board):
        """
        method to place a new figure to the start position of a board
        """
        start_pos = board.players_start_pos[self.no]

        # in case start position blocked
        if hasattr(board.fields[start_pos], "name"):
            # remove foreign player figure
            board.figure_cemetery.append(board.fields[start_pos])
            logger.info(
                "Target field is blocked by foreign player! Banning figure {}!".format(board.fields[start_pos].name))
        removed_figure = self.start_figures.pop()
        removed_figure.place(board)
        board.fields[start_pos] = removed_figure

    def move_figure(self, board, move_amount, selected_figure):
        """
        method to select and move a player figure
        """

        # select figure
        # figure = self.figures[int(selected_figure)-1]
        figure = self.find_figure_by_name(selected_figure)
        for field in board.fields:
            if hasattr(field, "name"):
                if figure.name in field.name:
                    # set figure
                    figured = field
                    # get field of figure
                    figured.field = board.fields.index(figured)
                    # check if figure can finish
                    if figured.distance_to_target <= move_amount:
                        # determine free slots in finished_figures
                        free_slots = []
                        for i in range(len(self.finished_figures)):
                            if self.finished_figures[i] == "0":
                                free_slots.append(i)
                        for slot in free_slots:
                            if abs(figured.distance_to_target - move_amount) == slot:
                                figured.finish_slot = slot
                    else:
                        # calc target field  of figure
                        figured.target_field = figured.field + move_amount
                        # handle field loop
                        if figured.target_field > board.field_amount - 1:
                            diff = board.field_amount - figured.field
                            figured.target_field = move_amount - diff

        if figure != "undefined":
            # check if figure has possible finish slot
            if figure.finish_slot != -1:
                self.finish_figure(board, figure)
            else:
                # remove figure from old field
                board.fields[figure.field] = "0"
                # check if new field is blocked by another figure
                if hasattr(board.fields[figure.target_field], "name"):
                    # check if blocking figure owned by player
                    if self.name in board.fields[figure.target_field].name:
                        # keep player figure on old field
                        board.fields[figure.field] = figure
                        logger.info("Target field is blocked by player's own figure {}! Revert move!".format(
                            board.fields[figure.target_field].name))
                    else:
                        # remove foreign player figure
                        board.figure_cemetery.append(board.fields[figure.target_field])
                        logger.info("Target field is blocked by foreign player! Banning figure {}!".format(
                            board.fields[figure.target_field].name))
                        # move player figure to new field
                        figure.move(move_amount)
                        board.fields[figure.target_field] = figure
                else:
                    # move player figure to new field
                    figure.move(move_amount)
                    board.fields[figure.target_field] = figure

    def finish_figure(self, board, figure):
        board.fields[figure.field] = "0"
        self.finished_figures[figure.finish_slot] = figure
        logger.info("Player {} reached the finish with figure {}!".format(self.name, figure.name))

    def find_figure_by_name(self, fig_name):
        for fig in self.figures:
            if fig.name == fig_name:
                return fig

        raise Exception(f"Figure with name {fig_name} does not exists")
