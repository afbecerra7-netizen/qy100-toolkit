# CLAUDE.md

> **This is the shareable subset of a larger working repository.**
>
> Not included here, and why:
>
> - **The manuals, the firmware image and Yamaha's Data Filer.** You'll already
>   have those; the page citations throughout still point at them and resolve.
> - **Most of the reference dumps** and all the generated MIDI (`midi/`). Not
>   needed to use the tools, and some contain unreleased music. The eight dumps
>   the test suite decodes **are** included, so the tests run; the suite reports
>   a lower total here than in the working repo for exactly that reason.
> - **An EP** that was produced with these tools. It belongs to someone else, so
>   only the technical measurements taken from it survive here — the memory
>   arithmetic, the note counts, the per-minute cost. Those are cited as "the EP".
>
> Everything else is here: the decoders, the generators, the live-play, screen
> and MIDI-export tools, and this document, which is the record of what is known
> about the format and how each piece of it was established.

Guidance for Claude Code (claude.ai/code) when working in this repository.

Tools and findings for the **Yamaha QY100** (hardware sequencer, 2000), in two
independent Python subprojects, each with its own `.venv`.

| Where | What it is |
| --- | --- |
| [`qy100-arp/`](qy100-arp/) | External arpeggiator and generative sequencer, over MIDI. [README](qy100-arp/README.md) |
| [`qy100-syx/`](qy100-syx/) | Dumping, decoding and writing over SysEx. [README](qy100-syx/README.md) |
| `Manuales/` · `manuales-md/` | Referenced throughout but **not included** — see the note at the top. Citations are by page number and still resolve against the real manuals |

```bash
cd qy100-arp && .venv/bin/python test_engine.py      # tests, no hardware
cd qy100-syx && .venv/bin/python test_protocol.py    # 162 checks — the last few
                                                     # read dumps/, so the total
                                                     # drops if those are absent
cd qy100-syx && .venv/bin/python test_regresiones.py # checks the checks bite
cd qy100-syx && .venv/bin/python medir_volcados.py   # recounts the cited figures
```

## The documents

This file used to be 1,146 lines mixing three unrelated subjects. It is now the
index; the detail lives one topic per file:

| Document | What's in it |
| --- | --- |
| [`docs/qy100-protocolo.md`](docs/qy100-protocolo.md) | SysEx, pattern and song format, factory phrases, firmware |
| *(not published)* | The studio inventory: what gear there is and on which channel. Personal information, of no use to a collaborator |
| [`docs/estilos-de-fabrica.md`](docs/estilos-de-fabrica.md) | The 128 factory styles with their full names |
| [`docs/musica-colombiana.md`](docs/musica-colombiana.md) | The measured rhythmic cells of each genre |
| [`docs/manuales.md`](docs/manuales.md) | Where each manual is and how to read it |
| *(not published)* | The plan for one particular live set. The memory measurements that came out of it are here, in the protocol document |
| *(not published)* | Plugin inventory of one particular studio |

## How certainty is marked

**Nearly every mistake this project has made has lived on the border between
what was measured and what was inferred**, and always for the same reason: a
coherent inference sounds exactly like a fact. Hence the marks:

```
[M]  measured against the device or against a primary source
[D]  deduced from something that is measured — coherent, unverified
[V]  unverified, or checked by a route that doesn't prove it
```

The three cases that illustrate it best, all real:

- **The time-signature denominator** was declared absent after sweeping four
  values of a three-bit field. Three values are valid and only one of them fell
  inside the sweep. **A partial sweep does not prove an absence.**
- **The DrumBrute's trigger parameter** was attributed to 102 because it was
  first in the list and read 0. It's 105. A one-datum hypothesis.
- **A file round-trip** was taken as proof that a program understood the format.
  A program that doesn't understand it and merely copies it produces the same
  result. **A round-trip only demonstrates comprehension if the output is
  generated.**
- **`451` control-change events turned out to be 10.** The count was of the byte
  `0xFB` anywhere in the stream — padding, prefix and misaligned tracks
  included — not of events reached by walking it. It carried a `[M]`, and it
  was measured; it just measured a different quantity than the sentence around
  it claimed. **A number is only as good as the question it answers**, so any
  figure a document cites now has to come out of
  [`medir_volcados.py`](qy100-syx/medir_volcados.py), which can be re-run.

And a corollary about tests, learned when three decoder fixes turned out to
share one suite that passed identically before and after all three: **a test
that cannot fail is a comment.** [`test_regresiones.py`](qy100-syx/test_regresiones.py)
puts each known defect back and requires that something goes red.

And the method that does work when a measurement depends on someone else's ear:
**ask for a comparison, not an absolute judgement.** Anyone can answer "is this
the same sound?"; almost nobody can answer "is that an F or an F sharp?". The
EP–40's pad map was solved that way after seven badly designed tests.

## Rules that keep things from breaking

All learned the hard way and detailed in the documents.

**When writing to the QY100** ([protocol](docs/qy100-protocolo.md)):

- The pattern goes **whole, and in the order the device dumped it** — tracks
  first, the 5 header blocks last. Reordering it wipes the pattern.
- Frame every write as `bulk mode ON → blocks → bulk mode OFF`. A loose block
  hangs the device.
- Every track starts with `F0 00`. Without it **the pattern sounds fine and
  hangs the editor**.
- `MIDI CONTROL = Off` to transfer, `In/Out` to play. Mutually exclusive.
- **Never send MIDI while someone is using the front panel.** It hangs.
- **Verify by re-reading and decoding events**, never by comparing bytes: the
  device re-serialises and returns 95 of 147 bytes different for the same data.
- Don't send `CLEAR` unless asked.

**In general, and this repeats across the whole rig**: a write reported as
successful proves nothing. The MOTU swallows writes silently, the QY100 ignores
them while playing, and the Minitaur's editor shows a list that may not be the
device's. **The only thing that proves state is reading it back.**

**And before blaming a device, power-cycle the interface.** It's the cheapest
check and it has resolved several false diagnoses. The next cheapest is asking
for `dump setup`: if it answers, the device and the cable are fine.

## Language

The owner's manual is in Spanish and the service manual in English, so
terminology appears in both. When quoting the owner's manual, keep the Spanish
term and gloss it — **the physical buttons are labelled in English**.

Documents that are published are written in English at the source, so that no
translation layer has to be maintained. `docs/equipo.md` and `PLAN-LIVESET.md`
stay in Spanish because they are never published.

## External resource

[QY100 Explorer](https://qy100.doffu.net/) — an active QY100/QY70 community. It
confirms that the productive route is **the data, not the firmware**: they get
out-of-range BPM and patterns above the cap by writing style files.

The project's public repository lives at
[`qy100-toolkit`](https://github.com/afbecerra7-netizen/qy100-toolkit) and is
synced with `sincronizar-publico.py`.
