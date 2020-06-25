class Figure:
    def __init__(self, name):
        self.name = name
        self.distance_to_target = -1
        self.field = -1
        self.target_field = -1
        self.finish_slot = -1

    def place(self, board):
        """
        method to place a figure
        """
        self.distance_to_target = board.field_amount

    def move(self, move_amount):
        """
        method to move a figure
        """
        if self.distance_to_target - move_amount > 0:
            self.distance_to_target = self.distance_to_target - move_amount
        else: 
            print("Figure {} not moved because distance to target would be lesser than 1".format(self.name))

    def ban(self):
        """
        method to ban a figure
        """
        self.distance_to_target = -1
        self.field = -1
        self.target_field = -1

    def __str__(self):
        return self.name