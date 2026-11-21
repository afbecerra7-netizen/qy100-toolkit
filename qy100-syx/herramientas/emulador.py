"""Prueba una escritura de patron en el emulador QYΩ antes de mandarla al QY100.

    .venv/bin/python herramientas/emulador.py              # la prueba de ida y vuelta
    .venv/bin/python herramientas/emulador.py --patron 5   # en otro patron de usuario

Necesita el emulador corriendo en local, con el firmware 1.37 cargado:

    QYOMEGA_FIRMWARE=/ruta/qy100_flash_v137.bin ./emu serve     # escucha en 127.0.0.1:8100

**No abre ningun puerto MIDI.** Le habla al emulador por HTTP (`POST /sysex`), que
mete los bytes por el MIDI IN emulado y devuelve lo que el aparato emulado contesta.
Nada de esto sale del ordenador ni llega al QY100 de verdad.

Que hace: arma un patron con el codificador de este repo (las mismas funciones
que usa `herramientas/importar.py`), lo escribe con el
mismo encuadre que al aparato (`bulk mode ON -> pistas -> 5 cabeceras -> bulk mode
OFF`), lo pide de vuelta y compara **las notas decodificadas**, no los bytes: el
aparato reserializa y devuelve bytes distintos para los mismos datos.

**Lo que prueba y lo que no.** Que el firmware real, corriendo en un modelo de su
procesador, acepta la escritura y la devuelve con las mismas notas. No prueba que el
QY100 de verdad haga lo mismo: el emulador no tiene tiempos exactos ni esta
comparado sistematicamente con el aparato. Es un primer filtro, no un permiso.
"""
import argparse
import json
import os
import sys
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [RAIZ, os.path.join(RAIZ, "herramientas")]
from qy100syx import patternfmt as F                                 # noqa: E402
from qy100syx import protocol as P                                   # noqa: E402
from qy100syx import generar as G                                    # noqa: E402

URL = os.environ.get("QYOMEGA_URL", "http://127.0.0.1:8100")


def enviar(mensajes):
    """Manda mensajes SysEx al emulador y devuelve lo que contesta, como bytes."""
    cuerpo = b"".join(mensajes)
    req = urllib.request.Request(URL + "/sysex", data=cuerpo, method="POST",
                                 headers={"Content-Type": "application/octet-stream"})
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.load(r)
    if d.get("error"):
        raise SystemExit("el emulador contesto un error: %s" % d["error"])
    return d.get("sent", 0), b"".join(bytes.fromhex(h) for h in d.get("replies") or [])


def leer_patron(n):
    """Pide el patron n (base cero) en bulk mode y devuelve sus bloques de volcado."""
    _s, blob = enviar([P.bulk_mode(True),
                       P.dump_request(P.Addr.pattern(n, F.HEADER_TR)),
                       P.bulk_mode(False)])
    msgs, _ = P.parse_all(blob)
    return [m for m in msgs if m.sub == P.SUB_DUMP]


def notas_por_pista(dumps):
    pistas = {}
    for m in dumps:
        if m.addr[2] != F.HEADER_TR:
            pistas.setdefault(m.addr[2], []).append(bytes(m.data))
    return {tr: F.decode_blocks(bl)[0] for tr, bl in pistas.items()}   # (notas, fin)


def patron_de_prueba():
    """Dos pistas en Main A, 2 compases. El bajo pasa de un bloque: prueba el encadenado."""
    Q = F.CLOCKS_PER_QUARTER
    compases, total = 2, 2 * 4 * Q
    bombo = [F.Note(36, 112, 60, t * Q) for t in range(8)]
    bajo = [F.Note(36 + (i * 5) % 24, 90 + i % 30, Q // 8, i * Q // 4) for i in range(32)]
    kit = G.kit_por_nombre("Rock Kit")[1]
    voz = G.voz_por_nombre("SynBass1")
    pistas = {}
    for idx, notas, prog, banco in ((0, bombo, kit, F.BANK_DRUMS),
                                    (5, bajo, voz, F.BANK_NORMAL)):
        pre = F.build_prefix(base=F.PREFIJO_BASE, compases=compases, nombre="PRUEBA",
                             tipo="Bypass", pista=idx, voz=prog, banco=banco)
        pistas[idx] = (G.a_bloques(notas, total, pre), notas, prog, banco == F.BANK_DRUMS)
    return compases, pistas


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--patron", type=int, default=3, help="patron de usuario, 1-64")
    args = ap.parse_args()
    n = args.patron - 1
    seccion = 1                                                   # Main A

    previas = leer_patron(n)
    print("antes: el patron %d devuelve %d bloque(s)" % (args.patron, len(previas)))

    compases, pistas = patron_de_prueba()
    cab = list(F.CABECERA_BASE)
    cab[0] = F.set_tempo(F.encode_header(cab[0], name="PRUEBA",
                                         measures=[compases] * len(F.SECTIONS)), 120)
    cab = F.set_registry(cab, {seccion: sorted(pistas)})
    for idx, (_b, _n, prog, es_bat) in pistas.items():
        cab = F.set_mixer_voice(cab, idx, prog, bateria=es_bat)

    salida = []
    for idx, (bloques, _n, _p, _b) in sorted(pistas.items()):
        tr = F.track_byte(seccion, idx)
        salida += [P.build_dump(P.Addr.pattern(n, tr), b) for b in bloques]
    salida += [P.build_dump(P.Addr.pattern(n, F.HEADER_TR), b) for b in cab]
    enviados, _ = enviar([P.bulk_mode(True)] + salida + [P.bulk_mode(False)])
    print("escritos %d bloques (%d pistas + %d cabeceras); el emulador conto %d mensajes"
          % (len(salida), len(salida) - len(cab), len(cab), enviados))

    vuelta = leer_patron(n)
    print("despues: el patron %d devuelve %d bloque(s)" % (args.patron, len(vuelta)))
    leidas = notas_por_pista(vuelta)
    fallos = 0
    for idx, (bloques, notas, _p, _b) in sorted(pistas.items()):
        tr = F.track_byte(seccion, idx)
        got = leidas.get(tr, [])
        ok = [(x.pitch, x.velocity, x.gate, x.time) for x in got] == \
             [(x.pitch, x.velocity, x.gate, x.time) for x in notas]
        fallos += not ok
        print("  %-12s %d bloque(s) escritos, %2d notas -> %2d leidas  %s"
              % (F.describe_tr(tr), len(bloques), len(notas), len(got), "IGUAL" if ok else "DISTINTO"))
    cab_v = [bytes(m.data) for m in vuelta if m.addr[2] == F.HEADER_TR]
    if cab_v:
        reg = F.decode_registry(cab_v)
        print("  cabecera: %d bloque(s), tempo %.1f, registro de Main A %s"
              % (len(cab_v), F.decode_tempo(cab_v[0]), reg.get(seccion)))
    else:
        fallos += 1
        print("  cabecera: NO volvio")
    print("\n%s" % ("IDA Y VUELTA BIEN en el emulador" if not fallos
                    else "%d diferencia(s): mirar antes de mandar esto al aparato" % fallos))
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
