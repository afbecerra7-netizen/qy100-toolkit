"""Linea de comandos de qy100-syx."""

from __future__ import annotations

import argparse
import os
import sys
import time

import mido

from . import patternfmt as F
from . import protocol as P
from . import report, transfer

TARGETS = {
    "patterns": (P.Addr.PATTERN_ALL, "los 64 patrones de usuario"),
    "songs":    (P.Addr.SONG_ALL,    "las 20 canciones"),
    "setup":    (P.Addr.SETUP,       "los parametros de setup"),
    "all":      (P.Addr.ALL,         "absolutamente todo"),
    "info-songs":   (P.Addr.INFO_SONG,          "informacion de canciones"),
    "info-patterns": (P.Addr.INFO_PATTERN_1_32, "informacion de patrones 1-32"),
    "effects":  (P.Addr.EFFECT_ALL,  "los efectos de guitarra"),
}


def log(*a):
    print(*a, file=sys.stderr)


def build_parser():
    # Los argumentos de conexion se declaran en un padre compartido y se cuelgan
    # tanto del parser principal como de cada subcomando, para que funcionen en
    # cualquier orden: `syx --out X dump patterns` y `syx dump patterns --out X`.
    # SUPPRESS evita que el subcomando pise con None el valor puesto antes.
    conn = argparse.ArgumentParser(add_help=False)
    conn.add_argument("--in", dest="in_port", default=argparse.SUPPRESS,
                      help="puerto MIDI de entrada")
    conn.add_argument("--out", dest="out_port", default=argparse.SUPPRESS,
                      help="puerto MIDI de salida")
    conn.add_argument("--quiet-for", type=float, default=argparse.SUPPRESS,
                      help="segundos de silencio que dan por terminado un volcado")
    conn.add_argument("--timeout", type=float, default=argparse.SUPPRESS,
                      help="tope de espera total, en segundos")

    p = argparse.ArgumentParser(
        prog="syx", parents=[conn],
        description="Volcado y restauracion SysEx del Yamaha QY100.",
        epilog="Los datos de usuario del QY100 viven en SRAM con respaldo de pila "
               "(IC6): si la pila se agota se pierden. Volcar es un respaldo real.")
    p.add_argument("--list", action="store_true", help="listar puertos y salir")
    p.set_defaults(in_port=None, out_port=None, quiet_for=1.5, timeout=120.0)

    sub = p.add_subparsers(dest="cmd")

    d = sub.add_parser("dump", parents=[conn], help="pedir datos al QY100 y guardarlos")
    d.add_argument("target", choices=sorted(TARGETS) + ["pattern", "song"])
    d.add_argument("number", nargs="?", type=int,
                   help="numero de patron (1-64) o cancion (1-20)")
    d.add_argument("-o", "--output", help="archivo .syx de salida")
    d.add_argument("--track", type=int, default=0, help="pista (byte bajo de la direccion)")
    d.add_argument("--no-bulk-mode", action="store_true",
                   help="no mandar bulk mode ON antes de pedir (por defecto si se manda)")

    m = sub.add_parser("monitor", parents=[conn],
                       help="escuchar y guardar lo que mande el equipo")
    m.add_argument("-o", "--output", required=True)
    m.add_argument("--silence", type=float, default=5.0, dest="mon_quiet",
                   help="segundos de silencio que cierran la captura (por defecto 5)")

    i = sub.add_parser("inspect", help="analizar un .syx ya guardado")
    i.add_argument("file")
    i.add_argument("--unpack", action="store_true",
                   help="probar los desempaquetados de 7 bits sobre los datos")

    f = sub.add_parser("diff", help="comparar dos volcados")
    f.add_argument("a")
    f.add_argument("b")
    f.add_argument("--context", type=int, default=4)

    es = sub.add_parser("estilo", parents=[conn],
                        help="generar un estilo de usuario entero "
                             "(6 secciones x N pistas) en una sola escritura")
    es.add_argument("--patron", type=int, default=1, help="patron 1-64")
    es.add_argument("--semilla", type=int, default=0)
    es.add_argument("--pistas", help="indices 0-7 separados por coma; "
                                     "por defecto D1,D2,PC,BA,C1,C2")
    es.add_argument("--receta", default="base", choices=["base", "afrobeat", "enka"],
                    help="que tipo de estilo generar")
    es.add_argument("--compases",
                    help="compases por seccion (1-32): un numero para las seis, "
                         "o seis separados por coma en el orden Intro, MainA, "
                         "MainB, FillAB, FillBA, Ending. Por defecto 4,8,8,1,1,2 "
                         "— **solo MAIN A y MAIN B hacen loop**; las otras cuatro "
                         "suenan una vez, asi que un fill de 8 compases no es un "
                         "fill (manual p. 1211-1214). El panel solo llega a 8; el "
                         "equipo honra hasta 32")
    es.add_argument("--escribir", action="store_true")
    es.add_argument("--yes", action="store_true")
    es.set_defaults(func=cmd_estilo)

    an = sub.add_parser("andina", parents=[conn],
                        help="estilo de musica andina colombiana en 3/4")
    an.add_argument("genero", help="bambuco o pasillo")
    an.add_argument("--patron", type=int, default=1)
    an.add_argument("--bpm", type=float)
    an.add_argument("--escribir", action="store_true")
    an.add_argument("--yes", action="store_true")
    an.set_defaults(func=cmd_andina)

    fr = sub.add_parser("frases",
                        help="buscar entre las 4.285 frases preset "
                             "(categoria + beat + numero)")
    fr.add_argument("texto", nargs="?", help="parte del nombre, p.ej. Bossa")
    fr.add_argument("--categoria", help="Da Db Fa Fb PC Ba Bb Ga Gb GR KC KR PD BR SE")
    fr.add_argument("--beat", help="8, 16 o 3/4")
    fr.add_argument("--limite", type=int, default=40)
    fr.set_defaults(func=cmd_frases)

    ge = sub.add_parser("generar", parents=[conn],
                        help="generar una pista con los motores generativos "
                             "y escribirla como frase de usuario")
    ge.add_argument("motor", choices=["euclid", "markov"])
    ge.add_argument("--patron", type=int, default=1, help="patron 1-64")
    ge.add_argument("--seccion", type=int, default=1,
                    help="0=Intro 1=MainA 2=MainB 3=FillAB 4=FillBA 5=Ending")
    ge.add_argument("--pista", type=int, default=1, help="pista 0-7 de la seccion")
    ge.add_argument("--compases", type=int,
                    help="por defecto, los que declare la cabecera del patron")
    ge.add_argument("--semilla", type=int)
    ge.add_argument("--division", default="1/16")
    ge.add_argument("--velocity", type=int, default=100)
    # euclid
    ge.add_argument("--pulsos", type=int, default=5)
    ge.add_argument("--pasos", type=int, default=16)
    ge.add_argument("--nota", type=int, default=36)
    # markov
    ge.add_argument("--root", default="C")
    ge.add_argument("--escala", default="minor")
    ge.add_argument("--octava", type=int, default=4)
    ge.add_argument("--densidad", type=float, default=0.6)
    # ajustes de la frase; se pueden fijar aunque la pista no exista todavia
    ge.add_argument("--nombre", help="nombre de la frase, hasta 12 caracteres")
    ge.add_argument("--voz",
                    help="voz por NOMBRE (SquareLd) o por el numero de pantalla "
                         "(081). Busca nombres con `syx voces <texto>`")
    ge.add_argument("--bateria", action="store_true",
                    help="la voz es un kit de bateria (banco 127)")
    ge.add_argument("--tipo", choices=sorted(F.PHRASE_TYPES),
                    help="tipo de frase; Bypass suena literal")
    ge.add_argument("--fuente", help="acorde fuente, p.ej. Cm7")
    ge.add_argument("--escribir", action="store_true",
                    help="escribir en el equipo (por defecto solo previsualiza)")
    ge.add_argument("--yes", action="store_true")

    v = sub.add_parser("voces", help="buscar voces del banco por nombre")
    v.add_argument("texto", nargs="?", default="",
                   help="parte del nombre; sin argumento lista todas")

    s = sub.add_parser("send", parents=[conn],
                       help="reenviar un .syx al QY100 (ESCRIBE en el equipo)")
    s.add_argument("file")
    s.add_argument("--delay", type=float, default=0.02)
    s.add_argument("--bulk-mode", action="store_true",
                   help="envolver el envio en bulk mode on/off")
    s.add_argument("--yes", action="store_true", help="no pedir confirmacion")
    return p


def open_ports(args, need_in=True, need_out=True):
    inp = outp = None
    if need_out:
        outp = mido.open_output(transfer.resolve(args.out_port, mido.get_output_names(), "out"))
        log("Salida : %s" % outp.name)
    if need_in:
        inp = mido.open_input(transfer.resolve(args.in_port, mido.get_input_names(), "in"))
        log("Entrada: %s" % inp.name)
        # El QY100 emite 49 relojes por segundo sin parar cuando MIDI CONTROL
        # esta en Out o In/Out, y esa avalancha hace perder bloques SysEx.
        transfer.silenciar_reloj(inp, log)
    return inp, outp


def default_name(target, number=None):
    stamp = time.strftime("%Y%m%d-%H%M%S")
    tag = target if number is None else "%s%02d" % (target, number)
    return os.path.join("dumps", "%s-%s.syx" % (tag, stamp))


def cmd_dump(args):
    if args.target in ("pattern", "song"):
        if args.number is None:
            raise SystemExit("Indica el numero: `dump pattern 1`")
        if args.target == "pattern":
            addr = P.Addr.pattern(args.number - 1, args.track)
        else:
            addr = P.Addr.song(args.number - 1, args.track)
        what = P.addr_name(addr)
    else:
        addr, what = TARGETS[args.target]

    out = args.output or default_name(args.target, args.number)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)

    inp, outp = open_ports(args)
    try:
        # Verificado contra el equipo: sin bulk mode ON, el QY100 ignora las
        # peticiones de setup por completo, y en patrones devuelve menos bloques
        # de los que tiene. El manual lista `bulk mode on/off` como primera
        # entrada de la Tabla 1-9 pero no dice que sea requisito.
        if not args.no_bulk_mode:
            outp.send(mido.Message("sysex", data=P.bulk_mode(True)[1:-1]))
            time.sleep(0.3)
            log("Bulk mode ON")

        log("Volcando %s. Deja el QY100 encendido y quieto." % what)
        blob, n = transfer.request(outp, inp, addr, args.quiet_for, args.timeout, log)
    finally:
        # Bulk mode BLOQUEA el panel del QY100: si se queda encendido, el equipo
        # no responde a sus propios botones y parece averiado. Hay que apagarlo
        # siempre, tambien si algo falla a medias.
        try:
            if outp is not None and not args.no_bulk_mode:
                outp.send(mido.Message("sysex", data=P.bulk_mode(False)[1:-1]))
                time.sleep(0.2)
                log("Bulk mode OFF")
        except Exception:
            pass
        for p in (inp, outp):
            if p:
                p.close()

    # Si lo unico que volvio es nuestra propia peticion, el QY100 esta haciendo
    # eco (ECHO BACK=Thru) pero no respondiendo. Es un fallo distinto a "no
    # llego nada" y merece un mensaje distinto: el cable de ida SI funciona.
    if blob:
        msgs, _ = P.parse_all(blob)
        if msgs and all(m.sub == P.SUB_DUMP_REQ for m in msgs):
            log("")
            log("Solo volvio el eco de nuestra propia peticion (%d bytes)." % len(blob))
            log("Eso confirma que el cable de ida funciona: los bytes llegaron")
            log("al equipo. Pero no esta respondiendo. Revisa en el QY100:")
            log("  - ECHO BACK = Off        (pag. 128) — ahora esta en Thru")
            log("  - MIDI CONTROL = In/Out  (pag. 127) — con solo Out ignora lo que recibe")
            return 1

    if not blob:
        log("")
        log("No contesto nada. Cosas que comprobar:")
        log("  - HOST SELECT del QY100 en MIDI")
        log("  - cableado: QY100 OUT -> interfaz IN, interfaz OUT -> QY100 IN")
        log("  - MIDI CONTROL en Out o In/Out (pag. 127)")
        log("  - que no este en un modo que bloquee el bulk (prueba desde el modo song)")
        return 1

    with open(out, "wb") as fh:
        fh.write(blob)
    log("")
    log("Guardado %s: %d mensajes, %d bytes" % (out, n, len(blob)))
    log("")
    report.inspect(blob, log)
    return 0


def cmd_monitor(args):
    inp, _ = open_ports(args, need_out=False)
    try:
        log("Escuchando. Lanza el volcado desde el QY100 "
            "(modo utilidades -> trasvase en bloque, pag. 129).")
        log("Termina solo tras %.0f s de silencio. Ctrl-C para cortar." % args.mon_quiet)
        blob, n = transfer.collect(inp, args.mon_quiet, args.timeout, log)
    finally:
        inp.close()

    if not blob:
        log("No llego nada.")
        return 1
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "wb") as fh:
        fh.write(blob)
    log("Guardado %s: %d mensajes, %d bytes" % (args.output, n, len(blob)))
    log("")
    report.inspect(blob, log)
    return 0


def cmd_inspect(args):
    blob = open(args.file, "rb").read()
    msgs = report.inspect(blob, print)
    if args.unpack and msgs:
        data = report.payload_of(msgs)
        print("")
        print("Desempaquetado de 7 bits (el manual no precisa el metodo):")
        for name, fn in (("7-en-8 (como el firmware)", P.unpack_7in8),
                         ("nibbles", P.unpack_nibbles)):
            out = fn(data)
            zeros = out.count(0) * 100.0 / max(1, len(out))
            print("   %-26s %6d bytes, %.1f%% ceros" % (name, len(out), zeros))
        print("")
        print("Mucho relleno de ceros suele indicar el metodo correcto sobre datos")
        print("de secuenciador poco poblados. Confirmalo con `diff` de dos volcados")
        print("que se diferencien en una sola nota.")
    return 0


def cmd_diff(args):
    a = open(args.a, "rb").read()
    b = open(args.b, "rb").read()
    report.diff(a, b, os.path.basename(args.a), os.path.basename(args.b),
                args.context, print)
    return 0


def cmd_generar(args):
    """Genera una pista y opcionalmente la escribe como frase de usuario.

    Antes de generar nada se LEE el patron de destino, por dos razones: hace
    falta el prefijo de 26 bytes de esa pista (lleva datos que aun no sabemos
    construir) y la longitud declarada en la cabecera.
    """
    from . import generar as G
    from . import patternfmt as F

    tr = F.track_byte(args.seccion, args.pista)
    addr = P.Addr.pattern(args.patron - 1, tr)

    inp, outp = open_ports(args)
    try:
        outp.send(mido.Message("sysex", data=P.bulk_mode(True)[1:-1]))
        time.sleep(0.3)
        log("Leyendo el patron %d para tomar el prefijo y la longitud..." % args.patron)
        blob, _ = transfer.request(outp, inp, P.Addr.pattern(args.patron - 1, F.HEADER_TR),
                                   args.quiet_for, args.timeout, log)
    finally:
        try:
            outp.send(mido.Message("sysex", data=P.bulk_mode(False)[1:-1]))
            time.sleep(0.2)
        except Exception:
            pass
        for p in (inp, outp):
            if p:
                p.close()

    msgs, _ = P.parse_all(blob)
    dumps = [m for m in msgs if m.sub == P.SUB_DUMP]
    por_addr = {}
    for m in dumps:
        por_addr.setdefault(m.addr, []).append(m)

    cab = por_addr.get(P.Addr.pattern(args.patron - 1, F.HEADER_TR))
    if not cab:
        log("No llego la cabecera del patron. Con MIDI CONTROL encendido el")
        log("QY100 inunda la entrada de reloj y se pierden bloques: ponlo en Off.")
        return 1
    nombre, compases = F.decode_header(bytes(cab[0].data))
    n_comp = args.compases or compases[args.seccion]

    destino = por_addr.get(addr)
    if destino:
        base = F.unpack(bytes(destino[0].data))[:F.EVENT_STREAM_START]
    else:
        # La pista no existe. Se fabrica su prefijo a partir de otra pista REAL
        # del mismo patron —asi los bytes que aun no entendemos vienen del
        # equipo y no de una plantilla nuestra— y solo si el patron esta
        # completamente vacio se cae a `PREFIJO_BASE`.
        otras = [m for a, grupo in por_addr.items() if a[2] != F.HEADER_TR
                 for m in grupo[:1]]
        if otras:
            base = F.unpack(bytes(otras[0].data))[:F.EVENT_STREAM_START]
            log("La pista %s no existe: se crea copiando el prefijo de %s."
                % (F.describe_tr(tr), F.describe_tr(otras[0].addr[2])))
        else:
            base = F.PREFIJO_BASE
            log("El patron esta vacio: se crea %s desde la plantilla."
                % F.describe_tr(tr))

    # --voz acepta nombre o numero de pantalla; por dentro todo es base cero.
    prog, banco_kit = None, F.BANK_DRUMS
    if args.voz:
        from . import generar as G
        if args.voz.isdigit():
            prog = int(args.voz) - 1
        elif args.bateria:
            # con --bateria el nombre se busca entre los kits, y ademas el kit
            # decide su propio banco (127 normal, 126 los de efectos)
            try:
                banco_kit, prog = G.kit_por_nombre(args.voz)
            except ValueError as e:
                log(str(e))
                return 1
        else:
            try:
                prog = G.voz_por_nombre(args.voz)
            except ValueError:
                cands = G.buscar_voz(args.voz)
                log("No conozco la voz %r." % args.voz)
                if cands:
                    log("Se parecen: %s" % ", ".join(
                        "%03d %s" % (k + 1, v) for k, v in cands[:8]))
                return 1
        log("voz: programa %d %s" % (
            prog, "(kit de bateria)" if args.bateria
            else G.banco()["normales_por_programa"][prog]))

    prefijo = F.build_prefix(
        base=base, compases=n_comp, nombre=args.nombre, tipo=args.tipo,
        fuente=args.fuente, pista=args.pista,
        voz=prog,
        banco=(banco_kit if args.bateria else
               (F.BANK_NORMAL if args.voz else None)))

    if args.motor == "euclid":
        notas, total = G.euclidiano(n_comp, pulsos=args.pulsos, pasos=args.pasos,
                                    nota=args.nota, division=args.division,
                                    velocity=args.velocity, semilla=args.semilla)
    else:
        notas, total = G.melodia(n_comp, root=args.root, escala=args.escala,
                                 octava=args.octava, division=args.division,
                                 densidad=args.densidad, velocity=args.velocity,
                                 semilla=args.semilla)

    bloques = G.a_bloques(notas, total, prefijo)
    log("")
    log("Patron %d (%r), %s, %d compases" % (args.patron, nombre,
                                             F.describe_tr(tr), n_comp))
    log(G.resumen(notas, total))
    log("  -> %d bloque(s) de %d bytes" % (len(bloques), F.BLOCK_BYTES))

    if not args.escribir:
        log("")
        log("Previsualizacion. Anade --escribir para mandarlo al equipo.")
        return 0

    # Prevuelo: reconstruir los bloques que NO tocamos y exigir que salgan byte
    # a byte iguales a los que mando el equipo. Si nuestro armador no reproduce
    # lo que ya existe, no tenemos derecho a mandarle nada nuevo.
    #
    # Se comprueba contra todos los bloques del patron, no solo el de destino:
    # si la pista es nueva no hay bloque original con el que comparar, y en ese
    # caso sin esto el prevuelo no verificaria nada.
    malos = [m for m in dumps
             if m.raw is not None and P.build_dump(m.addr, m.data) != m.raw]
    if malos:
        log("PREVUELO FALLIDO: %d bloque(s) no se reproducen byte a byte "
            "(el primero, %s)." % (len(malos), P.addr_name(malos[0].addr)))
        log("No se escribe nada.")
        return 1
    log("Prevuelo OK: %d bloques del patron reconstruidos exactos." % len(dumps))

    if not args.yes:
        try:
            if input("Escribe 'si' para escribir en el QY100: ").strip().lower() \
                    not in ("si", "sí"):
                log("Cancelado.")
                return 1
        except EOFError:
            log("Cancelado (sin terminal; usa --yes si estas seguro).")
            return 1

    # Se manda el PATRON COMPLETO, con la pista de destino sustituida, no solo
    # los bloques nuevos. Verificado por las malas: enviar 2 bloques de una sola
    # pista dejo al QY100 congelado y sin responder ni al panel ni a MIDI, y hubo
    # que apagarlo. El envio del patron entero (7 bloques) si funciona. El equipo
    # limpia el destino al entrar en bulk mode y espera recibirlo todo; una pista
    # suelta lo deja a medias.
    # **Y hay que respetar el ORDEN en que los mando el equipo.** El QY100
    # vuelca las pistas primero y la cabecera al final; construir la salida como
    # "todo lo demas y luego la pista nueva" mete los bloques nuevos detras de la
    # cabecera y el equipo lo rechaza: deja el patron borrado. Por eso restaurar
    # un volcado tal cual si funciona. Se sustituye en el sitio.
    # El QY100 vuelca **las pistas primero y los 5 bloques de cabecera al
    # final**, y ese orden es parte del trato: mandarlo de otra forma deja el
    # patron borrado (comprobado dos veces, la segunda con una pista nueva que
    # se colaba detras de la cabecera). Por eso se separan los dos grupos en vez
    # de recorrer la lista tal cual.
    pistas, cab_msgs = [], []
    puesto = False
    for m in dumps:
        if m.addr[2] == F.HEADER_TR:
            cab_msgs.append(m)
        elif m.addr == addr:
            if not puesto:
                pistas.extend(P.build_dump(addr, b) for b in bloques)
                puesto = True
        else:
            pistas.append(m.raw)
    if not puesto:                       # pista nueva: va con las demas pistas
        pistas.extend(P.build_dump(addr, b) for b in bloques)

    # Registrar la pista en la cabecera. Sin esto el equipo no ve la seccion:
    # los bloques quedan escritos y se releen enteros, pero el panel la muestra
    # vacia. Son dos tablas de 8 ranuras por seccion y hay que poner las dos.
    reg = {}
    for m in dumps:
        if m.addr[2] == F.HEADER_TR:
            continue
        s, t = divmod(m.addr[2], F.TRACKS_PER_SECTION)
        reg.setdefault(s, set()).add(t)
    reg.setdefault(args.seccion, set()).add(args.pista)
    cab = F.set_registry([bytes(m.data) for m in cab_msgs],
                         {s: sorted(v) for s, v in reg.items()})
    # La voz que suena es la de PISTA, no la de la frase: si solo se escribiera
    # la de la frase, el mezclador podria estar imponiendo otra cosa. Se ponen
    # las dos de acuerdo. Ojo: el mezclador es por patron, no por seccion, asi
    # que esto afecta a la misma pista en las seis.
    if prog is not None:
        cab = F.set_mixer_voice(cab, args.pista, prog, bateria=bool(args.bateria))
    cabecera = [P.build_dump(m.addr, cab[k]) for k, m in enumerate(cab_msgs)]
    salida = pistas + cabecera

    _, outp = open_ports(args, need_in=False)
    try:
        n = transfer.send_pattern(outp, salida, log=log)
        log("Escritos %d bloques (patron completo, %s regenerada)."
            % (n, F.describe_tr(tr)))
    finally:
        outp.close()
    log("")
    log("Recuerda: el QY100 rearmoniza segun el TYPE de la pista (manual p. 58).")
    log("Para oir exactamente lo generado, pon esa pista en Bypass.")
    return 0


def cmd_estilo(args):
    """Genera un estilo de usuario entero: seis secciones por N pistas.

    La diferencia con `generar` no es de tamano sino de forma. `generar` lee el
    patron, sustituye **una** pista y lo reescribe entero; repetirlo 36 veces
    serian 36 transferencias completas, y cada una es una ocasion de que una
    transferencia a medias corrompa la contabilidad de memoria del equipo (ya
    paso una vez y hubo que limpiar y restaurar). Aqui se lee una vez, se arma
    todo en memoria y se escribe una vez.
    """
    from . import estilo as E
    from . import generar as G
    from . import patternfmt as F

    inp, outp = open_ports(args)
    try:
        outp.send(mido.Message("sysex", data=P.bulk_mode(True)[1:-1]))
        time.sleep(0.3)
        log("Leyendo el patron %d entero..." % args.patron)
        blob, _ = transfer.request(outp, inp,
                                   P.Addr.pattern(args.patron - 1, F.HEADER_TR),
                                   args.quiet_for, args.timeout, log)
    finally:
        try:
            outp.send(mido.Message("sysex", data=P.bulk_mode(False)[1:-1]))
            time.sleep(0.2)
        except Exception:
            pass
        for pt in (inp, outp):
            if pt:
                pt.close()

    msgs, _ = P.parse_all(blob)
    dumps = [m for m in msgs if m.sub == P.SUB_DUMP]
    por_addr = {}
    for m in dumps:
        por_addr.setdefault(m.addr, []).append(m)

    cab_addr = P.Addr.pattern(args.patron - 1, F.HEADER_TR)
    if cab_addr not in por_addr:
        # **Un patron vacio no devuelve nada**, ni siquiera la cabecera, asi que
        # "no contesto" no distingue entre patron vacio y fallo de comunicacion.
        # Se resuelve arrancando de `CABECERA_BASE` —captura literal de un patron
        # vacio— en vez de exigir que el usuario vaya al panel a grabar una nota.
        # Si de verdad hubiera un fallo de linea, la escritura posterior lo
        # delata: el prevuelo no tiene bloques que reconstruir y el read-back
        # queda como comprobacion.
        if not dumps:
            log("El patron %d esta vacio: se crea desde la plantilla."
                % args.patron)
            cab_msgs_iniciales = [
                type("M", (), {"addr": cab_addr, "data": list(b), "raw": None})()
                for b in F.CABECERA_BASE]
            for m in cab_msgs_iniciales:
                por_addr.setdefault(cab_addr, []).append(m)
                dumps.append(m)
        else:
            log("Llegaron bloques pero no la cabecera. Con MIDI CONTROL encendido")
            log("el QY100 inunda la entrada de reloj y se pierden bloques.")
            return 1
    cab_bytes = [bytes(m.data) for m in por_addr[cab_addr]]
    if args.compases:
        try:
            trozos = [int(x) for x in str(args.compases).split(",")]
        except ValueError:
            log("--compases: numeros separados por coma")
            return 1
        if len(trozos) == 1:
            trozos = trozos * 6
        if len(trozos) != 6 or not all(1 <= x <= F.MAX_MEASURES for x in trozos):
            log("--compases: uno o seis valores, cada uno entre 1 y %d"
                % F.MAX_MEASURES)
            return 1
        # encode_header solo toca el primer bloque, que es donde viven
        # nombre y longitudes.
        cab_bytes[0] = F.encode_header(cab_bytes[0], measures=trozos)
        for k, m in enumerate(por_addr[cab_addr]):
            m.data = list(cab_bytes[k])
    nombre, compases = F.decode_header(cab_bytes[0])
    log("Patron %d (%r), compases por seccion: %s"
        % (args.patron, nombre, " ".join(str(x) for x in compases)))

    # Prefijos: se prefiere una pista REAL del mismo indice —asi los bytes que
    # todavia no sabemos leer vienen del equipo y de una pista del mismo papel—,
    # luego cualquier otra, y solo si el patron esta vacio la plantilla.
    def base_para(idx):
        for (_a, _b, tr), grupo in por_addr.items():
            if tr != F.HEADER_TR and tr % F.TRACKS_PER_SECTION == idx:
                return F.unpack(bytes(grupo[0].data))[:F.EVENT_STREAM_START], "misma pista"
        for (_a, _b, tr), grupo in por_addr.items():
            if tr != F.HEADER_TR:
                return F.unpack(bytes(grupo[0].data))[:F.EVENT_STREAM_START], "otra pista"
        return F.PREFIJO_BASE, "plantilla"

    pedidas = ([int(x) for x in args.pistas.split(",")] if args.pistas else None)
    piezas = E.construir(compases, semilla=args.semilla, pistas=pedidas,
                         receta=args.receta)

    pistas_receta = {p[0]: p for p in E.RECETAS[args.receta]}
    nuevos, total_notas, total_bloques = {}, 0, 0
    for (s, idx) in sorted(piezas):
        notas, total = piezas[(s, idx)]
        _i, nom, papel, tipo, voz, es_bat = pistas_receta[idx]
        base, origen = base_para(idx)
        prog = (G.kit_por_nombre(voz)[1] if es_bat else G.voz_por_nombre(voz))
        prefijo = F.build_prefix(
            base=base, compases=compases[s], nombre=("%s%s" % (nom, s + 1))[:8],
            tipo=tipo, pista=idx, voz=prog,
            banco=(F.BANK_DRUMS if es_bat else F.BANK_NORMAL))
        bloques = G.a_bloques(notas, total, prefijo)
        nuevos[F.track_byte(s, idx)] = bloques
        total_notas += len(notas)
        total_bloques += len(bloques)

    log("")
    log("%-8s %s" % ("seccion", "  ".join("%-4s" % p[1]
                                          for p in E.RECETAS[args.receta])))
    for s, (nom_s, inten, que) in enumerate(E.SECCIONES):
        fila = []
        for idx, nom, *_ in E.RECETAS[args.receta]:
            n = piezas.get((s, idx))
            fila.append("%-4s" % (len(n[0]) if n else "-"))
        log("%-8s %s   %.0f%%  %s" % (nom_s, "  ".join(fila), inten * 100, que))
    log("")
    log("%d notas, %d bloques (~%d KB de los 128 KB del equipo)"
        % (total_notas, total_bloques, total_bloques * F.BLOCK_BYTES / 1024.0))

    if not args.escribir:
        log("")
        log("Previsualizacion. Anade --escribir para mandarlo al equipo.")
        return 0

    malos = [m for m in dumps
             if m.raw is not None and P.build_dump(m.addr, m.data) != m.raw]
    if malos:
        log("PREVUELO FALLIDO: %d bloque(s) no se reproducen byte a byte. "
            "No se escribe nada." % len(malos))
        return 1
    log("Prevuelo OK: %d bloques reconstruidos exactos." % len(dumps))

    if not args.yes:
        try:
            if input("Escribe 'si' para escribir el estilo: ").strip().lower() \
                    not in ("si", "s\u00ed"):
                log("Cancelado.")
                return 1
        except EOFError:
            log("Cancelado (sin terminal; usa --yes si estas seguro).")
            return 1

    # Pistas primero y las 5 cabeceras al final: ese orden es parte del trato con
    # el equipo. Mandarlo de otra forma deja el patron borrado.
    pistas_out, cab_msgs, vistos = [], [], set()
    for m in dumps:
        tr = m.addr[2]
        if tr == F.HEADER_TR:
            cab_msgs.append(m)
        elif tr in nuevos:
            if tr not in vistos:
                vistos.add(tr)
                pistas_out.extend(P.build_dump(m.addr, b) for b in nuevos[tr])
        elif m.raw is not None:
            pistas_out.append(m.raw)
    for tr, bloques in sorted(nuevos.items()):
        if tr not in vistos:
            addr = P.Addr.pattern(args.patron - 1, tr)
            pistas_out.extend(P.build_dump(addr, b) for b in bloques)

    # Las dos tablas del registro, o el panel muestra las secciones vacias aunque
    # los datos esten escritos y se relean enteros.
    reg = {}
    for m in dumps:
        if m.addr[2] != F.HEADER_TR:
            s, t = divmod(m.addr[2], F.TRACKS_PER_SECTION)
            reg.setdefault(s, set()).add(t)
    for (s, idx) in piezas:
        reg.setdefault(s, set()).add(idx)
    cab = F.set_registry([bytes(m.data) for m in cab_msgs],
                         {s: sorted(v) for s, v in reg.items()})
    # El mezclador es POR PATRON, no por seccion: una voz por indice de pista.
    for idx, _nom, _papel, _tipo, voz, es_bat in E.RECETAS[args.receta]:
        if pedidas is not None and idx not in pedidas:
            continue
        prog = (G.kit_por_nombre(voz)[1] if es_bat else G.voz_por_nombre(voz))
        cab = F.set_mixer_voice(cab, idx, prog, bateria=es_bat)
    salida = pistas_out + [P.build_dump(m.addr, cab[k])
                           for k, m in enumerate(cab_msgs)]

    _, outp = open_ports(args, need_in=False)
    try:
        n = transfer.send_pattern(outp, salida, log=log)
        log("Escritos %d bloques en una sola transferencia." % n)
    finally:
        outp.close()
    return 0


def cmd_frases(args):
    """Busca entre las 4.285 frases preset por nombre, estilo o categoria.

    Devuelve los **tres campos con los que se direcciona una frase** —categoria,
    beat y numero (manual p. 54)—, que son justo los que hay que escribir en la
    cabecera del patron para referenciarla: la categoria y el beat van en la
    bandera del registro y el numero, menos uno, en la segunda tabla.

    El sufijo del nombre dice para que seccion es: `-I` intro, `-a` Main A,
    `-b` Main B, `-c` fill AB, `-d` fill BA, `-E` ending.
    """
    import json
    import os
    import re

    ruta = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "frases.json")
    d = json.load(open(ruta))
    cats = d["categorias"]

    texto = (args.texto or "").lower()
    quiere_cat = args.categoria
    quiere_beat = args.beat

    hits = []
    for cat in sorted(cats):
        if quiere_cat and cat.lower() != quiere_cat.lower():
            continue
        for beat, frases in cats[cat]["beats"].items():
            if quiere_beat and quiere_beat.lower() not in beat.lower():
                continue
            for num, nombre in sorted(frases.items()):
                if texto and texto not in nombre.lower():
                    continue
                hits.append((cat, beat, num, nombre, cats[cat]["nombre"]))

    if not hits:
        log("Nada. Categorias: %s" % " ".join(sorted(cats)))
        return 1

    # Agrupar por estilo hace la salida util: una frase suelta no dice nada, y
    # ver las seis secciones del mismo estilo juntas es lo que permite montar un
    # patron completo con material coherente.
    log("%-4s %-9s %-5s %-9s  %s" % ("cat", "beat", "num", "nombre", "categoria"))
    log("-" * 62)
    for cat, beat, num, nombre, desc in hits[:args.limite]:
        log("%-4s %-9s %-5s %-9s  %s" % (cat, beat, num, nombre, desc))
    if len(hits) > args.limite:
        log("... y %d mas (usa --limite)" % (len(hits) - args.limite))
    log("")
    log("%d frases de 4285" % len(hits))

    # El desglose por seccion solo tiene sentido cuando se busca un estilo.
    if texto:
        SUF = [("-I", "Intro"), ("-a", "Main A"), ("-b", "Main B"),
               ("-c", "Fill AB"), ("-d", "Fill BA"), ("-E", "Ending")]
        falta = [n for s, n in SUF
                 if not any(h[3].rstrip().endswith(s) for h in hits)]
        if falta:
            log("Secciones sin frase para esta busqueda: %s" % ", ".join(falta))
        else:
            log("Juego completo: las seis secciones tienen frase.")
    return 0


def cmd_andina(args):
    """Escribe un estilo de musica andina colombiana: seis secciones, una escritura.

    Sigue las tres reglas que `cmd_estilo` aprendio por las malas y que los
    primeros `bambuco.py`/`pasillo.py` incumplian: **leer el patron de destino
    antes de escribir**, mandar las seis secciones **de una vez**, y usar
    `set_registry` en vez de poner `0xF8` a mano — que es lo que preserva las
    referencias a frases de fabrica que hubiera en el patron.
    """
    from . import andina as A
    from . import generar as G
    from . import patternfmt as F

    if args.genero not in A.GENEROS:
        log("generos: %s" % " ".join(sorted(A.GENEROS)))
        return 1
    g = A.GENEROS[args.genero]()
    bpm = args.bpm or g.bpm

    inp, outp = open_ports(args)
    try:
        outp.send(mido.Message("sysex", data=P.bulk_mode(True)[1:-1]))
        time.sleep(0.3)
        log("Leyendo el patron %d..." % args.patron)
        blob, _ = transfer.request(outp, inp,
                                   P.Addr.pattern(args.patron - 1, F.HEADER_TR),
                                   args.quiet_for, args.timeout, log)
    finally:
        try:
            outp.send(mido.Message("sysex", data=P.bulk_mode(False)[1:-1]))
            time.sleep(0.2)
        except Exception:
            pass
        for pt in (inp, outp):
            if pt:
                pt.close()

    msgs, _ = P.parse_all(blob)
    dumps = [m for m in msgs if m.sub == P.SUB_DUMP]
    cab_addr = P.Addr.pattern(args.patron - 1, F.HEADER_TR)
    cab_msgs = [m for m in dumps if m.addr[2] == F.HEADER_TR]
    if not cab_msgs:
        # Un patron vacio no devuelve nada, ni la cabecera. Se arranca de la
        # plantilla en vez de exigir grabar una nota desde el panel.
        log("El patron %d esta vacio: se crea desde la plantilla." % args.patron)
        cab_bytes = list(F.CABECERA_BASE)
        previas = []
    else:
        cab_bytes = [bytes(m.data) for m in cab_msgs]
        previas = [m for m in dumps if m.addr[2] != F.HEADER_TR]

    compases = A.compases_por_seccion()
    cab_bytes[0] = F.encode_header(cab_bytes[0], name=g.nombre, measures=compases)
    cab_bytes[0] = F.set_tempo(cab_bytes[0], bpm)
    cab_bytes[0] = F.set_time_signature(cab_bytes[0], g.beats, 4)

    log("")
    log("%s — %.0f bpm, %d/4, progresion %s"
        % (g.nombre, bpm, g.beats, " ".join(p[0] for p in g.progresion)))
    log("")

    nuevos, total_notas, total_bloques = {}, 0, 0
    for s, (nom_s, intensidad, comp) in enumerate(A.SECCIONES):
        piezas = g.construir(s, comp, intensidad)
        total = g.total(comp)
        fila = []
        for idx, nom, _papel, voz, es_bat, _m in g.pistas:
            notas = sorted((n for n in piezas[idx] if n.time < total),
                           key=lambda n: n.time)
            prog = (G.kit_por_nombre(voz)[1] if es_bat else G.voz_por_nombre(voz))
            pre = F.build_prefix(base=F.PREFIJO_BASE, compases=comp,
                                 nombre="%s%d" % (nom, s + 1), tipo="Bypass",
                                 pista=idx, voz=prog,
                                 banco=F.BANK_DRUMS if es_bat else F.BANK_NORMAL)
            bl = G.a_bloques(notas, total, pre)
            nuevos[F.track_byte(s, idx)] = bl
            total_notas += len(notas)
            total_bloques += len(bl)
            fila.append("%s:%d" % (nom, len(notas)))
        log("  %-8s %2d cp   %s" % (nom_s, comp, "  ".join(fila)))

    log("")
    log("%d notas, %d bloques (~%.1f KB)"
        % (total_notas, total_bloques + 5, (total_bloques + 5) * 128 / 1024.0))

    if not args.escribir:
        log("")
        log("Previsualizacion. Anade --escribir.")
        return 0

    if not args.yes:
        try:
            if input("Escribe 'si' para escribir: ").strip().lower() not in ("si", "s\u00ed"):
                log("Cancelado.")
                return 1
        except EOFError:
            log("Cancelado (sin terminal; usa --yes).")
            return 1

    # Pistas primero, cabecera al final. Las pistas previas que no regeneramos
    # se reenvian intactas: el patron va entero o no va.
    salida, vistos = [], set()
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

    reg = {}
    for m in previas:
        s, t = divmod(m.addr[2], F.TRACKS_PER_SECTION)
        reg.setdefault(s, set()).add(t)
    for tr in nuevos:
        s, t = divmod(tr, F.TRACKS_PER_SECTION)
        reg.setdefault(s, set()).add(t)
    cab_f = F.set_registry(cab_bytes, {s: sorted(v) for s, v in reg.items()})
    for idx, _n, _p, voz, es_bat, _m in g.pistas:
        prog = (G.kit_por_nombre(voz)[1] if es_bat else G.voz_por_nombre(voz))
        cab_f = F.set_mixer_voice(cab_f, idx, prog, bateria=es_bat)
    salida += [P.build_dump(cab_addr, b) for b in cab_f]

    _, outp = open_ports(args, need_in=False)
    try:
        n = transfer.send_pattern(outp, salida, log=log)
        log("Escritos %d bloques en una sola transferencia." % n)
    finally:
        outp.close()
    return 0


def cmd_voces(args):
    from . import generar as G
    b = G.banco()
    hits = G.buscar_voz(args.texto) if args.texto else list(
        enumerate(b["normales_por_programa"]))
    for k, v in hits:
        print("  %03d  %s" % (k + 1, v))
    print("\n%d de %d voces normales" % (len(hits), len(b["normales_por_programa"])))
    if not args.texto:
        print("\nKits de bateria (orden de la ROM; su numero de programa NO esta")
        print("verificado, ver el aviso en voces.json):")
        for k, v in enumerate(b["kits_en_orden_de_rom"]):
            print("  idx %2d  %s" % (k, v))
    return 0


def cmd_send(args):
    blob = open(args.file, "rb").read()
    msgs, errs = P.parse_all(blob)
    dest = sorted({P.addr_name(m.addr) for m in msgs})

    log("Se va a ESCRIBIR en el QY100:")
    log("  archivo : %s (%d mensajes, %d bytes)" % (args.file, len(msgs), len(blob)))
    log("  destino : %s" % ", ".join(dest[:6]) + (" ..." if len(dest) > 6 else ""))
    if errs:
        log("  AVISO   : %d bloques ilegibles, se mandaran igual" % len(errs))
    danger = [m for m in msgs if m.addr in P.DESTRUCTIVE]
    if danger:
        log("  PELIGRO : el archivo trae %d comandos de BORRADO" % len(danger))
    log("  Esto sobrescribe los datos de usuario que haya en esas posiciones.")

    if not args.yes:
        try:
            if input("Escribe 'si' para continuar: ").strip().lower() not in ("si", "sí"):
                log("Cancelado.")
                return 1
        except EOFError:
            log("Cancelado (sin terminal para confirmar; usa --yes si estas seguro).")
            return 1

    _, outp = open_ports(args, need_in=False)
    try:
        if args.bulk_mode:
            outp.send(mido.Message("sysex", data=P.bulk_mode(True)[1:-1]))
            time.sleep(0.1)
        n = transfer.send_blob(outp, blob, args.delay, log)
        if args.bulk_mode:
            time.sleep(0.1)
            outp.send(mido.Message("sysex", data=P.bulk_mode(False)[1:-1]))
        log("Enviados %d mensajes." % n)
    finally:
        outp.close()
    return 0


def main(argv=None):
    args = build_parser().parse_args(argv)

    if args.list:
        print("Entradas:")
        for n in mido.get_input_names() or ["  (ninguna)"]:
            print("   ", n)
        print("Salidas:")
        for n in mido.get_output_names() or ["  (ninguna)"]:
            print("   ", n)
        return 0

    if not args.cmd:
        build_parser().print_help()
        return 1

    return {"dump": cmd_dump, "monitor": cmd_monitor, "inspect": cmd_inspect,
            "diff": cmd_diff, "send": cmd_send, "generar": cmd_generar,
            "estilo": cmd_estilo, "frases": cmd_frases, "andina": cmd_andina,
            "voces": cmd_voces}[args.cmd](args)
