#!/usr/bin/env python3
"""Genera «QY100 Silence», un dispositivo Max MIDI Effect para elegir qué canales ignora el QY100.

    .venv/bin/python herramientas/m4l_qy100_silencio.py --seco
    .venv/bin/python herramientas/m4l_qy100_silencio.py

**No abre ningún puerto MIDI:** escribe un `.amxd`. Va en una pista cuyo External
Instrument apunte al QY100 (en la plantilla del rig, la pista QY-100), como «QY100 Part».

**Para qué.** Las notas que entran al QY100 suenan en su generador y además, con
`ECHO BACK = Thru`, en el sinte de ese canal: el doble sonido. `[M]` Lo calla el
canal de recepción de la parte en `Off` (`F0 43 10 4C 08 nn 04 7F F7`), y **no
sobrevive al apagado** (2026-11-22, ver `docs/qy100-protocolo.md`). Por eso es un
botón que se aprieta al empezar la sesión.

- **16 botones, uno por canal.** Encendido = el QY100 ignora ese canal. Se guardan
  con el set. De fábrica vienen encendidos los de los sintes del rig: 1, 3, 4, 5 y
  6 (el barrido de canales del 2026-08-09).
- **SEND** manda los 16: los encendidos en `Off` y los apagados de vuelta a su
  canal. Así el QY100 queda igual a lo que muestra el dispositivo, sea cual sea su
  estado anterior. Apretar un botón no manda nada; solo SEND.
- **RESTORE ALL** devuelve las 16 partes a su canal sin mover los botones. Apagar y
  prender el QY100 hace lo mismo.
- Las notas que llegan pasan sin tocar.

`[D]` La parte `nn` recibe el canal `nn + 1` (el mapa de fábrica de XG). `[M]` Así
se probó en el canal 4. `[M]` Live deja salir el SysEx de un dispositivo por la
pista y el External Instrument («QY100 Part», 2026-11-22). `[M]` Con SEND desde Live los
sintes quedaron sonando solos (Felipe, 2026-11-22).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from m4l_qy100 import (AZUL, BEIGE, COLOR_GRUPO, FONDO, PLACA, TENUE, TEXTO,  # noqa: E402
                       _hex, amxd, caja, linea, objeto, parametro, rotulo)

SALIDA = "QY100 Silence.amxd"

CALLADOS = (1, 3, 4, 5, 6)
# Lo que hay en cada canal en el rig. Solo es un rótulo.
NOMBRES = {1: "DRUMBRUTE", 2: "QY D2", 3: "RIDDIM", 4: "MINITAUR", 5: "VOLCA",
           6: "LEMONDROP", 7: "QY C3", 8: "QY C4"}
ROJO = COLOR_GRUPO["tono"]
BLANCO = _hex("#ffffff")

CODIGO = r"""
// QY100 Silence: generado por herramientas/m4l_qy100_silencio.py. No editar a mano.
inlets = 1;
outlets = 1;   // MIDI, como listas de bytes

const calla = new Array(16).fill(0);

function mute(canal, v) {
  if (canal >= 1 && canal <= 16) calla[canal - 1] = v ? 1 : 0;
}

// XG Multi Part, Rcv Channel: F0 43 10 4C 08 <parte> 04 <canal-1 | 7F> F7
function rcv(parte, valor) {
  outlet(0, [240, 67, 16, 76, 8, parte, 4, valor, 247]);
}

// Un botón de Live puede mandar 1 al apretar y 0 al soltar: solo cuenta el primero.
function enviar(v) {
  if (v === 0) return;
  for (let p = 0; p < 16; p++) rcv(p, calla[p] ? 127 : p);
  post("QY100 Silence: muted " + (calla.map((c, i) => c ? i + 1 : 0).filter(x => x).join(" ") || "none") + "\n");
}

function devolver(v) {
  if (v === 0) return;
  for (let p = 0; p < 16; p++) rcv(p, p);
  post("QY100 Silence: all 16 parts back to their channel\n");
}
"""

ANCHO_BOTON, ALTO_BOTON, PASO = 46, 20, 50


def boton_canal(c):
    fila, col = divmod(c - 1, 8)
    x, y = 12 + col * PASO, 40 + fila * 46
    bid, pid = "mute_%d" % c, "p_mute_%d" % c
    piezas = [caja(bid, "live.text", [1300 + col * 60, 20 + fila * 80, 44, 18], numoutlets=2,
                   outlettype=["", ""], parameter_enable=1, varname="Mute %d" % c,
                   text=str(c), texton=str(c), mode=1,
                   activebgoncolor=ROJO, bgoncolor=ROJO, bgcolor=BEIGE, activebgcolor=BEIGE,
                   textcolor=TEXTO, activetextcolor=TEXTO, activetextoncolor=BLANCO,
                   textoncolor=BLANCO, bordercolor=TENUE, focusbordercolor=TENUE,
                   presentation=1, presentation_rect=[x, y, ANCHO_BOTON, ALTO_BOTON],
                   **parametro("Mute %d" % c, "Mute %d" % c, 2, parameter_enum=["off", "on"],
                               parameter_mmax=1.0, parameter_initial_enable=1,
                               parameter_initial=[1 if c in CALLADOS else 0])),
              objeto(pid, "prepend mute %d" % c, [1300 + col * 60, 45 + fila * 80, 80, 22])]
    if c in NOMBRES:
        piezas.append(rotulo("r_canal_%d" % c, NOMBRES[c], [x, y + 22, ANCHO_BOTON + 4, 12],
                             tam=7.0))
    return bid, pid, piezas


def boton_accion(id_, texto, mensaje, y, color):
    return [caja(id_, "live.text", [1800, 20 + y, 80, 20], numoutlets=2, outlettype=["", ""],
                 parameter_enable=0, text=texto, texton=texto, mode=0,
                 bgcolor=color, activebgcolor=color, bgoncolor=FONDO, activebgoncolor=FONDO,
                 textcolor=BLANCO, activetextcolor=BLANCO, textoncolor=BLANCO,
                 activetextoncolor=BLANCO, bordercolor=TENUE, focusbordercolor=TENUE,
                 presentation=1, presentation_rect=[420, y, 92, 24]),
            objeto("p_" + id_, "prepend %s" % mensaje, [1800, 50 + y, 90, 22])]


def parche():
    cajas, lineas = [], []
    cajas.append(caja("placa", "panel", [600, 450, 100, 20], numoutlets=0, bgcolor=PLACA,
                      border=0, rounded=6, background=1, presentation=1,
                      presentation_rect=[4, 4, 516, 161]))

    cajas.append(objeto("entra", "midiin", [20, 20, 50, 22], outlettype=["int"]))
    cajas.append(objeto("sale", "midiout", [20, 500, 55, 22], numoutlets=0, outlettype=[]))
    cajas.append(objeto("bytes", "iter", [120, 460, 40, 22]))
    lineas += [linea("entra", 0, "sale", 0), linea("bytes", 0, "sale", 0)]
    cajas.append(caja("logica", "v8.codebox", [120, 160, 420, 260], code=CODIGO, filename="none",
                      fontname="Menlo", fontsize=10.0, numoutlets=1, outlettype=[""],
                      saved_object_attributes={"parameter_enable": 0}))
    lineas.append(linea("logica", 0, "bytes", 0))

    cajas.append(rotulo("r_titulo", "QY100 · SILENCE", [12, 8, 200, 16], color=FONDO,
                        tam=11.0, negrita=1))
    cajas.append(rotulo("r_ayuda", "lit = the QY100 ignores that channel", [12, 23, 260, 13],
                        tam=8.0))
    for c in range(1, 17):
        bid, pid, piezas = boton_canal(c)
        cajas += piezas
        lineas += [linea(bid, 0, pid, 0), linea(pid, 0, "logica", 0)]

    for id_, texto, mensaje, y, color in (("enviar", "SEND", "enviar", 40, AZUL),
                                          ("devolver", "RESTORE ALL", "devolver", 86, TENUE)):
        cajas += boton_accion(id_, texto, mensaje, y, color)
        lineas += [linea(id_, 0, "p_" + id_, 0), linea("p_" + id_, 0, "logica", 0)]
    cajas.append(rotulo("r_nota", "resend after power-off", [420, 66, 96, 13], tam=7.0))
    cajas.append(rotulo("r_nota2", "same as power-cycling", [420, 112, 96, 13], tam=7.0))

    return {"patcher": {
        "fileversion": 1,
        "appversion": {"major": 9, "minor": 1, "revision": 5, "architecture": "x64", "modernui": 1},
        "classnamespace": "box", "rect": [80, 80, 1950, 640], "openinpresentation": 1,
        "default_fontsize": 10.0, "default_fontface": 0, "default_fontname": "Arial",
        "gridonopen": 1, "gridsize": [8, 8], "boxes": cajas, "lines": lineas,
        "dependency_cache": [], "latency": 0, "is_mpe": 0, "external_mpe_tuning_enabled": 0,
        "minimum_live_version": "", "minimum_max_version": "", "platform_compatibility": 0,
        "autosave": 0, "devicewidth": 524.0,
    }}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--salida", default=SALIDA)
    ap.add_argument("--forzar", action="store_true")
    ap.add_argument("--seco", action="store_true")
    a = ap.parse_args()
    p = parche()
    ids = [b["box"]["id"] for b in p["patcher"]["boxes"]]
    assert len(ids) == len(set(ids)), "un id repetido"
    for l in p["patcher"]["lines"]:
        for extremo in ("source", "destination"):
            assert l["patchline"][extremo][0] in ids, "línea a una caja que no existe"
    datos = amxd(p)
    print("  callados de fábrica: %s · %d cajas · %d bytes"
          % (" ".join(map(str, CALLADOS)), len(ids), len(datos)))
    if a.seco:
        print("(seco: no se escribió nada)")
        return
    if os.path.exists(a.salida) and not a.forzar:
        sys.exit("ya existe %s; usa --forzar para sobrescribir" % a.salida)
    os.makedirs(os.path.dirname(a.salida), exist_ok=True)
    open(a.salida, "wb").write(datos)
    print("escrito:", a.salida)


if __name__ == "__main__":
    main()
