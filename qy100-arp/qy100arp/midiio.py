"""Puertos MIDI y destinos alternativos (consola, archivo .mid)."""

from __future__ import annotations

import sys

import mido


def list_ports() -> None:
    print("Entradas MIDI:")
    for n in mido.get_input_names() or ["  (ninguna)"]:
        print("   ", n)
    print("Salidas MIDI:")
    for n in mido.get_output_names() or ["  (ninguna)"]:
        print("   ", n)


def _resolve(name, available, kind):
    """Coincidencia parcial, sin distinguir mayusculas."""
    if name is None:
        return None
    matches = [p for p in available if name.lower() in p.lower()]
    if not matches:
        raise SystemExit(
            "No encuentro el puerto de %s %r.\nDisponibles: %s"
            % (kind, name, ", ".join(available) or "(ninguno)"))
    return matches[0]


def open_output(name=None, virtual=False):
    if virtual:
        return mido.open_output("QY100 Arp OUT", virtual=True)
    resolved = _resolve(name, mido.get_output_names(), "salida")
    return mido.open_output(resolved)


def open_input(name=None, virtual=False):
    if virtual:
        return mido.open_input("QY100 Arp IN", virtual=True)
    if name is None:
        return None
    resolved = _resolve(name, mido.get_input_names(), "entrada")
    return mido.open_input(resolved)


class ConsoleOutput:
    """Imprime en vez de enviar. Para ver que hace el motor sin equipo."""

    def __init__(self, engine_ref=None, stream=None):
        self.engine_ref = engine_ref
        self.stream = stream or sys.stdout

    def send(self, msg):
        from .scales import note_name
        tick = self.engine_ref.tick if self.engine_ref else 0
        if msg.type == "note_on":
            self.stream.write("t%-6d ch%-2d  ON  %-4s vel %d\n"
                              % (tick, msg.channel + 1, note_name(msg.note), msg.velocity))
        elif msg.type == "note_off":
            self.stream.write("t%-6d ch%-2d  off %-4s\n"
                              % (tick, msg.channel + 1, note_name(msg.note)))

    def close(self):
        pass


class RenderOutput:
    """Acumula mensajes con su tick para volcarlos a un archivo .mid.

    La resolucion interna del motor ya es 24 PPQN, la misma que el MIDI Clock,
    asi que el archivo sale con ticks_per_beat=24 y no hay reescalado.
    """

    def __init__(self, engine_ref):
        self.engine_ref = engine_ref
        self.events = []

    def send(self, msg):
        self.events.append((self.engine_ref.tick, msg))

    def save(self, path, bpm=120.0):
        mid = mido.MidiFile(ticks_per_beat=24)
        track = mido.MidiTrack()
        mid.tracks.append(track)
        track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))

        last = 0
        for tick, msg in sorted(self.events, key=lambda e: e[0]):
            track.append(msg.copy(time=tick - last))
            last = tick
        mid.save(path)
        return len(self.events)

    def close(self):
        pass
