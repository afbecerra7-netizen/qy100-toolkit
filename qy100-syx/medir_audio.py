#!/usr/bin/env python3
"""Mide si la subdivision de una grabacion es binaria o ternaria.

    .venv/bin/python medir_audio.py fichero.mp3 [--desde 10] [--dura 60]
    .venv/bin/python medir_audio.py --autotest

Necesita `numpy` (en requirements.txt) y `ffmpeg` en el PATH para decodificar.

Existe porque buena parte de la musica que este proyecto genera no esta
transcrita: una grabacion es una fuente primaria tan buena como una partitura.

**Ha fallado dos veces, y las dos estan cubiertas por `--autotest`:**

1. La primera version proponia rejillas y las puntuaba con un 15 % de
   tolerancia: un ataque al azar "cae en rejilla" el 30 % de las veces, y
   reporto 32 % contra 30 % como si fuera un resultado. Era su propio suelo de
   ruido con formato de medicion.
2. La segunda enseñaba la distribucion (bien) pero: la envolvente adelantaba
   los ataques media ventana (~23 ms), la fase se anclaba al primer frame en
   vez de al pulso, y cada objetivo se leia en UNA casilla de 24. Con el pulso
   estimado a la octava equivocada, un click binario perfecto puntuaba
   ternario — **clasificaba al reves sus propios casos ideales.**

Lo que hace ahora: compensa la ventana, rota el perfil para que el pulso este
en la casilla 0, lee cada objetivo en una ventana de ±1.5 casillas, y puntua el
periodo estimado junto con su doble y su mitad, quedandose con el que mas
separa. `--autotest` sintetiza un click binario y uno ternario y exige que los
clasifique bien; si eso falla, ninguna medicion de esta herramienta vale.

**Lo que NO hace**: no dice que instrumento golpea; sobre mezcla densa se
ensucia; y no sustituye el oido — da la rejilla para que alguien decida.
"""

import argparse
import subprocess
import sys

import numpy as np

SR = 22050
HOP = 256
N = 1024                     # ventana del analisis espectral
FPS = SR / float(HOP)


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
    """(flujo espectral, tiempos en segundos de cada valor).

    El tiempo de cada valor es el CENTRO de su ventana, no su inicio: el flujo
    sube cuando la ventana empieza a contener el ataque, o sea hasta media
    ventana ANTES del ataque real. Sin compensarlo, todo el perfil queda
    adelantado ~23 ms y las casillas se corren.
    """
    ventana = np.hanning(N)
    marcos = 1 + (len(x) - N) // HOP
    esp = np.empty((marcos, N // 2 + 1), dtype=np.float32)
    for i in range(marcos):
        esp[i] = np.abs(np.fft.rfft(x[i * HOP:i * HOP + N] * ventana))
    dif = np.diff(esp, axis=0)
    dif[dif < 0] = 0
    flujo = dif.sum(axis=1)
    flujo /= (flujo.max() or 1.0)
    tiempos = (np.arange(len(flujo)) * HOP + N / 2.0) / SR
    return flujo, tiempos


def pulso(flujo):
    """Periodo del pulso por autocorrelacion, en segundos."""
    f = flujo - flujo.mean()
    f /= (f.std() or 1.0)
    ac = np.correlate(f, f, "full")[len(f) - 1:]
    ac /= (ac[0] or 1.0)
    lo, hi = int(FPS * 0.25), int(FPS * 1.2)          # 50 a 240 bpm
    return (lo + int(np.argmax(ac[lo:hi]))) / FPS


def perfil(flujo, tiempos, periodo, casillas=24):
    """Energia por posicion dentro del pulso, ROTADA para que el maximo — el
    pulso — quede en la casilla 0. Sin la rotacion, la fase depende de donde
    empezo el analisis, y las etiquetas "tercio"/"cuarto" no señalan nada."""
    fase = (tiempos % periodo) / periodo
    h, _ = np.histogram(fase, bins=casillas, weights=np.maximum(flujo, 0))
    h = np.roll(h, -int(np.argmax(h)))
    return h / (h.max() or 1.0)


def evaluar(h):
    """(ternaria, binaria): energia media en los objetivos de cada rejilla,
    leyendo cada objetivo en una ventana de ±1.5 casillas — un objetivo entre
    dos casillas reparte su energia y una lectura de casilla unica lo pierde."""
    n = len(h)

    def lee(objetivo):
        idx = [j for j in range(n) if min(abs(j / float(n) - objetivo),
                                          1 - abs(j / float(n) - objetivo)) <= 1.5 / n]
        return max(h[j] for j in idx)

    ter = float(np.mean([lee(1 / 3.0), lee(2 / 3.0)]))
    bin_ = float(np.mean([lee(0.25), lee(0.5), lee(0.75)]))
    return ter, bin_


def medir(x, forzar_bpm=None):
    """(periodo elegido, perfil, ternaria, binaria, tabla de candidatos)."""
    flujo, tiempos = envolvente(x)
    base = 60.0 / forzar_bpm if forzar_bpm else pulso(flujo)
    candidatos = [base] if forzar_bpm else [base / 2, base, base * 2]
    tabla = []
    for p in candidatos:
        if not 60.0 / 300 <= p <= 60.0 / 40:
            continue
        h = perfil(flujo, tiempos, p)
        ter, bin_ = evaluar(h)
        tabla.append((p, h, ter, bin_))
    if not tabla:
        raise SystemExit("ningun candidato de pulso en 40-300 bpm")
    # gana el periodo que mas separa las dos hipotesis: un pulso a la octava
    # equivocada las confunde, y ese era el segundo fallo historico.
    p, h, ter, bin_ = max(tabla, key=lambda fila: abs(fila[2] - fila[3]))
    return p, h, ter, bin_, tabla


def _click(sr, dur, periodos):
    """Tren de clicks sintetico: rafagas de ruido de 5 ms en cada instante."""
    x = np.zeros(int(sr * dur), dtype=np.float32)
    rng = np.random.RandomState(7)
    for t in periodos:
        i = int(t * sr)
        if i + 110 < len(x):
            x[i:i + 110] += rng.randn(110).astype(np.float32) * np.hanning(110)
    return x / (np.abs(x).max() or 1.0)


def autotest():
    """Un click binario y uno ternario, sintetizados: si no los clasifica bien,
    ninguna medicion de esta herramienta vale. La version 2 fallaba esto."""
    P, DUR = 0.5, 20.0
    binario = [k * P / 4 for k in range(int(DUR / (P / 4)))]
    ternario = [k * P / 3 for k in range(int(DUR / (P / 3)))]
    fallos = 0
    for nombre, tiempos, esperado in (("binario", binario, "BINARIA"),
                                      ("ternario", ternario, "TERNARIA")):
        x = _click(SR, DUR, tiempos)
        _p, _h, ter, bin_, _t = medir(x)
        got = "TERNARIA" if ter > bin_ else "BINARIA"
        ok = got == esperado and abs(ter - bin_) > 0.2
        print("  click %-9s -> ter %.2f bin %.2f -> %s  %s"
              % (nombre, ter, bin_, got, "ok" if ok else "**FALLA**"))
        fallos += 0 if ok else 1
    print("autotest: %s" % ("pasa" if not fallos else "FALLA"))
    return fallos


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("archivo", nargs="?")
    ap.add_argument("--desde", type=float, default=0.0)
    ap.add_argument("--dura", type=float, default=60.0)
    ap.add_argument("--bpm", type=float, help="forzar el pulso")
    ap.add_argument("--autotest", action="store_true")
    args = ap.parse_args()

    if args.autotest:
        return autotest()
    if not args.archivo:
        raise SystemExit("falta el fichero (o usa --autotest)")

    x = leer(args.archivo, args.desde, args.dura)
    print("%.1f s a %d Hz, desde el segundo %.0f" % (len(x) / SR, SR, args.desde))
    p, h, ter, bin_, tabla = medir(x, args.bpm)
    for pc, _hc, tc, bc in tabla:
        print("  candidato %.3f s (%5.1f bpm): ter %.2f  bin %.2f%s"
              % (pc, 60.0 / pc, tc, bc, "   <- elegido" if pc == p else ""))
    print("\nperfil en el pulso elegido (rotado: casilla 0 = pulso):")
    n = len(h)
    for i, v in enumerate(h):
        f = i / float(n)
        et = ("  <- pulso" if i == 0 else
              "  <- TERCIO" if min(abs(f - 1/3.), abs(f - 2/3.)) < 0.5 / n else
              "  <- cuarto" if min(abs(f - .25), abs(f - .5), abs(f - .75)) < 0.5 / n
              else "")
        print("   %4.2f  %-28s%s" % (f, "#" * int(v * 28), et))

    print("\nmedia en tercios: %.2f   en cuartos: %.2f" % (ter, bin_))
    if max(ter, bin_) < 0.25:
        print("  **Los dos debiles**: pulso probablemente mal, o deteccion sucia. "
              "No es medicion.")
    elif abs(ter - bin_) < 0.12:
        print("  **No decide** (umbral heuristico 0.12, calibrado con --autotest). "
              "Hace falta oido.")
    else:
        print("  -> subdivision **%s** (%.2f contra %.2f). Sobre esta grabacion "
              "y este tramo." % ("TERNARIA" if ter > bin_ else "BINARIA",
                                 max(ter, bin_), min(ter, bin_)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
