# qy100-syx

> **English translation of [`README.md`](README.md).** Keep the two in sync — this file is
> not authoritative; if they disagree, the Spanish original wins. Command-line flag
> names (`--patron`, `--escribir`, etc.) are left untranslated below because they are
> literal arguments the script expects — do not translate them when typing a command.

Backup, analysis and SysEx authoring tools for the **Yamaha QY100**. They let you
preserve the device's SRAM, inspect dumps, and build patterns or songs that the
sequencer plays back with no computer attached.

The project started as a reverse-engineering utility. The pattern format is
already solved and verified against hardware; the current code can read and
write events, multi-block tracks, headers, sections, voices, mixer, time
signatures and chords. The song mode's main tracks are solved too.

## What it can do

- Back up songs, patterns, setup and guitar effects.
- Capture dumps started from the front panel.
- Inspect, validate and compare `.syx` files.
- Restore backups with prior confirmation.
- Generate euclidean or Markov phrases inside a pattern.
- Create a track that doesn't exist yet and register it in the header.
- Read and write a song's 16 MIDI tracks.
- Search the 525 documented normal voices and 22 kits.
- Play the tone generator live, without writing to its memory.
- Export to a standard MIDI file, the fast route into Ableton.

The implementation relies on the service manual, Table 1-9, dumps measured on
the device, and Yamaha's own Data Filer decoder.

## What's here

| File | What it's for |
| --- | --- |
| [`syx.py`](syx.py) | The main tool: dump, inspect, restore, generate, search voices. |
| [`tocar.py`](tocar.py) | Plays the tone generator in real time. **Here we are the clock master**, unlike in `qy100-arp`. Writes nothing to the device. |
| [`exportar_midi.py`](exportar_midi.py) | Writes a standard `.mid`. For moving notes into a DAW **it beats the transfer outright**: exact, instant, and never silently drops blocks. |
| [`extraer_rom.py`](extraer_rom.py) | Decodes the firmware ROM; `voces.json` came from this. |
| [`extraer_frases.py`](extraer_frases.py) | Extracts the 4,285 preset phrases from the Data List. Self-validating. |
| [`test_protocol.py`](test_protocol.py) | 117 checks, no hardware needed. |
| `probe.py` | Loose reverse-engineering probes. |

Reference data, all generated and verified, not hand-transcribed:

| File | Contents |
| --- | --- |
| [`voces.json`](voces.json) | 525 normal voices and 22 kits. **Only the first 128 are addressable**: past that they are XG variations whose *bank LSB* is not decoded. |
| [`frases.json`](frases.json) | The 4,285 preset phrases, by category, beat and number. |
| [`tambores.json`](tambores.json) | Note map for *Tambores de San Jacinto* (Tribe Instruments): 8 instruments, 32 articulations. Includes the L/R pairs, which are left and right hand — alternating them is what makes a pattern sound played. |

## Installation

From this folder:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Dependencies: `mido` and `python-rtmidi`.

## Connecting and preparing the QY100

```text
QY100 MIDI OUT  →  interface MIDI IN
interface MIDI OUT  →  QY100 MIDI IN
```

Before transferring:

- `HOST SELECT = MIDI`.
- The sequencer must be stopped and on the main screen.
- `MIDI CONTROL = Off` while dumping or writing SysEx.
- Don't touch the panel during the transfer.

`MIDI CONTROL = Out` or `In/Out` makes the QY100 emit close to 49 clock
messages per second. On long transfers that stream can cause silent block loss
even though the messages received have valid checksums.

## Usage

Connection arguments can be written before or after the subcommand. Port names
accept partial matches.

### Ports and backups

```bash
.venv/bin/python syx.py --list

# The 64 user patterns
.venv/bin/python syx.py dump patterns --in "M4" --out "M4"

# Everything that can be backed up
.venv/bin/python syx.py dump all --in "M4" --out "M4" \
  -o dumps/full-backup.syx

# A single pattern or song
.venv/bin/python syx.py dump pattern 1 --in "M4" --out "M4"
.venv/bin/python syx.py dump song 1 --in "M4" --out "M4"
```

Other targets: `songs`, `setup`, `effects`, `info-songs` and `info-patterns`.
Without `-o`, the result is saved under `dumps/` with a date and time.

If the device doesn't respond to a request, you can start the dump from the
panel instead and capture it:

```bash
.venv/bin/python syx.py monitor -o dumps/manual.syx --in "M4"
```

### Inspection and comparison

```bash
.venv/bin/python syx.py inspect dumps/full-backup.syx
.venv/bin/python syx.py diff dumps/before.syx dumps/after.syx
```

`inspect` separates the messages, names their addresses, checks lengths and
checksums, and flags destructive commands. `diff` groups changes by address and
offset; it was the main tool used to decode the format.

### Generating a phrase

Without `--escribir`, `generar` only prepares and previews:

```bash
# Euclidean rhythm E(5,16), Main A, PC track
.venv/bin/python syx.py generar euclid \
  --patron 1 --seccion 1 --pista 2 \
  --pulsos 5 --pasos 16 --nota 36 --tipo Bypass

# Reproducible Markov melody in C minor
.venv/bin/python syx.py generar markov \
  --patron 1 --seccion 1 --pista 4 \
  --root C --escala minor --octava 4 --semilla 42
```

To write, add the ports and `--escribir`. The program first reads the full
pattern, substitutes or creates the track, updates the header registry, orders
the tracks before the five header blocks, and asks for confirmation.

```bash
.venv/bin/python syx.py generar euclid \
  --patron 1 --seccion 1 --pista 2 \
  --pulsos 5 --pasos 16 --nota 36 --tipo Bypass \
  --in "M4" --out "M4" --escribir
```

Sections are `0=Intro`, `1=Main A`, `2=Main B`, `3=Fill AB`, `4=Fill BA`,
`5=Ending`. Tracks are `0–7`: D1, D2, PC, BA and C1–C4.

*(Flag reference: `--patron`=pattern, `--seccion`=section, `--pista`=track,
`--pulsos`=pulses, `--pasos`=steps, `--nota`=note, `--tipo`=type,
`--escala`=scale, `--octava`=octave, `--semilla`=seed, `--escribir`=write.)*

### Searching voices

```bash
.venv/bin/python syx.py voces Square
.venv/bin/python syx.py voces Kit
```

### Playing live

Writes nothing to the device's memory: it only sounds.

```bash
.venv/bin/python tocar.py barrido          # three notes on each of the 16 channels
.venv/bin/python tocar.py acompanar        # E minor backing to play guitar over
.venv/bin/python tocar.py andino --tono G  # huayno, transposable
```

Two device settings are mandatory. **`ECHO BACK` must not be `RecMontr`**:
with that set, the QY100 re-channels everything coming in to the selected
record track's channel, and the 16 channels collapse into a single voice — the
manual lists this as its own fault, page 143. And it's worth **choosing an
empty song**, because a Program Change rewrites the loaded song's mixer voice.

### Exporting to MIDI

```bash
.venv/bin/python exportar_midi.py ep-quiebre --cuantizar 16
```

The engines run at 480 clocks per quarter note, which is the file's
`ticks_per_beat`: the conversion is 1:1 with no rounding. `--cuantizar 16`
removes only `humanizar()`'s micro-timing jitter, because all deliberate
placement already lands on exact sixteenths. **Coarser quantizing destroys the
material**: it would drag the bass from sixteenth 3 onto the downbeat.

### Restoring

`send` writes to user memory and asks for explicit confirmation:

```bash
.venv/bin/python syx.py send dumps/full-backup.syx --out "M4"
```

## Solved formats

### Pattern

- Address `12 nn tr`; `tr = section × 8 + track`.
- Five header blocks and up to 48 tracks per pattern.
- 147-byte MIDI payload packed into 128 real bytes per block.
- Variable-length time and note events.
- Multi-block tracks, `F0 00` start marker and `F2` terminator.
- Name, tempo, measures per section, time signature, registry, chord and mixer.
- Up to 32 measures per section, even though the panel normally offers eight.

### Song

- Address `11 nn tr`.
- Sixteen sequencer tracks, one per MIDI channel.
- Pattern track `Pt`, chord track `Cd`, and a six-block header.
- Same note grammar as patterns, without the phrase prefix.
- Verified with a 112-measure song and over 3,000 notes.

The discovery record is in [`HALLAZGOS.md`](HALLAZGOS.md) (Spanish — "findings").
Its bottom section keeps historical hypotheses that later turned out wrong; for
current behavior, `qy100syx/patternfmt.py`, `qy100syx/songfmt.py`, the tests
and the root summary [`../CLAUDE.md`](../CLAUDE.md) are authoritative.

## Tests

```bash
.venv/bin/python test_protocol.py
```

**117 offline checks**, no hardware. Cover Data Filer addresses and templates,
message construction and parsing, checksum, corruption detection, 7↔8 packing,
real tracks, round-trip encoding, sections, headers and 32-measure files.

## Safety rules

1. Do a `dump all` before writing.
2. Never send a `CLEAR` to make room: writing a track already replaces it.
3. Every write must be framed by `bulk mode ON/OFF`.
4. Send the whole object, in the device's own order: tracks first, header
   last.
5. Don't transfer while the sequencer is playing or on an edit screen; the
   QY100 can ignore it without an error.
6. Verify by reading back and decoding events. The device may reserialize
   valid padding with different bytes.
7. Don't use the panel while `bulk mode` is active: the panel is locked, and a
   concurrent interaction may require a power cycle.

`send` warns which addresses it will overwrite, detects erase commands and
asks for written confirmation. The tool never generates `CLEAR` commands on
its own.
