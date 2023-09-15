#!/usr/bin/python3
import jsockets
import sys
import time, random

def calc():
    # demoro un tiempo entre 0 y 3 s
    time.sleep(random.random()*3.0)
    return 20

# main
if len(sys.argv) != 2:
    print('Use: '+sys.argv[0]+' port')
    sys.exit(1)

s = jsockets.socket_tcp_bind(int(sys.argv[1]))

if s is None:
    print(f'could not open socket {sys.argv[1]}')
    sys.exit(1) 
    
while True:
    conn, addr = s.accept()
    print('Connected by', addr)
    conn.send(str(calc()).encode('UTF-8'))
    print(addr, 'result sent')
    conn.close()