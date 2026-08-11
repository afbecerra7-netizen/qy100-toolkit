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


#: Canal de percusion en General MIDI. Es el 10 contando desde 1, o sea el 9
#: contando desde 0, que es como lo entrega `mido`. **Este es el unico dato del
#: fichero que dice de verdad "esto es percusion"**; las alturas no lo dicen,
#: porque una marimba y un kit de bateria ocupan el mismo rango.
CANAL_PERCUSION = 9


def leer(ruta):
    """{nombre de pista: ([(tick, altura, velocity, duracion)], canales)}.

    Devuelve tambien el conjunto de canales MIDI por los que llego cada pista,
    porque es lo que distingue percusion de material melodico.
    """
    m = mido.MidiFile(ruta)
    sig, bpm = (4, 4), 120.0
    pistas = collections.defaultdict(list)
    canales = collections.defaultdict(set)
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
                canales[nom].add(msg.channel)
            elif msg.type == "note_off" or (msg.type == "note_on" and not msg.velocity):
                if abiertas.get(msg.note):
                    ini, vel = abiertas[msg.note].pop(0)
                    pistas[nom].append((ini, msg.note, vel, t - ini))
        # Las que quedaron abiertas al final del archivo se cierran con un valor
        # razonable en vez de descartarse: son notas reales.
        for alt, pend in abiertas.items():
            for ini, vel in pend:
                pistas[nom].append((ini, alt, vel, m.ticks_per_beat))
    return (m.ticks_per_beat, sig, bpm,
            {k: sorted(v) for k, v in pistas.items() if v},
            {k: canales[k] for k in pistas if pistas[k]})


def decidir_voz(canales, forzar_kit=False):
    """(es_bateria, por_que) de una pista, a partir de sus canales MIDI.

    Vive fuera del `__main__` **para poder probarla**. La decision que hacia esto
    se ha equivocado dos veces —primero por la ranura de destino, luego por el
    rango de alturas— y las dos veces se descubrio tocando, no leyendo, porque
    estaba enterrada en medio del bucle de importacion y no habia manera de
    interrogarla. Ahora `test_protocol.py` le pasa su propio caso motivador.
    """
    canales = set(canales)
    if forzar_kit:
        return True, "--voz kit"
    if canales == {CANAL_PERCUSION}:
        return True, "canal 10"
    if CANAL_PERCUSION in canales:
        # Mezcla: la pista trae percusion y notas por otros canales. No hay
        # respuesta buena, asi que se dice en voz alta y se cae del lado seguro.
        return False, ("MEZCLA de canales %s — se trata como melodica; usa "
                       "--voz kit si no es eso"
                       % sorted(c + 1 for c in canales))
    if not canales:
        return False, "sin canal, por defecto melodica"
    return False, "canal %s" % sorted(c + 1 for c in canales)


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
    ap.add_argument("--voz", help="voz del QY100 para las pistas melodicas. "
                                  "'kit' fuerza bateria en TODAS las pistas; "
                                  "por defecto manda el canal MIDI del fichero")
    ap.add_argument("--nombre", help="nombre del patron, hasta 8 caracteres")
    ap.add_argument("--escribir", action="store_true")
    ap.add_argument("--out", required=True, help="puerto MIDI de salida")
    ap.add_argument("--in", dest="inp", required=True,
                    help="puerto de entrada; hace falta para leer el patron "
                         "antes de escribirlo")
    ap.add_argument("--listar", action="store_true", help="solo listar las pistas")
    args = ap.parse_args()

    tpb, sig, bpm_orig, pistas, canales = leer(args.archivo)
    # `--voz kit` estuvo anunciado en la ayuda y sin implementar: llegaba a
    # `voz_por_nombre('kit')`, que no encuentra ninguna voz con ese nombre.
    forzar_kit = (args.voz or "").strip().lower() == "kit"
    try:
        beats = F.negras_por_compas(*sig)
    except ValueError as e:
        raise SystemExit("la partitura esta en %d/%d: %s" % (sig[0], sig[1], e))
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

    bloques, esperadas = {}, {}
    print("\ncompases %d-%d (%d), %d/%d a %.0f bpm\n" % (a, b, n_comp, sig[0], sig[1], bpm))
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
        # **Percusion o no se decide por el canal MIDI, que es un dato, no por
        # las alturas, que es una adivinanza.**
        #
        # Primero se decidia por la ranura: D1, D2 y PC eran percusion siempre.
        # Meter la marimba en `PC` la puso a sonar por un kit de bateria —las
        # alturas 55-74 caen en platos y campanas, y una sostenida daba un
        # pitido constante—. Costo encontrarlo porque el sintoma imitaba dos
        # fallos ya documentados: sonaba solo con el QY100 desmuteado y
        # **sobrevivia al ciclo de corriente**, porque el banco vive en el
        # mezclador del patron, que se guarda.
        #
        # El primer arreglo cambio la ranura por el rango de alturas: bateria si
        # abarca dos octavas o menos y no baja de 35. **Y no arreglaba su propio
        # caso**: la marimba mide 74-55 = 19 y arranca en 55, asi que seguia
        # entrando por bateria. No podia funcionar — un kit de GM ocupa 35-81 y
        # una marimba cabe entera ahi dentro. Ningun umbral de alturas separa
        # dos cosas que ocupan el mismo rango.
        #
        # El canal 10 de GM si lo dice, y viene en el fichero. Cuando el fichero
        # no lo respeta, se pide a mano en vez de suponer, y **la duda cae del
        # lado melodico**: una voz melodica tocando un patron de bateria suena
        # raro y ya; un kit tocando una marimba dejo un pitido que sobrevivio a
        # apagar el aparato.
        canales_pista = set()
        for k in coincide:
            canales_pista |= canales.get(k, set())
        es_bat, por_que = decidir_voz(canales_pista, forzar_kit)
        # `--voz` nombra la voz de las pistas MELODICAS; `--voz kit` es el unico
        # valor que decide que algo es bateria. Aplicar la voz a todas le habria
        # puesto marimba a un bombo.
        prog = (G.kit_por_nombre("Rock Kit")[1] if es_bat
                else G.voz_por_nombre("NylonGtr" if forzar_kit
                                      else (args.voz or "NylonGtr")))
        pre = F.build_prefix(base=F.PREFIJO_BASE, compases=n_comp,
                             nombre=destino, tipo="Bypass", pista=idx, voz=prog,
                             banco=F.BANK_DRUMS if es_bat else F.BANK_NORMAL)
        bl = G.a_bloques(notas, total, pre)
        bloques[idx] = (bl, prog, es_bat)
        esperadas[idx] = len(notas)
        # Se dice SIEMPRE por que se eligio kit o voz melodica. La version
        # anterior lo decidia en silencio, y el fallo de la marimba se paso
        # meses sin que nada en la salida diera una pista.
        print("  %-26s -> %-3s %4d notas  %2d bloques  %-9s %s"
              % (coincide[0][:26], destino, len(notas), len(bl),
                 "KIT" if es_bat else "melodica", por_que))

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
        # `inp` NO se cierra aqui: hace falta para releer despues de escribir.

    msgs, _ = P.parse_all(blob)
    dumps = [m for m in msgs if m.sub == P.SUB_DUMP]
    cab_msgs = [m for m in dumps if m.addr[2] == F.HEADER_TR]
    if not cab_msgs and dumps:
        # **Llegaron pistas pero no la cabecera: eso NO es un patron vacio.**
        #
        # Un patron vacio no devuelve absolutamente nada, ni un bloque. Si hay
        # bloques de pista y falta la cabecera, la captura perdio datos — y es
        # el modo de fallo mejor documentado del proyecto, porque el equipo
        # vuelca **las pistas primero y las 5 cabeceras al final**, que es justo
        # lo que se pierde si `collect` corta por silencio o si `MIDI CONTROL`
        # esta inundando la entrada de reloj.
        #
        # Aqui se preguntaba `if not cab_msgs` a secas. Con eso el patron se
        # daba por vacio, se arrancaba de la plantilla y `send_pattern` limpiaba
        # el destino: **se perdian el mezclador, los acordes por seccion, las
        # longitudes de las otras cinco secciones y todas las pistas previas**,
        # anunciandolo como "el patron esta vacio". Probado con un volcado de 4
        # bloques sin cabecera: conservaba 0 de 4 pistas.
        raise SystemExit(
            "Llegaron %d bloques de pista pero NO la cabecera del patron %d.\n"
            "La captura perdio datos; no se escribe nada porque escribir ahora "
            "borraria las pistas que si estan.\n"
            "Comprueba que MIDI CONTROL este en Off y vuelve a intentarlo."
            % (len(dumps), args.patron))
    if not cab_msgs:
        # Ningun bloque en absoluto: eso si es un patron vacio.
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
    # El denominador es el de la partitura, no `/4` clavado.
    cab_bytes[0] = F.set_time_signature(d, sig[0], sig[1])

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

    n = transfer.send_pattern(outp, salida, log=print)
    print("\nEscritos %d bloques en el patron %d, %s"
          % (n, args.patron, F.SECTIONS[args.seccion]))

    # **Releer, porque una escritura reportada como exitosa no prueba nada.**
    # El comentario del guardia prometia esta relectura y no existia: el puerto
    # de entrada se cerraba antes de escribir. La MOTU se traga escrituras con
    # el puerto a medias y el QY100 las ignora si esta reproduciendo; en los dos
    # casos `send_pattern` informa de exito.
    #
    # Se compara el NUMERO DE NOTAS decodificadas, no los bytes: el aparato
    # reserializa y devuelve 95 de 147 bytes distintos para los mismos datos.
    try:
        outp.send(mido.Message("sysex", data=P.bulk_mode(True)[1:-1]))
        time.sleep(0.3)
        blob2, _ = transfer.request(outp, inp, cab_addr, log=lambda *a: None)
    finally:
        try:
            outp.send(mido.Message("sysex", data=P.bulk_mode(False)[1:-1]))
            time.sleep(0.2)
        except Exception:
            pass
        inp.close()
        outp.close()

    m2, _ = P.parse_all(blob2)
    leidos = {}
    for m in (x for x in m2 if x.sub == P.SUB_DUMP and x.addr[2] != F.HEADER_TR):
        leidos.setdefault(m.addr[2], []).append(bytes(m.data))
    print("\nverificacion:")
    mal = 0
    for idx, (_bl, _prog, _eb) in sorted(bloques.items()):
        tr = F.track_byte(args.seccion, idx)
        if tr not in leidos:
            print("   %-3s NO ESTA en el aparato" % F.TRACK_NAMES[idx]); mal += 1
            continue
        try:
            notas, _ = F.decode_blocks(leidos[tr])
        except ValueError as e:
            print("   %-3s no decodifica: %s" % (F.TRACK_NAMES[idx], str(e)[:50]))
            mal += 1
            continue
        print("   %-3s %d notas" % (F.TRACK_NAMES[idx], len(notas)))
        if len(notas) != esperadas.get(idx):
            print("        ESPERABA %d — la escritura no llego entera"
                  % esperadas.get(idx))
            mal += 1
    if mal:
        raise SystemExit("\n%d pista(s) no llegaron. NO te fies de la escritura." % mal)
    print("   todas las pistas estan en el aparato")
