# qy100-arp

Arpegiador y secuenciador generativo externo para el **Yamaha QY100**.

El QY100 no trae arpegiador — verificado buscando en el manual de usuario y en el
service manual completos: cero coincidencias. Esto se lo agrega desde fuera por
MIDI, **sin tocar el firmware del equipo**.

El QY100 sigue siendo el maestro: él manda el reloj y nosotros lo seguimos. Todo
el motor avanza por ticks de MIDI Clock (24 por negra), así que no hay deriva
posible entre ambos.

## Dos topologías

### A — Inserción (el QY100 manda el tempo)

Requiere los dos puertos del QY100 libres.

```
[microteclado del QY100 o teclado externo]
        │  MIDI OUT  →  notas + Clock + Start/Stop + Song Position
        ▼
   [qy100-arp]
        │  MIDI IN
        ▼
   [QY100 generador de tonos XG]
```

```bash
.venv/bin/python run.py --in "FastTrack" --out "FastTrack" --local-off
```

Arranca cuando le das play al QY100. Nuestra precisión de tempo no importa aquí:
solo seguimos.

### B — En serie, modo maestro (`--master`)

Para cuando el `MIDI OUT` del QY100 ya está ocupado alimentando otros sintes y no
hay retorno disponible. La caja se mete **delante del controlador**, que es donde
siempre estuvo un arpegiador, y la salida a los sintes queda intacta.

```
[controlador] → [qy100-arp] → [QY100 IN]        [QY100 OUT] → sintes
                     ↑
              maestro de reloj
```

```bash
.venv/bin/python run.py --master --bpm 120 --in "Controlador" --out "FastTrack"
```

Aquí el QY100 pasa a esclavo: `MIDI SYNC = External`, `MIDI CONTROL = In` o
`In/Out`. Con `MIDI CONTROL` incluyendo `Out`, el QY100 reenvía el reloj a los
sintes de aguas abajo, así que toda la cadena queda sincronizada.

Los mensajes que no son notas (CC, pitch bend, program change, aftertouch) pasan
de largo del controlador al QY100, para que ruedas y knobs sigan funcionando. Se
desactiva con `"passthrough": false` en la config.

**Nota sobre precisión:** en este modo el reloj lo generamos nosotros, así que la
temporización de Python sí importa. Medido sobre puertos CoreMIDI reales: tempo
exacto y jitter máximo de 3–7 ms. Los receptores MIDI promedian el reloj entrante,
así que en la práctica se sostiene, pero si necesitas precisión de hardware, la
topología A no tiene este problema porque no transmitimos reloj.

## Ajustes obligatorios en el QY100

Están en el modo UTILITY. Cambian según la topología:

| Ajuste | Topología A | Topología B (`--master`) | Pág. |
|---|---|---|---|
| `MIDI SYNC` | `Internal` | **`External`** | 127 |
| `MIDI CONTROL` | `Out` o `In/Out` | `In` o `In/Out` | 127 |
| `ECHO BACK` | `Off` | `Off` | 128 |

`ECHO BACK` en `Off` es obligatorio en ambas, y por **dos** motivos distintos:

- Con `Thru`, lo que generamos vuelve a salir y se arma un bucle de
  realimentación.
- Con `RecMontr`, el QY100 **re-canaliza todo lo que entra al canal de la pista
  de grabación seleccionada**, así que varios canales distintos colapsan en una
  sola voz. El manual lo lista como avería propia (p. 143). El síntoma engaña:
  todo suena, pero todo con el mismo instrumento.

El interruptor **HOST SELECT** del QY100 debe estar en `MIDI`.

### Notas dobladas

Si tocas el **microteclado del propio QY100**, sus notas suenan por dentro *además*
del arpegio. Para evitarlo, arranca con `--local-off`: manda Local Control OFF
(CC 122), que el chart de implementación confirma que el QY100 reconoce. Se
restaura solo al salir.

Si el script muere sin restaurarlo y el teclado te queda mudo:

```bash
.venv/bin/python run.py --local-on --out "FastTrack"
```

(o simplemente apaga y enciende el QY100).

## Instalación

Ya está hecho, pero si hay que rehacerlo:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

## Uso

Ver qué puertos hay:

```bash
.venv/bin/python run.py --list
```

En vivo contra el QY100 (lo normal):

```bash
.venv/bin/python run.py --in "FastTrack" --out "FastTrack" --local-off
```

Queda esperando; arranca cuando le des **play** al QY100. `Ctrl-C` para salir
(apaga todas las notas antes de cerrar).

### Sin el equipo conectado

Ver los eventos en consola con reloj interno:

```bash
.venv/bin/python run.py --sim --bpm 120 --notes "C3 Eb3 G3 Bb3"
```

Puerto virtual CoreMIDI, para oírlo con cualquier instrumento del Mac:

```bash
.venv/bin/python run.py --virtual --sim --bpm 120 --notes "C3 Eb3 G3 Bb3"
```

Renderizar a un archivo `.mid` sin tiempo real:

```bash
.venv/bin/python run.py --render salida.mid --bars 16 --notes "C3 Eb3 G3 Bb3"
```

El `.mid` sale a 24 PPQN, la misma resolución que el MIDI Clock, sin reescalado.

## Configuración

Todo vive en [`config.json`](config.json), que acepta comentarios con `//`.
Los canales se escriben **1-16** como en el panel del QY100, no 0-15.

### Arpegiador

| Clave | Opciones |
|---|---|
| `pattern` | `up` `down` `updown` `updown_inc` `downup` `as_played` `random` `chord` |
| `division` | `1/4` `1/4T` `1/8` `1/8T` `1/16` `1/16T` `1/32` `1/32T` |
| `octaves` | 1 en adelante — recorre el conjunto completo, no repite el patrón por octava |
| `gate` | fracción del paso; `>1` liga con la siguiente |
| `latch` | sigue arpegiando al soltar las teclas |
| `velocity_mode` | `input` (como tocaste) · `fixed` · `accent` (patrón cíclico) |

### Generativo

**`euclid_lanes`** — percusión con reparto euclidiano, uno por línea. `E(pulses, steps)`
reparte los golpes lo más parejo posible. `E(4,16)` da `x...x...x...x...`,
`E(3,8)` da el tresillo `x..x..x.`. `rotation` corre la fase; `probability < 1`
hace que la línea falle golpes a propósito.

**`melody`** — cadena de Markov de orden 1 sobre grados de escala. La matriz de
transición no está escrita a mano: se arma con dos tendencias, tamaño del
intervalo (`stepwise`, favorece el grado conjunto) y gravedad tonal
(`tonal_pull`, favorece tónica/3ª/5ª). Súbelas o bájalas para cambiar el carácter
sin tocar código.

`"follow_held": true` hace que la melodía se pegue a las notas que estés tocando
en el teclado, así sigue tus acordes en vivo en vez de una escala fija. Es
probablemente el ajuste más divertido del archivo.

## Control en vivo por CC

Sin pantalla no sirve de nada editar un archivo: los parámetros tienen que estar
bajo los knobs. La sección `midi_control` de la config mapea números de CC a
parámetros del motor, y se aplican mientras suena.

```json
"midi_control": {
  "enabled": true,
  "channel": null,
  "map": { "74": "arp.division", "75": "arp.octaves", "76": "arp.gate" }
}
```

Un CC mapeado se **consume** y no llega al QY100. Los no mapeados pasan de largo.

Parámetros disponibles:

| | |
|---|---|
| `arp.` | `enabled` `latch` `pattern` `division` `octaves` `gate` `transpose` `fixed_velocity` |
| `melody.` | `enabled` `density` `stepwise` `tonal_pull` `velocity` `base_octave` |
| `lane.<nombre>.` | `enabled` `pulses` `rotation` `probability` `velocity` |

`<nombre>` es el campo `name` de la línea euclidiana (`bombo`, `caja`, `hihat` por
defecto). Un nombre o parámetro que no exista hace fallar el arranque con un
mensaje claro, en vez de quedarse callado.

Para averiguar qué CC manda cada knob de tu controlador, corre con `--sim` y
mira lo que llega.

## Pruebas

```bash
.venv/bin/python test_engine.py     # motor, sin hardware
```

```bash
.venv/bin/python test_control.py    # control por CC y ruteo de mensajes
```

```bash
.venv/bin/python test_master.py     # modo maestro sobre puertos CoreMIDI reales
```

`test_engine.py` cubre los patrones euclidianos, la cuantización a escala,
el orden de notas de cada patrón del arpegiador, la temporización en ticks, la
propagación de velocity a las octavas, el alineado por Song Position Pointer, y
que ningún patrón deje notas colgadas (`note_on` == `note_off`).

`test_master.py` levanta puertos virtuales, corre el programa de verdad como
subproceso y verifica contra MIDI real: que transmita Start/Clock/Stop, el tempo
y el jitter medidos, que los CC del controlador pasen de largo, y que **al matar
el proceso no queden notas sonando** — importante cuando hay sintes aguas abajo.

## Recursos externos

[QY100 Explorer](https://qy100.doffu.net/) es una comunidad activa dedicada al
QY100/QY70. Es relevante porque confirma que la vía productiva para extender el
equipo es **modificar datos, no firmware**: consiguen BPM fuera del rango normal
y patrones de más de 8 compases fabricando archivos de estilo a medida y
cargándolos por SysEx (`.syx` / `.Q1P`). Tienen descargas de estilos y un par de
webtools (generador de LFO MIDI, logger MIDI).
