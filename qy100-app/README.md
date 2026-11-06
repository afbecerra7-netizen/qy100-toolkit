# qy100-app — la maqueta del sitemap

El sitemap de `PLAN-IPAD.md` (no se publica) hecho tocable, hablándole al
QY100 de verdad. **No es la app**: es lo que contesta las preguntas que un
diagrama no contesta.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python maqueta.py
```

No es un paquete: importa por ruta `../qy100-syx` y `../qy100-vida`, así que las
tres carpetas tienen que estar juntas. `[M]` Con Python 3.9.6 arranca; con 3.14,
Kivy 2.3.1 se quedó sin proveedor de texto SDL2 y no dibujó nada.

| | | |
| --- | --- | --- |
| `PATRÓN` · secciones | **real** | `SECTION CONTROL`, medido 2026-08-16 |
| transporte | **real** | `FA`/`FB`/`FC` + pánico |
| `TOCAR` | **real** | el Game of Life de [`qy100-vida/`](../qy100-vida/) sigue el reloj del QY100 y toca notas |
| `CANCIÓN` · mezcla y envíos | **real, en vivo** | `CC 7/10/91/93/94`, un canal por pista |
| `CANCIÓN` · voz y batería | **real, en vivo** | cambio de voz (banco + programa), `NRPN` de voz y de batería, `PB` por `RPN` |
| `PATRÓN` · mezcla, envíos, acordes | cableado, **sin verificar de punta a punta** | `LEER`/`APLICAR`: vuelca la cabecera, la modifica y la reescribe. En modo patrón el mezclador es dato de cabecera, y los `CC` no lo mueven |
| hoja `VARIATION` | **real** | tipo, `02 01 40` |
| `CANCIÓN` · song select | **real** | `F3` |

Lo que no está cableado **lo dice en su propia cara**. Una maqueta que finge
estar conectada mide la ilusión, no el diseño.

⚠️ `MIDI CONTROL` en `In` o `In/Out`, o no llega nada — y ese silencio se lee
igual que «la maqueta no sirve». `../qy100-syx/ajustar_midi_control.py`.

## Lo que la maqueta enseñó, que es para lo que existe

**El efecto de variación se plegó dentro de `MEZCLA`.** Nació como hoja global
porque el aparato acepta el tipo desde cualquier pantalla. Pero en modo patrón
la variación es **siempre de sistema sobre las 8 pistas** (manual p. 122), y un
efecto de sistema solo se oye por su **envío por canal** — `CC 94`, que vale 0
de fábrica. No eran dos cosas: el envío *es* el mezclador.

Costó tres rondas de «no se oye nada» porque **los mensajes llegaban y el
aparato los obedecía**. El tipo de efecto cambiaba. Simplemente no había por
dónde sonara, y «obedece pero no hay ruta» se ve idéntico a «no llega nada».

**Las unidades costaron dos intentos.** Densidad 2 del Mac → medio iPad de
lienzo; densidad forzada a 1 → proporciones exactas y todo diminuto. La salida
es atar la densidad al tamaño de ventana, no fijar ninguna de las dos.

**Y una regla de interacción**: una hoja tiene que ser **una decisión**. La
primera `FX` traía enrutado, 18 efectos y 8 parámetros, y quedaba más alta que
la ventana — el botón de cerrar se salía por arriba. Dos fallos, un síntoma:
nadie sabía qué hacer con ella.
