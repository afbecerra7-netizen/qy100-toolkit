# CLAUDE.md

> **This is the shareable subset of a larger working repository.**
>
> Not included here, and why:
>
> - **The manuals, the firmware image and Yamaha's Data Filer.** You'll already
>   have those; the page citations throughout still point at them and resolve.
> - **The reference dumps** (`dumps/`) and the generated MIDI (`midi/`). Not
>   needed to use the tools, and some contain unreleased music.
> - **An EP** that was produced with these tools. It belongs to someone else, so
>   only the technical measurements taken from it survive here — the memory
>   arithmetic, the note counts, the per-minute cost. Those are cited as "the EP".
>
> Everything else is here: the decoders, the generators, the live-play, screen
> and MIDI-export tools, and this document, which is the record of what is known
> about the format and how each piece of it was established.

Guía para Claude Code (claude.ai/code) al trabajar en este repositorio.

Material de referencia y herramientas para el **Yamaha QY100** (secuenciador
hardware, 2000) y el resto de un montaje **sin ordenador en la cadena**. Dos
subproyectos con código, cada uno con su `.venv` e independientes entre sí.

| Dónde | Qué es |
| --- | --- |
| [`qy100-arp/`](qy100-arp/) | Arpegiador y secuenciador generativo externo, por MIDI. [README](qy100-arp/README.md) |
| [`qy100-syx/`](qy100-syx/) | Volcado, decodificación y escritura por SysEx. [README](qy100-syx/README.md) |
| `Manuales/` · `manuales-md/` | Documentación. Sin build, sin tests — no inventar comandos |

```bash
cd qy100-arp && .venv/bin/python test_engine.py     # tests, sin hardware
cd qy100-syx && .venv/bin/python test_protocol.py   # 117 comprobaciones, sin hardware
```

## Los documentos

Este archivo era de 1.146 líneas y mezclaba tres materias distintas. Ahora es el
índice; el detalle está separado por tema:

| Documento | Qué contiene |
| --- | --- |
| [`docs/qy100-protocolo.md`](docs/qy100-protocolo.md) | SysEx, formato de patrón y canción, frases de fábrica, firmware |
| *(no publicado)* | El inventario del estudio: qué aparatos hay y en qué canal. Es informacion personal y no aporta a un colaborador |
| [`docs/musica-colombiana.md`](docs/musica-colombiana.md) | Las células rítmicas medidas de cada género |
| [`docs/manuales.md`](docs/manuales.md) | Dónde está cada manual y cómo leerlo |
| *(no publicado)* | El plan de un directo concreto. Las mediciones de memoria que salieron de él sí están, en el documento de protocolo |
| *(no publicado)* | Inventario de plugins de un estudio concreto |

## Cómo se marca lo que se sabe

**Casi todos los errores de este proyecto han vivido en la frontera entre lo
medido y lo deducido**, y la causa siempre es la misma: una deducción coherente
suena exactamente igual que un hecho. Por eso se marca:

```
[M]  medido contra el aparato o contra una fuente primaria
[D]  deducido de algo que sí está medido — coherente, sin comprobar
[V]  sin verificar, o comprobado por una vía que no lo demuestra
```

Los tres casos que mejor lo ilustran, todos reales:

- **El denominador del compás** se dio por ausente tras barrer cuatro valores de
  un campo de tres bits. Los válidos eran tres y solo uno cayó en el barrido.
  **Un barrido parcial no prueba una ausencia.**
- **El disparo de la DrumBrute** se atribuyó al parámetro 102 por ser el primero
  de la lista y valer 0. Es el 105. Una hipótesis de un solo dato.
- **La ida y vuelta de un archivo** se tomó como prueba de que el programa lo
  entendía. Un programa que no lo entiende y se limita a copiarlo da idéntico
  resultado. **Un round-trip solo demuestra comprensión si la salida se genera.**

Y el método que sí funciona cuando hace falta el oído de otra persona: **pedir
una comparación, no un juicio absoluto.** «¿Es el mismo sonido?» lo contesta
cualquiera; «¿esto es un Fa o un Fa sostenido?» no lo contesta casi nadie. El
mapa de pads del EP–40 se resolvió así después de siete pruebas mal diseñadas.

## Reglas que evitan romper cosas

Todas aprendidas por las malas y detalladas en los documentos.

**Al escribir en el QY100** ([protocolo](docs/qy100-protocolo.md)):

- El patrón va **entero y en el orden en que el aparato lo volcó** — pistas
  primero, las 5 cabeceras al final. Reordenarlo lo borra.
- Enmarcar toda escritura como `bulk mode ON → bloques → bulk mode OFF`. Un
  bloque suelto cuelga el aparato.
- Toda pista empieza con `F0 00`. Sin eso **suena bien y cuelga el editor**.
- `MIDI CONTROL = Off` para transferir, `In/Out` para tocar. Incompatibles.
- **Nunca mandar MIDI mientras alguien usa el panel.** Cuelga el aparato.
- **Verificar releyendo y decodificando eventos**, nunca comparando bytes: el
  aparato reserializa y devuelve 95 de 147 bytes distintos con los mismos datos.
- No mandar `CLEAR` sin que lo pidan.

**En general, y esto se repite en todo el montaje**: una escritura reportada
como exitosa no prueba nada. La MOTU se traga escrituras en silencio, el QY100
las ignora si está reproduciendo, y el editor del Minitaur muestra una lista que
puede no ser la del aparato. **Lo único que prueba el estado es releerlo.**

**Y antes de culpar a un aparato, apaga y enciende la interfaz.** Es la
comprobación más barata y ha resuelto varios diagnósticos falsos. La siguiente
más barata es pedir `dump setup`: si contesta, el equipo y el cable están bien.

## Idioma

El manual de usuario está en español y el de servicio en inglés, así que la
terminología aparece en los dos. Al citar el de usuario, conservar el término
español y glosarlo — **los botones físicos están rotulados en inglés**.

## Recurso externo

[QY100 Explorer](https://qy100.doffu.net/) — comunidad activa de QY100/QY70.
Confirma que la vía productiva es **el dato, no el firmware**: consiguen BPM
fuera de rango y patrones por encima del tope escribiendo archivos de estilo.

El repositorio público del proyecto vive en
[`qy100-toolkit`](https://github.com/afbecerra7-netizen/qy100-toolkit) y se
sincroniza con `sincronizar-publico.py`.
