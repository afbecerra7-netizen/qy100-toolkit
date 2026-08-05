"""Escribe un tema del EP como archivo MIDI estandar, para arrastrar a Ableton.

    .venv/bin/python exportar_midi.py ep-quiebre --cuantizar 16

**Es la ruta corta hacia el DAW.** Pasar por el QY100 tiene sentido cuando se
quiere su secuenciador o sus voces, o para tocarlo en vivo; pero si lo unico
que se busca es meter las notas en Ableton, un archivo es directo, exacto y no
exige tocar `MIDI Sync`, `MIDI control` ni `Rec Count` — ni arriesga la perdida
silenciosa de bloques que sufre una captura larga.

Los motores trabajan a **480 relojes por negra**, que es justo el
`ticks_per_beat` que se le pone al archivo: la conversion es uno a uno, sin
redondeo.

`--cuantizar N` lleva cada nota a la subdivision 1/N mas cercana. **1/16 es lo
que corresponde en este material**, porque toda la colocacion —la del euclidiano
y la de las semicorcheas raras del bajo— ya cae en semicorcheas exactas; lo unico
que se quita es la microtemporizacion de `humanizar()`. Cuantizar mas grueso
arrastraria el bajo de la semicorchea 3 al tiempo fuerte y destruiria el tema.
"""
import argparse
import importlib.machinery
import os
import sys

import mido

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qy100syx import patternfmt as F                                 # noqa: E402

Q = F.CLOCKS_PER_QUARTER


def cargar(modulo):
    nombre = modulo.replace("-", "_")
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), modulo + ".py")
    return importlib.machinery.SourceFileLoader(nombre, ruta).load_module()


def cuantizar(notas, division):
    """Lleva cada nota a la subdivision 1/division mas cercana."""
    paso = int(Q * 4 / division)
    return [F.Note(n.pitch, n.velocity, n.gate,
                   int(round(n.time / float(paso))) * paso) for n in notas]


def escribir(tema, pistas, bpm, destino):
    mid = mido.MidiFile(ticks_per_beat=Q)

    cabecera = mido.MidiTrack()
    cabecera.append(mido.MetaMessage("track_name", name=tema, time=0))
    cabecera.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
    mid.tracks.append(cabecera)

    for canal, nombre, notas in pistas:
        pista = mido.MidiTrack()
        pista.append(mido.MetaMessage("track_name", name=nombre, time=0))
        # Un evento por extremo de nota, ordenados; MIDI usa tiempos relativos.
        eventos = []
        for n in notas:
            eventos.append((n.time, 1, n.pitch, n.velocity))
            eventos.append((n.time + max(n.gate, 1), 0, n.pitch, 0))
        eventos.sort(key=lambda e: (e[0], e[1]))
        anterior = 0
        for t, on, pitch, vel in eventos:
            pista.append(mido.Message(
                "note_on" if on else "note_off",
                channel=(canal - 1) % 16, note=int(pitch), velocity=int(vel),
                time=int(t - anterior)))
            anterior = t
        mid.tracks.append(pista)

    mid.save(destino)
    return mid


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("modulo", help="ep-quiebre, ep-conjuro, ep-levante, ep-bajon")
    ap.add_argument("--cuantizar", type=int, default=0,
                    help="subdivision, p.ej. 16 para semicorcheas. 0 = sin tocar")
    ap.add_argument("--salida", default="midi")
    args = ap.parse_args()

    T = cargar(args.modulo)
    os.makedirs(args.salida, exist_ok=True)

    pistas, movidas, total = [], 0, 0
    for canal, nombre, notas in T.PISTAS:
        notas = sorted(notas, key=lambda x: x.time)
        if args.cuantizar:
            q = cuantizar(notas, args.cuantizar)
            movidas += sum(1 for a, b in zip(notas, q) if a.time != b.time)
            notas = sorted(q, key=lambda x: x.time)
        total += len(notas)
        pistas.append((canal, nombre, notas))

    sufijo = "-q%d" % args.cuantizar if args.cuantizar else ""
    destino = os.path.join(args.salida, "%s%s.mid" % (T.NOMBRE, sufijo))
    escribir(T.NOMBRE, pistas, T.BPM, destino)

    print("%s — %.0f bpm, %d compases" % (T.NOMBRE, T.BPM, T.COMPASES))
    for canal, nombre, notas in pistas:
        print("   canal %-2d %-9s %5d notas" % (canal, nombre, len(notas)))
    if args.cuantizar:
        print("cuantizado a 1/%d: %d de %d notas movidas"
              % (args.cuantizar, movidas, total))
    print("escrito %s" % destino)
