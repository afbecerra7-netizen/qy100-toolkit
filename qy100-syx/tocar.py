"""Toca en vivo sobre el generador de tonos del QY100, por MIDI.

El QY100 es un generador XG multitimbrico: las notas que llegan por MIDI IN
en el canal N suenan con la voz asignada a ese canal. Asi que se puede tocar
sin tocar el secuenciador — nada de esto escribe en la memoria del equipo.

    .venv/bin/python tocar.py prueba

Aqui **el maestro somos nosotros**, no el QY100, asi que la temporizacion es
un reloj local. Es lo contrario de lo que hace `qy100-arp`, donde los motores
siguen el reloj entrante y un `sleep` propio romperia el sincronismo; la regla
de alli no aplica aqui porque no hay nada a lo que seguir.

Dos precauciones, ambas por experiencia del proyecto:

- **Un Program Change cambia la voz que el mezclador tiene puesta en ese
  canal.** Por eso se toca en canales que las canciones del EP no usan (ellas
  ocupan 1, 4, 5, 6, 7 y 8). Aun asi hay respaldo en `dumps/`.
- **Notas colgadas**: todo va en `try/finally` con note-off explicito y
  All Notes Off por canal. Un script que muere a media frase deja el
  generador sonando y no hay forma de callarlo desde el panel.
"""
import os
import argparse
import inspect
import sys
import time

import mido

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qy100syx import generar as G                                    # noqa: E402

PUERTO = "M4"
# Canales libres: el EP usa 1, 4, 5, 6, 7 y 8.
CH_LEAD, CH_BAJO, CH_PAD, CH_PERC = 2, 3, 9, 10

CC_BANCO_MSB, CC_BANCO_LSB = 0, 32
# **Hacen falta los dos.** `All Notes Off` (123) solo suelta las teclas: lo que
# ya esta en su fase de release sigue sonando, y con colas largas —los efectos
# del SFX Kit, los pads, un arroyo con gate de tres compases— eso puede quedar
# zumbando indefinidamente. `All Sound Off` (120) corta el sonido pase lo que
# pase. Mandar solo el 123 dejo el equipo pitando durante toda una tarde, y el
# pitido se confundio con un fallo de la composicion.
CC_ALL_SOUND_OFF, CC_ALL_NOTES_OFF = 120, 123


class Pieza:
    """Acumula eventos con tiempo absoluto en segundos y luego los reproduce."""

    def __init__(self, bpm):
        self.bpm = bpm
        self.negra = 60.0 / bpm
        self.eventos = []          # (t, prioridad, mensaje)
        self.canales = set()

    def voz(self, canal, nombre, volumen=100):
        """Fija la voz de un canal. Acepta nombre de voz normal o de kit.

        Solo sirven las **128 primeras** voces normales. `voces.json` guarda
        los 525 nombres en una lista plana y su indice coincide con el numero
        de programa unicamente hasta la 127 — de ahi en adelante son
        variaciones en otros bancos XG, y el *bank LSB* que las selecciona
        nunca se descifro. Mandar el indice como programa produce un valor
        fuera de 0..127. Afecta igual a `generar --voz`.
        """
        try:
            banco, programa = G.kit_por_nombre(nombre)
        except Exception:
            banco, programa = 0, G.voz_por_nombre(nombre)
        if not 0 <= programa <= 127:
            raise ValueError(
                "'%s' es la voz %d: pasa de 127, asi que es una variacion de "
                "banco XG y no sabemos su bank LSB. Usa una de las 128 "
                "basicas." % (nombre, programa))
        self.canales.add(canal)
        for msg in (
            mido.Message("control_change", channel=canal - 1,
                         control=CC_BANCO_MSB, value=banco),
            mido.Message("control_change", channel=canal - 1,
                         control=CC_BANCO_LSB, value=0),
            mido.Message("program_change", channel=canal - 1, program=programa),
            mido.Message("control_change", channel=canal - 1, control=7,
                         value=volumen),
        ):
            self.eventos.append((-1.0, 0, msg))

    def nota(self, canal, altura, t, dur, vel=100):
        """t y dur en negras."""
        self.canales.add(canal)
        ini, fin = t * self.negra, (t + dur) * self.negra
        self.eventos.append((ini, 1, mido.Message(
            "note_on", channel=canal - 1, note=int(altura), velocity=int(vel))))
        self.eventos.append((fin, 0, mido.Message(
            "note_off", channel=canal - 1, note=int(altura), velocity=0)))

    def acorde(self, canal, alturas, t, dur, vel=90):
        for a in alturas:
            self.nota(canal, a, t, dur, vel)

    def duracion(self):
        return max((t for t, _, _ in self.eventos), default=0.0)

    def tocar(self, puerto):
        # Los note_off se ordenan antes que los note_on en el mismo instante
        # (prioridad 0 < 1), para que repetir una nota no la corte a si misma.
        self.eventos.sort(key=lambda e: (e[0], e[1]))
        with mido.open_output(puerto) as out:
            try:
                inicio = time.time()
                for t, _p, msg in self.eventos:
                    espera = inicio + max(t, 0.0) - time.time()
                    if espera > 0:
                        time.sleep(espera)
                    out.send(msg)
                time.sleep(0.3)
            finally:
                for canal in sorted(self.canales):
                    for cc in (CC_ALL_SOUND_OFF, CC_ALL_NOTES_OFF):
                        out.send(mido.Message("control_change", channel=canal - 1,
                                              control=cc, value=0))


def altura(clase, octava):
    return clase % 12 + 12 * (octava + 1)


# --------------------------------------------------------------------------
def prueba(bpm=96):
    """Prueba corta: que se oiga algo inequivoco y se sepa que llega."""
    p = Pieza(bpm)
    p.voz(CH_LEAD, "SquareLd", volumen=100)
    p.voz(CH_BAJO, "SynBass1", volumen=105)

    DO = 0
    arpegio = [0, 3, 7, 12, 7, 3]          # do menor, subiendo y bajando
    for i in range(24):
        p.nota(CH_LEAD, altura(DO + arpegio[i % len(arpegio)], 5),
               t=i * 0.25, dur=0.22, vel=96 if i % 6 == 0 else 78)
    for c in range(3):
        p.nota(CH_BAJO, altura(DO, 2), t=c * 2.0, dur=1.8, vel=100)
    return p


def vigilia(bpm=92):
    """~2:15 en Do menor. Cuatro capas que entran y se retiran por tramos.

    Progresion `Cm - Ab - Fm - G` (i - VI - iv - V). Dos acordes menores
    sujetan el centro y el G mayor mete el Si natural como sensible, que es
    lo que da el tiron de vuelta al Do. Es la leccion del Quiebre aplicada de
    entrada: la version que sonaba mayor tenia dos triadas mayores y nada que
    anclara el modo.

    El pad va en **quintas abiertas y solo pone la tercera sobre las menores**,
    asi que el Ab y el G no suenan brillantes aunque sean mayores.
    """
    from qy100syx import patternfmt as F

    p = Pieza(bpm)
    COMPASES = 52
    NEGRAS = 4
    TOTAL = F.section_clocks(COMPASES)
    Q = F.CLOCKS_PER_QUARTER

    p.voz(CH_PERC, "Analog Kit", volumen=104)
    p.voz(CH_BAJO, "SynBass1", volumen=108)
    p.voz(CH_PAD, "Halo Pad", volumen=78)
    p.voz(CH_LEAD, "SquareLd", volumen=92)

    ENTRADA, BAJO, TEMA, CIMA, SALIDA = (1, 8), (9, 16), (17, 32), (33, 44), (45, 52)
    MENOR, MAYOR = (0, 3, 7), (0, 4, 7)
    PROGRESION = [(0, MENOR), (8, MAYOR), (5, MENOR), (7, MAYOR)]

    def acorde_de(c):
        return PROGRESION[((c - 1) // 2) % len(PROGRESION)]

    def en(c, *tramos):
        return any(a <= c <= b for a, b in tramos)

    def compas_de(n):
        return n.time // (Q * NEGRAS) + 1

    def emitir(canal, notas, vel=None):
        for n in notas:
            p.nota(canal, n.pitch, n.time / float(Q),
                   max(n.gate / float(Q), 0.05), vel or n.velocity)

    # --- percusion euclidiana ---------------------------------------------
    capas = []
    for kw, tramos in (
            (dict(pulsos=2, pasos=8, nota=36, semilla=901), (TEMA, CIMA)),
            (dict(pulsos=9, pasos=16, nota=42, semilla=902), (CIMA,)),
            (dict(pulsos=3, pasos=8, nota=82, semilla=903), (ENTRADA, BAJO, TEMA, CIMA)),
            (dict(pulsos=3, pasos=16, nota=39, rotacion=4, semilla=904), (CIMA,))):
        ns, _ = G.euclidiano(COMPASES, **kw)
        capas += [n for n in ns if en(compas_de(n), *tramos)]
    capas = G.acentuar(capas, fuerte=112, medio=92, flojo=72)
    capas = G.humanizar(capas, velocity=10, tiempo=5, semilla=9, total_clocks=TOTAL)
    emitir(CH_PERC, capas)

    # --- bajo: fundamental, con octava en la cima --------------------------
    for c in range(1, COMPASES + 1):
        if not en(c, BAJO, TEMA, CIMA, SALIDA):
            continue
        raiz, _ = acorde_de(c)
        base = (c - 1) * NEGRAS
        pasos = ((0, 1.5, 2.5) if en(c, TEMA, CIMA) else (0,))
        for i, t in enumerate(pasos):
            p.nota(CH_BAJO, altura(raiz, 2), base + t,
                   0.9 if i else 1.2, 108 if i == 0 else 88)
        if en(c, CIMA):
            p.nota(CH_BAJO, altura(raiz, 3), base + 3.5, 0.4, 84)

    # --- pad: quintas abiertas, dos compases por acorde --------------------
    for c in range(1, COMPASES + 1):
        if (c - 1) % 2 or not en(c, ENTRADA, BAJO, TEMA, CIMA, SALIDA):
            continue
        raiz, iv = acorde_de(c)
        base = 12 * 3 + raiz % 12
        voces = [base, base + 19, base + (15 if iv == MENOR else 24)]
        p.acorde(CH_PAD, voces, (c - 1) * NEGRAS, NEGRAS * 2 - 0.15, 74)

    # --- tema: notas del acorde colocadas por un euclidiano ----------------
    rej, _ = G.euclidiano(COMPASES, pulsos=7, pasos=16, nota=60, semilla=905)
    for i, n in enumerate(rej):
        c = compas_de(n)
        if not en(c, TEMA, CIMA):
            continue
        raiz, iv = acorde_de(c)
        grado = iv[i % len(iv)]
        t = n.time / float(Q)
        p.nota(CH_LEAD, altura(raiz + grado, 5), t, 0.45,
               96 if en(c, CIMA) else 80)
        if en(c, CIMA) and i % 3 == 0:
            p.nota(CH_LEAD, altura(raiz + grado, 6), t, 0.45, 70)
    return p


def acompanar(bpm=92):
    """~4 min en Mi menor, pensada como base para tocar guitarra encima.

    `Em - C - Am - D` (i - VI - iv - VII), dos compases cada uno. **Todo el
    ciclo es diatonico a Mi menor**, asi que no hay notas que evitar y una
    sola posicion sirve para el tema entero — que es lo que se le pide a una
    base para improvisar, no lucimiento armonico.

    Mi menor y no Do menor porque la guitarra vive ahi: el Mi grave al aire es
    la tonica, y el Sol, La, Si y Re caen bajo la mano.

    **No lleva melodia.** El registro medio se deja libre a proposito; una voz
    principal aqui competiria con quien toca. El pad va en quintas abiertas y
    solo pone la tercera en los acordes menores, para que el C y el D no
    empujen la sensacion hacia mayor.
    """
    from qy100syx import patternfmt as F

    p = Pieza(bpm)
    COMPASES = 96
    NEGRAS = 4
    TOTAL = F.section_clocks(COMPASES)
    Q = F.CLOCKS_PER_QUARTER

    p.voz(CH_PERC, "Analog Kit", volumen=100)
    p.voz(CH_BAJO, "SynBass1", volumen=106)
    p.voz(CH_PAD, "Halo Pad", volumen=76)

    INTRO, ENTRA, PLENO, HUECO = (1, 8), (9, 24), (25, 48), (49, 56)
    VUELTA, SALIDA = (57, 80), (81, 96)
    MENOR, MAYOR = (0, 3, 7), (0, 4, 7)
    MI = 4
    PROGRESION = [(MI, MENOR), (0, MAYOR), (9, MENOR), (2, MAYOR)]
    OFF = NEGRAS                      # un compas de claqueta antes de empezar

    def acorde_de(c):
        return PROGRESION[((c - 1) // 2) % len(PROGRESION)]

    def en(c, *tramos):
        return any(a <= c <= b for a, b in tramos)

    def compas_de(n):
        return n.time // (Q * NEGRAS) + 1

    # --- claqueta: un compas de baqueta para entrar en tiempo --------------
    for t in range(NEGRAS):
        p.nota(CH_PERC, 37, t, 0.2, 104 if t == 0 else 84)

    # --- bateria recta -----------------------------------------------------
    # Deliberadamente NO euclidiana. Un patron euclidiano no cae donde el oido
    # lo espera — es su gracia y por eso lo usamos en el EP — pero eso es justo
    # lo contrario de lo que necesita quien va a tocar encima. Bombo en 1 y 3,
    # caja en 2 y 4, charles marcando: la rejilla explicita y sin ambiguedad.
    BOMBO, CAJA, CHARLES, ABIERTO, CLAP = 36, 38, 42, 46, 39
    for c in range(1, COMPASES + 1):
        base = (c - 1) * NEGRAS + OFF
        denso = en(c, PLENO, VUELTA)

        for t in (0, 2):
            p.nota(CH_PERC, BOMBO, base + t, 0.2, 112)
        if denso:
            p.nota(CH_PERC, BOMBO, base + 2.75, 0.2, 92)

        # La caja nunca falta: es la referencia del compas.
        for t in (1, 3):
            p.nota(CH_PERC, CAJA, base + t, 0.2, 106)
        if en(c, VUELTA):
            for t in (1, 3):
                p.nota(CH_PERC, CLAP, base + t, 0.2, 88)

        paso = 0.25 if denso else 0.5
        n = int(NEGRAS / paso)
        for i in range(n):
            t = i * paso
            if denso and abs(t - 3.5) < 1e-6:
                continue                       # sitio del charles abierto
            p.nota(CH_PERC, CHARLES, base + t, 0.15,
                   88 if abs(t - round(t)) < 1e-6 else 66)
        if denso and c % 4 == 0:
            p.nota(CH_PERC, ABIERTO, base + 3.5, 0.35, 92)

    # Una capa euclidiana de shaker por encima, solo como textura: aporta el
    # caracter del proyecto sin discutirle la rejilla a la bateria.
    ns, _ = G.euclidiano(COMPASES, pulsos=5, pasos=16, nota=82, semilla=913)
    ns = G.humanizar(ns, velocity=10, tiempo=4, semilla=91, total_clocks=TOTAL)
    for n in ns:
        p.nota(CH_PERC, n.pitch, n.time / float(Q) + OFF,
               max(n.gate / float(Q), 0.05), min(n.velocity, 70))

    # --- bajo --------------------------------------------------------------
    for c in range(1, COMPASES + 1):
        if not en(c, ENTRA, PLENO, VUELTA, SALIDA):
            continue
        raiz, _ = acorde_de(c)
        base = (c - 1) * NEGRAS + OFF
        denso = en(c, PLENO, VUELTA)
        for i, t in enumerate((0, 1.5, 2.5) if denso else (0, 2)):
            p.nota(CH_BAJO, altura(raiz, 2), base + t,
                   0.9 if i else 1.2, 106 if i == 0 else 86)
        if en(c, VUELTA):
            p.nota(CH_BAJO, altura(raiz, 3), base + 3.5, 0.4, 82)

    # --- pad ---------------------------------------------------------------
    for c in range(1, COMPASES + 1):
        if (c - 1) % 2:
            continue
        raiz, iv = acorde_de(c)
        base = 12 * 4 + raiz % 12
        voces = [base, base + 19, base + (15 if iv == MENOR else 24)]
        vol = 66 if en(c, INTRO, HUECO, SALIDA) else 76
        p.acorde(CH_PAD, voces, (c - 1) * NEGRAS + OFF, NEGRAS * 2 - 0.15, vol)
    return p


def barrido(bpm=100):
    """Toca tres notas en cada canal, del 1 al 16, para ver cuales suenan.

    Diagnostico del sintoma "solo se oye una voz". El manual lo lista como
    averia propia (guia de problemas, p. 143): si `ECHO BACK` esta en
    `RecMontr`, lo que entra por MIDI IN **se re-canaliza al canal de la pista
    de grabacion seleccionada**, asi que 16 canales distintos colapsan en uno.
    La solucion es `ECHO BACK = Off`.

    **No manda Bank Select ni Program Change a proposito**: para saber si un
    canal recibe basta con que suene, sea cual sea su voz, y asi el mezclador
    de la cancion cargada queda intacto. Un barrido que ademas cambiara las
    voces dejaria el EP retocado en los 16 canales.
    """
    p = Pieza(bpm)
    t = 0.0
    for canal in range(1, 17):
        for i in range(3):
            p.nota(canal, altura(0, 4) + canal, t + i * 0.25,
                   0.22, 104 if i == 0 else 84)
        t += 1.75                      # hueco claro entre canal y canal
    return p


def cumbia(bpm=95):
    """~3 min en Sol mayor. Acordeon, bajo, guitarra y percusion latina.

    Lo que hace que suene a cumbia no es la armonia — que es la mas simple
    posible, `G - Em - C - D` — sino **dos cosas en la percusion**:

    - La **guacharaca**: guiro largo en cada tiempo y guiro corto en cada
      contratiempo. Es el raspado de ida y vuelta, y es la textura que
      identifica el genero antes que cualquier otra cosa.
    - El **llamador** en TODOS los contratiempos. Ese golpe a contratiempo,
      constante y sin excepcion, es el motor del baile.

    Y una consecuencia que conviene no invertir: **el bajo va simple**, casi
    solo en 1 y 3. La sincopa la pone la percusion; si ademas la pone el bajo,
    la cumbia se enreda y deja de empujar. Es lo contrario de lo que pedia el
    Quiebre del EP, donde la rareza tenia que venir del bajo.

    La tabla de bateria del Data List (p. 12) da los numeros: 74 guiro largo,
    73 guiro corto, 62 conga aguda apagada, 64 conga grave, 69 cabasa.
    """
    from qy100syx import patternfmt as F

    p = Pieza(bpm)
    COMPASES, NEGRAS, CICLO = 72, 4, 8
    OFF = 0.0

    CH_ACORD, CH_GUIT = 2, 4
    p.voz(CH_ACORD, "Acordion", volumen=96)
    p.voz(CH_BAJO, "FngrBass", volumen=108)
    p.voz(CH_GUIT, "SteelGtr", volumen=84)
    p.voz(CH_PERC, "Standard Kit", volumen=104)

    GUIRO_L, GUIRO_C, LLAMADOR, TAMBORA, CONGA_G, CONGA_A, CABASA = \
        74, 73, 62, 36, 64, 63, 69

    MAYOR, MENOR = (0, 4, 7), (0, 3, 7)
    SOL = 7
    PROGRESION = [(SOL, MAYOR), (4, MENOR), (0, MAYOR), (2, MAYOR)]

    # Melodia de acordeon: 8 compases, en semitonos sobre Sol4. Escrita a
    # mano y no generada — una cumbia pide una tonada que se pueda cantar, y
    # una cadena de Markov divaga justo donde hace falta que no lo haga.
    BASE_MEL = 67
    MELODIA = [
        (0.5, 4, .5), (1.0, 7, .5), (1.5, 4, .5), (2.5, 2, .5), (3.0, 0, 1.),
        (4.5, 7, .5), (5.0, 4, 1.), (6.5, 2, .5), (7.0, 4, 1.),
        (8.5, 9, .5), (9.0, 12, .5), (9.5, 9, .5), (10.5, 7, .5), (11.0, 4, 1.),
        (12.5, 9, .5), (13.0, 7, .5), (13.5, 4, 1.), (15.0, 2, 1.),
        (16.5, 5, .5), (17.0, 9, .5), (17.5, 12, .5), (18.5, 9, .5), (19.0, 5, 1.),
        (20.5, 9, .5), (21.0, 7, 1.), (22.5, 5, .5), (23.0, 9, 1.),
        (24.5, 11, .5), (25.0, 14, .5), (25.5, 11, .5), (26.5, 7, .5), (27.0, 11, 1.),
        (28.5, 14, .5), (29.0, 11, .5), (29.5, 7, 1.), (31.0, 2, 1.),
    ]

    ENTRADA, RITMO, TEMA1, HUECO = (1, 4), (5, 12), (13, 28), (29, 36)
    TEMA2, FINAL = (37, 60), (61, 72)

    def acorde_de(c):
        return PROGRESION[((c - 1) // 2) % len(PROGRESION)]

    def en(c, *tramos):
        return any(a <= c <= b for a, b in tramos)

    for c in range(1, COMPASES + 1):
        base = (c - 1) * NEGRAS + OFF
        pleno = en(c, TEMA1, TEMA2, FINAL)

        # --- guacharaca: largo en el tiempo, corto en el contratiempo ------
        for t in range(NEGRAS):
            p.nota(CH_PERC, GUIRO_L, base + t, 0.3, 84)
            p.nota(CH_PERC, GUIRO_C, base + t + 0.5, 0.2, 62)

        # --- llamador: el contratiempo, sin faltar nunca ------------------
        for t in range(NEGRAS):
            p.nota(CH_PERC, LLAMADOR, base + t + 0.5, 0.2, 100)

        # --- tambora y congas ---------------------------------------------
        for t in (0, 2):
            p.nota(CH_PERC, TAMBORA, base + t, 0.25, 110)
        p.nota(CH_PERC, CONGA_G, base + 2.5, 0.25, 88)
        if pleno:
            p.nota(CH_PERC, CONGA_A, base + 3.5, 0.25, 84)
            for i in range(NEGRAS * 2):
                p.nota(CH_PERC, CABASA, base + i * 0.5, 0.15,
                       74 if i % 2 == 0 else 58)

        if en(c, ENTRADA):
            continue

        raiz, iv = acorde_de(c)

        # --- bajo: simple a proposito, 1 y 3 ------------------------------
        p.nota(CH_BAJO, altura(raiz, 2), base, 1.4, 110)
        p.nota(CH_BAJO, altura(raiz + iv[2], 2), base + 2, 1.2, 98)
        if pleno:
            sig, _ = acorde_de(c + 1)
            p.nota(CH_BAJO, altura(sig, 2), base + 3.5, 0.4, 86)

        # --- guitarra: acordes solo en los contratiempos -------------------
        voces = [altura(raiz, 3), altura(raiz + iv[1], 4), altura(raiz + iv[2], 4)]
        for t in range(NEGRAS):
            p.acorde(CH_GUIT, voces, base + t + 0.5, 0.3, 82)

    # --- acordeon: la tonada, por ciclos de 8 compases ---------------------
    for ciclo in range(COMPASES // CICLO):
        c0 = ciclo * CICLO + 1
        if not en(c0, TEMA1, TEMA2, FINAL):
            continue
        base = (c0 - 1) * NEGRAS + OFF
        vel = 100 if en(c0, TEMA2, FINAL) else 92
        for t, semi, dur in MELODIA:
            p.nota(CH_ACORD, BASE_MEL + semi, base + t, dur * 0.9, vel)
    return p


def andino(bpm=100, tonica=4):
    """~2:50. Huayno para tocar quena encima. Mi menor por defecto.

    **La tonalidad no es un gusto, es la digitacion de la quena.** La quena
    estandar es en Sol, asi que su escala natural es Sol mayor — y su relativo
    menor, Mi menor, tiene exactamente las mismas notas. En Mi menor la quena
    toca todo con digitacion abierta; en otra tonalidad aparecen horquillas.
    Si la suya es en Re, Do o Fa, `tonica` transpone la pieza entera.

    Armonia `Em - D - C - D` (i - VII - VI - VII): modal, **sin sensible**.
    Ese Re natural en vez de Re# es lo que la mantiene andina en lugar de
    sonar a menor europeo, y ademas deja el ciclo entero dentro de Mi menor
    natural, asi que no hay una sola nota que la quena deba evitar.

    El motor ritmico es el **galope del huayno**: la celula de dos
    semicorcheas y una corchea, que el charango repite en cada tiempo. El
    bombo hace el largo-corto por debajo.

    **No lleva melodia**: el registro agudo se deja entero para la quena. El
    charango se mantiene por debajo del Sol4 justamente para no invadirlo.
    """
    p = Pieza(bpm)
    COMPASES, NEGRAS = 72, 4

    CH_CHARANGO, CH_GUIT, CH_ARPA = 2, 4, 9
    p.voz(CH_CHARANGO, "Banjo", volumen=86)
    p.voz(CH_BAJO, "Aco.Bass", volumen=104)
    p.voz(CH_GUIT, "NylonGtr", volumen=86)
    p.voz(CH_ARPA, "Harp", volumen=76)
    p.voz(CH_PERC, "Standard Kit", volumen=100)

    BOMBO, ARO, CHAJCHAS, MARACAS = 36, 37, 69, 70

    MAYOR, MENOR = (0, 4, 7), (0, 3, 7)
    PROGRESION = [(tonica, MENOR), (tonica - 2, MAYOR),
                  (tonica - 4, MAYOR), (tonica - 2, MAYOR)]

    INTRO, CHARANGO, PLENO, HUECO = (1, 4), (5, 12), (13, 28), (29, 36)
    VUELTA, CIERRE = (37, 60), (61, 72)

    def acorde_de(c):
        return PROGRESION[((c - 1) // 2) % len(PROGRESION)]

    def en(c, *tramos):
        return any(a <= c <= b for a, b in tramos)

    # El galope: dos semicorcheas y una corchea dentro de cada negra.
    GALOPE = ((0.0, 1.0), (0.25, 0.62), (0.5, 0.80))

    for c in range(1, COMPASES + 1):
        base = (c - 1) * NEGRAS
        pleno = en(c, PLENO, VUELTA, CIERRE)
        raiz, iv = acorde_de(c)

        # --- bombo: largo-corto, y aro al contragolpe ---------------------
        for t in (0, 2):
            p.nota(CH_PERC, BOMBO, base + t, 0.3, 112)
            p.nota(CH_PERC, BOMBO, base + t + 0.75, 0.2, 84)
        for t in (1, 3):
            p.nota(CH_PERC, ARO, base + t, 0.2, 88)

        # --- chajchas: el galope, en semillas ------------------------------
        for t in range(NEGRAS):
            for off, k in GALOPE:
                p.nota(CH_PERC, CHAJCHAS, base + t + off, 0.15, int(74 * k))
        if pleno:
            for t in range(NEGRAS):
                p.nota(CH_PERC, MARACAS, base + t + 0.5, 0.15, 56)

        if en(c, INTRO):
            continue

        # --- charango: el galope rasgueado, siempre por debajo del Sol4 ---
        voces = [altura(raiz, 4), altura(raiz + iv[1], 4), altura(raiz + iv[2], 4)]
        for t in range(NEGRAS):
            for off, k in GALOPE:
                p.acorde(CH_CHARANGO, voces, base + t + off, 0.22, int(84 * k))

        if en(c, CHARANGO):
            continue

        # --- bajo: la raiz y la quinta, con el corto del huayno -----------
        p.nota(CH_BAJO, altura(raiz, 2), base, 0.7, 108)
        p.nota(CH_BAJO, altura(raiz + iv[2], 2), base + 0.75, 0.4, 86)
        p.nota(CH_BAJO, altura(raiz, 2), base + 2, 0.7, 104)
        if pleno:
            sig, _ = acorde_de(c + 1)
            p.nota(CH_BAJO, altura(sig, 2), base + 3.5, 0.4, 84)

        if en(c, HUECO):
            continue

        # --- guitarra: acordes largos, sostienen la armonia ---------------
        graves = [altura(raiz, 3), altura(raiz + iv[2], 3)]
        p.acorde(CH_GUIT, graves, base, NEGRAS - 0.2, 80)

        # --- arpa: arpegios solo al final ---------------------------------
        if en(c, CIERRE):
            grados = [iv[0], iv[1], iv[2], iv[1]]
            for i, g in enumerate(grados * 2):
                p.nota(CH_ARPA, altura(raiz + g, 4), base + i * 0.5, 0.45, 70)
    return p


PIEZAS = {"prueba": prueba, "vigilia": vigilia, "acompanar": acompanar,
          "barrido": barrido, "cumbia": cumbia, "andino": andino}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pieza", choices=sorted(PIEZAS))
    ap.add_argument("--puerto", default=PUERTO)
    ap.add_argument("--bpm", type=float)
    ap.add_argument("--tono", help="tonica: C C# D D# E F F# G G# A A# B")
    args = ap.parse_args()

    kw = {}
    if args.bpm:
        kw["bpm"] = args.bpm
    if args.tono:
        NOTAS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        if args.tono not in NOTAS:
            ap.error("tono desconocido: %s (usa %s)" % (args.tono, " ".join(NOTAS)))
        if "tonica" not in inspect.signature(PIEZAS[args.pieza]).parameters:
            ap.error("la pieza '%s' no se transporta" % args.pieza)
        kw["tonica"] = NOTAS.index(args.tono)

    p = PIEZAS[args.pieza](**kw)
    print("tocando '%s' en %s — %.0f bpm, %.1f s, canales %s"
          % (args.pieza, args.puerto, p.bpm, p.duracion(),
             ", ".join(str(c) for c in sorted(p.canales))))
    p.tocar(args.puerto)
    print("listo")
