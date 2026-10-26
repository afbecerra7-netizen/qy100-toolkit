# Preparing and shaping MIDI for the QY100

Two related subjects. The first is **cleaning up a Standard MIDI File before
it becomes a QY100 song**, so it fits the memory, plays the right drums and
sets up reliably. The second is **adding performance detail** (vibrato,
swells, strums, trills, timing feel) to material that was typed in or
generated, which is exactly what this project's generators produce.

Certainty marks follow [`CLAUDE.md`](../CLAUDE.md): `[M]` measured against the
device or a primary source, `[D]` deduced, `[V]` unverified. **Nothing here has
been played on the QY100 yet.** The drum table is checked against the Data
List; everything else is technique, to be tried and measured.

## Part 1: cleaning a MIDI file before it becomes a song

Song memory is the constraint (`CLAUDE.md`: about 3.5 KB per minute of written
music, 128 KB shared by everything). MIDI files from the internet routinely
carry thousands of events that change nothing, and every one of them costs
memory once it is a song event. Each rule below says what to detect and what to
do about it.

### Redundant data: remove it

| Detect | Fix |
| --- | --- |
| The same controller value repeated on a channel with nothing in between (a second CC 7 = 100 after CC 7 = 100) | Delete the repeats. Keep the first occurrence at the start of the song, since it establishes state. Leave CC 84 (Portamento Control) alone: repeating it is meaningful. |
| The same pitch bend value repeated | Delete the repeats |
| Two events of the same controller, or two bends, on one channel at the same tick | Keep the last; the first is inaudible |
| Two Note Ons of the same pitch on the same channel at the same tick | Delete the duplicate |
| A Note On while Volume or Expression is 0 on that channel | Delete it; it cannot be heard |
| Notes shorter than a threshold (a few ticks) | Delete them; usually mis-touches from real-time input. **Never on the drum channel**, where one-tick gates are normal |
| Velocities in a suspicious range (1 to a few) | Flag, don't delete blindly: a velocity 1 cymbal note is sometimes a deliberate choke |

### Malformed data: repair it

| Detect | Fix |
| --- | --- |
| A Note On of a pitch that is already sounding on that channel | Shorten the earlier note so it ends before the new one starts |
| A Note On and a Note Off of the same pitch at the same tick | Move the Note Off one tick earlier |
| A Note On with no matching Note Off | Treat an All Sound Off (CC 120) or All Notes Off (CC 123) as the end; failing that, end it one tick before the next Note On of the same pitch, or at the end of the track |
| Data Entry (CC 6/38) with no RPN or NRPN selected before it | Flag it; nothing sensible can be inferred |
| RPN or NRPN with MSB and LSB in the wrong order | Swap into MSB then LSB so the parameter is recognised |
| A controller or bend at the same tick as a Note On | Move it one tick **earlier** (five for sustain, CC 64), so the note starts with the new value instead of racing it |

### Setup: where to put it

- **Leave a setup bar.** If the first note is on beat 1 of bar 1, insert an
  empty bar and put Bank Select, Program Change, volume, pan, sends and effect
  settings there. Setup and notes on the same tick make the note sound with the
  old voice on some receivers.
- **Start at least 50 ms in,** and after an XG System On or GM On, keep the
  50 ms gap before anything else (`[M]` Data List p. 49 requires it).
- **Stagger channels.** Give each channel's setup its own few ticks so sixteen
  channels' worth of setup does not land as one burst.
- **Skip defaults.** A value equal to what XG System On sets anyway is dead
  weight; leave it out unless the file is meant to play after something else
  that may have changed it.
- **Close every RPN and NRPN with a null RPN** (`Bn 65 7F`, `Bn 64 7F`). While
  a parameter is still selected, any later Data Entry on that channel, however
  unrelated, lands on it.
- **Send one NRPN address followed by several values** when a parameter is
  animated: `Bn 63 msb`, `Bn 62 lsb`, then only `Bn 06 value` per step, then the
  null RPN. Repeating the address with every step triples the event count.
  The corollary: never interleave two animated NRPN parameters on the same
  channel, because each step would need its address again.
- **Controller before NRPN.** Where a CC and an NRPN reach the same parameter
  (the table in [`xg-remote-control.md`](xg-remote-control.md)), prefer the CC:
  filter cutoff as CC 74 rather than NRPN `01 20`, resonance as CC 71 rather
  than `01 21`. `[D]` For vibrato depth, CC 1 (modulation) usually does the
  job of NRPN `01 09`, since the mod wheel drives the same pitch LFO by default.

### Drums: GS and GM2 files play the wrong sounds on the QY100

GS and GM Level 2 files use notes 27 to 34 and 85 to 87 for a set of
percussion sounds that XG places elsewhere. On the QY100 those notes are
something else entirely, or silence.

`[M]` from the QY100's own drum table, Data List p. 4 (Standard Kit): notes 27
to 34 are Brush Slap, Brush Tap Swirl, Snare Roll, Castanet, Snare Soft,
Sticks, Kick Soft and Open Rim Shot. **The kit ends at note 84 (Bell Tree);
85, 86 and 87 are empty.** So a GS file's castanets and surdos simply vanish,
and its High Q plays a brush.

The remap, as a table in
[`qy100-syx/gm2_xg_drums.json`](../qy100-syx/gm2_xg_drums.json):

| GS/GM2 note | Sound | QY100 (XG) note |
| --- | --- | --- |
| 25 | Snare Roll | 29 |
| 26 | Finger Snap | 19 |
| 27 | High Q | 15 |
| 28 | Slap | 16 |
| 29 | Scratch Push | 17 |
| 30 | Scratch Pull | 18 |
| 31 | Sticks | 32 |
| 32 | Square Click | 20 (Click Noise; nearest, not identical) |
| 33 | Metronome Click | 21 |
| 34 | Metronome Bell | 22 |
| 85 | Castanets | 30 |
| 86 | Mute Surdo | 13 |
| 87 | Open Surdo | 14 |

`[D]` The pairs are matched by name. 27 to 34 and 85 to 87 are the GM Level 2
layout; 25 and 26 exist on GS kits from the SC-88 onward only, so map them only
when the file says it is GS. Notes 35 to 81 are the shared GM range and need no
change. Apply only to the drum channels (channel 10, and any channel set to a
drum kit), never to melodic parts.

Going the other way, for a QY100 song exported to GM2 or GS gear: 13→86,
14→87, 15→27, 16→28, 17→29, 18→30, 21→33, 22→34, 30→85, 32→31, plus 19→26 and
29→25 for GS targets only. XG's
brush sounds (25 to 28), Kick Soft, Open Rim Shot and the sequencer clicks have
no GM2 counterpart and are better substituted by ear than by rule.

## Part 2: adding performance detail

Generated and step-entered parts sound mechanical because every note has a
fixed pitch, a flat volume and a velocity set by rule. Performance detail comes
from four things, and all four are ordinary MIDI a QY100 song can store:
controller or bend **curves inside each note**, **velocity** that follows the
music's shape, **small timing offsets**, and **ornaments** that replace one note
with several.

### Curves inside a note

One general mechanism covers vibrato, swells, fades, bends and filter sweeps.
For each note that passes a filter, add a stream of events of one kind (pitch
bend, CC 1, CC 11, CC 74, CC 71...) whose values follow a curve over time.

**Which notes.** Filters worth having: minimum length (vibrato only on long
notes), chords excluded or included, direction relative to the previous note
(rising, falling, repeated; a scoop suits rising notes), and pitch class.

**Where in the note.** The curve occupies either a percentage of the note or a
fixed time in ms, placed at the **head**, **middle** or **tail**. Fixed time
suits effects with a natural duration (a 200 ms fade at the end); percentage
suits effects that scale with the note. An offset of a tick or two before the
note lets a bend be in place when the note starts.

**The curve.** A composition of simple functions covers nearly everything:

```
y = f1( f2(x·a) · b ) · f3(x·c)        x runs 0..1 across the covered span
```

Each `f` is optional and is one of seven shapes, all defined so that one unit
of input is one full cycle or one full sweep:

| Shape | Definition | Over 0..1 |
| --- | --- | --- |
| Linear | `x` | ramp 0 to 1 |
| Sin | `sin(2πx)` | one full cycle |
| Cos | `cos(2πx)` | one full cycle, starting at the top |
| Exp | `(e^(1−x) − 1) / (e − 1)` | exponential decay from exactly 1 to exactly 0 |
| Square | `x²` | slow start, fast finish |
| Saw up | `x − ⌊x⌋` | repeats every unit, so `x·a` with `a = 4` gives four ramps |
| Saw down | `1 − (x − ⌊x⌋)` | the same, falling |

The Exp normalisation matters: plain `exp(−x)` only falls to 0.37 over the
span, which leaves a fade that never finishes. The coefficients `a` and `c` are
repetition counts: `sin(2π·x·6)` is six vibrato cycles across the span, whatever
its length. Coefficients from 0.1 to 5 in steps of 0.1 cover every recipe below.

How the pieces combine:

- `f1` alone gives a plain shape.
- `f3` multiplies it as an envelope. `sin · x²` is a vibrato that grows in,
  `sin · Exp` one that dies away.
- `f2` inside `f1` bends time: its output, times `b`, becomes `f1`'s input. With
  `f2 = x²` and `f1 = cos`, the cycles get closer together towards the end, a
  vibrato that speeds up. If `f2` is off, `f1` takes `x·a` directly.
- Then, in this order: optionally fold negative values up (`abs`), optionally
  flip vertically (`−y`), optionally flip horizontally (read the result
  backwards).

**Mapping onto the output range.** Sample the result at 256 evenly spaced
points and keep the largest absolute value, the peak. Then either:

- **Scale:** map `−peak .. +peak` linearly onto `min .. max`. **Zero lands in
  the middle of the range.** A cosine vibrato scaled to 0 to 3 semitones swings
  around 1.5, which is what makes it upward-only; a curve that is never negative
  (Square, Exp, the saws) only ever reaches the upper half of the range unless it
  is shifted first.
- **Clip:** use the value as it is (on a ±127 scale) and clamp it to
  `min .. max`. Useful when part of the curve should sit flat against a limit.

An event at a given position takes the nearest sample at or below it (no
interpolation). 256 steps is finer than any MIDI value can show over a note, so
nothing is lost.

**How dense.** Walk the span from its start in steps of the **interval** (a few
ticks), compute the value at each step, and emit an event only if it differs
from the **last emitted** value by at least the **minimum difference**.
Comparing against the last emitted value, not the previous step, is what stops
a slow curve from being dropped entirely. Then clean up the result: clamp
negative times to 0, sort by time, drop any event that repeats the previous
value of the same kind, and keep only the first of several events on the same
tick. Together these put events where the curve moves and nowhere else. This
matters twice over on the QY100, where every event is song memory: an
unthinned vibrato on every long note of a solo can add more events than the
notes themselves.

For a parameter reached by NRPN, send the address (CC 99, CC 98) once at the
start of the span, only Data Entry (CC 6) per step, and the null RPN
(CC 101 = 127, CC 100 = 127) after the last one.

**Clean edges.** Optionally write a value at the start (a pre-event) and reset
to neutral just before the next note (a post-event: bend back to 0, CC 11 back
to 127), so the next note does not inherit a bent pitch. Before adding, delete
existing events of the same kind in the span so two passes don't fight.

A reference implementation of the curve, 30 lines of Python:

```python
import math

E = math.e
SHAPES = {
    "linear":   lambda x: x,
    "sin":      lambda x: math.sin(2 * math.pi * x),
    "cos":      lambda x: math.cos(2 * math.pi * x),
    "exp":      lambda x: (math.exp(1 - x) - 1) / (E - 1),
    "square":   lambda x: x * x,
    "saw_up":   lambda x: x - math.floor(x),
    "saw_down": lambda x: 1 - (x - math.floor(x)),
}

def curve(f1, a=1.0, f2=None, b=1.0, f3=None, c=1.0,
          fold=False, flip_y=False, flip_x=False, n=256):
    ys = []
    for i in range(n):
        x = i / (n - 1)
        y = SHAPES[f1](SHAPES[f2](x * a) * b) if f2 else SHAPES[f1](x * a)
        if f3:
            y *= SHAPES[f3](x * c)
        if fold and y < 0:
            y = -y
        if flip_y:
            y = -y
        ys.append(y)
    return ys[::-1] if flip_x else ys

def scale(ys, lo, hi):
    peak = max(abs(y) for y in ys) or 1.0
    return [lo + (y / peak + 1) * (hi - lo) / 2 for y in ys]
```

Working recipes, as starting points:

| Effect | Events | Shape |
| --- | --- | --- |
| Brass vibrato | pitch bend, 0 to +3 semitones, upward only | notes of 3 beats or more; middle 70% of the note, at most 2.5 s; cosine that speeds up; interval 5 ticks, minimum difference about 150 bend units; reset to 0 after |
| Plain vibrato | pitch bend, ±1 semitone or less | sine; tail of the note; interval a few ticks |
| Tail fade | CC 11 | falls over the last 200 ms of long, isolated notes; x² curve; pairs well with a small downward bend at the same spot |
| Soft attack | CC 11 | rises over the first part of the note |
| Swell (cresc/decresc) | CC 11 | ramp over a whole selection rather than per note |
| Accordion | CC 11, 88 to 127 | slightly irregular rise and fall: a sine multiplied by exp(−x) |
| Wah | CC 74 | sweep per note; the controller form of XG filter cutoff |
| Scoop / fall | pitch bend | short ramp into the head (scoop) or off the tail (fall), on rising or falling notes only |
| Just intonation | pitch bend | one constant bend per pitch class, per key, for the whole note; only valid if the part is monophonic or all notes on the channel share a pitch class, since bend is per channel |

The bend range must cover the curve. A +3 semitone vibrato needs a range of at
least 3 (`Bn 65 00 64 00 06 nn`, then the null RPN), and XG's default is 2.

### Velocity by shape

Replace or offset velocity with a function of something musical:

- **position in the bar** (accents: a sawtooth `1 − frac(x)` over the beat
  gives strong downbeats, 64 to 120 is a usable range),
- **pitch** (brighter high notes, or the reverse),
- **time across the selection** (crescendo, decrescendo, fade out),
- **the note's length** (longer notes played harder, as a player leans into
  them),
- **the interval from the previous note**, signed or unsigned (leaps accented,
  steps relaxed; or rising lines louder than falling ones),
- **the original velocity itself** (compress or expand the dynamic range
  without flattening it).

Offering both "add to the existing velocity" and "replace it" keeps the
original phrasing when that matters.

### Timing feel

Shift note starts by a function of their position in the bar. A Viennese waltz
is the classic case: beat 2 early and beat 3 late, a sine of the beat position
scaled to about ±20 ticks at 480 per quarter. The same mechanism does swing, a
habanera lilt or a lazy backbeat, and a small random term humanises without a
pattern.

### Ornaments and gestures

Each replaces or adds notes, so each is a pass over the note list:

- **Trill.** Alternate the written note and a second note (the next scale step
  by default, which means the key must be known; any interval gives a tremolo)
  across the note, or until the next note. Options: start from the upper or
  lower note, stretch the first and last, end on the written note, finish with
  a turn. For wind and string sounds, a trill made of pitch bend on one sounding
  note is often more convincing than retriggered notes.
- **Slur into bend.** Replace a legato run on one channel with its first note
  plus pitch bend following the melody: guitar hammer-ons and slides, sax
  scoops. The glide between pitches should **end** at the next written note's
  start, not begin there as MIDI portamento does, and should have a maximum
  length so long notes don't crawl. The whole run must fit inside the bend
  range. The inverse (bends back into notes) is useful for moving a part to an
  instrument that can't bend.
- **Glide.** MIDI portamento (CC 65 on) with CC 5 ramping during the transition
  changes the speed of the slide mid-way, the analogue-synth glide. It
  generates many CC 5 events, so thin it.
- **Glissando.** A run from one note to another at a set start and end tick,
  drawn from a scale mask (white keys, black keys, or any set), velocity
  ramping, sustain held through it. Two masks with a small delay between them
  sound like two hands. Retuning individual strings of the mask (a harp's
  pedal settings, where a string can sound a semitone off its name) gives a
  harp.
- **Echo.** Repeat notes after a delay in ms, a set number of times, at a
  percentage of the velocity, optionally an octave away, onto another channel.
  Decide what happens when an echo overlaps the original (shorten, skip, or
  allow). Gating the echo with the sustain pedal (only while CC 64 is down, and
  cut when it lifts) makes it behave like a real delay pedal.
- **Strum.** Offset the notes of a chord so it sounds strummed: downstrokes low
  to high, upstrokes high to low, direction set by a grid (on eighths, down on
  the beat and up on the off-beat, or any pattern), spread between a minimum and
  maximum. A chord is any set of notes within a small tolerance of each other.
  With the spread set to zero the same pass does the opposite and tightens
  sloppy chords onto one tick.

## Where this fits in the project

- [`qy100-arp/`](../qy100-arp/) and `syx.py generar` produce exactly the flat,
  uniform material Part 2 is for. Tail fade, velocity by bar position and a
  small timing feel are the cheapest wins.
- Any tool that converts a downloaded MIDI file into a song should run Part 1
  first, drum remap included, before counting how much memory the result will
  take.
- Everything Part 2 adds is ordinary song data: pitch bend and CC events on the
  track's channel. `[V]` Worth measuring on the device: the memory cost per
  thousand bend events, and whether the song editor stays responsive with the
  density a thinned vibrato produces.
