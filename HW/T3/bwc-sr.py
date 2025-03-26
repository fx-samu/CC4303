#!/usr/bin/python3
import argparse
import logging
import time
import jsockets
import socket
import random
import sys
import math
from abc import ABC, abstractmethod

class CustomFormatter(logging.Formatter):
    green       = "\x1b[32;20m"
    cyan        = "\x1b[36;20m" 
    grey        = "\x1b[38;20m"
    yellow      = "\x1b[33;20m"
    red         = "\x1b[31;20m"
    bold_red    = "\x1b[31;1m"
    reset       = "\x1b[0m"
    format = "[%(levelname)-8s @ %(filename)10.10s:%(lineno)3d 󰥔 %(asctime)s]>\n%(message)s\n"
    FORMATS = {
        logging.DEBUG: cyan + format + reset,
        logging.INFO: green + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset
    }
    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)
    
logger = logging.getLogger("main")
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(CustomFormatter())
logger.addHandler(ch)
logger.addHandler(logging.FileHandler('output.log'))

N_TRIES_STABLISH_PROTOCOL = 2
WINDOW_SIZE = 50
MAX_FRAME = 100

class UdpConnectionInterface(ABC):
    """
    Inteface for UDP connection
    """
    
    @abstractmethod
    def send(self, data: bytes) -> None:
        pass
    
    @abstractmethod
    def recive(self, size: int) -> bytes:
        pass

def _send_loss(s, data, loss_rate):
    # Envia un paquete con loss_rate porcentaje de perdida
    # si loss_rate = 5, implica un 5% de perdida
    if random.random() * 100 > loss_rate:
        s.send(data)
    else:
        logger.warning("[send_loss]")

def _recv_loss(s, size, loss_rate):
    # Recibe un paquete con loss_rate porcentaje de perdida
    # Si decide perderlo, vuelve al recv y no retorna aun
    # Retorna None si hay timeout o error
    try:
        while True:
            data = s.recv(size)
            if random.random() * 100 <= loss_rate:
                logger.warning("[recv_loss]")
            else:
                break
    except socket.timeout:
        logger.error('[timeout]')
        data = None
    except socket.error:
        logger.error('[recv err]')
        data = None
    return data

class UdpToyConnection(UdpConnectionInterface):
    def __init__(self, address: str, port: int, loss_rate: float = 0.0, timeout: float = 0.0):
        self._address   = address
        self._port      = port
        self._loss_rate = loss_rate
        self._timeout   = timeout/1000
        
        self._socket = jsockets.socket_udp_connect(self._address, self._port)
        if self._socket is None:
            logger.error(f'Could not open UdpToyConnection')
            sys.exit(1)
        self._socket.settimeout(self._timeout)
    
    def __str__(self) -> str:
        return f'UDPTC [{self._address}:{self._port}]'
    
    def send(self, data: bytes) -> None:
        logger.debug(f'{self} <- {data}')
        _send_loss(self._socket, data, self._loss_rate)
    
    def recive(self, size: int) -> bytes:
        recived = _recv_loss(self._socket, size, self._loss_rate)
        if recived != None:
            log_msg = f"{str(recived):.20} (... +{len(recived)-20} ...)\'" if len(recived) > 20 else recived
            logger.debug(f'{self} -> {log_msg}')
        return recived

def stablish_protocol(udp_connection: UdpConnectionInterface, 
                      n_bytes: int, 
                      sv_timeout_ms: int, 
                      proposed_package_size: int
                      ) -> int:
    """
    Stablish protocol with server
    
    Args:
        udp_connection (UdpConnectionInterface): Connection interface used
        n_bytes (int): number of bytes to be received
        sv_timeout_ms (int): _description_
        proposed_package_size (int): _description_

    Returns:
        int: Returns package size agreed by the server
    """
    logger.debug(f'Init stablisish protocol')
    for i in range(N_TRIES_STABLISH_PROTOCOL):
        try:
            logger.info(f'propouse paquete: {proposed_package_size}')
            udp_connection.send(f"C{proposed_package_size:04d}{sv_timeout_ms:04d}".encode())
            in_msg  = udp_connection.recive(8).decode()
            if in_msg[0] != 'C':
                raise Exception(f'Invalid connection message, expected connection C, got {in_msg[0]}')
            package_size = int(in_msg[1:5])
            logger.info(f'recibo paquete: {package_size}')
            udp_connection.send(f"N{n_bytes}".encode())
            in_msg  = udp_connection.recive(package_size)
            in_msg  = in_msg.decode()
            if not (in_msg[0] == 'D' or in_msg[0] == 'E'): 
                raise Exception(f'Invalid data message, expected data D, got {in_msg[0]}')
            logger.info(f'Protocol stablished, data is being received')
            logger.info(f'recibiendo {n_bytes} nbytes')
            return package_size
            
        except Exception as e:
            logger.error(f'Error in stablish protocol: {e}')
            logger.error(f'Retrying... ({i+1})')
    logger.critical(f'Could not stablish protocol after {N_TRIES_STABLISH_PROTOCOL} tries')
    raise Exception(f'Could not stablish protocol after {N_TRIES_STABLISH_PROTOCOL} tries')

def bandwith_selective_repeat(udp_connection: UdpConnectionInterface, package_size: int, fileout: str) -> None:
    logger.info(f'Init bandwith selective repeat')
    start_time = time.time()
    fdout = open(fileout, 'wb')
    lfr = 0
    laf = WINDOW_SIZE
    window = [None] * WINDOW_SIZE
    errors = 0
    recv_bytes = 0
    pckge_count = 0
    last_pckge_num = None
    try:
        assert laf - lfr <= WINDOW_SIZE, "everything went wrong."
        while True:
            pckge = udp_connection.recive(package_size)
            if not pckge: 
                raise Exception('None received: Connection closed')
            pckge = pckge.decode()
            pckge_num = int(pckge[1:3])
            in_win_cond = lfr % MAX_FRAME <= pckge_num < laf % MAX_FRAME \
                            if lfr % MAX_FRAME <= laf % MAX_FRAME else \
                            not laf % MAX_FRAME <= pckge_num < lfr % MAX_FRAME
            if in_win_cond:
                place_in_win = pckge_num - (lfr%MAX_FRAME) \
                                if pckge_num >= lfr%MAX_FRAME else \
                                pckge_num + MAX_FRAME - (lfr%MAX_FRAME)
                window[place_in_win] = pckge
                if pckge_num == lfr%MAX_FRAME:
                    while window[0] != None:
                        fdout.write(window[0][3:].encode())
                        recv_bytes += len(window[0][3:].encode())
                        window.pop(0)
                        window.append(None)
                        lfr += 1
                        laf += 1
                        pckge_count += 1
                    udp_connection.send(f"A{(lfr-1)%MAX_FRAME:02d}".encode())
                    
                    if pckge[0] == 'E' or ((lfr-1)%MAX_FRAME) == last_pckge_num:
                        break
                else:
                    udp_connection.send(f"a{pckge_num:02d}".encode())
                    if pckge[0] == 'E':
                        last_pckge_num = pckge_num

                # recv_bytes += len(pckge.encode())
            else:
                # logger.warning(f'Package {pckge_num} not in window')
                errors += 1
                udp_connection.send(f"A{(lfr-1)%MAX_FRAME:02d}".encode())          
    except Exception as e:
        logger.critical(f'Error in bandwith selective repeat: \n{e}')
        end_time = time.time()
        logger.warning(f'Bandwith selective repeat finished unsucessfully in {end_time-start_time:.3f} seconds')
        logger.warning(f'Received {recv_bytes} bytes')
        logger.warning(f'Errors: {errors}')
        logger.warning(f'Received packages: {pckge_count}')
        print("0, 0, 0, 0")
        return 
    end_time = time.time()
    time_elapsed = end_time - start_time
    logger.info(f'Bandwith selective repeat finished in {time_elapsed:.3f} seconds')
    logger.info(f'Received {recv_bytes} bytes')
    bandwith = recv_bytes/time_elapsed/1024/1024
    logger.info(f'Bandwith: {bandwith:.3f} MBytes/s')
    logger.info(f'Errors: {errors}')
    logger.info(f'Received packages: {pckge_count}')
    print(f'{bandwith:.3g}, {recv_bytes}, {time_elapsed:.3g}, {errors}')

def argument_parser() -> argparse.Namespace:
    global WINDOW_SIZE
    parser = argparse.ArgumentParser(description='Bandwith connection Selective repeat')
    parser.add_argument('pack_sz', type=int, help='Package size')
    parser.add_argument('nbytes', type=int, help='Number of bytes to be received')
    parser.add_argument('timeout', type=int, help='Timeout')
    parser.add_argument('loss', type=int, help='Loss rate to be simulated')
    parser.add_argument('fileout', type=str, help='File to be written with the received data')
    parser.add_argument('host', type=str, help='Host to be connected')
    parser.add_argument('port', type=int, help='Port to connect')
    parser.add_argument('--window_sz', type=int, help='Window size', default=WINDOW_SIZE)
    args = parser.parse_args()
    if args.pack_sz < 1:
        parser.error('Package size must be greater than 0')
    if args.nbytes < 1:
        parser.error('Number of bytes must be greater than 0')
    if args.timeout < 1:
        parser.error('Timeout must be greater than 0')
    if not 0<= args.loss < 100:
        parser.error('Loss rate must be between 0 and 99')
    if not 0<= args.port <= 65535:
        parser.error('Port must be between 1 and 65535')
    if args.window_sz < 1:
        parser.error('Window size must be greater than 0')
    WINDOW_SIZE = args.window_sz
    args.nbytes += 3*math.ceil(args.nbytes/args.pack_sz)
    args.pack_sz += 3
    return args

def main():
    args = argument_parser()
    logger.info(f' > > > Init client with args: {args}')
    try:
        udp_connection = UdpToyConnection(args.host, args.port, args.loss, args.timeout)
        package_size = stablish_protocol(udp_connection, args.nbytes, args.timeout, args.pack_sz)
        print(udp_connection._socket.getsockname())
        bandwith_selective_repeat(udp_connection, package_size, args.fileout)
    except Exception as e:
        logger.critical(f'Error in main: {e}') 
    logger.info(f' < < < Finished client with args: {args}')
    pass

if __name__ == "__main__":
    main()

