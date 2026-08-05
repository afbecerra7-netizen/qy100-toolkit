"""Linea de comandos y bucle principal."""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time

import mido

from .clock import PPQN, InternalClock
from .control import ControlMap
from .engine import Engine
from .midiio import (ConsoleOutput, RenderOutput, list_ports, open_input,
                     open_output)
from .scales import note_name, parse_note

LOCAL_CONTROL_CC = 122
DEFAULT_CONFIG = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "config.json")


def strip_comments(raw):
    """Quita comentarios // respetando lo que este dentro de cadenas."""
    out = []
    i, n, in_str = 0, len(raw), False
    while i < n:
        c = raw[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(raw[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
        elif c == '"':
            in_str = True
            out.append(c)
            i += 1
        elif c == "/" and i + 1 < n and raw[i + 1] == "/":
            while i < n and raw[i] != "\n":
                i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def load_config(path):
    """JSON permitiendo comentarios de linea con // para que se pueda anotar."""
    with open(path, "r") as fh:
        raw = fh.read()
    try:
        return json.loads(strip_comments(raw))
    except ValueError as exc:
        raise SystemExit("config invalida (%s): %s" % (path, exc))


def build_parser():
    p = argparse.ArgumentParser(
        prog="qy100-arp",
        description="Arpegiador y secuenciador generativo externo para el Yamaha QY100.")
    p.add_argument("--list", action="store_true",
                   help="listar puertos MIDI y salir")
    p.add_argument("--config", default=DEFAULT_CONFIG,
                   help="archivo de configuracion (por defecto: config.json)")
    p.add_argument("--in", dest="in_port", default=None,
                   help="puerto MIDI de entrada (coincidencia parcial)")
    p.add_argument("--clock-in", dest="clock_port", default=None,
                   help="puerto MIDI aparte del que tomar el reloj. Para cuando "
                        "las notas llegan del controlador por un puerto y el "
                        "reloj del QY100 por otro, por ejemplo a traves de una "
                        "caja thru. Sin esto, ambos se leen de --in.")
    p.add_argument("--out", dest="out_port", default=None,
                   help="puerto MIDI de salida (coincidencia parcial)")
    p.add_argument("--virtual", action="store_true",
                   help="crear puertos virtuales CoreMIDI en vez de usar el hardware")
    p.add_argument("--sim", action="store_true",
                   help="reloj interno y salida por consola (sin hardware)")
    p.add_argument("--master", action="store_true",
                   help="ser el maestro de reloj: transmite MIDI Clock y Start/Stop. "
                        "Para cuando la caja va entre el controlador y el QY100 y "
                        "no hay retorno del MIDI OUT. Requiere MIDI SYNC=External "
                        "y MIDI CONTROL=In o In/Out en el QY100.")
    p.add_argument("--bpm", type=float, default=120.0,
                   help="tempo del reloj interno (solo con --sim o --render)")
    p.add_argument("--render", metavar="ARCHIVO.mid", default=None,
                   help="renderizar sin tiempo real a un archivo MIDI y salir")
    p.add_argument("--bars", type=int, default=8,
                   help="compases a renderizar (por defecto 8)")
    p.add_argument("--notes", default=None,
                   help="notas retenidas para el arpegiador en --sim/--render, "
                        "ej: 'C3 Eb3 G3 Bb3'")
    p.add_argument("--local-off", dest="local_off", action="store_true",
                   help="mandar Local Control OFF al arrancar (se restaura al salir)")
    p.add_argument("--local-on", action="store_true",
                   help="mandar solo Local Control ON y salir (para recuperar el teclado)")
    p.add_argument("--monitor", action="store_true",
                   help="no arpegiar nada: solo imprimir todo lo que entre por "
                        "--in. Sirve para averiguar que transmite de verdad un "
                        "aparato, en vez de fiarse de su manual.")
    p.add_argument("--quiet", action="store_true", help="menos mensajes")
    return p


def run_monitor(args, log):
    """Imprime el MIDI entrante tal cual llega."""
    inport = open_input(args.in_port, virtual=args.virtual)
    if inport is None:
        raise SystemExit("Indica el puerto con --in, o usa --virtual.")
    log("Escuchando %s. Ctrl-C para salir." % inport.name)
    log("")

    counts = {}
    clocks = 0
    last_clock = None
    channels = set()
    notes_seen = set()

    try:
        while True:
            for msg in inport.iter_pending():
                t = msg.type
                counts[t] = counts.get(t, 0) + 1

                # El reloj llega 24 veces por negra: resumirlo, no inundar.
                if t == "clock":
                    clocks += 1
                    if clocks % 96 == 0:
                        now = time.monotonic()
                        if last_clock is not None:
                            bpm = 96 / (now - last_clock) / 24 * 60
                            print("   [reloj] %d ticks, ~%.1f BPM" % (clocks, bpm), flush=True)
                        last_clock = now
                    continue

                if hasattr(msg, "channel"):
                    channels.add(msg.channel + 1)

                if t in ("note_on", "note_off"):
                    notes_seen.add(msg.note)
                    print("ch%-3d %-9s %-4s (nota %3d)  vel %d"
                          % (msg.channel + 1, t, note_name(msg.note),
                             msg.note, msg.velocity), flush=True)
                elif t == "control_change":
                    print("ch%-3d CC %-3d = %d" % (msg.channel + 1, msg.control, msg.value), flush=True)
                elif t == "songpos":
                    print("     song position -> %d (compas ~%d)"
                          % (msg.pos, msg.pos // 16 + 1), flush=True)
                elif t in ("start", "stop", "continue"):
                    print("     TRANSPORTE: %s" % t.upper(), flush=True)
                elif t == "sysex":
                    print("     sysex, %d bytes: %s"
                          % (len(msg.data), bytes(msg.data[:12]).hex(" ")), flush=True)
                else:
                    print("     %s" % msg, flush=True)
            time.sleep(0.0005)
    except KeyboardInterrupt:
        pass
    finally:
        inport.close()

    log("")
    log("── resumen ──")
    for t in sorted(counts, key=lambda k: -counts[k]):
        log("  %-16s %d" % (t, counts[t]))
    if channels:
        log("  canales vistos : %s" % ", ".join(str(c) for c in sorted(channels)))
    if notes_seen:
        lo, hi = min(notes_seen), max(notes_seen)
        log("  rango de notas : %d (%s) a %d (%s)"
            % (lo, note_name(lo), hi, note_name(hi)))
    return 0


def send_local_control(out, on, channels=(0,)):
    value = 127 if on else 0
    for ch in channels:
        out.send(mido.Message("control_change", channel=ch,
                              control=LOCAL_CONTROL_CC, value=value))


def describe(engine, log):
    a = engine.arp
    log("Arpegiador : %s  %s  %d oct  gate %.2f  canal %d%s"
        % (a.pattern, a.division, a.octaves, a.gate, a.channel + 1,
           "  [latch]" if a.latch else ""))
    for lane in engine.lanes:
        log("Euclid     : %s" % lane.describe())
    if engine.melody:
        m = engine.melody
        log("Melodia    : %s %s  densidad %.2f  canal %d%s"
            % (m.scale, m.division, m.density, m.channel + 1,
               "  [sigue teclado]" if m.follow_held else ""))


def feed_notes(engine, spec, log):
    notes = [parse_note(tok) for tok in spec.split()]
    for n in notes:
        engine.note_on(n, 100)
    log("Notas retenidas: %s" % " ".join(note_name(n) for n in notes))


def run_render(cfg, args, log):
    engine = Engine(cfg, None, log=log)
    out = RenderOutput(engine)
    engine.out = out
    describe(engine, log)
    if args.notes:
        feed_notes(engine, args.notes, log)

    engine.start(0)
    total = args.bars * 4 * PPQN
    for _ in range(total):
        engine.on_tick()
    engine.all_notes_off()

    n = out.save(args.render, bpm=args.bpm)
    log("Escrito %s: %d eventos, %d compases a %.1f BPM"
        % (args.render, n, args.bars, args.bpm))


def run_live(cfg, args, log):
    use_console = args.sim and not args.virtual

    inport = None
    outport = None
    clockport = None
    engine = None
    send_clock = False
    try:
        if use_console:
            engine = Engine(cfg, None, log=log)
            engine.out = ConsoleOutput(engine)
            outport = engine.out
        else:
            outport = open_output(args.out_port, virtual=args.virtual)
            engine = Engine(cfg, outport, log=log)
            log("Salida  : %s" % outport.name)

        if args.virtual:
            inport = open_input(virtual=True)
        elif args.in_port:
            inport = open_input(args.in_port)
        if inport is not None:
            log("Entrada : %s" % inport.name)

        if args.clock_port:
            clockport = open_input(args.clock_port)
            log("Reloj   : %s" % clockport.name)

        describe(engine, log)

        # El reloj lo generamos nosotros si nos lo piden explicitamente (--master),
        # si estamos simulando, o si no hay ningun puerto del que recibirlo.
        internal = args.master or args.sim or (inport is None and clockport is None)
        clock = InternalClock(args.bpm) if internal else None
        # Solo transmitimos reloj hacia afuera en modo maestro y con puerto real.
        send_clock = args.master and not use_console

        if args.local_off and not use_console:
            send_local_control(outport, False)
            log("Local Control OFF enviado (canal 1)")

        out_channels = engine.output_channels()
        in_filter = cfg.get("input_channel")   # None = omni
        if in_filter is not None:
            in_filter = int(in_filter) - 1

        passthrough = bool(cfg.get("passthrough", True))

        controls = ControlMap(cfg.get("midi_control"), engine, log)
        if controls.enabled and controls.map:
            log("Control por CC:")
            for cc in sorted(controls.map):
                log("   CC%-4d -> %s" % (cc, controls.map[cc]))

        if internal:
            if args.notes:
                feed_notes(engine, args.notes, log)
            clock.start()
            if send_clock:
                outport.send(mido.Message("start"))
            engine.start(0)
            if args.master:
                log("MAESTRO de reloj a %.1f BPM. Ctrl-C para salir." % args.bpm)
                log("  (QY100: MIDI SYNC=External, MIDI CONTROL=In o In/Out)")
            else:
                log("Reloj interno a %.1f BPM. Ctrl-C para salir." % args.bpm)
        else:
            log("Esperando MIDI Clock del QY100. Ctrl-C para salir.")
            log("  (QY100: MIDI SYNC=Internal, MIDI CONTROL=Out o In/Out, ECHO BACK=Off)")

        # Con --clock-in, el puerto de notas debe ignorar el transporte aunque
        # lo lleve: el reloj bueno es el del otro puerto.
        notes_ignore_transport = internal or clockport is not None

        while True:
            if clockport is not None:
                for msg in clockport.iter_pending():
                    handle_transport(engine, msg)
            if inport is not None:
                for msg in inport.iter_pending():
                    handle_message(engine, msg, out_channels, in_filter,
                                   notes_ignore_transport,
                                   outport if passthrough else None,
                                   controls)
            if clock is not None:
                for _ in range(clock.due()):
                    if send_clock:
                        outport.send(mido.Message("clock"))
                    engine.on_tick()
            time.sleep(0.0005)

    except KeyboardInterrupt:
        log("\nSaliendo.")
    finally:
        try:
            if engine is not None:
                engine.all_notes_off()
            if send_clock:
                outport.send(mido.Message("stop"))
            if args.local_off and not use_console:
                send_local_control(outport, True)
                log("Local Control ON restaurado")
        except Exception:
            pass
        for port in (inport, clockport, outport):
            if port is not None and hasattr(port, "close"):
                port.close()


# Mensajes del controlador que dejamos pasar tal cual hacia el QY100, para que
# sus ruedas, pedales y knobs sigan funcionando aunque las notas las capturemos.
PASSTHROUGH_TYPES = ("control_change", "pitchwheel", "program_change",
                     "aftertouch", "polytouch")


def handle_transport(engine, msg) -> bool:
    """Reloj y transporte. True si el mensaje era de ese tipo y ya se atendio."""
    t = msg.type
    if t == "clock":
        engine.on_tick()
    elif t == "start":
        engine.start(0)
    elif t == "continue":
        engine.cont()
    elif t == "stop":
        engine.stop()
    elif t == "songpos":
        engine.set_position(msg.pos)
    else:
        return False
    return True


def handle_message(engine, msg, out_channels, in_filter, internal,
                   passthrough_out=None, controls=None):
    t = msg.type

    # `internal` cubre dos casos: reloj propio, o reloj que llega por un puerto
    # aparte (--clock-in). En ambos hay que ignorar el transporte de este puerto,
    # o se contarian los ticks dos veces.
    if not internal and handle_transport(engine, msg):
        return

    if t in ("note_on", "note_off"):
        if in_filter is not None and msg.channel != in_filter:
            return

        if t == "note_on" and msg.velocity > 0:
            # Guarda anti-realimentacion. NO se puede filtrar por canal: lo normal
            # es que el controlador transmita en el mismo canal en que arpegiamos,
            # y hacerlo dejaria al arpegiador sin entrada. En cambio se descarta
            # solo la nota exacta que ya estamos sonando en ese canal, que es lo
            # que vuelve si ECHO BACK quedo encendido.
            # Se aplica solo al note_on: bloquear un note_off dejaria notas
            # trabadas en el arpegiador, que es peor que dejar pasar un eco.
            if engine.is_sounding(msg.channel, msg.note):
                return
            engine.note_on(msg.note, msg.velocity)
        else:
            engine.note_off(msg.note)
        return

    # Un CC mapeado a un parametro se consume aqui y no viaja al QY100.
    if t == "control_change" and controls is not None and controls.apply(msg):
        return

    # El passthrough NO se filtra por canal de salida: es normal que la rueda de
    # modulacion del controlador viaje por el mismo canal en que arpegiamos, y
    # descartarla ahi dejaria al controlador sin knobs.
    if passthrough_out is not None and t in PASSTHROUGH_TYPES:
        if in_filter is None or msg.channel == in_filter:
            passthrough_out.send(msg)


def _on_sigterm(signum, frame):
    """SIGTERM debe limpiar igual que Ctrl-C.

    Sin esto, matar el proceso deja notas sonando en los sintes conectados
    aguas abajo: el `finally` que las apaga nunca llega a correr.
    """
    raise KeyboardInterrupt


def main(argv=None):
    signal.signal(signal.SIGTERM, _on_sigterm)
    args = build_parser().parse_args(argv)
    log = (lambda *a: None) if args.quiet else (
        lambda *a: print(*a, file=sys.stderr))

    if args.list:
        list_ports()
        return 0

    if args.monitor:
        return run_monitor(args, log)

    if args.local_on:
        out = open_output(args.out_port, virtual=args.virtual)
        send_local_control(out, True)
        out.close()
        log("Local Control ON enviado.")
        return 0

    cfg = load_config(args.config)

    if args.render:
        run_render(cfg, args, log)
    else:
        run_live(cfg, args, log)
    return 0
