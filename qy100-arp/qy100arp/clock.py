"""Reloj interno, solo para cuando no hay QY100 mandando MIDI Clock.

En uso normal el reloj lo pone el QY100 y esta clase no se usa. Existe para
poder trabajar los motores sin equipo conectado.
"""

from __future__ import annotations

import time

PPQN = 24


class InternalClock:
    def __init__(self, bpm: float = 120.0):
        self.bpm = float(bpm)
        self.interval = 60.0 / (self.bpm * PPQN)
        self._next = None

    def start(self) -> None:
        self._next = time.monotonic()

    def due(self) -> int:
        """Cuantos ticks tocan desde la ultima consulta (recupera si se atrasa)."""
        if self._next is None:
            return 0
        now = time.monotonic()
        n = 0
        while now >= self._next:
            n += 1
            self._next += self.interval
            if n > 96:            # no intentar recuperar mas de un compas
                self._next = now + self.interval
                break
        return n
