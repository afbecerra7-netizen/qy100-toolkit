"""Motor generativo construido desde un loop medido, no desde teoria.

Existe por una medicion que separo nuestros motores de las referencias:

    motores de `andina.py`      mapale y cumbia: 8 de 8 compases IDENTICOS
    loops reales de Tribe       porro, chande, bullerengue: 1 de 4

Un conjunto real no repite exacto, y la variacion no es ruido: **es vocabulario
de la fuente**. Este motor lo trata asi. Del loop se separa:

- el **esqueleto**: los golpes presentes en >= 3/4 de los compases. Se toca
  SIEMPRE, identico — es la identidad del ritmo y no se varia.
- la **variacion**: el resto de golpes de la fuente, cada uno con la frecuencia
  con que la fuente lo usa. Se muestrea compas a compas con esa frecuencia,
  escalada por la intensidad de la seccion.

El motor **no puede inventar un golpe que la fuente no tenga**: solo redistribuye
los que hay, con las velocities y duraciones medidas. Esa es la diferencia con
"humanizar" — aqui se varia lo que la fuente varia, donde la fuente lo varia.

La marca de todo esto es `[M]` para el esqueleto y las frecuencias (salen de
contar el loop) y `[D]` para cada compas generado (la recombinacion es nuestra).
"""

import collections
import random

from . import patternfmt as F

#: Resolucion de la rejilla: 24 posiciones por compas. Es la mas fina que
#: aparecio en los loops medidos (semicorchea en 4 pulsos = 16, tresillo = 24).
SUB = 24

#: Umbral del esqueleto: presente en al menos 3/4 de los compases de la fuente.
UMBRAL_ESQUELETO = 0.75


class Modelo:
    __slots__ = ("esqueleto", "variaciones", "vel", "gate", "compases_fuente",
                 "pulsos_por_compas")

    def __init__(self):
        self.esqueleto = []        # [(pos, nota)]
        self.variaciones = {}      # {(pos, nota): frecuencia 0..1}
        self.vel = {}              # {(pos, nota): velocity media}
        self.gate = {}             # {nota: gate mediano en relojes}
        self.compases_fuente = 0
        self.pulsos_por_compas = 4


def cargar(notas, pulsos_por_compas=4):
    """Construye el modelo desde [(pulso, nota, velocity, duracion_en_pulsos)].

    `notas` es la salida de `importar_tribe.leer_mid` sobre el loop YA traducido
    al kit XG — el modelo hereda la traduccion, no la repite.
    """
    m = Modelo()
    m.pulsos_por_compas = pulsos_por_compas
    largo = float(pulsos_por_compas)
    ultimo = max(t for t, _a, _v, _d in notas)
    m.compases_fuente = max(1, int(round((ultimo + 0.5) / largo)))

    presencia = collections.defaultdict(set)
    vels = collections.defaultdict(list)
    gates = collections.defaultdict(list)
    for t, a, v, d in notas:
        c = int(t // largo)
        if c >= m.compases_fuente:
            continue
        pos = int(round((t % largo) / (largo / SUB))) % SUB
        presencia[(pos, a)].add(c)
        vels[(pos, a)].append(v)
        gates[a].append(max(1, int(round(d * F.CLOCKS_PER_QUARTER))))

    for clave, cs in presencia.items():
        frec = len(cs) / float(m.compases_fuente)
        m.vel[clave] = int(sum(vels[clave]) / len(vels[clave]))
        if frec >= UMBRAL_ESQUELETO:
            m.esqueleto.append(clave)
        else:
            m.variaciones[clave] = frec
    m.esqueleto.sort()
    for a, gs in gates.items():
        m.gate[a] = sorted(gs)[len(gs) // 2]
    return m


def generar(modelo, compases, intensidad, semilla=0, beats=4):
    """[Note] para una seccion: esqueleto fijo + variacion muestreada.

    Determinista con la misma semilla — un estilo escrito dos veces tiene que
    ser el mismo estilo. La intensidad escala SOLO la probabilidad de la
    variacion (0.3x a 1.3x); el esqueleto no se toca nunca, porque un fill que
    pierde el llamador deja de ser el genero.
    """
    rng = random.Random(semilla)
    largo = F.CLOCKS_PER_QUARTER * beats
    paso = largo / float(SUB)
    escala = 0.3 + intensidad
    notas = []
    for c in range(compases):
        for pos, a in modelo.esqueleto:
            notas.append(F.Note(a, modelo.vel[(pos, a)], modelo.gate.get(a, 120),
                                int(c * largo + pos * paso)))
        for (pos, a), frec in sorted(modelo.variaciones.items()):
            if rng.random() < min(1.0, frec * escala):
                notas.append(F.Note(a, modelo.vel[(pos, a)],
                                    modelo.gate.get(a, 120),
                                    int(c * largo + pos * paso)))
    notas.sort(key=lambda n: n.time)
    return notas
