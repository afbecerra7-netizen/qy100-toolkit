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
import os, sys                                                         # noqa: E401,E402
# Vive en una subcarpeta de qy100-syx/: el paquete `qy100syx` y las
# herramientas se importan desde la raiz. Se corre desde qy100-syx/.
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [RAIZ, os.path.join(RAIZ, "herramientas")]
import mido

MID = os.environ.get("QY100_FIRMWARE", os.path.join(
    os.path.dirname(RAIZ), "referencia", "firmware-1.37", "_QY100_v137.mid"))
# Junto al firmware, salvo que se diga otra cosa. Antes era una ruta absoluta a
# un directorio temporal de sesion, que ademas se publicaba en el repo abierto.
SALIDA = os.environ.get(
    "QY100_ROM_OUT", os.path.join(os.path.dirname(os.path.abspath(MID)),
                                  "qy100_rom.bin"))


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
