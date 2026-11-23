#!/usr/bin/env python3
"""Genera «QY100 Part», un dispositivo Max MIDI Effect para manejar una parte del QY100.

    .venv/bin/python herramientas/m4l_qy100.py --seco
    .venv/bin/python herramientas/m4l_qy100.py --forzar

**No abre ningún puerto MIDI:** escribe un `.amxd`. Lo que suena lo decide Live.

Va en una pista MIDI **antes del External Instrument** que apunta al canal de la
parte (en la plantilla del rig, la pista QY-100). Manda todo por el canal 1: el
External Instrument lo pasa al canal que tenga elegido. `[M]` Felipe, 2026-11-22:
funciona, y con una pista por canal cada parte se maneja sin tocar las otras.

- **Voz, con nombre y banco.** Dos menús: familia (las 16 de GM, más SFX y kits)
  y voz. Elegir una manda Bank Select MSB (CC 0), LSB (CC 32) y Program Change.
  Los nombres y bancos salen de `datos/bancos.json` (Data List, p. 2-3, 508
  nombres confirmados contra la ROM) y los kits de `datos/voces.json`. La voz se
  guarda en un parámetro de Live (`Voz`) y se vuelve a mandar al abrir el set.
- **Diez perillas con los CC que el QY100 recibe** (Data List, tabla de control
  change), en tres grupos de color: mezcla (volumen 7, pan 10, expresión 11),
  tono (brillo 74, resonancia 71, ataque 73, release 72) y envíos (reverb 91,
  chorus 93, variación 94).
- **El tipo de reverb, chorus y variación**, con las listas del Data List (Effect
  Type List). Son **globales**: cambian el efecto de todo el QY100, no de la
  parte. Por eso solo mandan si el botón `GLOBAL` del dispositivo está encendido;
  se enciende en una sola de las pistas del QY100. El mensaje es el XG Parameter
  Change `F0 43 10 4C 02 01 <00|20|40> MSB LSB F7`. `[M]` El del tipo de reverb,
  mandado desde Python por la Zoom, cambió el sonido (2026-11-22).
- Las notas que llegan pasan sin tocar.

La lógica va en un `v8.codebox` (JavaScript dentro del parche, Max 9.1.5 que trae
Live 12.4.16), así que el `.amxd` no depende de ningún archivo aparte.

`[M]` Live sí deja salir el SysEx del dispositivo por la pista y el External
Instrument: con `GLOBAL` encendido, el tipo de reverb cambió (Felipe, 2026-11-22).
Con `GLOBAL` apagado no manda nada, y así tiene que ser.
"""
import argparse
import json
import os
import struct
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = "QY100 Part.amxd"

# La interfaz del dispositivo va en inglés: se publica (decisión de Felipe, 2026-11-22).
FAMILIAS = ["Piano", "Chromatic Perc.", "Organ", "Guitar", "Bass", "Strings",
            "Ensemble", "Brass", "Reed", "Pipe", "Synth Lead", "Synth Pad",
            "Synth FX", "Ethnic", "Percussive", "Sound FX", "SFX (bank 64)", "Drum Kits"]

# (nombre, CC, valor inicial, grupo)
PERILLAS = [
    ("Volume", 7, 100, "mezcla"), ("Pan", 10, 64, "mezcla"), ("Expression", 11, 127, "mezcla"),
    ("Brightness", 74, 64, "tono"), ("Resonance", 71, 64, "tono"), ("Attack", 73, 64, "tono"),
    ("Release", 72, 64, "tono"),
    ("Reverb", 91, 40, "envios"), ("Chorus", 93, 0, "envios"), ("Variation", 94, 0, "envios"),
]

# Effect Type List del Data List: (nombre, MSB, LSB). El primero de cada lista es «apagado».
REVERBS = [("NO EFFECT", 0x00, 0x00), ("HALL1", 0x01, 0x00), ("HALL2", 0x01, 0x01),
           ("ROOM1", 0x02, 0x00), ("ROOM2", 0x02, 0x01), ("ROOM3", 0x02, 0x02),
           ("STAGE1", 0x03, 0x00), ("STAGE2", 0x03, 0x01), ("PLATE", 0x04, 0x00),
           ("WHITE ROOM", 0x10, 0x00), ("TUNNEL", 0x11, 0x00), ("BASEMENT", 0x13, 0x00)]
CHORUSES = [("NO EFFECT", 0x00, 0x00), ("CHORUS1", 0x41, 0x00), ("CHORUS2", 0x41, 0x01),
            ("CHORUS3", 0x41, 0x02), ("CHORUS4", 0x41, 0x08), ("CELESTE1", 0x42, 0x00),
            ("CELESTE2", 0x42, 0x01), ("CELESTE3", 0x42, 0x02), ("CELESTE4", 0x42, 0x08),
            ("FLANGER1", 0x43, 0x00), ("FLANGER2", 0x43, 0x01), ("FLANGER3", 0x43, 0x08)]
VARIACIONES = REVERBS[:9] + [
    ("DELAY L,C,R", 0x05, 0x00), ("DELAY L,R", 0x06, 0x00), ("ECHO", 0x07, 0x00),
    ("CROSS DELAY", 0x08, 0x00), ("EARLY REF1", 0x09, 0x00), ("EARLY REF2", 0x09, 0x01),
    ("GATE REVERB", 0x0A, 0x00), ("REVERSE GATE", 0x0B, 0x00), ("KARAOKE 1", 0x14, 0x00),
    ("KARAOKE 2", 0x14, 0x01), ("KARAOKE 3", 0x14, 0x02)] + CHORUSES[1:] + [
    ("SYMPHONIC", 0x44, 0x00), ("ROTARY SPEAKER", 0x45, 0x00), ("TREMOLO", 0x46, 0x00),
    ("AUTO PAN", 0x47, 0x00), ("PHASER1", 0x48, 0x00), ("PHASER2", 0x48, 0x08),
    ("DISTORTION", 0x49, 0x00), ("OVER DRIVE", 0x4A, 0x00), ("AMP SIMULATOR", 0x4B, 0x00),
    ("3BAND EQ (MONO)", 0x4C, 0x00), ("2BAND EQ (STEREO)", 0x4D, 0x00),
    ("AUTO WAH (LFO)", 0x4E, 0x00), ("THRU", 0x40, 0x00)]
# (parámetro, título, lista, dirección LSB del tipo, valor de fábrica)
EFECTOS = [("Reverb Type", "REVERB", REVERBS, 0x00, "HALL1"),
           ("Chorus Type", "CHORUS", CHORUSES, 0x20, "CHORUS1"),
           ("Variation Type", "VARIATION", VARIACIONES, 0x40, "DELAY L,C,R")]

def _hex(h):
    return [round(int(h[k:k + 2], 16) / 255, 3) for k in (1, 3, 5)] + [1.0]


# Colores del QY100 (2026-11-22). Se promediaron por zona sobre dos fotos: una del aparato con
# luz cálida y la foto de producto de Yamaha, con fondo azul que enfría todo. A Felipe no le
# gustó la primera paleta, sacada solo de la foto cálida (apagada, caqui): esta toma la carcasa
# plateada y los azules de la foto de producto, y el rojo y el verde corregidos de la dominante.
PLACA = _hex("#d6d7dd")       # carcasa plateada
FONDO = _hex("#334167")       # el marco azul de la pantalla: fondo de los menús
TEXTO_MENU = _hex("#eef0f6")  # texto claro sobre ese azul
TEXTO = _hex("#242c40")       # teclas negras: el texto
TENUE = _hex("#4d5570")       # rótulos chicos
AZUL = _hex("#496496")        # los botones SONG, PATTERN, CARD y MENU
BEIGE = _hex("#b9bac6")       # los botones grises: GLOBAL apagado
GRIS = _hex("#9395ac")        # arco apagado de las perillas
COLOR_GRUPO = {"mezcla": AZUL,
               "tono": _hex("#b8433f"),      # el botón rojo de grabar
               "envios": _hex("#2f8a63")}    # el LED verde   # el verde agua de la pantalla


def voces():
    """[[familia, nombre, msb, lsb, pc]] con pc contado desde 0, como va en el byte."""
    bancos = json.load(open(os.path.join(RAIZ, "datos/bancos.json"), encoding="utf-8"))["voces"]
    kits = json.load(open(os.path.join(RAIZ, "datos/voces.json"), encoding="utf-8"))["kits"]
    out = []
    for v in sorted(bancos, key=lambda v: (v["msb"], v["programa"], v["banco"])):
        pc = v["programa"] - 1
        if v["msb"] == 0:
            etiqueta = "%03d %s" % (v["programa"], v["nombre"]) + ("" if v["banco"] == 0 else "  ·%d" % v["banco"])
            out.append([pc // 8, etiqueta, 0, v["banco"], pc])
        elif v["msb"] == 64:
            out.append([16, "%03d %s" % (v["programa"], v["nombre"]), 64, v["banco"], pc])
    for k in sorted(kits, key=lambda k: (k["banco"], k["programa"])):
        out.append([17, "%03d %s" % (k["pgm"], k["nombre"]), k["banco"], 0, k["programa"]])
    return out


CODIGO = r"""
// QY100 Part: generado por herramientas/m4l_qy100.py. No editar a mano.
inlets = 1;
outlets = 7;   // 0: MIDI (listas de bytes)  1: menú familia  2: menú voz  3: parámetro Voz
               // 4-6: menús de tipo de reverb, chorus y variación (para reflejar otra copia)

const FAM = __FAMILIAS__;
const V = __VOCES__;            // [familia, nombre, msb, lsb, pc]
const EF = __EFECTOS__;         // {reverb: [lsbDireccion, [[msb, lsb], ...]], ...}
const POR_FAM = FAM.map((_, f) => V.map((v, i) => [v, i]).filter(x => x[0][0] === f).map(x => x[1]));

let familiaActual = -1;
let vozActual = 0;
let global_ = 0;
const tipos = {};               // último tipo elegido de cada efecto, para mandarlo al encender GLOBAL

function llenarFamilias() {
  outlet(1, "clear");
  FAM.forEach(n => outlet(1, "append", n));
}

function llenarVoces(f) {
  if (f === familiaActual) return;
  familiaActual = f;
  outlet(2, "clear");
  POR_FAM[f].forEach(i => outlet(2, "append", V[i][1]));
}

function mostrar(i) {
  const f = V[i][0];
  llenarVoces(f);
  outlet(1, "set", f);
  outlet(2, "set", POR_FAM[f].indexOf(i));
}

function mandar(i) {
  const v = V[i];
  outlet(0, [176, 0, v[2]]);
  outlet(0, [176, 32, v[3]]);
  outlet(0, [192, v[4]]);
}

function init() {
  llenarFamilias();
  mostrar(vozActual);
}

// Elegir familia ya cambia el sonido: queda la primera voz de esa familia (pedido de Felipe,
// 2026-11-22: antes solo llenaba el menú y el QY100 no cambiaba hasta elegir la voz).
function familia(f) {
  llenarVoces(f);
  const i = POR_FAM[f][0];
  if (i === undefined) return;
  vozActual = i;
  outlet(2, "set", 0);
  outlet(3, "set", i);
  mandar(i);
}

function voz(n) {
  const i = POR_FAM[familiaActual][n];
  if (i === undefined) return;
  vozActual = i;
  outlet(3, "set", i);
  mandar(i);
}

function restaurar(i) {
  i = Math.max(0, Math.min(V.length - 1, Math.round(i)));
  vozActual = i;
  if (familiaActual < 0) llenarFamilias();
  mostrar(i);
  mandar(i);
}

function cc(n, valor) {
  outlet(0, [176, n, Math.max(0, Math.min(127, Math.round(valor)))]);
}

// Tipo de efecto: XG Parameter Change, dirección 02 01 <00|20|40>. Global: solo con GLOBAL encendido.
function mandarTipo(ef) {
  if (!global_ || tipos[ef] === undefined) return;
  const [dir, lista] = EF[ef];
  const t = lista[tipos[ef]];
  if (!t) return;
  outlet(0, [240, 67, 16, 76, 2, 1, dir, t[0], t[1], 247]);
}

const MENU_EF = {reverb: 4, chorus: 5, variation: 6};

// Las copias del dispositivo se avisan entre sí por un nombre global de Max: la que tiene
// GLOBAL encendido anuncia cada tipo que manda, y las demás solo lo muestran.
function anunciar(ef) {
  if (global_ && tipos[ef] !== undefined) messnamed("qy100.efectos", ef, tipos[ef]);
}

function tipo(ef, i) {
  tipos[ef] = Math.round(i);
  mandarTipo(ef);
  anunciar(ef);
}

function global(v) {
  global_ = v ? 1 : 0;
  if (global_) Object.keys(tipos).forEach(ef => { mandarTipo(ef); anunciar(ef); });
}

// de otra copia (o de esta misma: con GLOBAL encendido se ignora)
function recibido(ef, i) {
  if (global_ || MENU_EF[ef] === undefined) return;
  tipos[ef] = Math.round(i);
  outlet(MENU_EF[ef], "set", tipos[ef]);
}
"""


# ---------------------------------------------------------------- piezas del parche
def caja(id_, maxclass, rect, **extra):
    b = {"id": id_, "maxclass": maxclass, "patching_rect": rect, "numinlets": 1}
    b.update(extra)
    return {"box": b}


def objeto(id_, texto, rect, numoutlets=1, outlettype=("",)):
    return caja(id_, "newobj", rect, text=texto, numoutlets=numoutlets, outlettype=list(outlettype))


def linea(a, sa, b, sb):
    return {"patchline": {"source": [a, sa], "destination": [b, sb]}}


def rotulo(id_, texto, pres, color=TENUE, tam=9.0, negrita=0):
    return caja(id_, "live.comment", [20, 600, 120, 18], numoutlets=0, text=texto,
                textjustification=0, fontsize=tam, fontface=negrita, textcolor=color,
                presentation=1, presentation_rect=pres)


def parametro(longname, shortname, tipo, **valores):
    v = {"parameter_longname": longname, "parameter_shortname": shortname, "parameter_type": tipo,
         "parameter_unitstyle": 0}
    v.update(valores)
    return {"saved_attribute_attributes": {"valueof": v}}


def parche(vs):
    cajas, lineas = [], []
    efectos_js = {titulo.lower(): [dir_, [[m, l] for _, m, l in lista]]
                  for _, titulo, lista, dir_, _ in EFECTOS}
    codigo = (CODIGO.replace("__FAMILIAS__", json.dumps(FAMILIAS, ensure_ascii=False))
                    .replace("__VOCES__", json.dumps(vs, ensure_ascii=False))
                    .replace("__EFECTOS__", json.dumps(efectos_js, ensure_ascii=False)))

    # Las placas de cada bloque, en la capa de fondo (`background`). `[M]` 2026-11-22: un panel
    # de fondo puesto solo por orden en la lista quedó ENCIMA de todo y el dispositivo se vio
    # negro; por eso no hay panel general (el fondo es el de Live) y las placas no se tocan.
    for k, (x, w) in enumerate([(4, 196), (204, 330), (538, 174)]):
        cajas.append(caja("placa_%d" % k, "panel", [600, 450 + 30 * k, 100, 20], numoutlets=0,
                          bgcolor=PLACA, border=0, rounded=6, background=1, presentation=1,
                          presentation_rect=[x, 4, w, 161]))

    # MIDI: lo que entra pasa; lo que genera el codebox sale byte a byte
    cajas.append(objeto("entra", "midiin", [20, 20, 50, 22], outlettype=["int"]))
    cajas.append(objeto("sale", "midiout", [20, 500, 55, 22], numoutlets=0, outlettype=[]))
    cajas.append(objeto("bytes", "iter", [120, 460, 40, 22]))
    lineas += [linea("entra", 0, "sale", 0), linea("bytes", 0, "sale", 0)]

    cajas.append(caja("logica", "v8.codebox", [120, 160, 420, 260], code=codigo, filename="none",
                      fontname="Menlo", fontsize=10.0, numoutlets=7, outlettype=[""] * 7,
                      saved_object_attributes={"parameter_enable": 0}))
    lineas.append(linea("logica", 0, "bytes", 0))

    cajas.append(objeto("dispositivo", "live.thisdevice", [120, 20, 90, 22], numoutlets=3,
                        outlettype=["bang", "int", "int"]))
    cajas.append(objeto("t_init", "t init", [120, 90, 40, 22]))
    lineas += [linea("dispositivo", 0, "t_init", 0), linea("t_init", 0, "logica", 0)]

    # ---- columna VOZ
    cajas.append(rotulo("r_titulo", "QY100 · PART", [12, 8, 180, 16], color=FONDO,
                        tam=11.0, negrita=1))
    cajas.append(rotulo("r_familia", "FAMILY", [12, 30, 100, 13]))
    estilo_menu = dict(numoutlets=3, outlettype=["int", "", ""], parameter_enable=0, items=[],
                       bgcolor=FONDO, bgfillcolor_type="color", bgfillcolor_color=FONDO,
                       textcolor=TEXTO_MENU, color=TEXTO_MENU, fontname="Arial", arrow=1)
    cajas.append(caja("menu_familia", "umenu", [600, 20, 140, 22], fontsize=10.0,
                      presentation=1, presentation_rect=[12, 44, 180, 20], **estilo_menu))
    cajas.append(rotulo("r_voz", "VOICE", [12, 70, 100, 13]))
    cajas.append(caja("menu_voz", "umenu", [760, 20, 170, 22], fontsize=12.0,
                      presentation=1, presentation_rect=[12, 84, 180, 24], **estilo_menu))
    cajas.append(objeto("p_familia", "prepend familia", [600, 60, 100, 22]))
    cajas.append(objeto("p_voz", "prepend voz", [760, 60, 80, 22]))
    lineas += [linea("menu_familia", 0, "p_familia", 0), linea("p_familia", 0, "logica", 0),
               linea("menu_voz", 0, "p_voz", 0), linea("p_voz", 0, "logica", 0),
               linea("logica", 1, "menu_familia", 0), linea("logica", 2, "menu_voz", 0)]

    cajas.append(caja("param_voz", "live.numbox", [600, 120, 50, 15], numoutlets=2,
                      outlettype=["", "float"], parameter_enable=1, varname="Voice",
                      presentation=1, presentation_rect=[12, 120, 44, 15],
                      **parametro("Voice", "Voice", 1, parameter_mmin=0.0,
                                  parameter_mmax=float(len(vs) - 1), parameter_initial_enable=1,
                                  parameter_initial=[0])))
    cajas.append(rotulo("r_indice", "voice no. (sends bank + PC)", [60, 121, 132, 13], tam=8.0))
    cajas.append(objeto("p_restaurar", "prepend restaurar", [600, 150, 110, 22]))
    lineas += [linea("param_voz", 0, "p_restaurar", 0), linea("p_restaurar", 0, "logica", 0),
               linea("logica", 3, "param_voz", 0)]

    # ---- columna PERILLAS: mezcla y envíos arriba, tono abajo
    cajas.append(rotulo("r_mezcla", "MIX", [212, 6, 90, 13], color=COLOR_GRUPO["mezcla"]))
    cajas.append(rotulo("r_envios", "SENDS", [380, 6, 90, 13], color=COLOR_GRUPO["envios"]))
    cajas.append(rotulo("r_tono", "TONE", [212, 86, 90, 13], color=COLOR_GRUPO["tono"]))
    posiciones = {"Volume": (210, 20), "Pan": (264, 20), "Expression": (318, 20),
                  "Reverb": (378, 20), "Chorus": (432, 20), "Variation": (486, 20),
                  "Brightness": (210, 100), "Resonance": (264, 100), "Attack": (318, 100),
                  "Release": (372, 100)}
    for nombre, cc, inicial, grupo in PERILLAS:
        x, y = posiciones[nombre]
        did, pid = "dial_%d" % cc, "p_cc_%d" % cc
        cajas.append(caja(did, "live.dial", [960 + (cc % 5) * 60, 20 + (cc // 30) * 90, 44, 48],
                          numoutlets=2, outlettype=["", "float"], parameter_enable=1, varname=nombre,
                          activedialcolor=COLOR_GRUPO[grupo], activeneedlecolor=COLOR_GRUPO[grupo], dialcolor=GRIS, needlecolor=TEXTO,
                          textcolor=TEXTO, presentation=1, presentation_rect=[x, y, 50, 58],
                          **parametro(nombre, nombre, 1, parameter_mmin=0.0, parameter_mmax=127.0,
                                      parameter_initial_enable=1, parameter_initial=[inicial])))
        cajas.append(objeto(pid, "prepend cc %d" % cc, [960 + (cc % 5) * 60, 75 + (cc // 30) * 90, 70, 22]))
        lineas += [linea(did, 0, pid, 0), linea(pid, 0, "logica", 0)]

    # ---- columna EFECTOS (GLOBAL)
    cajas.append(rotulo("r_efectos", "EFFECTS · WHOLE QY100", [546, 8, 160, 13],
                        color=COLOR_GRUPO["tono"]))
    cajas.append(caja("global", "live.text", [1300, 20, 60, 18], numoutlets=2, outlettype=["", ""],
                      parameter_enable=1, varname="Global", text="GLOBAL", texton="GLOBAL",
                      activebgoncolor=COLOR_GRUPO["tono"], bgoncolor=COLOR_GRUPO["tono"], bgcolor=BEIGE, activebgcolor=BEIGE, textcolor=TEXTO,
                      # Live usa los colores «active*» con el dispositivo encendido: sin ellos, el
                      # texto apagado salía gris claro sobre gris claro (captura de Felipe, 2026-11-22)
                      activetextcolor=TEXTO, activetextoncolor=_hex("#ffffff"), textoncolor=_hex("#ffffff"),
                      bordercolor=TENUE, focusbordercolor=TENUE,
                      presentation=1, presentation_rect=[546, 24, 56, 16],
                      **parametro("Global", "Global", 2, parameter_enum=["off", "on"],
                                  parameter_mmax=1.0, parameter_initial_enable=1,
                                  parameter_initial=[0])))
    cajas.append(rotulo("r_global", "on one track only", [606, 25, 100, 13], tam=8.0))
    cajas.append(objeto("p_global", "prepend global", [1300, 50, 90, 22]))
    lineas += [linea("global", 0, "p_global", 0), linea("p_global", 0, "logica", 0)]
    for k, (longname, titulo, lista, _, defecto) in enumerate(EFECTOS):
        y = 46 + k * 38
        mid, pid = "tipo_%d" % k, "p_tipo_%d" % k
        cajas.append(rotulo("r_tipo_%d" % k, titulo, [546, y, 120, 12], tam=8.0))
        cajas.append(caja(mid, "live.menu", [1300, 100 + k * 60, 120, 15], numoutlets=3,
                          outlettype=["", "", "float"], parameter_enable=1, varname=longname,
                          textcolor=TEXTO_MENU, activebgcolor=FONDO, bgcolor=FONDO, presentation=1, presentation_rect=[546, y + 13, 158, 16],
                          **parametro(longname, titulo.title(), 2,
                                      parameter_enum=[n for n, _, _ in lista],
                                      parameter_mmax=float(len(lista) - 1),
                                      parameter_initial_enable=1,
                                      parameter_initial=[[n for n, _, _ in lista].index(defecto)])))
        cajas.append(objeto(pid, "prepend tipo %s" % titulo.lower(), [1300, 125 + k * 60, 130, 22]))
        lineas += [linea(mid, 0, pid, 0), linea(pid, 0, "logica", 0), linea("logica", 4 + k, mid, 0)]
    # lo que anuncian las otras copias
    cajas.append(objeto("r_efectos_red", "r qy100.efectos", [1460, 100, 110, 22]))
    cajas.append(objeto("p_recibido", "prepend recibido", [1460, 130, 110, 22]))
    lineas += [linea("r_efectos_red", 0, "p_recibido", 0), linea("p_recibido", 0, "logica", 0)]

    return {"patcher": {
        "fileversion": 1,
        "appversion": {"major": 9, "minor": 1, "revision": 5, "architecture": "x64", "modernui": 1},
        "classnamespace": "box", "rect": [80, 80, 1500, 640], "openinpresentation": 1,
        "default_fontsize": 10.0, "default_fontface": 0, "default_fontname": "Arial",
        "gridonopen": 1, "gridsize": [8, 8], "boxes": cajas, "lines": lineas,
        "dependency_cache": [], "latency": 0, "is_mpe": 0, "external_mpe_tuning_enabled": 0,
        "minimum_live_version": "", "minimum_max_version": "", "platform_compatibility": 0,
        "autosave": 0, "devicewidth": 716.0,
    }}


def amxd(p):
    """La cabecera de un Max MIDI Effect y el parche en JSON."""
    datos = json.dumps(p, ensure_ascii=False, indent=1).encode("utf-8") + b"\n\x00"
    return (b"ampf" + struct.pack("<I", 4) + b"mmmm" + b"meta" + struct.pack("<I", 4)
            + struct.pack("<I", 0) + b"ptch" + struct.pack("<I", len(datos)) + datos)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--salida", default=SALIDA)
    ap.add_argument("--forzar", action="store_true")
    ap.add_argument("--seco", action="store_true")
    a = ap.parse_args()

    vs = voces()
    por = [sum(1 for v in vs if v[0] == f) for f in range(len(FAMILIAS))]
    print("  %d voces en %d familias: %s" % (len(vs), len(FAMILIAS),
          ", ".join("%s %d" % (n, c) for n, c in zip(FAMILIAS, por))))
    print("  perillas: " + ", ".join("%s CC%d" % (n, c) for n, c, _, _ in PERILLAS))
    print("  efectos: " + ", ".join("%s %d tipos" % (t, len(l)) for _, t, l, _, _ in EFECTOS))
    datos = amxd(parche(vs))
    print("  %d bytes" % len(datos))
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
