#!/usr/bin/env python3
"""Pruebas de los motores de genero. No necesitan el QY100 ni las partituras.

    .venv/bin/python test_generos.py

Existe porque una auditoria encontro 21 defectos en `andina.py` y `grep -c
andina test_protocol.py` daba **cero**. Los motores de genero llevan la mayor
densidad de dato medido a mano de todo el proyecto —celdas contadas compas a
compas sobre partituras que no estan en el repositorio— y no habia una sola
comprobacion que los tocara. Cualquiera de esos arreglos se podia deshacer sin
que nada se pusiera rojo.

Las partituras viven fuera del repositorio, asi que **aqui no se remide nada**:
lo que se comprueba es que el motor siga tocando lo que su propia procedencia
declara. Es una comprobacion de coherencia interna, no de verdad musical, y esa
distincion importa — para lo segundo hace falta la partitura y un oido.

Las cifras que aparecen aqui son las de las mediciones ya hechas; si alguna se
remide y cambia, **este fichero tiene que cambiar con ella**, y que falle es la
senal de que se movio algo.
"""

import sys

from qy100syx import andina as A

FALLOS = []
CUENTA = [0]


def check(etiqueta, obtenido, esperado):
    CUENTA[0] += 1
    if obtenido == esperado:
        print("  ok   %s" % etiqueta)
    else:
        print("  FALLA %s\n        obtenido: %r\n        esperado: %r"
              % (etiqueta, obtenido, esperado))
        FALLOS.append(etiqueta)


def corcheas(notas, beats, compas=0):
    """En que corcheas del compas `compas` cae algo."""
    largo = A.NEGRA * beats
    return sorted({(n.time - compas * largo) // A.CORCHEA + 1
                   for n in notas if compas * largo <= n.time < (compas + 1) * largo})


# --- Procedencia --------------------------------------------------------
#
# El defecto que motivo esto: `BambucoFiestero` y `BambucoMelancolico` no
# declaraban `fuentes` y heredaban el de `Bambuco`, asi que anunciaban por
# consola `[M]` sobre una partitura para pistas que tocan otra cosa. Un dict que
# existe para impedir la mezcla silenciosa de fuentes, mintiendo en silencio.

print("procedencia")
for nombre in sorted(A.GENEROS):
    clase = A.GENEROS[nombre]
    check("%-13s declara su propio dict de fuentes" % nombre,
          "fuentes" in clase.__dict__, True)

for nombre in sorted(A.GENEROS):
    g = A.GENEROS[nombre]()
    idx_pistas = {idx for idx, _n, _p, _v, _b, _m in g.pistas}
    # Las claves que no son indices de pista son anotaciones deliberadas (el
    # golpe simultaneo del currulao); no se exige que correspondan a una pista.
    faltan = sorted(i for i in idx_pistas if i not in g.fuentes)
    check("%-13s ninguna pista sin procedencia" % nombre, faltan, [])
    marcas = {r[1] for r in g.procedencia()}
    check("%-13s todas las marcas son validas" % nombre,
          marcas - {"[M]", "[D]", "[V]"}, set())

# Y que la herencia, si vuelve, se note. Se fabrica una subclase que no declara
# `fuentes` y se exige que `procedencia()` lo diga en vez de heredar callada.
class _Heredera(A.Bambuco):
    nombre = "PRUEBA"

marcas = {r[1] for r in _Heredera().procedencia()}
check("una subclase sin fuentes propio sale como [V], no como [M]",
      marcas, {"[V]"})
check("   y dice de quien lo heredaria",
      "HEREDADO" in _Heredera().procedencia()[0][2], True)

# --- Las celdas medidas -------------------------------------------------

print("\nlas celdas, contra lo que declara su procedencia")

# Mapale: **son DOS generos**, y el que no distingue cual es cual rompe el
# groove. La diferencia es donde cae el golpe de en medio del ciclo:
#
#     binario   0, 360, 600 de 960   el segundo al 37,5 % — 3+2+3
#     ternario  0, 320, 640          el segundo al 33,3 % — tres contra dos
#
# Cuatro por ciento del ciclo, y es todo el groove. El ternario tiene cinco
# fuentes documentales y **suena mal**; el binario no tiene ninguna y **suena
# bien**. Se escribio una vez el ternario encima del binario, sustituyendolo, y
# hubo que deshacerlo de oido. Estas comprobaciones existen para que no vuelva
# a pasar por descuido.
check("mapale: el binario es 4/4", (A.Mapale.beats, A.Mapale.denominador), (4, 4))
check("   celda 3+2+3 en semicorcheas", A.MAPALE_CELDA, (0, 3, 5))
g = A.GENEROS["mapale"]()
ost = sorted(g.construir(1, 1, 0.8)[3], key=lambda n: n.time)
check("   golpes en 0, 360 y 600", [n.time for n in ost[:3]], [0, 360, 600])
check("   y su celda va marcada [V], no [M]", A.Mapale.fuentes[3][0], "[V]")

check("ternario: es 6/8", (A.MapaleTernario.beats, A.MapaleTernario.denominador),
      (3, 8))
check("   celda en las corcheas 1, 3 y 5", A.MAPALE_CORCHEAS, (0, 2, 4))
gt = A.GENEROS["mapaleternario"]()
ot = sorted(gt.construir(1, 1, 0.8)[3], key=lambda n: n.time)
check("   golpes en 0, 480 y 960", [n.time for n in ot[:3]], [0, 480, 960])
check("   y esa si va marcada [M]", A.MapaleTernario.fuentes[3][0], "[M]")

# Lo que de verdad hay que impedir: que uno acabe tocando lo del otro.
check("los dos NO tocan en el mismo sitio",
      [n.time for n in ost[:3]] == [n.time for n in ot[:3]], False)
check("y son generos distintos, no el mismo renombrado",
      A.Mapale.nombre != A.MapaleTernario.nombre, True)

# Currulao: la partitura trae CUATRO golpes —madera en 1, 3 y 4, cuero en la 6—
# y el motor escribe cinco, anadiendo madera simultanea sobre el cuero. Ese
# quinto sale de la otra cartilla y tiene que estar declarado aparte.
g = A.GENEROS["currulao"]()
bombo = sorted(g.construir(1, 1, 0.8)[0], key=lambda n: n.time)
prim = [n for n in bombo if n.time < A.NEGRA * g.beats]
# Ojo con la etiqueta: la PARTITURA trae madera en 1, 3 y 4; el MOTOR escribe
# ademas la madera simultanea de la 6, que viene de la cartilla. Las dos cosas
# son ciertas y decir solo la primera aqui seria repetir el defecto.
check("currulao: madera en 1, 3 y 4 (partitura) mas la 6 (cartilla)",
      sorted({n.time // A.CORCHEA + 1 for n in prim if n.pitch == A.MADERA}),
      [1, 3, 4, 6])
check("   cuero solo en la 6",
      sorted({n.time // A.CORCHEA + 1 for n in prim if n.pitch == A.CUERO}), [6])
check("   son cinco golpes, no los cuatro de la partitura", len(prim), 5)
check("   y el quinto esta declarado aparte",
      "0-simultaneo" in g.fuentes, True)
check("   citando la cartilla, no la partitura",
      "Que te pasa vo" in g.fuentes["0-simultaneo"][1], True)

# Fiestero: bajo en las tres negras y acordes en las tres contras, alternancia
# estricta. Es lo que lo separa del de salon, que deja vacias la 1 y la 6.
g = A.GENEROS["fiestero"]()
p = g.construir(2, 1, 0.85)
check("fiestero: bajo en las corcheas 1, 3 y 5",
      corcheas(p[3], g.beats), [1, 3, 5])
check("   acordes en las corcheas 2, 4 y 6",
      corcheas(p[4], g.beats), [2, 4, 6])
check("   sin un solo hueco entre los dos",
      sorted(set(corcheas(p[3], g.beats) + corcheas(p[4], g.beats))),
      [1, 2, 3, 4, 5, 6])

# De salon: deja vacias la 1 y la 6, que es justamente la diferencia.
g = A.GENEROS["bambuco"]()
p = g.construir(2, 1, 0.85)
check("de salon: el acompanamiento deja vacias la 1 y la 6",
      sorted(set(corcheas(p[3], g.beats) + corcheas(p[4], g.beats))), [2, 3, 4, 5])

# Melancolico: el bajo rehuye el tiempo fuerte. Es lo unico medido de este
# genero, y la colocacion concreta va marcada `[D]`.
g = A.GENEROS["melancolico"]()
check("melancolico: el bajo nunca cae en la corchea 1",
      1 in corcheas(g.construir(2, 1, 0.85)[3], g.beats), False)

# Torbellino: EL MOTOR toca bajo y bombo doblando `TORB_CELDA` en las tres
# negras — por diseno. LA FUENTE toca otra cosa: bombo `[1,5]` en el 97 % y
# contrabajo `[1,5]` en el 52 %. La version anterior de estas dos comprobaciones
# afirmaba en su etiqueta que "el bombo lleva la celda de 1 y 5" mientras
# comprobaba [1,3,5]: **dos aserciones identicas sobre pistas identicas no
# pueden distinguir bombo de bajo**, y la suite imprimia en verde una frase
# falsa. Ahora cada etiqueta dice de que lado esta.
g = A.GENEROS["torbellino"]()
p = g.construir(2, 2, 0.85)
check("torbellino: el bajo del MOTOR va en las tres negras",
      corcheas(p[3], g.beats), [1, 3, 5])
check("   y el bombo del MOTOR dobla esa misma celda",
      corcheas(p[0], g.beats), [1, 3, 5])
check("   por eso su procedencia va en [D], no en [M]",
      (A.Torbellino.fuentes[3][0], A.Torbellino.fuentes[0][0]), ("[D]", "[D]"))
check("   y la fila del bajo ya no niega lo que la fuente si hace",
      "NO cae" in A.Torbellino.fuentes[3][2], False)
check("   la fuente vive DENTRO de la fila, citada como [M]",
      "[M]" in A.Torbellino.fuentes[3][2]
      and "52" in A.Torbellino.fuentes[3][2], True)
check("guabina: su bajo en 1 y 5 va marcado [D], no [M]",
      A.GENEROS["guabina"].fuentes[3][0], "[D]")

# Pasillo: bajo en la 1, acordes en 4 y 5. **No es el "metodo 3"** —acordes en
# 1, 3, 5 y bajo en 4 y 6— que el documento publicado le atribuia.
check("pasillo: el bajo va en la corchea 1", A.PASILLO_BAJO_EN, 0)
check("   y los acordes en la 4 y la 5", A.PASILLO_ACORDE_EN, (3, 4))

# --- Que todo lo que se genera quepa donde va ---------------------------
#
# Ninguna nota puede caer fuera de su seccion: esa es la clase de fallo que el
# denominador del compas producia y que nada miraba.

# --- El motor de loop -----------------------------------------------------
#
# Existe por una medicion: los motores repetian 8 de 8 compases identicos donde
# los loops reales repiten 1 de 4. Estas comprobaciones fijan el contrato: el
# esqueleto SIEMPRE, el vocabulario SOLO el de la fuente, y variacion real.

print("\nel motor de loop, contra el chande")
import os
if os.path.exists("midi/CHANDE-xg.mid"):
    import importar_tribe as I2
    from qy100syx import loopmotor as L
    notas_f, _b = I2.leer_mid("midi/CHANDE-xg.mid")
    mod = L.cargar(notas_f)
    check("el modelo separa esqueleto de variacion",
          (len(mod.esqueleto) > 0, len(mod.variaciones) > 0), (True, True))
    gen = L.generar(mod, 8, 0.7, semilla=1)
    largo = 480 * 4
    check("el esqueleto esta en TODOS los compases generados",
          all(any(n.pitch == a and n.time == int(c*largo + p*largo/24.0)
                  for n in gen)
              for c in range(8) for p, a in mod.esqueleto), True)
    import collections as C2
    hs = [frozenset((n.pitch, n.time - c*largo) for n in gen
                    if c*largo <= n.time < (c+1)*largo) for c in range(8)]
    rep = C2.Counter(hs).most_common(1)[0][1]
    check("varia como la fuente, no como un secuenciador (<=3 de 8 identicos)",
          rep <= 3, True)
    fuente = set(mod.vel.keys())
    fuera = [n for n in gen
             if (int(round((n.time % largo) / (largo/24.0))) % 24, n.pitch)
             not in fuente]
    check("cero golpes fuera del vocabulario de la fuente", len(fuera), 0)
    check("determinista con la misma semilla",
          L.generar(mod, 8, 0.7, semilla=1) == gen, True)
    check("y distinto con otra semilla",
          L.generar(mod, 8, 0.7, semilla=2) != gen, True)
else:
    print("  (sin midi/CHANDE-xg.mid: seccion omitida)")

print("\nlos seis tramos de cada genero")
for nombre in sorted(A.GENEROS):
    g = A.GENEROS[nombre]()
    fuera, vacias = 0, []
    for s, (nom_s, intensidad, comp) in enumerate(A.SECCIONES):
        piezas = g.construir(s, comp, intensidad)
        total = g.total(comp)
        for idx, nom, _p, _v, _b, _m in g.pistas:
            notas = piezas[idx]
            fuera += sum(1 for n in notas if n.time >= total or n.time < 0)
            if not notas and intensidad > 0.5:
                vacias.append("%s/%s" % (nom_s, nom))
    check("%-13s ninguna nota fuera de su seccion" % nombre, fuera, 0)
    check("%-13s ninguna pista muda con la seccion densa" % nombre, vacias, [])

# El compas declarado y las negras por compas tienen que cuadrar: es lo que
# escribe `cmd_andina` en el byte 14.
print("\ncompas declarado")
from qy100syx import patternfmt as F                                  # noqa: E402
for nombre in sorted(A.GENEROS):
    clase = A.GENEROS[nombre]
    num = clase.beats * 2 if clase.denominador == 8 else clase.beats
    check("%-13s %d/%d son %d negras, que es su `beats`"
          % (nombre, num, clase.denominador, clase.beats),
          F.negras_por_compas(num, clase.denominador), clase.beats)

print()
if FALLOS:
    print("FALLARON %d: %s" % (len(FALLOS), ", ".join(FALLOS)))
    sys.exit(1)
print("Generos verificados: %d comprobaciones." % CUENTA[0])
