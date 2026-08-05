"""Informes: inspeccionar un volcado y comparar dos.

`diff` es la pieza importante para deducir el formato interno: se borra un
patron, se graba una sola nota conocida, se vuelca, se cambia una cosa, se
vuelca otra vez, y se mira exactamente que bytes se movieron.
"""

from __future__ import annotations

import collections

from . import protocol as P


def inspect(blob: bytes, log=print):
    msgs, errs = P.parse_all(blob)
    log("%d mensajes SysEx, %d bytes en bruto" % (len(msgs), len(blob)))
    if errs:
        log("%d bloques ilegibles:" % len(errs))
        for k, e in errs[:5]:
            log("   #%d: %s" % (k, e))

    if not msgs:
        return msgs

    span, scores = P.detect_checksum_span(msgs)
    log("")
    log("Checksum: el manual no dice sobre que rango se calcula, asi que se")
    log("prueban las tres convenciones plausibles contra estos datos:")
    for name, (ok, total) in sorted(scores.items(), key=lambda kv: -kv[1][0]):
        mark = "  <- coincide" if name == span and ok == total and total else ""
        log("   %-22s %d/%d%s" % (name, ok, total, mark))
    if scores[span][0] != scores[span][1]:
        log("   NINGUNA valida todo. Los datos pueden venir incompletos, o la")
        log("   convencion es otra distinta a las tres probadas.")

    by_addr = collections.OrderedDict()
    for m in msgs:
        by_addr.setdefault(m.addr, []).append(m)

    log("")
    log("%-14s %-34s %6s %8s %8s" % ("direccion", "que es", "bloques", "bytes", "checksum"))
    log("-" * 76)
    for addr, group in by_addr.items():
        data = sum(len(m.data) for m in group)
        good = sum(1 for m in group if m.verify(span) is True)
        total = sum(1 for m in group if m.stored_checksum is not None)
        state = "n/a" if not total else ("ok" if good == total else "%d/%d" % (good, total))
        log("%-14s %-34s %6d %8d %8s"
            % ("%02X %02X %02X" % addr, P.addr_name(addr)[:34], len(group), data, state))

    bad_len = [m for m in msgs if not m.length_ok]
    if bad_len:
        log("")
        log("%d bloques con longitud distinta a su ByteCount:" % len(bad_len))
        for m in bad_len[:5]:
            log("   %s: declara %d, trae %d" % (P.addr_name(m.addr), m.byte_count, len(m.data)))
    return msgs


def payload_of(msgs, addr=None):
    """Concatena los datos de los bloques, opcionalmente de una sola direccion."""
    out = bytearray()
    for m in msgs:
        if m.sub != P.SUB_DUMP:
            continue
        if addr is not None and m.addr != addr:
            continue
        out += bytes(m.data)
    return bytes(out)


# Bytes que cambian entre volcados aunque el contenido sea identico. Verificado:
# dos capturas con el bloque de pista byte a byte igual traian valores distintos
# aqui. No es checksum del contenido ni campo de datos; es estado volatil del
# equipo. Se enmascara o ensucia todos los diffs.
#   clave: (direccion, offset dentro del payload concatenado de esa direccion)
VOLATILE = {((0x12, 0x00, 0x7F), 509)}


def _volatile(addr, offset):
    return (addr, offset) in VOLATILE


def diff(blob_a: bytes, blob_b: bytes, name_a="A", name_b="B", context=4,
         log=print, show_volatile=False):
    """Compara dos volcados bloque a bloque, emparejando por direccion.

    Los bytes conocidos como volatiles se ocultan por defecto; `show_volatile`
    los vuelve a mostrar.
    """
    ma, _ = P.parse_all(blob_a)
    mb, _ = P.parse_all(blob_b)

    ia = collections.OrderedDict()
    for m in ma:
        ia.setdefault(m.addr, []).append(m)
    ib = collections.OrderedDict()
    for m in mb:
        ib.setdefault(m.addr, []).append(m)

    log("%s: %d mensajes    %s: %d mensajes" % (name_a, len(ma), name_b, len(mb)))

    only_a = [a for a in ia if a not in ib]
    only_b = [a for a in ib if a not in ia]
    for label, lst in ((name_a, only_a), (name_b, only_b)):
        if lst:
            log("Solo en %s: %s" % (label, ", ".join(P.addr_name(a) for a in lst[:8])))

    total_changes = 0
    for addr in ia:
        if addr not in ib:
            continue
        da = payload_of(ia[addr], addr)
        db = payload_of(ib[addr], addr)

        if da == db:
            continue
        log("")
        log("### %s  (%02X %02X %02X)" % (P.addr_name(addr), *addr))
        if len(da) != len(db):
            log("   tamano distinto: %d vs %d bytes" % (len(da), len(db)))

        n = min(len(da), len(db))
        changed = [i for i in range(n) if da[i] != db[i]]
        if not show_volatile:
            ocultos = [i for i in changed if _volatile(addr, i)]
            changed = [i for i in changed if i not in ocultos]
            if ocultos:
                log("   (%d byte(s) volatil(es) ocultos: offsets %s)"
                    % (len(ocultos), ", ".join(str(i) for i in ocultos)))
            if not changed:
                continue
        total_changes += len(changed) + abs(len(da) - len(db))
        log("   %d de %d bytes distintos" % (len(changed), n))

        # agrupar posiciones contiguas para que se lea como regiones, no como ruido
        runs = []
        for i in changed:
            if runs and i == runs[-1][-1] + 1:
                runs[-1].append(i)
            else:
                runs.append([i])

        w = max(len(name_a), len(name_b))
        for run in runs[:20]:
            lo = max(0, run[0] - context)
            hi = min(n, run[-1] + 1 + context)
            log("   offset %-6d %s" % (run[0], "-" * 46))
            log("     %-*s %s" % (w, name_a, _hexline(da, lo, hi, run)))
            log("     %-*s %s" % (w, name_b, _hexline(db, lo, hi, run)))
        if len(runs) > 20:
            log("   ... y %d regiones mas" % (len(runs) - 20))

    if total_changes == 0:
        log("")
        log("Identicos byte a byte.")
    return total_changes


def _hexline(buf, lo, hi, highlight):
    hl = set(highlight)
    parts = []
    for i in range(lo, hi):
        parts.append("[%02X]" % buf[i] if i in hl else " %02X " % buf[i])
    return "".join(parts)
