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
    A pe.audio.sys daemon to autoplay a CD-Audio when inserted

    Usage:  autoplay_cdda.py  start | stop  &
"""

# To check your devices from command line:
# $ udevadm monitor
# ... ...
# UDEV  [5336.857159] change   /devices/pci0000:00/0000:00:1f.1/ata1/host0/target0:0:0/0:0:0:0/block/sr0 (block)
# UDEV  [5358.454256] change   /devices/pci0000:00/0000:00:1d.7/usb5/5-6/5-6:1.0/host4/target4:0:0/4:0:0:0/block/sr1 (block)

import os
import sys
import yaml
from time import sleep
import socket
import pyudev
from subprocess import check_output, Popen

# Some distros as Ubuntu 18.04 LTS doesn't have
# libcdio-dev >=2.0 as required from pycdio.
#import cdio, pycdio
# (i) pycdio dependencies:
#       python-dev libcdio-dev libiso9660-dev swig pkg-config
# Workaround: lets use 'cdinfo' from 'cdtool' package (cdrom command line tools)


def send_cmd(cmd):
    host, port = CTL_HOST, CTL_PORT
    print( f'({ME}) sending: {cmd} to {host}:{port}')
    with socket.socket() as s:
        try:
            s.connect( (host, port) )
            s.send( cmd.encode() )
            s.close()
        except:
            print( f'({ME}) socket error on {host}:{port}' )
    return


def check_for_CDDA(d):

    srDevice = d.device_path.split('/')[-1]
    CDROM = f'/dev/{srDevice}'

    def autoplay_CDDA():
        send_cmd( 'player pause' )
        sleep(.5)
        send_cmd( 'preamp input cd' )
        sleep(.5)
        send_cmd( 'player play' )

    # Verbose if not CDDA
    try:
        # $ cdinfo -a # will output: no_disc | data_disc | xx:xx.xx
        tmp = check_output( f'cdinfo -a -d {CDROM}'.split() ).decode().strip()
        if ':' in tmp:
            print( f'({ME}) trying to play the CD Audio disk' )
            autoplay_CDDA()
        elif 'no_disc' in tmp:
            print( f'({ME}) no disc' )
        elif 'data_disc' in tmp:
            print( f'({ME}) data disc' )
    except:
        print( f'({ME}) This script needs \'cdtool\' (command line cdrom tool)' )


def stop():
    Popen( f'pkill -KILL -f autoplay_cdda'.split() )
    sleep(.5)


def main():
    # Main observer daemon
    context = pyudev.Context()
    umonitor = pyudev.Monitor.from_netlink(context)
    umonitor.filter_by(subsystem='block', device_type='disk')
    uobserver = pyudev.MonitorObserver( umonitor, callback=check_for_CDDA )
    uobserver.daemon = False  # set False will block the process when started.
    uobserver.start()


if __name__ == '__main__':

    UHOME = os.path.expanduser("~")
    ME = __file__.split('/')[-1]

    # pe.audio.sys service addressing
    try:
        with open(f'{UHOME}/pe.audio.sys/config.yml', 'r') as f:
            cfg = yaml.safe_load(f)
            CTL_HOST, CTL_PORT = cfg['peaudiosys_address'], cfg['peaudiosys_port']
    except:
        print(f'({ME}) ERROR with \'pe.audio.sys/config.yml\'')
        exit()

    if sys.argv[1:]:
        if sys.argv[1] == 'start':
            main()
        elif sys.argv[1] == 'stop':
            stop()
        else:
            print(__doc__)
    else:
        print(__doc__)
