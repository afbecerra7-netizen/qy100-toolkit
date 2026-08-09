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


def construir(compases_por_seccion, semilla=0, pistas=None, secciones=None):
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
        for idx, _n, papel, _t, _v, _b in PISTAS:
            if quiere_p is not None and idx not in quiere_p:
                continue
            # La semilla mezcla seccion y pista: dos pistas del mismo estilo no
            # deben salir identicas, y el estilo entero debe ser reproducible.
            salida[(s, idx)] = MOTORES[papel](
                compases, intensidad, semilla * 1000 + s * 10 + idx, G)
    return salida
