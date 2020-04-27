from socket import socket, AF_INET, SOCK_STREAM
import time
from server import myrecv, recvall, mysend


def create_msg(msg):
    data_len = len(msg) if msg is not None else 0
    header_len = 10
    header = f"{data_len :< {header_len}}"
    msg_enc = msg.encode("utf-8")
    return header + msg


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
nickname = input("Please set your nickname\n> ")
mysend(s, create_msg(nickname))

# select room or create a new one
room = -1
while True:
    room = input("Create or select existing channel\n> ")
    try:
        int(room)
        break
    except ValueError:
        print("Try again")

mysend(s, create_msg(room))

try:
    while True:
        # read_socket, write_socket,
        msg = input("Enter msg: ")
        mysend(s, create_msg(msg))

except BrokenPipeError as e:
    print("Server error\nClosing...")
except KeyboardInterrupt:
    print("Closing...")
finally:
    s.close()
