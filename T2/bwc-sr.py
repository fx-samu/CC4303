#!/usr/bin/python3

#---------------------------------------------------------------------------
# Global basic configuration
#---------------------------------------------------------------------------
import socket, jsockets
import sys, random, logging, time
from abc import ABC, abstractmethod
logging.basicConfig(
    level=logging.DEBUG, 
    format='[%(asctime)s.%(msecs)03d | %(levelname).3s @ %(lineno)03d] %(message)s', 
    datefmt='%H:%M:%S'
)
logging.getLogger().addHandler(logging.FileHandler('output.log'))
N_TRIES_STABLISH_PROTOCOL = 100

#---------------------------------------------------------------------------
# Clases
#---------------------------------------------------------------------------
def _send_loss(s, data, loss_rate):
    # Envia un paquete con loss_rate porcentaje de perdida
    # si loss_rate = 5, implica un 5% de perdida
    if random.random() * 100 > loss_rate:
        s.send(data)
    else:
        logging.debug("[send_loss]")

def _recv_loss(s, size, loss_rate):
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
        logging.debug(f'{self} <- {data}')
        _send_loss(self._socket, data, self._loss_rate)
    
    def recive(self, size: int) -> bytes:
        recived = _recv_loss(self._socket, size, self._loss_rate)
        log_msg = f"{str(recived):.20} (... +{len(recived)-20} ...)\'" if len(recived) > 20 else recived
        logging.debug(f'{self} -> {log_msg}')
        return recived

#---------------------------------------------------------------------------
# Functions
#---------------------------------------------------------------------------

def bandwith_selective_repeat(udp_connection: UdpConnectionInterface, package_size: int, fileout: str) -> None:
    pass

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
    logging.debug(f'Init stablisish protocol')
    for i in range(N_TRIES_STABLISH_PROTOCOL):
        try:
            logging.info(f'propouse paquete: {proposed_package_size}')
            udp_connection.send(f"C{proposed_package_size:04d}{sv_timeout_ms:04d}".encode())
            in_msg  = udp_connection.recive(8).decode()
            package_size = int(in_msg[1:5])
            logging.info(f'recibo paquete: {package_size}')
            udp_connection.send(f"N{n_bytes}".encode())
            in_msg  = udp_connection.recive(package_size)
            in_msg  = in_msg.decode()
            if in_msg[0] != 'D': 
                raise Exception(f'Invalid data message, expected data D, got {in_msg[0]}')
            logging.info(f'Protocol stablisished, data is being received')
            logging.info(f'recibiendo {n_bytes} nbytes')
            return package_size
            
        except Exception as e:
            logging.error(f'Error in stablisish protocol: {e}')
            logging.error(f'Retrying... ({i+1})')
    logging.critical(f'Could not stablish protocol after {N_TRIES_STABLISH_PROTOCOL} tries')
    sys.exit(1)

def get_args(*args) -> tuple:
    """
    Get arguments from command line and check if they are valid
    
    Args:
        args: List of tuples with the arguments and their types... (name, type)

    Returns:
        tuple: Tuple with the arguments
    """
    _type_str = {int: 'int', float: 'float', str: 'str'}
    
    if any(len(arg) != 2 for arg in args):
        raise Exception('get_args: Invalid argument list')

    if len(sys.argv) != len(args) + 1:
        print(f'Use: {sys.argv[0]} {" ".join([f"<{arg[0]}: {_type_str[arg[1]]}>" for arg in args])}')
        sys.exit(1)
    
    args = [[arg[0], arg[1], sys.argv[i+1]] for i, arg in enumerate(args)]
    
    for arg in args:
        if arg[1] == int:
            try:
                arg[2] = int(arg[2])
            except:
                print(f'Invalid argument: {arg[0]}')
                sys.exit(1)
        elif arg[1] == float:
            try:
                arg[2] = float(arg[2])
            except:
                print(f'Invalid argument: {arg[0]}')
                sys.exit(1)
        elif arg[1] == str:
            pass
        else:
            Exception('get_args: Invalid argument type')
    
    return tuple(arg[2] for arg in args)

#---------------------------------------------------------------------------
# Main 
#---------------------------------------------------------------------------
def main():
    package_size, n_bytes, timeout, loss, fileout, host, port = \
    get_args(
        ("package_size", int), 
        ("nBytes", int), 
        ("timeout", int), 
        ("loss", int), 
        ("fileout", str), 
        ("host", str), 
        ("port", int)
    )
    udp_connection = UdpToyConnection(host, port, loss, timeout)
    stablish_protocol(udp_connection, n_bytes, timeout, package_size)

if __name__ == "__main__":
    main()