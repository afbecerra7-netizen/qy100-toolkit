"""Escalas y cuantizacion de notas."""

from __future__ import annotations

SCALES = {
    "chromatic":      [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
    "major":          [0, 2, 4, 5, 7, 9, 11],
    "minor":          [0, 2, 3, 5, 7, 8, 10],
    "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
    "melodic_minor":  [0, 2, 3, 5, 7, 9, 11],
    "dorian":         [0, 2, 3, 5, 7, 9, 10],
    "phrygian":       [0, 1, 3, 5, 7, 8, 10],
    "lydian":         [0, 2, 4, 6, 7, 9, 11],
    "mixolydian":     [0, 2, 4, 5, 7, 9, 10],
    "locrian":        [0, 1, 3, 5, 6, 8, 10],
    "pentatonic":     [0, 2, 4, 7, 9],
    "pentatonic_min": [0, 3, 5, 7, 10],
    "blues":          [0, 3, 5, 6, 7, 10],
    "whole_tone":     [0, 2, 4, 6, 8, 10],
}

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_ALIASES = {"DB": "C#", "EB": "D#", "GB": "F#", "AB": "G#", "BB": "A#"}


def parse_note(text) -> int:
    """Acepta 60, "C4", "F#3", "Bb2". C4 = 60 (convencion Yamaha)."""
    if isinstance(text, int):
        return text
    s = str(text).strip().upper()
    if s.lstrip("-").isdigit():
        return int(s)

    i = 1
    if len(s) > 1 and s[1] in "#B":
        i = 2
    head, tail = s[:i], s[i:]
    head = _ALIASES.get(head, head)
    if head not in NOTE_NAMES:
        raise ValueError("nota invalida: %r" % (text,))
    octave = int(tail) if tail else 4
    return NOTE_NAMES.index(head) + (octave + 1) * 12


def note_name(note: int) -> str:
    return "%s%d" % (NOTE_NAMES[note % 12], note // 12 - 1)


def scale_pitches(root: int, scale: str) -> list:
    """Clases de altura (0-11) de la escala, ya transpuestas a la tonica."""
    try:
        steps = SCALES[scale]
    except KeyError:
        raise ValueError("escala desconocida: %r (opciones: %s)"
                         % (scale, ", ".join(sorted(SCALES))))
    return sorted({(root + s) % 12 for s in steps})


def quantize(note: int, pitches) -> int:
    """Mueve la nota a la altura mas cercana del conjunto, sin salirse de rango.

    Cuando queda a la misma distancia de dos alturas validas (pasa siempre con
    las notas cromaticas en escalas de 7 grados) se elige la de abajo, por
    convenio, para que el resultado sea determinista.
    """
    if not pitches:
        return note
    best, best_d = note, 128
    for delta in range(-6, 7):
        cand = note + delta
        if 0 <= cand <= 127 and cand % 12 in pitches and abs(delta) < best_d:
            best, best_d = cand, abs(delta)
    return best


def degree_to_note(degree: int, root: int, scale: str, base_octave: int) -> int:
    """Grado de escala (puede salirse del rango, se envuelve en octavas) -> nota MIDI."""
    steps = SCALES[scale]
    n = len(steps)
    octave, idx = divmod(degree, n)
    note = root + steps[idx] + 12 * (base_octave + 1 + octave)
    return max(0, min(127, note))
