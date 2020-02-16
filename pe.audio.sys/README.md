# Credits

This is based on the former **FIRtro** and the current **pre.di.c** projects, as PC based digital preamplifier and crossover projects, designed by the pioneer **@rripio** and later alongside others contributors.

### https://github.com/rripio/pre.di.c

### https://github.com/AudioHumLab/FIRtro/wiki


# Overview

The system is intended as a personal audio system based on a PC.

The originary main features were:

- Digital crossover for sophysticated loudspeakers management
- Preamplifier with loudness compensated and calibrated volume control.
- Web page for system control (FIRtro)

 Additional features on **pe.audio.sys** are extended to involve:

- Music players management.
- Auxiliary system functions management (amplifier switching, ...).
- New control web page layout.

Most of the system is written in Python3, and config files are YAML kind of, thanks **@rripio**.

The control of the system is based on a tcp server architecture, thanks **@amr**.

The system core is mainly based on:

- JACK: the sound server (wiring audio streams and sound card interfacing)

- BRUTEFIR, a convolution engine that supports:

    - XOVER FIR filtering (multiway active loudspeaker crossover filtering)
    - DRC FIR filtering (digital room correction)
    - EQ: bass, treble, dynamic loudness compensation curves, in-room target eq curves.
    - LEVEL control.

# Controling the system

A web page front end is provided so you can easily control the system as well your integrated music players.

**@rripio** has also an IR interface than can be adapted to control through by an infrared remote.

Anyway the control of the system works through by **a TCP listening socket** that accepts **a set of commands**.

Some commands have aliases to keep backwards compatibility from FIRtro or pre.di.c controllers.

### Geeting help
 
    help                        This help

### Getting info:

    state | status | get_state  Returns the whole system status parameters,
                                as per stored in .state.yml
    get_inputs                  List of available inputs
    get_eq                      Returns the current Brutefir EQ stage (freq, mag ,pha)
    get_target_sets             List of target curves sets available under the eq folder
    get_drc_sets                List of drc sets available under the loudspeaker folder
    get_xo_sets                 List of xover sets available under the loudspeaker folder

### Selector stage:

    input | source  <name>
    solo            off |  l  | r
    mono            off | on  | toggle     ( aka midside => mid )
    midside         off | mid | side
    mute            off | on  | toggle

### Gain and Eq stage:

    level           xx [add]               'xx' in dB, use 'add' for a relative adjustment
    balance         xx [add]
    treble          xx [add]
    bass            xx [add]
    loudness_ref    xx [add]
    loudness | loudness_track     on | off | toggle   Loudness compensation
    set_target       <name>                           Select a target curve

### Convolver stages:

    set_drc | drc    <name>                 Select a DRC FIR set
    set_xo  | xo     <name>                 Select a XOVER FIR set

## Monitoring the system

The provided web page will show the system status as well music player's information.

An LCD service is provided to plug a LCD display to show the system status as well metadata from players.

You can also use the above getting info commands, through by a TCP connection.

## Tools

Some nice tools are provided under your `~/bin` folder, below a brief description.

    $HOME/bin/
          |
     ____/
    /
    |-- peaudiosys_control                  A command line tool to issue commands to the system
    |
    |-- peaudiosys_service_restart.sh       Restart or stop a service (for more info see config.yml)
    |
    |-- peaudiosys_view_brutefir.py         Shows the running Brutefir configuration:
    |                                       mapping to sound card ports, coeffs and filters running
    |
    |-- peaudiosys_plot_brutefir_eq.py      Plot the runtime EQ module in Brutefir
    |
    |-- peaudiosys_plot_eq_curves.py        A tool to plot the curves under the share/eq folder
    |
    |-- peaudiosys_do_target.py             Make target curves



# Filesystem tree

All files are hosted under **`$HOME/pe.audio.sys`**, so that you can run `pe.audio.sys` under any user name.

That way you can keep any `~/bin` an other files and directories under your home directory.

1st level contains the firsthand files (system configuration and the system start script) and the firsthand folders (loudspeakers, user macros).

Deeper `share/` levels contains runtime files you don't usually need to access to.


    $HOME/pe.audio.sys/
          |
     ____/
    /
    |-- README.md           This file
    |
    |-- pasysctrl.hlp       Help on system control commands
    |
    |-- .state.yml          The file that keeps the run-time system state
    |
    |-- config.yml          The main configuration file
    |
    |-- xxxx.yml            Other configuration files
    |
    |-- .asound.XXX         ALSA sound cards restore settings, see scripts/sound_cards_prepare.py
    |
    |-- start.py            This starts up or shutdown the whole system
    |
    |-- macros/             End user general purpose macro scripts (e.g. web interface buttons)
    |
    |-- doc/                Support documents
    |
    |-- loudspeakers/       
    |   |
    |   |-- lspk1/          Loudspeaker files: brutefir_config, xo & drc pcm FIRs
    |   |-- lspk2/
    |   |-- ...
    |
    \-- share/              System modules (the core and the tcp server)
        |
        |-- eq/             Tone, loudness and target curves .dat files
        |
        |-- services/       Services provided through by the tcp server (system control and others)
        |
        |-- scripts/        Additional scripts to launch at start up when issued at config.yml,
        |                   advanced users can write their own here.
        |
        \-- www/            A web interface to control the system



# Configuration: the `config.yml` file

All system features are configured under **`config.yml`**.

We provide a **`config.yml.example`** with clarifying comments, please take a look on it because you'll find there some useful info.

Few user scripts or shared modules can have its own `xxx.yml` file of the same base name for configuration if necessary.

This file allows to configure the whole system.

Some points:

- The **list of services** addressing here will trigger auto launching each service. The **`pasysctlr`** service is mandatory.

- The necessary preamp **loop ports** will be auto spawn under JACK when source `capture_ports` are named `xxx_loop` under the `sources:` section, so your player scripts have not to be aware of create loops, just configure the players to point to these preamp loops accordingly.

- You can force some audio **settings at start up**, see `init_xxxxx` options.

- You can force some audio **settings when change the input source**, see `on_change_input:` section.


Here you are an uncommented bare example of `config.yml`:


    services_addressing:

        pasysctrl_address:      0.0.0.0
        pasysctrl_port:         9989

        aux_address:            localhost
        aux_port:               9988

        players_address:        0.0.0.0
        players_port:           9987

    system_card: hw:UDJ6

    external_cards:

    jack_options:           -R -d alsa
    jack_backend_options:   -d $system_card -r 48000 -P -o 6


    balance_max:    6.0
    gain_max:       0.0

    loudspeaker: SeasFlat
    ref_level_gain: -10.0

    on_init:
        xo:                 mp
        drc:                mp_multipV1
        target:             +4.0-2.0_target
        level:              
        max_level:          -20
        muted:              false
        bass:               0
        treble:             0
        balance:            0
        loudness_track:     true
        loudness_ref:       6.0     # most records suffers loudness war mastering
        midside:            'off'
        solo:               'off'
        input:              'mpd'

    on_change_input:
        bass:               0.0
        treble:             0.0
        loudness_track:     True
        loudness_ref:       6.0     # most records suffers loudness war mastering
        midside:           'off'
        solo:              'off'

    sources:
        spotify:
            capture_port:   alsa_loop
            gain:           0.0
            xo:             mp
        mpd:
            capture_port:   mpd_loop
            gain:           0.0
            xo:             mp
        istreams:
            capture_port:   mplayer_istreams
            gain:           0.0
            xo:             mp
        salon:
            capture_port:   zita-n2j
            gain:           0.0
            xo:             mp

    source_monitors:

    scripts:
        - sound_cards_prepare.py
        - mpd.py
        - istreams.py
        - pulseaudio-jack-sink.py
        - librespot.py
        - zita-n2j_mcast.py

    aux:
        amp_manager:  /home/predic/bin/ampli.sh


# The share/eq folder

This folder contains the set of curves that will be used to apply "soft" EQ to the system, i.e.: tone, loudness compensation and psychoacoustic room dimension equalization (aka 'target').

(i) The curves will be rendered under the EQ stage on Brutefir, so your `brutefir_config` file must have an `"eq"` section properly configured with the same frequency bands as the contained into your xxxxxxxfreq.dat file. More info: https://www.ludd.ltu.se/~torger/brutefir.html#bflogic_eq

Similar to the loudspeaker folder, some rules here must be observed when naming files:

- Frequencies: `xxxxxxfreq.dat`
- Tone: `xxxxxxbass_mag.dat xxxxxxbass_pha.dat xxxxxxtreble_mag.dat xxxxxxtreble_pha.dat` 
- Loudness: `xxxxxxloudness_mag.dat xxxxxxloudness_pha.dat`
- Target: `yyyyyytarget_mag.dat yyyyyytarget_pha.dat` ... ...

On freq, tone and loudness files the xxxxxx part is optional.

On target files yyyyyyy is also optional but neccessary if more than one target set is desired.

You can issue the commands **`get_target_sets`** and **`set_target yyyyyytarget`** to manage the target eq.

The set of tone and loudness curves provided on this distro are the ones from the original **FIRtro** project from the pioneer **@rripio**

You can easily visualize these curves by using the command line tool `peaudiosys_plot_eq_curves.py`

### Optional share/eq files

If you want to use another sound processors, you can hold here some more files.

For instance, you can use Ecasound to add a parametric EQ processor before Brutefir, for more info see the section `scripts:` under the provided `config.yml.example` file.

# The audio routing

Here you are a typical JACK wiring screenshot.

The selected source is an MPD player wich is configured to point to the mpd_loop ports.

The preamp has a unique entrance point: the pre_in_loop. This loops feeds the main audio processor, i.e Brutefir.

You can add another audio processor, e.g. an Ecasound parametric EQ plugin. We provide hera a script that INSERTS it after the pre_in_loop and before the Brutefir input.

You are free to insert any other sound processor, Jack is your friend. To automate it on start up, you can prepare an appropriate script.

Brutefir is the last element and the only one that interfaces with the sound card Jack ports. The loudspeakers are a two way set, connected at the last sound card ports. 

![jack_wiring](https://github.com/Rsantct/pe.audio.sys/blob/master/pe.audio.sys/doc/images/jack_routing_sample.png)


# The loudspeaker

Loudspeaker config files kind of are leaved, only **`brutefir_config`** has to be adjusted to set the proper coeff levels and xover scheme, as well as the system card wiring and the delays on each port.

( for more info on `brutefir_config` please see `doc/Configuration.md` )

So *keep only useful files* under your loudspeaker folder, and *name them meaningfully*.

For control purposes, XO and DRC pcms will be scanned from the list of files found under the loudspeker folder.

Please name files as follows:


DRC pcm files must be named:

    drc.X.DRCSETNAME.pcm      where X must be L | R

XO pcm files must be named:

    xo.XX[.C].XOSETNAME.pcm   where XX must be:  fr | lo | mi | hi | sw
                              and channel C is OPTIONAL, can be: L | R

    Using C allows to have DEDICATED DRIVER FIR FILTERING if desired.  

    (fr: full range; lo,mi,hi: low,mid,high; sw: subwoofer)

### Full range loudspeaker w/o correction 'xo' filter

If you want not to use any xo filter at all, you simply do:

- configure `brutefir_config` with coeff -1:

        filter "f.fr.L" {
            from_filters: "f.drc.L";
            to_outputs:   "fr.L"/0.0/+1;
            coeff:        -1;
        };

        filter "f.fr.R" {
            from_filters: "f.drc.R";
            to_outputs:   "fr.R"/0.0/+1;
            coeff:        -1;
        };

- Leave blank `xo_init:` inside `config.yml`

- Leave blank `xo_set:` inside `.state.yml`

- Omit any `xo....pcm` file inside your loudspeaker folder.





