# Manuales, conversiones y procedimientos

Dónde está cada documento y cómo leerlo sin abrir el PDF.

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
