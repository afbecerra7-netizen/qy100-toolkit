"""Motores de musica andina colombiana: 3/4 nativo, seis secciones.

Modulo aparte de `estilo.py` **a proposito**, no por comodidad. Los motores de
alli estan escritos para 4/4 y no hay casi nada que reutilizar:

- El contragolpe en 2 y 4 —lo que hace que un beat se lea como bateria— **no
  tiene equivalente en 3/4**.
- La sesquialtera no existe en compas binario.
- El rasgueo del tiple es especifico del genero, no una densidad de un patron
  generico.

Forzar `beats_per_bar` por los motores de `estilo.py` habria arriesgado el
afrobeat y la soca, que ya funcionan, a cambio de un beneficio que solo usarian
los andinos. **La abstraccion compartida seria mas codigo que las dos
implementaciones separadas.**

## Lo que si comparten todos los andinos

El armazon: compas de 3/4, seis secciones con su densidad, una progresion por
genero, y las tres reglas de escritura que costaron caro aprender —

1. **Leer el patron de destino antes de escribir.** Los primeros `bambuco.py` y
   `pasillo.py` armaban la cabecera desde `CABECERA_BASE` (captura de un patron
   vacio) y escribian el registro a mano. Eso descarta el mezclador, los acordes
   por seccion, las longitudes de las otras secciones y **cualquier referencia a
   frase preset** del destino, sin avisar.
2. **Escribir las seis secciones de una vez.** Como hay que mandar el patron
   entero, escribir una seccion y luego otra borra la primera.
3. **`set_registry`, nunca `0xF8` a mano**, porque preserva las ranuras cuyo
   estado no reconoce — que son justamente las referencias a frases de fabrica.

## Sobre `Bypass`

Estos generos llevan **la progresion escrita dentro** de las notas, asi que van
en `Bypass`: lo que suena es lo que se escribio. Es lo contrario que las recetas
de `estilo.py`, cuyas pistas de acorde escriben Do mayor literal y delegan la
armonia al TYPE. Mezclar las dos convenciones en un mismo patron es como se
consigue que un `Cm7` suene mayor.
"""
from . import patternfmt as F

NEGRA = F.CLOCKS_PER_QUARTER
CORCHEA = NEGRA // 2
SEMI = NEGRA // 4

#: Densidad por seccion. En modo patron las secciones **no** se encadenan solas
#: —el Intro no salta a Main A y el Ending no cierra—, asi que estas no son
#: etapas de una forma: son **seis versiones del mismo groove** entre las que se
#: salta a mano con el miniteclado. De ahi que el Ending no "resuelva" nada;
#: simplemente es la mas desnuda, util como bajada.
SECCIONES = [
    ("Intro",   0.30, 4),
    ("Main A",  0.55, 8),
    ("Main B",  0.85, 8),
    ("Fill AB", 0.75, 2),
    ("Fill BA", 0.60, 2),
    ("Ending",  0.35, 4),
]


def compases_por_seccion():
    return [c for _n, _i, c in SECCIONES]


def _bar(c, beats):
    return c * NEGRA * beats


class Genero:
    """Una receta: progresion, pistas y motores. 3/4 salvo que se diga otra cosa.

    `progresion` es una lista de (nombre, raiz_midi, [alturas del acorde]) y se
    recorre a razon de `compases_por_acorde` por entrada. Las alturas se escriben
    literales porque la pista va en `Bypass`.
    """

    beats = 3
    nombre = "?"
    bpm = 120.0
    progresion = ()
    compases_por_acorde = 2
    pistas = ()          # (idx, nombre, papel, voz, es_bateria, motor)

    def acorde_de(self, c):
        i = (c // self.compases_por_acorde) % len(self.progresion)
        return self.progresion[i]

    def construir(self, seccion, compases, intensidad):
        """{indice_de_pista: [Note]} para una seccion."""
        return {idx: motor(self, compases, intensidad)
                for idx, _n, _p, _v, _b, motor in self.pistas}

    def total(self, compases):
        return F.section_clocks(compases, beats_per_bar=self.beats)


# --- Bambuco -------------------------------------------------------------
#
# Sesquialtera: las mismas seis corcheas oidas a la vez como 3+3 (6/8) y como
# 2+2+2 (3/4). **No son dos compases superpuestos** —eso seria un desfase— sino
# un solo compas leido de dos maneras, que funciona porque 6/8 y 3/4 duran igual.
#
#     corchea    1   2   3   4   5   6
#     6/8        X           X          percusion
#     3/4        X       X       X      tiple y bajo
#
# El patron del tiple viene documentado con precision de corchea: chasquido,
# rasgueo, bajo en la fundamental, rasgueo, bajo en la quinta, rasgueo. Los bajos
# caen en las corcheas 3 y 5, que en 3/4 son los tiempos 2 y 3 — o sea que **el
# tiple es la voz que cuenta en tres**, y es la que faltaba en las transcripciones
# de Tribe, donde marimba y tamboras agrupaban las dos en 3+3.

# --- El bambuco, medido sobre una partitura real -------------------------
#
# **"Papa con yuca"** es la onomatopeya del patron base, y es la identidad del
# genero. La celda sale de `te-ofrezco-mi-corazon-bambuco.mid` (coro, guitarra y
# tambora, 6/8), doblando los ataques por compas:
#
#     corchea      1      2       3      4       5      6
#     silaba       PA     PA      CON    YU      CA      ·
#     tambora     alto   alto    bajo   alto    bajo     ·
#     guitarra      ·   ACORDE   BAJO  ACORDE   BAJO     ·
#
# En 31 compases la guitarra da **31 ataques de acorde en la 2 y 31 en la 4**, y
# **31 notas graves sueltas en la 3 y 31 en la 5**. Uno por compas, sin
# excepcion. Los graves de la tambora coinciden exactamente con los bajos de la
# guitarra.
#
# **La corchea 6 esta vacia en los cuatro instrumentos de acompanamiento.**
#
# Y el bajo hace **quinta en la 3, fundamental en la 5** — en ese orden, en los
# treinta y un compases. No es fundamental-quinta como pondria cualquiera.
#
# ## Dos versiones equivocadas antes de esta, y por que
#
# 1. **Bombo en 1 y 4**, deducido de la sesquialtera sobre el papel: los dos
#    grupos de `3+3` empiezan ahi. Coherente y falso.
# 2. **Bombo en 1, 3, 5 con acordes en 1, 3, 5 y bajo en 4 y 6**, sacado de los
#    grooves de Tribe. El problema es que aquello es un bambuco tocado con
#    **tambores caribeños** —una adaptacion— y no el andino. Una transcripcion
#    real de otro conjunto no es una transcripcion del genero.
#
# La leccion: para el ritmo de un genero, **una partitura del genero** gana a la
# teoria metrica, a la prosa de internet y a una transcripcion de instrumentos
# que no son los suyos.

TAMB_ALTO, TAMB_BAJO = 45, 41        # parche agudo y grave de la tambora
ACORDE_EN = (1, 3)                   # corcheas 2 y 4
BAJO_EN = (2, 4)                     # corcheas 3 y 5


def _bambuco_tambora(g, compases, intensidad):
    """Cinco golpes: agudo en 1, 2 y 4, grave en 3 y 5. La 6 callada."""
    notas = []
    for c in range(compases):
        base = _bar(c, g.beats)
        for i, nota, vel in ((0, TAMB_ALTO, 104), (1, TAMB_ALTO, 84),
                             (2, TAMB_BAJO, 92), (3, TAMB_ALTO, 88),
                             (4, TAMB_BAJO, 96)):
            notas.append(F.Note(nota, vel, CORCHEA - 20, base + i * CORCHEA))
    return notas


def _bambuco_sonajas(g, compases, intensidad):
    """Guache continuo, **sin acentos**: es el suelo, no una voz.

    Si acentuara elegiria una lectura metrica y desharia la ambiguedad.
    """
    if intensidad < 0.45:
        return []
    return [F.Note(69, 62, CORCHEA - 30, _bar(c, g.beats) + i * CORCHEA)
            for c in range(compases) for i in range(6)]


def _bambuco_bajo(g, compases, intensidad):
    """Quinta en la corchea 3, fundamental en la 5. En ese orden.

    Medido en los 31 compases de la partitura sin una sola excepcion. Poner
    fundamental primero —lo natural— invierte el gesto: la llegada del bajo a la
    fundamental en la 5 es lo que cierra el compas.
    """
    notas = []
    for c in range(compases):
        _n, raiz, _v = g.acorde_de(c)
        base = _bar(c, g.beats)
        for i, alt, vel in ((BAJO_EN[0], raiz + 7, 88), (BAJO_EN[1], raiz, 100)):
            notas.append(F.Note(alt, vel, CORCHEA - 20, base + i * CORCHEA))
    return notas


def _bambuco_tiple(g, compases, intensidad):
    """Acorde en las corcheas 2 y 4, nada mas. Nunca en el tiempo fuerte."""
    notas = []
    for c in range(compases):
        _n, _r, voces = g.acorde_de(c)
        base = _bar(c, g.beats)
        for k, i in enumerate(ACORDE_EN):
            for alt in voces:
                notas.append(F.Note(alt, 90 if k == 0 else 80, CORCHEA - 30,
                                    base + i * CORCHEA))
    return notas


class Bambuco(Genero):
    nombre = "BAMBUCO"
    bpm = 152.0
    compases_por_acorde = 1
    # La forma armonica de la partitura, trasladada a Mi menor por el tiple:
    # i - i - iv - V7 - i - V7 - i - I. Ese ultimo mayor es el giro del compas 12
    # del original, dominante secundaria hacia el iv.
    progresion = (
        ("Em", 40, [52, 55, 59]),
        ("Em", 40, [52, 55, 59]),
        ("Am", 45, [57, 60, 64]),
        ("B7", 47, [51, 54, 59]),
        ("Em", 40, [52, 55, 59]),
        ("B7", 47, [51, 54, 59]),
        ("Em", 40, [52, 55, 59]),
        ("E",  40, [52, 56, 59]),
    )
    pistas = (
        (0, "D1", "tambora: papa con yuca", "Rock Kit", True,  _bambuco_tambora),
        (2, "PC", "guache continuo",        "Rock Kit", True,  _bambuco_sonajas),
        (3, "BA", "bajo: quinta y fundamental", "Aco.Bass", False, _bambuco_bajo),
        (4, "C1", "acordes en 2 y 4",       "NylonGtr", False, _bambuco_tiple),
    )


# --- Bambuco fiestero (santandereano) ------------------------------------
#
# El bambuco tiene variantes regionales documentadas —de salon, fiestero,
# sureño, sanjuanero, caucano, patiano, del litoral— y el caracter sigue a la
# geografia: lento y melancolico en el Cauca, **fiestero en el Tolima y los
# Santanderes**, campesino en el altiplano cundiboyacense.
#
# `brisas-del-pamplonita-bambuco.mid` es santandereano (el Pamplonita es un rio
# de Norte de Santander) y su acompanamiento es **otro patron**, no otra
# transcripcion del mismo:
#
#     corchea      1      2      3      4      5      6
#     brisas      BAJO  ACORDE  BAJO  ACORDE  BAJO  ACORDE     fiestero
#     te-ofrezco    ·   ACORDE  BAJO  ACORDE  BAJO    ·        de salon
#
# Medido: graves en 1/3/5 (51, 51, 65 ataques) frente a 2/4/6 (14, 12, 12), y
# agudos al reves. **Alternancia estricta bajo-acorde en las seis corcheas.**
#
# La diferencia es la que cabria esperar de los nombres: **el fiestero no deja
# huecos y empuja; el de salon deja vacias la 1 y la 6 y respira.** Que la
# variante fiestera este notada en 3/4 y la de salon en 6/8 deja de ser una
# eleccion del transcriptor y pasa a ser consecuencia del patron.
#
# La celda de tambora se comparte: es el mismo genero.


def _fiestero_bajo(g, compases, intensidad):
    """Bajo en las tres negras. Fundamental, quinta, fundamental."""
    notas = []
    for c in range(compases):
        _n, raiz, _v = g.acorde_de(c)
        base = _bar(c, g.beats)
        for k, (i, alt) in enumerate(((0, raiz), (2, raiz + 7), (4, raiz))):
            notas.append(F.Note(alt, 104 if k == 0 else 88, CORCHEA - 20,
                                base + i * CORCHEA))
    return notas


def _fiestero_tiple(g, compases, intensidad):
    """Acorde en las tres contras. Nunca coincide con el bajo."""
    posiciones = (1, 3, 5) if intensidad > 0.4 else (1, 5)
    notas = []
    for c in range(compases):
        _n, _r, voces = g.acorde_de(c)
        base = _bar(c, g.beats)
        for i in posiciones:
            for alt in voces:
                notas.append(F.Note(alt, 86 if i == 1 else 76, CORCHEA - 30,
                                    base + i * CORCHEA))
    return notas


class BambucoFiestero(Bambuco):
    nombre = "BAMBFIES"
    bpm = 168.0
    pistas = (
        (0, "D1", "tambora: papa con yuca", "Rock Kit", True,  _bambuco_tambora),
        (2, "PC", "guache continuo",        "Rock Kit", True,  _bambuco_sonajas),
        (3, "BA", "bajo en las tres negras", "Aco.Bass", False, _fiestero_bajo),
        (4, "C1", "acordes en las contras", "NylonGtr", False, _fiestero_tiple),
    )


# --- Pasillo -------------------------------------------------------------
#
# **Sin sesquialtera.** En ACMUS-MIR los 57 pasillos estan anotados en 3/4 con un
# solo nivel de pulso, frente a 71 de 73 bambucos en 6/8 con dos. Copiar aqui la
# estructura del bambuco meteria un cruce que el genero no tiene.
#
# La celda sale de `la-gata-goloza-fulgencio-garcia.mid`, el pasillo canonico.
# **El 60% de sus 184 compases repiten el mismo patron**, y separando por
# registro se ve que es:
#
#     corchea    1      2     3     4       5       6
#               BAJO    ·     ·   ACORDE  ACORDE    ·
#
# La corchea 1 lleva 183 graves contra 71 acordes; las corcheas 4 y 5 llevan 104
# y 110 acordes. **El bajo cae solo en el primer tiempo** —donde cambia el
# acorde— y los dos acordes vienen despues, el primero a contratiempo.
#
# Esa corchea de diferencia es lo que empuja: la version anterior de este modulo
# ponia los acordes en 3 y 5 (los tiempos 2 y 3), sacado de una descripcion en
# prosa. Poniendolos en 4 y 5, el primero cae **entre** los tiempos y el segundo
# en el tercero — sincopa y resolucion dentro del mismo compas.
#
# **Vino Tinto, del mismo compositor, usa otra celda**: el 58% de sus compases
# ocupan las seis corcheas, y va a 180 bpm frente a 160. Probablemente sea la
# misma division lento/fiestero que muestran los tempos anotados (dos grupos,
# 101 y 182). Aqui se implementa la de La Gata Golosa; la densa queda pendiente.

PASILLO_BAJO_EN = 0        # corchea 1
PASILLO_ACORDE_EN = (3, 4)  # corcheas 4 y 5


def _pasillo_bajo(g, compases, intensidad):
    """Solo en el primer tiempo. Fundamental, y quinta en los compases pares.

    Que el bajo suene **una vez por compas** es lo que deja sitio a los dos
    acordes. Rellenarlo con la quinta en el tercer tiempo —lo que hacia la
    version anterior— tapa la sincopa.
    """
    notas = []
    for c in range(compases):
        _n, raiz, _v = g.acorde_de(c)
        base = _bar(c, g.beats)
        alt = raiz if c % 2 == 0 else raiz + 7
        notas.append(F.Note(alt, 108, NEGRA - 40, base + PASILLO_BAJO_EN * CORCHEA))
    return notas


def _pasillo_tiple(g, compases, intensidad):
    """Dos acordes: uno a contratiempo y otro en el tercer tiempo."""
    notas = []
    for c in range(compases):
        _n, _r, voces = g.acorde_de(c)
        base = _bar(c, g.beats)
        for k, i in enumerate(PASILLO_ACORDE_EN):
            for alt in voces:
                notas.append(F.Note(alt, 78 if k == 0 else 90, CORCHEA - 20,
                                    base + i * CORCHEA))
    return notas


def _pasillo_requinto(g, compases, intensidad):
    """Contracanto en la segunda mitad de cada frase. Dialoga, no rellena."""
    if intensidad < 0.5:
        return []
    notas = []
    for c in range(compases):
        if c < compases / 2.0:
            continue
        _n, _r, voces = g.acorde_de(c)
        base = _bar(c, g.beats)
        for k, i in enumerate((1, 2, 5)):
            notas.append(F.Note(voces[k % len(voces)] + 12, 80, CORCHEA - 20,
                                base + i * CORCHEA))
    return notas


class Pasillo(Genero):
    nombre = "PASILLO"
    bpm = 160.0
    compases_por_acorde = 2
    progresion = (
        ("Am", 45, [57, 60, 64]),
        ("Dm", 50, [57, 62, 65]),
        ("E7", 52, [56, 59, 62]),
        ("Am", 45, [57, 60, 64]),
    )
    pistas = (
        (3, "BA", "bajo en el primer tiempo", "Aco.Bass", False, _pasillo_bajo),
        (4, "C1", "acordes en 4 y 5",         "NylonGtr", False, _pasillo_tiple),
        (5, "C2", "requinto, contracanto",    "SteelGtr", False, _pasillo_requinto),
    )


# --- Pasillo denso (fiestero, "Vino Tinto") ------------------------------
#
# `vino-tinto-fulgencio-garcia.mid`, mismo compositor que La Gata Golosa pero a
# 180 bpm en vez de 160, usa **otra celda**: el 58% de sus 216 compases ocupan
# las seis corcheas. Y midiendo esos 126 compases aparece que no es un rasgueo
# mas denso:
#
#     corchea              1     2     3     4     5     6
#     graves <G3         106   113    79    54    67    72
#     agudas              20    13    47    72    59    54
#     notas a la vez     1.0   1.0   1.0   1.0   1.0   1.0
#
# **Una sola nota por corchea, siempre, y la velocity constante.** No hay
# acordes: es una **linea que camina**, grave al principio del compas y subiendo
# hacia el final. A 180 bpm la mano izquierda no rasguea, corre.
#
# Encaja con la division lento/fiestero que ya salia en los tempos anotados del
# dataset (dos grupos, 101 y 182): el lento acompaña con acordes, el fiestero
# con linea.
#
# **Lo medido es la linea del bajo.** La colocacion de los acordes aqui es una
# eleccion: en el original la mano derecha lleva melodia, no acompanamiento, asi
# que no hay nada que copiar. Se ponen escasos y fuera del camino de la linea.

PASILLO_LINEA = (0, 0, 2, 4, 7, 4)     # grados sobre la fundamental, por corchea


def _pasillo_linea(g, compases, intensidad):
    """Corcheas continuas subiendo del grave al medio. Velocity plana.

    La velocity constante esta medida y **no se humaniza**: lo que hace correr a
    la linea es su regularidad. Acentuarla la convertiria en un patron con
    tiempo fuerte, que es justo lo que no es.
    """
    notas = []
    for c in range(compases):
        _n, raiz, _v = g.acorde_de(c)
        base = _bar(c, g.beats)
        grados = PASILLO_LINEA if intensidad > 0.45 else (0, None, 4, None, 7, None)
        for i, gr in enumerate(grados):
            if gr is None:
                continue
            notas.append(F.Note(raiz + gr, 92, CORCHEA - 15, base + i * CORCHEA))
    return notas


def _pasillo_acordes_escasos(g, compases, intensidad):
    """Acorde en el segundo y el tercer tiempo. Puntua, no acompana."""
    if intensidad < 0.4:
        return []
    notas = []
    for c in range(compases):
        _n, _r, voces = g.acorde_de(c)
        base = _bar(c, g.beats)
        for i in (2, 4):
            for alt in voces:
                notas.append(F.Note(alt + 12, 74, CORCHEA - 30, base + i * CORCHEA))
    return notas


class PasilloDenso(Pasillo):
    nombre = "PASDENSO"
    bpm = 180.0
    pistas = (
        (3, "BA", "linea en corcheas continuas", "Aco.Bass", False, _pasillo_linea),
        (4, "C1", "acordes escasos",             "NylonGtr", False,
         _pasillo_acordes_escasos),
        (5, "C2", "requinto, contracanto",       "SteelGtr", False, _pasillo_requinto),
    )


GENEROS = {"bambuco": Bambuco, "fiestero": BambucoFiestero,
           "pasillo": Pasillo, "pasillodenso": PasilloDenso}
