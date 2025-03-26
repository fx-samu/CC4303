#!/usr/bin/python3
from scapy import all as sc
import argparse as ap
import logging as lg
import time as tm

PAYLOAD = " |{PWNED BY H4CK5.py}| "
TIMEOUT = 60
FLOOD = False

sc.conf.L3socket=sc.L3RawSocket
sc.conf.verb = 0

lg.basicConfig(level=lg.DEBUG, format='[%(asctime)s.%(msecs)03d | %(levelname).3s @ %(lineno)03d] %(message)s', datefmt='%H:%M:%S')
def inject_packet(origin: str, origin_port: int, destination: str, destination_port: int, payload: str, socket: sc.socket = None):
    packet = sc.IP(src=origin, dst=destination)/sc.UDP(sport=origin_port, dport=destination_port)/payload
    socket = socket or sc.conf.L3socket()
    if FLOOD: 
        socket.send(packet)
    else:
        sc.send(packet)
    pass 

def argument_parser() -> ap.Namespace:
    global FLOOD
    parser = ap.ArgumentParser(description="H4CK5.py - A simple UDP packet injection tool")
    parser.add_argument('origin', type=str, help="The origin IP address")
    parser.add_argument('origin_port', type=int, help="The origin port")
    parser.add_argument('destination', type=str, help="The destination IP address")
    parser.add_argument('destination_port', type=int, help="The destination port")
    pass
    parser.add_argument('--payload', type=str, help="The payload to be sent", default=PAYLOAD)
    parser.add_argument('-t', '--timeout', type=int, help="The time to end the injections", default=TIMEOUT)
    parser.add_argument('-f', '--flood', action='store_true', help="Flood the destination with packages warning: this is a test feature")
    args = parser.parse_args()
    FLOOD = args.flood
    
    if not 0 <= args.origin_port <= 65535:
        parser.error("Invalid origin port")
    
    if not 0 <= args.destination_port <= 65535:
        parser.error("Invalid destination port")
        
    return args
    
def main():
    args = argument_parser()
    i = 0
    end = tm.time() + args.timeout
    sock = sc.conf.L3socket()
    while tm.time() < end:
        payload = (f'D{i:02d}{args.payload}')
        try:
            inject_packet(args.origin, args.origin_port, args.destination, args.destination_port, payload, socket=sock)
        except Exception as e:
            lg.error(f'Error while sending packet: {e}')
        i = (i+1)%100
    
    if FLOOD:
        for i in range(100):
            payload = (f'E{i:02d}{args.payload}')
            try:
                inject_packet(args.origin, args.origin_port, args.destination, args.destination_port, payload, socket=sock)
            except Exception as e:
                lg.error(f'Error while sending packet: {e}')
if __name__ == '__main__':
    main()