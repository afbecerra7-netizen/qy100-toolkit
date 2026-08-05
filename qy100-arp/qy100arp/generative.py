"""Motores generativos: percusion euclidiana y melodia por cadena de Markov.

Ambos se mueven por ticks igual que el arpegiador, asi que quedan enganchados al
reloj del QY100. La idea de uso es que el QY100 aporte la base (estilo, acordes,
bateria) y estos motores generen encima en canales MIDI libres.
"""

from __future__ import annotations

import random

from .arp import DIVISIONS
from .euclid import euclid, to_string
from .scales import SCALES, degree_to_note, parse_note, scale_pitches


class EuclidLane:
    """Una linea de percusion (o de nota fija) con reparto euclidiano."""

    def __init__(self, cfg, rng=None):
        self.name = cfg.get("name", "lane")
        self.enabled = cfg.get("enabled", True)
        self.steps = int(cfg.get("steps", 16))
        self.pulses = int(cfg.get("pulses", 4))
        self.rotation = int(cfg.get("rotation", 0))
        self.note = parse_note(cfg.get("note", 36))
        self.channel = int(cfg.get("channel", 10)) - 1
        self.velocity = int(cfg.get("velocity", 100))
        self.accent = int(cfg.get("accent", 0))          # plus en el primer paso
        self.probability = float(cfg.get("probability", 1.0))
        self.division = cfg.get("division", "1/16")
        self.ticks_per_step = DIVISIONS[self.division]
        self.gate_ticks = max(1, int(cfg.get("gate_ticks", 1)))
        self.pattern = euclid(self.pulses, self.steps, self.rotation)
        self._rng = rng or random.Random()

    def describe(self) -> str:
        return "%-10s ch%-2d %-4s E(%d,%d) %s" % (
            self.name, self.channel + 1, self.division,
            self.pulses, self.steps, to_string(self.pattern))

    def on_tick(self, tick: int):
        if not self.enabled or tick % self.ticks_per_step:
            return []
        idx = (tick // self.ticks_per_step) % self.steps
        if not self.pattern[idx]:
            return []
        if self.probability < 1.0 and self._rng.random() > self.probability:
            return []
        vel = self.velocity + (self.accent if idx == 0 else 0)
        return [(self.note, max(1, min(127, vel)), self.gate_ticks)]


class MarkovMelody:
    """Melodia por cadena de Markov de orden 1 sobre grados de escala.

    La matriz de transicion no viene escrita a mano: se construye a partir de dos
    tendencias musicales, el tamano del intervalo (favorece el grado conjunto) y
    la gravedad tonal (favorece tonica, tercera y quinta). Ajustando `stepwise` y
    `tonal_pull` cambia el caracter sin tocar codigo.
    """

    def __init__(self, cfg, rng=None):
        self.enabled = cfg.get("enabled", True)
        self.channel = int(cfg.get("channel", 2)) - 1
        self.root = parse_note(cfg.get("root", "C3")) % 12
        self.scale = cfg.get("scale", "minor")
        if self.scale not in SCALES:
            raise ValueError("escala desconocida: %r" % (self.scale,))
        self.base_octave = int(cfg.get("base_octave", 3))
        self.range_degrees = int(cfg.get("range_degrees", 8))
        self.density = float(cfg.get("density", 0.6))
        self.division = cfg.get("division", "1/16")
        self.ticks_per_step = DIVISIONS[self.division]
        self.gate = float(cfg.get("gate", 0.9))
        self.velocity = int(cfg.get("velocity", 90))
        self.velocity_jitter = int(cfg.get("velocity_jitter", 15))
        self.stepwise = float(cfg.get("stepwise", 1.0))
        self.tonal_pull = float(cfg.get("tonal_pull", 1.0))
        self.follow_held = bool(cfg.get("follow_held", False))
        self.rest_after_leap = bool(cfg.get("rest_after_leap", True))

        self._rng = rng or random.Random(cfg.get("seed"))
        self._degree = 0
        self._held = ()

    def set_held(self, notes) -> None:
        """Clases de altura tocadas en el teclado, para el modo follow_held."""
        self._held = tuple(sorted({n % 12 for n in notes}))

    # ---- pesos ------------------------------------------------------------

    def _weight(self, frm: int, to: int) -> float:
        n = len(SCALES[self.scale])
        dist = abs(to - frm)

        # tamano del intervalo: el grado conjunto manda, el salto grande es raro
        if dist == 0:
            w = 0.5
        elif dist == 1:
            w = 3.0 * self.stepwise
        elif dist == 2:
            w = 2.0 * self.stepwise
        elif dist == 3:
            w = 1.0
        elif dist == 4:
            w = 0.8
        else:
            w = 0.3

        # gravedad tonal: tonica, tercera y quinta atraen
        deg = to % n
        if deg == 0:
            w *= 2.0 * self.tonal_pull
        elif deg == 4 % n:
            w *= 1.5 * self.tonal_pull
        elif deg == 2 % n:
            w *= 1.3 * self.tonal_pull

        return max(w, 0.01)

    def _next_degree(self) -> int:
        candidates = range(0, self.range_degrees)
        weights = [self._weight(self._degree, d) for d in candidates]
        total = sum(weights)
        r = self._rng.random() * total
        acc = 0.0
        for d, w in zip(candidates, weights):
            acc += w
            if r <= acc:
                return d
        return self._degree

    # ---- llamada por tick -------------------------------------------------

    def on_tick(self, tick: int):
        if not self.enabled or tick % self.ticks_per_step:
            return []
        if self._rng.random() > self.density:
            return []

        prev = self._degree
        self._degree = self._next_degree()

        if self.rest_after_leap and abs(self._degree - prev) >= 5:
            # despues de un salto grande, dejar respirar de vez en cuando
            if self._rng.random() < 0.4:
                return []

        note = degree_to_note(self._degree, self.root, self.scale, self.base_octave)

        if self.follow_held and self._held:
            # pegar la nota a la altura mas cercana de lo que se esta tocando
            from .scales import quantize
            note = quantize(note, self._held)

        length = max(1, int(round(self.ticks_per_step * self.gate)))
        jitter = self._rng.randint(-self.velocity_jitter, self.velocity_jitter)
        vel = max(1, min(127, self.velocity + jitter))
        return [(note, vel, length)]
