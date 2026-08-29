# qy100-arp

> **English translation of [`README.md`](README.md).** Keep the two in sync — this file is
> not authoritative; if they disagree, the Spanish original wins. Command-line flag
> names and `config.json` keys are left untranslated below where they are literal
> arguments/keys the script expects — do not translate them when typing a command
> or editing the config.

External arpeggiator and generative sequencer for the **Yamaha QY100**.

The QY100 has no built-in arpeggiator — verified by searching the full owner's
manual and service manual: zero matches. This adds one from the outside over
MIDI, **without touching the device's firmware**.

The QY100 remains the master: it drives the clock and we follow. The whole
engine advances on MIDI Clock ticks (24 per quarter note), so there is no
possible drift between the two.

## Two topologies

### A — Insert (the QY100 sets the tempo)

Requires both of the QY100's ports free.

```
[QY100's own mini-keyboard or an external keyboard]
        │  MIDI OUT  →  notes + Clock + Start/Stop + Song Position
        ▼
   [qy100-arp]
        │  MIDI IN
        ▼
   [QY100 XG tone generator]
```

```bash
.venv/bin/python run.py --in "FastTrack" --out "FastTrack" --local-off
```

Starts when you hit play on the QY100. Our own tempo precision doesn't matter
here: we only follow.

### B — In series, master mode (`--master`)

For when the QY100's `MIDI OUT` is already busy feeding other synths and there
is no return path available. The box goes **in front of the controller**,
which is where an arpeggiator always sat, and the output to the synths stays
intact.

```
[controller] → [qy100-arp] → [QY100 IN]        [QY100 OUT] → synths
                     ↑
              clock master
```

```bash
.venv/bin/python run.py --master --bpm 120 --in "Controller" --out "FastTrack"
```

Here the QY100 becomes a slave: `MIDI SYNC = External`, `MIDI CONTROL = In` or
`In/Out`. With `MIDI CONTROL` including `Out`, the QY100 forwards the clock to
the downstream synths, so the whole chain stays in sync.

Non-note messages (CC, pitch bend, program change, aftertouch) pass straight
through from the controller to the QY100, so wheels and knobs keep working.
Disable with `"passthrough": false` in the config.

**On precision:** in this mode we generate the clock ourselves, so Python's
timing does matter. Measured over real CoreMIDI ports: exact tempo and a
maximum jitter of 3–7 ms. MIDI receivers average the incoming clock, so in
practice it holds up, but if you need hardware-grade precision, topology A
doesn't have this problem because we never transmit clock.

## Mandatory QY100 settings

These live in UTILITY mode. They change with the topology:

| Setting | Topology A | Topology B (`--master`) | Page |
|---|---|---|---|
| `MIDI SYNC` | `Internal` | **`External`** | 127 |
| `MIDI CONTROL` | `Out` or `In/Out` | `In` or `In/Out` | 127 |
| `ECHO BACK` | `Off` | `Off` | 128 |

`ECHO BACK = Off` is mandatory in both, for **two** distinct reasons:

- With `Thru`, what we generate comes back out again and forms a feedback
  loop.
- With `RecMontr`, the QY100 **re-channels everything coming in to the
  selected record track's channel**, so several distinct channels collapse
  into a single voice. The manual lists this as its own fault (p. 143). The
  symptom is deceptive: everything plays, but all with the same instrument.

The QY100's **HOST SELECT** switch must be set to `MIDI`.

### Doubled notes

If you play the **QY100's own mini-keyboard**, its notes sound internally *in
addition to* the arpeggio. To avoid it, start with `--local-off`: it sends
Local Control OFF (CC 122), which the implementation chart confirms the QY100
recognizes. It's restored automatically on exit.

If the script dies without restoring it and the keyboard goes silent:

```bash
.venv/bin/python run.py --local-on --out "FastTrack"
```

(or just power-cycle the QY100).

## Installation

Already done, but if it needs redoing:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

## Usage

See what ports exist:

```bash
.venv/bin/python run.py --list
```

Live against the QY100 (the normal case):

```bash
.venv/bin/python run.py --in "FastTrack" --out "FastTrack" --local-off
```

It waits; starts when you hit **play** on the QY100. `Ctrl-C` to exit (turns
off all notes before closing).

### Without the device connected

See the events in the console with an internal clock:

```bash
.venv/bin/python run.py --sim --bpm 120 --notes "C3 Eb3 G3 Bb3"
```

Virtual CoreMIDI port, to hear it with any instrument on a Mac:

```bash
.venv/bin/python run.py --virtual --sim --bpm 120 --notes "C3 Eb3 G3 Bb3"
```

Render to a `.mid` file with no real-time playback:

```bash
.venv/bin/python run.py --render output.mid --bars 16 --notes "C3 Eb3 G3 Bb3"
```

The `.mid` comes out at 24 PPQN, the same resolution as MIDI Clock, with no
rescaling.

## Configuration

Everything lives in [`config.json`](config.json), which accepts `//` comments.
Channels are written **1–16** as on the QY100's panel, not 0–15.

### Arpeggiator

| Key | Options |
|---|---|
| `pattern` | `up` `down` `updown` `updown_inc` `downup` `as_played` `random` `chord` |
| `division` | `1/4` `1/4T` `1/8` `1/8T` `1/16` `1/16T` `1/32` `1/32T` |
| `octaves` | 1 upward — walks the full set, doesn't repeat the pattern per octave |
| `gate` | fraction of the step; `>1` ties into the next |
| `latch` | keeps arpeggiating after keys are released |
| `velocity_mode` | `input` (as played) · `fixed` · `accent` (cyclic pattern) |

### Generative

**`euclid_lanes`** — percussion with euclidean distribution, one per line.
`E(pulses, steps)` spreads the hits as evenly as possible. `E(4,16)` gives
`x...x...x...x...`, `E(3,8)` gives the triplet `x..x..x.`. `rotation` shifts
the phase; `probability < 1` makes the lane deliberately miss hits.

**`melody`** — order-1 Markov chain over scale degrees. The transition matrix
isn't hand-written: it's built from two tendencies, interval size (`stepwise`,
favors stepwise motion) and tonal gravity (`tonal_pull`, favors
tonic/3rd/5th). Raise or lower them to change the character without touching
code.

`"follow_held": true` makes the melody stick to the notes you're holding on
the keyboard, so it follows your live chords instead of a fixed scale. Probably
the most fun setting in the file.

## Live control via CC

Without a screen, editing a file live is useless: parameters need to be under
knobs. The config's `midi_control` section maps CC numbers to engine
parameters, applied while it's running.

```json
"midi_control": {
  "enabled": true,
  "channel": null,
  "map": { "74": "arp.division", "75": "arp.octaves", "76": "arp.gate" }
}
```

A mapped CC is **consumed** and does not reach the QY100. Unmapped ones pass
straight through.

Available parameters:

| | |
|---|---|
| `arp.` | `enabled` `latch` `pattern` `division` `octaves` `gate` `transpose` `fixed_velocity` |
| `melody.` | `enabled` `density` `stepwise` `tonal_pull` `velocity` `base_octave` |
| `lane.<name>.` | `enabled` `pulses` `rotation` `probability` `velocity` |

`<name>` is the euclidean lane's `name` field (`bombo`, `caja`, `hihat` — bass
drum, snare, hi-hat — by default). A name or parameter that doesn't exist
fails startup with a clear message, rather than silently doing nothing.

To find out which CC each knob on your controller sends, run with `--sim` and
watch what arrives.

## Tests

```bash
.venv/bin/python test_engine.py     # engine, no hardware
```

```bash
.venv/bin/python test_control.py    # CC control and message routing
```

```bash
.venv/bin/python test_master.py     # master mode over real CoreMIDI ports
```

`test_engine.py` covers the euclidean patterns, scale quantization, note order
for each arpeggiator pattern, tick-level timing, velocity propagation to
octaves, Song Position Pointer alignment, and that no pattern leaves hanging
notes (`note_on` == `note_off`).

`test_master.py` brings up virtual ports, runs the real program as a
subprocess and verifies against real MIDI: that it transmits Start/Clock/Stop,
the measured tempo and jitter, that the controller's CCs pass through, and
that **killing the process leaves no notes sounding** — important when there
are synths downstream.

## External resources

[QY100 Explorer](https://qy100.doffu.net/) is an active QY100/QY70 community.
Relevant because it confirms that the productive way to extend the device is
**data, not firmware**: they achieve out-of-range BPM and patterns longer than
8 measures by authoring custom style files and loading them over SysEx
(`.syx` / `.Q1P`). They have style downloads and a couple of web tools (a MIDI
LFO generator, a MIDI logger).
