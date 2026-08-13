"""Barre los indices de categoria de una referencia a frase preset, oyendo.

    .venv/bin/python barrer_categorias.py --patron 3 --indices 0-14

La idea es de Felipe y es la que hace esto posible: **el barrido no necesita
leer**. Escribir la referencia y darle play son las dos unicas operaciones, y las
dos funcionan con `MIDI CONTROL = In/Out`. Lo que se rompe con In/Out son los
volcados —el reloj inunda la entrada y se pierden bloques—, pero aqui la
respuesta no es un dump: **es lo que suena**.

Asi que por cada indice candidato se escribe la cabecera con la bandera puesta,
se manda Start, se capturan las notas que emite el QY100 unos segundos y se manda
Stop. El contenido delata la familia de la frase: notas 35-50 en patron de kit es
una categoria de bateria, alturas graves sostenidas es bajo, acordes simultaneos
es una de acorde.

**Limite conocido**: esto separa familias, no siempre categorias. `Da` y `Db` son
las dos de bateria y su contenido puede ser indistinguible; ese residuo hay que
confirmarlo en el panel. Se marca en la salida en vez de resolverlo por
conjetura.

Requisitos, y el tercero no es opcional:

- `MIDI CONTROL` en **In/Out**
- el QY100 en el patron de destino, seccion Main A, parado
- **no tocar el panel mientras corre.** Manejarlo por MIDI mientras alguien
  navega los menus ya lo colgo una vez y hubo que apagarlo.
"""
import argparse
import collections
import sys
import time

import mido

from qy100syx import patternfmt as F
from qy100syx import protocol as P
from qy100syx import transfer

TR_DESTINO = F.track_byte(1, 0)          # Main A, pista D1
BEAT_NIBBLE = 0x9                        # uno de los tres; el otro medido es 0xA


def log(*a):
    print(*a, file=sys.stderr)


def cabecera_base(ruta_respaldo, patron_origen=0):
    """Los 5 bloques de cabecera de un patron vacio, capturados del equipo."""
    msgs, _ = P.parse_all(open(ruta_respaldo, "rb").read())
    cab = [m for m in msgs
           if m.sub == P.SUB_DUMP and m.addr[0] == 0x12
           and m.addr[1] == patron_origen and m.addr[2] == F.HEADER_TR]
    if len(cab) != 5:
        raise SystemExit("esperaba 5 bloques de cabecera, hay %d" % len(cab))
    return [bytes(m.data) for m in cab]


def con_referencia(cab, categoria, numero, beat=BEAT_NIBBLE):
    """Pone la referencia en la ranura de Main A D1 y devuelve los 5 bloques."""
    d = bytearray(b"".join(F.unpack(p) for p in cab))
    d[F.REGISTRY_FLAGS_OFF + TR_DESTINO] = (categoria << 4) | beat
    d[F.REGISTRY_OFF + TR_DESTINO] = numero - 1
    return [F.pack(bytes(d[i:i + F.UNPACKED_BYTES]))
            for i in range(0, len(d), F.UNPACKED_BYTES)]


def escuchar(inp, outp, segundos):
    """Manda Start, recoge note_on, manda Stop. Devuelve las notas."""
    for m in list(inp.iter_pending()):
        pass
    outp.send(mido.Message("start"))
    notas, fin = [], time.time() + segundos
    while time.time() < fin:
        for m in inp.iter_pending():
            if m.type == "note_on" and m.velocity > 0:
                notas.append(m.note)
        time.sleep(0.01)
    outp.send(mido.Message("stop"))
    # Cortar cualquier cola: 120 es el que corta de verdad, 123 solo suelta.
    for canal in range(16):
        for cc in (120, 123):
            outp.send(mido.Message("control_change", channel=canal,
                                   control=cc, value=0))
    return notas


def familia(notas):
    """Que clase de frase suena, por el contenido. Deliberadamente prudente."""
    if not notas:
        return "-- nada --"
    c = collections.Counter(notas)
    percusivas = sum(v for k, v in c.items() if 35 <= k <= 59)
    prop = percusivas / float(len(notas))
    if prop > 0.85:
        return "bateria o percusion"
    if prop < 0.15 and max(notas) < 60:
        return "bajo"
    if len(c) > 2 and prop < 0.5:
        return "acorde / melodica"
    return "mezcla, sin decidir"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--patron", type=int, default=3)
    ap.add_argument("--indices", default="0-14", help="p.ej. 0-14 o 0,2,5")
    ap.add_argument("--numero", type=int, default=1, help="numero de frase")
    ap.add_argument("--beat", type=lambda x: int(x, 0), default=BEAT_NIBBLE)
    ap.add_argument("--segundos", type=float, default=4.0)
    ap.add_argument("--respaldo", default="dumps/respaldo-antes-de-estilo.syx")
    ap.add_argument("--in", dest="in_port", default="M4")
    ap.add_argument("--out", dest="out_port", default="M4")
    args = ap.parse_args()

    if "-" in args.indices:
        a, b = args.indices.split("-")
        indices = list(range(int(a), int(b) + 1))
    else:
        indices = [int(x) for x in args.indices.split(",")]

    cab = cabecera_base(args.respaldo)
    inp = mido.open_input(args.in_port)
    outp = mido.open_output(args.out_port)
    # El reloj llega a 48/s con MIDI CONTROL en In/Out y ahogaria la captura.
    transfer.silenciar_reloj(inp, log)

    resultados = []
    try:
        for k in indices:
            bloques = con_referencia(cab, k, args.numero, args.beat)
            addr = P.Addr.pattern(args.patron - 1, F.HEADER_TR)
            salida = [P.build_dump(addr, b) for b in bloques]
            transfer.send_pattern(outp, salida)
            time.sleep(0.4)
            notas = escuchar(inp, outp, args.segundos)
            c = collections.Counter(notas)
            resultados.append((k, notas, familia(notas)))
            log("indice %2d (bandera %02X)  %3d notas  %-22s %s"
                % (k, (k << 4) | args.beat, len(notas), familia(notas),
                   " ".join("%d" % n for n, _ in c.most_common(6))))
    finally:
        for canal in range(16):
            outp.send(mido.Message("control_change", channel=canal,
                                   control=120, value=0))
        inp.close()
        outp.close()

    log("")
    mudos = [k for k, n, _ in resultados if not n]
    if mudos:
        log("Sin sonido en los indices: %s" % " ".join(map(str, mudos)))
        log("O no son categorias validas, o el equipo no arranco con Start.")
