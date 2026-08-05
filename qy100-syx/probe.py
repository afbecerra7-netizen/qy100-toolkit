#!/usr/bin/env python3
"""Sonda de diagnostico: prueba varias formas de pedirle un volcado al QY100.

El manual documenta el formato de los mensajes pero no la secuencia exacta que
espera el equipo. Esto prueba las hipotesis razonables una por una y reporta
cual produce respuesta, en vez de que las vayamos adivinando de a una.

    .venv/bin/python probe.py --in M4 --out M4
"""

import argparse
import time

import mido

from qy100syx import protocol as P

ap = argparse.ArgumentParser()
ap.add_argument("--in", dest="inp", required=True)
ap.add_argument("--out", dest="outp", required=True)
ap.add_argument("--wait", type=float, default=3.0,
                help="segundos de espera por cada intento")
args = ap.parse_args()


def resolve(name, avail):
    m = [p for p in avail if name.lower() in p.lower()]
    if not m:
        raise SystemExit("puerto %r no encontrado en %s" % (name, avail))
    return m[0]


inport = mido.open_input(resolve(args.inp, mido.get_input_names()))
outport = mido.open_output(resolve(args.outp, mido.get_output_names()))
print("entrada: %s\nsalida : %s\n" % (inport.name, outport.name))


def drain():
    for _ in inport.iter_pending():
        pass


def send(raw):
    outport.send(mido.Message("sysex", data=raw[1:-1]))


def listen(seconds):
    """Devuelve los SysEx recibidos, ignorando el eco de lo que mandamos."""
    got = []
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        for msg in inport.iter_pending():
            if msg.type == "sysex":
                got.append(bytes([0xF0]) + bytes(msg.data) + bytes([0xF7]))
        time.sleep(0.002)
    return got


def report(label, sent, got):
    echo = [g for g in got if g in sent]
    real = [g for g in got if g not in sent]
    if real:
        total = sum(len(g) for g in real)
        print("  >>> RESPUESTA: %d mensajes, %d bytes" % (len(real), total))
        for g in real[:3]:
            print("      %s%s" % (g[:24].hex(" "), " ..." if len(g) > 24 else ""))
        return True
    if echo:
        print("  solo eco (%d)" % len(echo))
    else:
        print("  silencio")
    return False


TESTS = []


def test(name):
    def deco(fn):
        TESTS.append((name, fn))
        return fn
    return deco


@test("1. Peticion directa de setup")
def t1():
    m = P.dump_request(P.Addr.SETUP)
    send(m)
    return [m], listen(args.wait)


@test("2. Bulk mode ON, luego peticion de setup")
def t2():
    a = P.bulk_mode(True)
    send(a)
    time.sleep(0.3)
    b = P.dump_request(P.Addr.SETUP)
    send(b)
    return [a, b], listen(args.wait)


@test("3. Peticion de patron 1")
def t3():
    m = P.dump_request(P.Addr.pattern(0))
    send(m)
    return [m], listen(args.wait)


@test("4. Bulk mode ON, luego patron 1")
def t4():
    a = P.bulk_mode(True)
    send(a)
    time.sleep(0.3)
    b = P.dump_request(P.Addr.pattern(0))
    send(b)
    return [a, b], listen(args.wait)


@test("5. Peticion de cancion 1")
def t5():
    m = P.dump_request(P.Addr.song(0))
    send(m)
    return [m], listen(args.wait)


@test("6. Peticion de parametro (bulk mode) - deberia contestar el valor")
def t6():
    m = P.param_request(P.Addr.BULK_MODE)
    send(m)
    return [m], listen(args.wait)


@test("7. Identity Request universal - responde casi cualquier equipo MIDI")
def t7():
    m = bytes([0xF0, 0x7E, 0x7F, 0x06, 0x01, 0xF7])
    send(m)
    return [m], listen(args.wait)


@test("8. Peticion de info de patrones (solo transmite, quiza mas permisiva)")
def t8():
    m = P.dump_request(P.Addr.INFO_PATTERN_1_32)
    send(m)
    return [m], listen(args.wait)


ok = []
for name, fn in TESTS:
    print(name)
    drain()
    sent, got = fn()
    if report(name, sent, got):
        ok.append(name)
    print()

print("=" * 60)
if ok:
    print("FUNCIONARON:")
    for n in ok:
        print("  ", n)
else:
    print("Ninguna produjo respuesta.")
    print("Siguiente hipotesis: el QY100 solo inicia volcados desde su propio")
    print("panel (utilidades -> trasvase en bloque, pag. 129). En ese caso se")
    print("usa `syx.py monitor` y se lanza desde el equipo.")

inport.close()
outport.close()
