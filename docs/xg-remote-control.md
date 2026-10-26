# Driving the QY100's XG tone generator over MIDI

The QY100's tone generator is a standard Yamaha XG part (model ID `4C`), and it
takes a much wider set of XG messages than the single Parameter Change family
first captured live in
[`qy100-remote-transmission-mapping/`](../qy100-remote-transmission-mapping/).
This document collects how the whole family works, what each message is good
for, and which of it has actually been proven on the device.

Certainty marks follow [`CLAUDE.md`](../CLAUDE.md): `[M]` measured against the
device or a primary source, `[D]` deduced from something measured, `[V]`
unverified. **Most of this document is `[M]` against the QY100 Data List and
`[V]` against the hardware.** The Data List says the device receives these
messages; nobody has yet sent most of them and watched what happens. Treat
every `[V]` as a test to run, not a rule.

A correction first: `CLAUDE.md` says the Data List's MIDI section covers Bulk
Dump and not this protocol. It does cover it. `[M]` Data List p. 43 (receive
flow), pp. 49 to 50 (message formats), pp. 58 to 62 (address tables).

## The four message types

All four share the header `F0 43 xn 4C`, where `x` selects the type and `n` is
the device number (0 to F; the QY100 answers on its own device number, and `1n`
with `n = 0` is what has worked so far).

| Type | Frame | Direction on the QY100 |
| --- | --- | --- |
| Parameter Change | `F0 43 1n 4C aa aa aa dd.. F7` | received; transmitted only in answer to a Parameter Request `[M]` p. 49 |
| Bulk Dump | `F0 43 0n 4C bb bb aa aa aa dd.. cc F7` | received; transmitted only in answer to a Dump Request `[M]` p. 50 |
| Dump Request | `F0 43 2n 4C aa aa aa F7` | received `[M]` p. 50 |
| Parameter Request | `F0 43 3n 4C aa aa aa F7` | received `[M]` p. 50 |

`aa aa aa` is the three-byte address (High, Mid, Low). The live captures in
`qy100-remote-transmission-mapping/` also show the device transmitting
Parameter Changes on its own when the panel changes an effect setting, which the
Data List does not mention. Both things are true: the Data List describes what
it promises, the captures show what it also does.

### Parameter Change carries as many bytes as the parameter is wide

A parameter whose table entry has Size 2 or 4 must be sent as **one** message
with all of its bytes (`[M]` p. 49: "For parameters with a Data Size of 2 or 4,
the corresponding amount of data will be transmitted"). Splitting it into one
message per byte gets an **XG Address Error** on screen `[M]` (seen on the
device). The wide parameters are:

| Address | Size | Parameter |
| --- | --- | --- |
| `00 00 00` | 4 | Master Tune, one nibble per byte (`0m 0m 0m 0m`) |
| `02 01 00`, `02 01 20`, `02 01 40` | 2 | Reverb, Chorus, Variation Type (MSB = family, LSB = variant) |
| `02 01 42` to `02 01 54`, even addresses | 2 | Variation Parameters 1 to 10 (MSB, LSB) |
| `08 nn 09` | 2 | Part Detune, one nibble per byte |

Example, Variation Type to Delay L,C,R:

```
F0 43 10 4C 02 01 40 05 00 F7
```

### Bulk Dump: a whole block in one message

A Bulk Dump writes a run of consecutive addresses at once. `bb bb` is the byte
count of the data as two 7-bit bytes (high first), and the checksum makes the
low 7 bits of *byte count + address + data + checksum* equal zero `[M]` p. 50:

```python
def xg_bulk_dump(address, data, device=0):
    body = [len(data) >> 7, len(data) & 0x7F, *address, *data]
    checksum = (-sum(body)) & 0x7F
    return bytes([0xF0, 0x43, device, 0x4C, *body, checksum, 0xF7])
```

The Reverb block with its XG defaults (Hall 1, parameters 1 to 10, Return,
Pan) is 14 bytes at `02 01 00`:

```
F0 43 00 4C 00 0E 02 01 00  01 00 12 0A 08 0D 31 00 00 00 00 28 40 40  64 F7
```

The natural block boundaries, taken from the TOTAL SIZE rows of the address
tables `[M]` pp. 58 to 62:

| Start | Size | Block |
| --- | --- | --- |
| `00 00 00` | `06` | System (Master Tune, Master Volume, Transpose) |
| `02 01 00` | `0E` | Reverb Type, Parameters 1 to 10, Return, Pan |
| `02 01 10` | `06` | Reverb Parameters 11 to 16 |
| `02 01 20` | `0F` | Chorus Type, Parameters 1 to 10, Return, Pan, Send to Reverb |
| `02 01 30` | `06` | Chorus Parameters 11 to 16 |
| `02 01 40` | `21` | Variation Type, Parameters 1 to 10, Return, Pan, Sends, Connection, Part, controller depths |
| `02 01 70` | `06` | Variation Parameters 11 to 16 |
| `08 nn 00` | `29` | Multi Part `nn`: voice, mode, mix, sends, sound offsets, controller routing |
| `08 nn 30` | `3F` | Multi Part `nn`, `30` to `6E`: channel aftertouch routing, portamento, pitch EG; most of it marked Not Used on the QY100 |
| `3n rr 00` | `10` | Drum Setup `n`, note `rr` |

Why bother, when Parameter Change already works:

- **Speed.** Restoring a complete effect setting is one 44-byte message instead
  of a dozen or more separate ones.
- **Atomicity.** The block lands at once, so there is no audible half-applied
  state while a type and its parameters arrive one by one.
- **No width traps.** Two- and four-byte parameters inside the block are just
  consecutive bytes; the Address Error problem above cannot happen.

Limits `[M]` p. 50: never send more than 512 bytes of data in one Bulk Dump; a
larger transfer goes in packets of 512 or less with at least 120 ms between
them. After XG System On (`F0 43 10 4C 00 00 7E 00 F7`) wait at least 50 ms
before the next message, because it resets every Multi Part and Effect value
`[M]` p. 49.

`[V]` Not yet sent to the device. The first test: dump the Reverb block above
with a changed Return, then read it back with a Dump Request.

### Dump Request and Parameter Request: reading the device's current state

`F0 43 2n 4C aa aa aa F7` asks for the block that starts at `aa aa aa`, and the
device answers with a Bulk Dump of it. `F0 43 3n 4C aa aa aa F7` asks for one
parameter, and the answer is a Parameter Change. So the current volume of part
1:

```
send:    F0 43 30 4C 08 00 0B F7
answer:  F0 43 10 4C 08 00 0B vv F7
```

This is what a remote editor needs to open with knobs that match the hardware,
instead of showing defaults until the user touches something. `[M]` p. 50 lists
System, Multi Effect, Multi Part and Drum Setup as answerable; System
Information (`01 00 00`, the model name `"QY100 "` and XG support level) is
answered to a Dump Request only `[M]` p. 58.

`[V]` Which blocks the QY100 actually answers, and how quickly, has not been
measured.

### Parameter Request as a "ready" handshake

Because a Parameter Request is always answered, it doubles as a flow-control
ping. Send a large transfer, then send a cheap Parameter Request
(`F0 43 30 4C 08 00 00 F7` is enough) and wait for its answer. The tone
generator handles incoming messages in order, so the reply arriving means
everything sent before it has been processed. This replaces a guessed fixed
delay after a big write with a measured one, and a missing reply within a
timeout is also a direct "the device is not listening" signal (wrong port,
MIDI CONTROL, dead cable).

`[D]` The ordering argument follows from a single serial MIDI input feeding one
parser. `[V]` Not tested, and whether the same holds for the sequencer's own
`43 x0 5F` Bulk Dump protocol (where the write is committed to flash, possibly
after the MIDI parser has moved on) is an open question. Don't use it as proof
that a pattern write succeeded; the rule in `CLAUDE.md` still stands: only
reading it back proves state.

## Controller equivalents: the same parameters as CC, NRPN and RPN

Many Multi Part and Drum Setup parameters also have a channel message that
reaches the same setting. The full table, with addresses, controller numbers
and value conversions, is in
[`qy100-remote-transmission-mapping/xg_controller_equivalents.json`](../qy100-remote-transmission-mapping/xg_controller_equivalents.json).
The Multi Part half:

| XG address | Parameter | Channel message |
| --- | --- | --- |
| `08 nn 01` / `02` | Bank Select MSB / LSB | CC 0 / CC 32 |
| `08 nn 03` | Program Number | Program Change |
| `08 nn 0B` | Volume | CC 7 |
| `08 nn 0E` | Pan | CC 10 |
| `08 nn 12` | Chorus Send | CC 93 |
| `08 nn 13` | Reverb Send | CC 91 |
| `08 nn 14` | Variation Send | CC 94 |
| `08 nn 15` / `16` / `17` | Vibrato Rate / Depth / Delay | NRPN `01 08` / `01 09` / `01 0A` |
| `08 nn 18` | Filter Cutoff | CC 74 (Brightness) |
| `08 nn 19` | Filter Resonance | CC 71 (Harmonic Content) |
| `08 nn 1A` | EG Attack | CC 73 |
| `08 nn 1B` | EG Decay | NRPN `01 64` |
| `08 nn 1C` | EG Release | CC 72 |
| `08 nn 23` | Pitch Bend range | RPN `00 00` |
| `08 nn 67` | Portamento Switch | CC 65 (send 0 or 127) |
| `08 nn 68` | Portamento Time | CC 5 |

NRPN is sent as `Bn 63 msb`, `Bn 62 lsb`, `Bn 06 value`; RPN as `Bn 65 msb`,
`Bn 64 lsb`, `Bn 06 value`. One conversion matters: `08 nn 23` runs `28..58`
around a centre of `40` (−24 to +24 semitones) while RPN `00 00` runs `0..24`,
so the RPN value is `max(0, xg − 0x40)`.

Drum Setup parameters map to NRPN with the **drum note as the LSB**
(`Bn 63 msb`, `Bn 62 note`, `Bn 06 value`):

| Drum Setup offset | Parameter | NRPN MSB |
| --- | --- | --- |
| `00` / `01` | Pitch Coarse / Fine | `18` / `19` |
| `02` | Level | `1A` |
| `04` | Pan | `1C` |
| `05` / `06` / `07` | Reverb / Chorus / Variation Send | `1D` / `1E` / `1F` |
| `0B` / `0C` | Filter Cutoff / Resonance | `14` / `15` |
| `0D` / `0E` | EG Attack / Decay 1 | `16` / `17` |

`[M]` Every controller number above is on the QY100's receive list, Data List
pp. 42 to 43 and the NRPN/RPN tables on pp. 47 to 48. `[D]` That each
controller lands on the same internal value as its XG address is how XG
defines them; not individually confirmed on this device.

### Why use the controller form

- **It can be recorded and edited.** CC, NRPN and RPN are ordinary channel
  events on a track. A remote editor that sends knob moves as controllers while
  the sequencer is recording should leave automation that can be edited on the
  device afterwards, where a SysEx message is at best one opaque event.
  `[V]` Neither real-time recording of incoming NRPN nor of incoming SysEx has
  been tested.
- **It follows the channel, not the part.** A Parameter Change is addressed to
  Multi Part `nn`; a controller goes to whichever parts have that Rcv Channel
  (`08 nn 04`). On the QY100 part and channel coincide by default, but a
  channel message stays right if they ever don't.
- **It is what the sequencer itself uses.** The Undo/Redo resync burst in
  `CLAUDE.md` is almost entirely CC 0/32, Program Change, CC 7, 10, 91, 93 and
  71 to 74, which is this table.

The trade-off: only the parameters in this table have a controller form. Effect
types and parameters, detune, note limits, element reserve and the rest remain
SysEx only.

## Following playback: a live mixer

The same table read backwards turns the QY100's MIDI Out into a mixer feed.
While a song or pattern plays with MIDI Out enabled, the device sends its
sequencer events, and every CC 7, 10, 11, 91, 93, 94 and 71 to 74 on channel N
is the current value of part N's volume, pan, expression, sends and sound
offsets. A remote editor can move its own knobs from that stream, and derive
per-channel activity meters from Note On velocities. Bank Select plus Program
Change tells it the current voice.

`[D]` Follows from the resync burst above, which shows the sequencer expressing
its mixer this way. `[V]` Whether MIDI Out carries these during ordinary
playback, and which MIDI settings gate it, has not been captured. `CLAUDE.md`
already establishes that `MIDI CONTROL` gates all transmission.

## Saving only what changed

Every Multi Part, Effect and Drum Setup parameter has a documented default
(`[M]` the Default value column, pp. 58 to 62). A setup worth saving can
therefore be written as XG System On followed by only the Parameter Changes
whose value differs from its default. That is much smaller than a full dump,
readable as a list of edits, and a good fit for embedding at the start of a
Standard MIDI File whose SysEx events the song converter then carries into a
song. Remember that XG System On itself resets everything, so it goes first and
nothing that should survive may come before it.

## The earlier live captures, decoded

The addresses in `qy100-remote-transmission-mapping/` sit inside the Variation
block and the Multi Part block of the XG tables. Reading them through the
layout above explains every result, including the negative one. `[D]` for all
of the following: the addresses are measured, the names come from the tables.

| Captured | Recorded as | XG name `[M]` pp. 59 to 61 |
| --- | --- | --- |
| `02 01 40` | Effect type | Variation Type (MSB, LSB) |
| `02 01 42` | Reverb Time | Variation Parameter 1 (2 bytes) |
| `02 01 44` / `46` / `48` / `4A` | Diffusion / Initial Delay / HPF / LPF | Variation Parameters 2 to 5 (2 bytes each) |
| `02 01 58` | Reverb Send | Send Variation to Reverb |
| `02 01 59` | Chorus Send | Send Variation to Chorus |
| `02 01 5A` | (no effect at `7F`) | Variation Connection, range `00..01` |
| `00 00 7E` (Undo burst) | not decoded | XG System On |
| `00 00 7D` (Undo burst) | not decoded | Drum Setup Reset |
| `08 0N 11` (Undo burst) | not decoded | Part N Dry Level |
| `08 0N 23` (Undo burst) | not decoded | Part N Bend Pitch Control |

So:

- **The "+2" layout** of the Variation Edit parameters is the XG layout: ten
  two-byte parameters from `42` to `55`. Parameters 11 to 16 are single bytes
  at `02 01 70` to `75`. Their meaning changes with the Variation Type, as the
  Effect Parameter List in the Data List shows; the Hall 1 names hold only for
  Hall 1.
- **"Reverb Send" and "Chorus Send"** on the FX screen are the Variation
  effect's own returns into the Reverb and Chorus blocks, not the per-part
  sends. The per-part sends are `08 nn 13` / `08 nn 12`, or CC 91 / CC 93,
  which is why both showed up separately.
- **`02 01 5A` did nothing at `7F`** because it is a two-value switch
  (insertion or system connection) and `7F` is out of range. The earlier
  conclusion that adjacent addresses aren't reliably related was right in
  spirit, but this particular address is real; test it with `00` and `01`.
- **The effect-type split at `40`** matches the XG Effect Type List: families
  below `40` are the reverb and delay types, `40` upward are the chorus,
  modulation, distortion and EQ types. The Variation block accepts both, which
  is why one selector reaches all of them.

## What to test first

In order, because each depends on the one before:

1. **Parameter Request answers.** Send `F0 43 30 4C 08 00 0B F7` and look for
   `F0 43 10 4C 08 00 0B vv F7`. If this works, reading device state and the
   ready handshake both work.
2. **Dump Request answers.** `F0 43 20 4C 02 01 40 F7` should return the
   33-byte Variation block; compare it with the FX screen.
3. **Bulk Dump is accepted.** Write that block back with one value changed,
   then read it again. Only the read-back proves it.
4. **Controller equivalents.** For CC 74 and NRPN `01 64`, send the controller,
   then Parameter Request the XG address and see whether it moved.
