"""Motor de arpegiador.

Se mueve por ticks de MIDI Clock (24 por negra), nunca por reloj propio, asi que
sigue el tempo del QY100 exactamente y sin deriva. Todas las divisiones caen en
un numero entero de ticks:

    1/4 = 24    1/8 = 12    1/8T = 8    1/16 = 6
    1/16T = 4   1/32 = 3    1/32T = 2
"""

from __future__ import annotations

import random
from collections import OrderedDict

DIVISIONS = {
    "1/4": 24, "1/4T": 16,
    "1/8": 12, "1/8T": 8,
    "1/16": 6, "1/16T": 4,
    "1/32": 3, "1/32T": 2,
}

PATTERNS = ("up", "down", "updown", "updown_inc", "downup",
            "as_played", "random", "chord")


class Arpeggiator:
    def __init__(self, cfg):
        self.enabled = cfg.get("enabled", True)
        self.pattern = cfg.get("pattern", "up")
        if self.pattern not in PATTERNS:
            raise ValueError("patron desconocido: %r (opciones: %s)"
                             % (self.pattern, ", ".join(PATTERNS)))
        self.division = cfg.get("division", "1/16")
        if self.division not in DIVISIONS:
            raise ValueError("division desconocida: %r (opciones: %s)"
                             % (self.division, ", ".join(DIVISIONS)))
        self.ticks_per_step = DIVISIONS[self.division]
        self.octaves = max(1, int(cfg.get("octaves", 1)))
        self.gate = float(cfg.get("gate", 0.5))
        self.channel = int(cfg.get("channel", 1)) - 1
        self.latch = bool(cfg.get("latch", False))
        self.velocity_mode = cfg.get("velocity_mode", "input")  # input|fixed|accent
        self.fixed_velocity = int(cfg.get("fixed_velocity", 100))
        self.accents = cfg.get("accents") or [1.0]
        self.transpose = int(cfg.get("transpose", 0))

        # nota -> velocity, en orden de llegada (para el patron as_played)
        self._held = OrderedDict()
        self._sustained = OrderedDict()   # copia congelada cuando latch esta activo
        self._step = 0
        self._rng = random.Random(cfg.get("seed"))

    # ---- entrada de notas -------------------------------------------------

    def note_on(self, note: int, velocity: int) -> None:
        if self.latch and not self._held:
            # primera tecla de un acorde nuevo: descarta el retenido anterior
            self._sustained.clear()
        self._held[note] = velocity
        if self.latch:
            self._sustained[note] = velocity

    def note_off(self, note: int) -> None:
        self._held.pop(note, None)

    def clear(self) -> None:
        self._held.clear()
        self._sustained.clear()
        self._step = 0

    @property
    def active_notes(self):
        if self.latch and self._sustained:
            return self._sustained
        return self._held

    # ---- generacion de la secuencia --------------------------------------

    def _sequence(self):
        """Lista de (nota_a_sonar, nota_origen).

        Primero se expanden las octavas sobre el conjunto completo y despues se
        aplica la direccion, que es como se comporta un arpegiador de hardware:
        updown con 2 octavas sube por las dos y baja por las dos, en vez de
        hacer updown suelto en cada una.

        Se arrastra la nota_origen para poder recuperar su velocity exacta.
        """
        notes = self.active_notes
        if not notes:
            return []

        order = (list(notes.keys()) if self.pattern == "as_played"
                 else sorted(notes.keys()))

        pool = []
        for octave in range(self.octaves):
            for n in order:
                pool.append((n + 12 * octave, n))

        if self.pattern == "down":
            seq = list(reversed(pool))
        elif self.pattern == "updown":
            seq = pool + list(reversed(pool))[1:-1]
        elif self.pattern == "updown_inc":
            seq = pool + list(reversed(pool))
        elif self.pattern == "downup":
            seq = list(reversed(pool)) + pool[1:-1]
        else:                      # up, as_played, random, chord
            seq = pool

        return seq or pool

    def _velocity(self, source_note: int) -> int:
        if self.velocity_mode == "fixed":
            vel = self.fixed_velocity
        elif self.velocity_mode == "accent":
            factor = self.accents[self._step % len(self.accents)]
            vel = int(self.fixed_velocity * factor)
        else:
            vel = self.active_notes.get(source_note, self.fixed_velocity)
        return max(1, min(127, vel))

    # ---- llamada por tick -------------------------------------------------

    def on_tick(self, tick: int):
        """Devuelve una lista de (nota, velocity, duracion_en_ticks) o []."""
        if not self.enabled or tick % self.ticks_per_step:
            return []

        seq = self._sequence()
        if not seq:
            return []

        length = max(1, int(round(self.ticks_per_step * self.gate)))

        if self.pattern == "chord":
            picks = seq
        elif self.pattern == "random":
            picks = [self._rng.choice(seq)]
        else:
            picks = [seq[self._step % len(seq)]]

        events = []
        for note, source in picks:
            n = note + self.transpose
            if 0 <= n <= 127:
                events.append((n, self._velocity(source), length))

        self._step += 1
        return events
