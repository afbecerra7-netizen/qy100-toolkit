> **El formato de notas que este documento buscaba ya está resuelto** — ver
> [`HALLAZGOS.md`](HALLAZGOS.md) y `CLAUDE.md`. Lo que sigue vigente es el
> **método**, que es exactamente el que se usa cada vez que aparece un campo
> nuevo: cambiar una sola cosa en el panel, volcar, y diffear.
>
> Funcionó otra vez el 2026-08-02 para medir el byte 19 del prefijo en las ocho
> pistas y para confirmar el mezclador entero. En esa última tanda corrigió una
> etiqueta que habíamos puesto por posición: *chorus* y *variation* no estaban
> donde parecía. **Deducir por posición sin medir es justo lo que este protocolo
> existe para evitar.**
>
> Una mejora aprendida desde entonces: **incluir siempre una pista de control**
> cuyo valor ya se conozca. Si el control devuelve lo esperado, la medición es
> fiable; si no, lo que falla es el procedimiento y no los datos.

# Protocolo para deducir el formato de patrón del QY100

Checklist para seguir **con el equipo conectado**. El objetivo es averiguar cómo
codifica el QY100 las notas dentro de un patrón de usuario, cambiando **una sola
variable a la vez** y mirando qué bytes se mueven.

El manual documenta el sobre del mensaje (§3-6-3 y Tabla 1-9) pero no el layout
interno del payload de 147 bytes. Eso es lo que se deduce aquí.

**No hay riesgo de brickear nada.** Son datos de usuario: se borran y reescriben
libremente. Nada que ver con tocar firmware.

---

## Antes de empezar

**Conexión**

```
QY100 MIDI OUT  →  FastTrack IN
FastTrack OUT   →  QY100 MIDI IN
```

- `HOST SELECT` del QY100 en **MIDI**
- `MIDI CONTROL` en **Out** o **In/Out** (p. 127)

**Convención de nombres.** Un archivo por experimento, numerado en orden. El
número importa más que el nombre: el `diff` siempre se hace contra el anterior.

```
dumps/re/00-respaldo-completo.syx
dumps/re/01-vacio.syx
dumps/re/02-do3.syx
...
```

```bash
mkdir -p dumps/re
```

En cada paso, anota **en papel o en un archivo** qué hiciste exactamente en el
equipo. Dentro de tres días no vas a recordar si la nota fue C3 o C4.

---

## Fase 0 — Respaldo (obligatorio, antes de tocar nada)

Los datos de usuario viven en SRAM con pila (IC6). Esto los salva, y de paso
valida que el diálogo SysEx funciona.

```bash
.venv/bin/python syx.py dump all --in "FastTrack" --out "FastTrack" -o dumps/re/00-respaldo-completo.syx
```

- [ ] El archivo existe y no está vacío
- [ ] `inspect` reporta una convención de checksum que valida **todos** los bloques
- [ ] **Copia este archivo fuera del proyecto.** Es tu única red.

**Si no responde nada**, salta al plan B: lanza el volcado desde el propio QY100
(utilidades → trasvase en bloque, p. 129) y captúralo:

```bash
.venv/bin/python syx.py monitor -o dumps/re/00-respaldo-completo.syx --in "FastTrack"
```

Si el plan B funciona y el plan A no, todo el resto del protocolo sirve igual —
solo cambia cómo obtienes cada volcado.

---

## Fase 1 — Fijar las dos incógnitas del protocolo

```bash
.venv/bin/python syx.py inspect dumps/re/00-respaldo-completo.syx --unpack
```

- [ ] **Checksum**: anota cuál de las tres convenciones valida todo
- [ ] **Empaquetado 7 bits**: anota cuál de los dos desempaquetados da un
      resultado con pinta razonable (mucho relleno de ceros suele ser buena señal
      en datos de secuenciador poco poblados)
- [ ] ¿Cuántos bloques por patrón? ¿La dirección usa el byte `tr` para pistas?

Con esto fijado, dímelo y lo dejo escrito en el código en vez de detectado.

---

## Fase 2 — Comprobar que los volcados son deterministas

**Este paso parece tonto y es el más importante del protocolo.** Si el QY100
mete un contador, un timestamp o basura de RAM sin inicializar, el `diff` va a
mostrar ruido en todos los experimentos y vas a perseguir fantasmas.

Sin tocar absolutamente nada en el equipo, vuelca el mismo patrón dos veces:

```bash
.venv/bin/python syx.py dump pattern 1 --in "FastTrack" --out "FastTrack" -o dumps/re/01a.syx
.venv/bin/python syx.py dump pattern 1 --in "FastTrack" --out "FastTrack" -o dumps/re/01b.syx
.venv/bin/python syx.py diff dumps/re/01a.syx dumps/re/01b.syx
```

- [ ] **Resultado esperado: `Identicos byte a byte.`**
- [ ] Si NO son idénticos: anota **qué offsets** cambian. Esos bytes hay que
      ignorarlos en todo lo que sigue. Pásamelos y añado una máscara al `diff`.

---

## Fase 3 — La línea base

En el QY100:

1. Ve al modo PATTERN, patrón de usuario **1**, sección **MAIN A**
2. **Borra** el patrón (`cler`, p. 56) — todas las pistas
3. Ajusta longitud a **1 compás** y compás **4/4** (lo más simple posible)

```bash
.venv/bin/python syx.py dump pattern 1 --in "FastTrack" --out "FastTrack" -o dumps/re/02-vacio.syx
```

- [ ] Anota cuántos bytes trae y cuántos son cero. Un patrón vacío debería ser
      casi todo relleno: ese es tu fondo contra el que resalta todo lo demás.

---

## Fase 4 — Una variable a la vez

**La regla de oro: entre un experimento y el siguiente cambia UNA cosa.** Si
cambias dos, el diff te muestra dos regiones y no sabes cuál es cuál.

Cada paso: graba en el equipo → vuelca → compara con el **anterior**.

```bash
.venv/bin/python syx.py dump pattern 1 --in "FastTrack" --out "FastTrack" -o dumps/re/NN-descripcion.syx
.venv/bin/python syx.py diff dumps/re/ANTERIOR.syx dumps/re/NN-descripcion.syx
```

| # | Qué grabar en el QY100 | Qué aísla el diff |
|---|---|---|
| 03 | **Una sola nota**: Do3, velocity media, en el tiempo 1, duración 1/16 | Dónde empieza a existir un evento de nota |
| 04 | Igual pero **Do#3** (un semitono arriba) | El byte de **altura** |
| 05 | Vuelve a Do3 pero con velocity **muy baja** (ej. 20) | El byte de **velocity** |
| 06 | Do3 velocity media, pero en el **tiempo 2** | El byte de **posición / delta de tiempo** |
| 07 | Do3 en tiempo 1 con duración **1/4** en vez de 1/16 | El byte de **duración / gate** |
| 08 | **Dos notas**: Do3 en tiempo 1 y Mi3 en tiempo 3 | Cómo se **encadenan** los eventos |
| 09 | Las mismas dos notas pero en otra **pista de patrón** (ej. `BA` en vez de `D1`) | Si la pista va en el byte `tr` de la dirección o dentro de los datos |

Después de la 09 ya deberías tener la codificación de nota completa. Los
siguientes salen del mismo bucle:

| # | Qué cambiar | Qué aísla |
|---|---|---|
| 10 | Longitud del patrón: 1 → **4 compases** | Dónde vive la longitud |
| 11 | Compás: 4/4 → **3/4** | Dónde vive la signatura |
| 12 | Tipo de frase: `Chord 1` → **`Parallel`** | Dónde vive el tipo de frase |
| 13 | Tempo del patrón | Dónde vive el tempo |

---

## Fase 5 — La prueba de que lo entendimos

Deducir un formato es fácil de auto-engañarse. La única prueba real es la
inversa: **construir bytes desde cero y que el equipo toque lo que predijimos.**

1. Con lo aprendido, genero un `.syx` con una nota conocida en una posición conocida
2. `syx.py send` al QY100
3. Reproducir el patrón

- [ ] ¿Suena la nota que esperábamos, donde la esperábamos?
- [ ] Si sí: el formato está resuelto y el generador es cuestión de escribir bytes
- [ ] Si no: el diff nos dijo *dónde* está cada campo pero no *cómo* se codifica.
      Vuelta a la Fase 4 con experimentos más finos sobre el campo que falló.

---

## Qué mandarme

Para poder avanzar sin el equipo delante, lo útil es:

- La salida de `inspect --unpack` de la Fase 1
- El resultado de la Fase 2 (deterministas o no, y qué offsets bailan)
- La salida del `diff` de cada paso de la Fase 4, con la nota de qué grabaste

Con los pasos 03 a 06 probablemente ya pueda escribir un decodificador
tentativo, y los demás sirven para confirmarlo.

---

## Si algo sale mal

**El patrón quedó raro o no suena.** Borra y vuelve a empezar; no se rompe nada.

**Perdiste datos de usuario.** Restaura el respaldo de la Fase 0:

```bash
.venv/bin/python syx.py send dumps/re/00-respaldo-completo.syx --out "FastTrack"
```

**El equipo deja de responder a SysEx.** Apágalo y enciéndelo. El bulk mode puede
quedarse colgado; un ciclo de energía lo resetea.

**Nunca mandes un comando CLEAR "a ver qué pasa".** Borrar desde el panel es
reversible con el respaldo; borrar por SysEx sin querer, con la dirección
equivocada, también — pero solo si el respaldo de la Fase 0 está hecho.
