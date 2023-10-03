#!/usr/bin/python3

"""
    IMPORTS
"""

import socket, jsockets
import sys, random, logging, time
from abc import ABC, abstractmethod
 
"""
    CONSTANTS
"""

N_TRIES_STABLISH_PROTOCOL = 100
 
"""
    REQUIRED CODE TO BE USED
""" 

def send_loss(s, data, loss_rate):
    # Envia un paquete con loss_rate porcentaje de perdida
    # si loss_rate = 5, implica un 5% de perdida
    if random.random() * 100 > loss_rate:
        s.send(data)
    else:
        logging.debug("[send_loss]")

def recv_loss(s, size, loss_rate):
    # Recibe un paquete con loss_rate porcentaje de perdida
    # Si decide perderlo, vuelve al recv y no retorna aun
    # Retorna None si hay timeout o error
    try:
        while True:
            data = s.recv(size)
            if random.random() * 100 <= loss_rate:
                logging.debug("[recv_loss]")
            else:
                break
    except socket.timeout:
        print('timeout', file=sys.stderr)
        data = None
    except socket.error:
        print('recv err', file=sys.stderr)
        data = None
    return data


""" 
    IMPLEMENTATION
"""

logging.basicConfig(level=logging.INFO, format='[%(asctime)s.%(msecs)03d | %(levelname).3s @ %(lineno)03d] %(message)s', datefmt='%H:%M:%S')

file_handler = logging.FileHandler('final.log')
logging.getLogger().addHandler(file_handler)

class UdpConnectionInterface(ABC):
    
    @abstractmethod
    def send(self, data: bytes) -> None:
        pass
    
    @abstractmethod
    def recive(self, size: int) -> bytes:
        pass

class UdpConnection(UdpConnectionInterface):
    
    def __init__(self, address: str, port: int):
        self._address   = address
        self._port      = port
        
        self._socket = jsockets.socket_udp_connect(self._address, self._port)
        if self._socket is None:
            logging.error(f'Could not open UdpConnection')
            sys.exit(1)
    
    def send(self, data: bytes) -> None:
        self._socket.send(data)
    
    def recive(self, size: int) -> bytes:
        return self._socket.recv(size)

class UdpToyConnection(UdpConnectionInterface):
    
    def __init__(self, address: str, port: int, loss_rate: float = 0.0, timeout: float = 0.0):
        self._address   = address
        self._port      = port
        self._loss_rate = loss_rate
        self._timeout   = timeout
        
        self._socket = jsockets.socket_udp_connect(self._address, self._port)
        if self._socket is None:
            logging.error(f'Could not open UdpToyConnection')
            sys.exit(1)
        self._socket.settimeout(self._timeout)
    
    def __str__(self) -> str:
        return f'UDPTC [{self._address}:{self._port}]'
    
    def send(self, data: bytes) -> None:
        logging.debug(f'{self} >> {data}')
        send_loss(self._socket, data, self._loss_rate)
    
    def recive(self, size: int) -> bytes:
        recived = recv_loss(self._socket, size, self._loss_rate)
        log_msg = f"{str(recived):.20} (... {len(recived)} ...)\'" if len(recived) > 20 else recived
        logging.debug(f'{self} << {log_msg}')
        return recived

def get_args() -> tuple:
    logging.debug(f'sys.argv = {sys.argv}')
    
    if len(sys.argv) != 8:
        logging.error(f'Use: {sys.argv[0]} pack_sz nbytes timeout loss fileout host port')
        sys.exit(1)
        
    package_size, n_bytes, timeout, loss_rate, file_out, host, port = sys.argv[1:]
    
    if any(not x.isdigit() for x in [package_size, n_bytes, timeout, loss_rate, port]):
        logging.error(f'Use: {sys.argv[0]} pack_sz nbytes timeout loss fileout host port')
        sys.exit(1)
        
    package_size, n_bytes, timeout, loss_rate, port = map(int, [package_size, n_bytes, timeout, loss_rate, port])
    file_out, host = map(str, [file_out, host])
    
    return package_size, n_bytes, timeout, loss_rate, file_out, host, port

def stablish_protocol(udp_connection: UdpConnectionInterface, n_bytes: int, sv_timeout_ms: int, proposed_package_size: int) -> int:
    logging.debug(f'Init stablisish protocol')
    for i in range(N_TRIES_STABLISH_PROTOCOL):
        try:
            udp_connection.send(f"C{proposed_package_size:04d}{sv_timeout_ms:04d}".encode())
            logging.info(f'propouse paquete: {proposed_package_size}')
            in_msg  = udp_connection.recive(8).decode()
            package_size = int(in_msg[1:5])
            logging.info(f'recibo paquete: {package_size}')
            udp_connection.send(f"N{n_bytes}".encode())
            in_msg  = udp_connection.recive(package_size)
            in_msg  = in_msg.decode()
            if in_msg[0] != 'D': 
                raise Exception(f'Invalid data message, expected data got {in_msg[0]}')
            logging.info(f'Protocol stablisished, data is being received')
            logging.info(f'recibiendo {n_bytes} nbytes')
            return package_size
            
        except Exception as e:
            logging.error(f'Error in stablisish protocol: {e}')
            logging.error(f'Retrying... ({i+1})')
    logging.critical(f'Could not stablish protocol after {N_TRIES_STABLISH_PROTOCOL} tries')
    sys.exit(1)

def bandwith_stop_and_wait(udp_connection: UdpConnectionInterface, package_size: int, file_out: str) -> None:
    logging.info(f'Init bandwith stop and wait stress test')
    start_time = time.time()
    fdout = open(file_out, 'w')
    i = 0
    errors = 0
    try:
        while True:
            in_msg = udp_connection.recive(package_size).decode()
            if in_msg[0] == "E":
                n_package = int(in_msg[1:3])
                udp_connection.send(f"A{n_package:02d}".encode())
                break
            elif in_msg[0] != 'D':
                raise Exception(f'Invalid data message, expected data got {in_msg[0]}')
            else:
                n_package = int(in_msg[1:3])
                if n_package != i:
                    errors += 1
                    logging.debug(f'Package {n_package} received out of order, expected {i}, discarding and acknowledging last package')
                    udp_connection.send(f"A{n_package:02d}".encode())
                    continue
                udp_connection.send(f"A{i:02d}".encode())
                i = (1+i) % 100
                fdout.write(in_msg[3:])
            
    except Exception as e:
        logging.error(f'Error in bandwith stop and wait stress test: {e}')
        sys.exit(1)
    
    logging.info(f'End of transmission')
    time_elapsed = time.time() - start_time 
    logging.info(f'bytes recibidos: {fdout.tell()}, \
time: {time_elapsed} s, \
bw = {(fdout.tell()) / (time_elapsed) / (1024*1024)} MB/s, \
errores = {errors}')

def main() -> None:
    package_size, n_bytes, sv_timeout_ms, loss_rate, file_out, host, port = get_args()
    
    connection = UdpToyConnection(host, port, loss_rate, 3)
    package_size = stablish_protocol(connection, n_bytes, sv_timeout_ms, package_size)
    bandwith_stop_and_wait(connection, package_size, file_out)

if __name__ == "__main__":
    main()