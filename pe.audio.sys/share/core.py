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


import os, sys
import socket
import subprocess as sp
import threading
import yaml
import json
import jack
import numpy as np
from time import sleep


# AUX and FILES MANAGEMENT: ====================================================

def read_yaml(filepath):
    """ Returns a dictionary from an YAML file """
    with open(filepath) as f:
        d = yaml.load(f)
    return d

def save_yaml(dic, filepath):
    """ Save a dict to disk """
    with open( filepath, 'w' ) as f:
        yaml.dump( dic, f, default_flow_style=False )

def find_target_sets():
    """ Returns the uniques target filenames w/o the suffix _mag.dat or _pha.dat,
        also will add 'none' as an additional set.
    """
    result = ['none']
    files = os.listdir( EQ_FOLDER )
    tmp = [ x for x in files if x[-14:-7] == 'target_'  ]
    for x in tmp:
        if not x[:-8] in result:
            result.append( x[:-8] )
    return result

def get_peq_in_use():
    """ Finds out the PEQ (parametic eq) filename used by an inserted Ecasound
        sound processor, if it is defined as an optional script inside config.yml
    """
    for item in CONFIG['scripts']:
        if type(item) == dict and 'ecasound_peq.py' in item.keys():
            return item["ecasound_peq.py"].replace('.ecs','')
    return 'none'

def get_eq_curve(curv, state):
    """ Retrieves the tone or loudness curve.
        Tone curves depens on state bass & treble.
        Loudness compensation curve depens on the target level dBrefSPL.
    """
    # Tone eq curves are provided in [-6...0...+6]
    if curv == 'bass':
        index = 6 - int(round(state['bass']))

    elif curv == 'treb':
        index = 6 - int(round(state['treble']))

    # For loudness eq curves there is a flat curve index previously detected,
    # also there is a limiting ceiling value inside config.yml
    elif curv == 'loud':

        index_min   = 0
        index_max   = EQ_CURVES['loud_mag'].shape[1] - 1
        index_flat  = LOUD_FLAT_CURVE_INDEX

        if state['loudness_track'] and ( state['level'] <= CONFIG['loud_ceil'] ):
            index = index_flat - state['level']
        else:
            index = index_flat
        index = int(round(index))

        # Clamp index to the available "loudness deepness" curves set
        index = max( min(index, index_max), index_min )

    return EQ_CURVES[f'{curv}_mag'][:,index], EQ_CURVES[f'{curv}_pha'][:,index]

def find_eq_curves():
    """ Scans share/eq/ and try to collect the whole set of EQ curves
        needed for the EQ stage in Brutefir
    """
    EQ_CURVES = {}
    eq_files = os.listdir(EQ_FOLDER)

    fnames = (  'loudness_mag.dat', 'bass_mag.dat', 'treble_mag.dat',
                'loudness_pha.dat', 'bass_pha.dat', 'treble_pha.dat',
                'freq.dat' )

    cnames = {  'loudness_mag.dat'  : 'loud_mag',
                'bass_mag.dat'      : 'bass_mag',
                'treble_mag.dat'    : 'treb_mag',
                'loudness_pha.dat'  : 'loud_pha',
                'bass_pha.dat'      : 'bass_pha',
                'treble_pha.dat'    : 'treb_pha',
                'freq.dat'          : 'freqs'     }

    # pendings curves to find ( freq + 2x loud + 4x tones = 7 )
    pendings = len(fnames)
    for fname in fnames:

        # Only one file named as <fname> must be found
        files = [ x for x in eq_files if fname in x]
        if files:
            if len (files) == 1:
                EQ_CURVES[ cnames[fname] ] = \
                                       np.loadtxt( f'{EQ_FOLDER}/{files[0]}' )
                pendings -= 1
            else:
                print(f'(core.py) too much \'...{fname}\' files under share/eq/')
        else:
                print(f'(core.py) ERROR finding a \'...{fname}\' file under share/eq/')

    if not pendings:
        return EQ_CURVES
    else:
        return {}

def find_loudness_flat_curve_index():
    """ scan all curves under the file xxx_loudness_mag.dat to find the flat one """
    index_max   = EQ_CURVES['loud_mag'].shape[1] - 1
    index_flat = -1
    for i in range(index_max):
        if np.sum( abs(EQ_CURVES['loud_mag'][:,i]) ) <= 0.1:
            index_flat = i
            break
    return index_flat

def calc_eq( state ):
    """ Calculate the eq curves to be applied in the Brutefir EQ module,
        as per the provided dictionary of state values.
    """
    loud_mag, loud_pha = get_eq_curve( 'loud', state )
    bass_mag, bass_pha = get_eq_curve( 'bass', state )
    treb_mag, treb_pha = get_eq_curve( 'treb', state )

    target_name = state['target']
    if target_name == 'none':
        targ_mag = np.zeros( EQ_CURVES['freqs'].shape[0] )
        targ_pha = np.zeros( EQ_CURVES['freqs'].shape[0] )
    else:
        targ_mag = np.loadtxt( f'{EQ_FOLDER}/{target_name}_mag.dat' )
        targ_pha = np.loadtxt( f'{EQ_FOLDER}/{target_name}_pha.dat' )

    eq_mag = targ_mag + loud_mag * state['loudness_track'] + bass_mag + treb_mag
    eq_pha = targ_pha + loud_pha * state['loudness_track'] + bass_pha + treb_pha

    return eq_mag, eq_pha

def calc_gain( state ):
    """ Calculates the gain from: level, ref_level_gain and the source gain offset
    """
    gain    = state['level'] + float(CONFIG['ref_level_gain']) - state['loudness_ref']
    if state['input'] != 'none':
        gain += float( CONFIG['sources'][state['input']]['gain'] )
    return gain

# BRUTEFIR MANAGEMENT: =========================================================

def bf_cli(command):
    """ send commands to Brutefir and disconnects from it """
    # using 'with' will disconnect the socket when done
    with socket.socket() as s:
        try:
            s.connect( ('localhost', 3000) )
            command = command + '; quit\n'
            s.send(command.encode())
        except:
            print (f'(core.py) Brutefir socket error')

def bf_set_midside( mode ):
    """ midside (formerly mono) is implemented at the f.eq.X stages:
        in.L  ------->  eq.L
                \/
                /\
        in.L  ------->  eq.L
    """
    if   mode == 'mid':
        bf_cli( 'cfia "f.eq.L" "in.L" m0.5 ; cfia "f.eq.L" "in.R" m0.5 ;'
                'cfia "f.eq.R" "in.L" m0.5 ; cfia "f.eq.R" "in.R" m0.5  ')
    elif mode == 'side':
        bf_cli( 'cfia "f.eq.L" "in.L" m0.5 ; cfia "f.eq.L" "in.R" m-0.5 ;'
                'cfia "f.eq.R" "in.L" m0.5 ; cfia "f.eq.R" "in.R" m-0.5  ')
    elif mode == 'off':
        bf_cli( 'cfia "f.eq.L" "in.L" m1.0 ; cfia "f.eq.L" "in.R" m0.0 ;'
                'cfia "f.eq.R" "in.L" m0.0 ; cfia "f.eq.R" "in.R" m1.0  ')
    else:
        pass

def bf_set_gains( state ):
    """ Adjust Brutefir gain at drc.X stages as per the provided state values """

    gain    = calc_gain( state )

    balance = float( state['balance'] )

    # Booleans:
    solo    = state['solo']
    muted   = state['muted']

    # (i) m_xxxx stands for an unity multiplier
    m_solo_L = {'off': 1, 'l': 1, 'r': 0} [ solo ]
    m_solo_R = {'off': 1, 'l': 0, 'r': 1} [ solo ]
    m_mute   = {True: 0, False: 1}        [ muted ]

    gain_L = (gain - balance/2.0)
    gain_R = (gain + balance/2.0)

    # We compute from dB to a multiplier, this is an alternative to
    # adjusting the attenuation on 'cffa' command syntax
    m_gain_L = 10**(gain_L/20.0) * m_mute * m_solo_L
    m_gain_R = 10**(gain_R/20.0) * m_mute * m_solo_R

    # cffa will apply atten at the 'from filters' input section on drc filters
    cmd =   'cffa "f.drc.L" "f.eq.L" m' + str( m_gain_L ) + ';' \
          + 'cffa "f.drc.R" "f.eq.R" m' + str( m_gain_R ) + ';'
    # print(cmd) # debug
    bf_cli(cmd)

def bf_set_eq( eq_mag, eq_pha ):
    """ Adjust the Brutefir EQ module  """
    freqs = EQ_CURVES['freqs']
    mag_pairs = []
    pha_pairs = []
    i = 0
    for freq in freqs:
        mag_pairs.append( str(freq) + '/' + str(round(eq_mag[i], 3)) )
        pha_pairs.append( str(freq) + '/' + str(round(eq_pha[i], 3)) )
        i += 1
    mag_str = ', '.join(mag_pairs)
    pha_str = ', '.join(pha_pairs)
    bf_cli('lmc eq "c.eq" mag '   + mag_str)
    bf_cli('lmc eq "c.eq" phase ' + pha_str)

def bf_read_eq():
    """ Returns a raw printout from issuing an 'info' query to the Brutefir's EQ module
    """
    try:
        cmd = 'lmc eq "c.eq" info; quit'
        tmp = sp.check_output( f'echo \'{cmd}\' | nc localhost 3000', shell=True ).decode()
    except:
        return ''
    tmp = [x for x in tmp.split('\n') if x]
    return tmp[2:]

def bf_set_drc( drcID ):
    """ Changes the FIR for DRC at runtime """
    if drcID == 'none':
        cmd = ( f'cfc "f.drc.L" -1             ; cfc "f.drc.R" -1             ;' )
    else:
        cmd = ( f'cfc "f.drc.L" "drc.L.{drcID}"; cfc "f.drc.R" "drc.R.{drcID}";' )
    bf_cli( cmd )

def bf_set_xo( ways, xo_coeffs, xoID ):
    """ Changes the FIRs for XOVER at runtime """

    # example:
    #   ways:
    #               f.lo.L f.hi.L f.lo.R f.hi.R f.sw
    #   xo_coeffs:
    #               xo.hi.L.mp  xo.hi.R.lp
    #               xo.hi.R.mp  xo.hi.L.lp
    #               xo.lo.mp    xo.lo.lp
    #               xo.sw.mp    xo.sw.lp
    #   xo_sets:
    #               mp          lp
    # NOTICE:
    #   This example has dedicated coeff FIRs for hi.L and hi.R,
    #   so when seleting the appropiate coeff we will try 'best matching'

    def find_best_match_coeff(way):

        found = ''
        # lets try matching coeff with way[2:] including the channel id
        for coeff in xo_coeffs:
            if way[2:] in coeff[3:] and xoID == coeff.split('.')[-1]:
                found = coeff

        # if not matches, then try just the way[2:4], e.g. 'lo'
        if not found:
            for coeff in xo_coeffs:
                if way[2:4] in coeff[3:] and xoID == coeff.split('.')[-1]:
                    found = coeff

        return found

    cmd = ''
    for way in ways:
        BMcoeff = find_best_match_coeff(way)
        cmd += f'cfc "{way}" "{BMcoeff}"; '

    #print (cmd)
    bf_cli( cmd )

def get_brutefir_config(prop):
    """ returns a property from brutefir_config file
        (BETA: currently only works for ludspeaker ways)
    """
    with open(f'{LSPK_FOLDER}/brutefir_config','r') as f:
        lines = f.read().split('\n')

    if prop == 'ways':
        ways = []
        for line in [ x for x in lines if x and 'filter' in x.strip().split() ]:
            if not '"f.eq.' in line and not '"f.drc.' in line and \
               line.startswith('filter'):
                   way = line.split()[1].replace('"','')
                   ways.append( way )
        return ways
    else:
        return []

def brutefir_runs():
    if JCLI.get_ports('brutefir'):
        return True
    else:
        return False

# JACK MANAGEMENT: =============================================================

def jack_connect(p1, p2, mode='connect', wait=1):
    """ Low level tool to connect / disconnect a pair of ports,
        by retriyng for a while
    """
    # Will retry during <wait> seconds, this is useful when a
    # jack port exists but it is still not active,
    # for instance Brutefir ports takes some seconds to be active.
    c = wait
    while c:
        try:
            if 'dis' in mode or 'off' in mode:
                JCLI.disconnect(p1, p2)
            else:
                if not p2 in JCLI.get_all_connections(p1):
                    JCLI.connect(p1, p2)
                else:
                    print ( f'(core) {p1.name} already connected to {p2.name}')
            print()
            return True
        except:
            c -= 1
            sleep(1)
    print ( f'(core) failed to connect \'{p1.name}\' to \'{p2.name}\'')
    return False

def jack_connect_bypattern(cap_pattern, pbk_pattern, mode='connect', wait=1):
    """ High level tool to connect/disconnect a given port name patterns
    """
    # Try to get ports by a port name pattern
    cap_ports = JCLI.get_ports( cap_pattern, is_output=True )
    pbk_ports = JCLI.get_ports( pbk_pattern, is_input= True )
    # If not found, it can be an alias pattern (loopback ports
    # have alias as expected from some source names)
    if not cap_ports:
        loopback_cap_ports = JCLI.get_ports( 'loopback', is_output=True )
        for p in loopback_cap_ports:
            # A port can have 2 alias, our user defined alias is the 2nd one.
            if cap_pattern in p.aliases[1]:
                cap_ports.append(p)
    if not pbk_ports:
        loopback_pbk_ports = JCLI.get_ports( 'loopback', is_input=True )
        for p in loopback_pbk_ports:
            if pbk_pattern in p.aliases[1]:
                pbk_ports.append(p)
    #print('CAPTURE  ====> ', cap_ports) # debug
    #print('PLAYBACK ====> ', pbk_ports) # debug
    if not cap_ports or not pbk_ports:
        print( f'(core) cannot connect "{cap_pattern}" to "{pbk_pattern}"' )
        return
    mode = 'disconnect' if ('dis' in mode or 'off' in mode) else 'connect'
    i=0
    for cap_port in cap_ports:
        pbk_port = pbk_ports[i]
        job_jc = threading.Thread( target=jack_connect,
                                   args=(cap_port,
                                         pbk_port,
                                         mode, wait) )
        job_jc.start()
        i += 1

def jack_clear_preamp():
    """ Force clearing ANY clients, no matter what input was selected """
    # NOTICE: 'pre_in_loop' is an alias for 'loopback 1&2' jack port names.
    pre1 = JCLI.get_port_by_name('loopback:playback_1')
    pre2 = JCLI.get_port_by_name('loopback:playback_2')
    for preport in (pre1, pre2):
        for client in JCLI.get_all_connections( preport ):
            jack_connect( client, preport, mode='off' )

def jack_prepare_loopback_aliases(loop_pnames):
    l = 1
    for pname in loop_pnames:
        for i in (1,2):
            p = JCLI.get_port_by_name( f'loopback:capture_{l}' )
            p.set_alias( f'{pname}:output_{i}' )
            p = JCLI.get_port_by_name( f'loopback:playback_{l}' )
            p.set_alias( f'{pname}:input_{i}' )
            l += 1


# THE PREAMP: AUDIO PROCESSOR, SELECTOR, and SYSTEM STATE KEEPER ===============

def init_source():
    """ Forcing if indicated on config.yml or restoring last state from disk
    """
    preamp = Preamp()

    if CONFIG["on_init"]["input"]:
        preamp.select_source  (   CONFIG["on_init"]["input"]      )
    else:
        preamp.select_source  (   core.state['input']             )

    state = preamp.state
    del(preamp)

    return state


def init_audio_settings():
    """ Forcing if indicated on config.yml or restoring last state from disk
    """

    preamp    = Preamp()
    convolver = Convolver()

    # (i) using != None below to detect 0 or False values

    on_init = CONFIG["on_init"]

    if on_init["muted"] != None:
        preamp.set_mute       (   on_init["muted"]                )
    else:
        preamp.set_mute       (   preamp.state['muted']           )

    if on_init["level"] != None:
        preamp.set_level      (   on_init["level"]                )
    else:
        preamp.set_level      (   preamp.state['level']           )

    if on_init["max_level"] != None:
        preamp.set_level(  min( on_init["max_level"], preamp.state['level'] ) )

    if on_init["bass"] != None :
        preamp.set_bass       (   on_init["bass"]                 )
    else:
        preamp.set_bass       (   preamp.state['bass']            )

    if on_init["treble"] != None :
        preamp.set_treble     (   on_init["treble"]               )
    else:
        preamp.set_treble     (   preamp.state['treble']          )

    if on_init["balance"] != None :
        preamp.set_balance    (   on_init["balance"]              )
    else:
        preamp.set_balance    (   preamp.state['balance']         )

    if on_init["loudness_track"] != None:
        preamp.set_loud_track (   on_init["loudness_track"]       )
    else:
        preamp.set_loud_track (   preamp.state['loudness_track']  )

    if on_init["loudness_ref"] != None :
        preamp.set_loud_ref   (   on_init["loudness_ref"]         )
    else:
        preamp.set_loud_ref   (   preamp.state['loudness_ref']    )

    if on_init["midside"]:
        preamp.set_midside    (   on_init["midside"]              )
    else:
        preamp.set_midside    (   preamp.state['midside']         )

    if on_init["solo"]:
        preamp.set_solo       (   on_init["solo"]                 )
    else:
        preamp.set_solo       (   preamp.state['solo']            )

    if on_init["xo"]:
        convolver.set_xo      (   on_init["xo"]                   )
        preamp.state["xo_set"] = on_init["xo"]
    else:
        convolver.set_xo      (   preamp.state['xo_set']          )

    if on_init["drc"]:
        convolver.set_drc     (   on_init["drc"]                  )
        preamp.state["drc_set"] = on_init["drc"]
    else:
        convolver.set_drc     (   preamp.state['drc_set']         )

    if on_init["target"]:
        preamp.set_target     (   on_init["target"]               )
    else:
        preamp.set_target     (   preamp.state['target']          )

    state = preamp.state
    del(convolver)
    del(preamp)

    return state

class Preamp(object):
    """ attributes:

            state           state dictionary
            inputs          the available inputs dict.
            target_sets     target curves available under the 'eq' folder
            bass_span       available span for tone curves
            treble_span
            gain_max        max authorised gain
            balance_max     max authorised balance

        methods:

            select_source
            set_level
            set_balance
            set_bass
            set_treble
            set_loud_ref
            set_loud_track
            set_target
            set_solo
            set_mute
            set_midside

            get_state
            get_inputs
            get_target_sets
            get_eq
    """

    def __init__(self):

        # The available inputs
        self.inputs = CONFIG['sources']
        # The state dictionary
        self.state = read_yaml( STATE_PATH )
        self.state['loudspeaker'] = CONFIG['loudspeaker']   # informative value
        self.state['peq_set'] = get_peq_in_use()            # informative value
        # The target curves available under the 'eq' folder
        self.target_sets = find_target_sets()
        # The available span for tone curves
        self.bass_span   = int( (EQ_CURVES['bass_mag'].shape[1] - 1) / 2 )
        self.treble_span = int( (EQ_CURVES['treb_mag'].shape[1] - 1) / 2 )
        # Max authorised gain
        self.gain_max    = float(CONFIG['gain_max'])
        # Max authorised balance
        self.balance_max = float(CONFIG['balance_max'])

    def _validate( self, candidate ):
        """ Validates that the given 'candidate' (new state dictionary)
            does not exceed gain limits
        """

        g               = calc_gain( candidate )
        b               = candidate['balance']
        eq_mag, eq_pha  = calc_eq( candidate )

        headroom = self.gain_max - g - np.max(eq_mag) - np.abs(b/2.0)

        if headroom >= 0:
            # APPROVED
            bf_set_gains( candidate )
            bf_set_eq( eq_mag, eq_pha )
            self.state = candidate
            return 'done'
        else:
            # REFUSED
            return 'not enough headroom'

    # Bellow we use *dummy to accommodate the pasysctrl.py parser mechanism wich
    # will include two arguments for any function call, even when not necessary.

    def get_state(self, *dummy):
        #return yaml.dump( self.state, default_flow_style=False )
        self.state['convolver_runs'] = brutefir_runs()      # informative value
        return json.dumps( self.state )

    def get_target_sets(self, *dummy):
        return json.dumps( self.target_sets )

    def set_level(self, value, relative=False):
        candidate = self.state.copy()
        if relative:
            candidate['level'] += round(float(value), 2)
        else:
            candidate['level'] =  round(float(value), 2)
        return self._validate( candidate )

    def set_balance(self, value, relative=False):
        candidate = self.state.copy()
        if relative:
            candidate['balance'] += round(float(value), 2)
        else:
            candidate['balance'] =  round(float(value), 2)
        if abs(candidate['balance']) <= self.balance_max:
            return self._validate( candidate )
        else:
            return 'too much'

    def set_bass(self, value, relative=False):
        candidate = self.state.copy()
        if relative:
            candidate['bass'] += round(float(value), 2)
        else:
            candidate['bass'] =  round(float(value), 2)
        if abs(candidate['bass']) <= self.bass_span:
            return self._validate( candidate )
        else:
            return 'too much'

    def set_treble(self, value, relative=False):
        candidate = self.state.copy()
        if relative:
            candidate['treble'] += round(float(value), 2)
        else:
            candidate['treble'] =  round(float(value), 2)
        if abs(candidate['treble']) <= self.treble_span:
            return self._validate( candidate )
        else:
            return 'too much'

    def set_loud_ref(self, value, relative=False):
        candidate = self.state.copy()
        # this try if intended just to validate the given value
        try:
            if relative:
                candidate['loudness_ref'] += round(float(value), 2)
            else:
                candidate['loudness_ref'] =  round(float(value), 2)
            return self._validate( candidate )
        except:
            return 'bad value'

    def set_loud_track(self, value, *dummy):
        candidate = self.state.copy()
        if type(value) == bool:
            value = str(value)
        try:
            value = { 'on':True , 'off':False, 'true':True, 'false':False,
                      'toggle': {True:False, False:True}[self.state['loudness_track']]
                    } [ value.lower() ]
            candidate['loudness_track'] = value
            return self._validate( candidate )
        except:
            return 'bad option'

    def set_target(self, value, *dummy):
        candidate = self.state.copy()
        if value in self.target_sets:
            candidate['target'] = value
            return self._validate( candidate )
        else:
            return f'target \'{value}\' not available'

    def set_solo(self, value, *dummy):
        if value.lower() in ['off', 'l', 'r']:
            self.state['solo'] = value.lower()
            bf_set_gains( self.state )
            return 'done'
        else:
            return 'bad option'

    def set_mute(self, value, *dummy):
        if type(value) == bool:
            value = str(value)
        try:
            if value.lower() in ['false', 'true', 'off', 'on', 'toggle']:
                value = { 'false':False, 'off':False,
                          'true' :True,  'on' :True,
                          'toggle': {False:True, True:False} [ self.state['muted'] ]
                        } [ value.lower() ]
                self.state['muted'] = value
                bf_set_gains( self.state )
                return 'done'
        except:
            return 'bad option'

    def set_midside(self, value, *dummy):
        if   value.lower() in [ 'mid', 'side', 'off' ]:
            bf_set_midside( value.lower() )
            self.state['midside'] = value.lower()
        else:
            return 'bad option'
        return 'done'

    def get_eq(self, *dummy):
        return yaml.dump( bf_read_eq(), default_flow_style=False )

    def select_source(self, value, *dummy):
        """ this is the source selector """

        def try_select(source):

            if source == 'none':
                jack_clear_preamp()
                return 'done'

            if not source in self.inputs:
                # do nothing
                return f'source \'{source}\' not defined'

            # clearing 'preamp' connections
            jack_clear_preamp()

            # connecting the new SOURCE to PREAMP input
            jack_connect_bypattern( CONFIG['sources'][source]['capture_port'],
                                    'pre_in' )

            # Trying to set the desired xo and drc for this source
            tmp = ''
            c = Convolver()
            try:
                xo = CONFIG["sources"][source]['xo']
                if c.set_xo( xo ) == 'done':
                    self.state['xo_set'] = xo
                else:
                    tmp = f'\'xo:{xo}\' in \'{source}\' is not valid'
                    print('(core)', tmp)
            except:
                pass
            try:
                drc = CONFIG["sources"][source]['drc']
                if c.set_drc( drc ) == 'done':
                    self.state['drc_set'] = drc
                else:
                    tmp += f'\'drc:{xo}\' in \'{source}\' is not valid'
                    print('(core)', tmp)
            except:
                pass
            del(c)

            # end of trying to select the source
            if not tmp:
                return 'done'
            else:
                return tmp

        def on_change_input_behavior(candidate):
            try:
                for option, value in CONFIG["on_change_input"].items():
                    if value != None:
                        candidate[option] = value
            except:
                print( '(config.yml) missing \'on_change_input\' options' )
            return candidate

        result = try_select(value)

        if result:
            self.state['input'] = value
            candidate = self.state.copy()
            candidate = on_change_input_behavior(candidate)
            # Special source loudness_ref overrides the one in on_change_input_behavior
            try:
                candidate["loudness_ref"] = CONFIG["sources"][value]['loudness_ref']
            except:
                pass
            self._validate( candidate )
            return result
        else:
            return f'something was wrong selecting \'{value}\''

    def get_inputs(self, *dummy):
        return json.dumps( [ x for x in self.inputs.keys() ] )

# THE CONVOLVER: DRC and XO Brutefir stages management =========================

class Convolver(object):
    """ attributes:

            drc_coeffs      list of pcm FIRs for DRC
            xo_coeffs       list of pcm FIRs for XOVER
            drc_sets        sets of FIRs for DRC
            xo_sets         sets of FIRs for XOVER
            ways            filtering stages (loudspeaker ways)

        methods:

            set_drc
            set_xo

            get_drc_sets
            get_xo_sets
    """

    def __init__(self):

        # DRC pcm files must be named:
        #    drc.X.DRCSETNAME.pcm   where X must be L | R
        #
        # XO pcm files must be named:
        #   xo.XX[.C].XOSETNAME.pcm     where XX must be:  fr | lo | mi | hi | sw
        #                               and channel C is **OPTIONAL**
        #                               can be: L | R
        #   Using C allows to have dedicated FIR per channel if necessary

        files   = os.listdir(LSPK_FOLDER)
        coeffs  = [ x.replace('.pcm','') for x in files ]
        self.drc_coeffs = [ x for x in coeffs if x[:4] == 'drc.'  ]
        self.xo_coeffs  = [ x for x in coeffs if x[:3] == 'xo.'   ]
        #print('\nxo_coeffs:', xo_coeffs) # debug

        # The available DRC sets
        self.drc_sets = []
        for drc_coeff in self.drc_coeffs:
            drcSetName = drc_coeff[6:]
            if not drcSetName in self.drc_sets:
                self.drc_sets.append( drcSetName )

        # The available XO sets, i.e the last part of a xo_coeff
        self.xo_sets = []
        for xo_coeff in self.xo_coeffs:
            xoSetName = xo_coeff.split('.')[-1]
            if not xoSetName in self.xo_sets:
                self.xo_sets.append( xoSetName )
        #print('xo_sets:', self.xo_sets) # debug

        # Ways are the XO filter stages definded inside brutefir_config
        # 'f.WW.C' where WW:fr|lo|mi|hi|sw and C:L|R
        self.ways = get_brutefir_config('ways')
        # print('ways:', self.ways) # debug

    # Bellow we use *dummy to accommodate the pasysctrl.py parser mechanism wich
    # will include two arguments for any function call, even when not necessary.

    def set_drc(self, drc, *dummy):
        if drc in self.drc_sets or drc == 'none':
            bf_set_drc( drc )
            return 'done'
        else:
            return f'drc set \'{drc}\' not available'

    def set_xo(self, xo_set, *dummy):
        if xo_set in self.xo_sets:
            bf_set_xo( self.ways, self.xo_coeffs, xo_set )
            return 'done'
        else:
            return f'xo set \'{xo_set}\' not available'

    def get_drc_sets(self, *dummy):
        return json.dumps( self.drc_sets )

    def get_xo_sets(self, *dummy):
        return json.dumps( self.xo_sets )


# JCLI: THE CLIENT INTERFACE TO THE JACK SERVER ================================
# IMPORTANT: this module core.py needs JACK to be running.

try:
    JCLI = jack.Client('tmp', no_start_server=True)
except:
    print( '(core.py) ERROR cannot commuticate to the JACK SOUND SERVER.' )

# COMMON USE VARIABLES: ========================================================

UHOME           = os.path.expanduser("~")
CONFIG          = read_yaml( f'{UHOME}/pe.audio.sys/config.yml' )
LSPK_FOLDER     = f'{UHOME}/pe.audio.sys/loudspeakers/{CONFIG["loudspeaker"]}'
STATE_PATH      = f'{UHOME}/pe.audio.sys/.state.yml'
EQ_FOLDER       = f'{UHOME}/pe.audio.sys/share/eq'
EQ_CURVES       = find_eq_curves()

if not EQ_CURVES:
    print( '(core.py) ERROR loading EQ_CURVES from share/eq/' )
    sys.exit()

LOUD_FLAT_CURVE_INDEX = find_loudness_flat_curve_index()

if LOUD_FLAT_CURVE_INDEX < 0:
    print( f'(core) MISSING FLAT LOUDNESS CURVE. BYE :-/' )
    sys.exit()

