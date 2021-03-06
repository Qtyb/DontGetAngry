from settings import LENGTH_LEN, PADDING_CHAR, LIST_DELIMITER
from game.logger_conf import network_logger
from pytlv.TLV import *
import socket

# TLV
TLV_NICKNAME_TAG = '0001'
TLV_ROOM_TAG = '0002'

# notifications
TLV_OK_TAG = '1111'
TLV_FAIL_TAG = '1112'
TLV_ROLLDICERESULT_TAG = '1113'

TLV_INFO_TAG = '0100'   # msg to print
TLV_GET_ROOMS = '3000'
TLV_GET_USERINFO = '3001'

TLV_START_MSG = '5000'
TLV_STARTED_TAG = '5001'
TLV_FINISHED_TAG = '5002'
TLV_NEWTURN_TAG = '5003'
TLV_ROLLDICE_TAG = '5010'
TLV_MOVEORPLACE_TAG = '5012'
TLV_PLACEFIGURE_TAG = '5013'
TLV_MOVEFIGURE_TAG = '5014'

TLV_OPTION_PUT = "6000"
TLV_OPTION_MOVE = "6001"
TLV_OPTION_SKIP = "6002"

TLV_TAGS = [TLV_NICKNAME_TAG, TLV_ROOM_TAG, TLV_ROLLDICE_TAG, TLV_NEWTURN_TAG, TLV_PLACEFIGURE_TAG, TLV_MOVEFIGURE_TAG, TLV_INFO_TAG, TLV_OK_TAG, TLV_FAIL_TAG,
            TLV_ROLLDICERESULT_TAG, TLV_GET_ROOMS, TLV_START_MSG, TLV_STARTED_TAG, TLV_FINISHED_TAG, TLV_MOVEORPLACE_TAG, TLV_GET_USERINFO,
            TLV_OPTION_PUT, TLV_OPTION_MOVE, TLV_OPTION_SKIP]

# TLV END

def create_msg(msg):
    data_len = len(msg) if msg is not None else 0
    header_len = 10
    header = f"{data_len :< {header_len}}"
    # msg_enc = msg.encode("utf-8")
    created_msg = header + msg
    network_logger.debug("created message: " + created_msg)
    return created_msg

def sendText(sock, msg):
    msg = msg.encode("utf-8")
    msg_len = len(msg)
    totalsent = 0
    while totalsent < msg_len:
        sent = sock.send(msg[totalsent:])
        if sent == 0:   # socket has been closed
            raise RuntimeError("socket connection broken")
        totalsent += sent


def recvall(sock, n):
    """Read n bytes from socket. Returns binary message. Raise EOFError if socket has been closed"""
    msg = b''
    while len(msg) < n:
        try:
            chunk = sock.recv(n - len(msg))
        except BlockingIOError:
            network_logger.error("BlockingIO Exception")
            return b""
        if not chunk:
            raise EOFError("socket closed while reading data")
        msg += chunk

    return msg

def recvText(sock):
    msg_len = (recvall(sock, LENGTH_LEN).decode("utf-8"))
    network_logger.debug("msg len: " + msg_len)
    msg_len = int(msg_len)
    return recvall(sock, msg_len).decode("utf-8")


# TLV functions
def create_tlv():
   return TLV(TLV_TAGS)

def isTlvMsgValid(msg):
    if PADDING_CHAR in msg:
        return False

    return True

def add_tlv_padding(msg):
    if divmod(len(msg), 2)[1] == 1:
        msg = PADDING_CHAR + msg

    return msg

def remove_tlv_padding(msg):
    return msg.replace(PADDING_CHAR, "")

def add_tlv_tag(tag, msg, tlv = None):
    if isTlvMsgValid(msg) == False:
        raise Exception("Message", msg, "contains | sign. It is not valid tlv message")

    msg = add_tlv_padding(msg)

    if tlv == None:
        tlv = create_tlv()

    tlv.build({tag: msg})
    return tlv
    
def build_tlv_with_tags(data_dict):
    tlv = create_tlv()

    parsed_dict = {}
    for tag, value in data_dict.items():
        if isinstance(value, list):
            value = serialize_list(value)
        parsed_dict[tag] = add_tlv_padding(value)

    network_logger.debug("Build tlv with dictionary after padding: {}".format(parsed_dict))
    
    tlv.build(parsed_dict)
    return tlv

def sendTlv(sock, tlv):
    message_to_send = tlv.tlv_string
    network_logger.debug("Sending TLV: " + message_to_send)

    sendText(sock, create_msg(message_to_send))  

def recvTlv(sock):      # !TODO handle EOFError
    msg_len = (recvall(sock, LENGTH_LEN).decode("utf-8"))
    network_logger.debug("msg len: " + msg_len)
    msg_len = int(msg_len)
    msg = recvall(sock, msg_len).decode("utf-8")
    tlv = create_tlv()
    network_logger.debug("recvTlv msg: " + msg)
    parsed_msg = tlv.parse(msg)
    for key, value in parsed_msg.items():
        parsed_msg[key] = remove_tlv_padding(value)

    return parsed_msg

def get_types(tlv_msg):
    """Return list of tlv message tags"""
    return list(tlv_msg.keys())


def is_ok_answer(ans):
    return True if TLV_OK_TAG in ans else False
# TLV functions


def is_ipv4(addr):
    """ Checks if address is ipv4 """
    try:
        socket.inet_pton(socket.AF_INET, addr)
    except OSError:
        return False
    return True


def is_ipv6(addr):
    """ Checks if address is ipv6 """
    try:
        socket.inet_pton(socket.AF_INET6, addr)
    except OSError:
        return False
    return True


def is_valid_port(port):
    try:
        if 0 < int(port) < 65536:
            return True
        return False
    except ValueError:
        return False


def serialize_list(l):
    """ list -> string (PADDING_CHAR delimiter)"""
    return f"{LIST_DELIMITER}".join(l)


def deserialize_list(string):
    """ string -> list (PADDING_CHAR split)"""
    return string.split(LIST_DELIMITER)
