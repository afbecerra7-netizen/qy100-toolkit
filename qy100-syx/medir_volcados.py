#!/usr/bin/env python3
"""Recuenta sobre los volcados las cifras que los documentos citan.

Existe porque **tres cifras publicadas resultaron ser de otra cosa**: los 451
control change eran apariciones del byte `0xFB` en cualquier posicion —relleno y
prefijo incluidos—, no eventos alcanzados, y el reparto «27 fallan / 15 callan»
de las pistas sin marcador salio de una cuenta que ya no se puede reproducir.

Cualquier cifra de estas que aparezca en un documento tiene que salir de aqui.

    .venv/bin/python medir_volcados.py

Dos trampas, las dos padecidas:

- **Las pistas de patron llevan 26 bytes de prefijo y las de cancion no.** Si se
  les quita el prefijo a las de cancion, empiezan a faltar marcadores que si
  estaban: 28 pistas sin marcador se convierten en 117.
- **Los volcados se repiten entre archivos.** Contar apariciones en vez de
  pistas distintas multiplica todo por algo mas de dos, sin avisar.
"""

import collections
import glob
import os
import sys

from qy100syx import protocol as P
from qy100syx import patternfmt as F

PATRON, CANCION = 0x12, 0x11

#: Pistas distintas en el cuaderno de trabajo, de donde salieron las cifras
#: que citan los documentos. Sirve para avisar cuando se corre sobre un
#: conjunto reducido y los numeros no van a parecerse.
CORPUS_COMPLETO = 415


def recoger(patron_glob="dumps/*.syx"):
    """{(tipo, flujo desempaquetado): primera procedencia}, sin duplicados."""
    bloques = collections.OrderedDict()
    archivos = 0
    for f in sorted(glob.glob(patron_glob)):
        try:
            ms, _ = P.parse_all(open(f, "rb").read())
        except Exception:
            continue
        archivos += 1
        for m in ms:
            if m.addr[0] not in (PATRON, CANCION):
                continue
            if m.addr[2] == 0x7F or len(m.data) != 147:   # 0x7F es la cabecera
                continue
            clave = (os.path.basename(f), m.addr[0], m.addr[1], m.addr[2])
            bloques.setdefault(clave, []).append(bytes(m.data))

    # el prefijo de 26 bytes solo lo llevan las pistas de patron
    pistas, apariciones = collections.OrderedDict(), 0
    for (arch, tipo, nn, tr), bl in bloques.items():
        start = F.EVENT_STREAM_START if tipo == PATRON else 0
        flujo = F.unpack(bl[0])[start:] + b"".join(F.unpack(p) for p in bl[1:])
        apariciones += 1
        pistas.setdefault((tipo, flujo), (arch, nn, tr))
    return pistas, apariciones, archivos


def recorrer(d):
    """Recorre un flujo alineado. (control changes, llego_a_F2, notas)."""
    i, ccs, notas = 0, [], 0
    while i < len(d):
        s = d[i]
        if 0x80 <= s <= 0x9F:   n = 1
        elif 0xA0 <= s <= 0xBF: n = 2
        elif 0xC0 <= s <= 0xCF: n = 3; notas += 1
        elif 0xD0 <= s <= 0xDF: n = 4; notas += 1
        elif 0xE0 <= s <= 0xEF: n = 5; notas += 1
        elif s == F.END_OF_TRACK:   return ccs, True, notas
        elif s == 0xF0:             n = 2
        elif s == F.CONTROL_CHANGE: n = 3
        else:                       return ccs, False, notas
        if i + n > len(d):
            return ccs, False, notas
        if s == F.CONTROL_CHANGE:
            ccs.append((d[i + 1], d[i + 2]))
        i += n
    return ccs, False, notas


def main():
    pistas, apariciones, archivos = recoger()
    if not pistas:
        print("no hay volcados en dumps/ — no hay nada que medir")
        return 1

    print("%d pistas distintas, en %d apariciones dentro de %d archivos"
          % (len(pistas), apariciones, archivos))
    # Las cifras que citan los documentos salieron de las 415 pistas del
    # cuaderno de trabajo. El repo publico lleva solo los ocho volcados que
    # necesitan las pruebas, asi que alli todo sale mucho mas pequeño y **eso no
    # significa que los documentos esten equivocados**. Sin esta linea, el
    # primero que lo ejecutara alli tendria motivos para creer que si.
    if len(pistas) < CORPUS_COMPLETO // 2:
        print("\n  OJO: los documentos citan %d pistas y aqui hay %d. Este es un\n"
              "  conjunto reducido de volcados —el repo publico lleva solo los que\n"
              "  usan las pruebas—, asi que los numeros de abajo NO son los\n"
              "  publicados ni los contradicen." % (CORPUS_COMPLETO, len(pistas)))
    print()

    print("marcador de inicio de pista")
    for tipo, nombre in ((PATRON, "patron "), (CANCION, "cancion")):
        del_tipo = [d for (t, d) in pistas if t == tipo]
        sin = [d for d in del_tipo if d[:2] != F.TRACK_MARKER]
        # La pregunta que justifica el chequeo: de las que no lo llevan,
        # ¿cuantas las cazaria igualmente el control de evento desconocido?
        # Hay que preguntarlo en ESTRICTO y saltandose el marcador; con
        # estricto=False no falla nada por construccion y no se prueba nada.
        revientan, callan, inventadas = 0, 0, 0
        for d in sin:
            try:
                notas, _ = F.decode_events(d, start=0, max_events=4096,
                                           estricto=True)
                callan += 1
                inventadas += len(notas)
            except ValueError:
                revientan += 1
        print("  %s  %3d pistas, %3d sin F0 00" % (nombre, len(del_tipo), len(sin)))
        if sin:
            print("           de esas: %d revientan solas, **%d se leen sin una "
                  "queja** y sacan %d notas que no son las de la pista"
                  % (revientan, callan, inventadas))

    print("\nfinal de pista")
    sanas = [(t, d) for (t, d) in pistas if d[:2] == F.TRACK_MARKER]
    sin_f2 = [k for k in sanas if not recorrer(k[1])[1]]
    print("  %d pistas empiezan bien; %d de ellas NUNCA llegan a F2"
          % (len(sanas), len(sin_f2)))

    print("\ncontrol change")
    ccs = []
    for t, d in sanas:
        c, bien, _ = recorrer(d)
        if bien:
            ccs.extend(c)
    crudo = sum(d.count(F.CONTROL_CHANGE) for (t, d) in pistas)
    print("  el byte 0xFB en cualquier posicion : %d   <- NO son eventos" % crudo)
    print("  eventos FB alcanzados alineados    : %d" % len(ccs))
    if ccs:
        print("     por numero de control : %r"
              % dict(collections.Counter(cc for cc, v in ccs)))
        print("     por valor             : %r"
              % dict(collections.Counter(v for cc, v in ccs)))
        n_pistas = sum(1 for t, d in sanas if recorrer(d)[0])
        print("     repartidos en %d pista(s)" % n_pistas)

    # --- recuento final, en los mismos terminos que el documento ---
    # Cuanto aporta consumir FB entero: se mide decodificando con y sin.
    def decodifica(d, con_fb):
        i, n = 0, 0
        while i < len(d):
            s = d[i]
            if 0x80 <= s <= 0x9F:   w = 1
            elif 0xA0 <= s <= 0xBF: w = 2
            elif 0xC0 <= s <= 0xCF: w = 3; n += 1
            elif 0xD0 <= s <= 0xDF: w = 4; n += 1
            elif 0xE0 <= s <= 0xEF: w = 5; n += 1
            elif s == F.END_OF_TRACK:   return True
            elif s == 0xF0:             w = 2
            elif s == F.CONTROL_CHANGE and con_fb: w = 3
            else:                       return False
            if i + w > len(d):
                return False
            i += w
        return False

    print("\nrecuento final")
    ok = sin_marca = sin_final = 0
    for t, d in pistas:
        if d[:2] != F.TRACK_MARKER:
            sin_marca += 1
        elif decodifica(d, True):
            ok += 1
        else:
            sin_final += 1
    print("  %d pistas decodifican enteras" % ok)
    print("  %d no llevan marcador — se rechazan" % sin_marca)
    print("  %d empiezan bien pero no llegan a F2" % sin_final)
    gana = sum(1 for t, d in pistas
               if d[:2] == F.TRACK_MARKER
               and decodifica(d, True) and not decodifica(d, False))
    print("  consumir FB entero, y no un byte, recupera %d pista(s)" % gana)
    return 0


if __name__ == "__main__":
    sys.exit(main())
