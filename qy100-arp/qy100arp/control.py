"""Control en vivo por CC MIDI.

En un setup DAWless no hay pantalla ni teclado donde editar un archivo: los
parametros tienen que estar bajo los knobs del controlador. Este modulo mapea
numeros de CC a parametros del motor y los aplica en tiempo real.

Un CC mapeado se consume (no se reenvia al QY100). Los no mapeados pasan de largo.
"""

from __future__ import annotations

from .arp import DIVISIONS, PATTERNS

DIVISION_ORDER = ["1/4", "1/4T", "1/8", "1/8T", "1/16", "1/16T", "1/32", "1/32T"]

# nombre -> (tipo, dominio)
#   toggle: >=64 enciende
#   enum:   recorre la lista a lo largo del rango del knob
#   int/float: escala lineal entre los dos extremos
PARAMS = {
    "arp.enabled":       ("toggle", None),
    "arp.latch":         ("toggle", None),
    "arp.pattern":       ("enum", list(PATTERNS)),
    "arp.division":      ("enum", DIVISION_ORDER),
    "arp.octaves":       ("int", (1, 4)),
    "arp.gate":          ("float", (0.05, 1.5)),
    "arp.transpose":     ("int", (-24, 24)),
    "arp.fixed_velocity": ("int", (1, 127)),

    "melody.enabled":    ("toggle", None),
    "melody.density":    ("float", (0.0, 1.0)),
    "melody.stepwise":   ("float", (0.0, 3.0)),
    "melody.tonal_pull": ("float", (0.0, 3.0)),
    "melody.velocity":   ("int", (1, 127)),
    "melody.base_octave": ("int", (1, 6)),
}

# para las lineas euclidianas: "lane.<nombre>.<parametro>"
LANE_PARAMS = {
    "enabled":     ("toggle", None),
    "pulses":      ("int", (0, 16)),
    "rotation":    ("int", (0, 15)),
    "probability": ("float", (0.0, 1.0)),
    "velocity":    ("int", (1, 127)),
}


def _scale(kind, domain, value):
    """value es 0-127 del CC."""
    if kind == "toggle":
        return value >= 64
    if kind == "enum":
        idx = min(len(domain) - 1, value * len(domain) // 128)
        return domain[idx]
    lo, hi = domain
    if kind == "int":
        return int(round(lo + (value / 127.0) * (hi - lo)))
    return lo + (value / 127.0) * (hi - lo)


class ControlMap:
    def __init__(self, cfg, engine, log=None):
        cfg = cfg or {}
        self.enabled = bool(cfg.get("enabled", False))
        ch = cfg.get("channel")
        self.channel = None if ch is None else int(ch) - 1
        self.log = log or (lambda *a: None)
        self.engine = engine

        self.map = {}
        for cc, param in (cfg.get("map") or {}).items():
            self._validate(param)
            self.map[int(cc)] = param

    def _validate(self, param):
        if param in PARAMS:
            return
        if param.startswith("lane."):
            bits = param.split(".")
            if len(bits) == 3 and bits[2] in LANE_PARAMS:
                names = [l.name for l in self.engine.lanes]
                if bits[1] in names:
                    return
                raise ValueError(
                    "linea %r no existe (hay: %s)" % (bits[1], ", ".join(names)))
        raise ValueError("parametro de control desconocido: %r" % (param,))

    def _resolve(self, param):
        """Devuelve (objeto, atributo, tipo, dominio) o None si no aplica."""
        if param.startswith("lane."):
            _, name, attr = param.split(".")
            for lane in self.engine.lanes:
                if lane.name == name:
                    kind, domain = LANE_PARAMS[attr]
                    if attr == "pulses":
                        domain = (0, lane.steps)
                    elif attr == "rotation":
                        domain = (0, max(0, lane.steps - 1))
                    return lane, attr, kind, domain
            return None

        section, attr = param.split(".", 1)
        target = self.engine.arp if section == "arp" else self.engine.melody
        if target is None:
            return None
        kind, domain = PARAMS[param]
        return target, attr, kind, domain

    def apply(self, msg) -> bool:
        """True si el CC fue consumido por el mapeo."""
        if not self.enabled or msg.control not in self.map:
            return False
        if self.channel is not None and msg.channel != self.channel:
            return False

        param = self.map[msg.control]
        resolved = self._resolve(param)
        if resolved is None:
            return False
        target, attr, kind, domain = resolved

        new = _scale(kind, domain, msg.value)
        old = getattr(target, attr, None)
        if new == old:
            return True

        setattr(target, attr, new)

        # las divisiones se guardan tambien en ticks, hay que recalcular
        if attr == "division":
            target.ticks_per_step = DIVISIONS[new]
        # cambiar pulsos o rotacion obliga a rehacer el patron euclidiano
        if attr in ("pulses", "rotation"):
            from .euclid import euclid
            target.pattern = euclid(target.pulses, target.steps, target.rotation)

        if isinstance(new, float):
            self.log("  %s = %.2f" % (param, new))
        else:
            self.log("  %s = %s" % (param, new))
        return True
