"""Formato de las canciones del QY100.

Direcciones `11 nn tr` (`P=1`), analogas a las de patron. Lo descifrado aqui es
la **pista de patron (`Pt`)**, que es la que dice que estilo y que seccion suena
en cada compas: es lo que convierte patrones sueltos en una cancion.

Vive en `tr = 0x19` (25). A diferencia de las pistas de patron, **no lleva el
prefijo de 26 bytes**: el flujo de eventos empieza en el byte 0.

Gramatica, medida contra el equipo con una cancion creada a mano compas a
compas sobre un aparato recien borrado —asi todo lo que aparecia era lo que se
acababa de meter—:

    F0 00        inicio, igual que en las pistas de patron
    F4 nn        estilo de USUARIO nn+1   (U1 -> F4 00)
    F5 nn        estilo PRESET nn+1       (001 -> F5 00)
    F3 nn        seccion: 0 Intro, 1 Main A, 2 Main B, 3 Fill AB,
                 4 Fill BA, 5 Ending
    C0 01        separador de compas: va ENTRE entradas, no tras cada una
    F2           fin

Verificado: `F3 05` salio al meter `Ending`, con un salto de la seccion 2 a la
5 que descarta que la codificacion fuera consecutiva por casualidad. Y `F4`/`F5`
son eventos distintos, no un rango dentro del mismo byte, lo que permite mezclar
los 128 estilos de fabrica con los 64 de usuario sin ambiguedad.

La cabecera de cancion (`tr=0x7F`) son **6 bloques**, uno mas que la de patron, y
comparte estructura: tempo en los bytes 0-1 en decimas de BPM, y el nombre en
los bytes 10-17 (en la de patron esta en 6-13).

La **pista de acordes (`Cd`)** esta en `tr = 0x1A` (26) y tambien descifrada:
ver mas abajo. Con las dos, una cancion se puede escribir entera desde el
software.

Los dos decodificadores reproducen los bytes del equipo **exactamente**, no solo
eventos equivalentes.
"""

from __future__ import annotations

from .patternfmt import SECTIONS, pack, unpack

PT_TRACK = 0x19             # pista de patron dentro de la cancion
HEADER_TR = 0x7F
HEADER_BLOCKS = 6

EV_INICIO = 0xF0
EV_SECCION = 0xF3
EV_USUARIO = 0xF4
EV_PRESET = 0xF5
EV_FIN = 0xF2
SEPARADOR = (0xC0, 0x01)

TEMPO_OFF = 0
NAME_OFF, NAME_LEN = 10, 8

MAX_USUARIO = 64
MAX_PRESET = 128


class Compas:
    """Un compas de la pista de patron: que estilo y que seccion suenan."""

    __slots__ = ("estilo", "usuario", "seccion")

    def __init__(self, estilo, seccion, usuario=True):
        self.estilo = estilo            # 1-64 si usuario, 1-128 si preset
        self.usuario = usuario
        self.seccion = seccion          # 0-5

    def __repr__(self):
        return "Compas(%s%d, %s)" % ("U" if self.usuario else "",
                                     self.estilo, SECTIONS[self.seccion])

    def __eq__(self, o):
        return (isinstance(o, Compas) and
                (self.estilo, self.usuario, self.seccion) ==
                (o.estilo, o.usuario, o.seccion))


def decode_pattern_track(payload, max_compases=512):
    """Devuelve la lista de `Compas` de una pista Pt.

    `payload` son los 147 bytes crudos del bloque.
    """
    d = unpack(payload)
    fuera = []
    estilo = usuario = seccion = None
    i = 0
    for _ in range(max_compases * 4):
        if i >= len(d):
            break
        s = d[i]
        if s == EV_FIN:
            break
        if s in (EV_INICIO, EV_SECCION, EV_USUARIO, EV_PRESET) or 0xC0 <= s <= 0xCF:
            if i + 1 >= len(d):
                break
            arg = d[i + 1]
            if s == EV_USUARIO:
                estilo, usuario = arg + 1, True
            elif s == EV_PRESET:
                estilo, usuario = arg + 1, False
            elif s == EV_SECCION:
                seccion = arg
            elif 0xC0 <= s <= 0xCF:          # separador: cierra el compas
                if estilo is not None and seccion is not None:
                    fuera.append(Compas(estilo, seccion, usuario))
                    estilo = seccion = None
            i += 2
        else:
            i += 1
    if estilo is not None and seccion is not None:
        fuera.append(Compas(estilo, seccion, usuario))
    return fuera


def encode_pattern_track(compases):
    """Construye la pista Pt. Devuelve los 147 bytes listos para `build_dump`.

    **Verificado contra el equipo** (2026-08-08): una cancion escrita entera por
    SysEx —cabecera con nombre y tempo, mas esta pista apuntando a un estilo de
    usuario— se releyo exacta y sono, con sus transiciones de seccion y parando
    sola al final.

    Ojo con el tamano: el encadenado de bloques en canciones **no** esta
    comprobado, asi que la pista tiene que caber en uno. Son 4 bytes la primera
    entrada y 6 cada una despues, mas inicio y fin: **unos 21 compases de tope**.
    """
    out = bytearray([EV_INICIO, 0x00])
    for k, c in enumerate(compases):
        if not 0 <= c.seccion < len(SECTIONS):
            raise ValueError("seccion fuera de rango 0-5: %r" % (c.seccion,))
        tope = MAX_USUARIO if c.usuario else MAX_PRESET
        if not 1 <= c.estilo <= tope:
            raise ValueError("estilo fuera de rango 1-%d: %r" % (tope, c.estilo))
        if k:
            out += bytes(SEPARADOR)
        out += bytes([EV_USUARIO if c.usuario else EV_PRESET, c.estilo - 1])
        out += bytes([EV_SECCION, c.seccion])
    out += bytes([EV_FIN])
    if len(out) > 128:
        raise ValueError("no cabe en un bloque: %d bytes. El encadenado de "
                         "bloques en canciones no esta comprobado." % len(out))
    return pack(bytes(out) + bytes(128 - len(out)))


def decode_header(payloads):
    """(nombre, tempo) de la cabecera de cancion."""
    d = b"".join(unpack(p) for p in payloads)
    nombre = bytes(d[NAME_OFF:NAME_OFF + NAME_LEN]).decode("ascii", "replace").rstrip()
    return nombre, ((d[TEMPO_OFF] << 8) | d[TEMPO_OFF + 1]) / 10.0


# --- Pista de acordes (Cd) ----------------------------------------------
#
# `tr = 0x1A` (26), justo al lado de la de patron, y tampoco lleva prefijo.
#
#     F0 00                inicio
#     D0 <raiz> <tipo> 0C 1C   un acorde
#     80 04                avance de compas (4 tiempos)
#     F2                   fin
#
# **La raiz y el tipo usan la misma codificacion que en los patrones**: raiz en
# semitonos con Do=0, y tipo segun `patternfmt.CHORD_TYPES`. Verificado con tres
# acordes elegidos para separar los campos: Cm7 y Fm7 comparten tipo y cambian
# raiz; Fm7 y G7 cambian los dos. Los tres salieron exactos.
#
# Los dos bytes `0C 1C` del final valen siempre lo mismo en lo medido y **no
# estan identificados**. El `1C` coincide con el valor de la signatura 4/4 en la
# cabecera de patron, y el `0C` con un array de la cabecera que ya probamos que
# no era la signatura; puede ser coincidencia. No se tocan: se copian.

CD_TRACK = 0x1A
EV_ACORDE = 0xD0
EV_AVANCE = 0x80
ACORDE_COLA = (0x0C, 0x1C)      # sin identificar; se reproduce tal cual


class Acorde:
    __slots__ = ("raiz", "tipo")

    def __init__(self, raiz, tipo):
        self.raiz, self.tipo = raiz, tipo       # raiz 0-11, tipo 0-26

    def __repr__(self):
        from .patternfmt import CHORD_ROOTS, CHORD_TYPES
        nom = next((k for k, v in CHORD_TYPES.items() if v == self.tipo), "?%d" % self.tipo)
        return "%s%s" % (CHORD_ROOTS[self.raiz % 12], nom)

    def __eq__(self, o):
        return isinstance(o, Acorde) and (self.raiz, self.tipo) == (o.raiz, o.tipo)


def decode_chord_track(payload, max_acordes=512):
    """Lista de `Acorde` de la pista Cd."""
    d = unpack(payload)
    fuera = []
    i = 0
    for _ in range(max_acordes * 3):
        if i >= len(d) or d[i] == EV_FIN:
            break
        s = d[i]
        if s == EV_ACORDE and i + 4 < len(d):
            fuera.append(Acorde(d[i + 1], d[i + 2])); i += 5
        elif s == EV_INICIO or s == EV_AVANCE:
            i += 2
        else:
            i += 1
    return fuera


def encode_chord_track(acordes):
    """Construye la pista Cd, un acorde por compas.

    **Sin verificar contra el equipo**: leer esta comprobado, escribir no.
    """
    from .patternfmt import CHORD_TYPE_MAX
    out = bytearray([EV_INICIO, 0x00])
    for k, a in enumerate(acordes):
        if not 0 <= a.raiz <= 11:
            raise ValueError("raiz fuera de rango 0-11: %r" % (a.raiz,))
        if not 0 <= a.tipo <= CHORD_TYPE_MAX:
            raise ValueError("tipo de acorde fuera de rango 0-%d: %r"
                             % (CHORD_TYPE_MAX, a.tipo))
        if k:
            out += bytes([EV_AVANCE, 0x04])
        out += bytes([EV_ACORDE, a.raiz, a.tipo]) + bytes(ACORDE_COLA)
    out += bytes([EV_FIN])
    if len(out) > 128:
        raise ValueError("no cabe en un bloque: %d bytes" % len(out))
    return pack(bytes(out) + bytes(128 - len(out)))


# --- Las 16 pistas de secuenciador --------------------------------------
#
# `tr = 0..15` para las pistas 1 a 16. Cada una tiene su canal MIDI, lo que las
# hace ideales para rutear a instrumentos externos o a un DAW: no dependen del
# mapeo fijo por posicion que impone `PATT OUT CH` en modo patron.
#
# **Misma gramatica de notas que las pistas de patron** —eventos de tiempo y de
# nota con gate, altura y velocity— y **sin el prefijo de 26 bytes**: el flujo
# empieza en el byte 0, como en `Pt` y `Cd`. Medido grabando una sola nota:
# `F0 00 | D0 6C 3C 70 | F2` = gate 108, nota 60, velocity 112.
#
# Ventaja frente a los patrones para temas largos: aqui no hay secciones ni
# tope de 32 compases. La cancion dura lo que dure.

MIDI_TRACKS = 16


def midi_track_addr_byte(pista):
    """`tr` de la pista 1-16 de una cancion."""
    if not 1 <= pista <= MIDI_TRACKS:
        raise ValueError("pista fuera de rango 1-%d: %r" % (MIDI_TRACKS, pista))
    return pista - 1


def decode_midi_track(payloads):
    """(notas, relojes) de una pista de secuenciador, encadenando bloques."""
    from .patternfmt import decode_blocks
    return decode_blocks(payloads, start=0)


def encode_midi_track(notas, total_clocks):
    """Bloques de una pista de secuenciador. Sin prefijo, marcador incluido."""
    from .patternfmt import encode_blocks
    return encode_blocks(notas, total_clocks, prefix=None, start=0)


# --- Mezclador de la cancion --------------------------------------------
#
# Mismo esquema que el de patron pero con **arrays de 16**, uno por pista de
# secuenciador. Localizado por paralelismo: en la cabecera de patron el orden es
# programa, bandera de bateria, volumen, panoramico, ..., reverb, y aqui
# aparecen los mismos valores por defecto (100, 64, 40) en 96, 112 y 160.
# Retrocediendo dos arrays de 16 desde el volumen salen 64 y 80.
#
# Explica por que una cancion recien escrita suena entera a piano: el programa
# vale 0 en las 16 pistas, y 0 es GrandPno.
#
# **El banco esta en el byte 32, no junto al programa**, y guarda el numero real
# (127 para percusion) en vez de una bandera. Se midio poniendo un kit desde el
# panel y comparando: cambiaron el 32 (a 127) y el 64 (el programa). Antes se
# habia supuesto una bandera en el 80 por analogia con el mezclador de patron, y
# era falso: la pista sonaba a SteelGtr, que es el programa 25 del banco normal.

MIX_BANK_OFF = 32           # 0 normal, 127 percusion, 126 efectos
MIX_PROG_OFF = 64           # programa de voz, base cero
MIX_VOL_OFF = 96
MIX_PAN_OFF = 112
MIX_REVERB_OFF = 160


def decode_mixer(payloads):
    """Estado del mezclador, una entrada por pista 1-16."""
    d = b"".join(unpack(p) for p in payloads)
    return [{"banco": d[MIX_BANK_OFF + k], "programa": d[MIX_PROG_OFF + k],
             "volumen": d[MIX_VOL_OFF + k], "panoramico": d[MIX_PAN_OFF + k],
             "reverb": d[MIX_REVERB_OFF + k]} for k in range(MIDI_TRACKS)]


def set_mixer(payloads, pista, programa=None, banco=None,
              volumen=None, panoramico=None, reverb=None):
    """Ajusta una pista 1-16 del mezclador de cancion."""
    if not 1 <= pista <= MIDI_TRACKS:
        raise ValueError("pista fuera de rango 1-%d: %r" % (MIDI_TRACKS, pista))
    d = bytearray(b"".join(unpack(p) for p in payloads))
    if len(d) < MIX_REVERB_OFF + MIDI_TRACKS:
        raise ValueError("cabecera incompleta: %d bytes" % len(d))
    k = pista - 1
    for valor, off, nombre in ((programa, MIX_PROG_OFF, "programa"),
                               (banco, MIX_BANK_OFF, "banco"),
                               (volumen, MIX_VOL_OFF, "volumen"),
                               (panoramico, MIX_PAN_OFF, "panoramico"),
                               (reverb, MIX_REVERB_OFF, "reverb")):
        if valor is None:
            continue
        if not 0 <= valor <= 127:
            raise ValueError("%s fuera de rango 0-127: %d" % (nombre, valor))
        d[off + k] = valor
    return [pack(bytes(d[i:i + 128])) for i in range(0, len(d), 128)]
