"""Receta de un estilo de usuario completo: seis secciones por ocho pistas.

`generar` escribe **una** pista, y para eso lee el patron entero por MIDI. Montar
un estilo asi serian 48 lecturas y 48 escrituras del patron completo, cada una un
punto donde una transferencia a medias puede corromper la contabilidad de memoria.

Aqui se hace al reves y es la decision de diseno que importa: **se lee una vez,
se genera todo en memoria y se escribe una vez.** Un solo `bulk mode ON ... OFF`.

## Por que las seis secciones no son intercambiables

Se planteo en su momento si las secciones debian ser una rampa de intensidad o
variantes sueltas, y la disyuntiva era falsa: **el aparato ya les asigno funcion**.
`Fill AB` y `Fill BA` son transiciones *direccionales* —de A hacia B y de vuelta—
y el footswitch cicla entre secciones en vivo (manual p. 121). Asi que la forma
la dicta el hardware y lo unico que elegimos es la densidad de cada una.

## Las reglas de Yamaha para frases rearmonizables

Manual p. 59, y son restricciones de diseno para los motores, no consejos:

1. Respetar el contexto armonico del acorde fuente.
2. Usar sobre todo fundamental, 3a, 5a y 7a mayor.
3. **Ceñirse a ritmos, evitar lineas melodicas.**

La 3 dice que el euclidiano es la herramienta correcta para percusion, y la 2 que
la melodia de Markov **no** lo es por defecto: camina por la escala y cae en notas
de paso que `Chord 1` transpone a disonancias. Por eso aqui las pistas de acorde
salen de `acordes()` y `arpegio()`, que solo pisan notas del acorde, en vez de
Markov. La melodia sigue disponible en `generar` para material en `Bypass`.
"""
from . import patternfmt as F

# Grados sobre la fundamental. Cuarta y sexta quedan fuera a proposito: son las
# que la regla 2 excluye, y son justo las que `Chord 1` convierte en choque.
TRIADA = (0, 4, 7)
SEPTIMA = (0, 4, 7, 11)

#: Funcion de cada seccion y su densidad. El orden es el de `F.SECTIONS`.
SECCIONES = [
    #  nombre      intensidad  que hace
    ("Intro",      0.35, "anuncia: sin kit completo"),
    ("Main A",     0.55, "el groove base"),
    ("Main B",     0.85, "la version subida"),
    ("Fill AB",    0.75, "transicion hacia B, abierta"),
    ("Fill BA",    0.60, "transicion de vuelta a A"),
    ("Ending",     0.40, "resuelve"),
]

#: Una entrada por pista. `tipo` es el TYPE de la tabla de frases: `Bypass` toca
#: las notas literales y `Chord 1` / `Bass` las rearmoniza contra la pista de
#: acordes, que es lo que permite tocar el estilo con ABC desde un teclado.
PISTAS = [
    # idx nombre  papel        tipo        voz            bateria
    (0, "D1", "bombo",     "Bypass",  "Rock Kit",  True),
    (1, "D2", "caja",      "Bypass",  "Rock Kit",  True),
    (2, "PC", "percusion", "Bypass",  "Rock Kit",  True),
    (3, "BA", "bajo",      "Bass",    "FngrBass",  False),
    (4, "C1", "acordes",   "Chord 1", "Warm Pad",  False),
    (5, "C2", "arpegio",   "Chord 1", "Saw Ld",    False),
]

BOMBO, CAJA, CHARLES, ABIERTO, SHAKER = 36, 38, 42, 46, 82


def _pasos_activos(intensidad, minimo, maximo):
    """Reparte la intensidad 0..1 sobre un rango entero de pulsos."""
    return int(round(minimo + (maximo - minimo) * intensidad))


def bombo(compases, intensidad, semilla, G):
    pulsos = _pasos_activos(intensidad, 2, 7)
    return G.euclidiano(compases, pulsos=pulsos, pasos=16, nota=BOMBO,
                        velocity=108, semilla=semilla)


def caja(compases, intensidad, semilla, G):
    """Contragolpe fijo en 2 y 4, mas charles que se densifica.

    El contragolpe **no** es euclidiano y esa es la diferencia entre que suene a
    kit o a patron: si el 2 y el 4 se reparten geometricamente, dejan de caer
    donde el oido los espera y el groove deja de leerse como bateria.
    """
    notas, total = G.euclidiano(compases, pulsos=_pasos_activos(intensidad, 4, 12),
                                pasos=16, nota=CHARLES, velocity=64, semilla=semilla)
    negra = F.CLOCKS_PER_QUARTER
    for c in range(compases):
        for t in (1, 3):
            notas.append(F.Note(CAJA, 104, negra // 2, c * negra * 4 + t * negra))
    return sorted(notas, key=lambda n: n.time), total


def percusion(compases, intensidad, semilla, G):
    nota = SHAKER if intensidad < 0.7 else ABIERTO
    return G.euclidiano(compases, pulsos=_pasos_activos(intensidad, 3, 9),
                        pasos=16, nota=nota, velocity=72, semilla=semilla)


def bajo(compases, intensidad, semilla, G):
    """Fundamental sobre una reja euclidiana.

    Una sola altura: el TYPE `Bass` la rearmoniza contra la pista de acordes, asi
    que la nota escrita solo fija el **ritmo**. Elegir alturas aqui seria pelear
    con el aparato por quien decide la armonia.
    """
    return G.euclidiano(compases, pulsos=_pasos_activos(intensidad, 2, 6),
                        pasos=8, nota=40,
                        velocity=100, semilla=semilla)


def acordes(compases, intensidad, semilla, G):
    """Golpes de acorde. Solo notas de la triada: regla 2 de Yamaha."""
    rejilla, total = G.euclidiano(compases,
                                  pulsos=_pasos_activos(intensidad, 2, 5),
                                  pasos=8, nota=60, velocity=88, semilla=semilla)
    negra = F.CLOCKS_PER_QUARTER
    grados = SEPTIMA if intensidad > 0.7 else TRIADA
    notas = [F.Note(60 + g, n.velocity, negra, n.time)
             for n in rejilla for g in grados]
    return sorted(notas, key=lambda n: n.time), total


def arpegio(compases, intensidad, semilla, G):
    """Semicorcheas tejiendo la triada en dos octavas.

    El vaiven —dos pasos adelante, uno atras— en vez de la subida recta: un
    arpegio ascendente puro se oye como ejercicio y cansa en cuatro compases.
    """
    patron = [0, 2, 1, 3, 2, 4, 3, 5]
    voces = [60 + g for g in TRIADA] + [72 + g for g in TRIADA]
    semi = F.CLOCKS_PER_QUARTER // 4
    por_compas = 16 if intensidad > 0.6 else 8
    salto = 16 // por_compas
    notas = []
    for c in range(compases):
        for i in range(por_compas):
            notas.append(F.Note(voces[patron[i % len(patron)]],
                                86 if i % 4 == 0 else 74,
                                semi - 20,
                                c * F.CLOCKS_PER_QUARTER * 4 + i * salto * semi))
    return notas, F.section_clocks(compases)


MOTORES = {"bombo": bombo, "caja": caja, "percusion": percusion,
           "bajo": bajo, "acordes": acordes, "arpegio": arpegio}




# --- Receta afrobeat -----------------------------------------------------
# The Shaolin Afronauts: Fela por un lado, Sun Ra por el otro.
#
# **El motor no es un patron, son varios que no coinciden.** En un beat de rock
# todas las partes se alinean sobre el mismo 2 y 4; en afrobeat cada instrumento
# recorre su propio ciclo y lo que se oye es la figura compuesta que aparece
# cuando se cruzan. Por eso aqui el euclidiano encaja mucho mejor que en material
# post-punk, donde peleaba contra un contragolpe que quiere estar en su sitio:
# aqui **no hay nada contra lo que pelear**, y las rotaciones distintas son el
# efecto buscado en vez de un accidente.
#
# De ahi que cada parte lleve su `rotacion` explicita y sus `pasos` propios. Dos
# lineas E(5,16) con rotaciones 0 y 3 no son la misma linea desplazada: son dos
# voces que se responden.

# (rotacion, pulsos, pasos) por nivel de intensidad, **de menos a mas denso**.
# Se escribieron primero en orden de seccion y el codigo las indexa por
# intensidad, que no es el mismo orden: Main B salia con menos bombo que Main A.
# Habria pasado por "Main B suena flojo" sin que nadie sospechara del codigo.
#
# Los pulsos crecen de forma monotona; **las rotaciones no**, y eso es a
# proposito: si todas las partes rotaran igual al densificarse, se alinearian y
# el entrelazado desapareceria justo donde mas hace falta.
AFRO_BOMBO = [(0, 3, 16), (2, 4, 16), (0, 5, 16), (2, 5, 16), (3, 6, 16), (4, 7, 16)]
AFRO_CONGA = [(1, 4, 16), (3, 5, 16), (1, 7, 16), (5, 7, 16), (3, 9, 16), (6, 11, 16)]
AFRO_SHAKE = [(0, 5, 16), (2, 7, 16), (0, 9, 16), (4, 9, 16), (2, 11, 16), (4, 13, 16)]

CONGA_ALTA, CONGA_BAJA, SHEKERE, CAMPANA = 62, 63, 70, 56


def afro_bateria(compases, intensidad, semilla, G):
    """Bombo, caja al borde y campana. La campana es el ancla del conjunto."""
    idx = min(int(intensidad * 6), 5)
    rot, pulsos, pasos = AFRO_BOMBO[idx]
    notas, total = G.euclidiano(compases, pulsos=pulsos, pasos=pasos, nota=BOMBO,
                                rotacion=rot, velocity=106, semilla=semilla)
    negra = F.CLOCKS_PER_QUARTER
    semi = negra // 4
    for c in range(compases):
        base = c * negra * 4
        # La campana marca el ciclo y no se genera: es la referencia contra la
        # que se oyen las demas. Si tambien fuera euclidiana no habria contra que
        # medir el desplazamiento de nadie.
        for i in (0, 3, 6, 8, 11, 14):
            notas.append(F.Note(CAMPANA, 92 if i == 0 else 74, semi, base + i * semi))
        if intensidad > 0.5:
            notas.append(F.Note(CAJA, 88, semi, base + 10 * semi))
    return sorted(notas, key=lambda n: n.time), total


def afro_congas(compases, intensidad, semilla, G):
    """Dos congas cruzadas: la figura es la que aparece entre las dos."""
    idx = min(int(intensidad * 6), 5)
    rot, pulsos, pasos = AFRO_CONGA[idx]
    alta, total = G.euclidiano(compases, pulsos=pulsos, pasos=pasos,
                               nota=CONGA_ALTA, rotacion=rot, velocity=88,
                               semilla=semilla)
    baja, _ = G.euclidiano(compases, pulsos=max(2, pulsos - 2), pasos=pasos,
                           nota=CONGA_BAJA, rotacion=(rot + 5) % pasos,
                           velocity=96, semilla=semilla + 1)
    return sorted(alta + baja, key=lambda n: n.time), total


def afro_shekere(compases, intensidad, semilla, G):
    idx = min(int(intensidad * 6), 5)
    rot, pulsos, pasos = AFRO_SHAKE[idx]
    return G.euclidiano(compases, pulsos=pulsos, pasos=pasos, nota=SHEKERE,
                        rotacion=rot, velocity=70, semilla=semilla)


def afro_bajo(compases, intensidad, semilla, G):
    """Riff corto que se repite sin variar. El bajo de Fela es un ostinato.

    Una sola altura, como en la receta base: el TYPE `Bass` lo rearmoniza, asi
    que lo que se escribe aqui es el **ritmo**, y en este genero el ritmo del
    bajo es casi todo lo que hay.
    """
    negra = F.CLOCKS_PER_QUARTER
    semi = negra // 4
    # Figura de dos compases: el desfase de la repeticion es lo que la hace girar.
    FIGURA = [0, 3, 6, 10, 12, 16, 19, 22, 26, 30]
    notas = []
    for c in range(0, compases, 2):
        base = c * negra * 4
        for i in FIGURA:
            if intensidad < 0.5 and i % 3 == 1:
                continue
            notas.append(F.Note(40, 104 if i % 8 == 0 else 88, semi * 2 - 20,
                                base + i * semi))
    total = F.section_clocks(compases)
    return sorted(_dentro(notas, total), key=lambda n: n.time), total


def afro_guitarra(compases, intensidad, semilla, G):
    """Guitarra tenor: una figura corta de dos compases que se repite.

    **Reescrita al medir el coste.** La primera version ponia el acorde entero en
    casi cada semicorchea: 1.632 notas, el 35% del estilo entero, mas que las tres
    pistas de percusion juntas. Y era menos idiomatica ademas de mas cara — una
    guitarra tenor no rasguea continuo, toca una celula corta y la repite hasta
    que se convierte en textura. Lo caro y lo falso eran lo mismo.

    Dos economias que no quitan nada musical:

    - **Dos voces, no la triada entera.** En una guitarra ritmica de este genero
      lo que se oye es el intervalo, no el acorde completo; el bajo ya pone la
      fundamental. Un tercio menos de notas.
    - **Figura fija de dos compases.** Se repite en vez de generarse compas a
      compas, que es como suena de verdad.

    Lo que no se toca: **nunca cae en el tiempo fuerte.** Es lo que define la
    parte, y si coincide con el bombo deja de entrelazarse y se vuelve
    acompanamiento.
    """
    negra = F.CLOCKS_PER_QUARTER
    semi = negra // 4
    # Semicorcheas de la contra dentro de dos compases (32 pasos). Ninguna en
    # multiplo de 4, que es donde caen los tiempos.
    FIGURA = [3, 6, 7, 11, 14, 15, 19, 22, 23, 27, 30, 31]
    if intensidad < 0.5:
        FIGURA = FIGURA[::2]
    voces = [0, 7] if intensidad < 0.7 else [0, 7, 10]
    notas = []
    for c in range(0, compases, 2):
        base = c * negra * 4
        for i in FIGURA:
            for g in voces:
                notas.append(F.Note(60 + g, 82 if i % 8 == 3 else 68,
                                    semi - 30, base + i * semi))
    total = F.section_clocks(compases)
    return sorted(_dentro(notas, total), key=lambda n: n.time), total


def afro_vientos(compases, intensidad, semilla, G):
    """Vientos al unisono: frases largas, silencio la mitad del tiempo.

    En los tramos flojos callan del todo. El arreglo de vientos entra y sale;
    tocar siempre es lo contrario de como funciona esta musica.
    """
    if intensidad < 0.5:
        return [], F.section_clocks(compases)
    negra = F.CLOCKS_PER_QUARTER
    grados = [0, 3, 7, 10, 7, 3]
    notas = []
    for c in range(compases):
        # En la segunda mitad de la seccion, no en compases alternos: con
        # secciones de dos compases lo segundo hacia que no tocaran nunca.
        # **Una regla escrita en compases absolutos falla cuando la seccion es
        # mas corta que la regla.**
        if c < compases / 2.0:
            continue
        base = c * negra * 4
        for k, g in enumerate(grados):
            notas.append(F.Note(67 + g, 100, negra - 40, base + k * (negra // 2)))
    total = F.section_clocks(compases)
    return _dentro(notas, total), total


def _dentro(notas, total):
    """Recorta lo que se sale de la seccion.

    Las figuras de esta receta duran dos compases —el desfase de la repeticion es
    lo que las hace girar— y hay secciones de uno. Sin esto, `encode_blocks`
    aborta con "la pista dura menos que su ultima nota", que es la comprobacion
    haciendo su trabajo: mejor que escribir eventos fuera del bucle.
    """
    return [n for n in notas if n.time < total]


MOTORES.update({"afro_bateria": afro_bateria, "afro_congas": afro_congas,
                "afro_shekere": afro_shekere, "afro_bajo": afro_bajo,
                "afro_guitarra": afro_guitarra, "afro_vientos": afro_vientos})

PISTAS_AFRO = [
    (0, "D1", "afro_bateria",  "Bypass",  "Rock Kit",   True),
    (1, "D2", "afro_shekere",  "Bypass",  "Rock Kit",   True),
    (2, "PC", "afro_congas",   "Bypass",  "Rock Kit",   True),
    (3, "BA", "afro_bajo",     "Bass",    "FngrBass",   False),
    (4, "C1", "afro_guitarra", "Chord 1", "CleanGtr",   False),
    # `BrssSect` y no `HiBrass`: este ultimo esta en el indice 298, fuera de los
    # 128 programas direccionables. `voces.json` lista las 525 de la ROM y solo
    # las primeras 128 se pueden mandar como program change.
    (5, "C2", "afro_vientos",  "Chord 1", "BrssSect",   False),
]


# --- Receta enka ---------------------------------------------------------
# El enka es la balada sentimental japonesa de posguerra, y en este catalogo no
# es una rareza exotica: **es musica domestica**. El QY100 se hizo en Japon para
# vender en Japon, asi que enka esta ahi por la misma razon que el country esta
# en un teclado americano.
#
# El catalogo cubre casi todo el estilo —bajo y acordes de teclado completos en
# las seis secciones—, asi que aqui solo se genera **la melodia**, que es lo
# unico que las frases de acompanamiento no traen y lo que en este genero lleva
# el tema.

# Escala: pentatonica menor sin cuarta ni septima —el *yonanuki* que le da su
# color—, pero **restringida a notas del acorde** porque la pista va en
# `Chord 1` y el aparato la rearmoniza. La regla 2 de Yamaha (fundamental, 3a,
# 5a) y la pentatonica coinciden en 1, b3 y 5; la 4 entra solo de paso.
ENKA_GRADOS = [0, 3, 7, 12, 7, 3]
ENKA_PASO = 5


def enka_melodia(compases, intensidad, semilla, G):
    """Frases largas con silencio entre ellas, no una linea continua.

    Lo que hace que suene a canto y no a secuencia es **el hueco**: dos compases
    de frase y uno de aire. Una melodia que no respira delata la maquina antes
    que cualquier eleccion de notas.
    """
    import random
    negra = F.CLOCKS_PER_QUARTER
    rnd = random.Random(semilla)
    notas = []
    for c in range(compases):
        if c % 3 == 2 and intensidad < 0.8:      # el compas de aire
            continue
        base = c * negra * 4
        # Figura de cuatro notas por compas, con la ultima sostenida: el gesto
        # de caida al final de frase que caracteriza al genero.
        pasos = [0, 1, 2, 3] if intensidad > 0.6 else [0, 2]
        for k, i in enumerate(pasos):
            g = ENKA_GRADOS[(c * 2 + k) % len(ENKA_GRADOS)]
            if rnd.random() < 0.15:
                g = ENKA_PASO
            largo = negra * 2 - 40 if k == len(pasos) - 1 else negra - 40
            notas.append(F.Note(60 + g, 92 if k == 0 else 78, largo,
                                base + i * negra))
    total = F.section_clocks(compases)
    return _dentro(notas, total), total


MOTORES["enka_melodia"] = enka_melodia

# Solo la melodia: todo lo demas sale del catalogo por referencia.
PISTAS_ENKA = [(4, "C1", "enka_melodia", "Chord 1", "Oboe", False)]

RECETAS = {"base": PISTAS, "afrobeat": PISTAS_AFRO, "enka": PISTAS_ENKA}


def construir(compases_por_seccion, semilla=0, pistas=None, secciones=None,
              receta="base"):
    """Devuelve {(seccion, pista): (notas, total_clocks)} para todo el estilo.

    `compases_por_seccion` es la lista de 6 longitudes que trae la cabecera del
    patron: cada seccion tiene la suya y hay que respetarla, o el aparato y los
    datos discrepan.
    """
    from . import generar as G

    quiere_p = set(pistas) if pistas else None
    quiere_s = set(secciones) if secciones else None
    salida = {}
    for s, (nombre_s, intensidad, _) in enumerate(SECCIONES):
        if quiere_s is not None and s not in quiere_s:
            continue
        compases = compases_por_seccion[s]
        for idx, _n, papel, _t, _v, _b in RECETAS[receta]:
            if quiere_p is not None and idx not in quiere_p:
                continue
            # La semilla mezcla seccion y pista: dos pistas del mismo estilo no
            # deben salir identicas, y el estilo entero debe ser reproducible.
            salida[(s, idx)] = MOTORES[papel](
                compases, intensidad, semilla * 1000 + s * 10 + idx, G)
    return salida
