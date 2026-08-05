"""Decodifica la ROM del QY100 desde el .mid de actualizacion. SOLO LECTURA.

    F0 43 00 5F 00 40 <addr:3B 7-bit> <64B empaquetados> <checksum> F7

Empaquetado 7-en-8 con dos detalles que costaron encontrar:

  - el byte de bits altos va **al FINAL** de cada grupo de 8, no al principio
  - dentro de ese byte, el **bit 6 corresponde al primer dato** (MSB primero)

El primero lo delato la tabla de kits: con el byte al principio salia
`Stand.it`, con un cero donde va la K. El segundo no se podia distinguir con
texto ASCII puro —los bits altos son 0 y da igual el orden— y hizo falta un
nombre con un byte de bit alto: `Sil.nKit` frente a `SilenKit`.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mido

MID = os.environ.get("QY100_FIRMWARE", os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "QY100_1.37", "_QY100_v137.mid"))
SALIDA = "/private/tmp/claude-501/-Users-felipebecerra-Proyectos-Yamaha/e7c8c4d4-1249-4761-965d-9929f6f431d4/scratchpad/qy100_rom.bin"


def unpack(d):
    out = bytearray()
    for g in range(0, len(d) - len(d) % 8, 8):
        gr = d[g:g + 8]
        msb = gr[7]
        for k in range(7):
            out.append(gr[k] | (((msb >> (6 - k)) & 1) << 7))
    return bytes(out)


rom = bytearray(); n = 0
for msg in mido.MidiFile(MID):
    if msg.type != "sysex":
        continue
    d = bytes(msg.data)
    if d[:5] == bytes([0x43, 0x00, 0x5F, 0x00, 0x40]) and len(d) >= 72:
        rom += unpack(d[8:8 + 64]); n += 1
print("%d bloques, %d bytes" % (n, len(rom)))
open(SALIDA, "wb").write(rom)
