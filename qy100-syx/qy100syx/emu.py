"""Cliente del emulador QYΩ: le habla por HTTP en lugar de por un puerto MIDI.

El emulador (`./emu serve`, en 127.0.0.1:8100) mete lo que recibe en `POST /sysex`
por su MIDI IN emulado y devuelve lo que el aparato emulado contesta. **Nada de
esto sale del ordenador ni llega al QY100 de verdad.**

Corre el firmware 1.37 real sobre un modelo de su procesador, pero no se ha
comparado sistemáticamente con el aparato (lo dice su autor). Una escritura que
el emulador acepta y devuelve igual pasó el primer filtro, no el último.
"""
import json
import os
import urllib.error
import urllib.request

from . import protocol as P
from .patternfmt import HEADER_TR

URL = os.environ.get("QYOMEGA_URL", "http://127.0.0.1:8100")


def enviar(mensajes, timeout=600):
    """Manda mensajes SysEx (bytes) y devuelve (cuántos contó, respuestas en bytes)."""
    req = urllib.request.Request(URL + "/sysex", data=b"".join(mensajes), method="POST",
                                 headers={"Content-Type": "application/octet-stream"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.load(r)
    except urllib.error.URLError as e:
        raise SystemExit("no contesta el emulador en %s (%s). Arráncalo con "
                         "`./emu serve`." % (URL, e.reason))
    if d.get("error"):
        raise SystemExit("el emulador contestó un error: %s" % d["error"])
    return d.get("sent", 0), b"".join(bytes.fromhex(h) for h in d.get("replies") or [])


def leer_patron(n):
    """Pide el patrón n (base cero) en bulk mode. Devuelve el volcado crudo."""
    _s, blob = enviar([P.bulk_mode(True), P.dump_request(P.Addr.pattern(n, HEADER_TR)),
                       P.bulk_mode(False)])
    return blob


def escribir(mensajes):
    """Escribe mensajes de volcado con el mismo encuadre que al aparato."""
    enviados, _ = enviar([P.bulk_mode(True)] + list(mensajes) + [P.bulk_mode(False)])
    return enviados
