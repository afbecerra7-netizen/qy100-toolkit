# qy100-syx

Herramientas de respaldo, análisis y autoría SysEx para el **Yamaha QY100**.
Permiten conservar la SRAM del equipo, inspeccionar volcados y construir patrones
o canciones que el secuenciador reproduce sin un computador conectado.

> **Licencia**: el código va bajo [MIT](../LICENSE) y la documentación bajo
> [CC BY 4.0](../LICENSE-DOCS). Las tablas derivadas de la documentación de
> Yamaha y el material de terceros están identificados en [NOTICE](../NOTICE).


El proyecto comenzó como una utilidad de ingeniería inversa. El formato de
patrones ya está resuelto y verificado contra hardware; el código actual puede
leer y escribir eventos, pistas multibloque, cabeceras, secciones, voces, mezcla,
métricas y acordes. También están resueltas las pistas principales del modo
canción.

## Qué puede hacer

- Respaldar canciones, patrones, setup y efectos de guitarra.
- Capturar volcados iniciados desde el panel.
- Inspeccionar, validar y comparar archivos `.syx`.
- Restaurar respaldos con confirmación previa.
- Generar frases euclidianas, Markov o **arpegios** dentro de un patrón.
- Crear una pista que todavía no exista y registrarla en la cabecera.
- Leer y escribir las 16 pistas MIDI de una canción.
- Buscar las 525 voces normales y los 22 kits documentados.
- Tocar el generador de tonos en vivo, sin escribir en su memoria.
- Exportar a archivo MIDI estándar, que es la ruta corta hacia Ableton.

La implementación se apoya en el service manual, la Tabla 1-9, volcados medidos
en el dispositivo y el decodificador del Data Filer oficial de Yamaha.

## Qué hay aquí

Cada script vive en la subcarpeta de lo que hace, y **todos se corren desde
`qy100-syx/`**, estén donde estén: `.venv/bin/python herramientas/tocar.py`.

| Carpeta | Qué guarda |
| --- | --- |
| `qy100syx/` | El paquete: protocolo, formatos de patrón y canción, generadores |
| `herramientas/` | Lo que se usa contra el aparato o contra archivos: tocar, importar, exportar, pantalla, sondas |
| `medir/` | Lo que recuenta las cifras que citan los documentos |
| `extraer/` | Extracción de solo lectura desde los manuales y la imagen del firmware |
| `experimentos/` | Barridos y diagnósticos de una vez, guardados como prueba de un hallazgo |
| `datos/` | Las tablas JSON: voces, frases, estilos, tambores, bancos, efectos |
| `dumps/` · `midi/` | Volcados de referencia y MIDI generado |


| Archivo | Para qué |
| --- | --- |
| [`syx.py`](syx.py) | La herramienta principal: volcar, inspeccionar, restaurar, generar pistas y estilos enteros, buscar voces y frases. |
| [`herramientas/tocar.py`](herramientas/tocar.py) | Toca el generador de tonos en tiempo real. **Aquí el maestro del reloj somos nosotros**, al revés que en `qy100-arp`. No escribe nada en el equipo. |
| [`herramientas/exportar_midi.py`](herramientas/exportar_midi.py) | Escribe un `.mid` estándar. Para mover notas a un DAW **le gana a la transferencia**: exacto, instantáneo, y no pierde bloques en silencio. |
| [`extraer/extraer_rom.py`](extraer/extraer_rom.py) | Decodifica la ROM del firmware; de aquí salió `datos/voces.json`. |
| [`extraer/extraer_frases.py`](extraer/extraer_frases.py) | Extrae las 4.285 frases preset del Data List. Se valida solo. |
| [`test_protocol.py`](test_protocol.py) | 182 comprobaciones, sin hardware. Unas cuantas leen `dumps/`, asi que el total baja si el conjunto de volcados es parcial. |
| [`test_regresiones.py`](test_regresiones.py) | Reintroduce cada defecto conocido y exige que la suite lo cace. |
| [`medir/medir_volcados.py`](medir/medir_volcados.py) | Recuenta sobre los volcados las cifras que citan los documentos. |
| [`test_generos.py`](test_generos.py) | 109 comprobaciones sobre los motores de género (menos si `midi/` va incompleto: unas cuantas leen los loops). |
| [`herramientas/importar_tribe.py`](herramientas/importar_tribe.py) | Traduce un loop de TRIBE Player al kit XG, con el criterio de cada golpe escrito al lado. |
| [`medir/medir_audio.py`](medir/medir_audio.py) | ¿Binaria o ternaria? — sobre una grabación. Lleva `--autotest` con clicks sintéticos; si falla, ninguna medición suya vale. |
| [`medir/medir_loops.py`](medir/medir_loops.py) | Lo mismo sobre loops MIDI: recalcula toda cifra de loop que citen los documentos. |
| [`medir/pesar_estilos.py`](medir/pesar_estilos.py) | Pesa cada estilo en bloques y en KB de memoria del aparato. |
| [`herramientas/m4l_qy100.py`](herramientas/m4l_qy100.py) | Genera **QY100 Part**, un dispositivo de Max for Live para manejar una parte del QY100 desde Ableton: voz con nombre y banco, CC y tipos de efecto. Ya generado en [`max/`](max/); cómo usarlo, en [`docs/max-for-live.md`](../docs/max-for-live.md). No abre puertos MIDI. |
| [`herramientas/pantalla.py`](herramientas/pantalla.py) | Escribe texto y mapas de bits de 16x16 en la pantalla, por XG Display Data. |
| [`experimentos/barrer_categorias.py`](experimentos/barrer_categorias.py) | Barre valores de una referencia a frase preset **escribiendo y oyendo**, sin volcar. Guarda el método aunque su lectura acabara siendo el panel. |
| `herramientas/probe.py` | Sondas sueltas de ingeniería inversa. |
| [`herramientas/emulador.py`](herramientas/emulador.py) | Escribe un patrón en el emulador QYΩ y lo lee de vuelta, comparando notas: **un primer filtro** antes de escribirle al aparato. No abre puertos MIDI. |

Datos de referencia, todos generados y verificados, no transcritos a mano:

| Archivo | Contenido |
| --- | --- |
| [`datos/voces.json`](datos/voces.json) | 525 voces normales y 22 kits. **Solo las 128 primeras son direccionables**: más allá son variaciones XG cuyo *bank LSB* no está descifrado. |
| [`datos/frases.json`](datos/frases.json) | Las 4.285 frases preset, por categoría, compás y número. |
| [`datos/tambores.json`](datos/tambores.json) | Mapa de notas de *Tambores de San Jacinto* (Tribe Instruments): 8 instrumentos, 32 articulaciones. Incluye los pares L/R, que son mano izquierda y derecha — alternarlos es lo que hace que un patrón suene tocado. |

## Instalación

Desde esta carpeta:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Dependencias: `mido` y `python-rtmidi`.

## Conexión y preparación del QY100

```text
QY100 MIDI OUT  →  interfaz MIDI IN
interfaz MIDI OUT  →  QY100 MIDI IN
```

Antes de transferir:

- `HOST SELECT = MIDI`.
- El secuenciador debe estar detenido y en la pantalla principal.
- El aparato debe estar **en modo de reproducción de patrón** para recibir
  bulk de patrón, y en modo canción para el de canción (manual, p. 129).
- No se debe tocar el panel durante la transferencia.
- `MIDI CONTROL = Off` es **recomendable pero no requisito**: el manual (p. 127)
  lo limita a la reproducción sincronizada y un patrón entero se escribió y
  releyó el 2026-08-12 sin tocarlo. La recomendación queda por otra razón,
  medida: en `Out` o `In/Out` el QY100 emite ~49 mensajes de reloj por segundo,
  y en transferencias largas esa corriente puede provocar pérdida silenciosa de
  bloques aunque los checksums salgan válidos. Este documento lo daba por
  requisito, y era la inferencia de siempre vestida de regla.

## Uso

Los argumentos de conexión pueden escribirse antes o después del subcomando.
Los nombres de puerto aceptan coincidencias parciales.

### Puertos y respaldos

```bash
.venv/bin/python syx.py --list

# Los 64 patrones de usuario
.venv/bin/python syx.py dump patterns --in "M4" --out "M4"

# Toda la memoria respaldable
.venv/bin/python syx.py dump all --in "M4" --out "M4" \
  -o dumps/respaldo-completo.syx

# Un patrón o una canción
.venv/bin/python syx.py dump pattern 1 --in "M4" --out "M4"
.venv/bin/python syx.py dump song 1 --in "M4" --out "M4"
```

Otros destinos: `songs`, `setup`, `effects`, `info-songs` e `info-patterns`.
Sin `-o`, el resultado se guarda en `dumps/` con fecha y hora.

Si el equipo no responde a una petición, se puede iniciar el volcado desde el
panel y capturarlo:

```bash
.venv/bin/python syx.py monitor -o dumps/manual.syx --in "M4"
```

### Inspección y comparación

```bash
.venv/bin/python syx.py inspect dumps/respaldo-completo.syx
.venv/bin/python syx.py diff dumps/antes.syx dumps/despues.syx
```

`inspect` separa los mensajes, nombra sus direcciones, comprueba longitudes y
checksums y señala comandos destructivos. `diff` agrupa cambios por dirección y
offset; fue la herramienta principal para descifrar el formato.

### Generar una frase

Sin `--escribir`, `generar` solo prepara y muestra una previsualización:

```bash
# Ritmo euclidiano E(5,16), Main A, pista PC
.venv/bin/python syx.py generar euclid \
  --patron 1 --seccion 1 --pista 2 \
  --pulsos 5 --pasos 16 --nota 36 --tipo Bypass

# Melodía Markov reproducible en Do menor
.venv/bin/python syx.py generar markov \
  --patron 1 --seccion 1 --pista 4 \
  --root C --escala minor --octava 4 --semilla 42
```

Para escribir se añaden los puertos y `--escribir`. El programa primero lee el
patrón completo, sustituye o crea la pista, actualiza el registro de la cabecera,
ordena las pistas antes de los cinco bloques de cabecera y pide confirmación.

```bash
.venv/bin/python syx.py generar euclid \
  --patron 1 --seccion 1 --pista 2 \
  --pulsos 5 --pasos 16 --nota 36 --tipo Bypass \
  --in "M4" --out "M4" --escribir
```

Las secciones son `0=Intro`, `1=Main A`, `2=Main B`, `3=Fill AB`,
`4=Fill BA`, `5=Ending`. Las pistas son `0–7`, o por nombre: D1, D2, PC, BA y C1–C4.

Después de escribir, `generar` **relee el patrón** y compara las notas
decodificadas: termina en `IGUAL` o en `DISTINTO`, y con `DISTINTO` sale con error.

### Un arpegio dentro del QY100

El QY100 no trae arpegiador. `generar arp` lo hornea: el arpegiador de
[`qy100-arp`](../qy100-arp/) toca en frío un acorde mantenido y el resultado se
escribe como frase. Por defecto la pista queda en `TYPE = Chord 2` con ese acorde
de fuente, así que el QY100 **reacomoda el arpegio a cada acorde de su pista de
acordes**, sin nada conectado.

```bash
# Sube y baja por CM7 en dos octavas, semicorcheas, en C1 de Main A
.venv/bin/python syx.py generar arp \
  --patron 10 --seccion 1 --pista C1 --compases 1 \
  --acorde CM7 --forma updown --octavas 2 --division 1/16 --voz SquareLd
```

- `--forma`: `up`, `down`, `updown`, `updown_inc`, `downup`, `as_played`,
  `random` (con `--semilla`, reproducible) o `chord`.
- `--gate` (0.5 por defecto) es la fracción del paso que suena. Por debajo de 1
  dos notas no se pisan, que es lo que necesita un sinte monofónico.
- `--acorde` admite los tipos M, M7, 6, add9, m, m7, m6 y 7.
- Chord 2 y no Chord 1: Chord 1 lleva un bit en la cabecera medido solo para la
  pista 0, y Chord 2 no lo necesita. `--tipo` lo cambia.

**Probar primero en el emulador.** Con `--emulador`, `generar` lee y escribe en el
emulador QYΩ (`./emu serve`, 127.0.0.1:8100) en vez de en el equipo, sin pedir
confirmación porque no toca nada real. `[M]` Así se escribió el ejemplo de arriba
y volvió igual (2026-11-22): 16 notas, `Chord 2`, fuente `CM7`. Que el emulador
lo acepte es el primer filtro; el QY100 de verdad se comprueba aparte. Para oírlo
en el emulador, en modo patrón hay que pasar del 128: `001`–`128` son los estilos
de fábrica y el patrón de usuario 10 es `U10`.

### Generar un estilo entero

```bash
.venv/bin/python syx.py estilo --patron 60 --in "M4" --out "M4"
```

Seis secciones por seis pistas **en una sola transferencia**. La diferencia con
`generar` no es de tamaño: aquel lee el patrón, sustituye una pista y lo reescribe
entero, así que montar un estilo serían 36 transferencias completas — y cada una
es una ocasión de que un corte a medias corrompa la contabilidad de memoria del
equipo. Aquí se lee una vez, se arma todo en memoria y se escribe una vez.

Sin `--escribir` solo previsualiza. `--pistas 4,5` escribe solo esas, que es lo
que permite **el patrón mixto**: frases de fábrica referenciadas en las pistas
rítmicas y material generativo en las de acorde.

Las secciones no son intercambiables y la receta lo respeta: `Fill AB` y `Fill BA`
son transiciones **direccionales** y el footswitch cicla entre ellas en vivo, así
que la forma la dictó Yamaha y lo único que se elige es la densidad.

### Buscar frases preset

```bash
.venv/bin/python syx.py frases Bossa
.venv/bin/python syx.py frases --categoria PC --beat 16
```

Devuelve **categoría, beat y número**, que son los tres campos con los que se
direcciona una frase — y justo lo que hay que escribir en la cabecera del patrón
para referenciarla. Avisa si el juego de las seis secciones está completo.

**Una frase de fábrica es una referencia y no cuesta memoria de usuario**: son dos
bytes del registro de la cabecera y nada más. Un estilo puede apoyar toda su base
rítmica en las 4.285 de Yamaha y pagar solo por el material propio.

Hoy se pueden escribir 7 de las 15 categorías (`Da` `Fa` `PC` `Ba` `Gb` `KC`
`BR`); el resto solo desde el panel. Ver `AGENTS.md`.

### Buscar voces

```bash
.venv/bin/python syx.py voces Square
.venv/bin/python syx.py voces Kit
```

### Tocar en vivo

No escribe nada en la memoria del equipo: solo suena.

```bash
.venv/bin/python herramientas/tocar.py barrido          # tres notas en cada uno de los 16 canales
.venv/bin/python herramientas/tocar.py acompanar        # base en Mi menor para tocar guitarra encima
.venv/bin/python herramientas/tocar.py andino --tono G  # huayno, transportable
```

Dos ajustes del equipo son obligatorios. **`ECHO BACK` no puede estar en
`RecMontr`**: con eso el QY100 re-canaliza lo que entra al canal de la pista
seleccionada, y los 16 canales colapsan en una sola voz — el manual lo lista
como avería propia en la página 143. Y conviene **elegir una canción vacía**,
porque un Program Change reescribe la voz del mezclador de la canción cargada.

### Exportar a MIDI

```bash
.venv/bin/python herramientas/exportar_midi.py mi-tema --cuantizar 16
```

Los motores trabajan a 480 relojes por negra, que es el `ticks_per_beat` del
archivo: la conversión es 1:1 y sin redondeo. `--cuantizar 16` quita solo la
microtemporización de `humanizar()`, porque toda la colocación deliberada ya cae
en semicorcheas exactas. **Cuantizar más grueso destruye el material**: arrastra
el bajo de la semicorchea 3 al tiempo fuerte.

### Restaurar

`send` escribe en la memoria de usuario y pide confirmación explícita:

```bash
.venv/bin/python syx.py send dumps/respaldo-completo.syx --out "M4"
```

## Formatos resueltos

### Patrón

- Dirección `12 nn tr`; `tr = sección × 8 + pista`.
- Cinco bloques de cabecera y hasta 48 pistas por patrón.
- Payload de 147 bytes MIDI empaquetado en 128 bytes reales por bloque.
- Eventos de tiempo y nota de longitud variable.
- Pistas multibloque, marcador inicial `F0 00` y terminador `F2`.
- Nombre, tempo, compases por sección, métrica, registro, acorde y mezclador.
- Hasta 32 compases por sección, aunque el panel normalmente ofrezca ocho.

### Canción

- Dirección `11 nn tr`.
- Dieciséis pistas de secuenciador, una por canal MIDI.
- Pista de patrones `Pt`, pista de acordes `Cd` y cabecera de seis bloques.
- Misma gramática de notas que los patrones, sin el prefijo de frase.
- Verificado con una canción de 112 compases y más de 3.000 notas.

El registro del descubrimiento está en [`HALLAZGOS.md`](HALLAZGOS.md). Su parte
inferior conserva hipótesis históricas que después resultaron incorrectas; para
el comportamiento vigente mandan `qy100syx/patternfmt.py`,
`qy100syx/songfmt.py`, las pruebas y el resumen raíz [`../AGENTS.md`](../AGENTS.md).

## Pruebas

```bash
.venv/bin/python test_protocol.py
```

Son **175 comprobaciones offline**, sin hardware — menos si `dumps/` va incompleto, porque las ultimas decodifican volcados reales. Cubren direcciones y plantillas
del Data Filer, construcción y parseo de mensajes, checksum, detección de
corrupción, empaquetado 7↔8, pistas reales, codificación ida y vuelta, secciones,
cabeceras y archivos de 32 compases.

## Reglas de seguridad

1. Haz un `dump all` antes de escribir.
2. Nunca envíes un `CLEAR` para hacer espacio: escribir una pista ya la
   reemplaza.
3. Toda escritura debe ir enmarcada por `bulk mode ON/OFF`.
4. Envía el objeto completo y en el orden del equipo: pistas primero, cabecera al
   final.
5. No transfieras mientras el secuenciador reproduce o está en una pantalla de
   edición; el QY100 puede ignorarlo sin informar error.
6. Verifica leyendo de vuelta y decodificando eventos. El equipo puede
   reserializar padding válido con bytes diferentes.
7. No uses el panel mientras `bulk mode` está activo: el panel queda bloqueado y
   una interacción concurrente puede exigir un ciclo de energía.

`send` advierte qué direcciones sobrescribirá, detecta comandos de borrado y
solicita confirmación escrita. La herramienta no genera comandos `CLEAR` por su
cuenta.
