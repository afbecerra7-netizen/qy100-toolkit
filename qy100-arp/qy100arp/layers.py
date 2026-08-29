"""Reusable compositional layers that aren't part of the live engine: fixed
gating, an echo/fade of another layer's strong notes, and a sine-wave LFO for
automating a CC over time (intended for panning, but generic).

All of them work on lists of (tick, message) events at the same resolution as
the rest of the project: 24 PPQN, the same as MIDI Clock.
"""

from __future__ import annotations

import math

import mido


class GatedLine:
    """Plays back (tick, note, velocity) with a short, fixed gate duration,
    for a plucked/staccato texture rather than a legato line."""

    def __init__(self, channel: int, gate_ticks: int):
        self.channel = channel
        self.gate_ticks = gate_ticks

    def render(self, notes):
        """notes: iterable of (tick, note, velocity)."""
        out = []
        for tick, note, vel in notes:
            out.append((tick, mido.Message("note_on", channel=self.channel,
                                           note=note, velocity=vel)))
            out.append((tick + self.gate_ticks,
                       mido.Message("note_off", channel=self.channel, note=note, velocity=0)))
        return out


class EchoFade:
    """Repeats the 'strong' notes (velocity >= threshold) of another layer,
    delayed and with velocity decaying geometrically on each repeat."""

    def __init__(self, channel: int, delay_ticks: int, gate_ticks: int,
                repeats: int = 3, decay: float = 0.55, threshold: int = 90):
        self.channel = channel
        self.delay_ticks = delay_ticks
        self.gate_ticks = gate_ticks
        self.repeats = repeats
        self.decay = decay
        self.threshold = threshold

    def render(self, notes):
        """notes: iterable of (tick, note, velocity) -- from the source layer."""
        out = []
        for tick, note, vel in notes:
            if vel < self.threshold:
                continue
            v = vel
            for i in range(1, self.repeats + 1):
                v = max(1, int(round(v * self.decay)))
                t = tick + self.delay_ticks * i
                out.append((t, mido.Message("note_on", channel=self.channel,
                                            note=note, velocity=v)))
                out.append((t + self.gate_ticks,
                           mido.Message("note_off", channel=self.channel, note=note, velocity=0)))
        return out


class SineLFO:
    """A CC (default 10 = Pan) oscillating as a sine wave between
    center-depth and center+depth. Only emits when the quantized value
    changes, so the file doesn't get flooded with identical messages."""

    def __init__(self, channel: int, cc: int = 10, center: int = 64, depth: int = 20,
                period_ticks: int = 24 * 4 * 2, step_ticks: int = 6):
        self.channel = channel
        self.cc = cc
        self.center = center
        self.depth = depth
        self.period_ticks = period_ticks
        self.step_ticks = step_ticks

    def render(self, total_ticks: int):
        out = []
        last_value = None
        for tick in range(0, total_ticks + 1, self.step_ticks):
            phase = (tick / self.period_ticks) * 2 * math.pi
            value = int(round(self.center + self.depth * math.sin(phase)))
            value = max(0, min(127, value))
            if value != last_value:
                out.append((tick, mido.Message("control_change", channel=self.channel,
                                               control=self.cc, value=value)))
                last_value = value
        return out
