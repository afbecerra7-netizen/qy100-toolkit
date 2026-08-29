"""Conversion between QY100 and QY70 bulk SysEx dumps.

The two machines share the exact same SysEx protocol, message framing and
checksum (service manual (3-6-3), Table 1-9); the only difference in a Bulk
Dump SEQ Data message is the P nibble in the address high byte -- P=1 for
QY100, P=0 for QY70 (protocol.P_QY100 / protocol.P_QY70). That is verified
independently in this project against one of doffu's own QY70 .q1p exports,
byte-identical to the QY100 one except for that nibble (see CLAUDE.md,
"The .q1p file format is solved").

The address-remapping approach here, and the detail that the QY70 seems to
only accept a bulk write to whichever pattern/song slot is currently selected
on the device (address byte 0x7E) rather than an explicit slot number, came
from a reference implementation supplied outside this repo. Its checksum
formula does not match this project's own hardware-verified messages (tested
against a real dump: 0/70 correct, versus 70/70 for `protocol.checksum`), so
this module uses `protocol.checksum` (via `protocol.build_dump`) instead. It
also preserves the source address's type nibble (pattern vs song) instead of
assuming every message is a pattern, and frames both conversion directions in
`bulk mode ON/OFF`, since a lone unframed block is documented elsewhere in
this project to wipe the target and hang the device.
"""

from __future__ import annotations

from . import protocol as P

CURRENT_SLOT = 0x7E  # "whichever slot is selected on the device" -- same
                     # convention as the .q1p file format's own nn=0x7E.


def _hi(type_nibble: int, p: int) -> int:
    return (p << 4) | type_nibble


def _bulk_mode(p: int, on: bool) -> bytes:
    return P.param_change((_hi(0, p), 0x00, 0x00), 1 if on else 0)


def _is_seq_dump(msg: P.Message) -> bool:
    """True for a Bulk Dump SEQ Data message (a pattern/song track block)."""
    return msg.sub == P.SUB_DUMP and msg.byte_count == P.SEQ_BYTE_COUNT


def _convert(raw: bytes, dest_p: int, target_slot: int):
    """Shared core: re-address every SEQ Data block to `dest_p`'s nibble,
    keep its original type (pattern/song) and track byte, recompute the
    checksum, and frame the whole thing in bulk mode ON/OFF."""
    msgs, errs = P.parse_all(raw)
    n = 0
    out = bytearray()
    out += _bulk_mode(dest_p, True)
    for m in msgs:
        if not _is_seq_dump(m):
            continue
        type_nibble = m.addr[0] & 0x0F      # pattern (2) or song (1), preserved
        tr = m.addr[2]                      # track byte, unchanged
        new_addr = (_hi(type_nibble, dest_p), target_slot, tr)
        out += P.build_dump(new_addr, m.data, byte_count=P.SEQ_BYTE_COUNT,
                            span="bytecount+addr+data")
        n += 1
    out += _bulk_mode(dest_p, False)
    return bytes(out), n, errs


def qy100_to_qy70(raw: bytes, target_slot: int = CURRENT_SLOT):
    """Converts a QY100 bulk dump to QY70 addressing.

    `target_slot` defaults to "currently selected slot" (0x7E): navigate the
    QY70 to the destination pattern/song slot before sending, the same way
    doffu's .q1p files require. Untested against real QY70 hardware.
    """
    return _convert(raw, P.P_QY70, target_slot)


def qy70_to_qy100(raw: bytes, target_slot: int = CURRENT_SLOT):
    """Converts a QY70 bulk dump to QY100 addressing.

    `target_slot` defaults to "currently selected slot" too, for symmetry
    with the QY70 direction -- but the QY100 is confirmed (this project's own
    testing) to accept an explicit slot number directly, so pass one instead
    (0-63 for a pattern) if you want to target a specific slot without first
    navigating there on the device.
    """
    return _convert(raw, P.P_QY100, target_slot)
