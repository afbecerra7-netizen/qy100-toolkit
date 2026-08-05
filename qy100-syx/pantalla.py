"""Escribe texto y dibujos en la pantalla del QY100.

    .venv/bin/python pantalla.py texto "HOLA"
    .venv/bin/python pantalla.py dibujo corazon

No es nada propio del QY100: es el **XG Display Data**, y el QY100 lo obedece
por ser un modulo XG. Esta en el Data List, tabla 1-5:

    texto    F0 43 1n 4C 06 00 00 <hasta 32 ASCII>  F7
    bitmap   F0 43 1n 4C 07 00 00 <48 bytes>        F7

`1n` es un *parameter change*, asi que **no lleva byte count ni checksum** — al
reves que los volcados en bloque, que si los llevan. `n` es el numero de
dispositivo; 0 es el aparato 1.

El bitmap es de **16x16**, repartido de una forma poco evidente: cada byte
guarda siete pixeles horizontales en los bits b6..b0, con **b6 a la izquierda**,
y los 48 bytes son tres bloques de columnas.

    bytes  0-15   filas 0-15, columnas 0-6
    bytes 16-31   filas 0-15, columnas 7-13
    bytes 32-47   filas 0-15, columnas 14-15   (solo b6 y b5)

El manual anade algo util: **se pueden mandar elementos sueltos y el resto se
queda como estaba**, asi que la pantalla se puede animar sin reenviarla entera.

**Las dos direcciones pintan en zonas distintas del QY100**, y eso el manual no
lo dice — se comprobo mirando el aparato (2026-08-04):

    06 00 00  MESSAGE WINDOW  ->  el popup, que se quita solo
    07 00 00  BITMAP WINDOW   ->  la franja de abajo, que se queda

Son complementarias, no alternativas: el popup sirve para avisos puntuales y la
franja para algo persistente. Y como la franja no se borra sola, ahi si tiene
sentido animar — a 104 bpm el latido va suelto, y el QY100 transmite reloj MIDI,
asi que una animacion podria seguir al secuenciador en vez de a un `sleep`.
"""
import argparse
import sys

import mido

PUERTO = "M4"
DISPOSITIVO = 0                     # 0 = aparato 1
ANCHO = ALTO = 16

CORAZON = [
    "................",
    "................",
    "..XXX....XXX....",
    ".XXXXX..XXXXX...",
    "XXXXXXXXXXXXXXX.",
    "XXXXXXXXXXXXXXX.",
    "XXXXXXXXXXXXXXX.",
    ".XXXXXXXXXXXXX..",
    "..XXXXXXXXXXX...",
    "...XXXXXXXXX....",
    "....XXXXXXX.....",
    ".....XXXXX......",
    "......XXX.......",
    ".......X........",
    "................",
    "................",
]

CORCHEA = [
    "................",
    ".....XXXXXX.....",
    ".....XXXXXXXX...",
    ".....XX....XXX..",
    ".....XX.....XX..",
    ".....XX....XXX..",
    ".....XXXXXXXX...",
    ".....XXXXXX.....",
    ".....XX.........",
    ".....XX.........",
    ".....XX.........",
    "...XXXX.........",
    "..XXXXXX........",
    "..XXXXXX........",
    "...XXXX.........",
    "................",
]

CARA = [
    "................",
    "....XXXXXXXX....",
    "..XX........XX..",
    ".X............X.",
    ".X............X.",
    "X..XX......XX..X",
    "X..XX......XX..X",
    "X..............X",
    "X..............X",
    "X..X........X..X",
    ".X..XX....XX..X.",
    ".X....XXXX....X.",
    "..XX........XX..",
    "....XXXXXXXX....",
    "................",
    "................",
]

DIBUJOS = {"corazon": CORAZON, "corchea": CORCHEA, "cara": CARA}


def codificar(filas):
    """16 cadenas de 16 caracteres -> los 48 bytes que espera el equipo."""
    if len(filas) != ALTO or any(len(f) != ANCHO for f in filas):
        raise ValueError("hacen falta %d filas de %d caracteres" % (ALTO, ANCHO))
    datos = [0] * 48
    for y, fila in enumerate(filas):
        for x, c in enumerate(fila):
            if c in " .":
                continue
            # b6 es el pixel de la izquierda de cada grupo de siete.
            bloque, dentro = divmod(x, 7)
            datos[bloque * 16 + y] |= 1 << (6 - dentro)
    return datos


def texto(msg, puerto=PUERTO):
    cuerpo = [0x43, 0x10 | DISPOSITIVO, 0x4C, 0x06, 0x00, 0x00]
    cuerpo += [ord(c) if 32 <= ord(c) <= 127 else 32 for c in msg[:32]]
    _mandar(cuerpo, puerto)


def dibujo(filas, puerto=PUERTO):
    _mandar([0x43, 0x10 | DISPOSITIVO, 0x4C, 0x07, 0x00, 0x00] + codificar(filas),
            puerto)


def _mandar(cuerpo, puerto):
    out = mido.open_output(puerto)
    try:
        out.send(mido.Message("sysex", data=cuerpo))
    finally:
        out.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("modo", choices=["texto", "dibujo"])
    ap.add_argument("valor", help="el texto, o el nombre de un dibujo: "
                                  + ", ".join(sorted(DIBUJOS)))
    ap.add_argument("--puerto", default=PUERTO)
    args = ap.parse_args()

    if args.modo == "texto":
        texto(args.valor, args.puerto)
        print("en pantalla: %r" % args.valor[:32])
    else:
        if args.valor not in DIBUJOS:
            raise SystemExit("dibujos: %s" % ", ".join(sorted(DIBUJOS)))
        d = DIBUJOS[args.valor]
        dibujo(d, args.puerto)
        print("\n".join(d).replace(".", " "))
        print("\nen pantalla: %s" % args.valor)
