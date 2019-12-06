#!/usr/bin/env python3
import argparse
import logging
import si4463
import sys

logger = logging.getLogger(__name__)

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

    logger.info('receiving...')
    while 1:
        rf.clear_interrupts()
        rf.clear_rx_fifo()
        rf.start_rx(channel=0, rx_len=64)
        rf.poll_packet_rx()
        data = rf.read_rx_fifo(length=64)
        logger.info('rcvd: %r', data[1:1+data[0]])

if __name__ == '__main__':
    main()
