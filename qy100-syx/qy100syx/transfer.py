"""Dialogo MIDI con el QY100: pedir volcados, escuchar, reenviar."""

from __future__ import annotations

import time

import mido

from . import protocol as P


def resolve(name, available, kind):
    if name is None:
        if len(available) == 1:
            return available[0]
        raise SystemExit(
            "Indica el puerto de %s con --%s. Disponibles: %s"
            % (kind, kind, ", ".join(available) or "(ninguno)"))
    matches = [p for p in available if name.lower() in p.lower()]
    if not matches:
        raise SystemExit("No encuentro el puerto de %s %r. Disponibles: %s"
                         % (kind, name, ", ".join(available) or "(ninguno)"))
    return matches[0]


def silenciar_reloj(inport, log=None):
    """Descarta reloj y active sensing en el driver, dejando pasar el SysEx.

    VERIFICADO contra el equipo: con `MIDI CONTROL` en `Out` o `In/Out` el
    QY100 emite **49 mensajes de reloj por segundo de forma continua, tambien
    con el secuenciador parado**. Esa avalancha hace perder bloques SysEx
    enteros incluso capturando por callback: un volcado que devolvia 7 bloques
    paso a devolver 3, y luego 2.

    Antes no se notaba porque `MIDI CONTROL` estaba apagado y no habia reloj.
    En cuanto se enciende —que hace falta para sincronizar una grabacion— el
    problema reaparece.

    `ignore_types` de python-rtmidi lo filtra antes de que llegue a la cola, que
    es donde hay que resolverlo: filtrarlo en Python ya seria tarde.
    """
    rt = getattr(inport, "_rt", None)
    if rt is None:                       # otro backend de mido: no se puede
        if log:
            log("  (aviso: no se pudo filtrar el reloj; backend sin rtmidi)")
        return False
    rt.ignore_types(sysex=False, timing=True, active_sense=True)
    return True


def collect(inport, quiet_for=1.5, overall_timeout=120.0, log=None):
    """Acumula SysEx entrante hasta `quiet_for` segundos de silencio.

    El QY100 manda los volcados largos en muchos mensajes seguidos; el corte por
    silencio es mas fiable que esperar una cantidad fija, porque no sabemos de
    antemano cuantos bloques va a mandar.

    Se captura por callback y no sondeando. Verificado contra el equipo: con
    sondeo se **perdian mensajes SysEx completos**, porque el QY100 transmite
    reloj MIDI sin parar (48 ticks por segundo) y esa avalancha llena la cola de
    entrada mientras llegan bloques de 158 bytes. El sintoma era enganoso: los
    mensajes que si llegaban estaban perfectos y con checksum valido, solo
    faltaban algunos. Lo delataba que setup y efecto —de un solo bloque— salian
    identicos, y todo lo multi-bloque variaba.
    """
    log = log or (lambda *a: None)
    blob = bytearray()
    state = {"count": 0, "last": None}

    def on_message(msg):
        if msg.type != "sysex":
            return
        blob.extend(bytes([P.SOX]) + bytes(msg.data) + bytes([P.EOX]))
        state["count"] += 1
        state["last"] = time.monotonic()
        if state["count"] % 25 == 0:
            log("  ... %d mensajes, %d bytes" % (state["count"], len(blob)))

    previo = inport.callback
    inport.callback = on_message
    try:
        start = time.monotonic()
        while True:
            now = time.monotonic()
            if state["last"] is not None and now - state["last"] >= quiet_for:
                break
            if now - start >= overall_timeout:
                log("  (se acabo el tiempo de espera)")
                break
            time.sleep(0.01)
    except KeyboardInterrupt:
        # Ctrl-C es la forma normal de cerrar una captura larga. Lo recibido
        # hasta aqui es valido y hay que devolverlo: descartarlo tira a la
        # basura un volcado que el usuario ya hizo y no se puede rehacer gratis.
        log("  (cortado a mano, se conserva lo capturado)")
    finally:
        inport.callback = previo

    return bytes(blob), state["count"]


def request(outport, inport, addr, quiet_for=1.5, timeout=120.0, log=None):
    """Manda un Bulk Dump Request y devuelve lo que conteste el equipo."""
    log = log or (lambda *a: None)
    req = P.dump_request(addr)
    log("Pidiendo %s  ->  %s" % (P.addr_name(addr), req.hex(" ")))
    outport.send(mido.Message("sysex", data=req[1:-1]))
    return collect(inport, quiet_for, timeout, log)


def send_blob(outport, blob: bytes, delay=0.02, log=None):
    """Reenvia mensajes SysEx al equipo, con pausa entre uno y otro.

    La pausa importa: el QY100 escribe en RAM con respaldo de pila mientras
    recibe, y si se le manda todo de golpe se pierden bloques.
    """
    log = log or (lambda *a: None)
    msgs = P.split_sysex(blob)
    for k, raw in enumerate(msgs, 1):
        outport.send(mido.Message("sysex", data=raw[1:-1]))
        time.sleep(delay)
        if k % 25 == 0:
            log("  ... %d/%d enviados" % (k, len(msgs)))
    return len(msgs)


def send_pattern(outport, blocks, delay=0.10, log=None):
    """Escribe bloques de patron en el QY100. VERIFICADO contra el equipo.

    El procedimiento importa y no esta en el manual:

      1. `bulk mode ON`
      2. los bloques, con pausa entre cada uno
      3. `bulk mode OFF`

    **Mandar un bloque suelto sin este marco borra el patron de destino y deja
    al equipo colgado en modo bulk**, sin responder a nada hasta que se le manda
    un `bulk mode OFF`. Comprobado: el QY100 limpia el destino antes de recibir
    —por eso su propio volcado empieza con CLEAR ALL— y si la secuencia no se
    completa, se queda a medias.

    **Y el marco no basta: hay que mandar el patron COMPLETO y EN SU ORDEN.**
    Dos fallos distintos lo demostraron el 2026-07-29, ambos con el prevuelo
    pasado:

      - Los 2 bloques de una sola pista, bien enmarcados, dejaron al QY100
        congelado: pantalla muerta, sordo al panel y a MIDI, sin recuperarse ni
        con un `bulk mode OFF`. Hubo que apagarlo.
      - Todos los bloques del patron pero **reordenados** (la pista nueva al
        final, detras de la cabecera) dejaron el equipo vivo pero **el patron
        borrado**. El QY100 vuelca las pistas primero y los 5 bloques de
        cabecera al final, y ese orden forma parte del trato.

    Sustituye los bloques de la pista **en su sitio** dentro de la lista, y
    mandala entera. Restaurar un volcado tal cual siempre funciona: eso fue lo
    que senalo al orden como culpable.

    `blocks` son mensajes SysEx completos (de F0 a F7).
    """
    log = log or (lambda *a: None)
    import mido as _mido
    outport.send(_mido.Message("sysex", data=P.bulk_mode(True)[1:-1]))
    time.sleep(0.5)
    for k, raw in enumerate(blocks, 1):
        outport.send(_mido.Message("sysex", data=raw[1:-1]))
        time.sleep(delay)
        if k % 10 == 0:
            log("  ... %d/%d bloques" % (k, len(blocks)))
    outport.send(_mido.Message("sysex", data=P.bulk_mode(False)[1:-1]))
    time.sleep(1.0)
    return len(blocks)
