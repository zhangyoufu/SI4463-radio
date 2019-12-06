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
    parser.add_argument('message', help='message to be sent')
    args = parser.parse_args()
    data = args.message.encode()
    if len(data) > 63:
        raise NotImplementedError

    rf = si4463.Si4463(args.port)
    assert rf.part_info().PART == 0x4463

    logger.info('configuring...')
    rf.config(args.config)

    logger.info('transmitting...')
    rf.clear_interrupts()
    rf.clear_tx_fifo()
    rf.write_tx_fifo(bytes([len(data)]) + data)
    rf.start_tx(channel=0, tx_len=1+len(data))
    rf.poll_packet_sent()
    logger.info('sent: %r', data)

if __name__ == '__main__':
    main()
