# QY100 — the 128 factory styles, with their full names

From Yamaha's **sales brochure** (`Manuales/QY100_Folleto_2000.pdf`, Adobe
PageMaker, December 2000). The device only shows five-character abbreviations,
so without this there is no way to look up `AfrJz` or `DncSw` by what they are.

`[M]` **The numbering is the device's**, not a reordered marketing list.
Checked against the four abbreviations already recorded off the panel:
`80MRk`→002, `DncSw`→040, `AfrJz`→090, `Bossa`→110. Four out of four.

`[V]` Number **062** is printed as `80's / Technical Fusion`, slash included. It
may be a name with a slash in it, or two entries that lost a number in layout.
Not checked on the device.

Extracted by slicing on column: `pdftotext -layout` interleaves the brochure's
columns, and without the slice foreign text leaks in — style 067 came out as
`6/8 R&B / MUSIC SEQUENCER`.

The data lives in [`qy100-syx/estilos.json`](../qy100-syx/estilos.json).

| nº | style | nº | style | nº | style | nº | style |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 001 | Hardcore Mixture | 033 | Metal Boogie | 065 | Acoustic Pop | 097 | 6/8 Hard Rock Ballad |
| 002 | 80's Mixture Rock | 034 | Hip Hop1 | 066 | R&B | 098 | Country Rock |
| 003 | Hard Core Punk | 035 | Hip Hop2 | 067 | 6/8 R&B | 099 | Country Pop |
| 004 | Melodious Core | 036 | Pop Hip Hop | 068 | Soul Shuffle | 100 | 16-beat Country Rock |
| 005 | Ska Core | 037 | Gangsta | 069 | Motown | 101 | Country Ballad |
| 006 | Rock Boogie | 038 | Rap | 070 | Slow Blues | 102 | Country Waltz |
| 007 | Grunge Rock | 039 | Jazz Hip Hop | 071 | R&B Waltz | 103 | Bluegrass |
| 008 | Mondo Rock | 040 | Dance Swing | 072 | Rock R&B | 104 | Samba |
| 009 | 80's Irish Rock | 041 | House | 073 | Rock'n' Roll | 105 | Mambo |
| 010 | British Rock | 042 | Garage House | 074 | Train Time | 106 | Rhumba |
| 011 | 80's Rock Shuffle | 043 | 90's R&B Swing | 075 | Rockabilly | 107 | Merengue |
| 012 | College Rock | 044 | 90's R&B Slow Jam | 076 | Oldies | 108 | Cha Cha |
| 013 | Glam Rock | 045 | 90's Pop R&B | 077 | Liverpool Pop | 109 | Salsa |
| 014 | 70's Rock | 046 | 90's R&B Smooth | 078 | Surf Rock | 110 | Bossa Nova |
| 015 | 70's 8-beat Folk Rock | 047 | Pop Techno | 079 | Disco Funk | 111 | Beguin |
| 016 | 70's Art Rock | 048 | Euro Techno | 080 | 70's Disco | 112 | Tango |
| 017 | 70's Punk Rock | 049 | Eurobeat | 081 | FP Funk | 113 | Reggae |
| 018 | Pub Rock | 050 | Electro Rock | 082 | JB Funk | 114 | Swing Reggae |
| 019 | Funk Rock | 051 | Bigbeat | 083 | Jazz Funk | 115 | Dance Hall Reggae |
| 020 | Latin Rock | 052 | Digital Rock1 | 084 | Combo Jazz | 116 | Lovers Rock |
| 021 | 60's Hard Rock | 053 | Digital Rock2 | 085 | Big Band Jazz | 117 | Ska |
| 022 | 70's Hard Rock1 | 054 | Industrial Rock | 086 | Jazz Ballad | 118 | Hawaiian |
| 023 | 70's Hard Rock2 | 055 | Psychedelic Rock | 087 | Jazz Waltz | 119 | Soca |
| 024 | 70's Hard Rock & Roll | 056 | Light Pop | 088 | Fast Bebop | 120 | Klezmer |
| 025 | 16-beat Hard Rock | 057 | A.O.R. Pop | 089 | Cool Jazz | 121 | Enka |
| 026 | American Hard Rock1 | 058 | Latin Pop | 090 | Afro Jazz | 122 | Polka |
| 027 | American Hard Rock2 | 059 | 80's British Pop | 091 | Organ Ballad | 123 | Dixieland |
| 028 | 90's Progressive Hard | 060 | 16-beat Pop | 092 | Piano Ballad | 124 | Foxtrot |
| 029 | Speed Metal | 061 | 24-beat Pop | 093 | Arpeggio Ballad | 125 | Vienna Waltz |
| 030 | Power Metal | 062 | 80's / Technical Fusion | 094 | Latin Ballad | 126 | Slow Waltz |
| 031 | Thrash Metal | 063 | Detroit Pop Shuffle | 095 | 6/8 Modern Ballad | 127 | March |
| 032 | Doom Metal | 064 | Med-tempo 8-beat Rock Pop | 096 | Hard Rock Ballad | 128 | 6/8 March |
