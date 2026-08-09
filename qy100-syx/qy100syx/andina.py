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

# El patron base de la tambora andina se llama **"papa con yuca"**, y es la
# identidad ritmica del genero: sin el, lo demas puede estar bien y no sonar a
# bambuco. Felipe lo señalo oyendo la primera version.
#
# La celda **no se dedujo de la teoria, se extrajo de una transcripcion real** —
# los grooves del Colombia Bundle de Tribe, doblando los ataques por compas de
# seis corcheas e instrumento por instrumento:
#
#                    1    2    3    4    5    6
#     Bombo Open    78    .   89    .  113    .
#     Bombo Cascara 98    .    .   89    .    .
#     Tamb Cascara  68    .   35   76    .    .
#     Tamb Damped    .    .   73    .    .    .
#     Tamb Open      .    .    .    .   98    .
#     Llamador      93    .   88   88    .   86
#     Alegre         .    .   77   84   87    .
#     Maracon      105    .    .  109    .    .
#
# Dos cosas que la version anterior tenia mal y que ninguna lectura del manual
# habria corregido:
#
# - **El bombo va en 1, 3 y 5**, no en 1 y 4. Poner 1 y 4 es lo que sale de
#   razonar la sesquialtera sobre el papel (3+3 contra 2+2+2) y suena plausible,
#   pero no es lo que se toca.
# - **El acento fuerte esta en la corchea 5**, con la velocity mas alta de todo
#   el patron (113). El tiempo fuerte del compas lleva 78. Un patron generado
#   pone el acento en el 1 por defecto, y ahi se pierde el genero entero.
#
# **La corchea 2 esta vacia en los once instrumentos.** Ese silencio es
# estructural, no una ausencia de datos.
#
# Los ataques caen en 1, 3, 4, 5 y 6 — cinco posiciones para las cinco silabas
# de "pa-pa con yu-ca", con los fuertes en 1 y 5.
BOMBO, BOMBO_CASC = 36, 37
TAMB_CASC, TAMB_DAMP, TAMB_OPEN = 77, 41, 45
LLAM_AB, LLAM_BAJ = 61, 60
ALEG_BAJ, ALEG_AB = 64, 63
MARACON, GUACHE = 70, 69

#: (corchea, nota, velocity) por capa. Copiado de la transcripcion.
PAPA_BOMBO = [(0, BOMBO, 78), (2, BOMBO, 89), (4, BOMBO, 113),
              (0, BOMBO_CASC, 98), (3, BOMBO_CASC, 89)]
PAPA_TAMBORA = [(0, TAMB_CASC, 68), (2, TAMB_CASC, 35), (3, TAMB_CASC, 76),
                (2, TAMB_DAMP, 73), (4, TAMB_OPEN, 98)]
PAPA_MANO = [(0, LLAM_AB, 93), (3, LLAM_AB, 88), (2, LLAM_BAJ, 88),
             (5, LLAM_BAJ, 86), (2, ALEG_BAJ, 77), (3, ALEG_AB, 84),
             (4, ALEG_AB, 87)]
PAPA_SONAJA = [(0, MARACON, 105), (3, MARACON, 109),
               (0, GUACHE, 103), (3, GUACHE, 108)]


def _celda(g, compases, capas):
    return [F.Note(nota, vel, CORCHEA - 20, _bar(c, g.beats) + i * CORCHEA)
            for c in range(compases) for capa in capas for i, nota, vel in capa]


def _bambuco_bombo(g, compases, intensidad):
    """Bombo y su cascara. La capa que lleva el "papa con yuca"."""
    capas = [PAPA_BOMBO]
    if intensidad < 0.4:
        # En las secciones desnudas se quitan capas, **nunca se mueven golpes**:
        # la celda es la identidad del genero y desplazarla la destruye.
        capas = [[x for x in PAPA_BOMBO if x[1] == BOMBO]]
    return _celda(g, compases, capas)


def _bambuco_tambora(g, compases, intensidad):
    if intensidad < 0.45:
        return []
    return _celda(g, compases, [PAPA_TAMBORA])


def _bambuco_manos(g, compases, intensidad):
    """Llamador, alegre y sonajas: el relleno de manos."""
    capas = [PAPA_SONAJA]
    if intensidad > 0.5:
        capas.append(PAPA_MANO)
    return _celda(g, compases, capas)


# El reparto armonico va **encima de la misma celda**, y lo dio Felipe cantandolo:
#
#     corchea    1       2     3       4      5       6
#     silaba     PA      ·     PA      CON    YU      CA
#                acorde        acorde  bajo   acorde  bajo
#
# Los acordes caen en 1, 3 y 5 —los tres negros del 3/4— y el bajo en 4 y 6,
# entre medias. **El acompanamiento marca el pulso ternario y el bajo sincopa
# contra el**: la sesquialtera repartida entre instrumentos, no deducida.
#
# La version anterior tenia justo lo contrario —bajos del tiple en 3 y 5,
# rasgueos en 2, 4 y 6— porque se construyo desde una descripcion en prosa del
# rasgueo ("chasquido, rasgueo, bajo, rasgueo, bajo, rasgueo") sin comprobar
# contra nadie que lo tocara. La descripcion era de otro patron.

ACORDE_EN = (0, 2, 4)      # corcheas 1, 3 y 5
BAJO_EN = (3, 5)           # corcheas 4 y 6


def _bambuco_bajo(g, compases, intensidad):
    """Fundamental en CON, quinta en CA. Nunca en el tiempo.

    Que el bajo **no toque en el 1** es el rasgo: si lo hace se alinea con el
    acorde y con el bombo, y el entrelazado desaparece.
    """
    notas = []
    for c in range(compases):
        _n, raiz, _v = g.acorde_de(c)
        base = _bar(c, g.beats)
        for i, alt in zip(BAJO_EN, (raiz, raiz + 7)):
            notas.append(F.Note(alt, 100 if i == 3 else 86, CORCHEA - 20,
                                base + i * CORCHEA))
    return notas


def _bambuco_tiple(g, compases, intensidad):
    """Acorde en las corcheas 1, 3 y 5. El primero es el fuerte.

    En las secciones desnudas se quita el del 3, el mas debil de los tres, y
    quedan el 1 y el 5 — los dos que el bombo tambien acentua.
    """
    posiciones = ACORDE_EN if intensidad > 0.45 else (0, 4)
    notas = []
    for c in range(compases):
        _n, _r, voces = g.acorde_de(c)
        base = _bar(c, g.beats)
        for i in posiciones:
            for alt in voces:
                notas.append(F.Note(alt, 92 if i == 0 else 78, CORCHEA - 30,
                                    base + i * CORCHEA))
    return notas


class Bambuco(Genero):
    nombre = "BAMBUCO"
    bpm = 152.0
    # Em - Am - B7 - Em con puente al relativo mayor en Main B, para que no sea
    # la misma cadencia que el pasillo transpuesta una quinta — que es lo que
    # eran las dos primeras versiones, y en el set iban seguidas.
    progresion = (
        ("Em", 40, [52, 55, 59]),
        ("G",  43, [55, 59, 62]),
        ("D",  38, [54, 57, 62]),
        ("B7", 47, [51, 54, 59]),
    )
    pistas = (
        (0, "D1", "papa con yuca: bombo", "Rock Kit", True,  _bambuco_bombo),
        (1, "D2", "papa con yuca: tambora", "Rock Kit", True, _bambuco_tambora),
        (2, "PC", "llamador, alegre, sonajas", "Rock Kit", True, _bambuco_manos),
        (3, "BA", "3/4 bajo",             "Aco.Bass", False, _bambuco_bajo),
        (4, "C1", "3/4 tiple",            "NylonGtr", False, _bambuco_tiple),
    )


# --- Pasillo -------------------------------------------------------------
#
# **Sin sesquialtera**, y eso sale de los datos: en ACMUS-MIR los 57 pasillos
# estan anotados en 3/4 con **un solo nivel de pulso**, frente a 71 de 73
# bambucos en 6/8 **con dos**. Copiar aqui la estructura del bambuco meteria un
# cruce que el genero no tiene.
#
# Tempo 182: los 57 anotados son bimodales, 23 alrededor de 101 (*lento*) y 34
# alrededor de 182 (*fiestero*). Y sin percusion: el pasillo es musica de
# cuerdas, y anadirle bombo para que tenga cuerpo en vivo lo convierte en otra
# cosa.


def _pasillo_bajo(g, compases, intensidad):
    """Principal en el 1, secundaria en el 3: el rasgo del fiestero.

    En la version lenta el bajo principal suena dos veces; alternar principal y
    quinta es lo que empuja.
    """
    notas = []
    for c in range(compases):
        _n, raiz, _v = g.acorde_de(c)
        base = _bar(c, g.beats)
        notas.append(F.Note(raiz, 108, NEGRA - 40, base))
        if intensidad > 0.4:
            notas.append(F.Note(raiz + 7, 88, NEGRA - 40, base + 2 * NEGRA))
    return notas


def _pasillo_tiple(g, compases, intensidad):
    """Bajo en el primero **sin acorde**, rasgueos en el segundo y el tercero.

    Si se rasguea tambien en el 1, los tres tiempos pesan igual y el compas
    pierde direccion. El pasillo empuja porque el 1 es bajo seco y el acorde
    llega despues.
    """
    notas = []
    for c in range(compases):
        _n, raiz, voces = g.acorde_de(c)
        base = _bar(c, g.beats)
        notas.append(F.Note(raiz + 12, 96, CORCHEA, base))
        for i in (1, 2):
            for alt in voces:
                notas.append(F.Note(alt, 84 if i == 1 else 72, CORCHEA - 20,
                                    base + i * NEGRA))
    return notas


def _pasillo_requinto(g, compases, intensidad):
    """Contracanto sincopado, solo en la segunda mitad de cada frase.

    Lo que sostiene un pasillo instrumental es el dialogo entre el rasgueo y esta
    voz. Si suena todo el rato deja de ser respuesta y se vuelve relleno.
    """
    if intensidad < 0.5:
        return []
    notas = []
    for c in range(compases):
        if c < compases / 2.0:
            continue
        _n, _r, voces = g.acorde_de(c)
        base = _bar(c, g.beats)
        for k, i in enumerate((1, 3, 5)):
            notas.append(F.Note(voces[k % len(voces)] + 12, 80, CORCHEA - 20,
                                base + i * CORCHEA))
    return notas


class Pasillo(Genero):
    nombre = "PASILLO"
    bpm = 182.0
    progresion = (
        ("Am", 45, [57, 60, 64]),
        ("Dm", 50, [57, 62, 65]),
        ("E7", 52, [56, 59, 62]),
        ("Am", 45, [57, 60, 64]),
    )
    pistas = (
        (3, "BA", "bajo principal y quinta", "Aco.Bass", False, _pasillo_bajo),
        (4, "C1", "tiple, rasgueo en 2 y 3", "NylonGtr", False, _pasillo_tiple),
        (5, "C2", "requinto, contracanto",   "SteelGtr", False, _pasillo_requinto),
    )


GENEROS = {"bambuco": Bambuco, "pasillo": Pasillo}
