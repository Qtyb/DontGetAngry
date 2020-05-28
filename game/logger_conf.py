import logging
import sys
from logging.handlers import TimedRotatingFileHandler


FORMATTER = logging.Formatter("%(asctime)s — %(name)s — %(levelname)s — %(message)s")
LOG_FILE = "log_files/game.log"
SERVER_LOG_FILE = "log_files/server.log"

def get_console_handler():
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(FORMATTER)
    return console_handler


def get_file_handler():
    file_handler = TimedRotatingFileHandler(LOG_FILE, when='midnight')
    file_handler.setFormatter(FORMATTER)
    return file_handler


def get_logger(logger_name):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(get_console_handler())
    logger.addHandler(get_file_handler())
    logger.propagate = False
    return logger


def setup_logger(logger_name, log_file, level=logging.INFO):
    handler = logging.FileHandler(log_file)
    handler.setFormatter(FORMATTER)

    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    logger.addHandler(handler)
    logger.addHandler(get_console_handler())

    return logger


# function to reveal player name on game board, used for logging
def reveal_name(list):
    new_list = []
    for item in list:
        if hasattr(item, "name"):
            new_list.append(item.name)
        else:
            new_list.append(item)
    return new_list


logger = get_logger("game")
server_logger = setup_logger("server", SERVER_LOG_FILE, level=logging.DEBUG)
