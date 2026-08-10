"""Formato interno de los patrones del QY100 — DESCIFRADO.

La gramatica de eventos salio del decodificador del propio Data Filer de Yamaha
(`QY100.exe`, VA 0x405f20 y siguientes) y esta **verificada de forma
independiente** contra nuestros volcados: decodifica correctamente las siete
capturas de referencia, incluidos los cambios de altura, velocity, posicion y
duracion que hicimos a proposito.

Dos cosas que estuvimos entendiendo mal mucho tiempo:

1. **El payload NO es un flujo de bits sin alinear.** Los 147 bytes de 7 bits se
   concatenan en 1029 bits, de los que se toman **1024 = 128 bytes de 8 bits** y
   se descartan los 5 ultimos. Sobre ESE flujo desempaquetado los campos si estan
   alineados a byte. Lo que parecia "campos a mitad de byte" era el efecto de
   mirar el stream en unidades de 7 bits.

2. **Los eventos son de longitud variable**, no registros de 48 bits. Lo que
   parecia un registro fijo era la suma de un evento de nota (4 bytes) y uno de
   tiempo (2 bytes).

Y de paso corrige dos valores que habiamos "verificado" mal: la velocity real es
112/32, no 56/16 (leiamos 7 bits de un byte de 8), y el campo de duracion que
daba 27 y 204 era una lectura desalineada del gate, que vale 108 y 432.
"""

from __future__ import annotations

CLOCKS_PER_QUARTER = 480     # resolucion del secuenciador (manual, pag. 3087)
EVENT_STREAM_START = 26      # donde empieza la lista de eventos en el bloque
BLOCK_BYTES = 147            # payload SysEx (ByteCount 0x01 0x13)
UNPACKED_BYTES = 128


# --- Direccionamiento de secciones -------------------------------------
#
# El byte bajo de la direccion (`12 nn tr`) codifica seccion y pista juntas.
# Verificado grabando en INTRO y en MAIN A: `12 00 00` y `12 00 08`.
TRACKS_PER_SECTION = 8
SECTIONS = ["Intro", "Main A", "Main B", "Fill AB", "Fill BA", "Ending"]
HEADER_TR = 0x7F


def track_byte(section: int, track: int = 0) -> int:
    if not 0 <= section < len(SECTIONS):
        raise ValueError("seccion fuera de rango 0-5: %d" % section)
    if not 0 <= track < TRACKS_PER_SECTION:
        raise ValueError("pista fuera de rango 0-7: %d" % track)
    return section * TRACKS_PER_SECTION + track


def describe_tr(tr: int) -> str:
    if tr == HEADER_TR:
        return "cabecera del patron"
    sec, t = divmod(tr, TRACKS_PER_SECTION)
    if sec < len(SECTIONS):
        return "%s pista %d" % (SECTIONS[sec], t)
    return "tr %d (fuera del mapa conocido)" % tr


# --- Empaquetado 7 <-> 8 bits -------------------------------------------

def unpack(payload) -> bytes:
    """147 bytes de 7 bits -> 128 bytes de 8 bits. Los 5 bits sobrantes se tiran.

    El descarte es **por bloque**, no continuo entre bloques.
    """
    bits = []
    for b in payload:
        for k in range(6, -1, -1):
            bits.append((b >> k) & 1)
    out = bytearray()
    for i in range(0, (len(bits) // 8) * 8, 8):
        v = 0
        for k in range(8):
            v = (v << 1) | bits[i + k]
        out.append(v)
    return bytes(out)


def pack(data, size=BLOCK_BYTES) -> bytes:
    """Inversa de unpack: bytes de 8 bits -> bytes de 7 bits, rellenando a `size`."""
    bits = []
    for b in data:
        for k in range(7, -1, -1):
            bits.append((b >> k) & 1)
    bits += [0] * (size * 7 - len(bits))
    out = bytearray()
    for i in range(0, size * 7, 7):
        v = 0
        for k in range(7):
            v = (v << 1) | bits[i + k]
        out.append(v)
    return bytes(out)


# --- Gramatica de eventos -----------------------------------------------
#
# Del clasificador del Data Filer (VA 0x405f20) y su rutina de nota (0x406130).
# Verificados contra nuestros datos: los eventos de tiempo, los de nota y el fin
# de pista. Los demas estados salen del binario pero no los hemos visto en datos
# reales, asi que se saltan en vez de inventarles significado.

END_OF_TRACK = 0xF2


class Note:
    __slots__ = ("pitch", "velocity", "gate", "time")

    def __init__(self, pitch, velocity, gate, time):
        self.pitch, self.velocity, self.gate, self.time = pitch, velocity, gate, time

    def __repr__(self):
        return "Note(pitch=%d, vel=%d, gate=%d, t=%d)" % (
            self.pitch, self.velocity, self.gate, self.time)

    def __eq__(self, o):
        return (isinstance(o, Note) and
                (self.pitch, self.velocity, self.gate, self.time) ==
                (o.pitch, o.velocity, o.gate, o.time))


def decode_track(payload, start=EVENT_STREAM_START, max_events=512, estricto=True):
    """Decodifica una pista de UN bloque. Devuelve (notas, duracion_en_relojes).

    `payload` son los 147 bytes crudos del bloque; el desempaquetado se hace
    aqui. El tiempo de cada nota es absoluto, en relojes desde el inicio del
    patron.

    Para una pista que ocupe varios bloques usa `decode_blocks`: aqui el flujo
    se corta en el borde del bloque y se pierden los eventos siguientes.
    """
    return decode_events(unpack(payload), start, max_events, estricto)


def decode_blocks(payloads, start=EVENT_STREAM_START, max_events=4096, estricto=True):
    """Decodifica una pista repartida en varios bloques.

    **Verificado**: solo el PRIMER bloque lleva el prefijo de 26 bytes. Los
    siguientes son continuacion pura del flujo de eventos, desde su byte 0. Se
    vio en el patron 4 de `dumps/12-callback-a.syx`, donde el segundo bloque
    empieza directamente por `A1 6D D1 57 56 64` — delta y nota, no cabecera.

    Los bloques tienen que venir en el orden en que los mando el equipo.
    """
    trozos = [unpack(p) for p in payloads]
    if not trozos:
        return [], 0
    flujo = trozos[0][start:] + b"".join(trozos[1:])
    return decode_events(flujo, 0, max_events, estricto)


def decode_events(d, start=EVENT_STREAM_START, max_events=512, estricto=True):
    """Recorre un flujo YA desempaquetado. Devuelve (notas, relojes_totales).

    Comprueba que cada evento quepa entero antes de leerlo: un evento partido
    por el final del buffer solia reventar con IndexError.

    **Solo entiende notas y tiempos, y eso es una limitacion real.** El flujo
    admite ademas control change, aftertouch, RPN/NRPN, program change, bank
    select, pitch bend y cambio de voz a mitad de pista — documentados en la
    hoja de datos de qyTools, no aqui. Ante un byte que no reconoce este
    decodificador avanza uno y sigue, asi que **una pista con cualquiera de esos
    eventos se desincroniza en silencio**: las notas posteriores salen con la
    altura y el tiempo equivocados, sin error y sin señal.

    No ha mordido todavia porque todo lo decodificado han sido pistas de notas,
    grabadas o generadas por nosotros. Muerde en cuanto se lea una pista que
    alguien haya tocado con rueda de modulacion o pedal.
    """
    i, t = start, 0
    notas, desconocidos = [], []
    for _ in range(max_events):
        if i >= len(d):
            break
        s = d[i]
        # un evento truncado al final del buffer no es un evento
        ancho = (1 if s < 0xA0 else 2 if s < 0xC0 else
                 3 if s < 0xD0 else 4 if s < 0xE0 else 5 if s < 0xF0 else 1)
        if i + ancho > len(d):
            break
        if 0x80 <= s <= 0x9F:                       # tiempo corto, 1 byte
            t += s & 0x1F
            i += 1
        elif 0xA0 <= s <= 0xBF:                     # tiempo, 2 bytes
            t += ((s & 0x1F) << 7) | d[i + 1]
            i += 2
        elif 0xC0 <= s <= 0xCF:                     # nota, gate de 4 bits
            notas.append(Note(d[i + 1], d[i + 2], s & 0x0F, t))
            i += 3
        elif 0xD0 <= s <= 0xDF:                     # nota, gate de 11 bits
            notas.append(Note(d[i + 2], d[i + 3], ((s & 0x0F) << 7) | d[i + 1], t))
            i += 4
        elif 0xE0 <= s <= 0xEF:                     # nota, gate de 18 bits
            notas.append(Note(d[i + 3], d[i + 4],
                              ((s & 0x0F) << 14) | (d[i + 1] << 7) | d[i + 2], t))
            i += 5
        elif s == END_OF_TRACK:
            break
        elif s == 0xF0:                             # marcador, no avanza el tiempo
            i += 2
        else:
            # **Un estado desconocido no se salta.** Avanzar un byte y seguir
            # deja el flujo desalineado, y a partir de ahi las notas salen con
            # la altura y el tiempo equivocados sin que nada lo delate. Es
            # preferible parar y decir donde.
            desconocidos.append((i, s))
            if estricto:
                raise ValueError(
                    "evento no reconocido 0x%02X en el byte %d. El flujo admite "
                    "control change, aftertouch, pitch bend y cambio de voz, que "
                    "este decodificador no entiende; saltarlos desalinea todo lo "
                    "que venga despues. Usa estricto=False para leer solo hasta "
                    "aqui." % (s, i))
            break
    return notas, t


def encode_track(notas, total_clocks, start=EVENT_STREAM_START, prefix=None):
    """Construye el flujo de eventos. Devuelve 128 bytes SIN empaquetar.

    `prefix` son los `start` bytes de cabecera que van delante. Reutilizalos de
    un bloque real: llevan informacion que todavia no entendemos, pero copiarlos
    tal cual funciona.

    **VERIFICADO contra el equipo** (2026-07-29): un arpegio de 12 negras
    construido entero desde cero se escribio en Main A y sono. Y confirmo que
    escribir un bloque **reemplaza** la pista: las 2 notas que habia antes
    desaparecieron sin mandar ningun CLEAR.

    En un solo bloque caben **16 notas** (99 bytes utiles, 6 por nota con
    delta > 31). Para pistas mas largas usa `encode_blocks`, que las encadena.
    """
    out = _event_stream(notas, total_clocks, prefix, start)
    if len(out) > UNPACKED_BYTES:
        raise ValueError("no cabe en un bloque: %d bytes (usa encode_blocks)"
                         % len(out))
    return out + bytes(UNPACKED_BYTES - len(out))


MAX_DELTA = (0x1F << 7) | 0x7F      # 4095, el tope de un evento de tiempo


def _delta_bytes(delta: int) -> bytes:
    """Un salto de tiempo, encadenando varios eventos si no cabe en uno.

    El evento mas largo (`An`/`Bn`) llega a 4095 relojes, poco mas de dos
    compases de 4/4. Un silencio mayor se parte en varios eventos seguidos.
    """
    if delta < 0:
        raise ValueError("delta negativo")
    out = bytearray()
    while delta > MAX_DELTA:
        out += bytes([0xA0 | (MAX_DELTA >> 7), MAX_DELTA & 0x7F])
        delta -= MAX_DELTA
    if delta == 0:
        return bytes(out)
    if delta <= 0x1F:
        out += bytes([0x80 | delta])
    else:
        out += bytes([0xA0 | ((delta >> 7) & 0x1F), delta & 0x7F])
    return bytes(out)


PAD_BYTE = 0x40         # con lo que el QY100 rellena la cola del ultimo bloque


MARCADOR_INICIO = bytes([0xF0, 0x00])
"""Evento con el que arranca el flujo de TODA pista grabada en el equipo.

Verificado en las tres pistas que grabo el propio QY100: la de Intro vacia
(`F0 00 | t+3840 | FIN`) y las dos con notas. Las pistas que escribiamos
nosotros no lo llevaban y **eso colgaba el editor del equipo**: reproducir
funcionaba —por eso las oiamos— pero al entrar en edicion se quedaba con el
icono de reloj fijo y habia que apagarlo.
"""


def _event_stream(notas, total_clocks, prefix, start, marcador=True):
    """Prefijo + eventos + fin de pista, sin empaquetar ni trocear."""
    cab = bytearray(prefix[:start]) if prefix else bytearray()
    cab += bytes(start - len(cab))
    out = bytearray(cab)
    if marcador:
        out += MARCADOR_INICIO
    t = 0
    for n in sorted(notas, key=lambda x: x.time):
        delta = n.time - t
        if delta < 0:
            raise ValueError("notas fuera de orden")
        out += _delta_bytes(delta)
        t = n.time
        # Dos formas de evento de nota segun lo que dure: la corta (`Dn`) llega
        # a 2047 relojes y la larga (`En`) a 262143. Hasta que aparecieron los
        # drones de dos compases solo se usaba la corta, y una nota sostenida
        # reventaba con "gate fuera de rango".
        if not 0 <= n.gate < (1 << 18):
            raise ValueError("gate fuera del rango soportado: %d "
                             "(el maximo son %d relojes)" % (n.gate, (1 << 18) - 1))
        if n.gate < (1 << 11):
            out += bytes([0xD0 | ((n.gate >> 7) & 0x0F), n.gate & 0x7F,
                          n.pitch & 0x7F, n.velocity & 0x7F])
        else:
            out += bytes([0xE0 | ((n.gate >> 14) & 0x0F), (n.gate >> 7) & 0x7F,
                          n.gate & 0x7F, n.pitch & 0x7F, n.velocity & 0x7F])
    if total_clocks < t:
        raise ValueError("la pista dura menos que su ultima nota")
    out += _delta_bytes(total_clocks - t)
    out += bytes([END_OF_TRACK])
    return bytes(out)


def encode_blocks(notas, total_clocks, prefix, start=EVENT_STREAM_START):
    """Construye la pista entera, encadenando bloques si hace falta.

    Devuelve una lista de payloads de 147 bytes, listos para `build_dump`, en
    el orden en que hay que mandarlos.

    **Verificado contra el equipo** (2026-07-29) grabando 32 notas de altura
    ascendente conocida: el QY100 las devolvio en dos bloques y se releen como
    48..79 exactas. El modelo es:

      - solo el PRIMER bloque lleva el prefijo de 26 bytes
      - los siguientes son continuacion pura del flujo, desde su byte 0
      - el `F2` de fin va una sola vez, al final del ultimo bloque
      - la cola del ultimo bloque se rellena con 0x40
      - el desempaquetado 7->8 es POR BLOQUE (se descartan 5 bits en cada uno),
        no continuo a lo largo de la pista

    **Limitacion: solo se reproducen notas y tiempos.** El flujo real del equipo
    trae ademas un marcador `F0 xx` por pista que aqui no se genera, asi que
    re-codificar una pista existente lo pierde. Para generar desde cero da igual
    —el arpegio escrito el 2026-07-29 sonaba sin ningun `F0`—, pero para un
    ida y vuelta fiel todavia no sirve. Por eso los bytes salen distintos a los
    del equipo aunque las notas se relean identicas.
    """
    flujo = bytearray(_event_stream(notas, total_clocks, prefix, start))
    flujo += bytes([PAD_BYTE]) * ((-len(flujo)) % UNPACKED_BYTES)
    return [pack(bytes(flujo[i:i + UNPACKED_BYTES]))
            for i in range(0, len(flujo), UNPACKED_BYTES)]


# --- Ayudas ------------------------------------------------------------

def position_to_bar_beat(clocks, beats_per_bar=4):
    por_compas = CLOCKS_PER_QUARTER * beats_per_bar
    compas, resto = divmod(clocks, por_compas)
    tiempo, sobra = divmod(resto, CLOCKS_PER_QUARTER)
    return compas + 1, tiempo + 1, sobra


def bar_beat_to_position(bar, beat=1, beats_per_bar=4):
    return ((bar - 1) * beats_per_bar + (beat - 1)) * CLOCKS_PER_QUARTER


def gate_for(figure_clocks, ratio=0.90):
    """Gate por defecto del QY100: el 90 % de la figura.

    Observado: semicorchea (120) -> gate 108; negra (480) -> gate 432.
    """
    return int(round(figure_clocks * ratio))


# ---------------------------------------------------------------- pendiente
#
#   - COMO SE ENCADENAN VARIOS BLOQUES en una misma pista. Es el limite
#     practico hoy: en un bloque solo caben 16 notas, y un arpegio de
#     semicorcheas en 3 compases son 48. Nunca hemos visto una pista de mas de
#     un bloque porque todas las pruebas fueron demasiado pequenas.
#   - los 26 bytes de cabecera del PRIMER bloque de cada pista. Lo poco que se
#     sabe:
#       * bytes 0-11: doce caracteres, en nuestros volcados todo espacios (0x20)
#         -> con toda probabilidad el nombre de la frase
#       * byte 12: HIPOTESIS, no verificado. Vale compases_de_la_seccion - 1,
#         el mismo valor que guarda la cabecera del patron. Coincide en 9 de 9
#         observaciones limpias, PERO todas vienen de patrones con las mismas
#         longitudes ([2,3,2,1,1,2]), asi que en realidad son dos casos
#         repetidos. Para confirmarlo hace falta un patron con secciones de
#         distinta longitud. El archivo de 32 compases de doffu no sirve: trae
#         solo la cabecera, sin bloques de pista.
#   - los 5 bloques `12 nn 7F`: cabecera del patron (longitud, signatura,
#     tipo de frase...)
#   - los estados F1, F3-FF: el binario les asigna longitud pero no los hemos
#     visto en datos, asi que no sabemos que significan


# --- Cabecera del patron (bloque `12 nn 7F`, el primero) -----------------
#
# Descifrado comparando nuestros volcados contra el archivo de desbloqueo de
# 32 compases de QY100 Explorer (doffu). Verificado en cinco capturas: la
# longitud declarada coincide siempre con la duracion real de las pistas.

# El tempo son los DOS PRIMEROS bytes de la cabecera, big-endian, en **decimas
# de BPM**: 120,0 se guarda como 1200 = `04 B0`. Se encontro sin tocar el equipo,
# viendo que el valor por defecto estaba a la vista en el bloque 0, y se confirmo
# escribiendo 1040 y leyendo 104 en pantalla.
TEMPO_OFF = 0
TEMPO_MIN, TEMPO_MAX = 25.0, 300.0

# --- Signatura de tiempo ------------------------------------------------
#
# Byte 14 de la cabecera. El **numerador esta verificado**: es
# `(byte >> 3) + 1`, medido en tres puntos (20 -> 3/4, 28 -> 4/4, 44 -> 6/4).
#
# El **denominador NO**: escribiendo los bits bajos a 3, 4, 0 y 7 con el mismo
# numerador, el equipo siguio mostrando /4 en todos los casos. O no viven ahi, o
# el equipo los normaliza. El byte 59 del bloque 3 tambien cambia con la
# signatura y es el siguiente sitio donde mirar, pero ese byte ya sabemos que
# empaqueta varias cosas a la vez.
#
# Solo se puede fijar desde el panel en un patron VACIO (manual p. 58), que es
# por que hizo falta medirlo creando dos patrones nuevos y comparando.
TIME_SIG_OFF = 14


# La signatura entera cabe en el byte 14:
#
#     byte 14 = ((numerador - 1) << 3) | (16 // denominador)
#
# Verificado contra los 40 archivos de signaturas ocultas de doffu, sin un solo
# fallo: numeradores 17-32 en los tres denominadores. Entre `TS17-4`, `TS17-8` y
# `TS17-16` lo unico que cambia es este byte.
#
# Los 3 bits bajos no dan para el 8 que pediria un `/2`, asi que **el formato
# solo admite /4, /8 y /16** — que es justamente el catalogo que publica doffu.
#
# Una sonda anterior escribio 0, 3, 4 y 7 en esos bits y el panel mostro `/4`
# siempre, lo que se leyo como "el denominador no esta aqui". Pero los valores
# validos son 1, 2 y 4: tres de las cuatro sondas eran invalidas —y el equipo
# cae a `/4`— y la unica valida *era* `/4`. El panel decia la verdad todo el
# tiempo. **Tres bits son ocho valores; probar cuatro y no ver nada no prueba
# nada.**
DENOMINADORES = {4: 4, 8: 2, 16: 1}


def decode_time_signature(payload):
    """(numerador, denominador) del byte 14."""
    b = unpack(payload)[TIME_SIG_OFF]
    bajo = b & 0x07
    inverso = {v: k for k, v in DENOMINADORES.items()}
    if bajo not in inverso:
        raise ValueError("bits de denominador invalidos (%d); validos %s"
                         % (bajo, sorted(inverso)))
    return (b >> 3) + 1, inverso[bajo]


def set_time_signature(payload, numerador, denominador=None):
    """Fija la signatura. Sin `denominador`, conserva el que hubiera."""
    if not 1 <= numerador <= 32:
        raise ValueError("numerador fuera de rango 1-32: %d" % numerador)
    d = bytearray(unpack(payload))
    if denominador is None:
        bajo = d[TIME_SIG_OFF] & 0x07
    else:
        if denominador not in DENOMINADORES:
            raise ValueError("denominador %d: solo %s caben en 3 bits"
                             % (denominador, sorted(DENOMINADORES)))
        bajo = DENOMINADORES[denominador]
    d[TIME_SIG_OFF] = ((numerador - 1) << 3) | bajo
    return pack(bytes(d))


def set_time_signature_numerator(payload, numerador):
    """Compatibilidad: cambia solo el numerador."""
    return set_time_signature(payload, numerador)

# --- Registro de pistas existentes --------------------------------------
#
# La cabecera lleva una tabla de **8 ranuras por seccion**, 48 bytes en total,
# donde cada ranura ocupada guarda su `tr` (= seccion*8 + pista) y las vacias
# valen 0.
#
# **Sin esto el equipo no ve la seccion**, aunque los bloques de pista esten
# escritos y se relean perfectos. Paso justamente eso: se escribieron las seis
# secciones, el volcado las devolvia enteras, y el panel solo mostraba Intro y
# Main A —las dos unicas cuyas pistas estaban en esta tabla, porque las habia
# registrado el propio equipo al crearlas—.
#
# Se localizo leyendo la cabecera y viendo `00 01 02 ...` seguido de
# `08 09 0A 0B 0C 0D 0E 0F`: los tr de Intro y de Main A, en su sitio.
# Son **dos** tablas paralelas de 48 bytes (8 ranuras x 6 secciones), pegadas:
#
#   byte 21..68  banderas: F8 = la pista tiene contenido, FE = vacia
#   byte 69..116 los `tr` de las pistas presentes, 0 en las vacias
#
# Escribir solo la segunda no basta: el equipo siguio sin ver las secciones.
REGISTRY_FLAGS_OFF = 21
REGISTRY_OFF = 69
REGISTRY_SLOTS = TRACKS_PER_SECTION
FLAG_PRESENTE = 0xF8
FLAG_VACIA = 0xFE


def decode_registry(header_payloads):
    """{seccion: [pistas registradas]} segun la cabecera."""
    d = b"".join(unpack(p) for p in header_payloads)
    out = {}
    for sec in range(len(SECTIONS)):
        base = REGISTRY_OFF + sec * REGISTRY_SLOTS
        pistas = []
        for k in range(REGISTRY_SLOTS):
            v = d[base + k]
            if v == sec * TRACKS_PER_SECTION + k:
                pistas.append(k)
        out[sec] = pistas
    return out


def set_registry(header_payloads, por_seccion):
    """Reescribe el registro. `por_seccion` es {seccion: [pistas]}.

    **Solo pisa lo que es nuestro.** Una ranura cuyo nibble bajo no sea `8`
    (contenido propio) ni `E` (vacia) esta en un estado que no escribimos
    nosotros —hoy, una frase preset referenciada, cuyo nibble bajo lleva el beat—
    y se deja intacta junto con su byte de la segunda tabla.

    Sin esto, escribir una sola pista generativa borra en silencio todas las
    frases de fabrica que hubiera asignadas desde el panel: la version anterior
    ponia `F8`/`FE` y el `tr` en las 48 ranuras sin mirar lo que habia. La
    escritura "funciona", no da error, y las frases desaparecen.

    La regla es conservadora a proposito: **se preserva todo lo que no
    reconocemos**, no solo los valores de referencia medidos. Del beat solo
    tenemos dos de los tres nibbles, y no vamos a borrar datos por no haber
    medido el tercero.

    Devuelve los 5 bloques de la cabecera.
    """
    d = bytearray(b"".join(unpack(p) for p in header_payloads))
    for sec in range(len(SECTIONS)):
        pistas = set(por_seccion.get(sec, []))
        for k in range(REGISTRY_SLOTS):
            i_flag = REGISTRY_FLAGS_OFF + sec * REGISTRY_SLOTS + k
            i_tr = REGISTRY_OFF + sec * REGISTRY_SLOTS + k
            if k in pistas:
                d[i_flag] = FLAG_PRESENTE
                d[i_tr] = sec * TRACKS_PER_SECTION + k
            elif d[i_flag] in (FLAG_PRESENTE, FLAG_VACIA):
                d[i_flag] = FLAG_VACIA
                d[i_tr] = 0
            # else: estado ajeno (frase preset referenciada) -> no se toca
    return [pack(bytes(d[i:i + UNPACKED_BYTES]))
            for i in range(0, len(d), UNPACKED_BYTES)]


def decode_tempo(payload):
    """BPM del primer bloque de la cabecera."""
    d = unpack(payload)
    return ((d[TEMPO_OFF] << 8) | d[TEMPO_OFF + 1]) / 10.0


def set_tempo(payload, bpm):
    """Reescribe el tempo. VERIFICADO: escribir 104,0 se vio en el panel."""
    if not TEMPO_MIN <= bpm <= TEMPO_MAX:
        raise ValueError("tempo fuera de rango %.0f-%.0f: %r"
                         % (TEMPO_MIN, TEMPO_MAX, bpm))
    d = bytearray(unpack(payload))
    v = int(round(bpm * 10))
    d[TEMPO_OFF], d[TEMPO_OFF + 1] = (v >> 8) & 0xFF, v & 0xFF
    return pack(bytes(d))


# --- Mezclador: la voz DE PISTA -----------------------------------------
#
# A partir del byte 154 hay arrays de 8, uno por pista de patron. El primero es
# **la voz de pista**, que es la que realmente suena: manda sobre la voz de la
# frase (manual p. 57). Durante horas la dimos por inalcanzable creyendo que
# vivia fuera del patron; esta en la cabecera y por tanto se puede escribir.
#
# Confirmado con un ancla: el mezclador del equipo mostraba `Dr010 DarkRKit`
# solo en D1, y el byte 154 valia 9, que es el programa de Dark Room Kit. Las
# pistas sin voz propia no aparecen en el mezclador.
#
# **Los tres estan verificados** (2026-07-29): se escribieron valores distintos
# en cada pista —D2 a volumen 20 y panoramico a la izquierda, PC a 127 y a la
# derecha, BA con reverb al maximo— y el mezclador del equipo los mostro todos.
# Se pusieron deliberadamente distintos entre si para que ninguna coincidencia
# pudiera ser casualidad.
MIXER_PROG_OFF = 154        # programa de voz, base cero
MIXER_DRUM_OFF = 162        # 1 = la pista usa kit de bateria
MIXER_VOL_OFF = 170         # 0-127
MIXER_PAN_OFF = 178         # 0 izquierda, 64 centro, 127 derecha
MIXER_REVERB_OFF = 202      # 0-127


def decode_mixer(header_payloads):
    """Una lista de 8 dicts con el estado del mezclador, una por pista."""
    d = b"".join(unpack(p) for p in header_payloads)
    return [{"programa": d[MIXER_PROG_OFF + k],
             "bateria": bool(d[MIXER_DRUM_OFF + k]),
             "volumen": d[MIXER_VOL_OFF + k],
             "panoramico": d[MIXER_PAN_OFF + k],
             "reverb": d[MIXER_REVERB_OFF + k]}
            for k in range(TRACKS_PER_SECTION)]


def set_mixer(header_payloads, pista, volumen=None, panoramico=None, reverb=None):
    """Ajusta niveles de una pista. Panoramico: 0 izquierda, 64 centro, 127 derecha."""
    if not 0 <= pista < TRACKS_PER_SECTION:
        raise ValueError("pista fuera de rango 0-7: %d" % pista)
    d = bytearray(b"".join(unpack(p) for p in header_payloads))
    # La cabecera son 5 bloques. Si llegan menos, el volcado vino incompleto y
    # escribir aqui corromperia lo que si llego, o reventaria por indice.
    if len(d) < MIXER_REVERB_OFF + TRACKS_PER_SECTION:
        raise ValueError("cabecera incompleta: %d bytes de %d. Repite el volcado."
                         % (len(d), 5 * UNPACKED_BYTES))
    for valor, off, nombre in ((volumen, MIXER_VOL_OFF, "volumen"),
                               (panoramico, MIXER_PAN_OFF, "panoramico"),
                               (reverb, MIXER_REVERB_OFF, "reverb")):
        if valor is None:
            continue
        if not 0 <= valor <= 127:
            raise ValueError("%s fuera de rango 0-127: %d" % (nombre, valor))
        d[off + pista] = valor
    return [pack(bytes(d[i:i + UNPACKED_BYTES]))
            for i in range(0, len(d), UNPACKED_BYTES)]


def set_mixer_voice(header_payloads, pista, programa, bateria=False):
    """Fija la voz de pista. `programa` es base cero (el de pantalla menos uno).

    **VERIFICADO** (2026-07-29): se escribio Analog Kit en D1, que arrastraba un
    Dark Room Kit de pruebas viejas, y el mezclador del equipo mostro el cambio.
    """
    if not 0 <= pista < TRACKS_PER_SECTION:
        raise ValueError("pista fuera de rango 0-7: %d" % pista)
    if not 0 <= programa <= 0x7F:
        raise ValueError("programa fuera de rango 0-127: %d" % programa)
    d = bytearray(b"".join(unpack(p) for p in header_payloads))
    d[MIXER_PROG_OFF + pista] = programa
    d[MIXER_DRUM_OFF + pista] = 1 if bateria else 0
    return [pack(bytes(d[i:i + UNPACKED_BYTES]))
            for i in range(0, len(d), UNPACKED_BYTES)]


NAME_OFF = 6
NAME_LEN = 8
MEASURES_OFF = 15        # un byte por seccion, valor = compases - 1
UI_MAX_MEASURES = 8      # tope que impone la interfaz del equipo
MAX_MEASURES = 32        # alcanzado con archivos de estilo, verificado por doffu


def decode_header(payload):
    """Del primer bloque `12 nn 7F`: (nombre, compases por seccion).

    `compases` es una lista de 6, en el orden de SECTIONS.
    """
    d = unpack(payload)
    nombre = bytes(d[NAME_OFF:NAME_OFF + NAME_LEN]).decode("ascii", "replace").rstrip()
    compases = [d[MEASURES_OFF + k] + 1 for k in range(len(SECTIONS))]
    return nombre, compases


def encode_header(payload, name=None, measures=None):
    """Reescribe nombre y/o longitudes en el primer bloque `12 nn 7F`.

    `measures` es una lista de 6 (o un dict {indice_de_seccion: compases}).
    Devuelve los 147 bytes empaquetados, listos para `build_dump`.

    Poner mas de UI_MAX_MEASURES es justo el truco de desbloqueo: el equipo
    respeta el valor aunque su interfaz no deje introducirlo. Ojo con el aviso
    de doffu: **al reducir la longitud desde el panel ya no se puede volver a
    subir** sin recargar el archivo.

    **Sin verificar contra el equipo**: leer esta comprobado; escribir cabeceras
    todavia no se ha probado.
    """
    d = bytearray(unpack(payload))
    if name is not None:
        txt = name.encode("ascii", "replace")[:NAME_LEN]
        d[NAME_OFF:NAME_OFF + NAME_LEN] = txt + b" " * (NAME_LEN - len(txt))
    if measures is not None:
        items = measures.items() if isinstance(measures, dict) else enumerate(measures)
        for k, m in items:
            if not 0 <= k < len(SECTIONS):
                raise ValueError("seccion fuera de rango 0-5: %d" % k)
            if not 1 <= m <= MAX_MEASURES:
                raise ValueError("compases fuera de rango 1-%d: %d" % (MAX_MEASURES, m))
            d[MEASURES_OFF + k] = m - 1
    return pack(bytes(d))


# --- Tipo de frase (tabla de transicion de notas) -----------------------
#
# Descifrado el 2026-07-29 cambiando UNICAMENTE el parametro TYPE en el equipo y
# volcando entre cada cambio, cinco veces. En las cinco pruebas **no se movio
# ningun otro byte del patron**, asi que el campo esta bien aislado.
#
# Determina como se rearmoniza la pista contra la pista de acordes (manual
# p. 58). Con `Bypass` suena literalmente lo escrito, que es lo que interesa
# para comprobar material generado.
#
# Los cinco valores son medidos, no deducidos. La estructura de bits se
# entiende a medias: `Chord 1`, `Bass` y `Parallel` comparten el nibble alto 9 y
# se distinguen por los bits 1-2 (0, 1, 2), lo que encaja con que el manual
# describa Bass y Parallel como variantes de la rearmonizacion por raiz. Pero
# `Bypass` (03) y `Chord 2` (A0) no siguen ese esquema, asi que **se usa como
# tabla de consulta y no se calcula**: inventar la aritmetica seria adivinar.

PHRASE_TYPE_OFF = 20            # byte del prefijo de la pista

PHRASE_TYPES = {
    "Bypass":   0x03,
    "Chord 1":  0x90,
    "Bass":     0x92,
    "Parallel": 0x94,
    "Chord 2":  0xA0,
}
_PHRASE_BY_BYTE = {v: k for k, v in PHRASE_TYPES.items()}

# En la cabecera del patron hay ademas un bit por pista que se enciende solo con
# `Chord 1` y `Bass` — justo los dos tipos a los que el manual dice que aplica
# `HI KEY` (p. 121). Coincide en las cinco pruebas.
#
# **Sin verificar: la posicion se midio solo para la pista 0 de Main A.** No
# sabemos si el offset depende de la pista o si es uno por pista contiguo. Antes
# de escribirlo para otra pista hay que repetir la medicion.
HEADER_HIKEY_OFF = 3 * UNPACKED_BYTES + 75
HEADER_HIKEY_BIT = 0x08
HIKEY_TYPES = ("Chord 1", "Bass")


def decode_phrase_type(payload):
    """Tipo de frase del primer bloque de una pista. None si no lo conocemos."""
    return _PHRASE_BY_BYTE.get(unpack(payload)[PHRASE_TYPE_OFF])


def set_phrase_type(payload, tipo):
    """Devuelve los 147 bytes del bloque con el tipo de frase cambiado.

    Solo toca el byte del prefijo. El bit de la cabecera del patron va aparte
    (`set_header_hikey`), y hay que poner los dos de acuerdo o quedaran
    incoherentes.
    """
    if tipo not in PHRASE_TYPES:
        raise ValueError("tipo de frase desconocido: %r (conocidos: %s)"
                         % (tipo, ", ".join(sorted(PHRASE_TYPES))))
    d = bytearray(unpack(payload))
    d[PHRASE_TYPE_OFF] = PHRASE_TYPES[tipo]
    return pack(bytes(d))


def set_header_hikey(payloads, tipo):
    """Ajusta en la cabecera el bit que acompana a `Chord 1` y `Bass`.

    `payloads` son los 5 bloques de la cabecera (`tr=0x7F`); devuelve otros 5.
    """
    d = bytearray(b"".join(unpack(p) for p in payloads))
    if HEADER_HIKEY_OFF >= len(d):
        raise ValueError("la cabecera trae %d bytes, se esperaban %d"
                         % (len(d), HEADER_HIKEY_OFF + 1))
    if tipo in HIKEY_TYPES:
        d[HEADER_HIKEY_OFF] |= HEADER_HIKEY_BIT
    else:
        d[HEADER_HIKEY_OFF] &= ~HEADER_HIKEY_BIT & 0xFF
    return [pack(bytes(d[i:i + UNPACKED_BYTES]))
            for i in range(0, len(d), UNPACKED_BYTES)]


# --- Acorde fuente (SOURCE CHORD) ---------------------------------------
#
# El acorde sobre el que se considera escrita la frase. Es **por pista**, y por
# eso vive en el prefijo de 26 bytes y no en la cabecera. Solo influye si el
# TYPE rearmoniza: con `Bypass` se ignora.
#
# Medido cambiando unicamente ese parametro:
#
#     SOURCE CHORD    byte 16   byte 21   byte 22
#     CM7             00        00        00
#     Cm7             09        00        08
#     Fm7             09        05        08
#
# **byte 21 = raiz** en semitonos con Do=0 (Do->Fa dio +5) y **byte 22 = tipo**,
# con la misma tabla que el acorde actual. Los dos, confirmados.
#
# El byte 16 tambien se movio en aquella prueba (00 -> 09) y se anoto como
# "derivado del tipo de acorde". **Era falso**: el byte 16 es el numero de
# programa de PHRASE VOICE, y cambio porque al entrar por primera vez en la
# Phrase Table el equipo escribio alli la voz real de la pista (Dr010 = 9). No
# tenia relacion con el acorde. Ver PHRASE_VOICE_* mas abajo.
#
# Leccion: en un diff, un byte que cambia **a la vez** que lo que tocaste no es
# necesariamente consecuencia de lo que tocaste. Abrir una pantalla de edicion
# ya es una accion con efectos.
#
# Y en la cabecera, el byte 75 del bloque 3 tambien se mueve —con el tipo de
# frase, con la raiz y con la calidad—, o sea que empaqueta varias cosas. **No
# lo tocamos**, y por eso:

SRC_CHORD_ROOT_OFF = 21
SRC_CHORD_TYPE_OFF = 22

# Solo los tipos medidos. Los 26 del equipo se completan midiendo, no
# conjeturando: un volcado por tipo.
SRC_CHORD_TYPES = {
    "M7": 0x00,
    "m7": 0x08,
}


def decode_source_chord(payload):
    """(raiz, tipo) del acorde fuente de una pista. tipo None si no lo conocemos."""
    d = unpack(payload)
    tipo = next((k for k, v in SRC_CHORD_TYPES.items()
                 if v == d[SRC_CHORD_TYPE_OFF]), None)
    return CHORD_ROOTS[d[SRC_CHORD_ROOT_OFF] % 12], tipo


def set_source_chord(payload, raiz, tipo):
    """Reescribe el acorde fuente en el primer bloque de una pista.

    **SIN VERIFICAR CONTRA EL EQUIPO.** Leerlo si esta comprobado, pero al
    escribirlo queda un cabo suelto: el byte 75 del bloque 3 de la cabecera
    tambien se mueve cuando se cambia esto desde el panel, y no sabemos que
    parte de el corresponde al acorde fuente. Escribir solo la pista puede
    dejar el patron incoherente. Comprobar en el equipo antes de fiarse.
    """
    if raiz not in CHORD_ROOTS:
        raise ValueError("raiz desconocida: %r" % (raiz,))
    if tipo not in SRC_CHORD_TYPES:
        raise ValueError("tipo de acorde fuente no medido: %r. Medidos: %s"
                         % (tipo, ", ".join(sorted(SRC_CHORD_TYPES))))
    d = bytearray(unpack(payload))
    d[SRC_CHORD_ROOT_OFF] = CHORD_ROOTS.index(raiz)
    d[SRC_CHORD_TYPE_OFF] = SRC_CHORD_TYPES[tipo]
    return pack(bytes(d))


# --- Voz de la frase (PHRASE VOICE) -------------------------------------
#
# Medido cambiando solo ese parametro: `Dr010 DarkKit` -> `Ld081 SquareLd`.
#
#     PHRASE VOICE      byte 14   byte 16
#     Dr010 DarkKit     7F        09
#     Ld081 SquareLd    00        50
#
# **byte 14 = banco**: 127 es el banco de bateria de XG, 0 el de voces normales.
# **byte 16 = numero de programa, base cero**: Dr010 -> 9 y Ld081 -> 80, los dos
# el numero que muestra la pantalla menos uno. Dos puntos independientes.
#
# El byte 15 vale 00 en todo lo que hemos visto y seria el sitio natural del
# banco LSB de XG, pero **no se ha medido** y no se toca.
#
# Ojo: esta es la voz guardada EN LA FRASE. La que suena es la de la pista, que
# se ajusta en el modo PATTERN VOICE y manda sobre esta (manual p. 57). Por eso
# una pista puede sonar melodica con un kit de bateria escrito aqui.

PHRASE_VOICE_BANK_OFF = 14
PHRASE_VOICE_PROG_OFF = 16
BANK_NORMAL = 0x00      # voces normales
BANK_DRUMS = 0x7F       # kits de bateria (127)
BANK_SFX = 0x7E         # kits de efectos (126), solo SFX Kit 1 y 2
BANCOS = (BANK_NORMAL, BANK_DRUMS, BANK_SFX)


def decode_phrase_voice(payload):
    """(banco, programa_base_cero) de la voz guardada en la frase."""
    d = unpack(payload)
    return d[PHRASE_VOICE_BANK_OFF], d[PHRASE_VOICE_PROG_OFF]


def set_phrase_voice(payload, programa, banco=BANK_NORMAL):
    """Fija la voz de la frase. `programa` es base cero: el numero de la
    pantalla menos uno (Ld081 -> 80).

    **VERIFICADO contra el equipo** (2026-07-29): se escribio el programa 0 en
    una pista que tenia el 80 y el arpegio paso a sonar a piano, con la Phrase
    Table mostrando la voz nueva.
    """
    if not 0 <= programa <= 0x7F:
        raise ValueError("programa fuera de rango 0-127: %d" % programa)
    if banco not in BANCOS:
        raise ValueError("banco desconocido: %02X (validos: 00, 7E, 7F)" % banco)
    d = bytearray(unpack(payload))
    d[PHRASE_VOICE_BANK_OFF] = banco
    d[PHRASE_VOICE_PROG_OFF] = programa
    return pack(bytes(d))


# --- Acorde actual (CURRENT CHORD) --------------------------------------
#
# El acorde con el que se esta reproduciendo el patron. **No es SOURCE CHORD**:
# lo etiquetamos mal al principio y hay que tenerlo claro, porque los dos
# aparecen juntos en la pantalla Phrase Table y es facil cambiar uno creyendo
# tocar el otro.
#
# Lo que lo zanjo: tras escribir aqui `Cm7`, la pantalla PRINCIPAL del equipo
# mostraba `Cm7` mientras la Phrase Table seguia mostrando `SOURCE CHORD = CM7`.
# Los bytes siguen a la principal. Encaja ademas con que sea comun a todo el
# patron —vive en la cabecera— mientras que SOURCE CHORD es por frase.
#
# El manual (p. 121): "CURRENT CHORD: Muestra el acorde seleccionado en ese
# momento para el modo de reproduccion de patron."
#
# Medido tres veces cambiando solo ese parametro, sin que se moviera ningun
# otro byte.
#
# **SOURCE CHORD sigue sin localizar.**

# **Es POR SECCION**, no del patron entero. Se etiqueto primero como SOURCE
# CHORD (falso) y luego como CURRENT CHORD del patron (incompleto): son dos
# arrays de 6, indexados por seccion. El byte 118 medido resulto ser el de
# Main A, que es la seccion 1, de ahi las bases 117 y 123.
#
# Lo delato que tras poner Cm7 "en el patron" el panel seguia mostrando CM7 en
# Main B, y su melodia sonaba mayor: acorde fuente Cm7 y actual CM7 hacen que
# Chord 1 la transporte de menor a mayor.
CUR_CHORD_ROOT_BASE = 117       # + numero de seccion
CUR_CHORD_TYPE_BASE = 123

CHORD_ROOTS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# El QY100 tiene 26 tipos de acorde (specs, p. 141). Aqui solo estan los
# **medidos**; el resto se anaden repitiendo la medicion, que cuesta un volcado
# por tipo. No se rellenan por conjetura.
# Medidos escribiendo un valor distinto en cada seccion y leyendo el panel.
# Los nombres son los que muestra el equipo. Faltan 17 de los 26.
# **Los 27 medidos**, escribiendo un valor distinto en cada seccion y leyendo el
# panel: cinco rondas de seis. Los nombres son los que muestra el equipo.
#
# El orden NO agrupa por familia —el 3 es m7(11), una menor, entre 6 y M7(9)—,
# asi que ninguno se dedujo: todos estan medidos.
#
# Del 28 en adelante el equipo muestra basura (`Con`, `C ^`, `C(9)mn`): esta
# leyendo mas alla de su tabla de nombres. No recorta ni protesta, asi que la
# validacion de rango la tiene que poner este codigo. El 27 muestra `C---` y
# probablemente sea el "sin ABC" de las specs; sin confirmar, no se incluye.
CHORD_TYPE_MAX = 26
CHORD_TYPES = {
    "M7":      0,
    "M":       1,
    "6":       2,
    "m7(11)":  3,
    "M7(9)":   4,
    "add9":    5,
    "m":       6,
    "m6":      7,
    "m7":      8,
    "m7(b5)":  9,
    "mM7":    10,
    "m7(9)":  11,
    "madd9":  12,
    "7":      13,
    "7(#5)":  14,
    "7(b9)":  15,
    "7(9)":   16,
    "7(#9)":  17,
    "7(#11)": 18,
    "7(b13)": 19,
    "7(13)":  20,
    "7sus4":  21,
    "sus4":   22,
    "dim":    23,
    "aug":    24,
    "6(9)":   25,
    "7(b5)":  26,
}
_CHORD_BY_BYTE = {v: k for k, v in CHORD_TYPES.items()}


def decode_current_chord(header_payloads, seccion=1):
    """(raiz, tipo, byte) del acorde actual de una seccion. Main A por defecto."""
    d = b"".join(unpack(p) for p in header_payloads)
    tb = d[CUR_CHORD_TYPE_BASE + seccion]
    return (CHORD_ROOTS[d[CUR_CHORD_ROOT_BASE + seccion] % 12],
            _CHORD_BY_BYTE.get(tb), tb)


def decode_current_chords(header_payloads):
    """{seccion: (raiz, tipo)} de las seis."""
    return {s: decode_current_chord(header_payloads, s)[:2]
            for s in range(len(SECTIONS))}


def set_current_chord(header_payloads, raiz, tipo, secciones=None):
    """Reescribe el acorde actual. Por defecto en las SEIS secciones.

    `secciones` limita a una lista concreta.
    """
    if raiz not in CHORD_ROOTS:
        raise ValueError("raiz desconocida: %r (%s)" % (raiz, ", ".join(CHORD_ROOTS)))
    if tipo not in CHORD_TYPES:
        raise ValueError("tipo de acorde no medido: %r. Medidos: %s. "
                         "Para anadir otro, cambialo en el equipo y compara volcados."
                         % (tipo, ", ".join(sorted(CHORD_TYPES))))
    d = bytearray(b"".join(unpack(p) for p in header_payloads))
    for s in (range(len(SECTIONS)) if secciones is None else secciones):
        d[CUR_CHORD_ROOT_BASE + s] = CHORD_ROOTS.index(raiz)
        d[CUR_CHORD_TYPE_BASE + s] = CHORD_TYPES[tipo]
    return [pack(bytes(d[i:i + UNPACKED_BYTES]))
            for i in range(0, len(d), UNPACKED_BYTES)]


# --- Construir el prefijo de una pista que aun no existe -----------------
#
# `generar` obligaba a que la pista existiera ya en el equipo, porque habia que
# copiarle estos 26 bytes. Con los campos que hemos descifrado se puede fabricar
# a partir de una plantilla real.
#
# La plantilla NO esta inventada: son los 26 bytes que volco el propio QY100
# para Main A pista 0 (`dumps/79-final.syx`). Los bytes que no entendemos se
# quedan con el valor que les puso el equipo, que es lo unico razonable.

PREFIJO_BASE = bytes(
    [0x20] * 12 +               # 0-11  nombre, espacios
    [0x02,                      # 12    compases - 1
     0x1C,                      # 13    ?  (1C en todo lo visto)
     0x7F,                      # 14    banco de la voz
     0x00,                      # 15    ?  (banco LSB, sin medir)
     0x00,                      # 16    programa de la voz
     0x7F,                      # 17    ?
     0x00,                      # 18    ?
     0x07,                      # 19    ?
     0x03,                      # 20    TYPE
     0x00,                      # 21    raiz del acorde fuente
     0x00,                      # 22    tipo del acorde fuente
     0x00,                      # 23    ?
     0x03,                      # 24    ?
     0xB5])                     # 25    ?

NAME_TRACK_LEN = 12

# Las 8 pistas del modo patron, en orden (manual p. 56).
TRACK_NAMES = ["D1", "D2", "PC", "BA", "C1", "C2", "C3", "C4"]

# Byte 19 del prefijo: sin descifrar, pero **depende del rol de la pista** y hay
# que ponerlo bien. Copiar el prefijo de una pista de bateria a una de percusion
# arrastraba un 07 donde iba un 03, y el equipo listaba la pista como vacia
# aunque los datos estuvieran y sonaran.
#
# Las ocho medidas, todas sobre pistas creadas por el propio equipo salvo PC,
# cuyo 3 sale de los volcados antiguos y de que ponerlo hizo aparecer la nuestra.
# La agrupacion es rara —percusion y bajo por un lado, todo lo demas por otro—
# pero es lo medido.
# Medido en el equipo para las ocho pistas (2026-08-02). Solo PC y BA valen 3;
# las demas valen 7. La tanda de C1-C4 llevaba BA como control, y devolvio el 3
# que ya teniamos — asi que la medicion es fiable y no una coincidencia.
TRACK_BYTE19 = {0: 7, 1: 7, 2: 3, 3: 3, 4: 7, 5: 7, 6: 7, 7: 7}

# Valores estandar de cada pista segun el manual (p. 58), confirmados al ver que
# el equipo creaba BA con Ba033 y tipo Bass, y C1-C4 con Pf001 y Chord 1.
# (tipo, programa base cero, banco)
TRACK_DEFAULTS = {
    0: ("Bypass",  0, 0x7F),      # D1  Dr001 Standard Kit
    1: ("Bypass",  0, 0x7F),      # D2  Dr001
    2: ("Bypass",  0, 0x7F),      # PC  Dr001
    3: ("Bass",   32, 0x00),      # BA  Ba033 Acoustic Bass
    4: ("Chord 1", 0, 0x00),      # C1  Pf001 Grand Piano
    5: ("Chord 1", 0, 0x00),      # C2
    6: ("Chord 1", 0, 0x00),      # C3
    7: ("Chord 1", 0, 0x00),      # C4
}
UNKNOWN_BYTE19_OFF = 19


def parse_chord(texto):
    """'Cm7' -> ('C', 'm7'). Acepta raices con sostenido: 'F#m7'."""
    for r in sorted(CHORD_ROOTS, key=len, reverse=True):
        if texto.startswith(r):
            return r, texto[len(r):]
    raise ValueError("no entiendo el acorde %r" % (texto,))


def build_prefix(base=None, nombre=None, compases=None, voz=None,
                 banco=None, tipo=None, fuente=None, pista=None):
    """Arma los 26 bytes de cabecera de una pista.

    `base` son los 26 bytes de otra pista real; si no se pasa, se usa
    `PREFIJO_BASE`. Preferir siempre una pista del mismo patron: los bytes que
    no sabemos leer vendran del equipo y no de nuestra plantilla.

    `voz` es el numero de programa en base cero (el de pantalla menos uno).
    `fuente` es ('C', 'm7') o la cadena 'Cm7'.
    """
    d = bytearray((base or PREFIJO_BASE)[:EVENT_STREAM_START])
    d += bytes(EVENT_STREAM_START - len(d))

    if pista is not None and pista in TRACK_BYTE19:
        d[UNKNOWN_BYTE19_OFF] = TRACK_BYTE19[pista]
    if nombre is not None:
        txt = nombre.encode("ascii", "replace")[:NAME_TRACK_LEN]
        d[0:NAME_TRACK_LEN] = txt + b" " * (NAME_TRACK_LEN - len(txt))
    if compases is not None:
        if not 1 <= compases <= MAX_MEASURES:
            raise ValueError("compases fuera de rango 1-%d: %d" % (MAX_MEASURES, compases))
        d[12] = compases - 1
    if banco is not None:
        if banco not in BANCOS:
            raise ValueError("banco desconocido: %02X" % banco)
        d[PHRASE_VOICE_BANK_OFF] = banco
    if voz is not None:
        if not 0 <= voz <= 0x7F:
            raise ValueError("programa fuera de rango 0-127: %d" % voz)
        d[PHRASE_VOICE_PROG_OFF] = voz
    if tipo is not None:
        if tipo not in PHRASE_TYPES:
            raise ValueError("tipo de frase desconocido: %r" % (tipo,))
        d[PHRASE_TYPE_OFF] = PHRASE_TYPES[tipo]
    if fuente is not None:
        raiz, cal = parse_chord(fuente) if isinstance(fuente, str) else fuente
        if raiz not in CHORD_ROOTS:
            raise ValueError("raiz desconocida: %r" % (raiz,))
        if cal not in SRC_CHORD_TYPES:
            raise ValueError("tipo de acorde fuente no medido: %r. Medidos: %s"
                             % (cal, ", ".join(sorted(SRC_CHORD_TYPES))))
        d[SRC_CHORD_ROOT_OFF] = CHORD_ROOTS.index(raiz)
        d[SRC_CHORD_TYPE_OFF] = SRC_CHORD_TYPES[cal]
    return bytes(d)


def section_clocks(measures, beats_per_bar=4):
    """Relojes que dura una seccion de `measures` compases."""
    return measures * beats_per_bar * CLOCKS_PER_QUARTER



# Los 5 bloques de cabecera de un patron VACIO, capturados del equipo con el
# registro puesto a cero. Existen porque **un patron vacio no devuelve nada**:
# ni una pista, ni la cabecera. Sin esto, cualquier herramienta que quiera crear
# un patron desde cero no tiene de donde leer, y hay que ir al panel a grabar
# una nota antes de poder escribir nada — cosa que bloqueo al generador de
# estilos dos veces antes de resolverlo asi.
#
# Como `PREFIJO_BASE`, es una captura literal y no una plantilla inventada: los
# bytes que todavia no sabemos leer vienen del QY100. Lo unico puesto a mano es
# el registro, que si sabemos escribir.
CABECERA_BASE = [bytes.fromhex(h) for h in (
    # bloque 0
    "022c00000000002010080402010040200e002010080000017f3f5f6f777b7d7e7f3f"
    "5f6f777b7d7e7f3f5f6f777b7d7e7f3f5f6f777b7d7e7f3f5f6f777b7d7e7f3f5f6f"
    "777b7d7e7f3f5f6f777b7c0000000000000000000000000000000000000000000000"
    "00000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000",
    # bloque 1
    "000301406030180c000000077b7d7e00000000000000000000000000000000000008"
    "000000000001004020000000000032190c4623114864321008040201004020100f77"
    "7b7d7e7f3f5f6f70000000000000000001205028140a050241200000000000000000"
    "00402010080402010040201008040201004020100804020100402010080402010040"
    "2010080402010040201000",
    # bloque 2
    "20100824120904422110482778010040201008040201004020100804020100402a5a"
    "2f776b7d7e553f5e4f762b3960532c174804020100402010080402011a4d26484562"
    "737d7e203f4804077b7d7e7f100804077b7d7e7f3f5f6f777b7d7e7f3f5f6f777b7d"
    "7e7f3f50080402010040201008040201004020100804020100402010080402010040"
    "2010080402010040201000",
    # bloque 3
    "20100804020100402010080402000a0006412068184e101344000920000000000000"
    "00000000006432190c462311486432190c4623114864320000000000000000001f6f"
    "777b7d7e7f3f5f6f777b7d7e7f3f5f6f777b7d7e7f3f5f6f777b7d7e7f3f5f6f777b"
    "7d7e7f3f5f6f777b7d7e7f3f5f6f777b7d7e7f3f5f6f777b7d7e7f3f5f6f777b7d7e"
    "7f3f5f6f777b7d7e7f3f40",
    # bloque 4
    "7f3f5f6f777b7d7e7f3f5f6f777b7d7e7f3f5f6f777b7d7e7f3f5f6f777800000000"
    "0000000000001e7f5f6f777b7d7e0025200a7802757e7f3f5f6f777b7d7e7f3f5f6f"
    "777b7d7e7f3f5f6f777b7d7e7f3f5f6f700676006c7f5f6f777b7d7e004940134005"
    "0f7e7f3f5f6f777b7d7e7f3f5f6f777b7d7e7f3f5f6f777b7d7e7f3f5f6f70070200"
    "103f5f6f77780156005600",
)]



# --- Referencia a frase, en el registro de la cabecera -------------------
#
# La bandera del registro **no se parte en dos nibbles**, aunque lo pareciera
# durante toda una tarde de mediciones: son **5 bits de categoria y 3 de
# estado**.
#
#     bandera = (indice_de_categoria << 3) | estado
#
#     estado 0        la pista tiene contenido propio
#     estado 1        frase preset, 16 beat
#     estado 2        frase preset, 8 beat
#     estado 3        frase preset, 3/4 beat
#     estado 6        vacia
#
# Y el numero de frase menos uno va en la **segunda tabla** del registro (bytes
# 69-116), la misma que guarda el `tr` cuando la pista tiene contenido propio.
# Esta sobrecargada segun el estado.
#
# Asi `F8` y `FE` encajan sin ser casos especiales: son la categoria `US` (31)
# con estado 0 y 6 — una frase de **usuario** con contenido o vacia.
#
# La tabla sale del **firmware**, offset 0x11AE24 de la imagen que produce
# `extraer_rom.py`, y los `__` son huecos reservados por Yamaha. Cuadra con las
# ocho banderas medidas en el equipo, 8 de 8.
#
# **Por que costo tanto**: se asumio una particion 4+4 y se barrio el nibble
# alto. Con el bajo fijo en 9, el indice resultante es `(k<<1)|1` — **solo los
# impares**, la mitad de la tabla. Las ocho categorias que "no existian" estaban
# todas en indices pares. El barrido no podia alcanzarlas y el resultado se leyo
# como que el formato no llegaba. Misma trampa que la del denominador de compas:
# **un barrido que no cubre el rango entero no prueba una ausencia.**
CATEGORIAS_FRASE = ['--', 'Da', 'Db', '__', '__', 'Fa', 'Fb', '__', '__', 'PC', '__', '__', '__', 'Ba', 'Bb', '__', '__', '__', 'Ga', 'Gb', 'GR', '__', '__', 'KC', 'KR', '__', '__', '__', 'PD', 'BR', 'SE', 'US']

FRASE_ESTADO_PROPIO = 0
FRASE_ESTADO_16BEAT = 1
FRASE_ESTADO_8BEAT = 2
FRASE_ESTADO_34BEAT = 3
FRASE_ESTADO_VACIA = 6

BEATS_FRASE = {"16 beat": FRASE_ESTADO_16BEAT,
               "8 beat": FRASE_ESTADO_8BEAT,
               "3/4 beat": FRASE_ESTADO_34BEAT}


def indice_categoria(codigo):
    """`Da` -> 1. Levanta ValueError si el codigo no existe."""
    for k, c in enumerate(CATEGORIAS_FRASE):
        if c == codigo:
            return k
    raise ValueError("categoria desconocida: %r. Validas: %s"
                     % (codigo, " ".join(sorted(c for c in CATEGORIAS_FRASE
                                                 if c not in ("__", "--")))))


def bandera_frase(categoria, beat):
    """Bandera de registro para referenciar una frase preset."""
    if beat not in BEATS_FRASE:
        raise ValueError("beat desconocido: %r. Validos: %s"
                         % (beat, ", ".join(sorted(BEATS_FRASE))))
    return (indice_categoria(categoria) << 3) | BEATS_FRASE[beat]


def leer_bandera(b):
    """Devuelve (categoria, estado). `estado` es el nombre del beat si aplica."""
    cat = CATEGORIAS_FRASE[b >> 3]
    estado = b & 0x7
    nombre = {v: k for k, v in BEATS_FRASE.items()}.get(estado)
    if nombre is None:
        nombre = {FRASE_ESTADO_PROPIO: "propio",
                  FRASE_ESTADO_VACIA: "vacia"}.get(estado, "?%d" % estado)
    return cat, nombre
