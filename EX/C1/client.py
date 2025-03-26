#!/usr/bin/python3

import jsockets
import sys, threading

return_value = []

class Client(threading.Thread):
    def __init__(self, addr, port):
        threading.Thread.__init__(self)
        self.addr = addr
        self.port = port

    def __str__(self):
        return f'Server [{self.addr}:{self.port}]'

    def run(self):
        sock = jsockets.socket_tcp_connect(self.addr, self.port)
        
        if sock is None:
            print(f'{self} could not open socket')
            return

        print(f'{self} connected')
        data = sock.recv(1024)
        print(f'{self} read {data}')
        sock.close()
        try:
            return_value.append(float(data.decode('UTF-8')))
        except:
            print(f'{self} could not convert data to float, unknown error')
# main
def main():
    if len(sys.argv) < 3 or len(sys.argv) % 2 != 1:
        print(f'Use: {sys.argv[0]} host port [host port] ...')
        sys.exit(1)

    addr, ports = sys.argv[1::2], sys.argv[2::2]
     
    for addr, port in zip(addr, ports):
        newthread = Client(addr, port)
        newthread.start()
    
    print('Waiting for threads to finish')
    for t in threading.enumerate():
        if t is not threading.current_thread():
            t.join()
    print('All threads finished')
    if len(return_value) > 0:
        print(f'Result: {sum(return_value)/len(return_value)}')
    else:
        print('No results')

if __name__ == "__main__":
    main()