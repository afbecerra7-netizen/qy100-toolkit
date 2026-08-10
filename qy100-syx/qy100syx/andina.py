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
    denominador = 4     # 6/8 lo pone el currulao
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


# --- Torbellino ----------------------------------------------------------
#
# Cundiboyacense. **"Tan tan tan taaaaan"**, y la clave es que eso se lee a
# caballo del compas: las tres cortas son el final de un compas y la larga es el
# tiempo fuerte del siguiente. Una anacrusa de tres golpes que aterriza.
#
#     corchea      1      2    3     4     5     6
#     bombo      TAAAAN   ·    ·     ·   tan     ·        96% de los compases
#     caja       TAAN     ·    ·    tan  tan   tan        58%
#                 ^ aterriza aqui   ^^^^^^^^^^^^^^ empuja hacia el siguiente
#
# Medido en `suite-colombiana-torbellino-micontrabajo.mid`: el bombo hace
# `c0 durando 4 corcheas, c4 durando 2` en el 96% de sus 99 compases, y la caja
# `c0:2 c3:1 c4:1 c5:1` en el 58%.
#
# **La primera version tenia las posiciones bien y el gesto perdido**: cuatro
# golpes iguales, cortos, sin direccion. Se analizaron los ataques y no las
# duraciones, y en este genero **la figura esta en las duraciones**. Felipe lo
# canto en cuatro silabas y ahi se vio.
#
# Aviso de procedencia: el arreglo medido es **orquestal**, no de conjunto
# tradicional (tiple, requinto, guitarra y chucho). El reparto ritmico se sostuvo
# al contrastarlo de oido, pero el requinto —que lleva la figura rapida y
# continua del torbellino— no tiene equivalente en una orquesta y **no esta
# aqui**. Si al oirlo falta movimiento, es eso.

TORB_BOMBO, TORB_CAJA, TORB_CHUCHO = 36, 38, 82

#: La celda dura **dos compases** y la armonia cambia dentro de ella:
#:
#:     compas 1    tan(I)   tan(I)   tan(IV)      tres negras
#:     compas 2    taaaaan(V) ---------------     una nota que llena el compas
#:
#: Termina en la dominante y por eso el ciclo pide volver a empezar. Lo canto
#: Felipe: "tan(tonica) tan(tonica) tan(subdominante) tan(dominante)".
#:
#: Cuadra con lo medido en el arreglo, donde los instrumentos melodicos alternan
#: `c0:2 c2:2 c4:2` (tres negras) con `c0:6` (una larga) — entre el 26% y el 37%
#: de sus compases cada figura. **Estaba en los datos y no se supo leer**: se
#: miraron las dos figuras como patrones alternativos en vez de como las dos
#: mitades de una sola celda de dos compases.
#:
#: La version anterior movia la armonia cada dos compases: **seis veces mas
#: lenta de lo que debe**.
TORB_CELDA = [
    (0, 0, 0), (0, 1, 0), (0, 2, 1),      # I, I, IV
    (1, 0, 2),                            # V, sostenido todo el compas
]


def _torb_grado(g, c, t):
    """Que acorde toca en el compas `c`, tiempo `t`. None si no hay ataque."""
    for cc, tt, grado in TORB_CELDA:
        if c % 2 == cc and t == tt:
            return g.progresion[grado]
    return None


def _torbellino_bombo(g, compases, intensidad):
    """Tres golpes en el primer compas, uno largo en el segundo.

    Que el segundo lleve **un solo golpe que dura tres tiempos** es lo que hace
    de la figura una llegada. Rellenarlo la deja sin direccion.
    """
    notas = []
    for c in range(compases):
        base = _bar(c, g.beats)
        for tiempo in range(g.beats):
            if _torb_grado(g, c, tiempo) is None:
                continue
            largo = NEGRA * 3 - 40 if c % 2 else NEGRA - 30
            notas.append(F.Note(TORB_BOMBO, 108 if tiempo == 0 else 92,
                                largo, base + tiempo * NEGRA))
    return notas


def _torbellino_caja(g, compases, intensidad):
    """Las tres cortas al final del segundo compas, empujando a la tonica.

    En crescendo: lo que las hace anacrusa y no relleno es que crezcan hacia el
    acorde que viene.
    """
    if intensidad < 0.4:
        return []
    notas = []
    for c in range(compases):
        if c % 2 == 0:
            continue
        base = _bar(c, g.beats)
        for k, i in enumerate((3, 4, 5)):
            notas.append(F.Note(TORB_CAJA, 70 + k * 10, CORCHEA - 30,
                                base + i * CORCHEA))
    return notas


def _torbellino_chucho(g, compases, intensidad):
    if intensidad < 0.5:
        return []
    return [F.Note(TORB_CHUCHO, 58, CORCHEA - 30,
                   _bar(c, g.beats) + i * CORCHEA)
            for c in range(compases) for i in range(6)]


def _torbellino_bajo(g, compases, intensidad):
    """La fundamental de cada acorde de la celda."""
    notas = []
    for c in range(compases):
        base = _bar(c, g.beats)
        for tiempo in range(g.beats):
            ac = _torb_grado(g, c, tiempo)
            if ac is None:
                continue
            largo = NEGRA * 3 - 40 if c % 2 else NEGRA - 30
            notas.append(F.Note(ac[1], 104 if tiempo == 0 else 88,
                                largo, base + tiempo * NEGRA))
    return notas


def _torbellino_tiple(g, compases, intensidad):
    """El acorde en cada ataque. Aqui vive la armonia rapida."""
    notas = []
    for c in range(compases):
        base = _bar(c, g.beats)
        for tiempo in range(g.beats):
            ac = _torb_grado(g, c, tiempo)
            if ac is None:
                continue
            largo = NEGRA * 3 - 60 if c % 2 else NEGRA - 50
            for alt in ac[2]:
                notas.append(F.Note(alt, 90 if tiempo == 0 else 76,
                                    largo, base + tiempo * NEGRA))
    return notas


class Torbellino(Genero):
    nombre = "TORBELLI"
    bpm = 120.0
    # Los tres grados en orden I, IV, V. La celda los recorre; `acorde_de` no se
    # usa aqui porque la armonia va por tiempo, no por compas.
    progresion = (
        ("Am", 45, [57, 60, 64]),      # I  tonica
        ("Dm", 50, [57, 62, 65]),      # IV subdominante
        ("E7", 52, [56, 59, 62]),      # V  dominante
    )
    pistas = (
        (0, "D1", "bombo con la celda",  "Rock Kit", True,  _torbellino_bombo),
        (1, "D2", "caja: tan tan tan",   "Rock Kit", True,  _torbellino_caja),
        (2, "PC", "chucho continuo",     "Rock Kit", True,  _torbellino_chucho),
        (3, "BA", "bajo con la celda",   "Aco.Bass", False, _torbellino_bajo),
        (4, "C1", "acordes I I IV | V",  "NylonGtr", False, _torbellino_tiple),
    )


# --- Guabina -------------------------------------------------------------
#
# Medida en `santo-guabina.mid`, y **empata con el torbellino en consistencia:
# 35 de 36 compases, el 97%**, en las tres capas a la vez.
#
#     corchea      1      2      3      4      5      6
#     bajo       BAJO     ·      ·      ·    BAJO     ·
#     acorde       ·      ·   ACORDE    ·      ·   ACORDE
#     tambora    grave    ·    agudo    ·    grave  agudo
#
# El bajo cae en 1 y 5 **igual que en el torbellino**; lo que separa los dos
# generos es la respuesta armonica. El torbellino pone los acordes en los tres
# negros y la guabina en las contras, justo detras de cada bajo. Mismo esqueleto,
# distinto eco.
#
# La tambora dobla las dos capas con timbres distintos —grave con el bajo, agudo
# con el acorde—, que es lo que hace audible el reparto sin que haya dos
# instrumentos.
#
# El coro del original canta sobre todo en 1 y 3 (42% de los compases): la
# melodia se apoya en el bajo y en el primer acorde, no en el segundo.

GUAB_BAJO, GUAB_ALTO = 41, 45      # tambora grave y aguda


def _guabina_tambora(g, compases, intensidad):
    """Grave en 1 y 5 con el bajo, agudo en 3 y 6 con el acorde."""
    notas = []
    for c in range(compases):
        base = _bar(c, g.beats)
        for i, nota, vel in ((0, GUAB_BAJO, 104), (2, GUAB_ALTO, 84),
                             (4, GUAB_BAJO, 96), (5, GUAB_ALTO, 78)):
            notas.append(F.Note(nota, vel, CORCHEA - 20, base + i * CORCHEA))
    return notas


def _guabina_chucho(g, compases, intensidad):
    if intensidad < 0.5:
        return []
    return [F.Note(82, 58, CORCHEA - 30, _bar(c, g.beats) + i * CORCHEA)
            for c in range(compases) for i in range(6)]


def _guabina_bajo(g, compases, intensidad):
    """Corcheas 1 y 5. Fundamental y quinta."""
    notas = []
    for c in range(compases):
        _n, raiz, _v = g.acorde_de(c)
        base = _bar(c, g.beats)
        for i, alt, vel in ((0, raiz, 104), (4, raiz + 7, 88)):
            notas.append(F.Note(alt, vel, CORCHEA - 20, base + i * CORCHEA))
    return notas


def _guabina_tiple(g, compases, intensidad):
    """Acordes en 3 y 6: detras de cada bajo, nunca encima."""
    posiciones = (2, 5) if intensidad > 0.35 else (2,)
    notas = []
    for c in range(compases):
        _n, _r, voces = g.acorde_de(c)
        base = _bar(c, g.beats)
        for k, i in enumerate(posiciones):
            for alt in voces:
                notas.append(F.Note(alt, 88 if k == 0 else 76, CORCHEA - 30,
                                    base + i * CORCHEA))
    return notas


class Guabina(Genero):
    nombre = "GUABINA"
    bpm = 120.0
    compases_por_acorde = 2
    progresion = (
        ("Am", 45, [57, 60, 64]),
        ("Dm", 50, [57, 62, 65]),
        ("Am", 45, [57, 60, 64]),
        ("E7", 52, [56, 59, 62]),
    )
    pistas = (
        (0, "D1", "tambora grave y aguda", "Rock Kit", True,  _guabina_tambora),
        (2, "PC", "chucho continuo",       "Rock Kit", True,  _guabina_chucho),
        (3, "BA", "bajo en 1 y 5",         "Aco.Bass", False, _guabina_bajo),
        (4, "C1", "acordes en 3 y 6",      "NylonGtr", False, _guabina_tiple),
    )


# --- Bambuco melancolico (caucano) ---------------------------------------
#
# La tercera variante: **lento y melancolico en el Cauca**, frente al fiestero
# del Tolima y los Santanderes y al de salon. Aqui las fuentes dan **menos** de
# lo habitual y conviene decirlo.
#
# Las dos partituras disponibles —el Bambuco No. 1 en Si menor de Adolfo Mejia y
# `y-un-cafe-a-las-8`— tienen consistencia del **30% y 37%**, por debajo del
# umbral: son una pieza de concierto y una cancion arreglada, no acompanamientos
# repetidos. **No hay celda que extraer.**
#
# Lo que si esta medido:
#
#     tempo            68 bpm      contra 152 (salon) y 168 (santandereano)
#     bajo             evita el 1  19 ataques en la corchea 1 contra 113 en la 2
#     acompanamiento   casi continuo, las seis corcheas en el 37% de los compases
#
# **Un bajo que rehuye el tiempo fuerte es lo que produce la sensacion de
# flotar**, y es la diferencia mas clara con las otras dos variantes, donde el
# bajo cae en 3 y 5 (salon) o en 1, 3 y 5 (fiestero).
#
# El reparto concreto de las corcheas **es criterio, no medicion**. Con dos
# fuentes por debajo del umbral no da para mas, y forzar una celda de un material
# que no la tiene es exactamente el error que costo tres intentos en el bambuco
# de salon. Si aparece una partitura de bambuco caucano con acompanamiento
# repetido, esto se mide y se sustituye.


def _melanc_bajo(g, compases, intensidad):
    """Nunca en el tiempo fuerte: corcheas 2 y 5.

    Medido — 19 ataques en la 1 contra 113 en la 2. El hueco en el 1 es lo que
    lo hace flotar.
    """
    notas = []
    for c in range(compases):
        _n, raiz, _v = g.acorde_de(c)
        base = _bar(c, g.beats)
        for i, alt, vel in ((1, raiz, 88), (4, raiz + 7, 74)):
            notas.append(F.Note(alt, vel, NEGRA - 40, base + i * CORCHEA))
    return notas


def _melanc_tiple(g, compases, intensidad):
    """Acompanamiento casi continuo y flojo: acompana sin marcar.

    A 68 bpm una corchea dura medio segundo, asi que "continuo" aqui no es
    denso: es un colchon. Las velocities son bajas y planas a proposito — si
    acentuara, marcaria un pulso y el genero es justamente el que no lo marca.
    """
    posiciones = (0, 2, 3, 5) if intensidad > 0.45 else (0, 3)
    notas = []
    for c in range(compases):
        _n, _r, voces = g.acorde_de(c)
        base = _bar(c, g.beats)
        for i in posiciones:
            for alt in voces:
                notas.append(F.Note(alt, 66, CORCHEA * 2 - 40, base + i * CORCHEA))
    return notas


def _melanc_tambora(g, compases, intensidad):
    """El **papa con yuca completo**, solo que flojo. Es el mismo genero.

    La primera version quitaba dos de los cinco golpes "para aligerar" y con eso
    dejaba de sonar a bambuco — Felipe lo detecto de oido en cuanto sono. Es la
    misma regla que ya estaba escrita tres modulos mas arriba y que se incumplio
    igual: **al bajar la intensidad se quitan capas, nunca se mueven ni se borran
    golpes de la celda**. Aligerar es bajar velocities.

    En las secciones desnudas desaparece entera, que si es quitar una capa: un
    bambuco caucano se sostiene solo con cuerdas.
    """
    if intensidad < 0.5:
        return []
    # Las mismas cinco posiciones que `_bambuco_tambora`, a ~70% de velocity.
    return [F.Note(nota, int(vel * 0.7), CORCHEA - 20,
                   _bar(c, g.beats) + i * CORCHEA)
            for c in range(compases)
            for i, nota, vel in ((0, TAMB_ALTO, 104), (1, TAMB_ALTO, 84),
                                 (2, TAMB_BAJO, 92), (3, TAMB_ALTO, 88),
                                 (4, TAMB_BAJO, 96))]


class BambucoMelancolico(Bambuco):
    nombre = "BAMBMELA"
    bpm = 68.0
    compases_por_acorde = 2
    # Mas movimiento armonico que las otras variantes, y con el sexto grado
    # menor: es de donde sale el color. Em - Am - C - B7.
    progresion = (
        ("Em", 40, [52, 55, 59]),
        ("Am", 45, [52, 57, 60]),
        ("C",  48, [52, 55, 60]),
        ("B7", 47, [51, 54, 59]),
    )
    pistas = (
        (0, "D1", "tambora, muy floja",   "Rock Kit", True,  _melanc_tambora),
        (3, "BA", "bajo fuera del tiempo", "Aco.Bass", False, _melanc_bajo),
        (4, "C1", "colchon continuo",     "NylonGtr", False, _melanc_tiple),
    )



# --- Currulao ------------------------------------------------------------
#
# **La celula mas limpia que se ha medido en este proyecto: 100%.** Sale de
# `bombo-golpeador-o-macho-currulao.mid`, 64 notas en 16 compases, y los
# dieciseis son identicos golpe por golpe. El torbellino daba 97 y el bambuco de
# salon 83.
#
#     corchea     1      2      3      4      5      6
#     golpe      ALTO    ·     ALTO   ALTO    ·     BAJO
#     altura     C#2           C#2    C#2           C2
#
# Tres golpes altos y **el grave en la sexta**, que es justo donde el bambuco de
# salon calla. Los dos generos reparten las mismas seis corcheas y se separan en
# esa nota: uno respira ahi y el otro apoya.
#
# **El currulao es 6/8 y no 3/4**, y esta vez la notacion coincide con la
# celula: las cinco partituras de currulao vienen en 6/8. El QY100 lo admite —el
# byte 14 codifica el denominador con 2 para /8— asi que se escribe como es.
#
# Lo melodico NO se genera: la marimba da 13% de repeticion y la guitarra 4%.
# Son arreglos, no celulas, igual que el porro y el chande. Aqui el motor pone la
# percusion y la armonia, y la marimba entra por el EP-40 desde la partitura o
# tocada en vivo.

BOMBO_ALTO, BOMBO_BAJO = 45, 41     # los mismos parches que la tambora del bambuco
GUASA = 82                          # sonaja: el shaker del kit XG
CURR_ALTO = (0, 2, 3)               # corcheas 1, 3 y 4
CURR_BAJO = 5                       # la sexta


def _currulao_bombo(g, compases, intensidad):
    """La celula medida, sin variar. Es la identidad del genero."""
    notas = []
    for c in range(compases):
        base = _bar(c, g.beats)
        for i in CURR_ALTO:
            notas.append(F.Note(BOMBO_ALTO, 100 if i == 0 else 88,
                                CORCHEA - 20, base + i * CORCHEA))
        notas.append(F.Note(BOMBO_BAJO, 108, CORCHEA - 20,
                            base + CURR_BAJO * CORCHEA))
    return notas


def _currulao_guasa(g, compases, intensidad):
    """Guasa en las seis corcheas; en las secciones flojas solo en las impares.

    Se quitan corcheas, **nunca se mueven las que quedan**: la rejilla es la del
    genero y desplazarla lo convierte en otra cosa.
    """
    paso = 1 if intensidad > 0.55 else 2
    return [F.Note(GUASA, 64 if i % 2 else 76, CORCHEA - 30,
                   _bar(c, g.beats) + i * CORCHEA)
            for c in range(compases) for i in range(0, 6, paso)]


def _currulao_bajo(g, compases, intensidad):
    """Fundamental en la 1 y quinta en la 4 — los dos apoyos de un 6/8."""
    notas = []
    for c in range(compases):
        _n, raiz, _v = g.acorde_de(c)
        base = _bar(c, g.beats)
        notas.append(F.Note(raiz, 112, CORCHEA * 2 - 20, base))
        notas.append(F.Note(raiz + 7, 96, CORCHEA * 2 - 20, base + 3 * CORCHEA))
    return notas


def _currulao_acordes(g, compases, intensidad):
    """Acorde en las corcheas 2 y 5, las que el bombo deja libres."""
    posiciones = (1, 4) if intensidad > 0.4 else (1,)
    notas = []
    for c in range(compases):
        _n, _r, voces = g.acorde_de(c)
        base = _bar(c, g.beats)
        for i in posiciones:
            for alt in voces:
                notas.append(F.Note(alt, 82, CORCHEA - 30, base + i * CORCHEA))
    return notas


class Currulao(Genero):
    nombre = "CURRULAO"
    bpm = 120.0
    beats = 3            # tres negras de duracion; la METRICA es 6/8
    denominador = 8
    compases_por_acorde = 2
    progresion = (
        ("Em", 40, [52, 55, 59]),
        ("Am", 45, [57, 60, 64]),
        ("Em", 40, [52, 55, 59]),
        ("B7", 47, [51, 54, 59]),
    )
    pistas = (
        (0, "D1", "bombo golpeador, celula medida", "Rock Kit", True,  _currulao_bombo),
        (2, "PC", "guasa",                          "Rock Kit", True,  _currulao_guasa),
        (3, "BA", "bajo en 1 y 4",                  "Aco.Bass", False, _currulao_bajo),
        (4, "C1", "acordes en 2 y 5",               "NylonGtr", False, _currulao_acordes),
    )


GENEROS = {
    "currulao": Currulao,"bambuco": Bambuco, "fiestero": BambucoFiestero,
           "pasillo": Pasillo, "pasillodenso": PasilloDenso,
           "torbellino": Torbellino, "guabina": Guabina,
           "melancolico": BambucoMelancolico}
