#!/usr/bin/env python3
"""Mide la rejilla ritmica de una grabacion: ataques, tempo y subdivision.

    .venv/bin/python medir_audio.py fichero.mp3 [--desde 10] [--dura 60]

Existe porque **buena parte de la musica que este proyecto quiere generar no
esta transcrita**. El mapale, sin ir mas lejos, no aparece ni una vez en las dos
cartillas del Ministerio: todo su `[M]` descansaba en una transcripcion para
piano de procedencia desconocida. Una grabacion es una fuente primaria tan buena
como una partitura, y hasta hoy no habia manera de preguntarle nada.

La pregunta que contesta es la unica que hace falta para el compas:
**¿la subdivision es binaria o ternaria?** Se responde midiendo donde caen los
ataques respecto al pulso y viendo que rejilla los explica mejor — el mismo
metodo que `analizar_loop.py` usa sobre MIDI, pero sobre audio.

**Lo que NO hace**, y conviene tenerlo claro antes de citarlo:

- No dice **que** instrumento golpea, solo **cuando**. Para separar cuero de
  madera hace falta un oido.
- Sobre percusion densa, con reverb o mezcla apretada, la deteccion se ensucia.
  Un loop limpio da mucho mejor que una grabacion de banda.
- Y **no sustituye el oido**: da la rejilla para que alguien decida, que es
  justo el reparto que este proyecto ya usa con las mediciones de MIDI.
"""

import argparse
import subprocess
import sys

import numpy as np

SR = 22050          # basta para percusion y va cuatro veces mas rapido
HOP = 256


def leer(ruta, desde=0.0, dura=None):
    """Decodifica a mono con ffmpeg. Devuelve float32 en [-1, 1]."""
    cmd = ["ffmpeg", "-v", "error"]
    if desde:
        cmd += ["-ss", str(desde)]
    cmd += ["-i", ruta]
    if dura:
        cmd += ["-t", str(dura)]
    cmd += ["-ac", "1", "-ar", str(SR), "-f", "s16le", "-"]
    crudo = subprocess.run(cmd, capture_output=True).stdout
    if not crudo:
        raise SystemExit("ffmpeg no devolvio audio de %r" % ruta)
    return np.frombuffer(crudo, dtype="<i2").astype(np.float32) / 32768.0


def envolvente(x):
    """Flujo espectral: sube cuando entra energia nueva. Es lo que marca un golpe."""
    n = 1024
    ventana = np.hanning(n)
    marcos = 1 + (len(x) - n) // HOP
    esp = np.empty((marcos, n // 2 + 1), dtype=np.float32)
    for i in range(marcos):
        esp[i] = np.abs(np.fft.rfft(x[i * HOP:i * HOP + n] * ventana))
    dif = np.diff(esp, axis=0)
    dif[dif < 0] = 0                      # solo lo que crece: un golpe, no un final
    flujo = dif.sum(axis=1)
    return flujo / (flujo.max() or 1.0)


def ataques(flujo, umbral=0.12, min_sep=0.045):
    """Picos de la envolvente, en segundos."""
    sep = max(1, int(min_sep * SR / HOP))
    picos, ultimo = [], -sep
    # media movil como suelo adaptativo: una grabacion no tiene nivel constante
    k = int(0.5 * SR / HOP)
    suelo = np.convolve(flujo, np.ones(k) / k, mode="same")
    for i in range(1, len(flujo) - 1):
        if (flujo[i] > flujo[i - 1] and flujo[i] >= flujo[i + 1]
                and flujo[i] > umbral and flujo[i] > suelo[i] * 1.5
                and i - ultimo >= sep):
            picos.append(i * HOP / float(SR))
            ultimo = i
    return np.array(picos)


def pulso(flujo, fps):
    """Periodo del pulso por autocorrelacion de la envolvente, en segundos.

    **No se proponen rejillas y se puntuan.** Ese fue el primer intento y daba
    30 % para la binaria y 30 % para la ternaria — que es exactamente lo que
    devuelve el azar con una tolerancia del 15 % a cada lado. El programa
    reportaba su propio suelo de ruido con formato de resultado.
    """
    f = flujo - flujo.mean()
    f /= (f.std() or 1.0)
    ac = np.correlate(f, f, "full")[len(f) - 1:]
    ac /= (ac[0] or 1.0)
    lo, hi = int(fps * 0.25), int(fps * 1.2)          # 50 a 240 bpm
    return (lo + int(np.argmax(ac[lo:hi]))) / fps


def perfil(flujo, fps, periodo, casillas=24):
    """Energia acumulada por posicion dentro del pulso, normalizada a 1.

    Esto es lo que hay que mirar: **donde se acumulan los golpes**, no cuantos
    caen dentro de una rejilla que uno propone. Si la subdivision es ternaria
    los picos salen en 1/3 y 2/3 y los cuartos quedan vacios, y se ve.
    """
    fase = (np.arange(len(flujo)) / fps % periodo) / periodo
    h, _ = np.histogram(fase, bins=casillas, weights=np.maximum(flujo, 0))
    return h / (h.max() or 1.0)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("archivo")
    ap.add_argument("--desde", type=float, default=0.0, help="segundos a saltar")
    ap.add_argument("--dura", type=float, default=60.0, help="segundos a analizar")
    ap.add_argument("--bpm", type=float, help="forzar el pulso en vez de estimarlo")
    args = ap.parse_args()

    x = leer(args.archivo, args.desde, args.dura)
    fps = SR / float(HOP)
    flujo = envolvente(x)
    print("%.1f s a %d Hz, desde el segundo %.0f" % (len(x) / SR, SR, args.desde))

    per = 60.0 / args.bpm if args.bpm else pulso(flujo, fps)
    print("pulso: %.4f s = %.1f bpm%s\n"
          % (per, 60.0 / per, " (forzado)" if args.bpm else " (autocorrelacion)"))

    h = perfil(flujo, fps, per)
    n = len(h)
    print("energia por posicion dentro del pulso:")
    for i, v in enumerate(h):
        f = i / float(n)
        et = ""
        if abs(f - 0) < 1e-9:                     et = "  <- pulso"
        elif min(abs(f - 1/3.), abs(f - 2/3.)) < 0.5 / n: et = "  <- TERCIO"
        elif min(abs(f - .25), abs(f - .5), abs(f - .75)) < 0.5 / n: et = "  <- cuarto"
        print("   %4.2f  %-28s%s" % (f, "#" * int(v * 28), et))

    def media(objetivos):
        return float(np.mean([max(h[j] for j in range(n)
                                  if abs(j / float(n) - o) < 0.5 / n) for o in objetivos]))
    ter = media([1/3., 2/3.])
    bin_ = media([.25, .5, .75])
    print("\nmedia en los tercios : %.2f" % ter)
    print("media en los cuartos : %.2f" % bin_)
    if max(ter, bin_) < 0.25:
        print("\n  **Los dos son debiles.** El pulso elegido probablemente no es el")
        print("  bueno, o la deteccion esta sucia. No lo cuentes como medicion.")
    elif abs(ter - bin_) < 0.12:
        print("\n  **No decide.** Los dos sitios tienen energia parecida — puede ser")
        print("  subdivision mixta. Hace falta oido.")
    else:
        cual = "TERNARIA" if ter > bin_ else "BINARIA"
        print("\n  -> subdivision **%s**: %.2f contra %.2f" % (cual, max(ter, bin_),
                                                              min(ter, bin_)))
        print("  Medido sobre esta grabacion y este tramo, no sobre el genero.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
