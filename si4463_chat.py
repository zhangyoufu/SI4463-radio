#!/usr/bin/env python3
import argparse
import logging
import si4463
import sys
import threading

logger = logging.getLogger(__name__)
lock_1 = threading.Lock()
lock_2 = threading.Lock()
recv_flag = True

def main():
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.DEBUG,
        datefmt='%H:%M:%S',
        format='%(asctime)s.%(msecs)03d %(message)s',
    )

    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='radio_config.h', help='path to radio_config.h')
    parser.add_argument('port', help='(Unix) path to serial tty; (Windows) COMx')
    args = parser.parse_args()

    rf = si4463.Si4463(args.port)
    assert rf.part_info().PART == 0x4463

    logger.info('configuring...')
    rf.config(args.config)
    rf.clear_interrupts()
    logger.info('input anything, press Enter to send')

    lock_1.acquire() # for receiver

    # BUG: thread exception not handled
    threading.Thread(target=sender, args=(rf,), daemon=True).start()
    receiver(rf)

def sender(rf):
    global recv_flag
    while 1:
        message = input()
        data = message.encode()[:63]
        rf.clear_packet_sent()
        rf.clear_tx_fifo()
        rf.write_tx_fifo(bytes([len(data)]) + data)
        lock_2.acquire() # acquire before inform
        recv_flag = False # break recv polling
        lock_1.acquire() # wait recv->send
        lock_1.release() # recycle
        rf.start_tx(channel=0, tx_len=1+len(data))
        rf.poll_packet_sent()
        lock_2.release() # inform send->recv
        logger.info('sent: %r', data)

def receiver(rf):
    global recv_flag
    first_recv = True
    while 1:
        rf.clear_packet_rx()
        rf.clear_rx_fifo()
        rf.start_rx(channel=0, rx_len=64)

        while recv_flag:
            if rf.get_ph_status() & si4463.PACKET_RX:
                data = rf.read_rx_fifo(length=64)
                if first_recv:
                    sys.stderr.write('\n')
                    first_recv = False
                logger.info('rcvd: %r', data[1:1+data[0]])
                break
        else:
            # recv polling breaked
            recv_flag = True # reset flag
            lock_1.release() # inform recv->send
            lock_2.acquire() # wait send->recv
            lock_2.release() # recycle
            lock_1.acquire() # acquire before inform
            first_recv = True

if __name__ == '__main__':
    main()
