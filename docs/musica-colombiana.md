# Colombian music, measured

The rhythmic cells of the genres this project uses, taken from scores and
transcriptions rather than from theory. The code is in
[`qy100-syx/qy100syx/andina.py`](../qy100-syx/qy100syx/andina.py) and the
measurements are reproducible with
[`analizar_loop.py`](../qy100-syx/analizar_loop.py).

> **How to read the marks.** Everything here is in one of three states, and
> keeping them apart is what stops the same mistakes repeating: nearly all of
> this project's have lived on the border between the second and the first.
>
> - `[M]` **measured** against the device or a primary source. Usable.
> - `[D]` **deduced** from something that is measured. Coherent, unchecked.
> - `[V]` **unverified**, or checked by a route that doesn't prove it.
>
> A coherent inference sounds exactly like a fact. The bambuco came out wrong
> three times running for that reason, and the DrumBrute's trigger parameter was
> attributed to the wrong byte because it happened to be first in the list.

### The bambuco, measured off scores — and three wrong versions first

**"Papa con yuca"** is the mnemonic for the Andean tambora's base pattern and it
is the genre's rhythmic identity: without it everything else can be right and it
still won't sound like a bambuco. Felipe caught that by ear on the first
generated version.

The cell comes from `te-ofrezco-mi-corazon-bambuco.mid` (choir, guitar and
tambora, 6/8), by folding the attacks per bar:

```
eighth       1      2       3      4       5      6
syllable     PA     PA      CON    YU      CA      ·
tambora     high   high    low    high    low      ·
guitar        ·   CHORD    BASS   CHORD   BASS     ·
```

Across 31 bars the guitar plays **31 chord attacks on 2 and 31 on 4**, and **31
bare low notes on 3 and 31 on 5**. One per bar, without exception. And the bass
plays **fifth on 3, root on 5** — in that order, always. Putting the root first,
which is the natural instinct, inverts the gesture: arriving at the root on 5 is
what closes the bar.

**The sixth eighth is empty across the whole accompaniment.**

**Three wrong versions before this one, each from a different kind of source:**

1. **Bass drum on 1 and 4**, deduced from the sesquialtera on paper: the two
   groups of `3+3` start there. Coherent and false.
2. **Bass drum on 1, 3, 5**, taken from Tribe's grooves. But that is a bambuco
   played with **Caribbean drums** — an adaptation — not the Andean one. **A real
   transcription of a different ensemble is not a transcription of the genre.**
3. **Chords on 1, 3, 5 and bass on 4 and 6**, from a prose description found
   online with eighth-note precision. It described another pattern. What made it
   convincing was exactly what made it dangerous: it carried enough detail to
   look measured.

For a genre's rhythm, **a score of that genre** beats metric theory, beats prose,
and beats a transcription for instruments that aren't its own.

**And the scores disagree with each other, which is the finding.** Four bambucos
— the fourth is `bambuco-no-1-en-si-menor-adolfo-mejia-navarro.mid`, at 30 %
consistency, which is why it does not carry a row of its own but does supply the
melancholic variant's only measurement:

```
te-ofrezco     6/8   chords 2,4       bass 3,5
y-un-cafe      6/8   chords 1,2,4,6   bass 3,5
brisas         3/4   chords 1,3,5
```

`te-ofrezco` puts the chords on the offbeats and `brisas` on the three quarters.
**It isn't that one is wrong: one plays the 6/8 side of the sesquialtera and the
other the 3/4 side.** That is why transcribers chose different time signatures
for the same music. The invariant between the two 6/8 scores is **the bass on 3
and 5**.

**The melody does not stick to the cell.** The flute in `y-un-cafe` spreads 367
notes almost evenly across the six eighths (64/54/54/76/64/55), with a slight
lean toward the 4th. It floats above the accompaniment. That is the opposite of
what a generative engine does, which aligns everything to the grid — and it
explains why a generated melody sounds like a machine even when the notes are
right. Pitches: the natural A-minor collection, with `E` and `A` most frequent,
spanning two octaves.

**The differences between scores are REGIONAL VARIANTS, not transcriber
preference.** The bambuco has documented variants — *de salón*, *fiestero*,
*sureño*, *sanjuanero*, *caucano*, *patiano*, *del litoral* — and character
follows geography: slow and melancholy in Cauca, **festive in Tolima and the
Santanderes**, rural on the highland plateau. `brisas-del-pamplonita` is
Santanderean (the Pamplonita is a river in Norte de Santander) and its pattern is
a different one:

```
eighth       1      2      3      4      5      6
fiestero    BASS  CHORD  BASS   CHORD  BASS   CHORD    Santanderean
de salón      ·   CHORD  BASS   CHORD  BASS     ·      te-ofrezco
```

**The fiestero leaves no gaps and pushes; the salón version leaves 1 and 6 empty
and breathes.** The tambora cell is shared: it is the same genre.

And with that **the notation stops being arbitrary**: in the fiestero the bass
falls on the three quarters, so 3/4 is the natural reading; in the salón version
the weight is on the 6/8 offbeats. The choice of time signature is **a
consequence of the pattern**, not of the transcriber's taste. A hypothesis from
two scores; confirming it needs more of each variant.

`qy100syx/andina.py`. That provenance note used to be followed by a `[V]`
saying the
pasillo was still built by method 3 and unchecked against any score. **It was
false, and it stayed published for more than thirty commits after it went
stale**: the engine has `PASILLO_BAJO_EN = 0` and `PASILLO_ACORDE_EN = (3, 4)`,
which is the row this document's own table gives two sections below, measured on
`la-gata-goloza` — bass on the 1st eighth (183 low notes against 71 chords) and
chords on the 4th and 5th (104 and 110), the pattern repeating in 110 of 184
bars. A `[V]` that has been resolved and not updated is worse than no mark: it
tells the reader to distrust something that is measured.

What is still unverified there is the **requinto**: it plays on eighths 2, 3 and
6 — precisely the three the measured cell leaves empty. It comes from no source
at all.

### Measuring how invariant a genre is

Extracting cells from four scores produced a method that works for any of them:
**count what percentage of bars repeat exactly the same attack pattern.** It
separates the genre's cell from the arranger's decisions.

```
guabina      97%   (35 of 36 bars — `[V]` this row predates the audit that
                    demoted the guabina's bass to a choice; its source,
                    santo-guabina.mid, is not in the repo to recheck)
torbellino   97%   (bass drum on 1 and 5, 96 of 99 bars)
bambuco      83%
pasillo      60%
vino tinto   58%   (a different cell of the same genre)
```

Below half there is no cell to extract, only an arrangement. And the number says
something musical, not technical: **how much room the performer has**. In the
torbellino, none; in the pasillo, four bars in ten belong to the arranger. It
explains why the pasillo took three attempts and the torbellino came out first
try.

Measured cells, all in 3/4 over six eighths:

```
                1      2      3      4       5       6
torbellino    DRUM     ·      ·    snare   DRUM    snare
guabina       BASS     ·   CHORD     ·     BASS    CHORD
bambuco salón   ·   CHORD   BASS   CHORD   BASS      ·
bambuco fiest BASS  CHORD   BASS   CHORD   BASS    CHORD
pasillo       BASS     ·      ·    CHORD   CHORD     ·
pasillo denso  a continuous eighth-note line, flat velocity
```

`[D]` **The guabina's bass on 1 and 5 is a choice, not a measurement** — but
the story of why took two corrections, and the second corrects the first.

This paragraph originally claimed the guabina shared the 1-and-5 bass with the
torbellino. An audit called that false, and the correction published here said
"what the torbellino has measured on 1 and 5 is **the bass drum**, not the
bass". **That correction was itself wrong about the source.** Measured on
2026-08-12, per part: the score's *Bombo 1* sits on `[1,5]` in 96 of 99 bars
(97 %) — and its *Contrabajo* also sits on `[1,5]`, in 46 of 89 bars (52 %),
against only 12 bars (13 %) on the three quarters. **The bass drum and the
bass of the source agree.** What plays the three quarters is our *engine's*
bass, by design, because it carries the harmony; the earlier text confused the
engine with the source, in the opposite direction from the first mistake.

The guabina's `[D]` stands regardless — nothing here is a guabina measurement.
What survives is the difference between the two genres as built: the torbellino
answers on the three quarters, the guabina on the offbeats behind each bass
note. And **the
festive bambuco is the only one that occupies all six eighths**: that's why it
pushes.

## The currulao — the cleanest cell measured so far

`[M]` From `bombo-golpeador-o-macho-currulao.mid`: **64 notes across 16 bars, and
all sixteen identical stroke for stroke. 100 % repetition.** The torbellino gave
97 and the salón bambuco 83.

```
eighth      1      2      3      4      5      6
syllable    Dé            le     du            ro
hand       LEFT          LEFT   LEFT         RIGHT
stroke     wood          wood   wood          head
pitch      C#2           C#2    C#2            C2
pulse       ●                    ●
```

`[M]` **The two pitches are not high and low heads: they are two surfaces.** The
score (*Bombo «gopeador» o Macho-Currulao*, Javier Martínez / Wilmer Vente) says
so outright — "the left hand plays the wood, notated as X, and the right hand the
drumhead". X noteheads are wood.

And the transcriber wrote it with GM semantics, so the MIDI already carried it:
`C#2 = 37` is the **side stick**, the dry rim stroke, and `C2 = 36` is the **bass
drum**. The first mapping sent them to two toms and erased exactly what
distinguishes the stroke. **The datum was in the file and was lost in
interpretation, not in measurement.**

`[M]` **It really is 6/8**, and here the notation agrees with the cell: all five
currulao scores come in 6/8. It is written that way on the device, which accepts
it — byte 14 encodes the denominator with `2` for `/8`. `cmd_andina` used to have
it hard-wired to `/4`, which would have written 3/4 over a six-eighth cell: it
sounds the same, but the machine counts bars differently in song mode.

Three strokes on wood and **the low one on the sixth eighth**, which is exactly
where the salón bambuco falls silent. The two genres divide the same six eighths
and part company on that one note: one breathes there, the other lands. That is
not an impression — it comes from comparing two attack tables measured
separately.

**And the two sources do not contradict each other, though it looks like it.**
Martínez and Vente's score reads "Con la orquesta dele duro" — eight syllables,
two bars — and the primer reads "Déle duro" — four, one. The second is the tail
of the first: the same cell named at two scales. Taking the primer as correct and
discarding the score would have been a method error; **a new source does not
invalidate an earlier one by being more official, it just says something else.**

`[V]` **The cycle is four bars, not one**: "three plain bases plus a variation".
The source measured here carries sixteen identical bars because it is the base in
isolation; in practice **every fourth bar carries a variation**. **The variation
is notated in the primer but has not been transcribed — the `Currulao` engine
plays the base alone, which is correct but incomplete.**

**The melodic material is not generated.** The marimba gives 13 % repetition and
the guitar 4 %: those are arrangements, not cells, like the porro and the chandé.
The engine supplies percussion and harmony; the marimba comes in through the
EP–40, from the score or played live.

It weighs **5.2 KB**, the cheapest of the Andean-family engines.

## The mapalé — an ostinato that swings by the octave

`[M]` From `mapale-ashcolom.mid`, a two-hand piano transcription. The
accompaniment's cell, in sixteenths of a half bar:

```
sixteenth      1    2    3    4    5    6    7    8
attacks      142    0    0  120   10  120    0    0
```

`[M]` **Three equal attacks per half-bar, not 3+2+3.** The half-bar is 960
clocks and the attacks land on 0, 320 and 640 — exact thirds, zero deviation
in 382 of its 392 attacks — the other 10, also grid-exact, sit on the
half (clock 480), printed in the table above — with each note holding its
full third (319 clocks in
372 of them). It is a quarter-note triplet over two quarters: a 3-against-2, and
that is what makes the genre run.

The table above is printed on a sixteenth grid, and **that grid is what produced
the "3+2+3"**: 320 and 640 do not fall on it, and rounding them gives 360 and
600. The attack counts were always right; the column they were printed in was
not.

**And then the ear overruled the paper — the mapalé is two genres now.** The
ternary cell was written to the device on 2026-08-12, replacing the binary one,
on the strength of five agreeing sources: Felipe's own 2/2 reading, this
transcription, a band score in
6/8 (*Prende la Vela*, Lucho Bermúdez), a drum method that labels the cell
"Tres contra dos", and a recording measuring ternary (re-measured 0.70 vs 0.44 at 149.8 bpm
after the tool's own audit; the earlier 0.90/0.26 came from a version whose
self-test now fails).
Played against the Tribe reference loop, **it was wrong** — the groove sits
elsewhere. The engines are split:

```
Mapale           4/4, 3+2+3          [V]  sounds right; no source supports it
MapaleTernario   6/8, three-vs-two   [M]  five sources; sounds wrong
```

That asymmetry is deliberate. The binary cell's documented origin is an
artifact (this ternary transcription read on a binary grid), so marking it
`[M]` because it works would invent a provenance for an ear decision. The
lesson, paid for twice in one day: **a correct measurement of one source does
not license changing what another source supports.** The Tribe loop itself
leans binary but does not decide (74 % vs 69 %).

And the pitches say something the count alone cannot see:

```
bar 71   s1 D3   s4 D4   s6 D3
bar 72   s1 D4   s4 D3   s6 D4
```

**The octave alternates on every stroke.** With three strokes per bar the cycle
inverts on the next one and returns on the third. It is not a static pedal: it is
an octave oscillation over a fixed grid, and that two-bar phase is what keeps it
from tiring.

`[M]` The harmony barely moves: **126 bars on D, 14 on F and one on A**, with 29
changes across 141 notated units — half-bar cells of the piano
transcription. The unit label used to say "bars"; and an earlier fix here
converted them to "roughly 71 real bars", **dividing in the wrong direction of
its own premise**: if the transcription is at half speed, each notated half-bar
IS one real 6/8 bar, so the real count would be ~141, not 71. Since the
half-speed reading is itself `[V]`, the figure is now stated only in the
transcription's own units. It is an ostinato genre.

`[V]` **Metre and tempo disagree across sources.** The piano transcription is
4/4 at 100; Tribe's catalogue gives 180 in 2/2; a live-set measurement (not published
here) says 202.7. The
clarinet score of *La Mecedora* (José Camilo Gómez) is in cut time, which
supports the 2/2. Most likely the piano transcription is written in half time —
100 × 2 = 200, close to 202.7 — but that is unconfirmed.

`[V]` **The percussion is in neither source.** What is measured is the
accompaniment cell and the harmony, not the drums, which in this genre are half
of it.

> **Careful with clarinet scores.** *La Mecedora* is written for **B♭ clarinet**,
> a transposing instrument: what is written sounds **a major second lower**.
> Taking its pitches at face value puts the piece a tone high, and it would sound
> perfectly fine in the wrong key — the error is inaudible with nothing to
> compare against.

## The marimba ensemble, per the academic source

From **Paz Hernández (2005)**, *Producción musical contemporánea utilizando las
células rítmicas del Pacífico colombiano* (San Buenaventura, Bogotá) — advised by
**Javier Martínez Maya**, the same person who signs the bombo golpeador score.
Converted at
`manuales-md/Paz2005_Celulas_Ritmicas_Pacifico.md`.

`[M]` **The marimba de chonta is 24 bars and two instruments in one:**

```
16 short bars    the TIPLERO      the melody
 8 long bars     the BORDONERO    the accompaniment
```

Four mallets in the hands of **two players**. That corrects an earlier exchange
in this project: on measuring 4 overlapping voices in Tribe's transcription it
was objected that two players cannot do that, and about *that* transcription it
was true — it carries only the tiplero's part, and its maximum simultaneous
attacks is 2 — but **on the real instrument four simultaneous strokes are
possible**. The objection was right about the source and wrong about the
instrument.

Consequence for sampling to the EP–40: the 34 bars sampled from Tribe cover the
full range, but **the instrument has two registers with different functions**.
Writing for it as if it were a uniform keyboard wastes that.

`[M]` **The full ensemble**: marimba de chontas, two cununos (macho and hembra),
two bombos (**golpeador** and **arrullador**), redoblante and guasás. The thesis
itself, producing in a studio, **records congas standing in for the cununos** —
because a cununo is hard to source and to mic — and uses a real arrullador and
tambora. That is the same decision this project faces with the EP–40: what gets
sampled for real and what gets substituted.

## The metric matrix — what we were doing already had a name

From **`Pitos y tambores`, Victoriano Valencia's musical primer** (Plan Nacional
de Música para la Convivencia, Ministry of Culture).

> *Two metric matrices gather the rhythms of the pitos-and-tambores axis. One,
> **binary, of eight events** defined by accent, pulse, first division and second
> division. The other, **ternary, of six events**.*

**The attack tables this project has been measuring are exactly that.** The
ternary six for bambuco, currulao and torbellino; the binary eight for mapalé,
chandé and cumbia. `[V]` **The chandé's placement in the binary column is
contested by its own primer**: Valencia's score is titled "RITMO DE CHANDÉ.
BASE TERNARIA", while the Tribe loop measures decisively binary — 89 % of
attacks on the binary grid against 47 % on the ternary one — reproducible with
`medir_loops.py`, which recomputes every loop figure this document cites. Two
sources, two answers, both real; the same shape as the mapalé split. This
document keeps the loop's answer for the engine work and records the
disagreement instead of picking silently. The same analytical device was reached by measurement,
without knowing that Colombian pedagogy had already formalised it and named it.

`[M]` **And the X convention is documented.** The primer gives the tambora's
notation key:

```
♩    open, or head — stick stroke on the drumhead
♩̣    muted — struck while pressing with the stick tip
✗    WOOD — struck on the shell of the tambora
⊗    rim
```

> *"Example of two-plane writing. **Wood above and head below**."*

So reading the bombo golpeador score's X noteheads as wood **was not a footnote
of that one document but the standard**. That backs the currulao mapping with a
pedagogical source rather than an inference.

## The cumbia, from the Ministry's primer

`[M]` The alignments over the binary matrix, as the primer gives them:

```
binary matrix     1   2   3   4   5   6   7   8
claps (pulse)     X               X
llamador                  X               X        offbeat
guacho            X       X       X       X
alegre            X   X   X   X   X   X   X   X    "reproduces the matrix"
```

The alegre playing all eight events is the basic **soledeña-type** cumbia
pattern. `[V]` **The offbeat llamador does not distinguish a cumbia.** The primer
applies that same binary offbeat to the "llamador de cumbia, gaita, porro,
chalupa, son corrido, puya sabanera" — six rhythms — and gives the cumbia clave
to the bullerengue, the porro palitiao and the gaita as well. What the source
supports is the position, not the identity.

`[V]` **The tambora needs a "double matrix"** — sixteen events — and is not
implemented: its variations take a full page of the primer and deserve measuring
separately.

`[D]` **The bass is not in the primer**, which is percussion material. The
engine's is a simple line on the pulse, deduced.

## The South Pacific is TWO systems, and currulao is one of them

From **`¡Qué te pasa vo! Canto de piel, semilla y chonta`**, the South Pacific
primer (Duque, Sánchez and Tascón — Plan Nacional de Música para la Convivencia).
The sibling of *Pitos y tambores*, for marimba, cununos, guasá and bombos.

`[M]` **The taxonomy**, which changes how to think about the repertoire:

```
bunde system       airs in 2/4
currulao system    airs in 6/8    currulao, berejú, patacoré, pango, juga
```

These are not separate genres that happen to share a cell: **they are airs of one
system**, which is why they share it. It confirms the currulao's 6/8 with a
pedagogical source, not just with the score.

`[M]` **The mnemonic is "Déle duro"** — four syllables, one bar, one stroke each.
And it agrees with what was measured by another route: *"each simple base has two
pulses… the pulses coincide with the strokes on the wood"*. In 6/8 the pulses are
eighths 1 and 4, and both are wood in the measured cell. The primer adds that one
claps or stamps **on the syllable "ro"**, which is the head stroke on the sixth.

## Where each track comes from

Every engine declares the provenance of its tracks, readable without hardware.
**That sentence was false when it was written**: four of the ten declared
nothing and two inherited another genre's table, so they announced `[M]` over a
score they do not play. It is true as of 2026-08-11, and `test_generos.py` now
fails if it stops being true.

```bash
cd qy100-syx && .venv/bin/python syx.py andina currulao --fuentes
```

```
track      source                                 what it contributes
D1   [M]  bombo-golpeador…mid (Martínez/Vente)   the cell, 100 % over 16 bars
PC   [D]  -                                      continuous guasá, deduced
BA   [D]  -                                      bass on 1 and 4, from the two pulses
C1   [D]  -                                      chords on 2 and 5
```

It exists because **blending sources silently is the expensive error in this
domain**. The bambuco has three engines precisely because
`te-ofrezco-mi-corazon` and `brisas-del-pamplonita` carry different patterns:
merging them would have produced a bambuco that exists nowhere. With provenance
written down, a new source can be checked against the old at a glance.

And it makes the uncomfortable part visible: in the currulao **three of the four
tracks are deduced**, and only the bombo is measured. That was invisible while
reading the code.

## The lead bombo has four bases, not one

From the South Pacific primer, §5.2.1.1 (physical page 36). Each with its
mnemonic:

| | base | strokes |
| --- | --- | --- |
| 1 | **«Déle duro»** | OPEN + WOOD |
| 2 | **«Con la horqueta»** | OPEN + WOOD |
| 3 | **«Papa con yuca»** | OPEN + WOOD |
| 4 | **«Cogé tu batea»** | OPEN, WOOD and MUTED |

**«Papa con yuca» is also a currulao base.** It was known here as the bambuco's
mnemonic, measured on `te-ofrezco-mi-corazon`. And the **arrullador** — the
second drum — plays a base the primer literally calls **«Bambuco»** (or «Totuma,
totuma»), alternating MUTED, WOOD and OPEN.

That is not a coincidence of names: it is the link that the paper *«similitudes
entre bambuco y música del Pacífico»* points at, and which had already been
brushed against here on noticing that the two families divide the same six
eighths.

`[M]` **The missing variation is the *apoyos*, and there are three**: "Con la
horqueta ×3 + a close", with closes called **cierro**, **acompaño** and
**marcando**. That completes the four-bar cycle.

`[M]` **The last stroke is WOOD and HEAD at once** — *"the last syllable
coincides with the simultaneous OPEN-WOOD stroke"*, and the pictogram draws it
with a different icon from the other three. The engine was writing only the head,
which is half the stroke. Fixed.

`[V]` **And there is an unresolved disagreement about the accent.** The primer
says every form of execution converges on *"a strong OPEN stroke (5th eighth)"*;
the measurement on Martínez and Vente's MIDI puts it on the **6th**. A
one-eighth offset, which would move the whole cell relative to bass and chords.

It cannot be settled from the primer: its notation is **pictographic** — drum
icons with a stick — and the spacing between icons is visual, not proportional.
Deducing positions from that would be exactly the error this project has already
made. It is settled by ear against track 40 of the primer's CD, or by playing
both versions and comparing.

## The currulao ensemble, instrument by instrument

From the CD index of the primer (tracks 40–45, physical page 49), which is text
and therefore verifiable without reading pictograms:

| track | instrument | bases |
| --- | --- | --- |
| 40 | **bombo golpeador** | Déle duro · Con la horqueta · Papa con yuca · Cogé tu batea |
| 41 | *apoyos* | Cierro · Acompaño · Marcando |
| 42 | **bombo arrullador** | base «Bambuco» + variation «Empujá pa que suene el bambuco» |
| 43 | **cununo apagador** | «Qué por qué» |
| 44 | **cununo repicador** | «Tráigalo pa'cá», with finger stroke and side stroke |
| 45 | *repicador variations* | Tráigalo tra · Tráigalo ya · Tráigamelo ya · Traitraitrai |

**The mnemonics are the rhythm**, not a memory aid bolted on afterwards. "Qué
por qué" is three syllables, "Déle duro" four, "Tráigalo pa'cá" five: the
syllable count and where the stress falls **are** the cell. That is why it is
taught this way, and why it lets someone verify by ear without reading music.

It also opens a route to transcription that does not depend on the pictogram:
**counting syllables bounds the number of strokes**, and the prosodic stress says
which one is strong. It doesn't replace measuring, but it rules out impossible
readings.
