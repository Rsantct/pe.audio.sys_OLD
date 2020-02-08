#!/usr/bin/env python3

# Copyright (c) 2019 Rafael Sánchez
# This file is part of 'pe.audio.sys', a PC based personal audio system.
#
# 'pe.audio.sys' is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# 'pe.audio.sys' is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with 'pe.audio.sys'.  If not, see <https://www.gnu.org/licenses/>.

"""
    You need an FTDI FT23xx USB UART with a 3 pin IR receiver at 38 KHz,
    e.g. TSOP31238 or TSOP38238.

    Usage:

        ir.py  [-t logfilename]

        -t  Learning mode. Prints out the received bytes so you can
            map "keyBytes: actions" inside the file 'ir.config'
"""

import serial
import sys
import yaml
import socket
from time import time
import os

def send_cmd(cmd):
    if cmd[:4] == 'aux ':
        host, port = AUX_HOST, AUX_PORT
        cmd = cmd[4:]
        svcName = 'aux'
    elif cmd[:8] == 'players ':
        host, port = PLY_HOST, PLY_PORT
        cmd = cmd[8:]
        svcName = 'players'
    else:
        host, port = CTL_HOST, CTL_PORT
        svcName = 'control'
    print('sending:', cmd, f'to {host}:{port}')
    with socket.socket() as s:
        try:
            s.connect( (host, port) )
            s.send( cmd.encode() )
            s.close()
        except:
            print (f'(ir.py) service \'{svcName}\' socket error on port {port}')
    return

def irpacket2cmd(packetOfBytes):
    #print(  ' '.join( b2hex(packetOfBytes) ) )
    try:
        return keymap[ ' '.join( b2hex(packetOfBytes) ) ]
    except:
        return ''

def b2hex(b):
    """ converts a bytes stream into a easy readable raw hex list, e.g:
        in:     b'\x00-m-i)m\xbb\xff'
        out:    ['00', '2d', '6d', '2d', '69', '29', '6d', 'bb', 'ff']
    """
    bh = b.hex()
    return [ bh[i*2:i*2+2] for i in range(int(len(bh)/2)) ]

def serial_params(d):
    """ read a remote dict config then returns serial params """
    # defaults
    baudrate    = 9600
    bytesize    = 8
    parity      = 'N'
    stopbits    = 1
    if 'baudrate' in d:
        baudrate = d['baudrate']
    if bytesize in d and d['bytesize'] in (5, 6, 7, 8):
        bytesize = d['bytesize']
    if 'parity' in d and d['parity'] in ('N', 'E', 'O', 'M', 'S'):
        parity = d['parity']
    if 'stopbits' in d and d['stopbits'] in (1, 1.5, 2):
        stopbits = d['stopbits']
    return baudrate, bytesize, parity, stopbits

def main_EOP():
    # LOOPING: reading byte by byte as received
    lastTimeStamp = time() # helper to avoid bouncing
    irpacket = b''
    while True:
        rx  = s.read( 1 )

        # Detecting the endOfPacket byte with some tolerance
        if  abs( int.from_bytes(rx, "big") -
                 int(endOfPacket, 16) ) <= 5:
            # (i) Here wo force the last byte as defined in endOfPacket,
            #     although the real one can differ in the above tolerance.
            irpacket += bytes.fromhex(endOfPacket)
            # try to translate it to a command according to the keymap table
            cmd = irpacket2cmd(irpacket)
            if cmd:
                if time() - lastTimeStamp >= antibound:
                    send_cmd(cmd)
                    lastTimeStamp = time()
            irpacket = b''

        else:
            irpacket += rx

def main_PL():
    # LOOPING: reading packetLength bytes
    lastTimeStamp = time() # helper to avoid bouncing
    while True:
        irpacket  = s.read( packetLength )
        cmd = irpacket2cmd(irpacket, keymap)
        if cmd:
            if time() - lastTimeStamp >= antibound:
                send_cmd(cmd)
                lastTimeStamp = time()

def main_TM():
    # Test mode will save the received bytes to a file so you can analyze them.
    irpacket = b''
    while True:
        rx  = s.read( 1 )
        print( rx.hex() )
        flog.write(rx)

if __name__ == "__main__":

    UHOME = os.path.expanduser("~")
    THISPATH = os.path.dirname(os.path.abspath(__file__))

    if '-h' in sys.argv:
        print(__doc__)
        exit()

    # pe.audio.sys services addressing
    try:
        with open(f'{UHOME}/pe.audio.sys/config.yml', 'r') as f:
            A = yaml.load(f)['services_addressing']
            CTL_HOST, CTL_PORT = A['pasysctrl_address'], A['pasysctrl_port']
            AUX_HOST, AUX_PORT = A['aux_address'], A['aux_port']
            PLY_HOST, PLY_PORT = A['players_address'], A['players_port']
    except:
        print('ERROR with \'pe.audio.sys/config.yml\'')
        exit()

    # IR config file
    try:
        with open(f'{THISPATH}/ir.config', 'r') as f:
            IRCFG = yaml.load(f)
            antibound   = IRCFG['antibound']
            REMCFG      = IRCFG['remotes'][ IRCFG['remote'] ]
            keymap      = REMCFG['keymap']
            baudrate, bytesize, parity, stopbits = serial_params(REMCFG)
            packetLength = REMCFG['packetLength']
            try:
                endOfPacket = REMCFG['endOfPacket']
            except:
                endOfPacket = None
    except:
        print(f'ERROR with \'{THISPATH}/ir.config\'')
        exit()

    # testing mode to learn new keys
    test_mode = sys.argv[1:] and sys.argv[1] == '-t'
    if test_mode:
        if sys.argv[2:]:
            logfname = f'{sys.argv[2]}'
            flog = open(logfname, 'wb')
            print(f'(i) saving to \'{logfname}\'')
        else:
            print('-t  missing the log filename')
            exit()

    # Open the IR usb device
    s = serial.Serial( port=IRCFG['ir_dev'], baudrate=baudrate, bytesize=bytesize,
                       parity=parity, stopbits=stopbits, timeout=None)
    print('Serial open:', s.name, baudrate, bytesize, parity, stopbits)

    # Go LOOPING
    if test_mode:
        main_TM()
    elif endOfPacket and packetLength:
        print( 'ERROR: choose endOfPacket OR packetLength on your remote config' )
    elif endOfPacket:
        main_EOP()
    elif packetLength:
        main_PL()