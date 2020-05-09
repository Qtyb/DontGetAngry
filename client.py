from socket import socket, AF_INET, SOCK_STREAM
import time
from common import *
from pytlv.TLV import *

# remote server address
HOST = '127.0.0.1'
PORT = 65432

MAXLINE = 1024


s = socket(AF_INET, SOCK_STREAM)
s.connect((HOST, PORT))

data = s.recv(MAXLINE)
if not data:
    s.close()
    print("Server error")
print(str(data.decode("utf-8")))

# set player nickname
while True:
    nickname = input("Please set your nickname\n> ")
    print("NICK:", nickname)
    if nickname:
        break
    print("Try again")

tlv = add_tlv_tag(TLV_NICKNAME_TAG, nickname)
sendTlv(s, tlv)

# select room or create a new one
room = -1
while True:
    room = input("Create or select existing channel\n> ")
    try:
        int(room)
        break
    except ValueError:
        print("Try again")

sendText(s, create_msg(room))

try:
    while True:
        # read_socket, write_socket,
        msg = input("Enter msg: ")
        sendText(s, create_msg(msg))

except BrokenPipeError as e:
    print("Server error\nClosing...")
except KeyboardInterrupt:
    print("Closing...")
finally:
    s.close()

