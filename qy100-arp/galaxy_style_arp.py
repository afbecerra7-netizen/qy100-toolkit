"""Generates an 8-bar sparse, pentatonic, Galaxy-style piano arpeggio, plus two
companion layers:

  ch1  (idx 0)  main arpeggio: a sparse random walk over a major pentatonic
                scale.
  ch2  (idx 1)  gated embellishment (staccato, higher register) + a sine LFO
                on Pan (CC10), a subtle left-right sweep.
  ch3  (idx 2)  echo/fade of channel 1's strong notes.

Doesn't use the live engine (arp.py/engine.py): this is an offline
composition with its own random walk, for direct control over the sparse
character the style calls for. Reuses qy100arp.scales for pitches and
qy100arp.layers for the gating, echo and LFO.
"""

from __future__ import annotations

import argparse
import os
import random

import mido

from qy100arp.layers import EchoFade, GatedLine, SineLFO
from qy100arp.scales import degree_to_note, parse_note

PPQN = 24  # same resolution as the engine and MIDI Clock, no rescaling


def build(bars=8, bpm=76, seed=None):
    rng = random.Random(seed)

    root = parse_note("D3") % 12
    scale = "pentatonic"          # D E F# A B -- major, no harsh half-steps
    step_ticks = PPQN // 2        # eighth-note grid (1/8)
    total_steps = bars * 4 * 2
    total_ticks = total_steps * step_ticks

    # ---- channel 1: main arpeggio, sparse random walk ----------------------
    arp_channel = 0
    degree = 0
    arp_notes = []  # (tick, note, velocity) -- for the other layers
    arp_msgs = []
    for step in range(total_steps):
        tick = step * step_ticks
        if rng.random() < 0.45:
            move = rng.choice([-2, -1, -1, 1, 1, 2, 7, -7])
            degree = max(-7, min(14, degree + move))
            note = degree_to_note(degree, root, scale, base_octave=4)
            strong = (step % 16 == 0) or rng.random() < 0.12
            velocity = rng.randint(92, 112) if strong else rng.randint(48, 72)
            gate = int(step_ticks * (1.3 if strong else 0.9))  # strong notes ring longer
            arp_notes.append((tick, note, velocity))
            arp_msgs.append((tick, mido.Message("note_on", channel=arp_channel,
                                                note=note, velocity=velocity)))
            arp_msgs.append((tick + gate, mido.Message("note_off", channel=arp_channel,
                                                        note=note, velocity=0)))

    # ---- channel 2: gated embellishment, higher and sparser -----------------
    orn_channel = 1
    orn_step_ticks = PPQN // 4    # sixteenth-note grid, interlocks with the arp's 1/8
    orn_degree = 7                # starts a fifth above the arpeggio
    orn_notes = []
    for step in range(total_steps * 2):
        tick = step * orn_step_ticks
        if step % 2 == 0:         # stays on the off-beats, off the arp's grid
            continue
        if rng.random() < 0.30:
            move = rng.choice([-2, -1, 1, 2, 4])
            orn_degree = max(0, min(21, orn_degree + move))
            note = degree_to_note(orn_degree, root, scale, base_octave=5)
            velocity = rng.randint(55, 80)
            orn_notes.append((tick, note, velocity))
    orn_gate = GatedLine(channel=orn_channel, gate_ticks=int(orn_step_ticks * 0.5))
    orn_msgs = orn_gate.render(orn_notes)

    # ---- channel 2 also: sine LFO on Pan, subtle left-right sweep ----------
    pan_lfo = SineLFO(channel=orn_channel, cc=10, center=64, depth=18,
                      period_ticks=PPQN * 4 * 2, step_ticks=6)
    pan_msgs = pan_lfo.render(total_ticks)

    # ---- channel 3: echo/fade of channel 1's strong notes -------------------
    echo = EchoFade(channel=2, delay_ticks=int(step_ticks * 1.5), gate_ticks=int(step_ticks * 0.8),
                    repeats=3, decay=0.55, threshold=90)
    echo_msgs = echo.render(arp_notes)

    all_msgs = arp_msgs + orn_msgs + pan_msgs + echo_msgs
    return all_msgs, total_ticks, bpm


def save(path, msgs, bpm):
    mid = mido.MidiFile(ticks_per_beat=PPQN)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))

    last = 0
    for tick, msg in sorted(msgs, key=lambda e: e[0]):
        track.append(msg.copy(time=tick - last))
        last = tick
    mid.save(path)
    return len(msgs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", type=int, default=8)
    ap.add_argument("--bpm", type=float, default=76.0)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--salida", default="galaxy_arp.mid")
    args = ap.parse_args()

    destino = args.salida
    if not os.path.dirname(destino):
        os.makedirs("midi", exist_ok=True)
        destino = os.path.join("midi", destino)

    msgs, total_ticks, bpm = build(bars=args.bars, bpm=args.bpm, seed=args.seed)
    n = save(destino, msgs, bpm)
    print("Wrote %s: %d events, %d bars at %.1f BPM "
          "(ch1 arpeggio, ch2 embellishment+subtle pan LFO, ch3 echo)"
          % (destino, n, args.bars, bpm))


if __name__ == "__main__":
    main()
