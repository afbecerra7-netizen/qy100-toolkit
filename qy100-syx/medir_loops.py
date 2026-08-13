#!/usr/bin/env python3
"""Mide si un loop MIDI es de subdivision binaria o ternaria, reproducible.

    .venv/bin/python medir_loops.py midi/CHANDE-loop.mid
    .venv/bin/python medir_loops.py            # los loops canonicos del repo

Existe porque dos cifras publicadas —el 89 %/47 % del chande y el 74 %/69 % del
mapale de Tribe— solo vivian en la prosa y en un mensaje de commit: ninguna
herramienta las recalculaba, contra la norma de CLAUDE.md de que toda cifra
citada tiene que salir de algo que se pueda volver a correr. Ahora salen de
aqui.

El metodo es el mismo que decidio el chande: se prueba cada rejilla (binaria de
8 y 4, ternaria de 6 y 3) sobre ciclos de 2 pulsos y de 1, con tolerancia del
10 % del paso, y se reporta que fraccion de los ataques explica cada una. El
30 % es el suelo del azar con esa tolerancia; una diferencia menor de ~8 puntos
no decide.
"""

import argparse
import collections
import sys

import mido

CANONICOS = ["midi/CHANDE-loop.mid", "midi/MAPALE-TRIBE-loop.mid",
             "midi/PORRO-loop.mid", "midi/BULLERENGUE-loop.mid",
             "midi/PUYA4-loop.mid", "midi/CURRULAO-loop.mid"]


def ataques(ruta):
    m = mido.MidiFile(ruta)
    tt, t = [], 0
    for tr in m.tracks:
        t = 0
        for x in tr:
            t += x.time
            if x.type == "note_on" and x.velocity:
                tt.append(t / float(m.ticks_per_beat))
    return sorted(tt)


def rejilla(tt, partes, ciclo):
    paso = float(ciclo) / partes
    dentro = hist = 0
    h = collections.Counter()
    for x in tt:
        fase = (x % ciclo) / paso
        d = min(fase % 1.0, 1.0 - (fase % 1.0))
        if d < 0.10:
            dentro += 1
            h[int(round(fase)) % partes] += 1
    return 100.0 * dentro / len(tt), [h.get(i, 0) for i in range(partes)]


def medir(ruta):
    tt = ataques(ruta)
    if len(tt) < 12:
        print("%s: solo %d ataques, no se mide" % (ruta, len(tt)))
        return None
    filas = []
    for partes, ciclo, etiqueta in ((8, 2, "binaria 8/2p"), (6, 2, "ternaria 6/2p"),
                                    (4, 1, "binaria 4/1p"), (3, 1, "ternaria 3/1p")):
        pct, h = rejilla(tt, partes, ciclo)
        filas.append((etiqueta, pct, h))
    b = max(p for e, p, _h in filas if "binaria" in e)
    t = max(p for e, p, _h in filas if "ternaria" in e)
    print("%s — %d ataques" % (ruta, len(tt)))
    for e, p, h in filas:
        print("   %-14s %3.0f %%   %s" % (e, p, h))
    if abs(b - t) < 8:
        print("   -> no decide (%.0f binaria contra %.0f ternaria)" % (b, t))
    else:
        print("   -> %s (%.0f %% contra %.0f %%)"
              % ("BINARIA" if b > t else "TERNARIA", max(b, t), min(b, t)))
    return b, t


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("archivos", nargs="*", help="por defecto, los canonicos")
    args = ap.parse_args()
    import os
    rutas = args.archivos or [r for r in CANONICOS if os.path.exists(r)]
    for r in rutas:
        medir(r)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
