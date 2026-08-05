"""Ritmos euclidianos (maximamente uniformes).

Usa el metodo de Bresenham en vez del algoritmo de Bjorklund: produce el mismo
tipo de patron maximamente uniforme en una linea, y como exponemos `rotation`
la diferencia de fase inicial no importa musicalmente.

    E(3,8)  -> x..x..x.   (tresillo)
    E(5,8)  -> x.x.xx.x
    E(4,16) -> x...x...x...x...
"""

from __future__ import annotations


def euclid(pulses: int, steps: int, rotation: int = 0) -> list:
    """Lista de bool de longitud `steps` con `pulses` golpes repartidos parejo."""
    if steps <= 0:
        return []
    pulses = max(0, min(pulses, steps))
    if pulses == 0:
        return [False] * steps
    if pulses == steps:
        return [True] * steps

    pattern = [((i * pulses) % steps) < pulses for i in range(steps)]
    if rotation:
        r = rotation % steps
        pattern = pattern[r:] + pattern[:r]
    return pattern


def to_string(pattern) -> str:
    """Representacion legible para depurar: 'x..x..x.'"""
    return "".join("x" if p else "." for p in pattern)
