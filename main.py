import sys
import signal
import socket
import struct
import select
import uuid
import random
import time

FORMAT = '!b16s'
ADDRFORMAT = '!BBBBh'
CHILD = 0
MSG = 1
LEFT = 2
PARENT = 3
ROOT = 4
GOODMSG = 5

port = 3000
sock = None
thread = None

root = False
parent = None
children = []
me = None
percent_loss = 0

timestamps = []

def create_message(msg_type: int, stamp: bytes) -> bytes:
    return struct.pack(FORMAT, msg_type, stamp)

def exit_handler(arg1, arg2):
    print()
    print("LOG: Saying goodbye.")
    if not root:
        send_info(LEFT, parent)

    if len(children) > 0:
        if root:
            new_parent = children[0]
            send_info(ROOT, new_parent)
        else:
            new_parent = parent
        for child in children:
            if child != new_parent:
                send_data(PARENT, pack_addr(new_parent), child)
                send_data(CHILD,  pack_addr(child), new_parent)
    sys.exit(0)

def send_info(msg_type, addr, code = uuid.uuid4().bytes):
    msg = create_message(msg_type, code)
    send_mes(msg_type, msg, code, addr)

def send_data(msg_type, data, addr, code = uuid.uuid4().bytes):
    msg = create_message(msg_type, code) + data
    send_mes(msg_type, msg, code, addr)

def send_mes(msg_type, msg, code, addr):
    timestamps.append((msg_type, msg, code, addr, time.time()))
    sock.sendto(msg, addr)

def uniq_mess_count():
    global timestamps
    msg = {}
    for tmp in timestamps:
        if tmp[0] == MSG:
            msg[tmp[1]] = 1
    print(len(msg))
    return len(msg)

def read_and_send_message():

    msg_body = str(input()).encode("utf8")

    if uniq_mess_count() > 9:
        print("LOG: Too many messages in processing.")
        return

    code = uuid.uuid4().bytes

    if not root:
        send_data(MSG, msg_body, parent, code)
    for child in children:
        send_data(MSG, msg_body, child)

def recv_message():
    global parent
    global root
    global percent_loss

    received, addr = sock.recvfrom(1024)


    header = received[:17]
    data = received[17:]
    recv = struct.unpack(FORMAT, header)
    type = recv[0]
    code = recv[1]

    if random.randrange(0,99,1) < percent_loss and type != GOODMSG:
        return

    if type == MSG and uniq_mess_count() > 9:
        print("LOG: Buffer overflowed, pack lost")
        return

    if type != GOODMSG:
        send_info(GOODMSG, addr, code)
    
    if type == MSG:
        print("Message from {0}: {1}".format(addr, str(data.decode("utf8"))))
        for child in children:
            if child != addr:
                send_data(MSG, data, child, code)
        if not root and parent != addr:
            send_data(MSG, data, parent, code)

    elif type == GOODMSG:
        print("LOG: Recved confirmation of sending from {0}".format(addr))
        for tmp in timestamps:
            print (tmp[2] == code)
            print (tmp[3], addr, me)
            if tmp[2] == code and tmp[3] == addr:
                print("INTSDFSDJFKLS")
                timestamps.remove(tmp)

    elif type == CHILD:
        children.append(unpack_addr(data))
        print("LOG: New child at {0}".format(addr))
        print("Children:")
        for child in children:
            print("Child at {0}".format(child))

    elif type == PARENT:
        parent = unpack_addr(data)
        print("LOG: New parent at {0}".format(addr))

    elif type == LEFT:
        print("LOG: Received LEFT message from {0}".format(addr))
        if addr in children:
            children.remove(addr)
            print("LOG: Child removed")

    elif type == ROOT:
        root = True
        parent = None
        print("LOG: I'm root now.")
    else:
        print("LOG: You will never see me.")

def pack_addr (addr):
    comps = [int(part) for part in addr[0].split('.')]
    return struct.pack(ADDRFORMAT, comps[0],comps[1],comps[2], comps[3],addr[1])

def unpack_addr(packed):
    tmp = struct.unpack(ADDRFORMAT, packed)
    return ("{0}.{1}.{2}.{3}".format(tmp[0],tmp[1],tmp[2],tmp[3]), tmp[4])

def check_and_resend(curr_time):
    for tmp in timestamps:
        if curr_time - tmp[4] > 1:
            sock.sendto(tmp[1],tmp[3])
            timestamps.append((tmp[0],tmp[1],tmp[2],tmp[3],curr_time))
            timestamps.remove(tmp)


if __name__ == "__main__":

    if len(sys.argv) != 5 || len(sys.argv) != 3:
        print("Usage: port_to_bind percent_of_message_losing (parent_host parent_port)")
        sys.exit(0)
        
    port = int(sys.argv[1])
    percent_loss = int(sys.argv[2])
    root = True
    if len(sys.argv) == 5:
        parent = (sys.argv[-2], int(sys.argv[-1]))
        root = False

    signal.signal(signal.SIGINT, exit_handler)

    sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    sock.bind(('', port))
    me = (socket.gethostbyname(socket.gethostname()), port)

    print("Hello! I'm {0}".format(me))

    if not root:
        send_data(CHILD, pack_addr(me), parent)
        print("Sending hello to parent")
    inputs = [sock, sys.stdin]
    outputs = []
        
    last_time = curr_time = time.time()

    while True:

        readable, writable, exceptional = select.select(inputs, outputs, inputs, 1)
        if sys.stdin in readable:
            read_and_send_message()
        if sock in readable:
            recv_message()
        curr_time = time.time()
        if curr_time - last_time > 1:
            print(1)
            check_and_resend(curr_time)
            last_time = curr_time
