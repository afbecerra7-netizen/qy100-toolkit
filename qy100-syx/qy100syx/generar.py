"""Convierte los motores generativos de `qy100-arp` en pistas de patron del QY100.

La idea del proyecto entero: en vez de que un ordenador toque el arpegio en
directo, se **hornea** dentro del QY100 como frase de usuario y el equipo queda
tocando solo, sin nada conectado.

Los motores (`EuclidLane`, `MarkovMelody`) avanzan por ticks de reloj MIDI a 24
PPQN. El QY100 usa 480 relojes por negra, o sea **exactamente 20 relojes por
tick**: la conversion es un producto entero, sin redondeos ni deriva.

Aqui se ejecutan en frio, sin hardware ni tiempo real: se recorre el rango de
ticks del patron y se recoge lo que cada motor produce.

Nota sobre acordes
------------------
El QY100 **rearmoniza** las frases contra su pista de acordes segun el `TYPE`
de la pista (manual p. 58): `Bypass` no toca nada, `Chord 1`/`Chord 2` las
reinterpretan sobre el acorde actual, `Parallel` solo transpone. Lo que se
genera aqui son alturas literales; que suenen tal cual o rearmonizadas lo decide
ese ajuste **en el equipo**, no este codigo. Para oir exactamente lo generado,
pon la pista en `Bypass`.
"""

from __future__ import annotations

import os
import sys

from .patternfmt import (CLOCKS_PER_QUARTER, Note, encode_blocks,
                         gate_for, section_clocks)

# `qy100-arp` es un proyecto hermano con su propio venv, pero sus motores no
# usan nada de terceros (solo `random` y `collections`), asi que basta con
# ponerlo en el path. Si algun dia dependen de algo instalado, esto fallara de
# forma ruidosa y habra que replantearlo.
_ARP = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "qy100-arp")

PPQN_MIDI = 24
CLOCKS_POR_TICK = CLOCKS_PER_QUARTER // PPQN_MIDI      # 20, exacto


def _motores():
    if _ARP not in sys.path:
        sys.path.insert(0, _ARP)
    try:
        from qy100arp.generative import EuclidLane, MarkovMelody
    except ImportError as e:
        raise SystemExit(
            "No encuentro los motores generativos en %s (%s).\n"
            "Se esperan en la carpeta hermana qy100-arp." % (_ARP, e))
    return EuclidLane, MarkovMelody


def render(motor, compases, beats_per_bar=4, ratio_gate=None):
    """Ejecuta un motor sobre `compases` y devuelve (notas, relojes_totales).

    `ratio_gate` fuerza el gate como fraccion de la figura; si es None se usa el
    que devuelva el motor. El QY100 usa 90 % por defecto (`gate_for`).
    """
    total_ticks = compases * beats_per_bar * PPQN_MIDI
    notas = []
    for t in range(total_ticks):
        for altura, vel, gate_ticks in motor.on_tick(t):
            gate = (gate_for(gate_ticks * CLOCKS_POR_TICK, ratio_gate)
                    if ratio_gate is not None else gate_ticks * CLOCKS_POR_TICK)
            notas.append(Note(pitch=altura, velocity=vel,
                              gate=max(1, gate), time=t * CLOCKS_POR_TICK))
    return notas, section_clocks(compases, beats_per_bar)


def euclidiano(compases, pulsos=5, pasos=16, nota=36, rotacion=0,
               division="1/16", velocity=100, semilla=None, beats_per_bar=4):
    """Linea de percusion con reparto euclidiano E(pulsos, pasos)."""
    import random
    EuclidLane, _ = _motores()
    lane = EuclidLane({"steps": pasos, "pulses": pulsos, "rotation": rotacion,
                       "note": nota, "division": division,
                       "velocity": velocity, "gate_ticks": 1},
                      rng=random.Random(semilla))
    return render(lane, compases, beats_per_bar)


def melodia(compases, root="C", escala="minor", octava=4, division="1/16",
            densidad=0.6, velocity=90, semilla=None, beats_per_bar=4,
            rango=8, stepwise=1.0, tonal_pull=1.0):
    """Melodia por cadena de Markov sobre grados de escala."""
    _, MarkovMelody = _motores()
    m = MarkovMelody({"root": root, "scale": escala, "base_octave": octava,
                      "division": division, "density": densidad,
                      "velocity": velocity, "range_degrees": rango,
                      "stepwise": stepwise, "tonal_pull": tonal_pull,
                      "seed": semilla})
    return render(m, compases, beats_per_bar)


def a_bloques(notas, total_clocks, prefijo):
    """Empaqueta unas notas generadas en bloques listos para `build_dump`.

    `prefijo` son los 26 bytes del primer bloque de una pista real: llevan
    informacion que todavia no entendemos (nombre de frase, y muy probablemente
    TYPE, SOURCE CHORD y los limites de altura de la tabla de frase), asi que se
    copian de un volcado en vez de inventarlos.
    """
    return encode_blocks(notas, total_clocks, prefix=prefijo)


def resumen(notas, total_clocks):
    """Una linea por compas con las alturas, para revisar antes de escribir."""
    por_compas = {}
    for n in notas:
        por_compas.setdefault(n.time // (CLOCKS_PER_QUARTER * 4), []).append(n)
    filas = []
    for c in sorted(por_compas):
        alturas = " ".join("%3d" % n.pitch for n in por_compas[c])
        filas.append("  compas %2d: %2d notas  %s" % (c + 1, len(por_compas[c]), alturas))
    filas.append("  total: %d notas, %d relojes (%.2f compases)"
                 % (len(notas), total_clocks, total_clocks / 1920.0))
    return "\n".join(filas)


# --- Banco de voces -----------------------------------------------------
#
# Extraido de la ROM del firmware (`extraer_rom.py`) y anclado en dos puntos
# medidos en el equipo: GrandPno = programa 0 y SquareLd = programa 80. Los dos
# caen exactos, asi que la numeracion de las voces normales es directa.
#
# **Los kits de bateria no.** Su orden en la ROM esta, pero el numero de
# programa no: por indice, Dr010 daria AnalgKit y el equipo mostraba DarkKit. En
# XG los kits ocupan numeros de programa no consecutivos. Hay que medirlos.

import json as _json
import os as _os

_VOCES = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                       "voces.json")
_cache = None


def banco():
    global _cache
    if _cache is None:
        with open(_VOCES) as fh:
            _cache = _json.load(fh)
    return _cache


def voz_por_nombre(nombre):
    """'SquareLd' -> 80 (programa base cero). Acepta may/minusculas.

    **Solo las 128 primeras son direccionables.** `voces.json` guarda los 525
    nombres en una lista plana, y su indice coincide con el numero de programa
    unicamente hasta la 127; de ahi en adelante son variaciones en otros bancos
    XG cuyo *bank LSB* nunca se descifro. Devolver el indice sin mas produce un
    programa fuera de 0..127, que en MIDI ni siquiera es un valor legal y en el
    mezclador se escribiria truncado.
    """
    lista = banco()["normales_por_programa"]
    n = nombre.strip().lower()
    for k, v in enumerate(lista):
        if v.lower() == n:
            if k > 127:
                raise ValueError(
                    "'%s' es la voz %d: pasa de 127, asi que es una variacion "
                    "de banco XG y no sabemos su bank LSB. Usa una de las 128 "
                    "basicas (`buscar_voz` las lista con su numero)." % (nombre, k))
            return k
    raise ValueError("voz desconocida: %r. Prueba `buscar_voz`." % (nombre,))


def buscar_voz(texto):
    """Devuelve [(programa_base_cero, nombre)] con las que contengan `texto`."""
    t = texto.strip().lower()
    return [(k, v) for k, v in enumerate(banco()["normales_por_programa"])
            if t in v.lower()]


def kit_por_nombre(texto):
    """'Dark Room' -> (banco, programa_base_cero). Busca por trozo del nombre."""
    t = texto.strip().lower()
    hits = [k for k in banco()["kits"] if t in k["nombre"].lower()]
    if not hits:
        raise ValueError("kit desconocido: %r. Disponibles: %s"
                         % (texto, ", ".join(k["nombre"] for k in banco()["kits"])))
    if len(hits) > 1:
        exactos = [k for k in hits if k["nombre"].lower() == t]
        if len(exactos) != 1:
            raise ValueError("ambiguo %r: %s"
                             % (texto, ", ".join(k["nombre"] for k in hits)))
        hits = exactos
    return hits[0]["banco"], hits[0]["programa"]


# --- Forma musical ------------------------------------------------------
#
# Los motores producen rejilla perfecta y velocity constante, que es lo que hace
# que suene a maquina. Estas funciones trabajan sobre las notas ya generadas, no
# dentro de los motores, para no tocar `qy100-arp`, que se usa en directo.
#
# El formato admite velocity por nota desde el principio y no la estabamos
# usando para nada.

import random as _random


def acentuar(notas, fuerte=None, medio=None, flojo=None, beats_per_bar=4):
    """Da peso metrico: acento en el primer tiempo del compas, medio en los
    demas tiempos, flojo entre tiempos.

    Es la diferencia entre una secuencia de golpes iguales y algo que tiene
    pulso. Los valores por defecto (110/95/70) son un contraste claro sin
    llegar a que las notas flojas desaparezcan.
    """
    fuerte = 110 if fuerte is None else fuerte
    medio = 95 if medio is None else medio
    flojo = 70 if flojo is None else flojo
    compas = CLOCKS_PER_QUARTER * beats_per_bar
    out = []
    for n in notas:
        if n.time % compas == 0:
            v = fuerte
        elif n.time % CLOCKS_PER_QUARTER == 0:
            v = medio
        else:
            v = flojo
        out.append(Note(n.pitch, v, n.gate, n.time))
    return out


def humanizar(notas, velocity=8, tiempo=0, semilla=None, total_clocks=None):
    """Pequenas variaciones de velocity y, si se pide, de colocacion.

    `tiempo` en relojes: 5 son unos 6 ms a 104 BPM, suficiente para quitar la
    rigidez sin que se note como error. No se permite que una nota se vaya antes
    del cero ni mas alla del final.
    """
    rng = _random.Random(semilla)
    out = []
    for n in notas:
        v = max(1, min(127, n.velocity + rng.randint(-velocity, velocity)))
        t = n.time
        if tiempo:
            t = max(0, n.time + rng.randint(-tiempo, tiempo))
            if total_clocks is not None:
                t = min(t, total_clocks - 1)
        out.append(Note(n.pitch, v, n.gate, t))
    return sorted(out, key=lambda x: x.time)


def swing(notas, cantidad=58, division=None):
    """Retrasa las subdivisiones debiles. 50 = sin swing, 66 = tresillo.

    A 58 queda el empuje sutil que se usa en groove sin llegar al swing de jazz.
    Solo mueve las notas que caen en subdivision impar; las que estan en la
    rejilla fuerte no se tocan, que es justo lo que hace que se perciba como
    balanceo y no como desajuste.
    """
    if not 50 <= cantidad <= 75:
        raise ValueError("cantidad de swing fuera de 50-75: %r" % (cantidad,))
    paso = division or (CLOCKS_PER_QUARTER // 4)      # semicorchea
    desfase = int(round(paso * 2 * (cantidad - 50) / 100.0))
    out = []
    for n in notas:
        impar = (n.time // paso) % 2 == 1
        out.append(Note(n.pitch, n.velocity, n.gate,
                        n.time + desfase if impar else n.time))
    return sorted(out, key=lambda x: x.time)
