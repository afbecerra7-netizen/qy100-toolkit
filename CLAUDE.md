# CLAUDE.md

> **This is the shareable subset of a larger working repository.**
>
> Not included here, and why:
>
> - **The manuals, the firmware image and Yamaha's Data Filer.** You'll already
>   have those; the page citations throughout still point at them and resolve.
> - **The reference dumps** (`dumps/`) and the generated MIDI (`midi/`). Not
>   needed to use the tools, and some contain unreleased music.
> - **An EP** that was produced with these tools. It belongs to someone else, so
>   only the technical measurements taken from it survive here — the memory
>   arithmetic, the note counts, the per-minute cost. Those are cited as "the EP".
>
> Everything else is here: the decoders, the generators, the live-play, screen
> and MIDI-export tools, and this document, which is the record of what is known
> about the format and how each piece of it was established.

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this directory is

Tools and findings for the **Yamaha QY100 hardware music sequencer** (released 2000), in two independent Python subprojects.

- `Manuales/` and `manuales-md/` are referenced throughout but **not included** — see the note at the top. Citations are by page number and still resolve against the real manuals.
- [`qy100-arp/`](qy100-arp/) — external arpeggiator + generative sequencer over MIDI. [README](qy100-arp/README.md)
- [`qy100-syx/`](qy100-syx/) — SysEx bulk dump / backup / restore. [README](qy100-syx/README.md)

Each has its own `.venv`; they are independent.

## qy100-arp

External arpeggiator + generative sequencer for the QY100, over MIDI. The QY100 has no arpeggiator (verified — zero hits for "arpegio"/"arpeggio" in both manuals), so this adds one from outside without touching firmware.

```bash
cd qy100-arp && .venv/bin/python test_engine.py     # tests, no hardware needed
```

```bash
cd qy100-arp && .venv/bin/python run.py --list      # show MIDI ports
```

Key design constraint: **everything is driven by incoming MIDI Clock ticks (24 PPQN), never by a local timer.** The QY100 is the master; the engine follows. That is why it can't drift. Song Position Pointer repositions the absolute tick counter so patterns align to the sequencer's bars. Don't introduce independent `time.sleep`-based scheduling into the engines — it would break sync.

Divisions all land on integer ticks at 24 PPQN (`1/16` = 6, `1/8T` = 8, etc.), so step timing is exact.

Three QY100 settings are mandatory or nothing works — `MIDI SYNC=Internal`, `MIDI CONTROL=Out`/`In/Out`, `ECHO BACK=Off` (manual pp. 127–128). The last one prevents a feedback loop.

## qy100-syx

```bash
cd qy100-syx && .venv/bin/python test_protocol.py       # 50 checks, no hardware
```

```bash
cd qy100-syx && .venv/bin/python syx.py dump patterns --in "FastTrack" --out "FastTrack"
```

**Tracks can be created from nothing.** `generar` used to require the target track to already exist, because it needed that track's 26-byte prefix. It now builds one with `patternfmt.build_prefix()`, copying an existing track's prefix from the same pattern (so the still-undeciphered bytes come from the device, not from us) and setting name, measures, `--voz`, `--tipo` and `--fuente`. `PREFIJO_BASE` is the fallback for a completely empty pattern and is a verbatim capture from the device, not a guess. Verified: a new `PC` track appeared at `12 00 0A` with 15 euclidean notes and the requested settings.

The pattern's 8 tracks are **D1, D2, PC, BA, C1–C4** (indices 0–7) — drums, percussion, bass, then four chord tracks. Put euclidean rhythms on D1/D2/PC with `Bypass` and melodic material on C1–C4 with `Chord 1`.

**Prefix byte 19 depends on the track's role**, and getting it wrong makes the device list the track as *empty* even though the data is stored, dumps back intact, and plays. **Measured for all eight tracks** (2026-08-02) by recording one note on each from the panel and dumping:

```
D1 = 7   D2 = 7   PC = 3   BA = 3
C1 = 7   C2 = 7   C3 = 7   C4 = 7
```

Only `PC` and `BA` take 3. The C1–C4 run included `BA` as a control and it returned the 3 already on record, so the procedure is sound rather than the numbers being a coincidence. `build_prefix(pista=...)` sets it.

That still leaves the flaw in copying a prefix from an existing track: it carries role-specific bytes with it. The same dumps show **byte 20** (phrase type) and **byte 16** (phrase voice) also assigned by role — `BA` came back `92` `Bass` with voice 32 (`Aco.Bass`), the four C tracks `90` `Chord 1` with voice 0 (`GrandPno`). So copy from a track of the same role, or set the fields explicitly.

**The end-to-end goal is met** (2026-07-29): `syx.py generar markov|euclid` renders the generative engines from `qy100-arp` into a pattern track and writes it as a user phrase — verified by ear, a 35-note C-minor Markov melody across two chained blocks playing off the device with nothing attached. Without `--escribir` it only previews. It reads the target pattern first, because it needs that track's 26-byte prefix (still undeciphered) and the section length from the header.

The engines run at 24 PPQN and the QY100 at 480 clocks per quarter — **exactly 20 clocks per tick**, so the conversion is an integer multiple with no rounding.

Playback is subject to the track's `TYPE` (phrase table, [MENU] → "Edit" → [MENU] → "Phrase Table" from normal pattern mode): `Bypass` plays the literal notes, `Chord 1`/`Chord 2` reharmonize against the chord track. Set `Bypass` to hear exactly what was generated. Yamaha's chord notation distinguishes case — `CM7` is C major seventh, `Cm7` is C minor seventh.

**`CURRENT CHORD` is decoded, and it is per-section** — pattern header block 0, two arrays of six indexed by section: **roots at bytes 117–122, types at 123–128**. The single byte pair first measured (118/124) was Main A's, which is section 1; reading it as a pattern-wide setting was the second wrong label this field got.

The symptom that exposed it: after setting "the pattern's" chord to `Cm7`, the panel still showed `CM7` on Main B and its melody played major — source chord `Cm7` against a current chord of `CM7` makes `Chord 1` transpose minor to major. The array hypothesis was then confirmed offline against an existing dump, which read back `Main A = Cm7` and the other five `CM7`, matching exactly what the panel showed.

Earlier notes, superseded: pattern header, block 0, byte 118 (root, semitones with C=0) and byte 124 (chord type). Measured three times with nothing else moving: `CM7` = `00`/`00`, `Fm7` = `05`/`08`, `G7` = `07`/`0D`. **All 27 chord types are now measured** — five rounds of writing six distinct values across the six sections and reading the panel back: `M7` `M` `6` `m7(11)` `M7(9)` `add9` `m` `m6` `m7` `m7(b5)` `mM7` `m7(9)` `madd9` `7` `7(#5)` `7(b9)` `7(9)` `7(#9)` `7(#11)` `7(b13)` `7(13)` `7sus4` `sus4` `dim` `aug` `6(9)` `7(b5)`, values 0–26 with no gaps. The order does **not** group by family — index 3 is `m7(11)`, a minor chord sitting between `6` and `M7(9)` — so none of them could have been inferred. Past 26 the panel renders garbage (`Con`, `C ^`, `C(9)mn`): it reads beyond its own name table without clamping or complaining, so range validation has to live in our code. `patternfmt.set_current_chord()`.

This was first labelled `SOURCE CHORD` and that was wrong. Both fields sit on the same Phrase Table screen, so a request to "change SOURCE CHORD" changed the neighbouring field instead. What settled it: after writing `Cm7` to these bytes, the device's **main** screen read `Cm7` while the Phrase Table still read `SOURCE CHORD = CM7` — the bytes follow the main screen. It also fits their location, since the header is per-pattern while `SOURCE CHORD` is per-phrase. **`SOURCE CHORD` is still unlocated.** When a decoded field's name comes from a screen that shows several similar values, confirm which one the device echoes back before naming it.

**`PHRASE VOICE` is decoded** — prefix byte 14 (bank: `7F` drums, `00` normal) and byte 16 (program, zero-based: `Dr010` → 9, `Ld081` → 80). This is the voice stored *in the phrase*; what actually sounds is the **track** voice, which overrides it (manual p. 57).

**And the track voice is writable too** — the whole pattern mixer lives in the header, in 8-byte arrays (one entry per track) starting at byte 154: **program at 154–161**, a drum flag at 162–169, **volume at 170**, **pan at 178** and **reverb send at 202**.

Those last three were long identified only by their default values (100, 64, 40). **Measured 2026-08-02**: setting C1 volume to 20, C2 pan hard left and C3 reverb to 127 from the panel changed exactly three bytes in the whole header — 174, 183 and 208, i.e. index 4, 5 and 6 of each array. No side effects anywhere else.

A second round measured the sends, and **corrected a guess made from position alone**: setting C4 chorus to 127 and BA variation to 90 moved bytes 201 and 213, so **chorus is at 194 and variation at 210 — after the reverb, not before it.** The full mixer:

| Base | Field | Default | How |
| --- | --- | --- | --- |
| 154 | program | — | measured |
| 162 | drum flag | 1 on D1/D2/PC | measured |
| 170 | volume | 100 | measured |
| 178 | pan | 64 | measured |
| 186 | dry level | 127 | **inferred** from value and XG order |
| 194 | chorus send | 0 | measured |
| 202 | reverb send | 40 | measured |
| 210 | variation send | 0 | measured |
| 218 | ? (note shift?) | 64 | **unidentified** |

The order matches the XG multi-part spec exactly — volume, pan, dry level, chorus, reverb, variation — which is what makes 186 a confident inference rather than a shot in the dark. It is still not measured.

**Pan hard left reads 1, not 0** — because **0 is `Random`**, an XG feature where the voice is placed differently on every note. Writing 0 for "hard left" would produce a voice that jumps around instead. Felipe spotted the `Random` entry on the panel; the byte confirmed it.

**And the panel does not show the byte.** It displays the musical position, `L63 … C … R63`, so hard left reads `63` on screen while the byte is `1`:

```
byte   1 = L63      byte  64 = C      byte 127 = R63      byte 0 = Random
byte = 64 + position
```

The two differ by 64. Reading `63` off the panel and writing 63 into the byte gives a voice slightly left of centre — wrong in a way that sounds plausible, which is the kind of error that survives review. Confirmed by a single anchor: the mixer showed `Dr010 DarkRKit` on D1 alone and byte 154 read 9, Dark Room Kit's program; writing 25 there made the panel show `Analog Kit`. `patternfmt.set_mixer_voice()`, and `generar` now sets both layers so they cannot contradict each other. Note the mixer is **per pattern, not per section**.

This closes the gap that looked worst all session — the assumption that the sounding voice lived outside the pattern and was unreachable by SysEx. It was forty bytes past where we had stopped reading.

**`SOURCE CHORD` is per-track** — prefix byte 21 (root, C=0) and byte 22 (type, same table as the current chord). Reading is verified; writing is not, because changing it from the panel also moves header block 3 byte 75, a byte that shifts with phrase type, chord root and chord quality alike — it packs several fields and is not isolated.

A methodological correction worth keeping: byte 16 was first attributed to chord quality because it moved during the source-chord test. It is the phrase-voice program, and it moved because *opening the Phrase Table* made the device write the track's real voice into it. **In a diff, a byte that changes at the same time as your edit is not necessarily caused by your edit** — entering an editor is itself an action with side effects.

**`TYPE` is decoded** — prefix byte 20, measured for all five values (`Bypass` `03`, `Chord 1` `90`, `Bass` `92`, `Parallel` `94`, `Chord 2` `A0`), plus a bit (`0x08`) in the pattern header at block 3 byte 75 that is set only for `Chord 1` and `Bass`, exactly the pair the manual says `HI KEY` applies to. `patternfmt.set_phrase_type()` / `set_header_hikey()` reproduce the device's own bytes in all five states. Treated as a lookup table: `Bypass` and `Chord 2` do not fit the bit pattern the other three share, so the arithmetic is not invented. The header bit's offset was measured only for Main A track 0 — re-measure before writing it for another track.

Protocol comes from the service manual §(3-6-3) and Table 1-9 — both hand-corrected in the Markdown. Addresses use `P=1` for QY100 (`0x12 nn tr` = user pattern), `P=0` for QY70; that single nibble is the whole difference between the two machines' style files.

### Verified against the hardware (2026-07-28, MOTU M4 interface)

- **Checksum is `bytecount+addr+data`** — two's complement, 7-bit. Confirmed on 60+ real messages, zero failures. No longer a guess.
- **`bulk mode ON` is mandatory** before any dump request — **and before CLEAR commands too**. Without it the QY100 silently ignores them. A bare `CLEAR ALL` left every pattern intact; the same message wrapped as `bulk ON → CLEAR ALL → bulk OFF` wiped the device. The manual lists the flag but never says it is a precondition.
- **Memory usage can be estimated from the dump at 128 bytes per block** (the unpacked block size) against 128 KB of SRAM. Two rough checks agreed with the device: 329 blocks predicted 32% and the bar looked about that; 367 blocks predicted 36% and the bar looked like 40%. **`USED MEMORY` is a bar with no number**, so it cannot confirm the model to better than several points — it is consistent with it, not proof of it. Use the estimate for planning and the bar for reassurance, and do not read a discrepancy into the gap between an exact figure and an eyeballed one. At the density of a 112-measure track with 16th-note hats (159 blocks), roughly 6 songs fit; sparse material goes much further. The 128 KB is shared by songs, patterns, phrases and effects, and the 20-song slot limit bites first for short pieces.
- **Written-out music costs ~3.5 KB per minute, and that does not scale to a live set.** Measured on the EP: 12.4 minutes across four songs = 343 blocks = 43 KB = 33%. Extrapolated, **40 minutes is 108% of memory and an hour is 162%** — a set cannot be written out as songs at any density we have used. The asymmetry that solves it is that **a song costs memory proportional to its duration while a pattern costs memory proportional to its material and then loops indefinitely**; a loaded 6-section style is ~18 KB and plays as long as you keep it running. So long-form performance belongs in pattern mode and fixed arrangements in song mode, not by taste but by arithmetic.
- **The rhythm tracks are 64% of that weight** (218 of 343 blocks on the EP) — 16th-note hats are the densest thing a track can hold. Moving percussion to an external drum machine with its own sequencer and memory roughly triples what the QY100 can hold. Dropping the drum tracks takes a playable style from ~18 KB to ~9 KB and the whole EP from 43 KB to 16 KB.
- **An interrupted bulk transfer can corrupt the memory accounting.** After a hang, `USED MEMORY` read full with only 47 notes stored, and pattern edit refused with `Memory Full` — while the data itself dumped clean, with valid checksums and sane lengths. The repair is a framed `CLEAR ALL` followed by restoring a backup. Take a full `dump all` first: it is 33 messages and a few seconds.
- **Never drive MIDI while someone is using the panel.** `bulk mode ON` locks the front panel by design, so a dump request issued while the user is navigating menus puts the device in two states at once. Doing exactly that hung it: a clock/busy icon stuck on the display, unresponsive to the panel and to MIDI, not cleared by repeated `bulk mode OFF` — a power cycle was needed. Either the tool is talking to it or the human is, never both.
- **`bulk mode` locks the front panel.** Leave it on and the device appears dead to its own buttons — `dump` now always sends OFF in a `finally`, including on failure.
- **A panel-initiated dump is self-framing**: `bulk mode ON → CLEAR ALL → data blocks → bulk mode OFF`. The CLEAR ALL is part of the payload so a restore wipes before writing. That framing also makes it possible to split a capture containing several dumps.
- **`MIDI CONTROL` must be `Off` while dumping** (2026-07-29). With it on, the QY100 emits ~49 clock messages per second continuously and bulk captures lose whole blocks: the same pattern returned 8 blocks, then 3, then 2, then a different subset each attempt — the 5-block pattern header came back as 2. Everything that arrives is well-formed with a valid checksum, so it looks like the data changed rather than like loss. Filtering the clock in the driver (`rtmidi.ignore_types(timing=True)`, now applied automatically in `transfer.silenciar_reloj`) is **not sufficient** — it must be turned off at the device. Practical workflow: `In/Out` to sync a recording, `Off` to dump.
- **Antes de culpar al QY100, apaga y enciende la interfaz.** Tras una transferencia larga la interfaz USB-MIDI puede quedarse con el puerto a medias y desde el software se ve exactamente igual que un aparato que no contesta: el volcado de verificacion no recibe respuesta y las pistas no salen por MIDI OUT aunque suenen. Ciclarla lo arregla. Costo dos diagnosticos falsos el 2026-08-08 —se reviso `MIDI CONTROL`, la pantalla del panel y el cableado— porque el sintoma es indistinguible de los fallos reales que si estan documentados aqui. **Es la comprobacion mas barata y va primero.**

- **The QY100 transmits MIDI Clock even while stopped.** So incoming clock is *not* evidence that the sequencer is running, and no tool should infer "playing" from it. A recording script that auto-started after seeing clock without a Start fired 32 notes at a device sitting in the utility menu and recorded nothing. Wait for an actual Start.
- **Capture must be callback-driven, not polled.** The QY100 streams MIDI clock continuously (48 ticks/s) and that flood makes a polling loop drop whole SysEx messages. The symptom is deceptive: everything that arrives is well-formed with a valid checksum, only some blocks are missing. The tell was that single-block items (setup, guitar effect) came back identical every time while anything multi-block varied.
- Identical payloads legitimately appear under different addresses — empty patterns share the same `7F` header block. That is not corruption.

- **The QY100 is deterministic** — five consecutive `setup` requests returned identical bytes once the device was cleared. The earlier chaos was volume: long multi-block transfers were losing whole messages under the polling capture. Small dumps were always reliable, which is why single-block items (setup, guitar effect) matched every time.
- **An empty pattern or song returns nothing at all.** That makes a cleared device the ideal reverse-engineering baseline: there is no background to subtract, so anything that appears after recording is the recorded data.
- **`CLEAR ALL` also resets the utility settings** — it silently reverted `MIDI CONTROL`, which stopped clock transmission. Re-check page 127/128 settings after any clear.

### The Data Filer is the ground truth

`QY100DataFiler/` holds Yamaha's official Windows utility (2002). Extract it with `unshield x DATA1.CAB`; the payload is `English_Files/QY100.exe` plus `Program_Dll_Files/MidiCtrl.dll` (the DLL is only a Windows MME wrapper — the protocol lives in the exe).

**`QY100.exe` at offset ~214600 contains Yamaha's own SysEx message template table.** It confirmed every address and ByteCount we had derived from the service manual, and corrected one thing: in `CLEAR SONG` / `CLEAR PATTERN` the item number goes in the **data byte**, not the address, with `0x7F` meaning all — the templates carry `ff` there as a substitution marker. `test_protocol.py` now asserts our output byte-for-byte against those templates. When a protocol question comes up, check this table before guessing.

The extracted `QY100DataFilerManual.pdf` is converted in `manuales-md/`; it documents that a bulk file can be split into individual songs and styles.

The 7-bit packing scheme is still undetermined; `inspect --unpack` tries 7-in-8 and nibble. Do not hardcode it until a real dump settles it.

`diff` is the tool for deducing the pattern format: clear a pattern, record one known note, dump, diff. It isolates exactly which bytes encode what. This is safe to iterate on — user data is freely erasable, nothing like firmware work.

### Song format — the pattern track is solved

[`songfmt.py`](qy100-syx/qy100syx/songfmt.py). Songs live at `11 nn tr`. The **pattern track `Pt`** — which style and section play in each measure — is at `tr = 0x19` (25) and, unlike pattern tracks, carries **no 26-byte prefix**: the event stream starts at byte 0.

```
F0 00     start (same marker as pattern tracks)
F4 nn     user style nn+1      (U1 → F4 00)
F5 nn     preset style nn+1    (001 → F5 00)
F3 nn     section 0–5
C0 01     measure separator — between entries, not after each
F2        end
```

`F4` and `F5` being distinct events, rather than ranges of one byte, is what lets a song mix the 128 factory styles with the 64 user ones unambiguously. Measured by building a song measure by measure on a freshly cleared device, so everything that appeared was what had just been entered; `F3 05` for `Ending` confirmed the section numbering with a jump from 2 to 5. `encode_pattern_track` reproduces the device's bytes exactly, not merely equivalent events.

Two of these — `F3` and `F4` — were on the "states the binary gives a length but we have never seen in data" list.

The song header is **6 blocks** (patterns have 5) and shares layout: tempo at bytes 0–1 in tenths of a BPM, name at bytes 10–17 (patterns put it at 6–13).

The **chord track `Cd`** is at `tr = 0x1A` (26), also without a prefix:

```
F0 00                     start
D0 <root> <type> 0C 1C    one chord
80 04                     advance one measure (4 beats)
F2                        end
```

**Root and type use the same encoding as patterns** — root in semitones with C=0, type per `CHORD_TYPES`. Measured with three chords chosen to separate the fields: `Cm7`/`Fm7` share a type and change root, `Fm7`/`G7` change both. All three landed exactly, so the 27-type table transfers to songs unchanged. The trailing `0C 1C` is constant in everything measured and **unidentified** — copied verbatim, not synthesised.

Both decoders reproduce the device's bytes exactly, so a song can now be written end to end from software.

The song's **16 sequencer tracks** are at `tr = 0..15`, one per MIDI channel, and use the **same note grammar as pattern tracks with no 26-byte prefix** — the stream starts at byte 0, like `Pt` and `Cd`. Verified: a 112-measure song with 3,541 notes across four tracks, the longest chaining 91 blocks. This is the route for long material — no sections, no 32-measure ceiling, and each track lands on its own channel for a DAW.

The **song mixer** mirrors the pattern one with arrays of 16: program at 64–79, drum flag at 80–95, volume at 96, pan at 112, reverb at 160. Found by parallel structure, not measured directly. A freshly written song sounds entirely like piano until this is set, because program 0 is `GrandPno`.

**The "send the whole object" rule applies to songs too**, and it is easy to forget after decoding a header field: writing just the 6 header blocks to install the mixer **wiped all four tracks**. Same failure as the pattern case. Build tracks and header together and send them in one framed transfer, tracks first.

### Exporting a song to a DAW — verified (2026-07-31)

**The QY100 streams its song tracks over MIDI, one per channel, and Ableton records them as separate tracks.** Verified end to end with the EP: Ableton as clock master, and pressing record there starts the QY100 and captures every track in one pass.

Yamaha's own procedure for this (manual p. 126–127) is three settings, and it is what was used:

- `MIDI Sync` = **External** — the QY100 follows the incoming clock instead of its own. This is what keeps a long take from drifting; the EP's tracks run 64–112 bars.
- `MIDI control` = **In** or **In/Out** — lets the DAW's transport start and stop the sequencer.
- `Rec Count` = **OFF** — otherwise the count-in offsets the whole recording by a bar.

**This is the exact inverse of the dump configuration.** `MIDI CONTROL` has to be `Off` to transfer SysEx, because with it on the QY100 floods ~49 clocks per second and bulk captures silently lose blocks; it has to be `In/Out` to play into a DAW. One setting, two workflows that cannot both be active — decide which one you are doing before touching anything.

It also settles the architectural bet behind the EP: **writing songs with one part per MIDI channel is what makes them exportable.** The 16 song tracks arrive in the DAW already separated, so no de-interleaving is needed afterwards. Patterns would not have given this — they are 8 tracks tied to sections.

**Song Position Pointer works, so the DAW can start anywhere and the QY100 lands on the same bar** — verified. Relocating Ableton's transport and hitting play reproduces exactly that part of the song, with no rewind to the top. Service manual §(3-3-1): `F2H`, 14 bits, *"transmitted when you move to a different measure in SONG PLAY Mode, **received when in SONG PLAY Standby**"* — so the reposition is taken while stopped, which is what a DAW does anyway (SPP, then Continue `FB`, not Start `FA`).

The unit is a **MIDI beat = 6 clocks = one sixteenth**, counted from the start of the song. 14 bits caps it at 16,384 sixteenths = **1,024 bars in 4/4**, far beyond the EP's longest at 112.

This closes a symmetry with [`qy100-arp/`](qy100-arp/), which uses SPP the other way round — repositioning its absolute tick counter so patterns align to the QY100's bars when the QY100 is master. The same mechanism holds with the QY100 as slave.

`SONG SELECT` (`F3H`) is also **received** in song play standby, so which of the 20 songs is loaded can be switched remotely. Not the same `F3` as the section event in the song pattern track — that one is a byte inside bulk dump payload, unrelated to live MIDI status bytes.

### Pattern format — SOLVED

[`qy100-syx/HALLAZGOS.md`](qy100-syx/HALLAZGOS.md) is the record; [`patternfmt.py`](qy100-syx/qy100syx/patternfmt.py) is the implementation. The event grammar came out of Yamaha's own decoder inside `QY100.exe` (the Data Filer) and is independently verified against all eight reference dumps.

**Unpack first.** The 147 seven-bit payload bytes concatenate to 1029 bits; take **1024 = 128 bytes of 8 bits** and discard the last 5, **per block**. On that unpacked stream the fields *are* byte-aligned. Every earlier attempt failed because we were reading the stream in 7-bit units, which made fields look like they started mid-byte.

**Events are variable length**, starting at unpacked byte 26, identified by a status byte:

| Status | Bytes | Meaning |
| --- | --- | --- |
| `8n`–`9n` | 1 | time, delta = `status & 0x1F` |
| `An`–`Bn` | 2 | time, delta = `((status & 0x1F) << 7) \| b1` |
| `Cn` / `Dn` / `En` | 3 / 4 / 5 | note; gate in the low nibble, extended by following bytes; then pitch, velocity |
| `F2` | 1 | end of track |

**Duration is gate time in clocks, not a figure index.** The QY100 defaults to 90% of the note value — a 16th (120) gives gate 108, a quarter (480) gives 432.

Also verified: `tr = section * 8 + track` in the address (Intro=0, Main A=8…).

**Time signature is fully solved** — the whole thing lives in **header byte 14**:

```
byte 14 = ((numerator - 1) << 3) | (16 / denominator)

    /4  -> low bits 4        numerator = (byte >> 3) + 1
    /8  -> low bits 2
    /16 -> low bits 1
```

Verified against **all 40 of doffu's hidden-time-signature files, zero mismatches** — numerators 17–32 across the three denominators. Only byte 14 differs between `TS17-4`, `TS17-8` and `TS17-16`; the other two changed bytes are the pattern name.

Because 3 bits cannot hold the 8 that `/2` would need, **the format admits only /4, /8 and /16** — which is exactly the three sets doffu publishes. The byte's structure explains the catalogue.

**Why this looked unsolvable for so long is the lesson.** An earlier sweep wrote 0, 3, 4 and 7 into those bits with the numerator fixed, and the panel showed `/4` every time — read as "the denominator isn't here". But the valid values are 1, 2 and 4: three of those four probes were invalid (the device falls back to `/4`), and the one valid probe *was* `/4`. The panel was telling the truth throughout. **Three bits is eight values; sample four of them and a null result means nothing.** Sweep the whole range of a small field.

Block 3 byte 59 also moves with the signature but shifts with the numerator too, so it is derived rather than a second home. `patternfmt.set_time_signature_numerator()` — now incomplete, and should gain the denominator.

Measuring this needed a detour: **the panel only lets you set the time signature on an empty pattern** (manual p. 58), so it took creating two fresh patterns — one 3/4, one 4/4, each with a single recorded note — and diffing their headers, which differed in exactly two bytes. When the panel refuses to change a field, the inverse works: write candidate values by SysEx and read what the display reports.

**The pattern header carries a two-table track registry, and writing tracks without it is invisible to the device** (2026-07-29). Two parallel 48-byte tables of 8 slots × 6 sections, back to back in the first header block:

- **bytes 21–68** — flags: `F8` the track has content, `FE` empty
- **bytes 69–116** — the `tr` value (`section*8 + track`) of each present track, `0` when empty

Six sections were written, dumped back complete with valid checksums and correctly decoded notes, and the panel still showed only Intro and Main A — the two the *device itself* had registered. Writing the `tr` table alone changed nothing; both tables are required. `patternfmt.set_registry()` writes them and `generar` now updates them on every write.

This is the third layer of the same trap, after the mandatory `F0 00` and the role-dependent prefix byte 19: **the QY100 keeps metadata about the data, and correct data with stale metadata reads as absent.** Every check available on the wire says green; the only signal is what the panel shows.

**Pattern header** (`tr=0x7F`, first block, unpacked): **bytes 0–1 are the tempo in tenths of a BPM**, big-endian (120.0 = 1200 = `04 B0`) — found by simply noticing the default value sitting in plain sight, and confirmed by writing 1040 and reading 104 on the panel. Bytes 6–13 are the 8-character name, bytes 15–20 are **measures per section minus one**, in `SECTIONS` order. Decoded by diffing our dumps against QY100 Explorer's 32-measure unlock file (`doffu/32measures/`). The "unlock" is nothing more than writing a value above what the UI allows — the device honours up to 32 while its own interface caps at 8. Their warning holds: once you lower the length from the panel you cannot raise it again without reloading the file.

**The 32-measure unlock is verified end to end** (2026-07-29), written by us rather than loaded from doffu's file: a 5-track generative pattern at 32 measures — 825 notes across 46 chained blocks — plays in full. Write the header's measures field *and* regenerate every track at the new length, or header and tracks disagree. This is only possible because multi-block chaining was solved: at 16 notes per block, a 32-measure pattern cannot be written at all.

The panel's length counter renders the value with a **single digit**, so 16 displays as `6` and 32 as `2` (`1/2` = bar 1 of "32"). Purely cosmetic — playback honours the real value. Worth knowing, because the display looks like the write failed when it did not. Neither the manual nor doffu mention it.

**The `.q1p` file format is solved, and it is the better channel for reverse engineering** (2026-08-02). Comparing doffu's `MEASR32.Q1P` against their own `Measr32_QY100.syx` of the same pattern:

```
offset 0     16 bytes   "YQ1PAT     V1.00"   magic + version, ASCII
offset 114    2 bytes   big-endian length of the meaningful payload (546)
offset 128    N bytes   the blocks, ALREADY UNPACKED to 8 bits
```

The body is **byte-for-byte the same data our decoder produces after `unpack()`** — 640 bytes for a 5-block pattern header, differing only in the pattern name and in padding past the declared length. So `patternfmt` reads a `.q1p` directly with the 7→8 step skipped, and both files decode to 32 measures in all six sections, confirming bytes 15–20 by an independent route.

The length field at 114–115 is inferred from a single file: 546 is exactly where the two files stop agreeing. Re-check it against another `.q1p` before relying on it.

Practically this matters a lot: **a SmartMedia card reader turns every experiment offline.** No `bulk mode`, no panel lock, no clock flooding the capture, no half-written transfers corrupting the memory accounting, no power cycles. Diff-and-extrapolate on files is what doffu has been doing all along, and it is strictly safer and faster than doing it over SysEx. SysEx remains necessary for playing the device live and for songs; for *decoding pattern structure*, files win.

That file also settles two protocol points: **`nn = 0x7E` targets the currently selected slot** rather than a pattern number (hence their instruction to navigate to an empty user slot first), and their QY70 build is byte-identical except `02` for `12` — independent confirmation of Table 1-9's `P=1`/`P=0`.

**A cautionary note that cost this project a lot of time.** Before finding Yamaha's decoder we had a bitstream model with passing tests that was wrong: velocity read 56/16 when the real values are 112/32 (we were reading 7 bits of an 8-bit value), and the duration field read 27/204 — a misaligned read of gates 108/432. The tests passed because they compared our decoder against its own output. **A decoder validated only against its own reads validates nothing.** It took an external reference to catch it.

**Generating a pattern from scratch works and is verified by ear** (2026-07-29) — a 12-note C-major arpeggio built entirely in software, not edited from a dump, played back correctly in Main A. Two consequences:

- **Writing a block replaces the track, it does not merge.** The two notes previously in that track vanished with no `CLEAR` sent. So never send a CLEAR to make room — it is destructive and unnecessary.
- The 26-byte block prefix can be reused verbatim from a real block. Still undeciphered, no longer blocking.

**A block holds at most 16 notes.** 128 unpacked bytes − 26 prefix − 3 terminator = 99 usable; 6 bytes per note at delta > 31, 5 when delta ≤ 31, 4 for staccato with gate ≤ 15. Longer tracks chain blocks — **solved and verified** (2026-07-29) by recording 32 known ascending pitches over MIDI and reading back exactly 48…79:

- Only the **first** block carries the 26-byte prefix; the rest are pure continuation from their byte 0.
- The `F2` terminator appears **once**, at the end of the last block.
- The last block's tail is padded with `0x40`.
- The 7→8 unpack (discard 5 bits) is **per block**, not continuous across the track.

`patternfmt.encode_blocks()` implements this.

**Every track's event stream must begin with `F0 00`** — verified 2026-07-29, and the most expensive lesson of the session. Every device-recorded track starts with it, including an empty one (`F0 00 | t+3840 | F2`). Tracks written without it **play back perfectly but hang the pattern editor**: entering edit froze the display on the busy icon, requiring a power cycle, and each hang left the memory accounting corrupted so `USED MEMORY` read full and edit then refused with `Memory Full`. Two full clear-and-restore cycles were needed to get back.

The trap is that playback tolerates the omission. The arpeggio sounded correct immediately, which made the missing marker look like a cosmetic detail — it was the defect. **Sounding right does not mean the data is well-formed; the player is more forgiving than the editor.** Verify a write by opening it in the device's editor, not only by ear.

**Writing works and is verified end to end** — a modified pattern was sent and the device played the changed note. Three rules, none of them in the manual:

- Frame every write as `bulk mode ON → blocks → bulk mode OFF`. A lone block **wipes the target pattern and hangs the device** until it receives a `bulk mode OFF`.
- **Send the whole pattern, in the order the device dumped it.** Two failures established this, both on writes that passed pre-flight:
  - Two correctly-framed blocks for a *single track alone* froze the device outright — dead display, deaf to panel and MIDI, not recoverable by `bulk mode OFF`. Needed a power cycle.
  - Sending all the pattern's blocks but **reordered** (the rebuilt track appended after the header blocks instead of in its original position) left the device responsive but **wiped the pattern**. The QY100 dumps tracks first and the 5 header blocks last; that order is part of the contract.

  Read the pattern, substitute the track's blocks *in place* in the message list, send the lot. Restoring a dump verbatim always works, which is what made the ordering the obvious suspect. The same trap bit again when adding a track that did not exist yet: with no block to substitute, the new one landed at the end, after the header, and wiped the pattern. Group explicitly — all track blocks first, the 5 header blocks last — rather than relying on the order of a substitution loop.
- **While the sequencer is playing, the QY100 ignores both dump requests and writes — silently.** A 47-block write sent during playback was discarded with no error; the pattern simply stayed as it was, and the discrepancy only surfaced when the read-back showed the old data. Edit screens block requests too. Stop playback and return to the main pattern screen before any transfer, and verify a write by reading back rather than trusting that it was sent.
- **The device does not pick up a SysEx-written track until something forces a refresh.** Twice a freshly written track looked empty in the mixer and stayed silent on playback, then appeared and sounded the moment record was armed on it — no recording actually done. The data was correct both times. So after writing, arm record on the track (or leave and re-enter the pattern) before concluding anything is wrong, and never diagnose a write from playback alone on the first pass.
- **An empty pattern returns nothing, so a wiped pattern looks exactly like a dead device.** Distinguish them by requesting `SETUP`: if that answers, the QY100 is fine and the pattern is simply gone. Keep a dump from before any write — restoring it is a two-second fix.
- Pre-flight: rebuild the unmodified message and require `build_dump(addr, data) == msg.raw` before sending anything altered. Recompute the checksum after touching the payload.
- **Do not verify a write by comparing bytes.** The QY100 reserializes the block and regenerates its own padding — 95 of 147 bytes came back different while the events were exactly as sent. Decode the events and compare values.

Writing to the device (`send`) prompts for confirmation, and clear commands are tagged destructive. **Never send a CLEAR command unprompted.**

### The 4,285 preset phrases are documented

`manuales-md/QY100_Frases_Preset.md` and `qy100-syx/frases.json`, both regenerated by [`extraer_frases.py`](qy100-syx/extraer_frases.py) from Data List pp. 16–34. The count matches Yamaha's published 4,285 exactly.

A phrase is addressed by **three fields, not one number**: category + beat + number (manual p. 54). Beat takes only `8 beat`, `16 beat`, `3/4 beat`, and the number's range changes with each combination — 45 blocks in all, each numbered from 001.

**The suffix says which section the phrase is for** — `-I` INTRO, `-a` MAIN A, `-b` MAIN B, `-c` FILL AB, `-d` FILL BA, `-E` ENDING. That is a result of the data, not a reading of the names: the fill categories `Fa`/`Fb` are almost entirely `-c`/`-d` (303 of 312) while the main drum categories `Da`/`Db` are almost entirely `-I`/`-a`/`-b`/`-E`. A leading digit (`-1a`, `-2a`) marks alternatives for the same section. Of 863 styles, 283 carry the full set of six.

**Job 15, *Copiar frase*, is the bridge to the SysEx work**: it copies a preset phrase into a pattern track (D1, D2, PC, BA, C1–C4) as a user phrase, which can then be dumped and read with `patternfmt.py` — Yamaha's own event streams, in the format we decoded. It repeats a short phrase to fill the pattern, truncates a long one, and **overwrites whatever was in the target track**.

Two traps in the extraction, both of the kind that pass every check:

- **The `Phrase Category=` header is not the page's title.** It sits directly above the `8 beat` block, and a category's `3/4 beat` block often spills onto the *next* page's left column, printed before that header. So a block to the **left** of the header belongs to the **previous** category — it happens at pp. 19, 20 and 28. Reading the header as "this page's category" puts those three blocks in the wrong category, where they collide with the 3/4 block that category already has.
- **The collision is silent.** A misfiled phrase overwrites another at the same number instead of leaving a hole, so a validator that only looks for gaps in 001…N reports success while 13 phrases have vanished. **Check for duplicates as well as gaps**; the totals looked plausible either way, and only the published 4,285 exposed the shortfall.

One erratum in Yamaha's own list: the first phrase of `GR` / `3/4 beat` (p. 28) is printed `01` instead of `001`. Normalized on extraction.

### Las frases de fabrica son referencias y no cuestan memoria (2026-08-08)

**Medido sobre un equipo recien borrado**, que es la linea base ideal porque un
patron vacio no devuelve absolutamente nada: cualquier cosa que aparezca es lo
que se acaba de hacer.

Asignar una frase preset a una pista desde el panel deja el patron **sin ningun
bloque de pista**. Solo aparecen los 5 bloques de cabecera. Las notas se quedan
en la ROM: el patron guarda una referencia. Confirmado tres veces seguidas.

La consecuencia practica es de arquitectura, no de detalle: **un estilo puede
mezclar frases de fabrica referenciadas (gratis) con frases generativas propias
(que si ocupan)**, y pagar memoria solo por lo segundo. Con 128 KB compartidos
entre canciones, patrones y frases, eso cambia cuanto cabe.

**La referencia completa son DOS BYTES**, los dos en el registro de la cabecera
del patron. Medido campo por campo, cambiando una sola variable cada vez:

```
bandera  (bytes 21-68)    = <categoria:4 bits> <beat:4 bits>
tabla tr (bytes 69-116)   = numero de frase - 1

   nibble bajo = 8      la pista tiene contenido propio
   nibble bajo = E      vacia
   nibble bajo = 9 / A  frase de fabrica; un valor por beat (falta medir el 3o)
```

Categoria, beat y numero —los tres campos con los que el manual (p. 54)
identifica una frase— caben en dos bytes. **Por eso no cuesta memoria: no hay
nada mas que guardar.**

Lo notable de la segunda tabla es que **esta sobrecargada**. Documentada como "el
valor `tr` de cada pista presente", guarda el `tr` cuando la pista tiene
contenido propio y el numero de frase cuando referencia una preset. Hay que
respetarlo al escribir el registro.

**Dos lecturas equivocadas por el camino, y las dos por el mismo motivo.**
Primero se leyo `09` frente a `B9` como dependencia del rol de la pista, por
analogia con el byte 19 del prefijo; era la categoria. Despues se leyo el nibble
bajo `9` como "es una frase de fabrica"; es el **beat**, y salia siempre `9`
porque en todas las pruebas anteriores el beat estaba fijo. **Un campo que no
varia en el experimento parece una constante**, y llamarlo constante es afirmar
algo que no se ha probado. Solo aparecio al mover esa variable a proposito.

Queda sin explicar el byte 26 del bloque 1: sigue al numero de frase pero no
linealmente (`11`, `71`, `00` para 001, 002 y 010) y es independiente de la
categoria. **No hace falta para la referencia**, ya que los tres campos estan
localizados sin el; probablemente sea cache.

Para escribir referencias por SysEx falta solo el diccionario: que indice de
categoria corresponde a cada una de las 15, y que valor de nibble a cada beat.
Es un barrido mecanico, no un problema.

### User phrases are slots, not a bank — and `Us—NNN` is our `tr` byte

**48 user phrases per style** (specs, manual p. 133), numbered `Us—001` … `Us—048`, and the manual states the two ends explicitly (p. 58): `Us—001` is **D1 of Intro**, `Us—048` is **C4 of Ending**. That is 6 sections × 8 tracks, walked in the same order as the address, so

    Us—NNN  ==  tr = NNN - 1        in `12 nn tr`

The number on the panel is our address byte off by one. Useful for talking to the device and the dump about the same phrase.

The consequence is structural: **a user phrase is bound to a (style, section, track) slot.** Unlike the 4,285 presets — a global read-only library addressed by category + beat + number, reachable from any pattern — there is no shared pool of user phrases. 64 user styles × 48 = 3,072 slots, all sharing the same 128 KB.

Reuse across patterns is therefore a *copy*, and the panel has jobs for each direction:

| Job | Direction |
| --- | --- |
| 15 Copiar frase | preset phrase → pattern track |
| 16 Obtener frase | song track, measure range → pattern track |
| 17 Poner frase | pattern track → song track at a measure |
| 18 Copiar pista | any style/section/track → any **user** style/section/track |
| 21 Copiar patrón | whole style |

**Job 18 is the one that answers "use my phrase in another pattern"**: the source may be a preset style (`001`–`128`) or a user one (`U01`–`U64`), and the destination is any user style, section and track.

Job 17 carries a trap worth remembering: *"los datos de patrón fuente **se rearmonizan con el acorde actual** ... antes de ser copiados"*. Putting a pattern phrase into a song track applies the chord transformation first, so generative material has to be on `Bypass` unless the reharmonization is what you want — the same `Chord 1` behaviour that made a `Cm7` melody play major.

**From SysEx none of these jobs are needed**: copying a phrase to another pattern is writing the same blocks to a different `12 nn tr`. The three standing rules still apply — the 26-byte prefix travels with the blocks and its byte 19 is role-dependent (copy into a track of the same role, or rebuild with `build_prefix(pista=...)`), the destination pattern's two registry tables must be updated or the track reads as empty, and the whole pattern goes in one framed transfer with tracks first and the 5 header blocks last.

For generated material the better framing is that **the engine is the library, not the slots** — `syx.py generar` renders straight into any (pattern, section, track), so varying seed, length or section is a parameter rather than a copy.

### Playing a user style live — ABC, and Yamaha's rules for reharmonizable phrases

A user style is not only storage, it is a **playable instrument**, and that is the case for baking generative material into patterns rather than songs. Three live controls, all on the device:

- **MUTE / SOLO per track** in pattern mode (manual p. 56).
- **Footswitch cycles sections** during pattern *or* song playback (p. 121). From a blank section it jumps to MAIN A, so empty slots are skipped rather than silent.
- **ABC (Auto Bass Chord)** reharmonizes the playing phrases from chords played live.

**ABC is the reason to write phrases as `Chord 1` / `Bass` rather than `Bypass`.** Utility `Fingered Zone` (p. 128): `FINGERED` On/Off, a `MIDI CHANNEL` (`All` or `01`–`16`) for chords arriving from an external keyboard, and a `LOW`/`HIGH` key split (`C-2`–`G8`). Chords played inside the zone drive the accompaniment live; **a note below `LOW` while holding a chord is read as an on-bass (slash) chord**. `FNGR` must also be on in the SONG/PATTERN screen.

So any external keyboard becomes the chord controller. One caveat: some controllers transmit on **two channels at once** in dual or split modes, so set ABC's `MIDI CHANNEL` to one specific channel rather than `All`, or every chord is read twice.

**Yamaha's own three rules for phrases that survive reharmonization** (p. 59), which are design constraints for the generators:

1. Respect the harmonic context of the **source chord**.
2. Use mainly **root, 3rd, 5th and major 7th**.
3. **Keep to rhythms, avoid melodic lines.**

These map straight onto what we have. Rule 3 says the **euclidean generator is exactly the right tool** — rhythmic figures reharmonize cleanly. Rule 2 says the **Markov melody is the wrong one by default**, because it walks a scale and lands on passing tones that ABC will transpose into dissonance. Constrain its pitch set to chord tones and it becomes usable under `Chord 1`, which buys chord-following in exchange.

This reframes an earlier fix: we made generated melodies sound right by setting `Bypass`, which works but *gives up* reharmonization. The principled version is to generate chord-tone material and keep `Chord 1`.

One practical constraint: `SOURCE CHORD` (prefix bytes 21–22) is readable but **writing it is unverified**, so generate material in whatever source chord the target track's prefix already declares rather than trying to set it — `build_prefix()` copies the prefix from an existing track, so the value comes along with it.

### Playing the device live, and the shortest route into a DAW

Two tools added 2026-08-02, both of which change how the rest of the project should work.

**[`tocar.py`](qy100-syx/tocar.py) plays the QY100's tone generator in real time.** Notes arriving on MIDI IN sound with the voice assigned to that channel, so the device can be played without touching the sequencer — nothing here writes to its memory. Here **we are the clock master**, so timing is a local `sleep` loop; that is the exact inverse of [`qy100-arp/`](qy100-arp/), where the engines follow incoming clock and a local timer would break sync. The rule from there does not apply here because there is nothing to follow.

Pieces are plain functions returning a `Pieza`; `prueba`, `vigilia`, `acompanar` (a backing track to play guitar over), `cumbia` and `andino` are written, plus `barrido`, which plays three notes on each of the 16 channels to find out which ones sound.

Three things it has to get right, all learned the hard way:

- **`ECHO BACK` must not be `RecMontr`.** The manual lists this as its own fault (troubleshooting, p. 143): with `RecMontr`, incoming MIDI is **re-channelised to the currently selected record track**, so 16 distinct channels collapse into one voice. The symptom is "everything plays but it's all one instrument". Set it to `Off`.
- **A Program Change rewrites the loaded song's mixer voice for that channel.** Play on channels the target song does not use, or select an empty song slot first.
- **Stuck notes need `All Sound Off` (CC 120), not just `All Notes Off` (CC 123).** 123 only releases the keys: anything already in its release phase keeps sounding, and with long tails — SFX-kit textures, pads, a `Stream` on a three-bar gate — that can ring indefinitely. 120 cuts it regardless. Sending only 123 left the device beeping for an entire afternoon.

  **And the beep was mistaken for a fault in the music.** Six tracks were played back in isolation, each ruled out by ear, and three separate hypotheses about the arrangement were built and discarded before anyone suspected the tooling. The tell was there early and got ignored: an `All Notes Off` silenced it once, and it came back **right after the next write** — twice. When a symptom disappears on a global reset and returns after your own action, the fault is yours, not the data's. `ep-escribir.py` now sends both CCs on all 16 channels after every write.

**[`exportar_midi.py`](qy100-syx/exportar_midi.py) writes a standard `.mid`, and for getting notes into a DAW it beats the transfer outright.** The engines run at 480 clocks per quarter, which is set directly as the file's `ticks_per_beat` — the conversion is 1:1 with no rounding. Against recording the QY100 into Ableton it is exact, instant, needs no `MIDI Sync` / `MIDI control` / `Rec Count` dance, and cannot silently drop blocks. **The QY100 route still earns its keep for playing live, for its voices, and for pattern mode; for moving notes it does not.**

`--cuantizar 16` snaps to sixteenths. That is the right grid for this material because every deliberate placement — euclidean hits, the bass on odd sixteenths, off-beat stabs — already lands on exact sixteenths; only `humanizar()`'s few-millisecond jitter is removed. **Quantising coarser destroys the music**: it would drag the bass from sixteenth 3 onto the downbeat. `ep-escribir.py` takes the same argument so the device and the DAW hold the identical version.

### Two traps in note numbering

**Only the first 128 voices are addressable.** `voces.json` stores all 525 names in a flat list and the index equals the program number **only up to 127**; past that they are variations in other XG banks whose *bank LSB* was never decoded. Sending the index as a program yields a value outside 0–127. `tocar.py` raises a clear error; **`generar --voz` has the same exposure** and should get the same guard.

**GM's drum names do not describe relative pitch.** Note 45 is called `Low Tom` but it is a rack tom — the floor toms are 41 (`Floor Tom L`) and 43 (`Floor Tom H`), *below* it. Trusting the name put a high tom where the EP wanted a floor tom, in two tracks, and it survived until Felipe heard it. Read the Data List's drum table (p. 12), not the name.

**Two drum parts conflict unless one of them is channel 10** (2026-08-04). A song with `SFX Kit 1` (bank 126) on channel 1 and `Rock Kit` (bank 127) on channel 2 makes the tone generator emit **a sustained tone that corresponds to no note in the data**. Move the same drum track to channel 10 and it is clean. Each channel alone is also clean — the conflict needs both.

This one is nasty because **it is invisible to every check we have**. It is not in the dump, the checksums are fine, the note counts are exact, and playing either track in isolation sounds correct. It also survives a power cycle, because the banks live in the song's mixer. The only symptom is the sound.

Finding it took a binary search over channels — write a subset, listen, halve — after six tracks had been individually cleared by ear and three hypotheses about the arrangement had been built and discarded. **When every track is clean alone but the combination is not, stop looking at the data and start looking at the tone generator.** The rule now: if a song needs two percussion parts, one of them goes on channel 10.

**Bank 126 loads from a song part** — verified on the panel (2026-08-04): a song track with bank 126 / program 0 shows `SFX` in the mixer, so both SFX kits are reachable from songs and not only from patterns.

That was checked while chasing a constant high beep in an atmospheric track, and the beep turned out not to be a mapping error at all. The note was `72 Bubble`, exactly what the Data List says. The mistake was **musical**: `Bubble` is the one *discrete* blip in a kit otherwise full of sustained textures (`68 Shower`, `69 Thunder`, `70 Wind`, `71 Stream`), and it was placed at `E(3,16)` for 68 bars — around 200 blips over three minutes. Repeated that often, a short bright sound stops reading as atmosphere and starts reading as a beep. Replaced with wind and stream on long gates, 92 events instead of 272.

Worth keeping because the first two hypotheses were both wrong and both plausible: that the wrong kit was loading (the same note is `Samba Whistle L` in the Standard Kit), and that the fault was in the mixer's bank byte. **Checking the panel killed both.** When something sounds wrong, the mapping is the obvious suspect and the arrangement is the likelier one.

Related, for anything leaving the QY100: **sample libraries do not share the QY100's map.** SSD5 is a drum-kit library and has nothing at note 82, so Bajón's shaker was simply inaudible there — not a setting, an absent instrument. That note is also the cheapest thing to route to Tribe's Colombian percussion, since it is a single pitch and needs no remapping.

### The screen is programmable — text and 16x16 bitmaps

The QY100 obeys **XG Display Data** (Data List, table 1-5), which is not a QY100
feature at all — it is standard XG, and the QY100 gets it for being an XG module.
Two parameter changes, neither carrying a byte count or a checksum:

```
F0 43 1n 4C 06 00 00 <up to 32 ASCII>  F7    text
F0 43 1n 4C 07 00 00 <48 bytes>        F7    bitmap
```

The bitmap is **16x16**, laid out unobviously: each byte holds seven horizontal
pixels in bits b6..b0 with **b6 on the left**, and the 48 bytes are three column
blocks — 0-15 are columns 0-6, 16-31 are columns 7-13, and 32-47 are columns
14-15 using only b6 and b5.

**The two addresses paint different regions, and the manual does not say so.**
Felipe spotted it on the device: `06 00 00` goes to the **popup**, which clears
itself, and `07 00 00` goes to a **strip at the bottom**, which stays. They are
complementary rather than alternatives — the popup for transient messages, the
strip for something persistent.

And because the manual allows refreshing individual elements while the rest holds,
the strip can be **animated**. Verified with a heart beating at 104 BPM. Since the
QY100 also transmits MIDI clock, an animation could follow the sequencer rather
than a local timer. `pantalla.py`.

## Firmware format (decoded)

`QY100_1.37/_QY100_v137.mid` is not music — it is the ROM image for IC3 (FlashROM 16 Mbit, `main prog`) encoded as MIDI SysEx. Decoded structure:

```
F0 43 00 5F 00 40 <addr:3B, 7-bit> <64B packed 7-in-8> <checksum> F7
```

**The 7-in-8 packing here is not the same as `protocol.unpack_7in8`** (corrected 2026-07-29): the MSB byte sits at the **end** of each group of 8, and within it **bit 6 carries the first data byte** (MSB-first). Getting either wrong yields text that looks almost right — `Stand.it` with a zero where the `K` goes, or `Sil.nKit` with one stray high bit — which is exactly the failure mode that survives a casual glance. Two independent anchors caught it: the drum-kit table (byte position) and a name containing a high-bit byte (bit order, invisible in pure ASCII). `qy100-syx/extraer_rom.py` implements the corrected version.

- 24,570 bulk blocks × 56 real bytes = **1,375,920 bytes**
- Checksum: two's complement of the 7-bit sum, taken from byte offset 3
- 21 banks of 64 KB, framed by control messages `43 10 5F 01` (select/erase) and `43 10 5F 03` (verify)
- Banks start at flash offset `0x10000` — **the first 64 KB is never written**, i.e. the bootloader is protected, so a failed flash is likely recoverable
- **Not encrypted**: entropy 6.93 bits/byte with 11% zero bytes, and plaintext `QY100`, `XG`, `Song` strings decode out

**The voice bank was extracted from this ROM** (2026-07-29) — see `qy100-syx/voces.json` and `syx.py voces <texto>`. 525 normal voices in fixed 8-byte records, anchored on two points measured on the device: `GrandPno` = program 0 (display 001) and `SquareLd` = program 80 (display 081). Both land exactly, and 525 + 22 kits matches the manual's 547. `--voz` now takes names.

The 22 drum kits are **settled by the Data List** (`QY100E2.pdf` pp. 4–9), not by the ROM: they sit at non-consecutive program numbers — 1, 2, 3, 4, 9, 10, 17, 18, 25… — on bank 127, except `SFX Kit 1`/`2` which are on **bank 126**. The device anchor confirms it: prefix byte 16 = 9 → Pgm# 10 = `Dark Room Kit`, which the ROM abbreviates to `DarkRKit` and the panel shows as `Dr010`. The earlier guess that the ROM list index *was* the program number was wrong, and the mismatch it produced was the clue.

The **chord type list** (p. 36–37, rendered to `manuales-md/diagramas/qy100-acordes-*.png` — the page is graphical and does not survive text conversion) names all 26 types with their intervals, but **carries no numeric codes**; the Data List's own MIDI section has none either. Only `M7`=0, `m7`=8 and `7`=13 are measured. The list still helps: it turns measuring the rest into a systematic sweep instead of guesswork.

The wall for actual firmware modification is the **SWX00B (HG73C205AFD)** CPU — Yamaha proprietary, two of them (IC1 main / IC2 sub), instruction set not publicly documented. Reading and rewriting the flash is solved; disassembling it is not. Prefer external augmentation (qy100-arp) or data-level changes over firmware patching.

## Contents

| File | What it is |
| --- | --- |
| `QY100S.pdf` | Owner's manual, **Spanish** (*Manual del Usuario*). Operating instructions for the end user. |
| `QY100E2.pdf` | **Data List**, English (2000) — the separate booklet the owner's manual keeps referring to as *"el manual adjunto de listas"*. XG normal and drum voice lists with program numbers, effect types and parameters, preset style and phrase lists, chord type list, drum table, amp simulator list, and its own MIDI data format section. Converted at `manuales-md/QY100_Data_List.md`. |
| `219610235-YAMAHA-QY100-Service-Manual.pdf` | Official Yamaha service manual, English (SY 011558, printed 2000.12). Hardware-level reference. |
| `QY100_1.37/_QY100_v137.mid` | Firmware v1.37 image, delivered as a Standard MIDI File (format 0, 1 track, 96 PPQN, ~1.8 MB). Not a musical performance — the ROM payload is encoded as MIDI data and streamed to the device. |
| `QY100_1.37/QY100 Firmware Update Readme.txt` | Step-by-step flashing procedure for that file. |

## Markdown conversions — read these, not the PDFs

`manuales-md/` holds a Markdown conversion of **every** PDF here. Grep or `Read` these instead of extracting PDF pages; it is far faster and the content is equivalent.

`manuales-md/QY100_Service_Manual.md` opens with a **line-number index** to every section (SysEx bulk dump, Table 1-9, implementation charts, LSI pins). Jump with `Read` + `offset` rather than scanning 3,900 lines.

Two tables in it were mangled by the converter and have been **hand-corrected** against `pdftotext -layout`, each flagged with an inline editorial note: Table 1-9 (shifted `Recv`/`Trans`/`Req` columns) and the Bulk Dump SEQ Data byte layout (a row that escaped its table). Everything else is untouched machine output — if a table looks wrong, check the PDF before trusting it.

Audited 2026-07-27: text coverage is 100.4% (service) and 100.3% (user manual) versus `pdftotext`, UTF-8 is clean with zero replacement characters, Spanish accents are intact, and neither file is truncated.

**Diagrams do not survive conversion** — their labels scatter into unrelated table cells and the spatial meaning is lost. That has been worked around two ways:

- Every diagram page is rendered to PNG in `manuales-md/diagramas/` (150 dpi; the block diagram also at 300 dpi). `Read` those files directly instead of paging through the PDF.
- The **block diagram (p. 9)** — the highest-value one — is transcribed into proper tables inside the Markdown, so IC-to-function mappings are now greppable. `IC3 = FlashROM 16M "main prog"`, `IC6 = SRAM "user data"` (battery-backed), etc.

The service manual Markdown carries an index of both. Other diagram pages (circuit board layout, IC block diagrams, parts list, overall circuit diagram) exist only as images — transcribe one if you need it.

To render more pages:

```bash
pdftoppm -r 150 -png -f FIRST -l LAST Manuales/FILE.pdf manuales-md/diagramas/PREFIX
```

Source PDFs live in `Manuales/` (capital M), conversions in `manuales-md/`. To convert a newly added one:

```bash
uvx --from 'markitdown[pdf]' markitdown Manuales/FILE.pdf > manuales-md/FILE.md
```

**If the result is ~1 line, the PDF is a scan with no text layer.** Check with `pdffonts` — no fonts listed means no text. OCR it instead; `tesseract` and `ocrmypdf` are already installed:

```bash
ocrmypdf --force-ocr -l eng --output-type pdf --quiet Manuales/FILE.pdf /tmp/ocr.pdf && pdftotext -layout /tmp/ocr.pdf -
```

OCR output can misread characters, so those files carry a warning header and their pages are also rendered to PNG alongside the conversion — check a number against the image before trusting it.

Use `uvx`, not the system Python: 3.9 is too old for MarkItDown (needs ≥3.10), and the `markitdown` on `PATH` is a 240-byte placeholder package that silently does nothing.

## The rest of the rig

The QY100 sits in a DAWless setup alongside other clock-capable gear, which is
why sync direction matters and why `MIDI CONTROL` keeps coming up. The specifics
of that rig are not published here.

One point worth keeping, because it is about the QY100 and not about the rig:
**only one device can be the clock master**, and the QY100's role flips with the
task. It is master when it drives an external arpeggiator (`MIDI SYNC =
Internal`), and slave when a DAW records it (`MIDI SYNC = External`, `MIDI
control = In/Out`, `Rec Count = OFF`). Those two configurations are mutually
exclusive; decide which one you are doing before touching anything.

## Service manual page map

The service manual is the answer to most technical questions; read the relevant pages rather than the whole PDF (`Read` with the `pages` parameter, max 20 pages per call):

- Specifications — 3/5
- Panel layout — 7
- Block diagram — 9
- Circuit board layout — 10
- Disassembly procedure — 11
- LSI pin description — 13
- IC block diagram — 15
- Circuit boards — 18
- Test program (service diagnostics) — 21/30
- Error messages — 39/42
- **MIDI data format — 45**
- **MIDI implementation chart — 70**
- Parts list and overall circuit diagram — after p. 70

The MIDI data format and implementation chart sections are the reference to cite for anything involving SysEx, bulk dump, or protocol work against the QY100.

## Firmware update procedure

From `QY100_1.37/QY100 Firmware Update Readme.txt` — the button chords are not guessable and the timing matters:

1. Connect QY100 to host via **MIDI IN/OUT**, set the Host Select switch to `MIDI`.
2. Power on while holding `[m7(9)]` + `[mM7]` + `[m7(11)]` — this enters update mode.
3. Play `_QY100_v137.mid` from the sequencer. **Takes ~18 minutes.**
4. Power off only *after* `Completed` appears on the display.
5. Verify: power on while holding `[AMP SIMULATOR]` + `[PARAMETER]` + `[SONG]` — the display shows `Main ROM V1.37`.
6. Power cycle once more.

Treat `_QY100_v137.mid` as read-only binary. Never edit, re-save, quantize, or round-trip it through a MIDI library — any transformation of the byte stream corrupts the ROM image and can brick the device. Copy it if a working file is needed.

## External resource

[QY100 Explorer](https://qy100.doffu.net/) — active QY100/QY70 community. Notable because it confirms the productive extension path is **data, not firmware**: they achieve out-of-range BPM and patterns beyond the 8-measure cap by authoring custom style files and loading them via SysEx (`.syx` / `.Q1P`).

## Language note

The owner's manual is Spanish and the service manual is English, so QY100 terminology appears in both. When quoting the owner's manual, keep the Spanish term and gloss it rather than silently translating panel labels — the physical buttons are labeled in English.
