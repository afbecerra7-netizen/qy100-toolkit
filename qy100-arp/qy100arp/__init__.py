"""Arpegiador y secuenciador generativo externo para el Yamaha QY100.

El QY100 no trae arpegiador (verificado: cero menciones en el manual de usuario
ni en el service manual). Este paquete lo aporta desde fuera, por MIDI, sin
tocar el firmware del equipo.

El QY100 manda el reloj; nosotros lo seguimos. Todo el motor se mueve por ticks
de MIDI Clock (24 por negra), asi que no hay deriva posible entre ambos.
"""

__all__ = ["arp", "clock", "engine", "euclid", "generative", "midiio", "scales"]
