# qy100-remote-transmission

Live-captured mappings of the standard Yamaha **XG Parameter Change** messages
(`F0 43 1n 4C aa bb cc dd... F7`) the QY100 sends and accepts for individual
panel settings — a different, model-agnostic protocol family from the
QY100-specific Bulk Dump/Parameter Change protocol (`43 x0 5F`) that
[`qy100-syx`](../qy100-syx/) decodes.

Found by listening on the MIDI IN port live while operating the panel, not
from the manual. See [`../CLAUDE.md`](../CLAUDE.md)'s "Remote control over
MIDI" section for the full writeup: what's silent (plain navigation), what's
one-directional telemetry (the Undo/Redo job's full-mixer resync burst), and
what's genuinely bidirectional and remote-settable (effect type, so far).

## What's here

| File | Contents |
| --- | --- |
| [`effect_types.json`](effect_types.json) | The pattern effect-type selector at address `02 01 40` — full family/variant table, verified bidirectional. Also documents a full sweep of every unmapped value in range: none are hidden effects, each block cleanly falls back to its own default (`No Effect` below `40`, `Thru` at/above `40`). |
| [`fx_send_levels.json`](fx_send_levels.json) | Reverb Send (`02 01 58`) and Chorus Send (`02 01 59`) — continuous 0–127 knobs, sequential addresses. Reverb confirmed bidirectional. Also records a negative result: the next address in sequence (`02 01 5a`, guessed as a Variation send) produced no effect — adjacent addresses aren't reliably related parameters. |
| [`effect_parameters.json`](effect_parameters.json) | Per-effect-type editable parameters from the panel's Variation Edit menu, captured under Hall 1: Reverb Time (`02 01 42`, confirmed bidirectional), Diffusion (`44`), Initial Delay (`46`), HPF Cutoff (`48`), LPF Cutoff (`4a`). Each slot is a clean +2 from the last. None reach the full `00–7f` range the send levels do — every parameter has its own real ceiling. Not yet confirmed whether the same addresses mean the same thing under other effect types. |
| [`xg_controller_equivalents.json`](xg_controller_equivalents.json) | The CC, NRPN and RPN messages that reach the same Multi Part and Drum Setup parameters as their XG addresses (Volume = CC 7, Filter Cutoff = CC 74, EG Decay = NRPN `01 64`, drum level = NRPN `1A <note>`, and so on), with the one value conversion that matters. From the Data List, not yet confirmed parameter by parameter on the device. |

**Every address above now has an XG name.** They all sit in the XG Variation
block: `02 01 40` is Variation Type, `42` to `4A` are Variation Parameters 1 to 5
(two bytes each), `58`/`59` are Send Variation to Reverb/Chorus, and `5A` is
Variation Connection, which only takes `00` or `01`. See
[`../docs/xg-remote-control.md`](../docs/xg-remote-control.md) for that decode,
the rest of the XG message family (block writes, reading values back), and
what to test next.

Meant to be extended as more parameters get captured and verified the same
way: change a setting on the panel, note what SysEx/CC came out, then confirm
it's actually settable (not just telemetry) by sending the same bytes back
and checking the panel reacts.
