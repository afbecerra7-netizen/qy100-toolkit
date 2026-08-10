"""Mapa de notas de la Arturia DrumBrute Impact, y la traduccion desde GM.

Medido en el equipo (Centro de Control MIDI, pestana DEVICE SETTINGS) y
confirmado contra el manual ES p. 103. Es el mapa **de fabrica**, sin editar.

**No es GM, y solo dos notas coinciden.** La trampa esta en el 42: en GM es el
charles cerrado —la nota mas frecuente de cualquier patron— y aqui es el
cencerro. Un patron GM mandado tal cual a la Impact suena a cencerro donde
deberia llevar el charles, que es un fallo que se oye raro sin delatar su causa.

Cada instrumento tiene una segunda nota, la **color**, que dispara una variante
timbrica del mismo sonido. Son diez voces extra que no gastan instrumento;
sirven para acentuar sin robarle un canal al patron. El cencerro es el unico que
no la tiene.

El canal global de la Impact es el **1**, y su reloj esta en 24 PPQ, que es lo
que emite el QY100: se sincronizan sin conversion.
"""

# instrumento -> (nota, nota de color). None = no tiene color.
IMPACT = {
    "kick":    (36, 48),
    "snare1":  (37, 49),
    "snare2":  (38, 50),
    "tom_h":   (39, 51),
    "tom_l":   (40, 52),
    "cymbal":  (41, 53),
    "cowbell": (42, None),
    "cl_hat":  (43, 55),
    "op_hat":  (44, 56),
    "fm":      (45, 57),
}

NOTA = {k: v[0] for k, v in IMPACT.items()}
COLOR = {k: v[1] for k, v in IMPACT.items() if v[1] is not None}

CANAL = 1          # canal global de la Impact, 1-16
PPQ = 24           # igual que el reloj del QY100

# GM -> instrumento de la Impact. Las diez voces no cubren un kit GM entero, asi
# que esto **decide**, no traduce: los tres charles de GM caen en dos, los seis
# toms en dos, y los platos en uno. Lo que no aparece aqui no tiene destino
# razonable y se descarta antes que sonar como otra cosa.
DESDE_GM = {
    35: "kick",     36: "kick",
    37: "snare1",   40: "snare1",              # rim y caja electrica
    38: "snare2",   39: "snare2",              # caja y palmas
    41: "tom_l",    43: "tom_l",    45: "tom_l",
    47: "tom_h",    48: "tom_h",    50: "tom_h",
    42: "cl_hat",   44: "cl_hat",              # cerrado y de pedal
    46: "op_hat",
    49: "cymbal",   51: "cymbal",   57: "cymbal",   59: "cymbal",
    56: "cowbell",
}


# --- El formato .drumbruteimpact -----------------------------------------
#
# Las plantillas que exporta el Centro de Control MIDI son **JSON plano**, un
# diccionario de 209.090 pares. Eso hace la Impact mucho mas accesible que el
# QY100: no hay protocolo, ni sumas de control, ni `bulk mode`, ni panel que se
# bloquee. Se escribe un archivo y se arrastra.
#
# Un detalle: Arturia deja **una coma sobrante antes de la llave final**, asi
# que no es JSON estricto y `json.load` lo rechaza. Hay que quitarla al leer.
#
#     clave = banco _ parametro _ patron [ _ instrumento [ _ paso ] ]
#
#     banco        26..29    A B C D
#     patron        1..16
#     instrumento   1..10    en el orden de IMPACT
#     paso          1..64
#
# 4 x 16 x 10 x 64 = 40.960 por parametro. El archivo escribe **todo**
# explicitamente aunque este vacio, de ahi que pese 4,5 MB sin una sola nota.
#
# **Medido por diferencia** (2026-08-09) contra una plantilla recien exportada de
# un aparato vacio, que es la linea base ideal porque cada parametro tenia un
# unico valor en las 209.090 claves. Se grabo el bombo en los pasos 1, 5, 9 y 13
# del patron 1 del banco A y **cambiaron exactamente cuatro claves**, todas
# `105`. Nada mas se movio.
#
# El disparo es el **105**, no el 102, que es lo que se habia supuesto por ser el
# primero de la lista y valer 0. Una hipotesis de un solo dato, y estaba mal.

# **La rejilla del Centro de Control es `Working Memory`, o sea el aparato** —
# no una vista previa de la plantilla seleccionada. Lo vio Felipe: lo que se ve
# en la rejilla es lo que se transfiere, y si ahi no hay nada, no va nada.
#
# Importar una plantilla solo la mete en la lista de la izquierda; la rejilla no
# se inmuta y parece que la importacion fallo. Para que llegue al aparato hay que
# desplegar la plantilla con el `+`, buscar el patron y **arrastrarlo encima de
# `Working Memory`** (manual §9.4.3). Sobrescribe esa posicion.
#
# Costo media hora de diagnostico equivocado: la rejilla mostraba un patron que
# no era ninguna de nuestras dos versiones y se leyo como que la escritura
# estaba mal. El round-trip lo descarto —importar y reexportar dio cero claves
# distintas de 209.090—, y ahi quedo claro que el archivo era correcto y la
# pantalla describia otra cosa.
#
# Tercera pantalla del mismo dia que no describe el dato, tras el editor del
# Minitaur y su lista de presets de hardware. **En una herramienta de gestion,
# averiguar que representa cada panel antes de interpretar lo que muestra**:
# aqui habia dos selecciones azules a la vez, una del aparato y otra de un
# archivo, y la rejilla seguia a la primera.

DEFECTOS = {
    # (numero_de_campos, parametro): valor en una plantilla vacia
    (3, 80): 0, (3, 81): 93, (3, 82): 96, (3, 97): 0, (3, 98): 2,
    (3, 100): 50, (3, 101): 0,
    (4, 99): 16, (4, 103): 0, (4, 108): 50, (4, 109): 0, (4, 110): 0,
    (4, 111): 0,
    (5, 102): 0, (5, 104): 50, (5, 105): 0, (5, 106): 100, (5, 107): 1,
}

PARAM_GOLPE = 105       # por paso: 1 = suena, 0 = no. **Medido.**
PARAM_LARGO = 99        # por instrumento: pasos del bucle. 16 por defecto;
                        # que sea por instrumento es lo que permite el polirritmo.

# Sin medir todavia, y cada uno necesita su propia prueba aislada: 104 (=50,
# probablemente velocity), 106 (=100), 107 (=1) y 102 (=0) por paso; 108 por
# instrumento; y por patron 100 (=50, probablemente el swing, donde 50 es "sin
# swing") y 98 (=2, division de tiempo). **No usar ninguno sin medirlo antes**:
# la lista de arriba ya produjo una atribucion falsa.

BANCOS = "ABCD"
ORDEN = ["kick", "snare1", "snare2", "tom_h", "tom_l",
         "cymbal", "cowbell", "cl_hat", "op_hat", "fm"]


def leer_plantilla(ruta):
    """Carga un `.drumbruteimpact`, tolerando la coma sobrante de Arturia."""
    import json
    import re
    return json.loads(re.sub(r",(\s*})", r"\1", open(ruta).read()))


def escribir_plantilla(datos, ruta):
    """Escribe el JSON reproduciendo el formato exacto del Centro de Control.

    **`device` y `version` van primero, y hay coma antes de la llave final.**
    No es cosmetico: la primera version ordenaba todo alfabeticamente y en ASCII
    los digitos van antes que las letras, asi que las dos claves de cabecera
    acababan al final. El Centro de Control importaba el archivo sin protestar y
    luego no mostraba nada — probablemente porque lee la primera clave para
    identificar el aparato.

    Y la comprobacion que se hizo entonces **no probaba nada**: se importo el
    archivo, se reexporto y salio identico, lo que se leyo como "el programa lo
    entiende". Un programa que no entiende un archivo y se limita a copiarlo da
    exactamente el mismo resultado. **Un round-trip solo demuestra comprension si
    el formato de salida se genera, no si puede haberse copiado.**
    """
    import json
    cab = [k for k in ("device", "version") if k in datos]
    resto = sorted(k for k in datos if k not in cab)
    with open(ruta, "w") as fh:
        fh.write("{\n")
        for k in cab + resto:
            fh.write('\t%s: %s,\n' % (json.dumps(k), json.dumps(datos[k])))
        fh.write("}")     # sin salto final: Arturia termina el archivo en la llave


def poner(datos, banco, patron, instrumento, pasos, largo=None):
    """Enciende `pasos` (1..64) del `instrumento` en un patron. Modifica en sitio.

    `instrumento` es un nombre de `IMPACT` o un indice 1..10. `banco` es una
    letra o 26..29. Apaga los pasos que no esten en la lista, para que el
    resultado sea el patron pedido y no la union con lo que hubiera.
    """
    b = banco if isinstance(banco, int) else 26 + BANCOS.index(banco.upper())
    i = (instrumento if isinstance(instrumento, int)
         else ORDEN.index(instrumento) + 1)
    activos = set(pasos)
    for paso in range(1, 65):
        datos["%d_%d_%d_%d_%d" % (b, PARAM_GOLPE, patron, i, paso)] = (
            1 if paso in activos else 0)
    if largo is not None:
        datos["%d_%d_%d_%d" % (b, PARAM_LARGO, patron, i)] = largo
    return datos


def desde_gm(nota, color=False):
    """Nota GM -> nota de la Impact, o None si no hay destino razonable.

    Con `color=True` devuelve la variante timbrica cuando existe, y la nota
    normal cuando no (el cencerro).
    """
    inst = DESDE_GM.get(nota)
    if inst is None:
        return None
    return COLOR.get(inst, NOTA[inst]) if color else NOTA[inst]
