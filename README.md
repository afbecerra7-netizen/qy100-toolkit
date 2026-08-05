# qy100-toolkit

Python tools and reverse-engineering notes for the **Yamaha QY100** (2000), a
hardware sequencer with an XG tone generator. Two independent subprojects:

| | |
| --- | --- |
| [`qy100-syx/`](qy100-syx/) | Read, decode, generate and write the QY100's user memory over SysEx. Also plays it live and exports standard MIDI. |
| [`qy100-arp/`](qy100-arp/) | External arpeggiator and generative sequencer driven by the QY100's MIDI clock. |

**[`CLAUDE.md`](CLAUDE.md) is the real documentation.** It records every decoded
field, how each one was established, and — deliberately — the conclusions that
turned out to be wrong and what corrected them. It is written to be read by an
AI agent as much as by a person: pointing Claude Code at this repository gives it
the whole picture in one file.

## What is decoded

The pattern and song formats are solved and verified against hardware.

- **Events**: variable-length note and time events over the 7→8 unpacked stream,
  with multi-block chaining. The grammar came out of Yamaha's own decoder inside
  the Data Filer, not from guessing.
- **Pattern header**: tempo, name, measures per section, **time signature
  including the denominator**, the two-table track registry, current chord per
  section, and the full mixer.
- **Song format**: the 16 sequencer tracks, the pattern track (`tr = 0x19`), the
  chord track (`0x1A`) and the 6-block header.
- **Reference data**, all generated rather than transcribed: 525 voices and 22
  kits pulled from the firmware ROM, the 4,285 preset phrases from the Data List.

Some things are still open — most of the 26-byte track prefix, writing
`SOURCE CHORD`, and the bank LSB for XG voices above program 127. `CLAUDE.md`
says which is which, and marks inferences as inferences.

## Three things that will cost you a session

All learned the hard way, all documented in full:

**Every track's event stream must start with `F0 00`.** Without it a pattern
plays back perfectly and then **hangs the pattern editor**, and each hang
corrupts the memory accounting until a clear-and-restore. Playback is more
forgiving than the editor — verify writes by opening them on the device.

**The header carries a two-table track registry.** Bytes 21–68 are presence
flags, 69–116 hold each track's `tr`. Correct track data with a stale registry
reads as **empty** on the panel: valid checksums, dumps back clean, plays fine,
and the device says there is nothing there.

**Send the whole object, in the order the device dumped it** — tracks first,
header last, framed by `bulk mode ON` / `OFF`. A single block on its own wipes
the pattern and freezes the device.

## Quick start

```bash
python3 -m venv qy100-syx/.venv
qy100-syx/.venv/bin/pip install -r qy100-syx/requirements.txt
qy100-syx/.venv/bin/python qy100-syx/test_protocol.py    # 117 checks, no hardware
```

```bash
cd qy100-syx
.venv/bin/python syx.py dump all --in "M4" --out "M4" -o dumps/backup.syx
.venv/bin/python syx.py inspect dumps/backup.syx
```

Read [`qy100-syx/README.md`](qy100-syx/README.md) before writing anything to the
device, and take a full `dump all` first.

## Not included

The manuals, the firmware image and Yamaha's Data Filer are cited throughout but
are not redistributed here — they belong to Yamaha and others. Reference dumps
and generated music are also left out. See the note at the top of `CLAUDE.md`.
