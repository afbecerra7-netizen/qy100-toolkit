"""Escribe un tramo de una partitura MIDI en un patron del QY100, tal cual.

    .venv/bin/python importar.py partitura.mid --patron 14 --compases 1-8 \\
        --pista "Flauta=C1" --pista "Contrabajo=BA" --pista "Bombo 1=D1"

**No deduce nada.** Los motores de `andina.py` extraen una celda y la repiten;
esto copia las notas que hay. Son dos usos distintos y conviene no confundirlos:

- Un **estilo** es un motor: seis secciones, densidades, y una celda que se
  repite indefinidamente. Sirve para tocar encima.
- Una **importacion** es la pieza. Suena como la partitura y se acaba donde ella
  se acaba.

Cuando la pieza es de dominio publico o el arreglo es libre, importar es la via
mas fiel: no hay intermediacion, no hay celda que extraer mal, y las tres veces
que se dedujo un patron de bambuco a partir de teoria o de prosa salio mal.

## Lo que hay que decidir al importar

**Que pista va a que pista.** Un arreglo orquestal tiene veinte instrumentos y el
patron tiene ocho. Hay que elegir, y elegir es interpretar: la flauta y el oboe
del torbellino doblan la misma melodia, asi que meter las dos es duplicar.

**Que tramo.** Un patron llega a 32 compases y las piezas duran mas. Se corta.

**El compas.** Se lee de la partitura y se escribe en la cabecera, porque el
QY100 admite /4, /8 y /16 pero no /2 (tres bits para el denominador).
"""
import argparse
import collections
import os
import sys
import time

import mido

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qy100syx import patternfmt as F                                 # noqa: E402
from qy100syx import protocol as P, transfer                         # noqa: E402


def leer(ruta):
    """{nombre de pista: [(tick, altura, velocity, duracion)]} y la metrica."""
    m = mido.MidiFile(ruta)
    sig, bpm = (4, 4), 120.0
    pistas = collections.defaultdict(list)
    for tr in m.tracks:
        t = 0
        nom = ""
        abiertas = collections.defaultdict(list)
        for msg in tr:
            t += msg.time
            if msg.type == "track_name":
                # Los nombres suelen venir con un NUL al final.
                nom = msg.name.strip().strip("\x00")
            elif msg.type == "time_signature":
                sig = (msg.numerator, msg.denominator)
            elif msg.type == "set_tempo":
                bpm = 60e6 / msg.tempo
            elif msg.type == "note_on" and msg.velocity:
                abiertas[msg.note].append((t, msg.velocity))
            elif msg.type == "note_off" or (msg.type == "note_on" and not msg.velocity):
                if abiertas.get(msg.note):
                    ini, vel = abiertas[msg.note].pop(0)
                    pistas[nom].append((ini, msg.note, vel, t - ini))
        # Las que quedaron abiertas al final del archivo se cierran con un valor
        # razonable en vez de descartarse: son notas reales.
        for alt, pend in abiertas.items():
            for ini, vel in pend:
                pistas[nom].append((ini, alt, vel, m.ticks_per_beat))
    return m.ticks_per_beat, sig, bpm, {k: sorted(v) for k, v in pistas.items() if v}


def a_qy100(notas, tpb, desde_tick):
    """Ticks de la partitura -> relojes del QY100. Exacto si tpb divide a 480."""
    Q = F.CLOCKS_PER_QUARTER
    return sorted((F.Note(alt, max(1, min(127, vel)),
                          max(1, int(round(dur * Q / float(tpb)))),
                          int(round((ini - desde_tick) * Q / float(tpb))))
                   for ini, alt, vel, dur in notas),
                  key=lambda n: n.time)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("archivo")
    ap.add_argument("--patron", type=int, default=14)
    ap.add_argument("--seccion", type=int, default=1, help="1 = Main A")
    ap.add_argument("--compases", default="1-8", help="rango, p.ej. 1-8")
    ap.add_argument("--pista", action="append", default=[],
                    help='"Nombre en la partitura=D1" — repetible. '
                         "Destinos: D1 D2 PC BA C1 C2 C3 C4")
    ap.add_argument("--bpm", type=float, help="por defecto, el de la partitura")
    ap.add_argument("--voz", help="voz del QY100 para las pistas melodicas, o "
                                  "'kit' para forzar bateria")
    ap.add_argument("--nombre", help="nombre del patron, hasta 8 caracteres")
    ap.add_argument("--escribir", action="store_true")
    ap.add_argument("--out", required=True, help="puerto MIDI de salida")
    ap.add_argument("--in", dest="inp", required=True,
                    help="puerto de entrada; hace falta para leer el patron "
                         "antes de escribirlo")
    ap.add_argument("--listar", action="store_true", help="solo listar las pistas")
    args = ap.parse_args()

    tpb, sig, bpm_orig, pistas = leer(args.archivo)
    beats = sig[0] if sig[1] == 4 else sig[0] // 2
    compas_ticks = tpb * beats
    bpm = args.bpm or bpm_orig

    print("%s — %d/%d, %.0f bpm, %d ticks por negra"
          % (os.path.basename(args.archivo), sig[0], sig[1], bpm_orig, tpb))
    if args.listar or not args.pista:
        print("\npistas disponibles:")
        for nom, ev in sorted(pistas.items(), key=lambda x: -len(x[1])):
            alt = [n for _t, n, _v, _d in ev]
            print("   %-28s %5d notas  %d-%d" % (nom[:28] or "(sin nombre)",
                                                 len(ev), min(alt), max(alt)))
        if not args.pista:
            print('\nElige con --pista "Nombre=D1".')
        raise SystemExit(0)

    a, b = (int(x) for x in args.compases.split("-"))
    n_comp = b - a + 1
    if not 1 <= n_comp <= F.MAX_MEASURES:
        raise SystemExit("el tramo son %d compases; el maximo es %d"
                         % (n_comp, F.MAX_MEASURES))
    desde, hasta = (a - 1) * compas_ticks, b * compas_ticks
    total = F.section_clocks(n_comp, beats_per_bar=beats)

    from qy100syx import generar as G
    IDX = {n: i for i, n in enumerate(F.TRACK_NAMES)}

    bloques = {}
    print("\ncompases %d-%d (%d), %d/%d a %.0f bpm\n" % (a, b, n_comp, beats, 4, bpm))
    for spec in args.pista:
        try:
            origen, destino = spec.rsplit("=", 1)
        except ValueError:
            raise SystemExit('formato: --pista "Nombre=D1", no %r' % spec)
        if destino not in IDX:
            raise SystemExit("destino desconocido: %r. Validos: %s"
                             % (destino, " ".join(F.TRACK_NAMES)))
        coincide = [k for k in pistas if origen.lower() in k.lower()]
        if not coincide:
            raise SystemExit("no encuentro ninguna pista que contenga %r" % origen)
        ev = [e for k in coincide for e in pistas[k] if desde <= e[0] < hasta]
        notas = [n for n in a_qy100(ev, tpb, desde) if n.time < total]
        idx = IDX[destino]
        # **La voz se decide por el contenido, no por la ranura.** Antes se
        # asumia que D1, D2 y PC son percusion siempre, y meter la marimba en
        # `PC` la puso a sonar por un kit de bateria: las alturas 55-74 caen en
        # platos y campanas, y una de ellas sostenida daba un pitido constante.
        #
        # Costo un rato porque el sintoma imitaba dos fallos ya documentados:
        # sonaba solo con el QY100 desmuteado y **sobrevivia al ciclo de
        # corriente** —el banco vive en el mezclador del patron, que se guarda—,
        # que es exactamente el cuadro del choque de dos kits de bateria.
        #
        # El criterio: si las alturas se salen del rango de un kit de bateria
        # (35-81 en GM) o si la pista abarca mas de dos octavas, es material
        # melodico. `--voz` manda sobre todo esto.
        alturas = [n.pitch for n in notas] or [60]
        rango = max(alturas) - min(alturas)
        es_bat = idx in (0, 1, 2) and rango <= 24 and min(alturas) >= 35
        # `--voz` nombra la voz de las pistas MELODICAS y no decide si algo es
        # bateria: aplicarlo a todas le habria puesto marimba a un bombo.
        prog = (G.kit_por_nombre("Rock Kit")[1] if es_bat
                else G.voz_por_nombre(args.voz or "NylonGtr"))
        pre = F.build_prefix(base=F.PREFIJO_BASE, compases=n_comp,
                             nombre=destino, tipo="Bypass", pista=idx, voz=prog,
                             banco=F.BANK_DRUMS if es_bat else F.BANK_NORMAL)
        bl = G.a_bloques(notas, total, pre)
        bloques[idx] = (bl, prog, es_bat)
        print("  %-26s -> %-3s %4d notas  %2d bloques"
              % (coincide[0][:26], destino, len(notas), len(bl)))

    tot = sum(len(b) for b, _p, _x in bloques.values()) + 5
    print("\n%d bloques = %.1f KB" % (tot, tot * 128 / 1024.0))
    if not args.escribir:
        print("\nPrevisualizacion. Anade --escribir.")
        raise SystemExit(0)

    # --- Leer el patron de destino ANTES de escribir -----------------------
    #
    # Esto no estaba, y era el mismo fallo que ya arrastraban `bambuco.py` y
    # `pasillo.py`: armar la cabecera desde `CABECERA_BASE` —una captura de un
    # patron VACIO— y escribir el registro poniendo `0xF8` a mano.
    #
    # Lo que se perdia en cada importacion: el mezclador, los acordes por
    # seccion, las longitudes de las otras cinco secciones, las pistas que ya
    # hubiera, y **toda referencia a frase preset**. Esto ultimo en silencio,
    # porque `set_registry` preserva a proposito las ranuras cuyo estado no
    # reconoce y escribir el byte a mano se salta esa proteccion. Ademas
    # importar dos secciones seguidas borraba la primera.
    #
    # La regla que lo gobierna todo: **el patron va entero o no va**, pistas
    # primero y las 5 cabeceras al final, en el orden en que el aparato lo
    # volco.
    cab_addr = P.Addr.pattern(args.patron - 1, F.HEADER_TR)
    inp = mido.open_input(args.inp)
    outp = mido.open_output(args.out)
    try:
        outp.send(mido.Message("sysex", data=P.bulk_mode(True)[1:-1]))
        time.sleep(0.3)
        print("\nLeyendo el patron %d..." % args.patron)
        blob, _ = transfer.request(outp, inp, cab_addr, log=print)
    finally:
        try:
            outp.send(mido.Message("sysex", data=P.bulk_mode(False)[1:-1]))
            time.sleep(0.2)
        except Exception:
            pass
        inp.close()

    msgs, _ = P.parse_all(blob)
    dumps = [m for m in msgs if m.sub == P.SUB_DUMP]
    cab_msgs = [m for m in dumps if m.addr[2] == F.HEADER_TR]
    if not cab_msgs:
        # Un patron vacio no devuelve NADA, ni la cabecera, asi que "no
        # contesto" no distingue entre vacio y fallo de linea. Se arranca de la
        # plantilla; si de verdad hubiera fallo, la relectura posterior lo dice.
        print("El patron %d esta vacio: se crea desde la plantilla." % args.patron)
        cab_bytes, previas = list(F.CABECERA_BASE), []
    else:
        cab_bytes = [bytes(m.data) for m in cab_msgs]
        previas = [m for m in dumps if m.addr[2] != F.HEADER_TR]
        print("Leidas %d pistas previas; se conservan." % len({m.addr[2] for m in previas}))

    # Solo se toca la longitud de LA seccion importada; las otras cinco se
    # quedan como estan.
    _n, comp_actuales = F.decode_header(cab_bytes[0])
    comp_actuales = list(comp_actuales)
    comp_actuales[args.seccion] = n_comp
    d = F.encode_header(cab_bytes[0], name=(args.nombre or "IMPORT")[:8],
                        measures=comp_actuales)
    d = F.set_tempo(d, bpm)
    cab_bytes[0] = F.set_time_signature(d, beats, 4)

    # Pistas primero, sustituyendo en su sitio; lo que no regeneramos se
    # reenvia intacto.
    salida, vistos = [], set()
    nuevos = {F.track_byte(args.seccion, idx): bl
              for idx, (bl, _p, _x) in bloques.items()}
    for m in previas:
        tr = m.addr[2]
        if tr in nuevos:
            if tr not in vistos:
                vistos.add(tr)
                salida += [P.build_dump(m.addr, b) for b in nuevos[tr]]
        else:
            salida.append(m.raw)
    for tr, bl in sorted(nuevos.items()):
        if tr not in vistos:
            salida += [P.build_dump(P.Addr.pattern(args.patron - 1, tr), b)
                       for b in bl]

    # `set_registry` en vez del byte a mano: es lo que preserva las referencias
    # a frases de fabrica que hubiera en el patron.
    reg = {}
    for m in previas:
        s, t = divmod(m.addr[2], F.TRACKS_PER_SECTION)
        reg.setdefault(s, set()).add(t)
    for tr in nuevos:
        s, t = divmod(tr, F.TRACKS_PER_SECTION)
        reg.setdefault(s, set()).add(t)
    cab_f = F.set_registry(cab_bytes, {s: sorted(v) for s, v in reg.items()})
    for idx, (_b, prog, es_bat) in bloques.items():
        cab_f = F.set_mixer_voice(cab_f, idx, prog, bateria=es_bat)
    salida += [P.build_dump(cab_addr, b) for b in cab_f]

    try:
        n = transfer.send_pattern(outp, salida, log=print)
    finally:
        outp.close()
    print("\nEscritos %d bloques en el patron %d, %s"
          % (n, args.patron, F.SECTIONS[args.seccion]))
