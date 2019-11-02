#!/usr/bin/env python3

# Copyright (c) 2019 Rafael Sánchez
# This file is part of 'pe.audio.sys', a PC based personal audio system.

# This is based on 'pre.di.c,' a preamp and digital crossover
# https://github.com/rripio/pre.di.c
# Copyright (C) 2018 Roberto Ripio
# 'pre.di.c' is based on 'FIRtro', a preamp and digital crossover
# https://github.com/AudioHumLab/FIRtro
# Copyright (c) 2006-2011 Roberto Ripio
# Copyright (c) 2011-2016 Alberto Miguélez
# Copyright (c) 2016-2018 Rafael Sánchez
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
    Launch the spotify_monitor_daemon_vX.py daemon that will:

    - listen for events from Spotify Desktop

    - and writes down the metadata into a file for others to read it.

    usage:   spotify_monitor.py   start | stop
"""
# For playerctl v0.x will run spotify_monitor_daemon_v1.py
# For playerctl v2.x will run spotify_monitor_daemon_v2.py

import sys, os
from subprocess import Popen, check_output

HOME = os.path.expanduser("~")
SCRIPTSFOLDER = f'{HOME}/pe.audio.sys/share/scripts'

def get_playerctl_version():
    try:
        tmp = check_output('playerctl --version'.split()).decode()
        tmp = tmp.lower().replace('v','')
        return tmp[0]
    except:
        return -1

def start():
    v = get_playerctl_version()
    if v != '-1':
        if v in ('0','1'):
            v = 1
        Popen( f'{SCRIPTSFOLDER}/spotify_monitor_daemon_v{v}.py' )
    else:
        print( '(spotify_monitor) Unable to find playerctl --version)' )

def stop():
    Popen( ['pkill', '-f',  'spotify_monitor'] )

if sys.argv[1:]:
    if True:
        option = {
            'start' : start,
            'stop'  : stop
            }[ sys.argv[1] ]()
    #except:
    #    print( '(spotify_monitor) bad option' )
else:
    print(__doc__)