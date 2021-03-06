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

import os
from subprocess import Popen, check_output
import json

UHOME = os.path.expanduser("~")
MAINFOLDER = f'{UHOME}/pe.audio.sys'

# bitrate HARDWIRED pending on how to retrieve it from the desktop client.
SPOTIFY_BITRATE   = '320'


# Auxiliary to detect the Spotify Client in use: desktop or librespot
def detect_spotify_client():
    cname = None
    # Check if a desktop client is running:
    try:
        check_output( 'pgrep -f Spotify'.split() )
        cname = 'desktop'
    except:
        pass
    # Check if 'librespot' (a Spotify Connect daemon) is running:
    try:
        check_output( 'pgrep -f librespot'.split() )
        cname = 'librespot'
    except:
        pass
    return cname


# Auxiliary function to format hh:mm:ss
def timeFmt(x):
    """ in:     x seconds   (float)
        out:    'hh:mm:ss'  (string)
    """
    # x must be float
    h = int( x / 3600 )         # hours
    x = int( round(x % 3600) )  # updating x to reamining seconds
    m = int( x / 60 )           # minutes from the new x
    s = int( round(x % 60) )    # and seconds
    return f'{h:0>2}:{m:0>2}:{s:0>2}'


# Spotify Desktop control
def spotify_control(cmd):
    """ Controls the Spotify Desktop player
        input:  a command
        output: the resulting status string
    """
    # It is assumed that you have the mpris2-dbus utility 'playerctl' installed.
    #      https://wiki.archlinux.org/index.php/spotify#MPRIS
    # dbus-send command can also work
    #       http://www.skybert.net/linux/spotify-on-the-linux-command-line/

    # playerctl - Available Commands:
    #   play                    Command the player to play
    #   pause                   Command the player to pause
    #   play-pause              Command the player to toggle between play/pause
    #   stop                    Command the player to stop
    #   next                    Command the player to skip to the next track
    #   previous                Command the player to skip to the previous track
    #   position [OFFSET][+/-]  Command the player to go to the position or seek forward/backward OFFSET in seconds
    #   volume [LEVEL][+/-]     Print or set the volume to LEVEL from 0.0 to 1.0
    #   status                  Get the play status of the player
    #   metadata [KEY]          Print metadata information for the current track. Print only value of KEY if passed

    # (!) Unfortunately, 'position' does not work, so we cannot rewind neither fast forward
    if cmd in ('play', 'pause', 'next', 'previous' ):
        Popen( f'playerctl --player=spotify {cmd}'.split() )

    # Retrieving the playback state
    result = ''
    if cmd == 'state':
        try:
            result = check_output( f'playerctl --player=spotify status'
                                    .split() ).decode()
        except:
            pass
    # playerctl just returns 'Playing' or 'Paused'
    if 'play' in result.lower():
        return 'play'
    else:
        return 'pause'


# Spotify Desktop metadata
def spotify_meta(md):
    """ Analize the MPRIS metadata info retrieved by the daemon scripts/spotify_monitor
        which monitorizes a Spotify Desktop Client
        Input:      blank md dict
        Output:     Spotify metadata dict
        I/O:        .spotify_events (r) MPRIS desktop metadata from spotify_monitor.py
    """
    md['player']  = 'Spotify Desktop Client'
    md['bitrate'] = SPOTIFY_BITRATE

    try:
        with open(f'{MAINFOLDER}/.spotify_events', 'r') as f:
            tmp = f.read()

        tmp = json.loads( tmp )
        # Example:
        # {
        # "mpris:trackid": "spotify:track:5UmNPIwZitB26cYXQiEzdP",
        # "mpris:length": 376386000,
        # "mpris:artUrl": "https://open.spotify.com/image/798d9b9cf2b63624c8c6cc191a3db75dd82dbcb9",
        # "xesam:album": "Doble Vivo (+ Solo Que la Una/Con Cordes del Mon)",
        # "xesam:albumArtist": ["Kiko Veneno"],
        # "xesam:artist": ["Kiko Veneno"],
        # "xesam:autoRating": 0.1,
        # "xesam:discNumber": 1,
        # "xesam:title": "Ser\u00e9 Mec\u00e1nico por Ti - En Directo",
        # "xesam:trackNumber": 3,
        # "xesam:url": "https://open.spotify.com/track/5UmNPIwZitB26cYXQiEzdP"
        # }

        # regular fields:
        for k in ('artist', 'album', 'title'):
            value = tmp[ f'xesam:{k}']
            if type(value) == list:
                md[k] = ' '.join(value)
            elif type(value) == str:
                md[k] = value
        # track_num:
        md['track_num'] = tmp["xesam:trackNumber"]
        # and time lenght:
        md['time_tot'] = timeFmt( tmp["mpris:length"] / 1e6 )

    except:
        pass

    return md
