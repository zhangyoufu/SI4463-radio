import ast
import ctypes
import re
import serial
import threading
import typing

# State
NOCHANGE = REMAIN = 0
SLEEP = 1
SPI_ACTIVE = 2
READY = 3
READY2 = 4
TX_TUNE = 5
RX_TUNE = 6
TX = 7
RX = 8
RX_IDLE = 9

# Command
NOP = 0x00
PART_INFO = 0x01
POWER_UP = 0x02
FUNC_INFO = 0x10
SET_PROPERTY = 0x11
GET_PROPERTY = 0x12
GPIO_PIN_CFG = 0x13
FIFO_INFO = 0x15
PACKET_INFO = 0x16
GET_INT_STATUS = 0x20
GET_PH_STATUS = 0x21
GET_MODEM_STATUS = 0x22
START_TX = 0x31
START_RX = 0x32
REQUEST_DEVICE_STATE = 0x33
CHANGE_STATE = 0x34
RX_HOP = 0x36
TX_HOP = 0x37
READ_CMD_BUFF = 0x44
FRR_A_READ = 0x50
FRR_B_READ = 0x51
FRR_C_READ = 0x53
FRR_D_READ = 0x57
WRITE_TX_FIFO = 0x66
READ_RX_FIFO = 0x77

# Interrupt
PACKET_RX = 0x10
PACKET_SENT = 0x20

class PartInfo(ctypes.BigEndianStructure):
    _pack_ = 1
    _fields_ = [
        ('CHIPREV',  ctypes.c_uint8),
        ('PART',     ctypes.c_uint16),
        ('PBUILD',   ctypes.c_uint8),
        ('ID',       ctypes.c_uint16),
        ('CUSTOMER', ctypes.c_uint8),
        ('ROMID',    ctypes.c_uint8),
    ]

class Si4463:
    def __init__(self, port):
        self._conn = serial.Serial(port, baudrate=230400, exclusive=True)
        self._conn_lock = threading.Lock()

    def request(self, *items, rsp_len=0):
        req = join_bytes(*items)
        req_len = len(req)
        if req_len < 1:
            raise ValueError
        data = bytearray(2+req_len)
        data[0] = req_len
        data[1] = rsp_len
        data[2:] = req

        with self._conn_lock:
            self._conn.write(data)
            if rsp_len:
                rsp = self._conn.read(rsp_len)
            else:
                self._conn.read(1) # sync
                rsp = b''
        return rsp

    def config(self, path):
        with open(path) as f:
            data = f.read()
        for match in re.finditer(r'(?m)^#define (?:RF_[A-Z0-9_]+) (.*)', data):
            self.request(ast.literal_eval(match.group(1)))

    def part_info(self):
        return PartInfo.from_buffer_copy(self.request(PART_INFO, rsp_len=8))

    def get_property(self, group, index, num_props):
        data = self.request(GET_PROPERTY, group, num_props, index, rsp_len=num_props)
        return data[0] if num_props == 1 else data

    def set_property(self, group, index, data):
        if isinstance(data, int): data = (data,)
        self.request(SET_PROPERTY, group, len(data), index, data)

    def rx_fifo_count(self):
        return self.request(FIFO_INFO, 0x00, rsp_len=1)[0]

    def tx_fifo_space(self):
        return self.request(FIFO_INFO, 0x00, rsp_len=2)[1]

    def clear_tx_fifo(self):
        self.request(FIFO_INFO, 0x01)

    def clear_rx_fifo(self):
        self.request(FIFO_INFO, 0x02)

    def clear_interrupts(self):
        self.request(GET_INT_STATUS, 0x00, 0x00, 0x00)

    def clear_packet_rx(self):
        self.request(GET_PH_STATUS, ~PACKET_RX)

    def clear_packet_sent(self):
        self.request(GET_PH_STATUS, ~PACKET_SENT)

    def write_tx_fifo(self, *items):
        self.request(WRITE_TX_FIFO, join_bytes(*items))

    def read_rx_fifo(self, length):
        return self.request(READ_RX_FIFO, rsp_len=length)

    def get_ph_status(self):
        return self.request(FRR_A_READ, rsp_len=1)[0]

    def poll_packet_rx(self):
        while self.get_ph_status() & PACKET_RX == 0:
            pass

    def poll_packet_sent(self):
        while self.get_ph_status() & PACKET_SENT == 0:
            pass

    def start_tx(self, channel, retransmit=0, start=0, tx_complete_state=READY, tx_len=0):
        self.request(
            START_TX,
            channel,
            tx_complete_state << 4 | retransmit << 2 | start,
            tx_len.to_bytes(2, byteorder='big'),
        )

    def start_rx(self, channel, start=0, rx_len=0, rx_timeout_state=NOCHANGE, rx_valid_state=READY, rx_invalid_state=RX):
        self.request(
            START_RX,
            channel,
            start,
            rx_len.to_bytes(2, byteorder='big'),
            rx_timeout_state,
            rx_valid_state,
            rx_invalid_state,
        )

def join_bytes(*items):
    length = 0
    for item in items:
        if isinstance(item, int):
            length += 1
        elif isinstance(item, typing.Iterable):
            length += len(item)
        else:
            raise TypeError

    buf = bytearray(length)
    offset = 0
    for item in items:
        if isinstance(item, int):
            if -128 <= item < 0:
                item = item & 0xFF
            buf[offset] = item
            offset += 1
        elif isinstance(item, typing.Iterable):
            buf[offset:offset+len(item)] = item
            offset += len(item)
        else:
            raise NotImplementedError

    return buf
