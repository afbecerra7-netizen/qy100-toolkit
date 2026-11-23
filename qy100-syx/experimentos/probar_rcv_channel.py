#!/usr/bin/env python3
"""Prueba si `Rcv Channel = Off` calla una parte del QY100 sin tocar al sinte, y cómo se deshace.

    .venv/bin/python experimentos/probar_rcv_channel.py apagar   --canal 4 --puerto L6max
    .venv/bin/python experimentos/probar_rcv_channel.py devolver --canal 4 --puerto L6max
    .venv/bin/python experimentos/probar_rcv_channel.py devolver --todos  --puerto L6max
    .venv/bin/python experimentos/probar_rcv_channel.py apagar   --canal 4 --seco

**La pregunta.** Las notas que entran por el `MIDI IN` del QY100 suenan en su
generador y, con `ECHO BACK = Thru`, también en el sinte de ese canal: el doble
sonido. `[M]` Callarlo con el volumen de la parte no sirve: el 2026-11-22, bajar
la parte 4 bajó también el Minitaur, que obedece el CC 7 como nivel de salida.
El candidato es el canal de recepción de la parte en `Off` (Data List, tabla
1-6, `08 nn 04`, `7F = off`). Sin probar `[V]`.

**El mapa parte↔canal es el de fábrica de XG**: la parte `nn` recibe el canal
`nn + 1`. `[D]` La ráfaga de Undo/Redo que capturó Shea lleva `08 0N 11` canal
por canal, lo que encaja. Si `apagar --canal 4` no calla nada, lo primero que
se sospecha es este mapa, no el parámetro.

**Deshacerlo.** Tres caminos, del más fino al más bruto:

1. `devolver --canal N`: la parte vuelve a recibir su canal. Solo toca esa parte.
2. `devolver --todos`: las 16 partes, cada una a su canal. Deja el mapa de
   fábrica sin tocar nada más.
3. Apagar y prender el QY100. `[M]` El `Off` no sobrevive al apagado
   (2026-11-22): al prender, volvieron a sonar los dos.

`XG System On` (`F0 43 10 4C 00 00 7E 00 F7`, ya en `probar_variation.py xg-on`)
también los devuelve, `[D]` pero pone de fábrica **todo** el generador (voces,
volúmenes, efectos) hasta que se vuelva a elegir el patrón. Solo si lo demás falla.

**La prueba, con comparaciones.** El patrón parado y nadie tocando el panel
mientras se manda algo: un mensaje durante el uso del panel cuelga el QY100.

    0. Desde Ableton, notas por el canal 4.     ¿Suenan el Minitaur y el QY100?
    1. apagar --canal 4. Las mismas notas.      ¿Suena solo el Minitaur?
                                                ¿Igual de fuerte que en el 0?
    2. Un patrón sonando, con la pista BA.      ¿El BA sigue en el Minitaur?
                                                ¿Suena también por dentro?
    3. Otro patrón, y las notas del 1.          ¿Sigue callado el QY100?
    4. devolver --canal 4. Las notas del 0.     ¿Vuelven a sonar los dos?
    5. apagar --canal 4, apagar y prender.      ¿Vuelven a sonar los dos?

El 2 dice si el parámetro calla también al secuenciador del propio QY100, el 3
si cambiar de patrón lo borra, y el 5 si sobrevive al apagado. Cada respuesta
cambia cómo se usa en el set y en el mute de E36.

Con `ECHO BACK = Thru` el SysEx también sale hacia la THRU-6 y llega a todos los
sintes. `[D]` Un SysEx de Yamaha no lo toma ningún otro aparato del rig, porque
cada uno filtra por su propio ID de fabricante.
"""

import argparse
import sys

#: Parte XG, dirección y valor. `F0 43 1n 4C 08 nn 04 vv F7`, con n = 0.
RCV_OFF = 0x7F


def mensaje_rcv(parte: int, canal) -> bytes:
    """El Parameter Change de `Rcv Channel`. `canal` es 1..16, o None para Off."""
    if not 0 <= parte <= 15:
        raise ValueError("parte fuera de 0..15: %r" % parte)
    if canal is None:
        valor = RCV_OFF
    elif 1 <= canal <= 16:
        valor = canal - 1
    else:
        raise ValueError("canal fuera de 1..16: %r" % canal)
    return bytes([0xF0, 0x43, 0x10, 0x4C, 0x08, parte, 0x04, valor, 0xF7])


def plan(modo: str, canal, todos: bool):
    """Lista de (etiqueta, bytes). Sin MIDI: se puede mirar con --seco."""
    if todos:
        if modo != "devolver":
            raise SystemExit("--todos solo va con devolver: apagar las 16 partes "
                             "callaría el QY100 entero.")
        return [("parte %2d <- canal %2d" % (p, p + 1), mensaje_rcv(p, p + 1))
                for p in range(16)]
    if canal is None or not 1 <= canal <= 16:
        raise SystemExit("falta --canal 1..16, o --todos para devolver.")
    parte = canal - 1
    if modo == "apagar":
        return [("parte %2d (canal %2d) -> Off" % (parte, canal),
                 mensaje_rcv(parte, None))]
    return [("parte %2d <- canal %2d" % (parte, canal), mensaje_rcv(parte, canal))]


def abrir(subcadena: str):
    import mido
    nombres = mido.get_output_names()
    hallados = [n for n in nombres if subcadena.lower() in n.lower()]
    # El puerto del mezclador de la Zoom también dice «L6max»: se excluye, porque
    # lo que vaya ahí lo toma la Zoom y no llega al QY100.
    hallados = [n for n in hallados if "mixer" not in n.lower()
                and "editor" not in n.lower()] or hallados
    if len(hallados) != 1:
        print("--puerto %r no deja un puerto y solo uno. Los que hay:" % subcadena)
        for n in nombres:
            print("   ", n)
        raise SystemExit(1)
    print("puerto:", hallados[0])
    return mido.open_output(hallados[0])


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("modo", choices=["apagar", "devolver"])
    ap.add_argument("--canal", type=int, help="canal MIDI 1..16")
    ap.add_argument("--todos", action="store_true",
                    help="con devolver: las 16 partes a su canal")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--puerto", help="parte del nombre del puerto de salida")
    g.add_argument("--seco", action="store_true", help="solo imprime los bytes")
    args = ap.parse_args()

    mensajes = plan(args.modo, args.canal, args.todos)
    if args.seco:
        for etq, raw in mensajes:
            print("   %-28s %s" % (etq, raw.hex(" ").upper()))
        return

    import mido
    out = abrir(args.puerto)
    try:
        for etq, raw in mensajes:
            print("   %-28s %s" % (etq, raw.hex(" ").upper()))
            out.send(mido.Message("sysex", data=raw[1:-1]))
    finally:
        out.close()


if __name__ == "__main__":
    sys.exit(main())
