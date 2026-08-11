#!/usr/bin/env python3
"""Pesa cada estilo en bloques y en KB de memoria del aparato.

    .venv/bin/python pesar_estilos.py

Existe porque la tabla de `PLAN-LIVESET.md` estaba calculada a **147 bytes por
bloque, que es el tamaño en el cable y no en el aparato**. El 7->8 es
codificacion de transporte: 147 bytes de 7 bits llevan 128 de 8, y lo que ocupa
memoria son los 128. Todo el presupuesto salia un 14,8 % inflado y contradecia
al documento de protocolo, que fija los 128 y los contrasto dos veces contra la
barra de `USED MEMORY` del equipo. `cli.py` siempre uso 128; era el plan el que
iba por libre.

Este programa replica lo que hace `cmd_andina` —las seis secciones, las mismas
pistas, los mismos prefijos— para que la cifra no dependa de que alguien copie
bien la aritmetica a mano. Que es como se colo la primera vez.
"""

import sys

from qy100syx import andina as A
from qy100syx import generar as G
from qy100syx import patternfmt as F

#: Lo que ocupa un bloque en la SRAM del QY100. **No son 147.**
BYTES_POR_BLOQUE = F.UNPACKED_BYTES
#: IC6, `uPD431000`. `SRAM 1M` es un megabit, o sea 128 KB.
SRAM_KB = 128
#: Los 5 bloques de cabecera que lleva todo patron, ademas de las pistas.
CABECERA = 5

#: El set de 40 minutos, segun `PLAN-LIVESET.md`. El torbellino y la cumbia van
#: dos veces, y cada aparicion es un patron distinto con su propia cabecera.
SET = ["torbellino", "torbellino", "pasillo", "fiestero", "currulao",
       "cumbia", "cumbia", "mapale", "afrobeat (4/4)", "soca"]


def pesar(clase):
    """(notas, bloques, bloques_de_percusion) de un estilo entero, 6 secciones."""
    g = clase()
    notas_tot = bloques = ritmo = 0
    for s, (_nom_s, intensidad, comp) in enumerate(A.SECCIONES):
        piezas = g.construir(s, comp, intensidad)
        total = g.total(comp)
        for idx, nom, _papel, voz, es_bat, _m in g.pistas:
            notas = sorted((n for n in piezas[idx] if n.time < total),
                           key=lambda n: n.time)
            prog = (G.kit_por_nombre(voz)[1] if es_bat else G.voz_por_nombre(voz))
            pre = F.build_prefix(base=F.PREFIJO_BASE, compases=comp,
                                 nombre="%s%d" % (nom, s + 1), tipo="Bypass",
                                 pista=idx, voz=prog,
                                 banco=F.BANK_DRUMS if es_bat else F.BANK_NORMAL)
            n = len(G.a_bloques(notas, total, pre))
            notas_tot += len(notas)
            bloques += n
            if es_bat:
                ritmo += n
    return notas_tot, bloques + CABECERA, ritmo


def pesar_receta(receta):
    """Lo mismo para las recetas de `estilo.py`, que son las de 4/4."""
    from qy100syx import estilo as E
    comp = [c for _n, _i, c in A.SECCIONES]
    piezas = E.construir(comp, semilla=0, receta=receta,
                         beats_per_bar=E.COMPASES_SOPORTADOS.get(receta, (4,))[0])
    notas_tot = bloques = ritmo = 0
    percusion = {idx for idx, _n, _p, _t, _v, es_bat in E.RECETAS[receta] if es_bat}
    for (s, idx), (notas, total) in sorted(piezas.items()):
        pre = F.build_prefix(base=F.PREFIJO_BASE, compases=comp[s],
                             nombre="R%d%d" % (s, idx), tipo="Bypass",
                             pista=idx, voz=0,
                             banco=F.BANK_DRUMS if idx in percusion else F.BANK_NORMAL)
        n = len(G.a_bloques(notas, total, pre))
        notas_tot += len(notas)
        bloques += n
        if idx in percusion:
            ritmo += n
    return notas_tot, bloques + CABECERA, ritmo


def kb(bloques):
    return bloques * BYTES_POR_BLOQUE / 1024.0


def main():
    from qy100syx import estilo as E
    filas = []
    for nombre in sorted(A.GENEROS):
        try:
            filas.append((nombre,) + pesar(A.GENEROS[nombre]))
        except Exception as e:
            print("%-14s no se pudo pesar: %s: %s" % (nombre, type(e).__name__, e))
    for receta in sorted(E.RECETAS):
        try:
            filas.append((receta + " (4/4)",) + pesar_receta(receta))
        except Exception as e:
            print("%-14s no se pudo pesar: %s: %s" % (receta, type(e).__name__, e))

    if not filas:
        return 1

    print("estilo entero: las %d secciones, todas las pistas\n" % len(A.SECCIONES))
    print("| estilo | notas | bloques | KB | de eso, ritmo |")
    print("| --- | --- | --- | --- | --- |")
    for nombre, notas, bl, rit in sorted(filas, key=lambda f: f[2]):
        pct = (" (%d %%)" % round(100.0 * rit / bl)) if bl else ""
        print("| %s | %d | %d | %.1f | %.1f%s |"
              % (nombre, notas, bl, kb(bl), kb(rit), pct))

    tot = sum(f[2] for f in filas)
    print("\nlos %d generos completos: %d bloques = %.1f KB = %.0f %% de los %d KB"
          % (len(filas), tot, kb(tot), 100.0 * kb(tot) / SRAM_KB, SRAM_KB))
    print("a 147 bytes por bloque saldria %.1f KB, un %.1f %% de mas"
          % (tot * 147 / 1024.0, 100.0 * (147.0 / BYTES_POR_BLOQUE - 1)))

    ritmo = sum(f[3] for f in filas)
    print("\nde ese total, %.1f KB (%.0f %%) son percusion, que es justo lo que\n"
          "puede apuntar a frases de fabrica sin gastar memoria de usuario."
          % (kb(ritmo), 100.0 * ritmo / tot))

    # --- el set concreto ---
    #
    # Se calcula aqui y no a mano porque **aplicar el porcentaje global de
    # percusion a un subconjunto da un numero equivocado**, y eso ya paso al
    # reescribir el plan: el 44 % de arriba es de los trece estilos, y el set
    # tiene otra mezcla. El porcentaje de un conjunto no es el de sus partes.
    por_nombre = {f[0]: f for f in filas}
    faltan = sorted(set(n for n in SET if n not in por_nombre))
    presentes = [n for n in SET if n in por_nombre]   # con repeticiones
    if presentes:
        bl = sum(por_nombre[n][2] for n in presentes)
        rit = sum(por_nombre[n][3] for n in presentes)
        print("\nel set (%s):" % ", ".join(presentes))
        print("   %d bloques = %.1f KB = %.0f %% de los %d KB"
              % (bl, kb(bl), 100.0 * kb(bl) / SRAM_KB, SRAM_KB))
        print("   de eso %.1f KB (%.0f %%) es percusion; referenciada a frases de"
              % (kb(rit), 100.0 * rit / bl))
        print("   fabrica el set queda en %.1f KB = %.0f %%"
              % (kb(bl - rit), 100.0 * kb(bl - rit) / SRAM_KB))
    if faltan:
        print("   OJO: %s no existe(n) como motor, asi que su peso NO esta"
              % ", ".join(faltan))
        print("   medido y no entra en las cifras de arriba.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
