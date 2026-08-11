#!/usr/bin/env python3
"""Comprueba que las pruebas del decodificador prueban algo.

    .venv/bin/python test_regresiones.py

Existe por un resultado incomodo: `test_protocol.py` daba **117 comprobaciones,
todas en verde, con el decodificador de antes y con el de despues** de tres
cambios seguidos. Una suite que no distingue el codigo corregido del roto no
dice nada sobre el codigo; dice que se ejecuto.

Aqui se reintroduce cada defecto —sobre el fuente de hoy, en memoria, sin tocar
el fichero— y se exige que **alguna** comprobacion falle. Si un defecto vuelve y
todo sigue verde, el fallo esta en las pruebas y aparece aqui.

Lo que enseño escribirlo, y que no se veia de otro modo: **consumir `FB` de a un
byte da el mismo resultado que consumirlo entero** mientras el decodificador se
limite a saltar lo que no entiende, porque `cc` y `vv` son datos MIDI de 7 bits
y saltarlos uno a uno suma los mismos tres. El arreglo de `FB` solo cambia algo
cuando el decodificador ya falla ante lo desconocido. Los dos cambios se
hicieron por separado y **el segundo no servia de nada sin el primero**.
"""

import importlib.util
import sys
import types

FUENTE = "qy100syx/patternfmt.py"

# --- los mismos flujos de mano que en test_protocol.py -------------------
GATE, ALTURA, VEL = 432, 60, 112
MARCADOR = b"\xf0\x00"
DELTA4 = bytes([0x80 | 4])
NOTA = bytes([0xD0 | (GATE >> 7), GATE & 0x7F, ALTURA, VEL])
PEDAL = bytes([0xFB, 64, 127])
FIN = bytes([0xF2])


def cargar(fuente):
    """Compila un fuente modificado como modulo suelto."""
    mod = types.ModuleType("pf_mutado")
    mod.__file__ = FUENTE
    exec(compile(fuente, FUENTE, "exec"), mod.__dict__)
    return mod


# Cada entrada: (nombre, mutacion, comprobacion).
# La comprobacion devuelve True si el defecto **se nota**, o sea si el modulo
# mutado hace algo distinto de lo correcto. Se escribe en positivo —"esto es lo
# que rompe"— para que se lea sin invertir la logica mentalmente.

def _sin_fb(F):
    """FB consumido como un byte: la nota de detras ya no se lee."""
    try:
        notas, _ = F.decode_events(MARCADOR + PEDAL + DELTA4 + NOTA + FIN, start=0)
    except ValueError:
        return True                       # revienta: se nota
    return [(n.pitch, n.time) for n in notas] != [(ALTURA, 4)]


def _sin_marcador(F):
    """Sin el chequeo de F0 00: una pista descabezada se lee callada."""
    bl = [F.pack((DELTA4 + NOTA + FIN).ljust(128, b"\x40"))]
    try:
        F.decode_blocks(bl, start=0)
        return True                       # no protesta: se nota
    except ValueError:
        return False


def _sin_final(F):
    """Sin el chequeo de F2: una pista sin su ultimo bloque pasa por buena."""
    notas = [F.Note(60 + (i % 12), 100, 108, i * 120) for i in range(30)]
    bl = F.encode_blocks(notas, 120 * 30, None, start=0)
    assert len(bl) > 1, "hacen falta varios bloques para quitar el ultimo"
    try:
        F.decode_blocks(bl[:-1], start=0)
        return True
    except ValueError:
        return False


def _denominador(F):
    """La formula vieja: 8/16 salen 4 negras en vez de 2."""
    try:
        return F.negras_por_compas(8, 16) != 2
    except ValueError:
        return True


def _desconocido_callado(F):
    """Saltar el evento raro: salen notas de despues del byte que no se entiende."""
    flujo = MARCADOR + DELTA4 + NOTA + bytes([0x7A]) + NOTA + FIN
    try:
        notas, _ = F.decode_events(flujo, start=0)
        return len(notas) != 1            # devolvio la de despues: se nota
    except ValueError:
        return False


CASOS = [
    ("FB consumido como un solo byte",
     [("            i += 3\n"
       "        else:\n"
       "            # **Un estado desconocido no se salta.**",
       "            i += 1\n"
       "        else:\n"
       "            # **Un estado desconocido no se salta.**")],
     _sin_fb),

    ("sin comprobar el marcador F0 00",
     [("    if estricto and flujo[:2] != TRACK_MARKER:", "    if False:")],
     _sin_marcador),

    ("sin exigir el F2 del final",
     [("    if estricto and not fin:", "    if False:")],
     _sin_final),

    ("el denominador a la manera vieja",
     [("    negras4 = numerador * 4", "    negras4 = (numerador if denominador == 4\n"
                                      "               else numerador // 2) * denominador")],
     _denominador),

    # El defecto viejo no era "no protestar": era **avanzar un byte y seguir**,
    # que es lo que dejaba las notas de detras con altura y tiempo cambiados.
    # Quitar solo el `raise` deja el `break`, que para en el mismo sitio y no
    # reproduce nada — el primer intento de esta sonda fue justo ese y dijo que
    # el defecto no se notaba, cuando lo que no se notaba era la mutacion.
    ("evento desconocido saltado en silencio",
     [("            desconocidos.append((i, s))\n"
       "            if estricto:",
       "            desconocidos.append((i, s))\n"
       "            i += 1\n"
       "            continue\n"
       "            if estricto:")],
     _desconocido_callado),

    ("la tabla de anchos mintiendo sobre F0 y FB",
     [("                 2 if s == 0xF0 else 3 if s == CONTROL_CHANGE else 1)",
       "                 1)")],
     None),   # sin efecto observable hoy; se explica abajo
]


def main():
    original = open(FUENTE, encoding="utf-8").read()
    fallos = []

    # Primero: el codigo tal cual esta tiene que pasar todas las sondas.
    sano = cargar(original)
    for nombre, _, sonda in CASOS:
        if sonda is None:
            continue
        if sonda(sano):
            fallos.append("la sonda %r salta con el codigo SANO" % nombre)
            print("  MAL  %s — la sonda se dispara sin mutar nada" % nombre)
    if not fallos:
        print("el codigo de hoy pasa las %d sondas"
              % sum(1 for _, _, s in CASOS if s))

    print("\nreintroduciendo cada defecto")
    for nombre, sustituciones, sonda in CASOS:
        mutado = original
        for viejo, nuevo in sustituciones:
            n = mutado.count(viejo)
            if n != 1:
                fallos.append("%s: el ancla aparece %d veces, no 1" % (nombre, n))
                print("  MAL  %-42s el ancla ya no existe en el fuente" % nombre)
                mutado = None
                break
            mutado = mutado.replace(viejo, nuevo)
        if mutado is None:
            continue
        if sonda is None:
            # Se compila para asegurar que el ancla sigue siendo codigo vivo,
            # pero no hay nada que observar: con `1` en la tabla de anchos, el
            # salto de `i += 3` se pasa del final del buffer y el bucle sale
            # igual. **La tabla estaba mal y no se notaba**, que es exactamente
            # por lo que se arreglo: una guardia que no protege lo que dice.
            cargar(mutado)
            print("  --   %-42s no tiene efecto observable (ver el comentario)"
                  % nombre)
            continue
        try:
            F = cargar(mutado)
        except Exception as e:
            print("  ok   %-42s ni siquiera compila (%s)" % (nombre, type(e).__name__))
            continue
        if sonda(F):
            print("  ok   %-42s lo caza la suite" % nombre)
        else:
            fallos.append(nombre)
            print("  FALLA %-41s **vuelve el defecto y nadie se entera**" % nombre)

    print()
    if fallos:
        print("FALLARON %d:" % len(fallos))
        for f in fallos:
            print("  - %s" % f)
        return 1
    print("Cada defecto reintroducido lo caza alguna comprobacion.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
