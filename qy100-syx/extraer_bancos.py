#!/usr/bin/env python3
"""Saca el `bank LSB` de cada voz XG del Data List, y lo cruza contra la ROM.

    .venv/bin/python extraer_bancos.py

**El problema que resuelve.** `voces.json` trae los 525 nombres de voz sacados
de la ROM del firmware, en orden, pero **solo los primeros 128 son
direccionables**: el indice equivale al program change hasta el 127 y de ahi en
adelante son variaciones cuyo banco nunca se decodifico. Eso limitaba el
navegador de voces de la app a 128 de 525 — anotado en `HALLAZGOS.md` como uno
de los pendientes.

**Y no hacia falta barrer el equipo: estaba en el Data List.** Pagina 2,
encabezado: `Bank Select  MSB=000, LSB=Bank Number`. La tabla trae, por voz,
el numero de programa y el de banco.

Formato de la tabla, leido sin `-layout` para que las cuatro columnas salgan en
orden de lectura y no entrelazadas:

    1              programa nuevo
    0              banco
    GrandPno 1     nombre y numero de elementos
    1              otro banco DEL MISMO programa
    GrndPnoK 1
    18
    MelloGrP       a veces el nombre y los elementos van en lineas separadas
    1

**La verificacion es que hay dos fuentes independientes.** La ROM da los
nombres en un orden; el Data List da nombre + programa + banco. Si las dos
secuencias de nombres coinciden, cada una confirma a la otra — y ese es el unico
motivo para creerle a un parser de PDF.
"""

import json
import os
import re
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
PDF = os.path.join(AQUI, "..", "Manuales", "QY100E2.pdf")
PAGINAS = (2, 3)

#: Nombres de banco, de la pagina 3. Solo para que la salida se lea.
BANCOS = {
    0: "GM", 1: "Key Scale Panning", 3: "Stereo", 6: "Single", 8: "Slow",
    12: "Fast Decay", 14: "Double Attack", 16: "Bright", 17: "Bright",
    18: "Dark", 19: "Dark", 20: "Resonant", 24: "Attack", 25: "Release",
    27: "Reso Sweep", 28: "Muted", 32: "Detune 1", 33: "Detune 2",
    34: "Detune 3", 35: "Octave 1", 36: "Octave 2", 38: "5th 2", 39: "Bend",
    40: "Tutti", 41: "Tutti", 42: "Tutti", 43: "Velo-Switch",
    45: "Velo-Xfade", 64: "Other wave", 65: "Other wave", 66: "Other wave",
    67: "Other wave", 68: "Other wave", 69: "Other wave", 70: "Other wave",
    71: "Other wave", 72: "Other wave", 96: "Other wave", 97: "Other wave",
}

SOLO_NUMEROS = re.compile(r"^[\d\s]+$")
NOMBRE = re.compile(r"^([A-Za-z0-9][\w.&+#!/'\- ]{1,7})\s*(\d)?$")


def tokens():
    """Las lineas del PDF, **con los numeros pegados ya separados**.

    `[M]` **Ese detalle costaba 83 voces de 525.** El PDF a veces pone el
    programa y el banco en la misma linea:

        110 0
        Bagpipe
        2

    `parsear()` decide por linea con `t.isdigit()`, y `"110 0"` no lo es — asi
    que descartaba el par entero y la voz siguiente se quedaba sin numeros y sin
    emitirse. La version anterior ya habia visto la linea («son dos columnas
    pegadas, no un nombre») y solo la rechazaba, que es media solucion: dejaba
    de confundirla con un nombre y seguia perdiendo los dos numeros.

    Se parten aqui y no en `parsear()` para que aquella siga razonando sobre un
    flujo de un dato por token, que es lo unico que sabe hacer.
    """
    fuera = []
    for pag in PAGINAS:
        txt = subprocess.run(["pdftotext", "-f", str(pag), "-l", str(pag),
                              PDF, "-"], capture_output=True, text=True).stdout
        for l in txt.split("\n"):
            l = l.strip()
            if not l:
                continue
            if SOLO_NUMEROS.match(l) and " " in l:
                fuera += l.split()
                continue
            # **Segunda forma de pegado**, y distinta: `112 AnlgBass`, el numero
            # y el nombre en la misma linea. La regla de arriba no la toca
            # porque no es de puros numeros, y `NOMBRE` la rechaza entera —
            # asi se perdian otras 20 voces. Se parte solo el numero de cabeza:
            # `60sEl.P1` no lleva espacio y no entra aqui, que es lo que hay que
            # proteger.
            m = re.match(r"^(\d+)\s+(\S.*)$", l)
            if m and not SOLO_NUMEROS.match(m.group(2)):
                fuera += [m.group(1), m.group(2)]
            else:
                fuera.append(l)
    return fuera


#: Palabras del encabezado y de la leyenda de bancos que NO son voces.
BASURA = {"Bank", "Select", "Program", "Voice", "Name", "Category", "Ele",
          "ment", "EleVoice", "List", "Normal", "Drum", "SFX", "Kit",
          "MSB", "LSB", "GM", "Stereo", "Single", "Slow", "Bright", "Dark",
          "Resonant", "Attack", "Release", "Muted", "Detune", "Octave",
          "Bend", "Tutti", "Other", "wave", "Fast", "Decay", "Double",
          "Panning", "Scale", "Key", "Reso", "Sweep", "Velo", "Switch",
          "Xfade", "the", "for", "of", "is", "to"}


#: `[M]` **El MSB no siempre es 0**, y este extractor lo daba por hecho. El Data
#: List declara cuatro bloques con su propio Bank Select, y la app de Ilya Orange
#: (QY70 Controller, agosto 2026) modela lo mismo como «Voice Mode»:
#:
#:     MSB 0    voces normales XG   (el LSB es la variacion del programa)
#:     MSB 64   voces de efectos    LSB 000
#:     MSB 126  kits de efectos
#:     MSB 127  kits de bateria
#:
#: Los 48 nombres que este script no resolvia **no eran «la seccion Other wave»**
#: como decia el comentario anterior: son en su mayoria **el banco de efectos**.
#: Se supo comparando con el catalogo de esa app, que los tiene todos juntos.
MSB_NORMAL, MSB_SFX, MSB_KIT_SFX, MSB_BATERIA = 0, 64, 126, 127


def parsear_sfx():
    """Las voces de efectos, del bloque `MSB=064, LSB=000` de la pagina 3.

    **Aqui SI se usa `-layout`**, al reves que en la tabla principal. Ese bloque
    lista `programa nombre elementos` por fila —sin columna de banco, porque el
    banco es fijo para todo el bloque— y sin `-layout` los numeros y los nombres
    salen en columnas separadas que no se pueden emparejar.

    ⚠️ **Y se corta por geometria, no por patron.** Buscar `numero nombre digito`
    con una regex hacia atras agarra la ultima columna de voces NORMALES cuando
    la de efectos esta vacia: da un nombre plausible en el programa equivocado.
    Paso dos veces —`Soft Pad` en el 17, `RotarStr` en el 65— y las dos veces el
    resultado parecia bueno hasta contrastarlo con anclas.

    ⚠️ **La tabla es dispersa.** Los programas 1-6 tienen voz, el 7 no, el 17 si.
    Suponer que los nombres van contiguos desde 1 —cosa que intente -- corre todo
    y da 43 asignaciones equivocadas que se leen perfectamente bien.
    """
    txt = subprocess.run(["pdftotext", "-layout", "-f", "3", "-l", "3", PDF, "-"],
                         capture_output=True, text=True).stdout
    # ⚠️ **El nombre se acota a 8 caracteres**, que es el largo real de un nombre
    # de voz de Yamaha. Sin ese tope el `.*?` atraviesa el relleno de espacios y
    # se traga el contador de elementos: salian entradas como `'Stream      2'`,
    # que no fallan — se escriben, parecen nombres y no cuadran con nada.
    fila = re.compile(r"^\s*(\d{1,3})\s+([A-Za-z0-9][\x20-\x7e]{0,7}?)\s+(\d)\s*$")
    fuera = {}
    for l in txt.split("\n"):
        for a, b in ((130, 162), (162, 200)):
            m = fila.match(l[a:b])
            if m and 1 <= int(m.group(1)) <= 128:
                # Gana el primero: la tabla se lee de arriba abajo.
                fuera.setdefault(int(m.group(1)), m.group(2).strip())
    return fuera


#: Anclas leidas de la version renderizada del propio Data List. **Sin esto la
#: extraccion no se puede creer**: tres intentos distintos dieron 43, 47 y 48
#: nombres, todos con aspecto correcto, y solo las anclas los separaron.
ANCLAS_SFX = {1: "CuttngNz", 4: "Str Slap", 17: "Fl.KClik",
              65: "PhonCall", 68: "ScratchC", 81: "CarEIgnt"}


def parsear():
    """Devuelve [(programa, banco, nombre)] en el orden de la tabla.

    **La regla, y el bug que costo la primera version:** tras cada nombre viene
    su numero de ELEMENTOS, y ese numero no es ni programa ni banco. Si se deja
    en el flujo, se lee como el banco de la voz siguiente y todo se corre —
    salia "programa 2, banco 36, PowerGt2", que es imposible porque el programa
    2 es un piano.

    Asi que despues de emitir un nombre se descarta exactamente un numero, salvo
    que el nombre ya viniera con el pegado (`GrandPno 1`).
    """
    ts = tokens()
    fuera, prog, nums, comer = [], None, [], False
    for t in ts:
        if t.isdigit():
            if comer:                      # el contador de elementos
                comer = False
                continue
            nums.append(int(t))
            continue
        m = NOMBRE.match(t)
        # **No basta con exigir letra inicial**: `60sEl.P1` y `60sDrOr1` son
        # voces de verdad y empiezan por digito. Lo que hay que rechazar es lo
        # que sea SOLO numeros — "110 0" son dos columnas pegadas, no un nombre.
        if not m or m.group(1).strip() in BASURA or SOLO_NUMEROS.match(t):
            nums, comer = [], False
            continue
        nombre = m.group(1).strip()
        traia_elementos = m.group(2) is not None
        if len(nums) >= 2:
            prog, banco = nums[-2], nums[-1]
        elif len(nums) == 1:
            banco = nums[-1]
        else:
            nums, comer = [], False
            continue
        if prog is not None and 1 <= prog <= 128 and 0 <= banco <= 127:
            fuera.append((prog, banco, nombre))
        nums = []
        comer = not traia_elementos
    return fuera


def main():
    tabla = parsear()
    rom = json.load(open(os.path.join(AQUI, "voces.json")))["normales_por_programa"]
    print("Data List : %d voces" % len(tabla))
    print("ROM       : %d voces\n" % len(rom))

    # --- la verificacion: dos fuentes, misma secuencia de nombres ---
    # **El cruce va por CONJUNTO, no por posicion**: el Data List agrupa por
    # programa (todos los bancos del 1, luego del 2) y la ROM agrupa por banco
    # (los 128 del banco 0 primero). Mismo conjunto, orden distinto.
    # **La ROM manda sobre los nombres y el Data List sobre los numeros.** Las
    # dos fuentes escriben el mismo nombre distinto —`ArcoStr` contra
    # `Arco Str`, `Ana. Pad` contra `Ana.Pad`— porque una sale del firmware y la
    # otra de un PDF maquetado a cuatro columnas. Y hay un caso peor: en
    # `60sEl.P1` el `1` final ES parte del nombre, no el contador de elementos,
    # y desde el texto solo eso es indistinguible. Por eso el cruce normaliza.
    def norm(x):
        return x.replace(" ", "").lower()
    por_norm = {}
    for pr, bk, nom in tabla:
        por_norm.setdefault(norm(nom), (pr, bk))
    en_tabla = set(norm(x[2]) for x in tabla)
    en_rom = set(norm(x) for x in rom)
    print("nombres en las dos fuentes : %d" % len(en_tabla & en_rom))
    print("solo en el Data List       : %d" % len(en_tabla - en_rom))
    print("solo en la ROM             : %d" % len(en_rom - en_tabla))
    for etiq, faltan in (("solo Data List", en_tabla - en_rom),
                         ("solo ROM", en_rom - en_tabla)):
        if faltan:
            print("   %s (%d): %s" % (etiq, len(faltan), sorted(faltan)[:8]))
    n = len(en_rom)

    print("\nmuestra de lo extraido:")
    for k in (0, 1, 2, 128, 129, 300, len(tabla) - 1):
        if k < len(tabla):
            pr, bk, nom = tabla[k]
            print("   %3d  programa %3d  banco %3d (%-18s) %s"
                  % (k, pr, bk, BANCOS.get(bk, "?"), nom))

    # **Se escribe lo verificado y se nombra lo que falta.**
    #
    # La version anterior era todo-o-nada: si las dos fuentes no coincidian
    # exactamente, no escribia nada. La disciplina era buena —ningun numero sin
    # confirmar— pero el efecto era que 477 voces verificadas no le servian a
    # nadie porque 48 seguian sin resolver.
    #
    # Asi que se conserva la disciplina y se cambia el reparto: **solo entra en
    # `voces` lo que aparece en las DOS fuentes**, y lo que falta queda listado
    # en `_faltan` para que se vea y no se confunda con «no existe».
    sfx = parsear_sfx()
    fallan = {pr: (sfx.get(pr), esp) for pr, esp in ANCLAS_SFX.items()
              if sfx.get(pr) != esp}
    if fallan:
        print("\n⚠️  las anclas del bloque SFX no cuadran, no se escribe:")
        for pr, (real, esp) in sorted(fallan.items()):
            print("   prog %3d: %s, esperado %s" % (pr, real, esp))
        return 1
    print("\nbloque SFX (MSB=064): %d voces, %d/%d anclas"
          % (len(sfx), len(ANCLAS_SFX), len(ANCLAS_SFX)))

    salida = os.path.join(AQUI, "bancos.json")
    buenas = [{"msb": MSB_NORMAL, "programa": pr, "banco": bk, "nombre": nom}
              for pr, bk, nom in tabla if norm(nom) in en_rom]
    vistos = {norm(v["nombre"]) for v in buenas}
    # ⚠️ **Tambien las SFX pasan por la ROM.** La primera version las anadia sin
    # comprobar, mientras el propio archivo se declaraba «confirmado contra la
    # ROM: dos fuentes independientes». Ocho entradas mal parseadas entraron por
    # ahi, y la frase de verificacion las cubria sin haberlas visto.
    buenas += [{"msb": MSB_SFX, "programa": pr, "banco": 0, "nombre": nom}
               for pr, nom in sorted(sfx.items())
               if norm(nom) not in vistos and norm(nom) in en_rom]
    faltan = sorted(en_rom - {norm(v["nombre"]) for v in buenas})
    with open(salida, "w") as f:
        json.dump({"_origen": "Data List QY100E2.pdf paginas 2-3, "
                              "'Bank Select MSB=000, LSB=Bank Number'",
                   "_verificacion": "%d nombres confirmados contra la ROM "
                                    "(voces.json): dos fuentes independientes"
                                    % len(buenas),
                   "_faltan": faltan,
                   "_bancos": {"0": "voces normales XG (el banco es el LSB)",
                               "64": "voces de efectos (SFX), LSB 000",
                               "126": "kits de efectos", "127": "kits de bateria"},
                   "_por_que_faltan": "Filas que ninguno de los dos parsers "
                                      "alcanza todavia: variaciones con el nombre "
                                      "partido por la maquetacion, y algunas SFX "
                                      "cuyas filas caen fuera de las columnas "
                                      "medidas. Inferirlas por posicion daria "
                                      "numeros plausibles y sin comprobar.",
                   "voces": buenas}, f, ensure_ascii=False, indent=1)
    print("\nescrito %s: %d voces con banco, %d sin resolver"
          % (os.path.basename(salida), len(buenas), len(faltan)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
