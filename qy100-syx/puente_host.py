#!/usr/bin/env python3
"""Puente entre el TO HOST del QY100 (cable USB-serie) y un puerto MIDI virtual.

    .venv/bin/python puente_host.py                       # busca el cable solo
    .venv/bin/python puente_host.py --dev /dev/cu.usbserial-XXXX
    .venv/bin/python puente_host.py --baud 38400          # selector en PC-2

Con el puente en marcha, el Mac ve un puerto llamado `QY100 TO HOST` (entrada y
salida), y cualquier herramienta que acepte puerto por nombre lo usa:

    .venv/bin/python syx.py --in "QY100 TO HOST" --out "QY100 TO HOST" dump setup

**Para que sirve.** El QY100 habla MIDI por el conector TO HOST sin necesitar una
interfaz MIDI: basta un cable mini-DIN 8 a USB-serie. CoreMIDI no sabe nada de
eso (es un puerto serie, no un puerto MIDI), asi que los scripts no lo ven. Este
guion lo convierte en un puerto virtual.

## Lo medido (2026-10-13)  `[M]`

- **`HOST SELECT = PC-1` va a 31.250 baudios, 8N1.** El manual da 31.250 para
  `Mac` y 38.400 para `PC-2`, y **no dice nada de `PC-1`**. Se midio escuchando
  el cable en pasivo: a 31.250 llegan `FE` (active sensing) limpios, uno cada
  255 ms; a 38.400 llega una mezcla de `FC`/`FE`, que es lo que da un marco mal.
- **Un FTDI (RS-232) sirve en las DOS direcciones con el selector en `PC-1`.**
  El manual dice que `Mac` es RS-422 diferencial; con `PC-1`/`PC-2` es RS-232 y
  el FTDI no tiene problema. Se probo pidiendo `dump setup`: contesto, y
  `parse_all` lo decodifica sin errores.

## Lo que hay que saber  `[V]` donde no se ha medido

- **Todo lo que entra por TO HOST sale tambien por el MIDI OUT del QY100**, y lo
  que entra por MIDI IN sale por TO HOST (manual de servicio, p. 54). Un pedido
  de volcado de Yamaha no afecta al resto del equipo, pero una nota si sonaria
  en lo que cuelgue de esa salida.
- **Leer un patron entero funciona** `[M]`: el patron 4 son 16 mensajes y 2.528
  bytes, en 3,9 s; tres lecturas seguidas salen identicas byte a byte, con los 5
  bloques de la cabecera y todos los checksums bien. Por MIDI con `MIDI
  CONTROL` en `In/Out` esa misma lectura se quedaba en 2 de 5. **El estado de `MIDI
  CONTROL` no se comprobo en la prueba**, asi que 5 de 5 es coherente con `Off`
  pero no lo prueba.
- **ESCRIBIR un patron por este cable no se ha probado** `[V]`. El puerto serie no
  tiene control de flujo; los bloques largos los pausa `transfer.send_blob`, pero
  que esa pausa baste aqui esta sin medir.
- `syx.py` toma `--in/--out` **despues** del subcomando (`dump setup --in ...`):
  puestos antes los pisa el subcomando y el error dice que falta el puerto.
- Lanzado con `nohup ... &`, ignora `SIGINT`: se cierra con `SIGTERM`.
"""

import argparse
import fcntl
import glob
import os
import select
import struct
import sys
import termios
import threading
import time

import mido

#: Llamada de macOS para fijar una velocidad que no esta en la tabla de termios.
#: 31.250 no es estandar: `tcsetattr` con ese numero da EINVAL (medido).
IOSSIOSPEED = 0x80045402

NOMBRE = "QY100 TO HOST"


def encuentra_cable():
    cables = sorted(glob.glob("/dev/cu.usbserial-*"))
    if len(cables) == 1:
        return cables[0]
    raise SystemExit("Indica el cable con --dev. Encontrados: %s"
                     % (", ".join(cables) or "(ninguno)"))


def abre_serie(dev, baud):
    """8N1 crudo. Se abre en bloqueante para escribir sin EAGAIN; la lectura usa
    `select`, que no depende de eso."""
    fd = os.open(dev, os.O_RDWR | os.O_NOCTTY)
    a = termios.tcgetattr(fd)
    a[0] = a[1] = a[3] = 0                                   # iflag oflag lflag
    a[2] = termios.CS8 | termios.CREAD | termios.CLOCAL      # cflag
    a[4] = a[5] = termios.B38400            # valor valido; la velocidad real va abajo
    a[6][termios.VMIN], a[6][termios.VTIME] = 1, 0
    termios.tcsetattr(fd, termios.TCSANOW, a)
    fcntl.ioctl(fd, IOSSIOSPEED, struct.pack("I", baud))
    termios.tcflush(fd, termios.TCIOFLUSH)
    return fd


class Puente:
    def __init__(self, fd, silenciar_fe):
        self.fd = fd
        self.silenciar_fe = silenciar_fe
        self.fin = threading.Event()
        self.n_rx = self.n_tx = 0
        # `virtual=True`: rtmidi crea el puerto en CoreMIDI. Ojo con los nombres:
        # `open_output(virtual)` es lo que OTROS ven como una ENTRADA (de ahi se
        # lee), y `open_input(virtual)` lo que ven como una SALIDA (ahi se manda).
        self.hacia_mac = mido.open_output(NOMBRE, virtual=True)
        self.desde_mac = mido.open_input(NOMBRE, virtual=True, callback=self._tx)

    def _tx(self, msg):
        """Del Mac al QY100."""
        datos = bytes(msg.bytes())
        self.n_tx += len(datos)
        escrito = 0
        while escrito < len(datos):
            escrito += os.write(self.fd, datos[escrito:])

    def corre(self):
        """Del QY100 al Mac. Bloquea hasta Ctrl-C."""
        parser = mido.Parser()
        while not self.fin.is_set():
            if not select.select([self.fd], [], [], 0.2)[0]:
                continue
            datos = os.read(self.fd, 4096)
            self.n_rx += len(datos)
            parser.feed(datos)
            for msg in parser:
                if self.silenciar_fe and msg.type == "active_sensing":
                    continue
                self.hacia_mac.send(msg)

    def cierra(self):
        self.fin.set()
        self.desde_mac.close()
        self.hacia_mac.close()
        os.close(self.fd)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dev", help="cable USB-serie (por defecto, el unico /dev/cu.usbserial-*)")
    ap.add_argument("--baud", type=int, default=31250,
                    help="31250 con HOST SELECT = PC-1 o Mac; 38400 con PC-2")
    ap.add_argument("--sin-fe", action="store_true",
                    help="no pasar el active sensing (el QY100 manda uno cada 255 ms)")
    args = ap.parse_args()

    dev = args.dev or encuentra_cable()
    fd = abre_serie(dev, args.baud)
    p = Puente(fd, args.sin_fe)
    print("puente en marcha: %s @ %d baud  <->  puerto MIDI virtual %r"
          % (dev, args.baud, NOMBRE))
    print("Ctrl-C para cerrar.")
    t0 = time.time()
    try:
        p.corre()
    except KeyboardInterrupt:
        pass
    finally:
        p.cierra()
        print("\ncerrado tras %.0f s: %d bytes del QY100, %d bytes hacia el QY100"
              % (time.time() - t0, p.n_rx, p.n_tx))
    return 0


if __name__ == "__main__":
    sys.exit(main())
