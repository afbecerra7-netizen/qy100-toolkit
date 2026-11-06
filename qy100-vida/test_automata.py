"""Comprobaciones del automata. Sin pantalla, sin Kivy, sin aparato.

    .venv/bin/python test_automata.py

Siguiendo la regla de la casa: cada comprobacion tiene que poder fallar. Las
que miran defectos concretos dicen cual, para que si alguien "simplifica" el
codigo se sepa que se rompio.
"""

import automata as A

fallos = []
hechas = 0


def check(condicion, nombre, detalle=""):
    global hechas
    hechas += 1
    if not condicion:
        fallos.append(nombre + (" — " + detalle if detalle else ""))


def nueva(figura=None, **kw):
    a = A.Automata(semilla=7, **kw)
    a.limpiar()
    if figura:
        for f, c in figura:
            a.celdas[f][c] = True
    return a


# --- las reglas -------------------------------------------------------------

# El blinker es la prueba clasica: tres en linea oscilan con periodo 2.
a = nueva([(5, 4), (5, 5), (5, 6)])
inicio = a.huella()
a.evolucionar()
check(a.vivas() == 3, "blinker sigue con 3 celulas")
check(a.celdas[4][5] and a.celdas[5][5] and a.celdas[6][5],
      "blinker rota a vertical")
a.evolucionar()
check(a.huella() == inicio, "blinker vuelve al inicio en 2 generaciones")

# El bloque 2x2 es still life: no se mueve nunca.
a = nueva([(8, 8), (8, 9), (9, 8), (9, 9)])
antes = a.huella()
a.evolucionar()
check(a.huella() == antes, "el bloque 2x2 no cambia")

# Una celula sola muere; tres en L crean una cuarta.
a = nueva([(3, 3)])
a.evolucionar()
check(a.vivas() == 0, "una celula sola muere")

# El mundo es toroidal: un glider en el borde no se cae.
a = nueva()
a.sembrar_figura("glider", fila=0, col=0)
vivas0 = a.vivas()
for _ in range(8):
    a.evolucionar()
check(a.vivas() > 0, "el glider sobrevive al borde",
      "si se rompe, `vecinos` dejo de ser toroidal y el mundo tiene paredes")
check(vivas0 == 5, "el glider nace con 5 celulas")


# --- estancamiento ----------------------------------------------------------

# Un still life SI se detecta.
a = nueva([(8, 8), (8, 9), (9, 8), (9, 9)])
for _ in range(4):
    a.evolucionar()
check(a.estancada, "el still life se detecta como estancado")

# A NIVEL DE REJILLA un oscilador NO se marca quieto: repite, pero no se queda
# parado. Este es el defecto que se evito a proposito — comparar contra las
# ultimas N HUELLAS habria dado lo mismo para un still life y para un blinker.
a = nueva([(5, 4), (5, 5), (5, 6)])
marcas = []
for _ in range(8):
    a.evolucionar()
    marcas.append(a.rejilla_quieta)
check(not any(marcas), "la REJILLA no se marca quieta con un oscilador",
      "si falla, el detector de rejilla volvio a comparar contra las ultimas N "
      "huellas en vez de contra la anterior, y confunde un riff con la muerte")

# Pero A NIVEL DE MUSICA ese mismo blinker SI es un ciclo cerrado de periodo 2,
# y para este instrumento eso es el final: su premisa es no volver al mismo
# sitio. Misma comparacion, dos unidades, dos respuestas opuestas.
check(a.periodo == 2, "el blinker solo cierra un ciclo musical de periodo 2",
      "periodo medido: %s" % a.periodo)

# **El caso real, medido en el aparato el 2026-08-15**: dos bloques 2x2 y un
# blinker, 11 vivas. No estaba muerta ni rala — alternaba 5 y 7 columnas
# sonando. Es un loop de dos compases, y hay que cazarlo.
a = nueva([(9, 6), (9, 7), (10, 6), (10, 7),
           (2, 10), (3, 10), (4, 10),
           (1, 3), (1, 4), (2, 3), (2, 4)])
check(a.vivas() == 11, "preparado: la configuracion real son 11 celulas")
for _ in range(5):
    a.evolucionar()
check(a.periodo == 2, "la configuracion real se caza como ciclo de 2 compases",
      "periodo medido: %s — si es 0, volvio a mirar solo el compas anterior "
      "y los ciclos de periodo par se le escapan" % a.periodo)
check(not a.rejilla_quieta, "y la rejilla NO estaba quieta: por eso hacia falta "
      "medir la musica y no la rejilla")
check(not a.rala, "ni estaba rala: 5-7 columnas de 16 pasan el umbral")

# Y la rejilla vacia tambien es estancamiento, aunque no se repita nada.
a = nueva([(3, 3)])
a.evolucionar()
check(a.vivas() == 0 and a.estancada, "la rejilla vacia cuenta como estancada")

# Tocar la rejilla reinicia la deteccion.
a = nueva([(8, 8), (8, 9), (9, 8), (9, 9)])
for _ in range(4):
    a.evolucionar()
check(a.estancada, "preparado: estancada antes de tocar")
a.alternar(0, 0)
check(not a.estancada, "tocar la rejilla limpia el estancamiento")


# --- la subasta -------------------------------------------------------------

# Doce vivas en una columna no pueden ser doce notas.
a = nueva()
for f in range(12):
    a.celdas[f][3] = True
sel = a.subasta(3)
check(len(sel) == A.MAX_VOCES, "la subasta respeta el tope de voces",
      "sin esto el QY100 recibe acordes de doce notas")
check(sel == sorted(sel), "la subasta devuelve las filas de grave a agudo")

# Con menos vivas que el tope, salen todas.
a = nueva([(2, 5), (7, 5)])
check(len(a.subasta(5)) == 2, "con 2 vivas salen 2, no 4")

# Columna vacia, cero notas.
check(a.subasta(0) == [], "columna vacia no suena")

# La prioridad es estabilidad: la celula con mas vecinos gana. Se monta un
# bloque (cada celula con 3 vecinos) y una suelta en la misma columna.
a = nueva([(4, 6), (4, 7), (5, 6), (5, 7), (12, 6)])
sel = a.subasta(6, max_voces=2)
check(12 not in sel, "la celula aislada pierde contra el bloque",
      "si falla, la prioridad dejo de ser el numero de vecinos")


# --- las escalas ------------------------------------------------------------

a = nueva()

a.escala = A.NOMBRES_ESCALA.index("pentatonica menor")
check([a.nota_de(f) for f in range(6)] == [48, 51, 53, 55, 58, 60],
      "pentatonica menor por grados, con octava al sexto grado")

a.escala = A.NOMBRES_ESCALA.index("mayor")
check([a.nota_de(f) for f in range(8)] == [48, 50, 52, 53, 55, 57, 59, 60],
      "mayor por grados, octava justa al octavo")

# **Ninguna escala puede dar un semitono entre grados consecutivos** salvo los
# que la escala declara. Lo que se prueba aqui es que el mapeo va por GRADOS y
# no por semitonos: si alguien cambia nota_de a `NOTA_BASE + fila`, la fila 12
# daria 60 en todas las escalas.
notas12 = set()
for i, nombre in enumerate(A.NOMBRES_ESCALA):
    a.escala = i
    notas12.add(a.nota_de(12))
check(len(notas12) > 1, "escalas distintas dan notas distintas en la fila 12",
      "si falla, el mapeo volvio a ser cromatico y Life suena atonal")

# Todo lo que sale cabe en MIDI.
for i in range(len(A.NOMBRES_ESCALA)):
    a.escala = i
    for f in range(A.FILAS):
        n = a.nota_de(f)
        check(0 <= n <= 127, "nota %d de la fila %d en rango MIDI" % (n, f))


# --- resultado --------------------------------------------------------------

print("%d comprobaciones" % hechas)
if fallos:
    print("\nFALLAN %d:" % len(fallos))
    for f in fallos:
        print("  -", f)
    raise SystemExit(1)
print("todo bien")
