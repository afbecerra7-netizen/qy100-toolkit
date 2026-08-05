"""Planificador central: convierte ticks en note on/off concretos.

Un unico contador de ticks absoluto gobierna todo. El Song Position Pointer del
QY100 lo reposiciona, de modo que los patrones quedan alineados al compas del
secuenciador y no a "cuando le diste play al script".
"""

from __future__ import annotations

import random

import mido

from .arp import Arpeggiator
from .generative import EuclidLane, MarkovMelody


class Engine:
    def __init__(self, cfg, output, log=None):
        self.out = output
        self.log = log or (lambda *a: None)

        seed = cfg.get("seed")
        self._rng = random.Random(seed)

        self.arp = Arpeggiator(cfg.get("arpeggiator", {}))

        gen = cfg.get("generative", {})
        self.lanes = [EuclidLane(l, self._rng)
                      for l in gen.get("euclid_lanes", [])]
        mel_cfg = gen.get("melody")
        self.melody = MarkovMelody(mel_cfg, self._rng) if mel_cfg else None

        self.tick = 0
        self.running = False
        self._offs = {}          # (canal, nota) -> tick de apagado
        self._sounding = set()   # (canal, nota) actualmente sonando

    # ---- canales que producimos (para filtrar realimentacion) -------------

    def output_channels(self):
        chans = {self.arp.channel}
        chans.update(l.channel for l in self.lanes)
        if self.melody:
            chans.add(self.melody.channel)
        return chans

    # ---- entrada del teclado ---------------------------------------------

    def note_on(self, note: int, velocity: int) -> None:
        self.arp.note_on(note, velocity)
        if self.melody and self.melody.follow_held:
            self.melody.set_held(self.arp.active_notes.keys())

    def note_off(self, note: int) -> None:
        self.arp.note_off(note)
        if self.melody and self.melody.follow_held:
            self.melody.set_held(self.arp.active_notes.keys())

    # ---- transporte -------------------------------------------------------

    def start(self, tick: int = 0) -> None:
        self.tick = tick
        self.running = True
        self.arp._step = 0
        self.log("transporte: START en tick %d" % tick)

    def cont(self) -> None:
        self.running = True
        self.log("transporte: CONTINUE en tick %d" % self.tick)

    def stop(self) -> None:
        self.running = False
        self.all_notes_off()
        self.log("transporte: STOP")

    def set_position(self, midi_beats: int) -> None:
        """SPP: 1 beat MIDI = 1/16 de nota = 6 ticks a 24 PPQN."""
        self.tick = midi_beats * 6
        self.log("posicion -> tick %d (compas ~%d)" % (self.tick, self.tick // 96 + 1))

    # ---- emision ----------------------------------------------------------

    def _send_off(self, channel: int, note: int) -> None:
        self.out.send(mido.Message("note_off", channel=channel, note=note, velocity=0))
        self._sounding.discard((channel, note))

    def _emit(self, channel: int, note: int, velocity: int, length: int) -> None:
        key = (channel, note)
        if key in self._sounding:
            self._send_off(channel, note)      # rearticular, no ligar
        self.out.send(mido.Message("note_on", channel=channel,
                                   note=note, velocity=velocity))
        self._sounding.add(key)
        self._offs[key] = self.tick + max(1, length)

    def is_sounding(self, channel: int, note: int) -> bool:
        return (channel, note) in self._sounding

    def all_notes_off(self) -> None:
        for channel, note in list(self._sounding):
            self._send_off(channel, note)
        self._offs.clear()

    # ---- un tick de reloj -------------------------------------------------

    def on_tick(self) -> None:
        if not self.running:
            return
        t = self.tick

        # 1) apagados vencidos, antes de encender nada nuevo
        for key, off_at in list(self._offs.items()):
            if off_at <= t:
                self._send_off(key[0], key[1])
                del self._offs[key]

        # 2) nuevos eventos
        for note, vel, length in self.arp.on_tick(t):
            self._emit(self.arp.channel, note, vel, length)

        for lane in self.lanes:
            for note, vel, length in lane.on_tick(t):
                self._emit(lane.channel, note, vel, length)

        if self.melody:
            for note, vel, length in self.melody.on_tick(t):
                self._emit(self.melody.channel, note, vel, length)

        self.tick = t + 1
