Loopback ports provides:

- A generic preamp input

- Ports to players (like Mplayer or MPD) to connect their streams without to bind directly to the preamp.

Previous versions of pe.audio.sys provided several loops for each player instance so that sources can be easily identified and switched.

This method needs to maintain several jack python callbacks threads to loop audio frames. This needs lots of CPU ~10% under modest machines (Raspberry PI an so)

A better option is to use jackd -L N, which provides a group of N loopback ports:


These ones are C pure callbacks, so CPU compsumption is negligible.

We can easily identify each loop pair thanks to ALIAS mechanism in Jack.

As a drawback, Mplayer doesn't knows how to connect to an alias, neither how to connect to a specific ports belonging to a group.

This is a limitation on Mplayer, so we will assume it.

In practice, there is no problem at all, unless you force to load audio streams in several Mplayer instances at once.


