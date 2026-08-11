#!/usr/bin/env python3
"""Pruebas del protocolo. No necesitan el QY100 conectado.

Valida el armado y parseo de mensajes contra lo que dice el service manual
(seccion 3-6-3 y Tabla 1-9), y el flujo de diff sobre volcados sinteticos.

    .venv/bin/python test_protocol.py
"""

import io
import sys

from qy100syx import protocol as P
from qy100syx import report

FAILS = []
CHECKS = [0]


def check(label, got, want):
    CHECKS[0] += 1
    if got == want:
        print("  ok   %s" % label)
    else:
        print("  FALLA %s\n        obtenido: %r\n        esperado: %r" % (label, got, want))
        FAILS.append(label)


print("direcciones (Tabla 1-9, P=1)")
check("bulk mode", P.Addr.BULK_MODE, (0x10, 0x00, 0x00))
check("cancion 1", P.Addr.song(0), (0x11, 0x00, 0x00))
check("cancion 20", P.Addr.song(19), (0x11, 0x13, 0x00))
check("todas las canciones", P.Addr.SONG_ALL, (0x11, 0x7F, 0x00))
check("patron 1", P.Addr.pattern(0), (0x12, 0x00, 0x00))
check("patron 64", P.Addr.pattern(63), (0x12, 0x3F, 0x00))
check("todos los patrones", P.Addr.PATTERN_ALL, (0x12, 0x7F, 0x00))
check("setup", P.Addr.SETUP, (0x13, 0x00, 0x00))
check("info patrones 1-32", P.Addr.INFO_PATTERN_1_32, (0x15, 0x01, 0x00))

for bad, fn in ((20, P.Addr.song), (64, P.Addr.pattern), (-1, P.Addr.pattern)):
    try:
        fn(bad)
        check("rechaza indice %d" % bad, "no fallo", "ValueError")
    except ValueError:
        check("rechaza indice %d" % bad, "ValueError", "ValueError")

print("\nnombres legibles")
check("patron", P.addr_name(P.Addr.pattern(4)), "patron de usuario 5 pista 0")
check("cancion", P.addr_name(P.Addr.song(0)), "cancion 1 pista 0")
check("todos", P.addr_name(P.Addr.PATTERN_ALL), "todos los patrones")
check("comando", P.addr_name(P.Addr.CLEAR_PATTERN), "CLEAR PATTERN")

print("\nmensajes construidos (bytes exactos del manual)")
check("dump request patron 1",
      P.dump_request(P.Addr.pattern(0)).hex(" "),
      "f0 43 20 5f 12 00 00 f7")
check("dump request todos los patrones",
      P.dump_request(P.Addr.PATTERN_ALL).hex(" "),
      "f0 43 20 5f 12 7f 00 f7")
check("bulk mode on", P.bulk_mode(True).hex(" "), "f0 43 10 5f 10 00 00 01 f7")
check("bulk mode off", P.bulk_mode(False).hex(" "), "f0 43 10 5f 10 00 00 00 f7")
check("param request", P.param_request(P.Addr.BULK_MODE).hex(" "),
      "f0 43 30 5f 10 00 00 f7")

print("\nchecksum")
# El ejemplo del manual fija ByteCount = 01 13 = 147 para SONG/PATTERN DATA.
data = list(range(147))
msg = P.build_dump(P.Addr.pattern(0), data)
check("ByteCount de 147 se codifica 01 13", msg[4:6].hex(" "), "01 13")
check("longitud total", len(msg), 1 + 3 + 2 + 3 + 147 + 1 + 1)
m = P.Message(msg)
check("round-trip: direccion", m.addr, P.Addr.pattern(0))
check("round-trip: byte count", m.byte_count, 147)
check("round-trip: datos", m.data, data)
check("round-trip: checksum valido", m.verify("bytecount+addr+data"), True)
check("checksum cabe en 7 bits", 0 <= m.stored_checksum <= 0x7F, True)
check("longitud coherente con ByteCount", m.length_ok, True)

corrupt = bytearray(msg)
corrupt[20] ^= 0x01
check("detecta dato corrupto", P.Message(bytes(corrupt)).verify("bytecount+addr+data"), False)

print("\ndeteccion de la convencion de checksum")
for span in ("bytecount+addr+data", "addr+data", "data"):
    blob = b"".join(P.build_dump(P.Addr.pattern(i), [i] * 147, span=span)
                    for i in range(4))
    msgs, _ = P.parse_all(blob)
    best, scores = P.detect_checksum_span(msgs)
    check("identifica %r" % span, (best, scores[span]), (span, (4, 4)))

print("\nparseo de flujos")
blob = (P.dump_request(P.Addr.PATTERN_ALL)
        + P.build_dump(P.Addr.pattern(0), [1] * 147)
        + P.build_dump(P.Addr.pattern(1), [2] * 147)
        + P.bulk_mode(True))
msgs, errs = P.parse_all(blob)
check("cuenta mensajes", len(msgs), 4)
check("sin errores", errs, [])
check("tipos", [m.kind for m in msgs],
      ["dump-request", "dump", "dump", "param"])

ruido = b"\x90\x40\x64" + blob + b"\xf8\xfe"
msgs2, _ = P.parse_all(ruido)
check("ignora bytes que no son SysEx", len(msgs2), 4)

trunc = blob[:len(blob) - 40]
msgs3, _ = P.parse_all(trunc)
check("no explota con un flujo cortado", len(msgs3) >= 2, True)

print("\ndesempaquetado de 7 bits")
packed = bytes([0b0000011] + [0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07])
check("7-en-8 aplica los MSB", list(P.unpack_7in8(packed)),
      [0x81, 0x82, 0x03, 0x04, 0x05, 0x06, 0x07])
check("7-en-8: 8 bytes -> 7", len(P.unpack_7in8(bytes(16))), 14)
check("nibbles: 2 bytes -> 1", list(P.unpack_nibbles(bytes([0x0A, 0x0B]))), [0xAB])

print("\ninforme de diff")
a = P.build_dump(P.Addr.pattern(0), [0] * 147)
b = P.build_dump(P.Addr.pattern(0), [0] * 40 + [0x3C] + [0] * 106)
buf = io.StringIO()
n = report.diff(a, b, "antes", "despues", 4, lambda *x: buf.write(" ".join(map(str, x)) + "\n"))
out = buf.getvalue()
check("cuenta un byte cambiado", n, 1)
check("localiza el offset", "offset 40" in out, True)
check("marca el byte nuevo", "[3C]" in out, True)
check("nombra el patron", "patron de usuario 1" in out, True)

buf2 = io.StringIO()
n2 = report.diff(a, a, "x", "y", 4, lambda *x: buf2.write(" ".join(map(str, x)) + "\n"))
check("iguales dan cero cambios", n2, 0)
check("lo dice explicitamente", "Identicos" in buf2.getvalue(), True)

print("\nseguridad")
check("los comandos de borrado estan marcados",
      P.Addr.CLEAR_PATTERN in P.DESTRUCTIVE and P.Addr.CLEAR_SONG in P.DESTRUCTIVE, True)
check("un volcado normal no lo esta", P.Addr.pattern(0) in P.DESTRUCTIVE, False)
try:
    P.param_change(P.Addr.BULK_MODE, 200)
    check("rechaza valores de mas de 7 bits", "no fallo", "ValueError")
except ValueError:
    check("rechaza valores de mas de 7 bits", "ValueError", "ValueError")

# --- verificado contra las plantillas del Data Filer oficial de Yamaha ---
# Extraidas de QY100.exe (offset 214600). El `ff` de las plantillas es un
# marcador que el programa sustituye por el numero de elemento.
print("\nplantillas del Data Filer de Yamaha")
check("bulk mode ON",  P.bulk_mode(True).hex(" "),  "f0 43 10 5f 10 00 00 01 f7")
check("bulk mode OFF", P.bulk_mode(False).hex(" "), "f0 43 10 5f 10 00 00 00 f7")
check("param request", P.param_request(P.Addr.BULK_MODE).hex(" "), "f0 43 30 5f 10 00 00 f7")
check("pedir todo",    P.dump_request(P.Addr.ALL).hex(" "), "f0 43 20 5f 14 00 00 f7")
check("pedir cancion 1",  P.dump_request(P.Addr.song(0)).hex(" "),    "f0 43 20 5f 11 00 00 f7")
check("pedir patron 1",   P.dump_request(P.Addr.pattern(0)).hex(" "), "f0 43 20 5f 12 00 00 f7")
check("pedir setup",      P.dump_request(P.Addr.SETUP).hex(" "),      "f0 43 20 5f 13 00 00 f7")
check("CLEAR SONG todas",   P.clear_song().hex(" "),    "f0 43 10 5f 18 00 00 7f f7")
check("CLEAR SONG la 3",    P.clear_song(2).hex(" "),   "f0 43 10 5f 18 00 00 02 f7")
check("CLEAR PATTERN todos", P.clear_pattern().hex(" "), "f0 43 10 5f 18 01 00 7f f7")
check("CLEAR PATTERN el 5",  P.clear_pattern(4).hex(" "), "f0 43 10 5f 18 01 00 04 f7")
check("CLEAR ALL",           P.clear_all().hex(" "),      "f0 43 10 5f 18 02 00 00 f7")
for mal, fn in ((20, P.clear_song), (64, P.clear_pattern)):
    try:
        fn(mal); check("clear rechaza %d" % mal, "no fallo", "ValueError")
    except ValueError:
        check("clear rechaza %d" % mal, "ValueError", "ValueError")
# ByteCounts que declaran las plantillas de volcado
check("ByteCount cancion/patron = 147", (1<<7)|0x13, 147)
check("ByteCount setup = 37",           (0<<7)|0x25, 37)
check("ByteCount info canciones = 320", (2<<7)|0x40, 320)
check("ByteCount info patrones = 512",  (4<<7)|0x00, 512)

# --- formato de patron: gramatica del Data Filer, verificada contra el equipo ---
import os
from qy100syx import patternfmt as F

def _blk(f, addr):
    ms, _ = P.parse_all(open(f, "rb").read())
    g = [m for m in ms if m.addr == addr]
    return bytes(g[0].data) if g else None

print("\nempaquetado 7 <-> 8 bits")
check("147 bytes de 7 bits dan 128 de 8", len(F.unpack(bytes(147))), 128)
check("pack es la inversa de unpack",
      F.unpack(F.pack(bytes(range(128)))), bytes(range(128)))
check("pack rellena a 147 bytes", len(F.pack(bytes(10))), 147)
check("todo lo empaquetado cabe en 7 bits",
      all(b < 0x80 for b in F.pack(bytes(range(128)))), True)

# --- El decodificador, evento a evento -----------------------------------
#
# Existe porque la suite pasaba de 117 comprobaciones **con el decodificador de
# antes y con el de despues**, palabra por palabra igual. Tres cambios seguidos
# —fallar en voz alta, consumir `FB` entero, exigir el marcador— y ninguno tenia
# una sola prueba que los distinguiera. Cada bloque de aqui esta escrito para
# fallar con la version anterior al cambio que comprueba; los que no pueden
# fallar asi lo dicen.
#
# Los flujos se arman a mano en vez de sacarlos de un volcado: un volcado prueba
# que hoy funciona con los datos que hay, y una regresion en `FB` no aparece
# hasta que alguien vuelve a grabar con pedal.

print("\ngramatica de eventos, flujos armados a mano")

# Los bytes se escriben con la aritmetica a la vista en vez de llamar al
# codificador: si los generase `encode_track`, esto comprobaria que el
# codificador y el decodificador se entienden entre si, que es cierto aunque
# los dos estuvieran equivocados. Aqui el numero de la izquierda es el dato y el
# de la derecha su reparto en bits, y se puede comprobar a mano.
# Van literales, sin nombrar las constantes del modulo, para que estas pruebas
# se puedan correr contra una version que no las tenga —que es justo contra la
# que hay que correrlas para saber si prueban algo—. Lo que si se comprueba es
# que las constantes del modulo valgan lo que dicen los literales.
GATE, ALTURA, VEL = 432, 60, 112
MARCADOR = b"\xf0\x00"
RELLENO, POR_BLOQUE = 0x40, 128
DELTA4 = bytes([0x80 | 4])                                    # +4 relojes
NOTA   = bytes([0xD0 | (GATE >> 7), GATE & 0x7F, ALTURA, VEL])
PEDAL  = bytes([0xFB, 64, 127])                   # pedal de sostenido pisado
FIN    = bytes([0xF2])
check("la nota de mano lleva el gate que dice", (GATE >> 7, GATE & 0x7F), (3, 48))
check("y el modulo llama a esos bytes por su nombre",
      (F.TRACK_MARKER, F.CONTROL_CHANGE, F.END_OF_TRACK, F.PAD_BYTE,
       F.UNPACKED_BYTES),
      (MARCADOR, 0xFB, 0xF2, RELLENO, POR_BLOQUE))

def leer(flujo, **kw):
    return F.decode_events(MARCADOR + flujo, start=0, **kw)

# `FB cc vv` son tres bytes. Con `i += 1` el `64` cae como estado y revienta.
notas, dur = leer(PEDAL + DELTA4 + NOTA + FIN)
check("FB no se come la nota que le sigue",
      [(n.pitch, n.velocity, n.gate, n.time) for n in notas],
      [(ALTURA, VEL, GATE, 4)])

# Y el invariante que importa: meter un control change no cambia la musica.
sin_pedal, d1 = leer(DELTA4 + NOTA + FIN)
con_pedal, d2 = leer(PEDAL + DELTA4 + NOTA + PEDAL + FIN)
check("un control change no altera las notas", con_pedal, sin_pedal)
check("   ni la duracion", d2, d1)

# Un FB partido por el final del buffer no puede reventar. Esto NO falla con la
# version vieja —la tabla de anchos mentia pero el salto se pasaba de largo y el
# bucle salia igual—; esta para que siga sin reventar si alguien la toca.
notas, _ = leer(DELTA4 + NOTA + b"\xfb\x40",
                estricto=False)
check("FB truncado al final no revienta", len(notas), 1)

# Un evento desconocido para, y dice donde. Antes avanzaba uno y seguia.
try:
    leer(DELTA4 + NOTA + bytes([0x7A]) + NOTA + FIN)
    check("evento desconocido para", "no fallo", "ValueError")
except ValueError as e:
    check("evento desconocido para", "ValueError", "ValueError")
    check("   y dice en que byte", "byte 7" in str(e), True)

# Con estricto=False devuelve lo de antes del byte raro, no lo de despues.
notas, _ = leer(DELTA4 + NOTA + bytes([0x7A]) + NOTA + FIN, estricto=False)
check("estricto=False corta donde empieza la duda", len(notas), 1)

# --- El marcador de inicio de pista ---
#
# `decode_blocks` no tenia ni una prueba, y es la unica funcion que puede
# comprobar el marcador, porque es la unica que recibe la pista entera.

print("\nla pista entera: marcador y final")

def bloques(flujo, relleno=True):
    """Empaqueta un flujo en bloques de 147 bytes, como los manda el equipo."""
    b = bytearray(flujo)
    if relleno:
        b += bytes([RELLENO]) * ((-len(b)) % POR_BLOQUE)
    return [F.pack(bytes(b[i:i + POR_BLOQUE]))
            for i in range(0, len(b), POR_BLOQUE)]

buena = bloques(MARCADOR + DELTA4 + NOTA + FIN)
check("una pista bien formada se lee", len(F.decode_blocks(buena, start=0)[0]), 1)

# Sin marcador: falta el primer bloque. Antes se leia desalineada y callada.
sin_marca = bloques(DELTA4 + NOTA + FIN)
try:
    F.decode_blocks(sin_marca, start=0)
    check("sin F0 00 se rechaza", "no fallo", "ValueError")
except ValueError as e:
    check("sin F0 00 se rechaza", "ValueError", "ValueError")
    check("   y dice por donde empieza", "84" in str(e), True)

check("   con estricto=False se lee igual, avisando el que llama",
      len(F.decode_blocks(sin_marca, start=0, estricto=False)[0]), 1)

# El caso peligroso, entero: un flujo desalineado que NO revienta y saca notas
# en tiempos falsos. Es lo que hacian 10 pistas de los volcados.
#
# **Un desplazamiento de un byte cualquiera no vale para demostrarlo**, y ese
# fue el primer intento: como los bytes de dato son todos menores que 0x80, caer
# sobre uno da "evento desconocido" y para. Solo se cuela cuando el corte cae
# justo sobre un byte de estado — que es lo que pasa cuando falta un bloque
# entero. Se simula cortando por el inicio de la primera nota: lo que queda es
# gramatica valida y **las dos notas salen 4 relojes antes de donde estan**.
verdadero = MARCADOR + DELTA4 + NOTA + DELTA4 + NOTA + FIN
reales, _ = F.decode_events(verdadero, start=0)
desplazado = verdadero[3:]                    # se pierden `F0 00` y el delta
enganosas, _ = F.decode_events(desplazado, start=0, estricto=False)
check("desalineado saca las mismas notas...", len(enganosas), len(reales))
check("   ...en tiempos que no son los suyos, y sin una queja",
      ([n.time for n in enganosas], [n.time for n in reales]), ([0, 4], [4, 8]))

# Encadenado de bloques: solo el primero lleva prefijo, el resto es continuacion
# pura. Si alguien le quita el prefijo a todos, las notas del segundo se pierden.
# 30 notas y no 20: con 20 el flujo son 122 bytes y cabe entero en un bloque,
# asi que la prueba de encadenado no encadenaba nada y la de "falta el ultimo
# bloque" se quedaba sin bloques que quitar.
NOTAS = 30
notas_muchas = [F.Note(60 + (i % 12), 100, 108, i * 120) for i in range(NOTAS)]
bl = F.encode_blocks(notas_muchas, 120 * NOTAS, None, start=0)
check("%d notas necesitan mas de un bloque" % NOTAS, len(bl) > 1, True)
vuelta, _ = F.decode_blocks(bl, start=0)
check("ida y vuelta por varios bloques", vuelta, notas_muchas)

# Sin F2: falta el ultimo bloque. Nadie lo comprobaba.
#
# **Hay que quitarle el ultimo bloque a una pista de verdad, no fabricar un
# bloque corto.** Un bloque corto se rellena de ceros al empaquetar, el
# decodificador se topa con el relleno y falla por "evento desconocido": la
# prueba pasaba, pero por un motivo que no era el suyo. De ahi la comprobacion
# del texto del error.
try:
    F.decode_blocks(bl[:-1], start=0)
    check("sin F2 se rechaza", "no fallo", "ValueError")
except ValueError as e:
    check("sin F2 se rechaza", "ValueError", "ValueError")
    check("   por el final que falta, no por otra cosa", "F2" in str(e), True)
check("   y con estricto=False devuelve lo leido",
      len(F.decode_blocks(bl[:-1], start=0, estricto=False)[0]) > 0, True)

# `decode_track` NO puede exigir el F2: un bloque suelto de una pista larga
# acaba a media pista y eso es normal. Que siga sin exigirlo.
check("un bloque suelto sin F2 se lee sin queja",
      len(F.decode_track(bl[0], start=0)[0]) > 0, True)

# --- Negras por compas ---
#
# La formula era `num` para /4 y `num // 2` para lo demas: acierta en /4 y en
# los /8 de numerador par, o sea en todo lo que generan los motores hoy, y falla
# en las otras doce signaturas que el aparato admite.

print("\nnegras por compas")
for num, den, esperado in ((4, 4, 4), (3, 4, 3), (6, 8, 3), (12, 8, 6),
                           (8, 16, 2), (16, 16, 4), (2, 4, 2), (9, 8, 4.5)):
    if esperado != int(esperado):
        try:
            F.negras_por_compas(num, den)
            check("rechaza %d/%d" % (num, den), "no fallo", "ValueError")
        except ValueError:
            check("rechaza %d/%d, que son %.1f negras" % (num, den, esperado),
                  "ValueError", "ValueError")
    else:
        check("%d/%d son %d negras" % (num, den, esperado),
              F.negras_por_compas(num, den), esperado)

# El caso que el codigo viejo se tragaba redondeando: 8/16 son 2 negras y
# `num // 2` daba 4, o sea el doble de la seccion.
check("8/16 no son 4 negras (era el fallo)", F.negras_por_compas(8, 16) != 8 // 2, True)

for den in (2, 3, 32):
    try:
        F.negras_por_compas(4, den)
        check("rechaza denominador %d" % den, "no fallo", "ValueError")
    except ValueError:
        check("rechaza denominador %d" % den, "ValueError", "ValueError")

# Y que la signatura escrita en el byte 14 se relea igual y case con las
# negras. Es el circuito completo: lo que se escribe, lo que se lee y lo que se
# usa para medir la pista.
for num, den in ((4, 4), (3, 4), (6, 8), (12, 8), (8, 16), (16, 16)):
    pl = F.set_time_signature(bytes(147), num, den)
    check("%2d/%-2d ida y vuelta por el byte 14" % (num, den),
          F.decode_time_signature(pl), (num, den))
    check("   y son %d negras" % F.negras_por_compas(num, den),
          F.negras_por_compas(*F.decode_time_signature(pl)),
          F.negras_por_compas(num, den))


# --- Percusion o no, al importar una partitura --------------------------
#
# Esta decision se ha equivocado dos veces, y las dos se descubrio tocando:
#
#   1. Por la ranura de destino: D1, D2 y PC eran percusion siempre. Meter la
#      marimba en `PC` la puso a sonar por un kit de bateria, con una nota
#      sostenida que daba un pitido y sobrevivia al ciclo de corriente.
#   2. Por el rango de alturas: bateria si abarca dos octavas o menos y no baja
#      de 35. **No arreglaba su propio caso** — la marimba mide 55-74, o sea 19
#      de rango arrancando en 55, y seguia entrando por bateria. No podia
#      funcionar: un kit de GM ocupa 35-81 y una marimba cabe entera ahi dentro.
#
# El caso motivador va aqui dentro, literal, para que el tercer intento no pueda
# repetir el segundo.

print("\nvoz al importar: percusion o melodia")
import importar as I

MARIMBA = [55, 62, 67, 74, 60, 55]     # las alturas reales del caso
check("la marimba cabe entera en el rango de un kit de GM",
      (min(MARIMBA) >= 35, max(MARIMBA) <= 81), (True, True))
check("y por eso ningun umbral de alturas la separa",
      max(MARIMBA) - min(MARIMBA) <= 24, True)

check("marimba por el canal 1 -> melodica", I.decidir_voz({0})[0], False)
check("bombo por el canal 10 -> kit", I.decidir_voz({I.CANAL_PERCUSION})[0], True)
check("varios canales melodicos -> melodica", I.decidir_voz({0, 2, 5})[0], False)
check("sin canal -> melodica, que es el lado seguro",
      I.decidir_voz(set())[0], False)
check("--voz kit manda sobre el canal",
      I.decidir_voz({0}, forzar_kit=True)[0], True)

# La mezcla no tiene respuesta buena, asi que se cae del lado seguro y se avisa.
es_bat, por_que = I.decidir_voz({0, I.CANAL_PERCUSION})
check("canal 10 mezclado con otros -> melodica", es_bat, False)
check("   y lo dice en voz alta", "MEZCLA" in por_que, True)

# Y que la razon nunca vaya vacia: el fallo de la marimba se paso meses sin que
# la salida diera una pista de por que se habia elegido kit.
for canales in (set(), {0}, {I.CANAL_PERCUSION}, {0, I.CANAL_PERCUSION}):
    check("siempre dice por que (canales %s)" % sorted(canales),
          bool(I.decidir_voz(canales)[1]), True)

print("\ndecodificacion de pistas reales")
CASOS = [
    ("dumps/30-una-nota.syx",        (0x12,0x00,0x00), [(60,112,108,0)],            3840),
    ("dumps/31-semitono-arriba.syx", (0x12,0x00,0x00), [(61,112,108,0)],            3840),
    ("dumps/32-dos-semitonos.syx",   (0x12,0x00,0x00), [(62,112,108,0)],            3840),
    ("dumps/33-octava.syx",          (0x12,0x00,0x00), [(72,112,108,0)],            3840),
    ("dumps/34-velocity-suave.syx",  (0x12,0x00,0x00), [(60, 32,108,0)],            3840),
    ("dumps/36-posicion.syx",        (0x12,0x00,0x00), [(60,112,108,1920)],         3840),
    ("dumps/41-duracion.syx",        (0x12,0x00,0x08), [(60,112,432,0),(60,112,432,1920)], None),
    ("dumps/53-escrito-72.syx",      (0x12,0x00,0x08), [(72,112,432,0),(60,112,432,1920)], None),
]
for archivo, addr, esperadas, total in CASOS:
    if not os.path.exists(archivo):
        continue
    pl = _blk(archivo, addr)
    notas, dur = F.decode_track(pl)
    check("%-28s notas" % os.path.basename(archivo),
          [(n.pitch, n.velocity, n.gate, n.time) for n in notas], esperadas)
    if total is not None:
        check("   duracion total = %d relojes (%d compases)" % (total, total // 1920), dur, total)

print("\nlo que revelo la gramatica")
check("gate de semicorchea al 90%", F.gate_for(120), 108)
check("gate de negra al 90%", F.gate_for(480), 432)
check("negra/semicorchea = 432/108 = 4", 432 // 108, 4)
check("un compas de 4/4 = 1920 relojes", F.CLOCKS_PER_QUARTER * 4, 1920)
check("INTRO de 2 compases = 3840", F.bar_beat_to_position(3), 3840)

print("\nsecciones en el byte tr")
check("Intro pista 0",  F.track_byte(0, 0), 0x00)
check("Main A pista 0", F.track_byte(1, 0), 0x08)
check("Main B pista 0", F.track_byte(2, 0), 0x10)
check("describe 0x08", F.describe_tr(0x08), "Main A pista 0")
check("describe 0x7F", F.describe_tr(0x7F), "cabecera del patron")
for mal, args in (("seccion 6", (6, 0)), ("pista 8", (0, 8))):
    try:
        F.track_byte(*args); check("rechaza %s" % mal, "no fallo", "ValueError")
    except ValueError:
        check("rechaza %s" % mal, "ValueError", "ValueError")

print("\ncodificar: ida y vuelta")
if os.path.exists("dumps/41-duracion.syx"):
    pl = _blk("dumps/41-duracion.syx", (0x12,0x00,0x08))
    notas, dur = F.decode_track(pl)
    crudo = F.encode_track(notas, dur, prefix=F.unpack(pl))
    notas2, dur2 = F.decode_track(F.pack(crudo))
    check("re-codificar y volver a leer da las mismas notas", notas2, notas)
    check("   y la misma duracion total", dur2, dur)
    # construido desde cero
    hechas = [F.Note(60, 100, F.gate_for(480), 0), F.Note(67, 100, F.gate_for(480), 1920)]
    crudo2 = F.encode_track(hechas, 3840)
    n3, d3 = F.decode_track(F.pack(crudo2))
    check("patron construido desde cero se relee igual", n3, hechas)
    check("   con su duracion total", d3, 3840)
    # El gate tiene dos formas: hasta 2047 usa el evento corto, mas alla el
    # largo, que llega a 262143. El limite viejo era 2047 y lo rompio el primer
    # drone de dos compases (3800 relojes).
    n = F.Note(60, 100, 3800, 0)
    d4, t4 = F.decode_track(F.pack(F.encode_track([n], 7680)))
    check("gate largo, ida y vuelta", d4, [n])
    try:
        F.encode_track([F.Note(60, 100, 1 << 18, 0)], 1920)
        check("rechaza gate imposible", "no fallo", "ValueError")
    except ValueError:
        check("rechaza gate imposible", "ValueError", "ValueError")

print("\ncabecera del patron")
DOFFU = "../doffu/32measures/Measr32_QY100.syx"
def _cab(f):
    ms, _ = P.parse_all(open(f, "rb").read())
    c = [bytes(m.data) for m in ms if m.addr[0] == 0x12 and m.addr[2] == 0x7F]
    return c[0] if c else None

CAB = [("dumps/30-una-nota.syx", "", [2,2,2,1,1,2]),
       ("dumps/41-duracion.syx", "", [2,3,2,1,1,2]),
       ("dumps/53-escrito-72.syx", "", [2,3,2,1,1,2])]
for archivo, nombre, compases in CAB:
    if not os.path.exists(archivo): continue
    n, m = F.decode_header(_cab(archivo))
    check("%-24s nombre y compases" % os.path.basename(archivo), (n, m), (nombre, compases))

if os.path.exists(DOFFU):
    n, m = F.decode_header(_cab(DOFFU))
    check("archivo de desbloqueo: nombre", n, "MEASR32")
    check("   32 compases en las seis secciones", m, [32]*6)
    check("   supera el tope de la interfaz", all(x > F.UI_MAX_MEASURES for x in m), True)

if os.path.exists("dumps/41-duracion.syx"):
    base = _cab("dumps/41-duracion.syx")
    # la longitud declarada coincide con la duracion real de las pistas
    ms, _ = P.parse_all(open("dumps/41-duracion.syx", "rb").read())
    _, comp = F.decode_header(base)
    for m_ in ms:
        if m_.addr[0] == 0x12 and m_.addr[2] != 0x7F:
            _, dur = F.decode_track(bytes(m_.data))
            check("   %s: cabecera y pista coinciden" % F.describe_tr(m_.addr[2]),
                  dur, F.section_clocks(comp[m_.addr[2] // 8]))
    # round-trip de escritura de cabecera
    nueva = F.encode_header(base, name="TEST", measures=[32,16,8,4,2,1])
    n2, m2 = F.decode_header(nueva)
    check("round-trip nombre", n2, "TEST")
    check("round-trip compases", m2, [32,16,8,4,2,1])
    check("reescribir lo mismo no cambia bytes",
          F.encode_header(base, name="", measures=[2,3,2,1,1,2]), base)
    for mal in (0, 33):
        try:
            F.encode_header(base, measures=[mal]*6)
            check("rechaza %d compases" % mal, "no fallo", "ValueError")
        except ValueError:
            check("rechaza %d compases" % mal, "ValueError", "ValueError")

print()
if FAILS:
    print("FALLARON %d: %s" % (len(FAILS), ", ".join(FAILS)))
    sys.exit(1)
print("Protocolo verificado: %d comprobaciones." % CHECKS[0])
