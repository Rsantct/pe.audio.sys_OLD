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
    usage:  start.py <mode> [ --log ]

    mode:
        'all '              :   restart all
        'stop' or 'shutdown':   stop all
        'core'              :   restart core except Jackd

    --log   messages redirected to 'pe.audio.sys/start.log'

"""

import os
import sys
import subprocess as sp
from time import sleep
import yaml

ME    = __file__.split('/')[-1]
UHOME = os.path.expanduser("~")
BDIR  = f'{UHOME}/pe.audio.sys'

with open( f'{BDIR}/config.yml', 'r' ) as f:
    CONFIG = yaml.safe_load(f)
LOUDSPEAKER     = CONFIG['loudspeaker']
LSPK_FOLDER     = f'{BDIR}/loudspeakers/{LOUDSPEAKER}'
TCP_BASE_PORT   = CONFIG['peaudiosys_port']


def jack_is_running():
    try:
        sp.check_output( 'jack_lsp >/dev/null 2>&1'.split() )
        return True
    except sp.CalledProcessError:
        return False


def start_jackd():

    jack_backend_options = CONFIG["jack_backend_options"].replace(
                            '$system_card', CONFIG["system_card"] )

    cmdlist = ['jackd'] + f'{CONFIG["jack_options"]}'.split() + \
              f'{jack_backend_options}'.split()
    #print( ' '.join(cmdlist) ) ; sys.exit() # DEBUG

    if 'pulseaudio' in sp.check_output("pgrep -fl pulseaudio",
                                       shell=True).decode():
        cmdlist = ['pasuspender', '--'] + cmdlist

    sp.Popen( cmdlist, stdout=sys.stdout, stderr=sys.stderr )
    sleep(1)

    # Will check if JACK ports are available
    c = 10
    while c:
        if jack_is_running():
            print( f'({ME}) JACKD STARTED' )
            return True
        print( f'({ME}) waiting for jackd ' + '.' * c )
        sleep(.5)
        c -= 1
    return False


def start_brutefir():
    os.chdir( LSPK_FOLDER )
    #os.system('pwd') # debug
    sp.Popen( 'brutefir brutefir_config'.split(), stdout=sys.stdout,
                                                  stderr=sys.stderr )
    os.chdir( UHOME )
    print( f'({ME}) STARTING BRUTEFIR' )
    sleep(1)  # wait a while for Brutefir to start ...


def restart_service( service, address='localhost', port=TCP_BASE_PORT,
                     onlystop=False, todevnull=False ):
    # Stop
    print( f'({ME}) stopping SERVICE: \'{service}\'' )
    sp.Popen( f'pkill -KILL -f "server.py {service}" \
               >/dev/null 2>&1', shell=True, stdout=sys.stdout,
                                             stderr=sys.stderr )
    if onlystop:
        return
    sleep(.25)  # this is necessary because of asyncronous stopping

    # Start
    print( f'({ME}) starting SERVICE: \'{service}\'' )
    cmd = f'python3 {BDIR}/share/server.py {service} {address} {port}'
    if todevnull:
        with open('/dev/null', 'w') as fnull:
            sp.Popen( cmd, shell=True, stdout=fnull, stderr=fnull)
    else:
        sp.Popen( cmd, shell=True, stdout=sys.stdout, stderr=sys.stderr)


def stop_processes(jackd=False):

    # Stop scripts
    if run_level == 'all':
        run_scripts( mode='stop' )

    # Stop services:
    for idx, svc in enumerate( ('preamp', 'players') ):
        port = TCP_BASE_PORT + idx + 1
        restart_service( svc, port=port, onlystop=True )

    # Stop Brutefir
    sp.Popen( 'pkill -KILL -f brutefir >/dev/null 2>&1', shell=True )

    # Stop Jack
    if jackd:
        print( f'({ME}) STOPPING JACKD' )
        sp.Popen( 'pkill -KILL -f jackd >/dev/null 2>&1', shell=True )

    sleep(1)


def prepare_extra_cards( channels=2 ):

    if not CONFIG['external_cards']:
        return

    for card, params in CONFIG['external_cards'].items():
        jack_name = card
        alsacard  = params['alsacard']
        resampler = params['resampler']
        quality   = str( params['resamplingQ'] )
        try:
            misc = params['misc_params']
        except KeyError:
            misc = ''

        cmd = f'{resampler} -d{alsacard} -j{jack_name} ' + \
              f'-c{channels} -q{quality} {misc}'
        if 'zita' in resampler:
            cmd = cmd.replace("-q", "-Q")

        print( f'({ME}) loading resampled extra card: {card}' )
        #print(cmd) # DEBUG
        sp.Popen( cmd.split(), stdout=sys.stdout, stderr=sys.stderr )


def run_scripts(mode='start'):
    for script in CONFIG['scripts']:
        #(i) Some elements on the scripts list from config.yml can be a dict,
        #    e.g the ecasound_peq, so we need to extract the script name.
        if type(script) == dict:
            script = list(script.keys())[0]
        print( f'({ME}) will {mode} the script \'{script}\' ...' )
        sp.Popen( f'{BDIR}/share/scripts/{script} {mode}', shell=True,
                                  stdout=sys.stdout, stderr=sys.stderr )
    if mode == 'stop':
        sleep(.5)  # this is necessary because of asyncronous stopping


def kill_bill():
    """ killing any previous instance of this, becasue
        some residual try can be alive accidentaly.
    """

    # List processes like this one
    processString = f'pe.audio.sys/start.py all'
    rawpids = []
    cmd =   f'ps -eo etimes,pid,cmd' + \
            f' | grep "{processString}"' + \
            f' | grep -v grep'
    try:
        rawpids = sp.check_output( cmd, shell=True ).decode().split('\n')
    except sp.CalledProcessError:
        pass
    # Discard blanks and strip spaces:
    rawpids = [ x.strip().replace('\n', '') for x in rawpids if x ]
    # A 'rawpid' element has 3 fields 1st:etimes 2nd:pid 3th:comand_string

    # Removing the own pid
    own_pid = str(os.getpid())
    for rawpid in rawpids:
        if rawpid.split()[1] == own_pid:
            rawpids.remove(rawpid)

    # Just display the processes to be killed, if any.
    print( '-' * 21 + f' ({ME}) killing running before me ' + '-' * 21 )
    for rawpid in rawpids:
        print(rawpid)
    print( '-' * 80 )

    if not rawpids:
        return

    # Extracting just the 'pid' at 2ndfield [1]:
    pids = [ x.split()[1] for x in rawpids ]

    # Killing the remaining pids, if any:
    for pid in pids:
        print(f'({ME}) killing old \'start.py\' processes:', pid)
        sp.Popen( f'kill -KILL {pid}'.split() )
        sleep(.1)
    sleep(.5)


def check_state_file():
    state_file = f'{BDIR}/.state.yml'
    with open( state_file, 'r') as f:
        state = f.read()
        # if the file is ok, lets backup it
        if 'xo_set:' in state:
            sp.Popen( f'cp {state_file} {state_file}.BAK'.split() )
            print( f'({ME}) (i) .state.yml copied to .state.yml.BAK' )
        # if it is damaged:
        else:
            print( f'({ME}) ERROR \'state.yml\' is damaged, ' +
                    'you can restore it from \'.state.yml.BAK\'' )
            sys.exit()


if __name__ == "__main__":

    run_level = ''
    logFlag = False

    # READING OPTIONS FROM COMMAND LINE
    if sys.argv[1:]:
        mode = sys.argv[1]
    else:
        print(__doc__)
        sys.exit()
    if sys.argv[2:] and '-l' in sys.argv[2]:
        logFlag = True

    if logFlag:
        flog = open( f'{BDIR}/start.log', 'w')
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        sys.stdout = flog
        sys.stderr = flog

    # Lets backup .state.yml to help us if it get damaged.
    check_state_file()

    # KILLING ANY PREVIOUS INSTANCE OF THIS
    kill_bill()

    if mode in ['stop', 'shutdown']:
        run_level = 'all'
        stop_processes(jackd=True)

    elif mode == 'core':
        run_level = 'core'
        stop_processes(jackd=False)

    elif mode == 'all':
        run_level = 'all'
        stop_processes(jackd=True)
        # Trying to start JACKD
        if not start_jackd():
            print('({ME}) Problems starting JACK ')

    else:
        if logFlag:
            sys.stdout = original_stdout
            sys.stderr = original_stderr
        print(__doc__)
        sys.exit()

    if jack_is_running():

        # (i) Importing core.py needs JACK to be running
        import share.core as core

        # JACK LOOPS
        sp.Popen( f'{BDIR}/share/jloops_daemon.py' )
        sleep(1)  # this is necessary, or checking for ports to be activated

        # Running USER SCRIPTS
        run_scripts()

        # BRUTEFIR
        start_brutefir()

        # ADDIGN EXTRA SOUND CARDS RESAMPLED INTO JACK
        prepare_extra_cards()

        # PREAMP  -->   BRUTEFIR  (be careful that both pre_in_loops are alive)
        # Wait 60 sec because Brutefir ports can take some time to be activated.
        core.jack_connect_bypattern('pre_in_loop', 'brutefir', wait=60)

        # RESTORE: audio settings
        state = core.init_audio_settings()
        core.save_yaml(state, core.STATE_PATH)

        # RESTORE source as set under config.yml
        state = core.init_source()
        core.save_yaml(state, core.STATE_PATH)

        # SERVICES (TCP SERVERS):
        # (i) - The 'preamp' control service needs jack to be running.
        #     - From now on, 'preamp' MUST BE the ONLY OWNER of STATE_PATH.
        for idx, svc in enumerate( ('preamp', 'players') ):
            port = TCP_BASE_PORT + idx + 1
            restart_service( svc, port=port )

        # PREAMP  --> MONITORS
        # Needs to check if monitors ports are created, or simply wait a bit.
        if CONFIG["source_monitors"]:
            for monitor in CONFIG["source_monitors"]:
                core.jack_connect_bypattern( 'pre_in_loop', monitor, wait=10 )

    else:
        print( f'({ME}) JACK not detected')

    # The 'peaudiosys' service always runs, so that we can do basic operation
    restart_service( 'peaudiosys', address=CONFIG['peaudiosys_address'],
                      todevnull=True )

    if logFlag:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        print( f'start process logged at \'{BDIR}/start.log\'' )
