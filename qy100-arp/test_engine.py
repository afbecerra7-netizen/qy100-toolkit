#!/usr/bin/env python3
"""Pruebas del motor. No necesitan hardware MIDI.

    .venv/bin/python test_engine.py
"""

import sys

from qy100arp.arp import Arpeggiator
from qy100arp.engine import Engine
from qy100arp.euclid import euclid, to_string
from qy100arp.midiio import RenderOutput
from qy100arp.scales import note_name, parse_note, quantize, scale_pitches

FAILS = []


def check(label, got, want):
    if got == want:
        print("  ok   %s" % label)
    else:
        print("  FALLA %s\n        obtenido: %r\n        esperado: %r" % (label, got, want))
        FAILS.append(label)


def collect(cfg, bars=1, held=(), bpm_ticks=96):
    """Corre el motor y devuelve los note_on como (tick, canal, nota, vel)."""
    engine = Engine(cfg, None)
    out = RenderOutput(engine)
    engine.out = out
    for n in held:
        engine.note_on(parse_note(n), 100)
    engine.start(0)
    for _ in range(bars * bpm_ticks):
        engine.on_tick()
    engine.all_notes_off()
    return [(t, m.channel, m.note, m.velocity)
            for t, m in out.events if m.type == "note_on"]


def only_arp(**over):
    arp = {"enabled": True, "pattern": "up", "division": "1/16",
           "octaves": 1, "gate": 0.5, "channel": 1}
    arp.update(over)
    return {"arpeggiator": arp, "generative": {}}


print("euclid")
check("E(3,8)", to_string(euclid(3, 8)), "x..x..x.")
check("E(4,16)", to_string(euclid(4, 16)), "x...x...x...x...")
check("E(2,16) rot4", to_string(euclid(2, 16, 4)), "....x.......x...")
check("E(0,8)", to_string(euclid(0, 8)), "........")
check("E(8,8)", to_string(euclid(8, 8)), "xxxxxxxx")
# maximalmente uniforme = los huecos entre golpes solo pueden ser n o n+1
_on = [k for k, v in enumerate(euclid(5, 8)) if v]
check("E(5,8) huecos", sorted(j - i for i, j in zip(_on, _on[1:])), [1, 2, 2, 2])
check("E(5,8) golpes", len(_on), 5)

print("\nescalas")
check("C menor", scale_pitches(0, "minor"), [0, 2, 3, 5, 7, 8, 10])
check("parse C4=60", parse_note("C4"), 60)
check("parse Bb2", parse_note("Bb2"), 46)
check("parse F#3", parse_note("F#3"), 54)
check("nombre 60", note_name(60), "C4")
check("cuantiza: nota ya en escala no se mueve",
      note_name(quantize(parse_note("D4"), scale_pitches(0, "minor"))), "D4")
# en pentatonica F# no esta empatado: G esta a 1 semitono y E a 2
check("cuantiza F#->G (sin empate)",
      note_name(quantize(parse_note("F#4"), scale_pitches(0, "pentatonic"))), "G4")
# F# en menor esta a la misma distancia de F y de G: el empate baja, por convenio
check("empate resuelve hacia abajo",
      note_name(quantize(parse_note("F#4"), scale_pitches(0, "minor"))), "F4")
# invariante: el resultado siempre cae dentro de la escala
_cm = scale_pitches(0, "minor")
check("todo lo cuantizado cae en la escala",
      all(quantize(n, _cm) % 12 in _cm for n in range(24, 108)), True)

print("\narpegiador: orden de notas")
notes = ("C3", "E3", "G3")
seq = [note_name(n) for _, _, n, _ in collect(only_arp(pattern="up"), held=notes)]
check("up 1 oct", seq[:6], ["C3", "E3", "G3", "C3", "E3", "G3"])

seq = [note_name(n) for _, _, n, _ in collect(only_arp(pattern="down"), held=notes)]
check("down 1 oct", seq[:3], ["G3", "E3", "C3"])

seq = [note_name(n) for _, _, n, _ in collect(only_arp(pattern="updown"), held=notes)]
check("updown 1 oct", seq[:4], ["C3", "E3", "G3", "E3"])

seq = [note_name(n) for _, _, n, _ in collect(
    only_arp(pattern="up", octaves=2), held=notes)]
check("up 2 oct recorre todo", seq[:6], ["C3", "E3", "G3", "C4", "E4", "G4"])

seq = [note_name(n) for _, _, n, _ in collect(
    only_arp(pattern="updown", octaves=2), held=notes)]
check("updown 2 oct sube y baja entero", seq[:10],
      ["C3", "E3", "G3", "C4", "E4", "G4", "E4", "C4", "G3", "E3"])

seq = [note_name(n) for _, _, n, _ in collect(
    only_arp(pattern="as_played"), held=("G3", "C3", "E3"))]
check("as_played respeta orden", seq[:3], ["G3", "C3", "E3"])

ev = collect(only_arp(pattern="chord"), held=notes)
check("chord suena simultaneo", len([e for e in ev if e[0] == 0]), 3)

print("\narpegiador: temporizacion")
ticks = [t for t, _, _, _ in collect(only_arp(division="1/16"), held=("C3",))]
check("1/16 cada 6 ticks", ticks[:5], [0, 6, 12, 18, 24])
ticks = [t for t, _, _, _ in collect(only_arp(division="1/8"), held=("C3",))]
check("1/8 cada 12 ticks", ticks[:4], [0, 12, 24, 36])
ticks = [t for t, _, _, _ in collect(only_arp(division="1/8T"), held=("C3",))]
check("1/8T cada 8 ticks", ticks[:4], [0, 8, 16, 24])
check("1 compas de 1/16 = 16 notas",
      len(collect(only_arp(division="1/16"), held=("C3",))), 16)

print("\nvelocity")
engine = Engine(only_arp(pattern="up", octaves=2, velocity_mode="input"), None)
out = RenderOutput(engine)
engine.out = out
engine.note_on(parse_note("C3"), 40)
engine.note_on(parse_note("G3"), 120)
engine.start(0)
for _ in range(24):
    engine.on_tick()
vels = [m.velocity for _, m in out.events if m.type == "note_on"]
check("velocity del origen se propaga a la octava", vels[:4], [40, 120, 40, 120])

print("\nintegridad: nada queda colgado")
for pattern in ("up", "down", "updown", "updown_inc", "downup", "as_played",
                "random", "chord"):
    engine = Engine(only_arp(pattern=pattern, octaves=2), None)
    out = RenderOutput(engine)
    engine.out = out
    for n in ("C3", "E3", "G3", "B3"):
        engine.note_on(parse_note(n), 100)
    engine.start(0)
    for _ in range(384):
        engine.on_tick()
    engine.all_notes_off()
    ons = sum(1 for _, m in out.events if m.type == "note_on")
    offs = sum(1 for _, m in out.events if m.type == "note_off")
    check("%s: on==off (%d)" % (pattern, ons), ons == offs and ons > 0, True)

print("\nlatch")
engine = Engine(only_arp(latch=True), None)
out = RenderOutput(engine)
engine.out = out
engine.note_on(parse_note("C3"), 100)
engine.note_off(parse_note("C3"))
engine.start(0)
for _ in range(24):
    engine.on_tick()
check("latch sigue sonando tras soltar",
      len([m for _, m in out.events if m.type == "note_on"]) > 0, True)

print("\nSPP alinea al compas")
engine = Engine({"arpeggiator": {"enabled": False},
                 "generative": {"euclid_lanes": [
                     {"name": "k", "steps": 16, "pulses": 4, "note": 36,
                      "channel": 10, "division": "1/16"}]}}, None)
out = RenderOutput(engine)
engine.out = out
engine.start(0)
engine.set_position(16)          # 16 semicorcheas = compas 2
for _ in range(96):
    engine.on_tick()
first = [t for t, m in out.events if m.type == "note_on"][0]
check("primer golpe cae en el downbeat del compas 2", first % 96, 0)

print()
if FAILS:
    print("FALLARON %d prueba(s): %s" % (len(FAILS), ", ".join(FAILS)))
    sys.exit(1)
print("Todas las pruebas pasaron.")
