#!/usr/bin/env python3
"""Prueba del control en vivo por CC.

    .venv/bin/python test_control.py
"""

import sys

import mido

from qy100arp.cli import PASSTHROUGH_TYPES, handle_message, load_config
from qy100arp.control import ControlMap
from qy100arp.engine import Engine

FAILS = []


def check(label, got, want):
    if got == want:
        print("  ok   %s = %r" % (label, got))
    else:
        print("  FALLA %s: obtenido %r, esperado %r" % (label, got, want))
        FAILS.append(label)


cfg = load_config("config.json")
engine = Engine(cfg, None)
controls = ControlMap(cfg.get("midi_control"), engine)


def cc(control, value, channel=0):
    return mido.Message("control_change", channel=channel,
                        control=control, value=value)


print("mapeo cargado")
check("mapeo activo", controls.enabled, True)
check("cantidad de CC mapeados", len(controls.map), 10)

print("\ncontinuos")
controls.apply(cc(76, 127))
check("gate al maximo", round(engine.arp.gate, 2), 1.5)
controls.apply(cc(76, 0))
check("gate al minimo", round(engine.arp.gate, 2), 0.05)
controls.apply(cc(78, 64))
check("densidad a media", round(engine.melody.density, 2), 0.5)

print("\nenteros")
controls.apply(cc(75, 127))
check("octavas al maximo", engine.arp.octaves, 4)
controls.apply(cc(75, 0))
check("octavas al minimo", engine.arp.octaves, 1)

print("\nenum")
controls.apply(cc(74, 0))
check("division mas lenta", engine.arp.division, "1/4")
check("  ticks recalculados", engine.arp.ticks_per_step, 24)
controls.apply(cc(74, 127))
check("division mas rapida", engine.arp.division, "1/32T")
check("  ticks recalculados", engine.arp.ticks_per_step, 2)
controls.apply(cc(77, 0))
check("primer patron", engine.arp.pattern, "up")
controls.apply(cc(77, 127))
check("ultimo patron", engine.arp.pattern, "chord")

print("\ntoggles")
controls.apply(cc(82, 127))
check("latch encendido", engine.arp.latch, True)
controls.apply(cc(82, 0))
check("latch apagado", engine.arp.latch, False)
controls.apply(cc(83, 0))
check("melodia apagada", engine.melody.enabled, False)

print("\nlineas euclidianas")
bombo = [l for l in engine.lanes if l.name == "bombo"][0]
antes = list(bombo.pattern)
controls.apply(cc(80, 127))
check("pulsos del bombo al maximo", bombo.pulses, 16)
check("  patron rehecho", bombo.pattern != antes and all(bombo.pattern), True)
controls.apply(cc(80, 0))
check("pulsos del bombo a cero", bombo.pulses, 0)
check("  patron vacio", any(bombo.pattern), False)

caja = [l for l in engine.lanes if l.name == "caja"][0]
controls.apply(cc(81, 64))
check("rotacion de la caja", caja.rotation, 8)
controls.apply(cc(79, 0))
check("probabilidad del hihat", [l for l in engine.lanes
                                 if l.name == "hihat"][0].probability, 0.0)

print("\nruteo de CC")


class Spy:
    def __init__(self):
        self.sent = []

    def send(self, m):
        self.sent.append(m)


spy = Spy()
out_channels = engine.output_channels()

# un CC mapeado se consume: no debe llegar al QY100
handle_message(engine, cc(76, 100), out_channels, None, True, spy, controls)
check("CC mapeado no se reenvia", len(spy.sent), 0)

# un CC no mapeado pasa de largo
handle_message(engine, cc(1, 100), out_channels, None, True, spy, controls)
check("CC no mapeado pasa de largo", len(spy.sent), 1)
check("  llega intacto", (spy.sent[0].control, spy.sent[0].value), (1, 100))

# pitch bend tambien pasa
handle_message(engine, mido.Message("pitchwheel", channel=0, pitch=2000),
               out_channels, None, True, spy, controls)
check("pitch bend pasa de largo", spy.sent[-1].type, "pitchwheel")

# y las notas nunca se reenvian crudas: las reemplaza el arpegio
handle_message(engine, mido.Message("note_on", channel=0, note=60, velocity=90),
               out_channels, None, True, spy, controls)
check("nota cruda no se reenvia", len(spy.sent), 2)
check("  pero entra al arpegiador", 60 in engine.arp.active_notes, True)

print("\nvalidacion de config")
try:
    ControlMap({"enabled": True, "map": {"20": "arp.noexiste"}}, engine)
    check("rechaza parametro invalido", "no fallo", "ValueError")
except ValueError as e:
    check("rechaza parametro invalido", "ValueError", "ValueError")
try:
    ControlMap({"enabled": True, "map": {"20": "lane.fantasma.pulses"}}, engine)
    check("rechaza linea inexistente", "no fallo", "ValueError")
except ValueError:
    check("rechaza linea inexistente", "ValueError", "ValueError")

print()
if FAILS:
    print("FALLARON %d: %s" % (len(FAILS), ", ".join(FAILS)))
    sys.exit(1)
print("Control por CC verificado.")
