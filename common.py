from settings import LENGTH_LEN
from pytlv.TLV import *

# TLV
TLV_NICKNAME_TAG = '0001'
TLV_TAGS = [TLV_NICKNAME_TAG]
# TLV END

def create_msg(msg):
    data_len = len(msg) if msg is not None else 0
    header_len = 10
    header = f"{data_len :< {header_len}}"
    print("header: " + header)
    msg_enc = msg.encode("utf-8")
    return header + msg

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
    """Read n bytes from socket. Returns binary message."""
    msg = b''
    while len(msg) < n:
        try:
            chunk = sock.recv(n - len(msg))
        except BlockingIOError:
            print("BlockingIO Exception")
            return b""
        if not chunk:
            raise EOFError("[ERROR] socket closed while reading data")
        msg += chunk

    return msg

def recvText(sock):
    # msg_type = recvall(sock, TYPE_LEN).decode("utf-8")
    msg_len = int(recvall(sock, LENGTH_LEN).decode("utf-8"))
    # TODO handle different types of msgs
    return recvall(sock, msg_len).decode("utf-8")

# TLV functions
def create_tlv():
   return TLV(TLV_TAGS)

def isTlvMsgValid(msg):
    if "|" in msg:
        return False

    return True

def add_tlv_padding(msg):
    if divmod(len(msg), 2)[1] == 1:
        msg = "|" + msg

    return msg

def remove_tlv_padding(msg):
    return msg.replace("|", "")

def add_tlv_tag(tag, msg, tlv = None):
    if isTlvMsgValid(msg) == False:
        raise Exception("Message", msg, "contains | sign. It is not valid tlv message")

    msg = add_tlv_padding(msg)

    if tlv == None:
        tlv = create_tlv()

    tlv.build({tag: msg})
    return tlv

def sendTlv(sock, tlv):
    message_to_send = tlv.tlv_string
    print("Sending TLV:", message_to_send)

    sendText(sock, create_msg(message_to_send))  

def recvTlv(sock):
    msg_len = int(recvall(sock, LENGTH_LEN).decode("utf-8"))
    msg = recvall(sock, msg_len).decode("utf-8")

    tlv = create_tlv()
    parsed_msg = tlv.parse(msg)
    print("parsed recvTLV: ", parsed_msg)

    return parsed_msg  

# TLV functions



