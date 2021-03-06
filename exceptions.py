class Error(Exception):
    """ Base class for custom exceptions """
    pass


class MaxReachedException(Error):
    """ Raised when max numbers of rooms / clients have been reached """
    pass


class WrongRNumException(Error):
    pass


class ClearClientException(Error):
    """ Called to inform that client disconnected and server should remove connection from database """
    pass


class YouAreAloneException(Error):  # !TODO change name
    pass


class UnsubscribeException(Error):
    pass

class UnknownTagException(Error):
    """ Called if unknown tag is received """
    pass