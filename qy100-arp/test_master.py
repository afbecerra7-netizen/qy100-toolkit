#!/usr/bin/env python3
"""Verifica el modo maestro de reloj sobre puertos virtuales CoreMIDI reales.

Simula la topologia de Felipe: controlador -> caja -> QY100 IN.
Nosotros hacemos de "QY100" escuchando lo que la caja transmite.

    .venv/bin/python test_master.py
"""

import subprocess
import sys
import threading
import time

import mido

BPM = 120.0
SECONDS = 3.0

FAILS = []


def check(label, got, want_fn, want_desc):
    if want_fn(got):
        print("  ok   %s (%s)" % (label, got))
    else:
        print("  FALLA %s: obtenido %r, esperado %s" % (label, got, want_desc))
        FAILS.append(label)


# Puerto que hace de "QY100 MIDI IN": escucha lo que emite la caja.
listener = mido.open_input("FAKE QY100 IN", virtual=True)
# Puerto que hace de "controlador": le manda notas a la caja.
controller = mido.open_output("FAKE CONTROLLER", virtual=True)
time.sleep(0.3)

proc = subprocess.Popen(
    [sys.executable, "run.py", "--master", "--bpm", str(BPM),
     "--in", "FAKE CONTROLLER", "--out", "FAKE QY100 IN"],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
time.sleep(1.5)          # que abra los puertos y arranque el reloj

received = []
stop = threading.Event()


def pump():
    while not stop.is_set():
        for m in listener.iter_pending():
            received.append((time.monotonic(), m))
        time.sleep(0.0005)


th = threading.Thread(target=pump, daemon=True)
th.start()

# Vaciar el backlog: mientras arrancabamos, la caja ya venia mandando reloj al
# buffer del puerto. Si no se descarta, todo eso llega de golpe y arruina la
# medicion de tempo y de jitter.
time.sleep(0.6)
# El Start se transmite al arrancar, o sea antes de este vaciado: hay que
# anotarlo aparte o se pierde junto con el backlog.
saw_start = sum(1 for _, m in received if m.type == "start")
received.clear()

# El "controlador" toca un acorde de Do menor.
for n in (48, 51, 55):
    controller.send(mido.Message("note_on", channel=0, note=n, velocity=100))
    time.sleep(0.01)
# Y mueve la rueda de modulacion, que debe pasar de largo hacia el QY100.
controller.send(mido.Message("control_change", channel=0, control=1, value=64))

time.sleep(SECONDS)
controller.send(mido.Message("note_off", channel=0, note=48))
controller.send(mido.Message("note_off", channel=0, note=51))
controller.send(mido.Message("note_off", channel=0, note=55))
time.sleep(0.3)

# Terminar primero y seguir escuchando: el Stop y los note_off de cierre salen
# durante el apagado, asi que cortar el listener antes se los come.
proc.terminate()
try:
    proc.wait(timeout=5)
except subprocess.TimeoutExpired:
    proc.kill()
time.sleep(0.5)
stop.set()
th.join(timeout=1)
listener.close()
controller.close()

kinds = {}
for _, m in received:
    kinds[m.type] = kinds.get(m.type, 0) + 1
print("recibido:", kinds)
print()

clocks = [t for t, m in received if m.type == "clock"]
notes = [m for _, m in received if m.type == "note_on"]

print("reloj")
check("transmite Start", saw_start, lambda v: v == 1, "1")
check("transmite Clock", len(clocks), lambda v: v > 100, ">100")

# 24 ticks por negra a 120 BPM = 48 ticks/segundo
if len(clocks) > 50:
    span = clocks[-1] - clocks[0]
    rate = (len(clocks) - 1) / span
    bpm = rate / 24.0 * 60.0
    check("tempo medido", round(bpm, 1), lambda v: abs(v - BPM) < 2.0,
          "%.1f +-2 BPM" % BPM)
    gaps = [b - a for a, b in zip(clocks, clocks[1:])]
    avg = sum(gaps) / len(gaps)
    jitter = max(abs(g - avg) for g in gaps) * 1000
    check("jitter maximo ms", round(jitter, 2), lambda v: v < 8.0, "<8 ms")

print("\nnotas")
check("produjo notas", len(notes), lambda v: v > 20, ">20")

# El arpegiador sale por canal 1 (indice 0). Esto es lo que de verdad prueba que
# el acorde del controlador entro y se arpegio: sin esta comprobacion la suite
# pasaba solo con la bateria euclidiana, que no necesita entrada ninguna.
arp_notes = [m.note for m in notes if m.channel == 0]
check("el arpegiador respondio al controlador", len(arp_notes),
      lambda v: v > 10, ">10 notas en el canal 1")
check("arpegio las notas del acorde tocado",
      sorted({n % 12 for n in arp_notes}), lambda v: v == [0, 3, 7],
      "clases de altura de Do menor: [0, 3, 7]")
check("bateria euclidiana en el canal 10",
      len([m for m in notes if m.channel == 9]), lambda v: v > 5, ">5")
check("modulacion pasa de largo", kinds.get("control_change", 0),
      lambda v: v >= 1, ">=1")

# Contar mensajes no sirve: al vaciar el backlog se descartan note_on cuyo
# note_off llega despues, y eso da un desbalance que no significa nada. Lo que
# importa de verdad es que al final no quede ninguna nota sonando, asi que se
# sigue el estado real nota por nota.
sounding = set()
for _, m in received:
    if m.type == "note_on" and m.velocity > 0:
        sounding.add((m.channel, m.note))
    elif m.type in ("note_off", "note_on"):
        sounding.discard((m.channel, m.note))
check("sin notas colgadas al cerrar", sorted(sounding), lambda v: v == [], "ninguna")
check("transmite Stop al salir", kinds.get("stop", 0), lambda v: v == 1, "1")

print()
if FAILS:
    print("FALLARON %d: %s" % (len(FAILS), ", ".join(FAILS)))
    sys.exit(1)
print("Modo maestro verificado sobre puertos MIDI reales.")
