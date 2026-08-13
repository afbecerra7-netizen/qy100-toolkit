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
los que hay. Las velocities se MUESTREAN de las medidas —cada valor emitido
existe en la fuente— y el gate es la mediana por instrumento, que tambien es
siempre un valor real. La primera version prometia esto y emitia una media
truncada que la fuente no contenia: un [M] que era [D].

La marca: `[M]` el esqueleto y las frecuencias (salen de contar el loop);
`[D]` cada compas generado (la recombinacion es nuestra).

## La rejilla, y por que 48

La primera version uso SUB=24 razonando "semicorchea en 4 pulsos = 16, tresillo
= 24" y tomando el maximo. **El maximo no contiene al otro: hace falta el minimo
comun multiplo**, mcm(16,24) = 48. Con 24, toda semicorchea a contratiempo caia
en la casilla del tresillo mas cercano — el motor convertia material binario en
ternario, exactamente la distincion que este proyecto protege. Es el mismo error
de unidad del denominador del compas y del mapale, en su cuarta aparicion.
"""

import collections
import random

from . import patternfmt as F

#: mcm(16, 24): contiene la rejilla binaria de semicorcheas Y la ternaria de
#: tresillos, exactas las dos. Ver la cabecera.
SUB = 48

#: Umbral del esqueleto: presente en al menos 3/4 de los compases de la fuente.
UMBRAL_ESQUELETO = 0.75

#: Con menos de 4 compases de fuente no hay estadistica: el esqueleto se traga
#: todo y salen compases identicos — lo que este motor existe para evitar.
MIN_COMPASES = 4


class Modelo:
    __slots__ = ("esqueleto", "variaciones", "vel", "gate", "compases_fuente",
                 "pulsos_por_compas", "golpes_fuente", "golpes_modelo", "avisos")

    def __init__(self):
        self.esqueleto = []        # [(pos, nota)]
        self.variaciones = {}      # {(pos, nota): frecuencia 0..1}
        self.vel = {}              # {(pos, nota): [velocities medidas]}
        self.gate = {}             # {nota: gate mediano en relojes}
        self.compases_fuente = 0
        self.pulsos_por_compas = 4
        self.golpes_fuente = 0     # notas de la fuente dentro de los compases
        self.golpes_modelo = 0     # apariciones (pos, nota, compas) del modelo
        self.avisos = []


def cargar(notas, pulsos_por_compas=4, compases=None, permitir_corto=False):
    """Construye el modelo desde [(pulso, nota, velocity, duracion_en_pulsos)].

    `compases` es el numero declarado de compases del loop (el que dice
    `loops.json`). La primera version lo deducia de DONDE EMPIEZA la ultima
    nota —`round((ultimo + 0.5) / largo)`— que mide otra cosa: un cuarto compas
    de notas tempranas se lo tragaba entero. Sin declararlo, se infiere del
    indice de celda de la ultima nota, que al menos mide lo que dice.
    """
    m = Modelo()
    m.pulsos_por_compas = pulsos_por_compas
    largo = float(pulsos_por_compas)
    celda = largo / SUB

    # atribucion por celda GLOBAL: compas y posicion salen del mismo redondeo,
    # asi que un golpe al filo del compas cae en el compas al que de verdad
    # pertenece. La primera version hacia `round(...) % SUB` por separado y
    # mandaba el final de un compas al downbeat del MISMO compas: 4 de los 98
    # golpes del chande desaparecian dentro de otros.
    celdas = []
    for t, a, v, d in notas:
        g = int(round(t / celda))
        celdas.append((g // SUB, g % SUB, a, v, d))

    m.compases_fuente = compases or (max(c for c, _p, _a, _v, _d in celdas) + 1)
    if m.compases_fuente < MIN_COMPASES and not permitir_corto:
        raise ValueError(
            "la fuente son %d compases y el minimo util es %d: con tan pocos, "
            "todo acaba en el esqueleto y el motor genera compases identicos — "
            "justo lo que existe para evitar. Usa permitir_corto=True si de "
            "verdad quieres eso." % (m.compases_fuente, MIN_COMPASES))

    presencia = collections.defaultdict(set)
    vels = collections.defaultdict(list)
    gates = collections.defaultdict(list)
    vistos = set()
    fuera = colisiones = 0
    for c, pos, a, v, d in celdas:
        if c >= m.compases_fuente:
            fuera += 1
            continue
        m.golpes_fuente += 1
        if (c, pos, a) in vistos:
            colisiones += 1
        vistos.add((c, pos, a))
        presencia[(pos, a)].add(c)
        vels[(pos, a)].append(v)
        gates[a].append(max(1, int(round(d * F.CLOCKS_PER_QUARTER))))
    if fuera:
        m.avisos.append("%d golpe(s) mas alla de los %d compases declarados: "
                        "descartados" % (fuera, m.compases_fuente))
    if colisiones:
        m.avisos.append("%d golpe(s) cayeron en una celda ya ocupada (misma "
                        "nota, misma posicion, mismo compas): la rejilla de %d "
                        "no los separa" % (colisiones, SUB))

    for clave, cs in presencia.items():
        frec = len(cs) / float(m.compases_fuente)
        m.golpes_modelo += len(cs)
        m.vel[clave] = sorted(vels[clave])
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
    pierde el llamador deja de ser el genero. La velocity de cada golpe se
    muestrea de las que la fuente uso en esa misma celda.
    """
    rng = random.Random(semilla)
    largo = F.CLOCKS_PER_QUARTER * beats
    paso = largo / float(SUB)
    escala = 0.3 + intensidad
    notas = []
    for c in range(compases):
        for pos, a in modelo.esqueleto:
            notas.append(F.Note(a, rng.choice(modelo.vel[(pos, a)]),
                                modelo.gate.get(a, 120),
                                int(c * largo + pos * paso)))
        for (pos, a), frec in sorted(modelo.variaciones.items()):
            if rng.random() < min(1.0, frec * escala):
                notas.append(F.Note(a, rng.choice(modelo.vel[(pos, a)]),
                                    modelo.gate.get(a, 120),
                                    int(c * largo + pos * paso)))
    notas.sort(key=lambda n: n.time)
    return notas
