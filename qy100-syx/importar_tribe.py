#!/usr/bin/env python3
"""Importa un loop de TRIBE Player al QY100, traduciendo su mapa al kit XG.

    .venv/bin/python importar_tribe.py Proyecto.als --patron 16
    .venv/bin/python importar_tribe.py Proyecto.als --patron 16 --escribir

Existe porque un loop de Tribe **no es un patron de bateria**: es un conjunto de
San Jacinto con seis instrumentos y varias articulaciones cada uno —la tambora
sola tiene cascara, abierto y apagado— y el QY100 tiene un kit General MIDI.
Meterlo por `importar.py` a pelo manda cada nota a la altura que le toque en el
kit, que es como la marimba acabo sonando por platos y campanas.

**La tabla de abajo es una decision musical, no una conversion.** Cada linea
elige que golpe del kit XG se parece mas a cada articulacion de Tribe, y eso lo
tiene que mirar alguien con oido antes de darlo por bueno. Va marcada `[D]`
entera hasta que se compare contra el original en el equipo.
"""

import argparse
import collections
import gzip
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qy100syx import patternfmt as F                                  # noqa: E402
from qy100syx import protocol as P, transfer                          # noqa: E402

#: Tribe -> (nota del kit XG, pista de destino, nombre legible).
#:
#: `[D]` **Ninguna linea de esto esta medida.** El criterio, para que se pueda
#: discutir linea a linea en vez de en bloque:
#:
#: - La **cascara** de la tambora es madera contra el aro, asi que va al side
#:   stick (37), que es lo que este proyecto ya usa como `MADERA` en el currulao.
#: - Los **parches** de la tambora van a toms, grave y medio, que es lo que ya
#:   hace el bambuco con `TAMB_BAJO`/`TAMB_ALTO`.
#: - El **alegre** es un tambor de mano: congas. Abierto -> conga abierta,
#:   quemao -> conga apagada, latigazo -> conga aguda seca.
#: - **Maracon y guache** son sonajas: maracas y shaker.
#:
#: Lo mas dudoso es el latigazo, que es un golpe seco y agudo y en un kit XG no
#: tiene equivalente limpio.
MAPA = {
    36: (36, 0, "Bombo Open        -> bombo"),
    41: (41, 0, "Tambora Open L    -> tom grave"),
    43: (41, 0, "Tambora Open R    -> tom grave"),
    45: (45, 0, "Tambora Damped L  -> tom medio"),
    47: (45, 0, "Tambora Damped R  -> tom medio"),
    44: (37, 0, "Tambora Cascara L -> side stick (madera)"),
    46: (37, 0, "Tambora Cascara R -> side stick (madera)"),
    #: `[D]` **El llamador NO puede compartir nota con el alegre.** Estuvieron
    #: los dos en las congas 63 y 64 y sonaban identicos — y el llamador es el
    #: que marca el tiempo, o sea el peor sitio posible para un choque. Va al
    #: bongo grave, que es libre, esta en la familia del tambor de mano y queda
    #: por debajo del bongo agudo que usa el latigazo. Sus dos articulaciones se
    #: colapsan en una: el llamador toca practicamente un solo golpe repetido, y
    #: perder esa distincion es mucho menos grave que confundirlo con otro tambor.
    48: (61, 1, "Llamador Bajoneo  -> bongo grave"),
    50: (61, 1, "Llamador Abierto  -> bongo grave"),
    52: (64, 1, "Alegre Bajoneo    -> conga baja"),
    53: (63, 1, "Alegre Abierto    -> conga abierta"),
    55: (62, 1, "Alegre Quemao     -> conga apagada"),
    #: `[D]` **El latigazo no tiene equivalente en un kit XG.** El kit trae tres
    #: tonos de conga —abierta, apagada y baja— y ninguno es un slap. Mandarlo a
    #: la conga apagada, como estuvo, colapsaba quemao y latigazo en un mismo
    #: golpe: 23 ataques distintos sonando igual, y el alegre perdiendo el filo.
    #: El bongo agudo es del mismo tipo de tambor, suena por encima de las congas
    #: y ataca mas seco. **Es una sustitucion elegida, no un equivalente.**
    57: (60, 1, "Alegre Latigazo   -> bongo agudo (slap; el kit XG no tiene)"),
    59: (82, 2, "Guache Up         -> shaker"),
    60: (82, 2, "Guache Down       -> shaker"),
    #: `[D]` **`Rain` es la unica articulacion SOSTENIDA del conjunto**: dura 950
    #: relojes en el porro, casi dos negras, cuando todo lo demas ronda los 120.
    #: Mandarla al shaker la convertia en un click, y **conservarle la duracion no
    #: lo arregla**: en un kit sampleado el `note off` no alarga la muestra, asi
    #: que un shaker corto suena corto por mucho gate que lleve. El vibraslap es
    #: lo unico del kit XG que se prolonga por si solo. No es un guache — es una
    #: sustitucion por DURACION, no por timbre, y esa es la unica manera de que
    #: un barrido siga sonando a barrido.
    62: (58, 2, "Guache Rain       -> vibraslap (barrido; el shaker no sostiene)"),
    64: (82, 2, "Guache Tremolo    -> shaker"),
    65: (70, 2, "Maracon Up        -> maracas"),
    67: (70, 2, "Maracon Down      -> maracas"),
    69: (70, 2, "Maracon Tremolo   -> maracas"),
}
DESTINOS = {0: "D1", 1: "D2", 2: "PC", 3: "BA", 4: "C1"}

#: `[D]` **El bajo no viene del loop: el clip es solo percusion.** Se deduce de
#: donde el propio loop tiene su esqueleto, medido sobre sus cuatro compases con
#: una rejilla de doce por compas de cuatro negras:
#:
#:     doceavo        1  2  3  4  5  6  7  8  9 10 11 12
#:     cascara        3  ·  ·  4  ·  ·  4  ·  ·  3  ·  ·
#:     tambora        1  ·  ·  ·  4  ·  4  ·  1  ·  1  ·
#:     latigazo       3  ·  ·  1  1  ·  4  ·  1  ·  2  ·
#:     maracon        3  ·  ·  3  ·  ·  4  ·  ·  3  1  ·
#:
#: **El doceavo 7 es el ancla**: cascara, tambora, latigazo y maracon caen ahi
#: los cuatro compases. Y el **doceavo 5 es la cruz de la tambora**, tambien 4
#: de 4 — el golpe mas consistente del loop y el unico que se sale del pulso.
#:
#: El bajo toma esos tres: **1 y 7**, que son las dos mitades del 2/2, y **5**,
#: para amarrarse a la tambora en vez de ir por su cuenta. Ni la partitura de
#: banda ni el metodo de bateria dan linea de bajo —la primera son seis partes
#: en unisono ritmico y el segundo es de bateria sola— asi que **esto es
#: criterio, no medicion**, y solo el sitio de los golpes esta medido.
BAJO_DOCEAVOS = (0, 4, 6)      # doceavos 1, 5 y 7
#: `[M]` **Sol menor**, leido de la partitura de banda `PRENDE LA VELA`: las
#: seis armaduras cuadran entre si al destransponer —clarinete y tenor sin
#: alteraciones, alto con un sostenido, lira y trombon con dos bemoles— y el
#: fichero de Finale lo lleva en el nombre. Lo unico que se toma de esa
#: partitura es **la tonalidad**; la melodia es de Lucho Bermudez y no se copia.
BAJO_TONICA = 43                       # Sol
#: `[D]` La progresion es criterio: el loop es solo percusion y no trae armonia.
#: Tres compases sobre la tonica y uno sobre el relativo mayor, que es el
#: movimiento minimo que no suena estatico en un genero de ostinato.
BAJO_PROGRESION = (0, 0, 3, 0)         # Gm Gm Bb Gm, en semitonos
BAJO_GRADOS = (0, 7, 0)                # fundamental, quinta, fundamental

#: `[D]` **La base armonica.** Va en los doceavos 4 y 10 — las dos negras que el
#: bajo deja libres, y donde la cascara y el maracon caen en 3 y 4 de los 4
#: compases. Entre bajo y acordes cubren 1, 4, 5, 7 y 10, que es exactamente el
#: esqueleto medido del loop: **ninguna de las dos voces elige un sitio que el
#: loop no tenga ya marcado**.
#:
#: Las voces son la triada, escritas literales porque la pista va en `Bypass`.
ACORDE_DOCEAVOS = (3, 9)
ACORDE_VOCES = (0, 3, 7)               # menor; en el compas del relativo, mayor
ACORDE_TONICA = 55                     # Sol, una octava y media sobre el bajo


def leer_mid(ruta):
    """[(pulso, nota, velocity, duracion_en_pulsos)] de un .mid, y el bpm.

    **La duracion se conserva y no es un detalle.** La primera version ponia una
    semicorchea fija a todo, y el `Guache Rain` del porro —que en la fuente dura
    950 relojes, casi dos negras, cuando el resto ronda los 120— se convirtio en
    un click. Un barrido sostenido y un golpe seco no son la misma nota con otra
    etiqueta.
    """
    import mido
    m = mido.MidiFile(ruta)
    bpm, notas, abiertas = None, [], collections.defaultdict(list)
    for tr in m.tracks:
        t = 0
        for x in tr:
            t += x.time
            if x.type == "set_tempo" and bpm is None:
                bpm = 60e6 / x.tempo
            elif x.type == "note_on" and x.velocity:
                abiertas[x.note].append((t, x.velocity))
            elif x.type == "note_off" or (x.type == "note_on" and not x.velocity):
                if abiertas.get(x.note):
                    ini, vel = abiertas[x.note].pop(0)
                    notas.append((ini / float(m.ticks_per_beat), x.note, vel,
                                  (t - ini) / float(m.ticks_per_beat)))
    for alt, pend in abiertas.items():
        for ini, vel in pend:
            notas.append((ini / float(m.ticks_per_beat), alt, vel, 0.25))
    return sorted(notas), bpm


def leer_als(ruta, pista_filtro="DRUM"):
    """[(pulso, nota, velocity)] del clip de bateria, y el tempo del proyecto."""
    r = ET.fromstring(gzip.open(ruta).read())
    bpm = None
    for t in r.iter("Tempo"):
        m = t.find("Manual")
        if m is not None:
            bpm = float(m.get("Value")); break
    notas = []
    for tr in r.iter("MidiTrack"):
        nom = tr.find(".//EffectiveName")
        nom = (nom.get("Value") if nom is not None else "") or ""
        if pista_filtro.upper() not in nom.upper():
            continue
        for c in tr.iter("MidiClip"):
            for kt in c.iter("KeyTrack"):
                alt = int(kt.find(".//MidiKey").get("Value"))
                for n in kt.iter("MidiNoteEvent"):
                    notas.append((float(n.get("Time")), alt, int(n.get("Velocity")),
                                  float(n.get("Duration", 0.25))))
    return sorted(notas), bpm


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("proyecto")
    ap.add_argument("--patron", type=int, default=16)
    ap.add_argument("--seccion", type=int, default=1, help="1 = Main A")
    ap.add_argument("--compases", type=int, help="cuantos usar; por defecto, todos")
    ap.add_argument("--pulsos-por-compas", type=float, default=2.0,
                    help="2 para 2/4 o 2/2; 4 para 4/4")
    ap.add_argument("--pista", default="DRUM")
    ap.add_argument("--bajo", action="store_true",
                    help="anadir un bajo deducido del esqueleto del loop")
    ap.add_argument("--acordes", action="store_true",
                    help="anadir la base armonica en las negras que deja el bajo")
    ap.add_argument("--mid", default="midi/MAPALE-TRIBE-xg.mid",
                    help="a donde escribir el MIDI traducido")
    ap.add_argument("--out", default="M4")
    ap.add_argument("--in", dest="inp", default="M4")
    args = ap.parse_args()

    if args.proyecto.lower().endswith(".mid"):
        notas, bpm = leer_mid(args.proyecto)
    else:
        notas, bpm = leer_als(args.proyecto, args.pista)
    if not notas:
        raise SystemExit("no encontre notas en una pista que contenga %r" % args.pista)
    # **El `+1` de aqui creaba un compas vacio.** El ultimo ataque de un loop de
    # 16 pulsos cae en el 15,4, y sumarle uno daba 16,4, que al redondear hacia
    # arriba pedia 5 compases de 4 pulsos en vez de 4. El quinto salia en blanco
    # y en el punto de loop se oia el hueco. Un loop dura lo que dura su rejilla,
    # no lo que dura su ultima nota: se redondea al compas COMPLETO mas cercano.
    ultimo = max(t for t, _a, _v, _d in notas)
    compases = args.compases or max(1, int(round(
        (ultimo + 0.5) / args.pulsos_por_compas)))
    dur_pulsos = compases * args.pulsos_por_compas
    print("%s — %d notas, %.1f pulsos, tempo del proyecto %.0f"
          % (os.path.basename(args.proyecto), len(notas), dur_pulsos, bpm or 0))
    print("%d compases de %g pulsos\n" % (compases, args.pulsos_por_compas))

    sin_mapa = sorted({a for _t, a, _v, _d in notas if a not in MAPA})
    if sin_mapa:
        print("**%d altura(s) sin traducir: %s**" % (len(sin_mapa), sin_mapa))
        print("Se descartan. Anadelas a MAPA si hacen falta.\n")

    usadas = collections.Counter(a for _t, a, _v, _d in notas if a in MAPA)
    print("traduccion, golpe a golpe:")
    for a, k in sorted(usadas.items(), key=lambda x: -x[1]):
        print("   %3d x%-3d  %s" % (a, k, MAPA[a][2]))

    # a relojes del QY100
    por_pista = collections.defaultdict(list)
    for t, a, v, dur in notas:
        if a not in MAPA:
            continue
        alt, idx, _n = MAPA[a]
        # La duracion de la fuente, no una fija: separa un barrido de un golpe.
        gate = max(1, int(round(dur * F.CLOCKS_PER_QUARTER)))
        por_pista[idx].append(F.Note(alt, max(1, min(127, v)), gate,
                                     int(round(t * F.CLOCKS_PER_QUARTER))))
    if args.bajo:
        SUB, tonica = 12, BAJO_TONICA
        largo = int(args.pulsos_por_compas * F.CLOCKS_PER_QUARTER)
        paso = largo // SUB
        for c in range(compases):
            raiz = tonica + BAJO_PROGRESION[c % len(BAJO_PROGRESION)]
            for k, doce in enumerate(BAJO_DOCEAVOS):
                sig = (BAJO_DOCEAVOS[k + 1] if k + 1 < len(BAJO_DOCEAVOS)
                       else SUB + BAJO_DOCEAVOS[0])
                por_pista[3].append(F.Note(
                    raiz + BAJO_GRADOS[k], 104 if doce == 0 else 88,
                    (sig - doce) * paso - 20, c * largo + doce * paso))

    if args.acordes:
        SUB = 12
        largo = int(args.pulsos_por_compas * F.CLOCKS_PER_QUARTER)
        paso = largo // SUB
        for c in range(compases):
            desp = BAJO_PROGRESION[c % len(BAJO_PROGRESION)]
            # sobre el relativo mayor la triada es mayor, no menor
            voces = (0, 4, 7) if desp == 3 else ACORDE_VOCES
            for k, doce in enumerate(ACORDE_DOCEAVOS):
                for v in voces:
                    por_pista[4].append(F.Note(
                        ACORDE_TONICA + desp + v, 84 if k == 0 else 74,
                        paso * 2 - 20, c * largo + doce * paso))

    print("\npor pista del QY100:")
    for idx in sorted(por_pista):
        print("   %-3s %3d notas" % (DESTINOS[idx], len(por_pista[idx])))

    # --- exportar a MIDI ---
    #
    # **La escritura al QY100 no se hace aqui, a proposito.** `importar.py` ya
    # sabe leer el patron antes de escribirlo, conservar las otras secciones y
    # negarse cuando el volcado llega sin cabecera. Escribir un segundo escritor
    # seria tener dos caminos y que solo uno tenga los guardias.
    #
    # Las pistas salen por el **canal 10 de General MIDI**, que es como
    # `importar.py` sabe que son percusion. Sin eso trataria la tambora como
    # material melodico y le pondria una guitarra.
    import mido
    m = mido.MidiFile(ticks_per_beat=F.CLOCKS_PER_QUARTER)
    cab = mido.MidiTrack(); m.tracks.append(cab)
    # el compas declarado sale de lo que se midio, no de un 4/4 fijo: con
    # --pulsos-por-compas 2 esto escribia 4/4 y el resumen decia "de 4/4".
    cab.append(mido.MetaMessage("time_signature",
                                numerator=int(args.pulsos_por_compas),
                                denominator=4, time=0))
    if bpm:
        cab.append(mido.MetaMessage("set_tempo", tempo=int(60e6 / bpm), time=0))
    for idx in sorted(por_pista):
        tr = mido.MidiTrack(); m.tracks.append(tr)
        tr.append(mido.MetaMessage("track_name", name=DESTINOS[idx], time=0))
        ev = []
        for x in sorted(por_pista[idx], key=lambda y: y.time):
            ev.append((x.time, 1, x.pitch, x.velocity))
            ev.append((x.time + x.gate, 0, x.pitch, 0))
        ev.sort()
        prev = 0
        # **El canal decide si es percusion.** Las tres pistas de tambores van
        # por el 10 de GM (indice 9); el bajo NO, porque `importar.py` mira el
        # canal para elegir kit o voz melodica y un contrabajo por el canal 10
        # saldria tocando platos. Se escribio asi la primera vez.
        canal = 9 if idx < 3 else idx - 2      # 10 = percusion; el resto, melodicas
        for t_, on, alt, vel in ev:
            tr.append(mido.Message("note_on" if on else "note_off", channel=canal,
                                   note=alt, velocity=vel, time=int(t_ - prev)))
            prev = t_
    m.save(args.mid)
    print("\nescrito %s — %d compases de %d/4, %.0f bpm, canal 10"
          % (args.mid, compases, int(args.pulsos_por_compas), bpm or 0))
    print("\npara meterlo al QY100:")
    print("  .venv/bin/python importar.py %s \\" % args.mid)
    print("      --patron %d --seccion %d --compases 1-%d \\"
          % (args.patron, args.seccion, compases))
    print("      %s \\" % " ".join('--pista "%s=%s"' % (DESTINOS[i], DESTINOS[i])
                                    for i in sorted(por_pista)))
    print("      --bpm %.0f --nombre MAPTRIBE --escribir" % (bpm or 120))
    return 0


if __name__ == "__main__":
    sys.exit(main())
