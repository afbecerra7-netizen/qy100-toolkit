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
    #: **De donde sale cada pista**: {indice: (marca, fuente, que aporta)}.
    #: Existe porque la mezcla silenciosa de fuentes es el error caro de este
    #: dominio: el bambuco tiene tres motores justo porque `te-ofrezco` y
    #: `brisas-del-pamplonita` traen patrones distintos, y fundirlos habria dado
    #: un bambuco que no existe en ninguna parte. Con la procedencia escrita,
    #: cuando aparece una fuente nueva se ve al instante que confirma y que
    #: contradice, sin releer comentarios.
    fuentes = {}
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

    def procedencia(self):
        """Filas (pista, marca, fuente, aporte) para las pistas documentadas.

        **Se niega a heredar el dict.** `BambucoFiestero` y `BambucoMelancolico`
        no declaraban el suyo, asi que salian por consola anunciando `[M]` sobre
        `te-ofrezco-mi-corazon-bambuco.mid` para pistas que no tocan lo que esa
        partitura dice: el fiestero pone el bajo en 1/3/5 y el melancolico en
        2/5, y la fila heredada describia 3 y 5. Una subclase que cambia lo que
        toca y no cambia su procedencia **miente con la voz del que la hereda**,
        que es justo lo que este dict existe para impedir.
        """
        propio = type(self).__dict__.get("fuentes")
        if propio is None and self.fuentes:
            heredado = ("[V]", "HEREDADO de %s — sin verificar para este genero"
                        % type(self).__mro__[1].__name__, "")
            return [(nom,) + heredado
                    for idx, nom, _p, _v, _b, _m in self.pistas]
        return [(nom, ) + self.fuentes.get(idx, ("[V]", "sin documentar", ""))
                for idx, nom, _p, _v, _b, _m in self.pistas]


# --- Bambuco -------------------------------------------------------------
#
# Sesquialtera: las mismas seis corcheas oidas a la vez como 3+3 (6/8) y como
# 2+2+2 (3/4). **No son dos compases superpuestos** —eso seria un desfase— sino
# un solo compas leido de dos maneras, que funciona porque 6/8 y 3/4 duran igual.
#
#     corchea    1   2   3   4   5   6
#     6/8        X           X          agrupacion 3+3
#     3/4        X       X       X      agrupacion 2+2+2
#
# **Las dos filas son agrupaciones metricas, no instrumentos**, y estuvieron
# rotuladas "percusion" y "tiple y bajo". Ninguno de los dos rotulos era cierto:
# la tambora ataca en 1, 2, 3, 4 y 5 —no en 1 y 4— y el tiple toca solo en 2 y 4,
# sin pisar una sola negra (`ACORDE_EN = (1, 3)`, "nunca en el tiempo fuerte").
# "Percusion en 1 y 4" es literalmente **la version equivocada nº 1** que este
# mismo fichero declara "coherente y falso" treinta lineas mas abajo, y estaba
# escrita arriba como si fuera el resumen bueno.
#
# El patron del tiple viene documentado con precision de corchea: chasquido,
# rasgueo, bajo, rasgueo, bajo, rasgueo. Los bajos caen en las corcheas 3 y 5,
# que en 3/4 son los tiempos 2 y 3 — o sea que **el tiple es la voz que cuenta en
# tres**, y es la que faltaba en las transcripciones de Tribe, donde marimba y
# tamboras agrupaban las dos en 3+3. **Quinta en la 3 y fundamental en la 5**, en
# ese orden y no al reves; aqui decia "fundamental... quinta" y se contradecia
# con la medicion de veinte lineas mas abajo.

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
# ## Tres versiones equivocadas antes de esta, y por que
#
# 1. **Bombo en 1 y 4**, deducido de la sesquialtera sobre el papel: los dos
#    grupos de `3+3` empiezan ahi. Coherente y falso.
# 2. **Bombo en 1, 3, 5 con acordes en 1, 3, 5 y bajo en 4 y 6**, sacado de los
#    grooves de Tribe. El problema es que aquello es un bambuco tocado con
#    **tambores caribeños** —una adaptacion— y no el andino. Una transcripcion
#    real de otro conjunto no es una transcripcion del genero.
# 3. **Acordes en 1, 3, 5 y bajo en 4 y 6**, de una descripcion en prosa
#    encontrada en internet. Es la que se le aplico al pasillo, y la que la
#    moraleja de abajo cuenta como tercera derrota — este encabezado decia
#    "dos" y enumeraba dos, mientras el documento publicado decia tres.
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
    fuentes = {
        0: ("[M]", "te-ofrezco-mi-corazon-bambuco.mid",
                   "la celula del papa con yuca, medida en los 31 compases"),
        2: ("[D]", "-", "guache continuo, deducido"),
        3: ("[M]", "te-ofrezco-mi-corazon-bambuco.mid",
                   "quinta en la corchea 3 y fundamental en la 5, en los 31 "
                   "compases"),
        4: ("[M]", "te-ofrezco-mi-corazon-bambuco.mid",
                   "acordes en las corcheas 2 y 4"),
    }
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
    #: **Propio, no heredado de `Bambuco`.** Estuvo heredado y por eso el
    #: fiestero anunciaba `[M]` de `te-ofrezco` en las tres pistas, incluidas
    #: dos que tocan otra cosa.
    fuentes = {
        0: ("[D]", "-", "la celda de tambora se traslada desde `te-ofrezco`; "
                        "es el mismo genero, pero no esta medida sobre `brisas`"),
        2: ("[D]", "-", "guache continuo, deducido"),
        3: ("[M]", "brisas-del-pamplonita-bambuco.mid",
                   "bajo en las corcheas 1, 3 y 5: 51, 51 y 65 ataques graves "
                   "contra 14, 12 y 12 en las contras. `[D]` el reparto "
                   "fundamental-quinta-fundamental: lo medido es el registro, "
                   "no la altura"),
        4: ("[M]", "brisas-del-pamplonita-bambuco.mid",
                   "acordes en las corcheas 2, 4 y 6, en alternancia estricta "
                   "con el bajo: sin huecos, que es lo que separa al fiestero "
                   "del de salon"),
    }


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
    fuentes = {
        3: ("[M]", "la-gata-goloza-fulgencio-garcia.mid",
                   "bajo en la corchea 1: 183 graves contra 71 acordes ahi. El "
                   "patron (1,4,5) se repite en 110 de 184 compases (60 %)"),
        4: ("[M]", "la-gata-goloza-fulgencio-garcia.mid",
                   "acordes en las corcheas 4 y 5: 104 y 110 ataques"),
        5: ("[V]", "-", "el requinto toca en 2, 3 y 6 — **las tres corcheas que "
                        "la celda medida deja vacias**. No sale de ninguna "
                        "fuente: es contracanto inventado"),
    }


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
    fuentes = {
        3: ("[M]", "vino-tinto-fulgencio-garcia.mid",
                   "el reparto de registro por corchea y la ausencia de acordes "
                   "—una nota a la vez, 1.0— en 126 compases. `[D]` los grados "
                   "concretos de `PASILLO_LINEA`: la medicion es de ocupacion y "
                   "registro, **no trae un solo intervalo**"),
        4: ("[M]", "vino-tinto-fulgencio-garcia.mid",
                   "acordes escasos; el 58 % de los compases ocupan las seis "
                   "corcheas"),
        5: ("[V]", "-", "requinto inventado, igual que en el pasillo de salon"),
    }


# --- Torbellino ----------------------------------------------------------
#
# Cundiboyacense. **"Tan tan tan taaaaan"**, y la clave es que eso se lee a
# caballo del compas: las tres cortas son el final de un compas y la larga es el
# tiempo fuerte del siguiente. Una anacrusa de tres golpes que aterriza.
#
#     corchea      1      2    3     4     5     6
#     bombo      TAAAAN   ·    ·     ·   tan     ·        97% de los compases
#     caja       TAAN     ·    ·    tan  tan   tan        58%
#                 ^ aterriza aqui   ^^^^^^^^^^^^^^ empuja hacia el siguiente
#
# Medido en `suite-colombiana-torbellino-micontrabajo.mid`: el bombo hace
# `c0 durando 4 corcheas, c4 durando 2`: por POSICIONES son 96 de 99 compases
# (97 %) y con las duraciones exactas 95 (96 %). Las dos cifras son de la
# FUENTE — **el motor no toca esa figura**: dobla `TORB_CELDA` en las tres
# negras. El parentesis correctivo que hubo aqui ("la cifra estuvo como 96 %,
# que es el recuento leido como porcentaje") era el mismo falso: 96 % siempre
# fue el porcentaje correcto de la figura CON duraciones. Y la caja
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
#: `c0:2 c2:2 c4:2` (tres negras) con `c0:6` (una larga). **El rango real,
#: medido atril a atril el 2026-08-12, es del 5 % al 37 %** — no "26 a 37":
#: violin 1 da 5 %, flauta 16 %, y solo trompeta, trombon, viola y chelo pasan
#: del 30 %. Flauta y oboe tienen como figura MAS frecuente `[1,5]`, la del
#: bombo. "Los melodicos atacan en las tres negras" generalizaba de mas
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
    #: Reescrito 2026-08-12 tras auditarlo: dos filas llevaban `[M]` afirmando
    #: lo contrario de lo que dice el fichero que citaban. El error de fondo:
    #: **marcar EL MOTOR con la marca de LA FUENTE.** Lo que el motor toca es
    #: diseno; lo que la fuente toca es medicion; cada cosa con su marca.
    fuentes = {
        0: ("[D]", "-",
            "bombo doblando `TORB_CELDA`: par 1/3/5, impar solo la 1. `[M]` La "
            "fuente ('Bombo 1') toca OTRA figura: `[1,5]` en 96 de 99 compases "
            "(97 %), con duraciones 4+2 corcheas en 95 (96 %). El motor no la "
            "reproduce, y esta fila lo contaba al reves"),
        1: ("[D]", "-",
            "caja `tan tan tan` en 4, 5 y 6. `[M]` La fuente ('Caja clara') da "
            "`[1,4,5,6]` en 62 de 107 compases (58 %): trae el golpe de la "
            "corchea 1 que este motor omite"),
        2: ("[D]", "-", "chucho continuo, deducido"),
        3: ("[D]", "-",
            "bajo doblando `TORB_CELDA` en las tres negras — por diseno, para "
            "llevar la armonia. `[M]` La fuente ('Contrabajo') cae en `[1,5]` "
            "—la celula del bombo— en 46 de 89 compases (52 %), y en las tres "
            "negras solo 12 (13 %). **La equivalencia bombo/bajo que esta fila "
            "negaba es cierta en la fuente**; el que toca 1/3/5 es el motor"),
        4: ("[D]", "-",
            "acordes en las tres negras. `[V]` El arreglo es orquestal y no "
            "tiene instrumento de acordes; la celda `[1,3,5]` va del 5 % "
            "(violin 1) al 37 % (trombon) segun el atril, y **la figura mas "
            "frecuente de flauta y oboe es `[1,5]`**, la del bombo. Solo la "
            "trompeta la lleva como figura principal (30 %)"),
    }


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
# **La equivalencia con el torbellino era falsa, y era el unico aval que tenia
# esta colocacion.** Decia "el bajo cae en 1 y 5 igual que en el torbellino", y
# el bajo del MOTOR del torbellino cae en las tres negras —por diseno— pero el
# contrabajo de su FUENTE cae en [1,5] el 52 % (medido 2026-08-12), no en
# 5: sale de `TORB_CELDA`, la misma de la que salen sus acordes, y el propio
# parrafo lo desmentia dos lineas mas abajo al decir que el torbellino pone los
# acordes en los tres negros. Lo que el torbellino si tiene medido en 1 y 5 es
# **el bombo**, no el bajo (`c0` durando 4 corcheas y `c4` durando 2, en el 97 %
# de sus 99 compases). Confundir el bombo con el bajo y usar la confusion como
# respaldo de otro genero es exactamente la mezcla silenciosa de fuentes que
# `fuentes` existe para impedir.
#
# `[D]` Asi que el bajo de la guabina en 1 y 5 **no esta medido**: es criterio,
# elegido para que el tiple conteste en las contras. Lo que separa los dos
# generos —el torbellino contestando en los tres negros y la guabina en las
# contras— sigue en pie; lo que se cae es el "mismo esqueleto".
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
    #: Este genero es el que menos respaldo tiene, y estuvo saliendo entero como
    #: `[V] sin documentar` por no declarar nada — que era honesto por omision,
    #: no por diseno.
    fuentes = {
        0: ("[D]", "-", "tambora doblando las dos capas con timbres distintos"),
        2: ("[D]", "-", "chucho continuo, deducido"),
        3: ("[D]", "-", "bajo en las corcheas 1 y 5. **Criterio, no medicion**: "
                        "el unico aval que tuvo fue una equivalencia falsa con "
                        "el torbellino, cuyo bajo va en las tres negras"),
        4: ("[D]", "-", "acordes en 3 y 6, elegidos para contestar detras de "
                        "cada bajo sin pisarlo"),
    }


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
# **Las tres salen del Mejia**, no de `y-un-cafe`, y no lo decia. Se comprobo
# recontando los graves por corchea en las dos: el Mejia da el valle en la 1 y
# el pico en la 2, y `y-un-cafe` tiene el pico justamente en la 1. Citar "las
# dos partituras" y luego dar una cifra de una sola es como se pierde el rastro
# de una medicion.
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
    #: **Propio, no heredado.** Heredaba el de `Bambuco` y salia anunciando
    #: `[M]` de `te-ofrezco` con el bajo "en la corchea 3 y la 5" — y este
    #: motor lo pone en la 2 y la 5. Aqui la marca tiene que ser mas floja que
    #: en las otras dos variantes, y el bloque de arriba ya lo decia con todas
    #: las letras: **"No hay celda que extraer"** y "el reparto concreto de las
    #: corcheas es criterio, no medicion". El dict decia lo contrario.
    fuentes = {
        0: ("[D]", "-", "tambora trasladada desde `te-ofrezco`, muy floja; no "
                        "hay percusion medida en las fuentes caucanas"),
        3: ("[M]", "bambuco-no-1-en-si-menor-adolfo-mejia-navarro.mid",
                   "el bajo rehuye el tiempo fuerte: 19 ataques en la corchea 1 "
                   "contra 113 en la 2. `[D]` que caiga en 2 y 5 en concreto — "
                   "lo medido es que evita la 1, no donde se posa"),
        4: ("[D]", "-", "colchon casi continuo: las seis corcheas en el 37 % de "
                        "los compases del Mejia, pero con 30 % y 37 % de "
                        "consistencia **no hay celda que extraer**; el reparto "
                        "es criterio"),
    }



# --- Currulao ------------------------------------------------------------
#
# **La celula mas limpia que se ha medido en este proyecto: 100%.** Sale de
# `bombo-golpeador-o-macho-currulao.mid`, 64 notas en 16 compases, y los
# dieciseis son identicos golpe por golpe. El torbellino daba 97 y el bambuco de
# salon 83.
#
#     corchea     1      2      3      4      5      6
#     silaba     Con           laor   ques          ta        (y luego de-le-du-ro)
#     mano       IZQ           IZQ    IZQ           DER
#     golpe     madera        madera madera        cuero
#     altura     C#2           C#2    C#2           C2
#
# **"Con la orquesta dele duro"** es su onomatopeya, como el *papa con yuca* del
# bambuco: ocho silabas sobre dos compases de cuatro golpes. El reparto de
# silabas por corchea es `[D]`, deducido del texto bajo el pentagrama; los
# golpes y las alturas son `[M]`.
#
# `[M]` **Las dos alturas son dos superficies, no dos parches**: la partitura
# dice que la izquierda golpea la madera (cabezas en X) y la derecha el cuero.
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

# **No son parche agudo y grave: son dos superficies.** La partitura lo dice
# expreso — *"la mano izquierda toca en la madera la X y la derecha el cuero del
# bombo"*. Las tres X son madera y el golpe restante es el parche.
#
# El transcriptor lo escribio con semantica GM y por eso el MIDI ya lo traia:
# `C#2 = 37` es el **side stick**, el golpe seco en el aro, y `C2 = 36` es el
# **bombo**. Mapearlo a dos toms —que fue el primer intento— borra justo lo que
# distingue el golpe: uno es madera seca y el otro es cuero.
MADERA, CUERO = 37, 36
GUASA = 82                          # sonaja: el shaker del kit XG
CURR_ALTO = (0, 2, 3)               # corcheas 1, 3 y 4
CURR_BAJO = 5                       # la sexta


def _currulao_bombo(g, compases, intensidad):
    """La celula medida. El ultimo golpe es MADERA y CUERO **a la vez**.

    Lo dice la cartilla del Pacifico Sur al describir la base 1: *"la ultima
    silaba coincide con el golpe simultaneo ABIERTO-MADERA"*, y el pictograma lo
    dibuja con un icono distinto de los otros tres. Antes se escribia solo el
    cuero, que es la mitad del golpe.
    """
    notas = []
    for c in range(compases):
        base = _bar(c, g.beats)
        for i in CURR_ALTO:
            notas.append(F.Note(MADERA, 100 if i == 0 else 88,
                                CORCHEA - 20, base + i * CORCHEA))
        t = base + CURR_BAJO * CORCHEA
        notas.append(F.Note(CUERO,  108, CORCHEA - 20, t))
        notas.append(F.Note(MADERA,  92, CORCHEA - 20, t))   # simultaneo
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
    fuentes = {
        0: ("[M]", "bombo-golpeador-o-macho-currulao.mid (Javier Martinez / "
                   "Wilmer Vente)",
                   "la celula: 64 notas en 16 compases, 100% identicas. **Son "
                   "CUATRO golpes** — madera en las corcheas 1, 3 y 4 y cuero "
                   "en la 6; no hay madera en la 6. Las cabezas en X son madera "
                   "y la nota normal es cuero, segun la propia partitura y la "
                   "clave de `Pitos y tambores`"),
        # El motor escribe CINCO: anade madera simultanea sobre el cuero de la
        # corchea 6. Eso **no sale de la partitura** sino de la otra cartilla, y
        # es una mezcla de fuentes en el punto exacto donde estan declaradas en
        # desacuerdo (ver el `[V]` del acento, abajo). Sin esta entrada, el
        # quinto golpe salia amparado por el `[M]` de arriba.
        "0-simultaneo": (
            "[D]", "¡Que te pasa vo! (Pacifico Sur), grafico 17",
            "el ultimo golpe es ABIERTO-MADERA simultaneo. La cartilla lo situa "
            "en la 5a corchea y aqui se escribe en la 6a, que es donde lo pone "
            "la partitura: la discrepancia sigue abierta"),
        2: ("[D]", "-", "guasa continua, deducida. La cartilla del Pacifico Sur "
                        "la nombra pero no se ha transcrito su patron"),
        3: ("[D]", "-", "bajo en 1 y 4, deducido de los dos pulsos del 6/8"),
        4: ("[D]", "-", "acordes en 2 y 5, elegidos por no pisar al bombo"),
    }
    #: `[V]` **Falta la variacion.** La cartilla `¡Que te pasa vo!` dice que el
    #: ciclo son cuatro compases —tres bases mas una variacion— y esta fuente
    #: trae solo la base repetida, por ser material de estudio. Este motor toca
    #: la base sola: correcto pero incompleto.
    #:
    #: Las dos fuentes NO se contradicen en la onomatopeya, aunque lo parezca:
    #: la partitura dice "Con la orquesta dele duro" (8 silabas, 2 compases) y la
    #: cartilla "Dele duro" (4 silabas, 1 compas). La segunda es la cola de la
    #: primera — la misma celula nombrada a dos escalas.
    # "Con la orquesta dele duro"
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


# --- Mapale --------------------------------------------------------------
#
# De `mapale-ashcolom.mid` (piano a dos manos, 4/4 a 100).
#
# `[M]` **El genero es 6/8 y su celda es un "tres contra dos".** Cinco fuentes
# independientes, ninguna en contra:
#
#     metodo de bateria `MAPALE.pdf`   6/8, y **rotula la celda "Tres contra
#                                      dos"** en su tercer ejercicio
#     `PRENDE LA VELA`, Lucho Bermudez 6/8 en las seis partes de la banda
#     Felipe                           2/2 — la misma estructura, otra notacion:
#                                      dos tiempos por compas partidos en tres
#     grabacion a 150, medida          subdivision ternaria; **las tres
#                                      posiciones binarias son los tres puntos
#                                      mas vacios del ciclo** (5, 3 y 3 contra
#                                      26 y 17 en los tercios)
#     transcripcion para piano         ataques en las corcheas 1, 3 y 5
#
# El compas mide 6 corcheas y los golpes caen en la **1, la 3 y la 5**: tres
# ataques equidistantes cruzandose contra los dos tiempos de negra con puntillo.
# Eso es el "tres contra dos", y es lo que hace correr al genero.
#
# **Estuvo escrito como 4/4 con celda "3+2+3 en semicorcheas", y era doblemente
# falso.** La transcripcion para piano de la que salio esta escrita a mitad de
# tiempo en 4/4, asi que cada "medio compas" suyo de 960 relojes es en realidad
# un compas entero de 6/8; y dentro de el, 320 y 640 no caen en la rejilla de
# semicorchea, de modo que al forzarlos a ella salian 360 y 600. El motor tocaba
# el tresillo aplanado contra una rejilla binaria.
#
# El orden en que el metodo lo ensena dice algo que ninguna otra fuente daba:
# tom, aro, **tres contra dos**, y solo entonces "incluimos bombo en el tiempo
# 1". **El bombo no es la base del mapale: es lo ultimo que se anade.**
#
#     relojes desde el inicio del medio compas
#       0    320    480    640
#     142    120     10    120     <- ataques
#
# **Estuvo escrito como «3+2+3 en semicorcheas», y era el redondeo.** 320 y 640
# no caen en la rejilla de semicorchea (120): al llevarlos a ella salen 360 y
# 600, que es lo que tocaba este motor. El segundo golpe llegaba 40 relojes
# tarde y el tercero 40 pronto — 50 ms a 100 bpm, con el tresillo aplanado
# contra una rejilla binaria. La cifra de ataques (142/120/10/120) siempre fue
# correcta; **la columna en la que se imprimio, no**. `CLOCKS_PER_QUARTER` son
# 480, asi que 320 y 640 son exactos en el QY100 y no habia nada que redondear.
#
# `[M]` **Cada nota dura su tercio entero**: 319 relojes en 372 de los 392
# ataques. No es un picado sobre una rejilla, es legato de tresillo.
#
# `[M]` **El apoyo se acentua poco**: velocity 85 de media en el golpe 1 (80-96)
# y 80 exactos en los otros dos. El contraste 108/92 que se usaba aqui no sale
# de la fuente.
#
# Y las alturas dicen algo que el recuento por si solo no ve:
#
#     compas 71   sc1 D3   sc4 D4   sc6 D3
#     compas 72   sc1 D4   sc4 D3   sc6 D4
#
# **La octava alterna en cada golpe.** Como son tres por compas, el ciclo se
# invierte al compas siguiente y vuelve al tercero. No es un pedal quieto sino
# una oscilacion de octava sobre una rejilla fija.
#
# `[M]` La armonia casi no se mueve: 126 compases sobre Re, 14 sobre Fa y uno
# sobre La, con 29 cambios en 141 compases. Es un genero de ostinato.
#
# `[V]` **El tempo no cuadra entre fuentes.** La partitura va a 100 en 4/4, el
# plan del directo dice 202,7 y el catalogo de Tribe da 180 en 2/2. Lo mas
# probable es que la partitura este escrita a mitad de tiempo —100 x 2 = 200, muy
# cerca de 202,7— pero no esta comprobado. Aqui se usa el de la partitura.
#
# `[V]` **La percusion no esta en esta fuente**: es una transcripcion para piano.
# Lo medido es la celda y la armonia, no los tambores, que en este genero son la
# mitad del asunto.

#: Las corcheas del 6/8 donde cae el "tres contra dos": la 1, la 3 y la 5.
#: Se guardan como indices de corchea y no como relojes, porque **el marco
#: metrico es lo que estuvo mal** y en indices se ve: 1, 3 y 5 de seis.
#: **La celda binaria: semicorcheas 1, 4 y 6 de cada medio compas**, o sea
#: huecos de 3+2+3. `[V]` Es la que suena bien —Felipe la valido de oido y
#: rechazo la ternaria por groove— pero **su procedencia es un artefacto**: se
#: obtuvo leyendo `mapale-ashcolom.mid`, que esta cuantizado a tercios, sobre
#: una rejilla de semicorchea. La medicion de la que salio dice otra cosa.
#: Se conserva porque el oido manda sobre el papel, y se marca `[V]` porque no
#: hay ninguna fuente binaria que la sostenga. Si aparece una, sube a `[M]`.
MAPALE_CELDA = (0, 3, 5)
#: Las corcheas del 6/8 del `MapaleTernario`: la 1, la 3 y la 5.
MAPALE_CORCHEAS = (0, 2, 4)
#: `[M]` velocity 85 de media en el apoyo y 80 exactos en los otros dos golpes,
#: medido sobre la transcripcion para piano.
MAPALE_VEL = (85, 80, 80)


def _mapale_ostinato(g, compases, intensidad):
    """La oscilacion de octava sobre la celda binaria de 3+2+3."""
    notas, golpe = [], 0
    for c in range(compases):
        _n, raiz, _v = g.acorde_de(c)
        base = _bar(c, g.beats)
        for mitad in range(g.beats // 2):
            for k, i in enumerate(MAPALE_CELDA):
                notas.append(F.Note(raiz + (12 if golpe % 2 else 0),
                                    MAPALE_VEL[k], SEMI * 2 - 10,
                                    base + mitad * 2 * NEGRA + i * SEMI))
                golpe += 1
    return notas


def _mapale_ternario_ostinato(g, compases, intensidad):
    """Lo mismo sobre el «tres contra dos» del 6/8: corcheas 1, 3 y 5."""
    notas = []
    for c in range(compases):
        _n, raiz, _v = g.acorde_de(c)
        base = _bar(c, g.beats)
        for k, i in enumerate(MAPALE_CORCHEAS):
            # Cada nota llena hasta la siguiente: 319 de 320 en la fuente.
            notas.append(F.Note(raiz + (12 if (c * 3 + k) % 2 else 0),
                                MAPALE_VEL[k], CORCHEA * 2 - 1,
                                base + i * CORCHEA))
    return notas


def _mapale_bombo(g, compases, intensidad):
    """Bombo en la misma celda; en las secciones flojas solo en el apoyo.

    `[V]` **El metodo de bateria lo contradice.** Ensena el patron por capas —
    tom, aro, tres contra dos— y solo al final dice "incluimos bombo en el
    tiempo 1": el bombo entra ahi, no doblando la celda entera. Esto se deja
    como esta hasta leer la partitura con cuidado, pero **queda marcado como
    contradicho, no como deducido**.
    """
    posiciones = MAPALE_CELDA if intensidad > 0.5 else (0,)
    return [F.Note(CUERO, 112 if i == 0 else 96, SEMI,
                   _bar(c, g.beats) + mitad * 2 * NEGRA + i * SEMI)
            for c in range(compases) for mitad in range(g.beats // 2)
            for i in posiciones]


def _mapale_ternario_bombo(g, compases, intensidad):
    """Bombo sobre el tres contra dos.

    `[V]` **El metodo de bateria lo contradice.** Ensena el patron por capas —
    tom, aro, tres contra dos— y solo al final dice "incluimos bombo en el
    tiempo 1": el bombo entra ahi, no doblando la celda entera.
    """
    posiciones = MAPALE_CORCHEAS if intensidad > 0.5 else (0,)
    return [F.Note(CUERO, 112 if i == 0 else 96, SEMI,
                   _bar(c, g.beats) + i * CORCHEA)
            for c in range(compases) for i in posiciones]


def _mapale_guasa(g, compases, intensidad):
    """Sonaja continua: el colchon que hace correr el genero."""
    paso = 1 if intensidad > 0.6 else 2
    return [F.Note(GUASA, 70 if i % 4 else 84, SEMI - 10,
                   _bar(c, g.beats) + i * SEMI)
            for c in range(compases) for i in range(0, g.beats * 4, paso)]


class Mapale(Genero):
    """El mapale binario. **Es el que suena**, validado de oido.

    Felipe oyo la version ternaria en el equipo y la rechazo por groove. Eso
    manda: es lo unico que oye, y el resto son papeles.
    """

    nombre = "MAPALE"
    fuentes = {
        0: ("[D]", "-", "bombo sobre la misma celda del ostinato, deducido"),
        2: ("[D]", "-", "sonaja continua, deducida"),
        3: ("[V]", "validado de oido por Felipe; sin fuente que lo sostenga",
                   "la celda 3+2+3 en semicorcheas y la alternancia de octava. "
                   "**La celda salio de leer `mapale-ashcolom.mid` sobre una "
                   "rejilla binaria, y ese fichero esta cuantizado a tercios**: "
                   "su procedencia documentada es un artefacto de lectura. El "
                   "loop de Tribe se inclina binario pero no decide (74 % contra "
                   "69 %). Sube a `[M]` en cuanto aparezca una fuente binaria"),
    }
    bpm = 100.0
    beats = 4
    compases_por_acorde = 8      # casi no se mueve: 29 cambios en 141 compases
    progresion = (
        ("Dm", 50, [50, 53, 57]),
        ("Dm", 50, [50, 53, 57]),
        ("F",  53, [53, 57, 60]),
        ("Dm", 50, [50, 53, 57]),
    )
    pistas = (
        (0, "D1", "bombo en la celda",      "Rock Kit", True,  _mapale_bombo),
        (2, "PC", "sonaja en semicorcheas", "Rock Kit", True,  _mapale_guasa),
        (3, "BA", "ostinato de octavas",    "Aco.Bass", False, _mapale_ostinato),
    )


class MapaleTernario(Mapale):
    """El mapale de banda, en 6/8. **No es el mismo groove que `Mapale`.**

    Existe por la misma razon que el bambuco tiene tres motores: dos fuentes
    traen patrones distintos y fundirlos daria un mapale que no existe en
    ninguna parte. Aqui la diferencia es de cuatro por ciento del ciclo —el
    golpe de en medio al 33,3 % en vez de al 37,5 %— y **es todo el groove**.

    Se escribio primero como si fuera EL mapale, sustituyendo al binario. Sonaba
    mal, y el error no fue de medicion sino de alcance: **una medicion correcta
    sobre una fuente no autoriza a cambiar lo que otra fuente sostiene.**
    """

    nombre = "MAPALTER"
    fuentes = {
        0: ("[V]", "MAPALE.pdf (metodo de bateria)",
                   "el metodo ensena el patron por capas y mete el bombo AL "
                   "FINAL, solo en el tiempo 1 — aqui dobla la celda entera, "
                   "que es lo contrario de como se ensena"),
        2: ("[D]", "-", "sonaja continua, deducida"),
        3: ("[M]", "MAPALE.pdf (metodo de bateria) + PRENDE LA VELA (Lucho "
                   "Bermudez) + mapale-ashcolom.mid + grabacion medida",
                   "el «tres contra dos» en 6/8: golpes en las corcheas 1, 3 y "
                   "5. El metodo **rotula la celda con ese nombre**; la "
                   "partitura de banda confirma el 6/8; la grabacion da "
                   "subdivision ternaria —las tres posiciones binarias son los "
                   "puntos mas vacios del ciclo— y la transcripcion para piano "
                   "da las tres posiciones exactas en 382 de 392 ataques (los "
                   "10 restantes, exactos tambien, caen en el reloj 480) "
                   "ataques"),
    }
    #: `[V]` La grabacion da el compas en 0,80 s, lo que pondria la negra en 225.
    #: Pero de la autocorrelacion **no se pudo establecer cual periodicidad era
    #: el compas y cual el tiempo**, asi que este numero no esta medido: esta
    #: derivado de una eleccion que no se verifico.
    bpm = 225.0
    beats = 3            # tres negras de duracion; la METRICA es 6/8
    denominador = 8
    pistas = (
        (0, "D1", "bombo en la celda",      "Rock Kit", True,  _mapale_ternario_bombo),
        (2, "PC", "sonaja en semicorcheas", "Rock Kit", True,  _mapale_guasa),
        (3, "BA", "ostinato de octavas",    "Aco.Bass", False, _mapale_ternario_ostinato),
    )


# --- Cumbia --------------------------------------------------------------
#
# `[M]` De **`Pitos y tambores`, la cartilla de iniciacion musical de Victoriano
# Valencia** (Plan Nacional de Musica para la Convivencia, Ministerio de
# Cultura). Fuente pedagogica primaria, no una transcripcion suelta.
#
# La cartilla formaliza lo que este proyecto venia haciendo sin saber que tenia
# nombre: la **matriz metrica**, binaria de ocho eventos o ternaria de seis. Las
# tablas de ataques por corchea que se han ido midiendo *son* esa matriz — la
# ternaria para el bambuco y el currulao, la binaria para el mapale y el chande.
#
# La base de cumbia, con las alineaciones que da la cartilla:
#
#     matriz binaria    1   2   3   4   5   6   7   8
#     palmas (pulso)    X               X
#     llamador                  X               X        contratiempo
#     guacho            X       X       X       X
#     alegre            X   X   X   X   X   X   X   X    "reproduce la matriz"
#
# El alegre tocando los ocho eventos es lo que la cartilla llama el patron
# basico de cumbia **tipo soledeña**. La tambora necesita "matriz doble" —
# dieciseis eventos— y no se implementa aqui: sus variaciones ocupan una pagina
# entera de la cartilla y merecen medirse aparte.
#
# `[D]` **El bajo no viene en la cartilla**, que es material de percusion. El que
# hay aqui es una linea sencilla en el pulso, deducida, no medida.

CUM_LLAMADOR = (2, 6)              # contratiempo
CUM_GUACHO = (0, 2, 4, 6)
CUM_PULSO = (0, 4)


def _cumbia_llamador(g, compases, intensidad):
    """El contratiempo: eventos 3 y 7 de la matriz binaria.

    `[M]` La cartilla situa ahi el llamador de la cumbia. `[V]` **Pero no es lo
    que la distingue**: `Pitos y tambores` aplica el mismo contratiempo binario
    al "llamador de cumbia, gaita, porro, chalupa, son corrido, puya sabanera"
    —seis ritmos—, y da la clave de cumbia tambien al bullerengue, al porro
    palitiao y a la gaita. Lo que la fuente sostiene es la posicion, no la
    identidad. Aqui estuvo escrito "es lo que hace que una cumbia sea una
    cumbia", que es mas de lo que dice la cartilla.
    """
    return [F.Note(MADERA, 104, SEMI, _bar(c, g.beats) + i * SEMI)
            for c in range(compases) for i in CUM_LLAMADOR]


def _cumbia_alegre(g, compases, intensidad):
    """Los ocho eventos de la matriz; en secciones flojas, solo la mitad."""
    pasos = range(8) if intensidad > 0.5 else CUM_GUACHO
    return [F.Note(TAMB_ALTO, 96 if i in CUM_PULSO else 74, SEMI - 10,
                   _bar(c, g.beats) + i * SEMI)
            for c in range(compases) for i in pasos]


def _cumbia_guacho(g, compases, intensidad):
    return [F.Note(GUASA, 84 if i in CUM_PULSO else 68, SEMI - 10,
                   _bar(c, g.beats) + i * SEMI)
            for c in range(compases) for i in CUM_GUACHO]


def _cumbia_bajo(g, compases, intensidad):
    """`[D]` En el pulso. La cartilla es de percusion y no trae bajo."""
    notas = []
    for c in range(compases):
        _n, raiz, _v = g.acorde_de(c)
        base = _bar(c, g.beats)
        for k, i in enumerate(CUM_PULSO):
            notas.append(F.Note(raiz if k == 0 else raiz + 7, 108 if k == 0 else 92,
                                SEMI * 3, base + i * SEMI))
    return notas


class Cumbia(Genero):
    nombre = "CUMBIA"
    fuentes = {
        0: ("[M]", "Pitos y tambores (V. Valencia, Plan Nacional de Musica)",
                   "llamador a contratiempo: eventos 3 y 7 de la matriz binaria"),
        1: ("[M]", "Pitos y tambores",
                   "el alegre 'reproduce la matriz metrica binaria' — los ocho "
                   "eventos, patron basico tipo soledeña"),
        2: ("[M]", "Pitos y tambores", "guacho en 1, 3, 5 y 7"),
        3: ("[D]", "-", "bajo en el pulso. La cartilla es de percusion y no "
                        "trae bajo"),
    }
    bpm = 96.0
    beats = 2                    # la matriz binaria son 8 semicorcheas de 2/4
    compases_por_acorde = 4
    progresion = (
        ("Am", 45, [57, 60, 64]),
        ("Am", 45, [57, 60, 64]),
        ("E7", 40, [56, 59, 64]),
        ("Am", 45, [57, 60, 64]),
    )
    pistas = (
        (0, "D1", "llamador: el contratiempo", "Rock Kit", True,  _cumbia_llamador),
        (1, "D2", "alegre: la matriz entera",  "Rock Kit", True,  _cumbia_alegre),
        (2, "PC", "guacho",                    "Rock Kit", True,  _cumbia_guacho),
        (3, "BA", "bajo en el pulso [D]",      "Aco.Bass", False, _cumbia_bajo),
    )


#: Los generos disponibles. **El modulo se llama `andina` y ya no todos lo son**:
#: el currulao es del Pacifico y el mapale del Caribe. Comparten el armazon —seis
#: secciones, celda medida, progresion escrita dentro— pero el nombre pide un
#: cambio. Pendiente.
GENEROS = {
    "bambuco":      Bambuco,
    "fiestero":     BambucoFiestero,
    "melancolico":  BambucoMelancolico,
    "pasillo":      Pasillo,
    "pasillodenso": PasilloDenso,
    "torbellino":   Torbellino,
    "guabina":      Guabina,
    "currulao":     Currulao,
    "mapale":       Mapale,
    #: El ternario va aparte y NO sustituye al binario. Mismo motivo que
    #: los tres bambucos: dos fuentes, dos patrones, y fundirlos daria uno
    #: que no existe en ninguna parte.
    "mapaleternario": MapaleTernario,
    "cumbia":       Cumbia,
}
