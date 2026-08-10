"""Lee un clip MIDI de un proyecto de Ableton, lo mide y lo exporta a `.mid`.

    .venv/bin/python analizar_loop.py ~/ruta/Proyecto.als --pista DRUMS \\
        --nombre BULLERENGUE --bpm 80

Existe porque la via para meter ritmos de Tribe en el proyecto es dejarlos en una
pista de Ableton, y hacerlo a mano tres veces seguidas ya es una herramienta.

## Que mide, y por que esas dos cosas

**La repeticion entre compases** — el porcentaje de compases con exactamente el
mismo patron de ataques. Es la misma medida que separo la celda del bambuco de
las decisiones del arreglista, y decide **que se puede hacer con el material**:

    > 80 %   hay una celda: se puede convertir en un motor generativo
    50-80 %  celda con variacion; extraible con cuidado
    < 50 %   es un arreglo, no un patron. Va como loop de audio y punto

El porro y el chande dan 25 %: sus cuatro compases son todos distintos. No hay
nada que extraer, y forzarlo produciria una version pobre del original.

**El compas real**, probando la dispersion de los ataques al plegar el clip en
2, 3 y 4 tiempos. Mas dispersion es mas estructura metrica: si al plegar cada
dos tiempos los golpes se concentran, la celda es de 2/4 aunque Ableton diga
4/4. El chande salio asi. El currulao salio 3/4 contra el 4/4 declarado.

Un reparto plano no significa "sin ritmo", significa que ese no es el compas:
doblar un patron de tres sobre una rejilla de cuatro promedia y borra los huecos.
Y **un hueco es informacion** — la sexta corchea vacia es lo que identifica al
bambuco de salon.
"""
import argparse
import collections
import gzip
import os
import xml.etree.ElementTree as ET

import mido

NOMBRES = "C Cs D Ds E F Fs G Gs A As B".split()


def nota(n):
    return "%s%d" % (NOMBRES[n % 12], n // 12 - 1)


def leer(ruta, filtro):
    """Eventos (tiempo_en_pulsos, altura, velocity, duracion) del primer clip."""
    raiz = ET.fromstring(gzip.open(ruta).read())
    for tr in raiz.iter("MidiTrack"):
        nom = tr.find(".//EffectiveName").get("Value")
        if filtro.lower() not in nom.lower():
            continue
        clips = list(tr.iter("MidiClip"))
        if not clips:
            continue
        ev = [(float(e.get("Time")), int(k.find("MidiKey").get("Value")),
               int(float(e.get("Velocity"))), float(e.get("Duration")))
              for k in clips[0].iter("KeyTrack")
              for e in k.iter("MidiNoteEvent")]
        return nom, sorted(ev)
    return None, []


def compas_probable(ev):
    """Prueba 2, 3 y 4 tiempos y devuelve el reparto de cada uno."""
    salida = []
    for beats in (2, 3, 4):
        pos = collections.Counter(
            int(round((t % beats) * 4)) % (beats * 4) for t, *_ in ev)
        fila = [pos.get(i, 0) for i in range(beats * 4)]
        m = sum(fila) / float(len(fila))
        disp = (sum((v - m) ** 2 for v in fila) / len(fila)) ** 0.5
        salida.append((beats, fila, disp))
    return salida


def repeticion(ev, beats):
    """% de compases que repiten exactamente el mismo patron de ataques."""
    comp = collections.defaultdict(set)
    for t, a, _v, _d in ev:
        comp[int(t // beats)].add((int(round((t % beats) * 4)), a))
    if not comp:
        return 0, 0
    cuenta = collections.Counter(frozenset(v) for v in comp.values())
    return len(comp), 100 * cuenta.most_common(1)[0][1] // len(comp)


def exportar(ev, ruta, bpm, beats):
    TPB = 480
    m = mido.MidiFile(ticks_per_beat=TPB)
    cab = mido.MidiTrack()
    m.tracks.append(cab)
    cab.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
    cab.append(mido.MetaMessage("time_signature", numerator=beats,
                                denominator=4, time=0))
    mt = mido.MidiTrack()
    m.tracks.append(mt)
    mt.append(mido.MetaMessage("track_name",
                               name=os.path.basename(ruta)[:-4], time=0))
    cola = []
    for t, a, v, d in ev:
        cola.append((int(round(t * TPB)), "note_on", a, v))
        cola.append((int(round((t + d) * TPB)), "note_off", a, 0))
    cola.sort()
    prev = 0
    for t, tipo, a, v in cola:
        mt.append(mido.Message(tipo, note=a, velocity=v, time=t - prev))
        prev = t
    m.save(ruta)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("proyecto")
    ap.add_argument("--pista", default="DRUMS")
    ap.add_argument("--nombre", required=True)
    ap.add_argument("--bpm", type=float, required=True)
    ap.add_argument("--compas", type=int, help="por defecto, el mas probable")
    ap.add_argument("--dir", default="midi")
    args = ap.parse_args()

    nom, ev = leer(os.path.expanduser(args.proyecto), args.pista)
    if not ev:
        raise SystemExit("no encuentro clips en una pista que contenga %r"
                         % args.pista)

    hist = collections.Counter(a for _t, a, _v, _d in ev)
    vel = collections.defaultdict(list)
    for _t, a, v, _d in ev:
        vel[a].append(v)
    largo = max(t + d for t, _a, _v, d in ev)
    print("%s — pista %r, %d notas, %d alturas, %.0f pulsos"
          % (args.nombre, nom, len(ev), len(hist), largo))

    print("\ninstrumentos (por uso):")
    for a, n in sorted(hist.items(), key=lambda x: -x[1]):
        print("   %-5s %4d %4d golpes   vel media %3d"
              % (nota(a), a, n, sum(vel[a]) // len(vel[a])))

    print("\ncompas probable:")
    pruebas = compas_probable(ev)
    mejor = max(pruebas, key=lambda x: x[2])
    for beats, fila, disp in pruebas:
        marca = "  <-- el mas estructurado" if beats == mejor[0] else ""
        print("   %d/4  %-52s disp %4.1f%s"
              % (beats, " ".join("%2d" % v for v in fila), disp, marca))

    # **El periodo de la celula no es el compas**, y confundirlos escribio un
    # bullerengue como 2/4 cuando Tribe lo publica en 4/4. La celula del chande
    # y la del bullerengue se repiten cada dos tiempos dentro de un compas de
    # cuatro, igual que la del bambuco de salon ocupa seis corcheas dentro de un
    # 6/8. Lo que se mide arriba es util para colocar acentos; **la notacion la
    # dice la fuente**, y por eso `--compas` manda y el defecto es 4.
    beats = args.compas or 4
    if mejor[0] != beats:
        print("   (la celula se repite cada %d tiempos, pero se escribe en %d/4;"
              " usa --compas si la fuente dice otra cosa)" % (mejor[0], beats))
    n_comp, rep = repeticion(ev, beats)
    print("\n%d compases de %d/4, repeticion %d%%" % (n_comp, beats, rep))
    if rep >= 80:
        print("   hay celda: se puede convertir en motor generativo")
    elif rep >= 50:
        print("   celda con variacion; extraible con cuidado")
    else:
        print("   es un ARREGLO, no un patron. Va como loop de audio")

    # **Ableton solo escribe el `.als` al guardar**, asi que si el usuario cambia
    # el clip y no pulsa Cmd+S, aqui se lee el anterior y se exporta con el
    # nombre nuevo. Paso una vez: un `puya` que era el bullerengue, identico en
    # las 115 notas. Un archivo bien formado con la etiqueta equivocada no lo
    # detecta ninguna comprobacion posterior.
    os.makedirs(args.dir, exist_ok=True)
    huella = sorted((round(t, 4), a, v) for t, a, v, _d in ev)
    for otro in sorted(os.listdir(args.dir)):
        if not otro.endswith("-loop.mid") or otro.startswith(args.nombre):
            continue
        try:
            m = mido.MidiFile(os.path.join(args.dir, otro))
        except Exception:
            continue
        prev, otros = 0, []
        for msg in mido.merge_tracks(m.tracks):
            prev += msg.time
            if msg.type == "note_on" and msg.velocity:
                otros.append((round(prev / float(m.ticks_per_beat), 4),
                              msg.note, msg.velocity))
        if sorted(otros) == huella:
            raise SystemExit(
                "\nESTE CLIP ES IDENTICO A %s — no se exporta nada.\n"
                "Ableton solo escribe el proyecto al guardar: pulsa Cmd+S y "
                "vuelve a lanzarlo." % otro)

    ruta = os.path.join(args.dir, "%s-loop.mid" % args.nombre)
    exportar(ev, ruta, args.bpm, beats)
    print("\nguardado en %s  (%.0f bpm, %d/4)" % (ruta, args.bpm, beats))
