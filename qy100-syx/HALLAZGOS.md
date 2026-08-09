# Formato de patrón del QY100 — RESUELTO

> **El formato está descifrado.** La gramática de eventos salió del decodificador
> del propio Data Filer de Yamaha (`QY100.exe`) y está verificada de forma
> independiente contra nuestras ocho capturas de referencia.
>
> Implementado en `qy100syx/patternfmt.py`. Lo que sigue debajo de "Cómo se llegó
> aquí" es el registro del proceso, con varias conclusiones intermedias que
> resultaron **equivocadas** — se conservan porque explican los errores y cómo se
> detectaron, pero **no son la verdad actual**.

## El formato

### 1. Desempaquetado

Los 147 bytes de 7 bits del payload SysEx se concatenan en 1029 bits, de los que
se toman **1024 = 128 bytes de 8 bits**; los 5 últimos se descartan. El descarte
es **por bloque**, no continuo entre bloques.

Sobre ese flujo desempaquetado **los campos sí están alineados a byte**. Lo que
durante toda la investigación pareció "campos a mitad de byte" era el efecto de
mirar el stream en unidades de 7 bits.

### 2. Gramática de eventos

La lista empieza en el **byte 26** del bloque desempaquetado. Eventos de longitud
variable, identificados por el byte de estado:

| Estado | Bytes | Significado |
| --- | --- | --- |
| `8n`–`9n` | 1 | tiempo, delta = `estado & 0x1F` (0–31 relojes) |
| `An`–`Bn` | 2 | tiempo, delta = `((estado & 0x1F) << 7) \| b1` (0–4095) |
| `Cn` | 3 | nota, gate = `n` |
| `Dn` | 4 | nota, gate = `(n << 7) \| b1`, luego altura y velocity |
| `En` | 5 | nota, gate = `(n << 14) \| (b1 << 7) \| b2` |
| `F0` | 2 | marcador, no avanza el tiempo |
| `F2` | 1 | **fin de pista** |

Los estados `F1` y `F3`–`FF` tienen longitud asignada en el binario pero no
aparecen en nuestros datos: no sabemos qué significan.

### 3. La duración es gate time en relojes

No es índice a una tabla de figuras. **El QY100 usa por defecto el 90 % de la
figura**:

| Figura | Relojes | Gate observado |
| --- | --- | --- |
| semicorchea | 120 | **108** |
| negra | 480 | **432** |

Factor 4 exacto, que es semicorchea → negra. Un solo punto habría bastado: la
escala es directa.

### 4. Cabecera del patrón — nombre y longitud

En el **primer bloque `12 nn 7F`**, ya desempaquetado:

| Bytes | Campo |
| --- | --- |
| 6–13 | **nombre** del patrón, 8 caracteres ASCII, rellenado con espacios |
| 15–20 | **compases por sección**, un byte cada una, valor = compases − 1 |

Los seis bytes van en el orden de `SECTIONS`: Intro, Main A, Main B, Fill AB,
Fill BA, Ending.

Descifrado comparando nuestros volcados contra el **archivo de desbloqueo de 32
compases de [QY100 Explorer](https://qy100.doffu.net/)**. Su archivo trae `1F`
(31 → 32 compases) en las seis secciones y el nombre `MEASR32`; los nuestros
traen `01 02 01 00 00 01` → 2, 3, 2, 1, 1, 2 compases, que coincide exactamente
con la duración real medida en las pistas y con los valores por defecto del
manual.

**El "desbloqueo" es simplemente poner un valor mayor del que la interfaz
permite.** El equipo respeta hasta 32 aunque su UI tope en 8. Aviso de doffu que
conviene respetar: **al reducir la longitud desde el panel ya no se puede volver
a subir** sin recargar el archivo.

Su archivo revela además dos cosas del protocolo:

- **`nn = 0x7E` significa "la ranura seleccionada ahora"**, no un número de
  patrón — por eso su Readme insiste en navegar antes a una ranura de usuario
  vacía. Los patrones normales van del 0 al 63.
- El archivo del QY70 es **idéntico salvo `02` en lugar de `12`**, que confirma
  desde fuera el `P=1`/`P=0` de la Tabla 1-9.

## Verificación

`decode_track` reproduce las ocho capturas de referencia, incluyendo todos los
cambios que hicimos a propósito:

```
30-una-nota    Note(pitch=60, vel=112, gate=108, t=0)     total 3840
31-semitono    Note(pitch=61, ...)
33-octava      Note(pitch=72, ...)
34-vel-suave   Note(pitch=60, vel=32, ...)
36-posicion    Note(pitch=60, ..., t=1920)                total 3840
41-duracion    gate=432 en ambas notas
53-escrito-72  Note(pitch=72, ...) + Note(pitch=60, ...)  ← nuestra escritura
```

Los totales dan múltiplos exactos de 1920: INTRO = 3840 (2 compases), MAIN A =
5760 (3 compases).

## Dos "verificaciones" nuestras que estaban mal

Vale la pena dejarlas anotadas, porque las dimos por buenas con pruebas que
pasaban:

- **Velocity**: creíamos 56 y 16. Son **112 y 32**. Leíamos 7 bits de un valor de
  8, o sea la mitad exacta. Las pruebas pasaban porque comparaban nuestra lectura
  contra sí misma.
- **Duración**: el campo que daba 27 y 204 era una lectura desalineada del gate.
  Los valores reales son 108 y 432, y los 27/204 se reproducen exactamente
  leyendo 8 bits desde la posición equivocada — por eso parecían consistentes.

La lección: **un decodificador que se verifica contra sus propias lecturas no
verifica nada.** Hizo falta una fuente externa —el binario de Yamaha— para
detectarlo.

## Generar desde cero — VERIFICADO (2026-07-29)

Se construyó el flujo de eventos completo —no una modificación de uno existente—
y el QY100 lo aceptó: **arpegio de Do mayor, 12 negras sobre 3 compases,
confirmado de oído en Main A.**

Tres cosas quedaron demostradas de paso:

- **Escribir un bloque REEMPLAZA la pista, no la fusiona.** La pista tenía 2
  notas antes y quedaron exactamente las 12 generadas. No hace falta un `CLEAR`
  previo, y conviene no darlo: es destructivo y resulta innecesario.
- La velocity se escribe tal cual. Se eligió 100 —un valor que el equipo nunca
  pone solo— y volvió 100.
- El prefijo de 26 bytes se puede reutilizar de un bloque real sin entenderlo.
  Sigue sin descifrarse, pero ya no bloquea nada.

### El techo de un bloque: 16 notas

Un bloque son 128 bytes desempaquetados, de los que 26 son el prefijo y 3 el
cierre: **quedan 99 bytes para eventos.**

| Caso | bytes/nota | notas |
| --- | --- | --- |
| Negras o semicorcheas (delta > 31, evento `Dn`) | 6 | **16** |
| Notas muy juntas (delta ≤ 31) | 5 | 19 |
| Staccato con gate ≤ 15 (evento `Cn`) | 4 | 24 |

Esto importa para el objetivo del proyecto: un arpegio de semicorcheas en 3
compases son 48 notas, **tres bloques**. Todas nuestras grabaciones de prueba
fueron demasiado pequeñas para producir más de un bloque por pista, así que
**cómo se encadenan sigue sin verse.** Es lo siguiente en la ruta crítica.

## Encadenado multi-bloque — RESUELTO (2026-07-29)

Se grabaron **32 notas de altura ascendente conocida** (48…79) mandándolas por
MIDI enganchadas al reloj del propio equipo. Volvieron en dos bloques y se
releen exactamente como 48…79, 5760 relojes. El modelo:

- Solo el **primer** bloque lleva el prefijo de 26 bytes.
- Los siguientes son **continuación pura del flujo, desde su byte 0**.
- El `F2` de fin aparece **una sola vez**, al final del último bloque. El
  bloque 0 de una pista larga no lo tiene.
- La cola del último bloque se rellena con `0x40`.
- El desempaquetado 7→8 con descarte de 5 bits es **por bloque**, no continuo.

Un intento previo sobre volcados antiguos daba resultados absurdos (una altura
de 161, duraciones no redondas). No era el modelo: **esas capturas tenían
bloques perdidos**, así que se estaban concatenando trozos no consecutivos.

### El marcador `F0 00` es obligatorio

Toda pista grabada por el equipo empieza su flujo con `F0 00`, incluso una
vacía (`F0 00 | t+3840 | F2`). Las que escribíamos nosotros no lo llevaban.

**Suenan perfectamente igual, pero cuelgan el editor del equipo.** Al entrar en
edición la pantalla se quedaba con el icono de reloj fijo y había que apagar.
Y cada cuelgue dejaba corrompida la contabilidad de memoria: `USED MEMORY`
marcaba lleno con 47 notas dentro, y a partir de ahí la edición se negaba con
`Memory Full`. Hicieron falta dos ciclos completos de borrado y restauración.

Lo caro fue el diagnóstico, no la corrección. El arpegio sonó bien a la primera,
así que dimos la escritura por buena y el marcador quedó anotado como "detalle
pendiente, irrelevante para generar desde cero". Era justo al revés.

**Que suene no prueba que el dato esté bien formado: el reproductor es más
tolerante que el editor.** Una escritura se verifica abriéndola en el equipo,
no solo de oído.

## Tipo de frase (TYPE) — RESUELTO (2026-07-29)

Cambiando **únicamente** ese parámetro en el equipo y volcando entre cada
cambio, cinco veces. En las cinco pruebas no se movió ningún otro byte del
patrón.

**Byte 20 del prefijo de la pista:**

| TYPE | valor | binario |
| --- | --- | --- |
| Bypass | `03` | `0000 0011` |
| Chord 1 | `90` | `1001 0000` |
| Bass | `92` | `1001 0010` |
| Parallel | `94` | `1001 0100` |
| Chord 2 | `A0` | `1010 0000` |

`Chord 1`, `Bass` y `Parallel` comparten el nibble alto `9` y se distinguen por
los bits 1–2 (0, 1, 2), lo que encaja con que el manual describa los dos últimos
como variantes de la rearmonización por raíz. Pero `Bypass` y `Chord 2` no
siguen ese esquema, así que **se usa como tabla de consulta, no se calcula**.
Los cinco valores están medidos; la aritmética de bits sería adivinada.

**Y un bit en la cabecera del patrón**, bloque 3 byte 75, valor `08`: encendido
solo con `Chord 1` y `Bass` — justo los dos tipos a los que el manual (p. 121)
dice que aplica `HI KEY`. Se predijo antes de medir `Bass` y se cumplió.

Ojo: la posición de ese bit se midió **solo para la pista 0 de Main A**. No se
sabe si el offset depende de la pista.

Verificación: `decode_phrase_type` acierta los cinco, y `set_phrase_type` +
`set_header_hikey` reproducen byte a byte los bloques del equipo en los cinco
estados.

## Voz de la frase (PHRASE VOICE) — RESUELTO (2026-07-29)

| PHRASE VOICE | byte 14 | byte 16 |
| --- | --- | --- |
| Dr010 DarkKit | `7F` | `09` |
| Ld081 SquareLd | `00` | `50` |

**Byte 14 = banco** (127 el de batería de XG, 0 el de voces normales) y
**byte 16 = número de programa en base cero**: `Dr010` → 9 y `Ld081` → 80, los
dos el número de pantalla menos uno. Dos puntos independientes que encajan.

El byte 15 vale `00` en todo lo visto y sería el sitio natural del banco LSB de
XG, pero no está medido y no se toca.

Cuidado con la distinción: esta es la voz guardada **en la frase**. La que suena
es la de la **pista**, que se ajusta en el modo PATTERN VOICE y manda sobre esta
(manual p. 57). Por eso una pista puede sonar melódica teniendo un kit de
batería escrito aquí — que fue justo lo que se observó y llevó a mirarlo.

### Una corrección que importa para el método

En la prueba del acorde fuente se anotó que el byte 16 "cambiaba con la calidad
del acorde" (`00` → `09`). **Era falso.** El byte 16 es el programa de
PHRASE VOICE, y cambió porque al entrar por primera vez en la Phrase Table el
equipo escribió allí la voz real de la pista (`Dr010` = 9). No tenía relación
con el acorde.

**En un diff, un byte que cambia a la vez que lo que tocaste no es
necesariamente consecuencia de lo que tocaste.** Abrir una pantalla de edición
ya es una acción con efectos.

## Acorde fuente (SOURCE CHORD) — leer resuelto, escribir no (2026-07-29)

Es **por pista**, así que vive en el prefijo de 26 bytes, no en la cabecera.

| SOURCE CHORD | byte 16 | byte 21 | byte 22 |
| --- | --- | --- | --- |
| CM7 | `00` | `00` | `00` |
| Cm7 | `09` | `00` | `08` |
| Fm7 | `09` | `05` | `08` |

**Byte 21 = raíz** (semitonos, Do=0; Do→Fa dio +5) y **byte 22 = tipo**, con la
misma tabla que el acorde actual. Confirmados.

El **byte 16** cambia con la calidad del acorde pero no con la raíz: es algo
derivado del tipo. Se escribe copiándolo de la tabla medida, no calculándolo.

**Escribirlo está sin verificar**, y hay una razón concreta: al cambiar esto
desde el panel también se mueve el byte 75 del bloque 3 de la cabecera, que
además se mueve con el tipo de frase y con la raíz. Ese byte empaqueta varias
cosas y no está separado. Escribir solo la pista podría dejar el patrón
incoherente.

## Acorde actual (CURRENT CHORD) — RESUELTO (2026-07-29)

> **Ojo: esto se etiquetó primero como `SOURCE CHORD` y era falso.** Los dos
> campos aparecen juntos en la pantalla Phrase Table, así que al pedir "cambia
> SOURCE CHORD" se cambió el de al lado. Lo que lo zanjó: tras escribir `Cm7` en
> estos bytes, la pantalla **principal** del equipo mostraba `Cm7` mientras la
> Phrase Table seguía mostrando `SOURCE CHORD = CM7`. Los bytes siguen a la
> principal. **`SOURCE CHORD` sigue sin localizar.**

Está en la cabecera del patrón, bloque 0, en dos bytes separados. Que viva ahí
encaja con que sea común a todo el patrón, mientras que `SOURCE CHORD` es por
frase.

| byte del bloque 0 | qué es |
| --- | --- |
| 118 | raíz, en semitonos con Do = 0 |
| 124 | tipo de acorde |

Medido tres veces, cambiando solo ese parámetro, sin que se moviera ningún otro
byte:

| acorde | 118 | 124 |
| --- | --- | --- |
| CM7 | `00` | `00` |
| Fm7 | `05` | `08` |
| G7 | `07` | `0D` |

La raíz queda demostrada: Do→Fa son 5 semitonos y el byte pasó de 0 a 5; Sol dio
7. De los **26 tipos de acorde** que tiene el equipo solo hay tres medidos
(`M7`=0, `m7`=8, `7`=13); el resto se añaden repitiendo la medición, a un
volcado por tipo. **No se rellenan por conjetura.**

Con `Bypass` el acorde fuente se ignora: cambiarlo de `CM7` a `Fm7` no alteró el
sonido, que es justo lo que promete el manual.

## Resuelto después de escribir este documento

La cabecera del patrón, que aquí figuraba entera como pendiente, está hoy
descifrada y **se escribe de rutina**. `CLAUDE.md` es la referencia al día de
cada campo; el resumen:

| Campo | Dónde | Cómo se supo |
| --- | --- | --- |
| Tempo | bytes 0–1, décimas de BPM | medido |
| Nombre | bytes 6–13 | medido |
| Signatura completa | **byte 14** | 40 archivos de doffu, 0 fallos |
| Compases por sección | bytes 15–20 | diff contra el archivo de 32 compases |
| Registro de pistas | 21–68 banderas, 69–116 `tr` | medido — **sin esto la pista se ve vacía**. Las dos tablas están **sobrecargadas**: ver abajo |
| Acorde actual por sección | 117–122 raíz, 123–128 tipo | medido, 27 tipos |
| Mezclador | 154 programa … 210 variation | medido |

La signatura cabe entera en el byte 14:
`byte 14 = ((numerador - 1) << 3) | (16 / denominador)`, con `/4 /8 /16` como
únicos denominadores que caben en tres bits.

El **byte 19 del prefijo** está medido para las ocho pistas: `PC` y `BA` valen
3, las otras seis valen 7. La tanda llevaba `BA` de control.

## El registro tiene tres estados, y las dos tablas están sobrecargadas

Medido el 8 de agosto de 2026 sobre un equipo recién borrado — la línea base
ideal, porque un patrón vacío no devuelve absolutamente nada y cualquier cosa que
aparezca es lo que se acaba de hacer.

**Una frase preset asignada a una pista no deja ni un bloque de pista.** Solo
aparecen los 5 de cabecera: el patrón guarda una referencia y las notas se quedan
en la ROM. **No cuesta memoria de usuario.**

```
bandera  (21–68)    = (índice de categoría << 3) | estado      5 bits + 3
tabla tr (69–116)   = número de frase − 1

   estado 0   contenido propio      (la tabla tr guarda el `tr`)
   estado 1   frase preset, 16 beat (la tabla tr guarda el número)
   estado 2   frase preset, 8 beat
   estado 3   frase preset, 3/4 beat
   estado 6   vacía
```

La tabla de categorías sale del **firmware**, offset `0x11AE24`: 32 entradas de
3 bytes, los quince códigos y huecos `__` reservados por Yamaha.

```
-- Da Db __ __ Fa Fb __ __ PC __ __ __ Ba Bb __ __ __ Ga Gb GR __ __ KC KR __ __ __ PD BR SE US
```

Con eso **`F8` y `FE` dejan de ser casos especiales**: son la categoría `US`
—frase de usuario, índice 31— con estado 0 y 6.

Verificado escribiendo `09`/`00` por SysEx y leyendo en el panel
`Da 001 80MRk-1I`, que es exactamente lo que predice `frases.json`, extraído del
PDF. Dos fuentes que no se hablan dando lo mismo.

**Consecuencia para quien escriba el registro**: `set_registry` debe preservar
toda ranura cuyo nibble bajo no reconozca. Antes ponía `F8`/`FE` en las 48 sin
mirar, y escribir una sola pista generativa borraba en silencio todas las frases
preset asignadas desde el panel — sin error, sin señal, solo desaparecían.

**Tres lecturas equivocadas por el camino, las tres por el mismo motivo.** Se leyó
`09` frente a `B9` como dependencia del rol de la pista (por analogía con el byte
19 del prefijo); era la categoría. Se leyó el nibble bajo `9` como "es una frase
preset"; era el **beat**, y salía siempre `9` porque en las pruebas anteriores el
beat estaba fijo. Y se dio por refutada una lista ordenada de categorías usando
"vacío" para dos cosas distintas —fila en blanco y fila con categoría pero sin
nombre—. **Un campo que no varía en el experimento parece una constante**, y
llamarlo constante es afirmar algo que no se ha probado.

## Lo que sigue sin resolver

- El marcador `F0 xx` de cada pista: qué significa el segundo byte
- **La mayor parte de los 26 bytes del prefijo.** Identificados: 0–11 nombre,
  14 banco de voz, 16 programa de voz, 19 rol de pista, 20 tipo de frase,
  21–22 acorde fuente. El byte 12 **parece** ser `compases − 1`, pero las 9
  coincidencias vienen de patrones con las mismas longitudes: son dos
  observaciones repetidas, no nueve independientes
- **Escribir `SOURCE CHORD`**, bloqueado por el byte 75 del bloque 3, que
  empaqueta varios campos y no se deja aislar
- El array del **byte 218** del mezclador (64 en todas las pistas)
- El **bank LSB** de las 397 voces XG por encima del programa 127
- Los estados `F1`, `F5`–`FF` (`F3` y `F4` se resolvieron en canciones)


---

# Cómo se llegó aquí

> Lo que sigue es el registro del proceso. **Contiene conclusiones que
> resultaron equivocadas** y se conserva por el método, no por los resultados.

## Escribir en el equipo — VERIFICADO

Ciclo completo probado contra el QY100: leer un patrón, cambiarle la altura de
una nota, devolvérselo, y **oír la nota modificada al reproducir**. Confirmado
de oído, no solo por volcado.

### El procedimiento importa, y no está en el manual

```
1. bulk mode ON
2. los bloques, con pausa entre cada uno (100 ms funciona)
3. bulk mode OFF
```

**Mandar un bloque suelto sin ese marco borra el patrón de destino y deja al
equipo colgado en modo bulk**, sin responder a nada. Pasó: tras enviar un solo
bloque, el QY100 dejó de contestar a todo —ni siquiera a un Identity Request— y
los patrones quedaron vacíos. Se recupera mandándole un `bulk mode OFF`; no hace
falta apagarlo.

Eso revela que **el equipo limpia el destino antes de recibir**, que es
justamente por qué su propio volcado empieza con un `CLEAR ALL`. Si la secuencia
no se completa, se queda a medias.

### El prevuelo obligatorio

Antes de enviar nada modificado, **reconstruir el mensaje original y comprobar
que sale byte a byte idéntico**. Si no se reproduce el original, no se tiene
derecho a mandar una versión alterada. `P.build_dump(addr, data) == msg.raw`.

Y recalcular el checksum siempre: al tocar el payload, el original deja de valer.

### El equipo reserializa

La ida y vuelta **no conserva los bytes**. Al devolver el patrón, el QY100 lo
regenera desde su representación interna y rehace el relleno a su manera: de 147
bytes, 95 volvieron distintos aunque los eventos eran exactamente los pedidos.

Así que **no se debe comprobar la escritura comparando bytes** — hay que
decodificar los eventos y comprobar los valores. Es un error fácil de cometer y
da un falso negativo.

## La clave: es un flujo de bits

El payload **no tiene campos alineados a bytes**. Los bytes de 7 bits del SysEx
se concatenan en un flujo continuo, y cada campo empieza en la posición de bit
que le toque. Por eso no aparecía `0x3C` (nota 60) por ninguna parte, ni en
crudo ni desempaquetando a 8 bits — la altura estaba partida entre dos bytes.

Leyendo desde el **byte 34** del bloque `12 nn 00` como flujo de bits:

| Campo | Bit | Ancho | Verificado con |
| --- | --- | --- | --- |
| **Altura** | 3 | 7 | 60, 61, 62, 72 (incluye octava, fuerza acarreo) |
| **Velocity** | 10 | 7 | 56 (fuerte) frente a 16 (suave) |

Implementado en `patternfmt.py` con `BitStream`, y comprobado en las cinco
capturas de referencia.

Los 3 bits anteriores a la altura y lo que sigue a velocity siguen sin
descifrar.

## Posición — valor identificado, campo no localizado

Con la nota movida al **inicio del compás 2** (grabación por pasos, misma altura
y misma duración):

- El evento **sobrevive intacto**: se siguen leyendo altura 60 y velocity 56,
  desplazados **16 bits** más adelante (del bit 31 al 47, contando desde el
  byte 30). El decodificador de campos funciona; lo que falta es saber dónde
  empieza cada evento.
- **El valor 1920 aparece exacto** en el flujo — que es precisamente 4 negras ×
  480 relojes, el inicio del compás 2. Se lee como campo de 12 bits en el bit 17
  (o de 11 bits en el 18).

Pero **el campo no está en posición fija**: en la toma original ese mismo bit 17
lee 2102, no 0. Los flujos divergen ya desde el bit 15, así que la codificación
delante del evento es de longitud variable.

Con una sola posición conocida hay demasiadas lecturas que dan 1920 por
casualidad. **Hace falta una segunda posición** — por ejemplo el inicio del
compás 3 (3840 relojes) — para cruzar y fijar la regla.

## Secciones — resuelto

El byte bajo de la dirección (`12 nn tr`) **no es solo la pista**: codifica
sección y pista juntas.

```
tr = sección * 8 + pista
```

Verificado grabando la misma nota en INTRO y en MAIN A del mismo patrón:
aparecieron en `12 00 00` y `12 00 08`. Seis secciones × 8 pistas = 48 valores,
que caben en el byte de 7 bits — y eso explica los 384 patrones de usuario del
manual (64 estilos × 6 secciones). `tr = 0x7F` no es pista: es la cabecera.

## Dos notas — los eventos van encadenados

Dos notas iguales (60, velocity 56) en la misma pista, la primera en el tiempo 1:

```
evento 1: altura@bit 31, velocity@bit 38
evento 2: altura@bit 79, velocity@bit 86
          separación: 48 bits
```

**Los eventos se encadenan en el mismo flujo de bits**, no en registros
separados. Los dos se leen con el mismo decodificador.

Descontando altura y velocity (14 bits), quedan **34 bits entre eventos**. Ahí
tienen que estar la **duración** y el **tiempo hasta el siguiente evento** — los
dos campos que faltan.

### Mapa del evento — corregido

**El evento empieza en el bit 20, no en el 31.** Lo destapó el experimento de
duración: los bits que cambiaron formaban dos grupos separados 48 bits en los
bits 20–27 y 68–75, o sea *antes* de donde creíamos que empezaba el evento.

```
evento = 48 bits, primero en el bit 20, siguiente en el 68

  offset  0-7    duracion    campo localizado, codificacion sin resolver
  offset 11-17   altura      ✅
  offset 18-24   velocity    ✅
  offset 29-40   delta       ✅ relojes hasta el evento siguiente
  offset  8-10, 25-28, 41-47  sin identificar
```

Los offsets de altura, velocity y delta son los mismos de antes; solo cambia
desde dónde se cuentan.

### Duración — localizada, sin descifrar

Cambiando solo la duración de ambas notas, cambiaron **12 bits** en los offsets
0, 1, 3, 5, 6 y 7 de cada evento. Leído como 8 bits en el offset 0:

| | valor |
| --- | --- |
| duración anterior | 27 |
| duración nueva (negras) | 204 |

**No corresponde a relojes**: una negra son 480 y no aparece 480 en ninguna
lectura razonable cerca del evento. Tampoco 240, 120 ni 960 de forma limpia.
Podría ser un índice de figura, un valor de gate, o tener otra escala.

**No se pudo despejar porque solo se conoce una de las dos duraciones** — la
nueva. Para resolverlo hacen falta dos figuras conocidas y anotadas, mejor si
son de relación simple (por ejemplo negra y corchea, que es factor 2).

### El evento mide 48 bits

Comparando dos tomas donde **solo cambió la posición de la segunda nota**
(parte 3 de 16 → inicio del compás 2), cambiaron exactamente **12 bits**, en dos
grupos idénticos separados 48 bits:

```
grupo 1:  50, 51, 52, 56, 57, 59      (evento 1 + 19)
grupo 2:  98, 99, 100, 104, 105, 107  (evento 2 + 19)
```

Los dos eventos **no son duplicados**: sus regiones difieren a partir del
offset 18. Son dos notas reales.

Reparto interno del evento, con lo que sabemos:

| Offset | Campo |
| --- | --- |
| 0–6 | altura ✅ |
| 7–13 | velocity ✅ |
| 14–17 | ? (iguales en ambos eventos) |
| ~19–28 | **tiempo** — aquí cambiaron los 12 bits |
| 29–47 | ? |

**La codificación exacta del tiempo no está resuelta.** Y no se debe seguir
ajustando ventanas de bits contra los datos actuales: de los dos puntos, el de
"parte 3 de 16" **tiene posición incierta** — no encaja con 240 relojes ni con
ningún valor musical, y quien lo grabó no estaba seguro de haberlo hecho bien.
Ajustar contra un dato dudoso es cómo se inventan campos que no existen.

Para retomar hacen falta **dos posiciones verificadas**. La forma segura:
comprobar en la pantalla del QY100, evento por evento, dónde quedó cada nota
antes de volcar. Y usar valores separados y redondos, tipo compás 1 tiempo 1 y
compás 2 tiempo 1.

## Byte volátil — descartado como dato

El byte en el offset 509 de los bloques `12 nn 7F` **cambia entre volcados
aunque el contenido sea idéntico**: dos capturas con el bloque de pista byte a
byte igual traían valores distintos ahí. No es checksum del contenido ni campo
de datos. Está enmascarado en `report.VOLATILE` y el `diff` lo oculta; llevaba
toda la sesión ensuciando las comparaciones.

## Cuidado con la cuantización

Un intento de mover la nota al tiempo 2 produjo un volcado **byte a byte
idéntico** al original: `Timing Correct` la había devuelto al tiempo 1. Si un
experimento de posición no cambia nada, es lo primero que hay que mirar. La
grabación por pasos lo evita.

## Campo de altura — cómo se localizó

Cambiando la nota de a un semitono, con todo lo demás igual:

| Nota | byte 35 de `12 00 00` | binario |
| --- | --- | --- |
| original | `0x47` (71) | `100 0111` |
| +1 semitono | `0x57` (87) | `101 0111` |
| +2 semitonos | `0x67` (103) | `110 0111` |

**Delta constante de +0x10 por semitono.** Los bits 4–6 van 4 → 5 → 6; los bits
0–3 no se mueven.

Conclusión: **el campo de altura empieza en el bit 4 del byte 35**, o sea que
los campos **no están alineados a bytes** — es un flujo de bits. Eso explica que
no apareciera `0x3C` literal por ninguna parte, ni en crudo ni desempaquetando.

Pista de consistencia: los tres bits bajos valen 4, así que la nota cumple
`N mod 8 = 4`. El Do central (60) lo cumple.

Pendiente: dónde continúan los bits altos. El byte 36 no se movió en estas tres
muestras, así que hace falta un salto grande (una octava) para forzar el
desbordamiento y verlo.

## Segundo byte que cambia

También se movió un byte en los bloques `12 00 7F`, pero de forma no monótona
(`0x07 → 0x3F → 0x37`). Puede ser otro campo, algo derivado, o un artefacto de
concatenar bloques que en realidad son registros independientes. Sin conclusión
todavía.

## Método

Cambiar **una sola variable** y comparar con el volcado anterior. El `diff` de
`syx.py` agrupa por dirección y resalta los bytes movidos con contexto.

```bash
.venv/bin/python syx.py diff dumps/30-una-nota.syx dumps/31-semitono-arriba.syx
```

Funciona porque el andamiaje es idéntico entre tomas: cualquier byte que se mueva
pertenece al cambio que hiciste.
