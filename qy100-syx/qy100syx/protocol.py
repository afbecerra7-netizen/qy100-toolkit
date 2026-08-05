"""Protocolo SysEx del QY100.

Todo lo de aqui sale del service manual, seccion (3-6-3) BULK DUMP and PARAMETER
CHANGE (p. 59) y de la Tabla 1-9 SEQUENCER PARAMETER ADDRESS (p. 68). Ver
`manuales-md/QY100_Service_Manual.md`, que trae ambas ya corregidas.

Formatos de mensaje
-------------------
    Bulk Dump SEQ Data   F0 43 00 5F 01 13 aH aM aL <147 bytes> ck F7
    Bulk Dump Data       F0 43 00 5F bH bL aH aM aL <bytes>     ck F7
    Parameter Change     F0 43 10 5F aH aM aL dd                   F7
    Bulk Dump Request    F0 43 20 5F aH aM aL                      F7
    Parameter Request    F0 43 30 5F aH aM aL                      F7

El byte de subestado codifica la operacion: 00 volcado, 10 cambio de parametro,
20 peticion de volcado, 30 peticion de parametro.
"""

from __future__ import annotations

SOX, EOX = 0xF0, 0xF7
YAMAHA = 0x43
MODEL_QY100 = 0x5F

SUB_DUMP = 0x00
SUB_PARAM = 0x10
SUB_DUMP_REQ = 0x20
SUB_PARAM_REQ = 0x30

# P = 1 en el QY100, 0 en el QY70. De ahi que los archivos de ambos equipos sean
# el mismo formato con el byte alto cambiado.
P_QY100 = 1
P_QY70 = 0


def _hi(nibble: int, p: int = P_QY100) -> int:
    return (p << 4) | nibble


class Addr:
    """Direcciones de la Tabla 1-9, ya con P=1 aplicado."""

    BULK_MODE = (_hi(0), 0x00, 0x00)          # size 1

    @staticmethod
    def song(n: int, track: int = 0):
        """Cancion n (0-19). 147 bytes por bloque."""
        if not 0 <= n <= 19:
            raise ValueError("cancion fuera de rango 0-19: %d" % n)
        return (_hi(1), n, track)

    SONG_ALL = (_hi(1), 0x7F, 0x00)           # solo peticion

    @staticmethod
    def pattern(n: int, track: int = 0):
        """Patron de usuario n (0-63). 147 bytes por bloque."""
        if not 0 <= n <= 63:
            raise ValueError("patron fuera de rango 0-63: %d" % n)
        return (_hi(2), n, track)

    PATTERN_ALL = (_hi(2), 0x7F, 0x00)        # solo peticion
    SETUP = (_hi(3), 0x00, 0x00)              # 32 bytes
    ALL = (_hi(4), 0x00, 0x00)                # solo peticion
    INFO_SONG = (_hi(5), 0x00, 0x00)          # 320, solo transmite
    INFO_PATTERN_1_32 = (_hi(5), 0x01, 0x00)  # 512, solo transmite
    INFO_PATTERN_33_64 = (_hi(5), 0x01, 0x01)  # 512, solo transmite

    @staticmethod
    def effect(n: int):
        return (0x16, n, 0x00)

    EFFECT_ALL = (0x16, 0x7F, 0x00)

    # Comandos destructivos.
    #
    # OJO: en estos el numero del elemento va en el BYTE DE DATOS, no en la
    # direccion. Confirmado contra las plantillas del propio Data Filer de
    # Yamaha (QY100.exe, offset 214600), donde aparecen como
    #     f0 43 10 5f 18 00 00 ff f7   con ff = marcador del numero
    # Usa clear_song() / clear_pattern(), que lo arman bien. 0x7F = todos.
    CLEAR_SONG = (_hi(8), 0x00, 0x00)
    CLEAR_PATTERN = (_hi(8), 0x01, 0x00)
    # La tabla lista 08 02 00 (borra cancion y patron) y 18 02 00 (ademas
    # efectos) como filas distintas, con los valores literales y no con P.
    CLEAR_SONG_AND_PATTERN = (0x08, 0x02, 0x00)
    CLEAR_ALL_WITH_EFFECTS = (0x18, 0x02, 0x00)
    INIT_EFFECT = (0x18, 0x03, 0x00)


ALL_ITEMS = 0x7F        # valor de "todos" en los comandos de borrado


DESTRUCTIVE = {
    Addr.CLEAR_SONG, Addr.CLEAR_PATTERN, Addr.CLEAR_SONG_AND_PATTERN,
    Addr.CLEAR_ALL_WITH_EFFECTS, Addr.INIT_EFFECT,
}

SEQ_BYTE_COUNT = 147          # fijo para SONG DATA y PATTERN DATA


def addr_name(addr) -> str:
    """Nombre legible de una direccion, para los informes."""
    h, m, l = addr
    if addr == Addr.BULK_MODE:
        return "bulk mode on/off"
    if h == _hi(1):
        return "todas las canciones" if m == 0x7F else "cancion %d pista %d" % (m + 1, l)
    if h == _hi(2):
        return "todos los patrones" if m == 0x7F else "patron de usuario %d pista %d" % (m + 1, l)
    if h == _hi(3):
        return "setup"
    if h == _hi(4):
        return "todo"
    if h == _hi(5):
        return {(0x00, 0x00): "info de canciones",
                (0x01, 0x00): "info de patrones 1-32",
                (0x01, 0x01): "info de patrones 33-64"}.get((m, l), "info %02X %02X" % (m, l))
    if h == 0x16:
        return "efecto de guitarra %s" % ("todos" if m == 0x7F else m + 1)
    if h in (0x08, 0x18):
        return {(0x00, 0x00): "CLEAR SONG", (0x01, 0x00): "CLEAR PATTERN",
                (0x02, 0x00): "CLEAR ALL", (0x03, 0x00): "INIT EFFECT"}.get(
                    (m, l), "comando %02X %02X" % (m, l))
    return "desconocida %02X %02X %02X" % (h, m, l)


# ---------------------------------------------------------------- checksum

def checksum(payload) -> int:
    """Complemento a dos de la suma, a 7 bits. Convencion Yamaha."""
    return (-sum(payload)) & 0x7F


# El manual no dice sobre que rango exacto se calcula. Estas son las tres
# convenciones plausibles; `detect_checksum_span` decide cual usa el equipo
# mirando un volcado real, en vez de que lo adivinemos nosotros.
CHECKSUM_SPANS = {
    "bytecount+addr+data": lambda m: m.body,
    "addr+data": lambda m: m.body[m.count_len:],
    "data": lambda m: m.data,
}


# ---------------------------------------------------------------- mensajes

def _frame(sub: int, tail) -> bytes:
    return bytes([SOX, YAMAHA, sub, MODEL_QY100] + list(tail) + [EOX])


def dump_request(addr) -> bytes:
    """Pide al QY100 que vuelque lo que haya en esa direccion."""
    return _frame(SUB_DUMP_REQ, list(addr))


def param_request(addr) -> bytes:
    return _frame(SUB_PARAM_REQ, list(addr))


def param_change(addr, value: int) -> bytes:
    """Cambio de parametro de un byte (bulk mode, comandos de borrado)."""
    if not 0 <= value <= 0x7F:
        raise ValueError("el valor debe caber en 7 bits: %d" % value)
    return _frame(SUB_PARAM, list(addr) + [value])


def bulk_mode(on: bool) -> bytes:
    return param_change(Addr.BULK_MODE, 1 if on else 0)


# ---------------------------------------------------------------- borrado
#
# **Los comandos de borrado exigen `bulk mode ON`**, igual que las peticiones de
# volcado. Verificado el 2026-07-29: un CLEAR ALL suelto se ignora sin protestar
# —los patrones seguian intactos despues— y el mismo mensaje enmarcado como
# `bulk mode ON -> CLEAR ALL -> bulk mode OFF` borro todo. El manual no lo dice,
# pero encaja con el volcado que hace el propio equipo desde el panel, que
# empieza justo asi.

def clear_song(n=ALL_ITEMS) -> bytes:
    """Borra la cancion n (0-19), o todas con ALL_ITEMS (0x7F)."""
    if n != ALL_ITEMS and not 0 <= n <= 19:
        raise ValueError("cancion fuera de rango 0-19 (o 0x7F para todas): %r" % n)
    return param_change(Addr.CLEAR_SONG, n)


def clear_pattern(n=ALL_ITEMS) -> bytes:
    """Borra el patron de usuario n (0-63), o todos con ALL_ITEMS (0x7F)."""
    if n != ALL_ITEMS and not 0 <= n <= 63:
        raise ValueError("patron fuera de rango 0-63 (o 0x7F para todos): %r" % n)
    return param_change(Addr.CLEAR_PATTERN, n)


def clear_all() -> bytes:
    """Borra canciones, patrones, frases y efectos. El byte de datos es fijo 00."""
    return param_change(Addr.CLEAR_ALL_WITH_EFFECTS, 0)


def build_dump(addr, data, byte_count=None, span="bytecount+addr+data") -> bytes:
    """Arma un mensaje de volcado. Se usa para reenviar datos al equipo."""
    data = list(data)
    n = len(data) if byte_count is None else byte_count
    body = [(n >> 7) & 0x7F, n & 0x7F] + list(addr) + data
    if span == "addr+data":
        ck = checksum(body[2:])
    elif span == "data":
        ck = checksum(data)
    else:
        ck = checksum(body)
    return _frame(SUB_DUMP, body + [ck])


# ---------------------------------------------------------------- parseo

class Message:
    """Un mensaje SysEx del QY100 ya desarmado."""

    def __init__(self, raw: bytes):
        self.raw = bytes(raw)
        if len(raw) < 6 or raw[0] != SOX or raw[-1] != EOX:
            raise ValueError("no es un SysEx completo (%d bytes)" % len(raw))
        if raw[1] != YAMAHA:
            raise ValueError("no es de Yamaha: ID %02X" % raw[1])
        self.sub = raw[2]
        self.model = raw[3]
        self.count_len = 2

        if self.sub == SUB_DUMP:
            self.body = list(raw[4:-2])       # bytecount + addr + data
            self.byte_count = (raw[4] << 7) | raw[5]
            self.addr = (raw[6], raw[7], raw[8])
            self.data = list(raw[9:-2])
            self.stored_checksum = raw[-2]
        elif self.sub in (SUB_DUMP_REQ, SUB_PARAM_REQ):
            self.body = list(raw[4:-1])
            self.byte_count = 0
            self.addr = (raw[4], raw[5], raw[6])
            self.data = []
            self.stored_checksum = None
        elif self.sub == SUB_PARAM:
            self.body = list(raw[4:-1])
            self.byte_count = 1
            self.addr = (raw[4], raw[5], raw[6])
            self.data = list(raw[7:-1])
            self.stored_checksum = None
        else:
            raise ValueError("subestado desconocido: %02X" % self.sub)

    @property
    def kind(self) -> str:
        return {SUB_DUMP: "dump", SUB_PARAM: "param",
                SUB_DUMP_REQ: "dump-request",
                SUB_PARAM_REQ: "param-request"}[self.sub]

    def verify(self, span="bytecount+addr+data"):
        """True/False si hay checksum, None si el mensaje no lleva."""
        if self.stored_checksum is None:
            return None
        return checksum(CHECKSUM_SPANS[span](self)) == self.stored_checksum

    @property
    def length_ok(self) -> bool:
        return self.sub != SUB_DUMP or len(self.data) == self.byte_count

    def __repr__(self):
        return "<%s %s %d bytes>" % (self.kind, addr_name(self.addr), len(self.data))


def split_sysex(blob: bytes):
    """Separa un flujo de bytes en mensajes SysEx completos, ignorando basura."""
    out, i, n = [], 0, len(blob)
    while i < n:
        start = blob.find(bytes([SOX]), i)
        if start < 0:
            break
        end = blob.find(bytes([EOX]), start)
        if end < 0:
            break
        out.append(blob[start:end + 1])
        i = end + 1
    return out


def parse_all(blob: bytes):
    """Devuelve (mensajes_ok, [(indice, error), ...])."""
    msgs, errs = [], []
    for k, raw in enumerate(split_sysex(blob)):
        try:
            msgs.append(Message(raw))
        except ValueError as e:
            errs.append((k, str(e)))
    return msgs, errs


def detect_checksum_span(messages):
    """Decide empiricamente que rango cubre el checksum.

    El manual no lo especifica, asi que en vez de adivinar se prueban las tres
    convenciones contra un volcado real y gana la que valide todo.
    """
    scores = {}
    for name in CHECKSUM_SPANS:
        ok = sum(1 for m in messages if m.verify(name) is True)
        total = sum(1 for m in messages if m.stored_checksum is not None)
        scores[name] = (ok, total)
    best = max(scores, key=lambda k: scores[k][0])
    return best, scores


# ------------------------------------------------- empaquetado 7 bits

def unpack_7in8(data):
    """Desempaqueta el esquema Yamaha de MSB compartido: 8 bytes -> 7 bytes.

    El manual solo dice "8bit original data will be converted into 7bit MIDI
    data" sin precisar el metodo. Este es el que usa el propio firmware del
    QY100, verificado al decodificar `_QY100_v137.mid`, asi que es el primer
    candidato. `inspect` reporta si el resultado tiene pinta razonable.
    """
    out = bytearray()
    for g in range(0, len(data) - len(data) % 8, 8):
        msb = data[g]
        for k in range(7):
            out.append(data[g + 1 + k] | (((msb >> k) & 1) << 7))
    return bytes(out)


def unpack_nibbles(data):
    """Alternativa: dos nibbles de 4 bits por byte (MSB primero)."""
    out = bytearray()
    for i in range(0, len(data) - len(data) % 2, 2):
        out.append(((data[i] & 0x0F) << 4) | (data[i + 1] & 0x0F))
    return bytes(out)
