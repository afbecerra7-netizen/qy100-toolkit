#!/usr/bin/env python3
"""Maqueta del sitemap de QY100 Touch, corriendo y hablandole al aparato.

    .venv/bin/python maqueta.py

**Que es y que no.** No es la app: es el sitemap hecho tocable, para contestar
las preguntas que un diagrama no contesta. ¿Cinco pantallas hermanas se navegan
sin perderse? ¿Una hoja que se desliza encima se siente distinta de una pantalla
nueva? ¿Disparar una seccion desde una tableta se siente como un instrumento o
como un formulario?

**Lo que aqui mueve el aparato de verdad, y lo que no, esta marcado en pantalla.**
Esa distincion es el punto: una maqueta que finge estar conectada mide la
ilusion, no el diseno. Las pantallas sin cablear lo dicen en su propia cara.

    PATRON · secciones          REAL   SECTION CONTROL, medido el 2026-08-16
    HOJA FX                     REAL   XG param change, mapeado por Shea Kennedy
    CANCION · song select       REAL   F3, dos bytes
    TOCAR                       REAL   el Game of Life de `qy100-vida/` sigue el reloj
    CANCION · mezcla, voz, bat. REAL   en vivo: CC, cambio de voz, NRPN
    PATRON · mezcla y acordes   cableado, sin verificar de punta a punta (LEER/APLICAR)

⚠️ **Para que el aparato reciba, `MIDI CONTROL` tiene que estar en `In` o
`In/Out`.** Con `Off` no llega nada y el silencio se lee igual que «la maqueta
no sirve». Se pone sin tocar el panel:

    cd ../qy100-syx && .venv/bin/python ajustar_midi_control.py in/out
"""

import os
import threading

os.environ.setdefault("KIVY_NO_ARGS", "1")

#: ⚠️ **Las unidades de esta maqueta costaron dos intentos, los dos por el mismo
#: motivo.** Un iPad 7 son 2160x1620 pixeles a 2x, o sea **1080x810 puntos**, y
#: lo que una maqueta de disposicion tiene que reproducir son los PUNTOS.
#:
#:   1. Ventana de 1024 px con la densidad 2 del Mac  -> 512 dp de lienzo.
#:      Salia todo apretado y parecia un problema de diseno. Era la mitad del
#:      iPad.
#:   2. Densidad forzada a 1 y ventana de 1080 px -> proporciones exactas, pero
#:      en una pantalla Retina eso son 540 puntos fisicos: todo diminuto.
#:
#: Aritmetica correcta sobre la unidad equivocada, dos veces seguidas — el mismo
#: animal que en este proyecto ya se llevo el denominador del compas, un compas
#: de mas en un bucle y el mapale medido en 4/4.
#:
#: **La salida es atar la densidad al tamano de ventana**, no fijar ninguna de
#: las dos: el lienzo mide siempre 1080x810 dp —un iPad exacto— y la ventana se
#: hace tan grande como convenga mirarla. Las proporciones no dependen de la
#: pantalla en la que se abra.
LIENZO = (1080, 810)                  # puntos de un iPad 7
VENTANA = (2000, 1500)                # pixeles, lo que se ve comodo en el Mac
os.environ.setdefault("KIVY_METRICS_DENSITY", "%.6f" % (VENTANA[0] / LIENZO[0]))

from kivy.app import App                                    # noqa: E402
from kivy.clock import Clock                                # noqa: E402
from kivy.core.window import Window                         # noqa: E402
from kivy.graphics import Color, Line, RoundedRectangle     # noqa: E402
from kivy.metrics import dp                                 # noqa: E402
from kivy.uix.behaviors import ButtonBehavior               # noqa: E402
from kivy.uix.boxlayout import BoxLayout                    # noqa: E402
from kivy.uix.floatlayout import FloatLayout                # noqa: E402
from kivy.uix.gridlayout import GridLayout                  # noqa: E402
from kivy.uix.label import Label                            # noqa: E402
from kivy.uix.scrollview import ScrollView                  # noqa: E402
from kivy.uix.slider import Slider                          # noqa: E402
from kivy.uix.textinput import TextInput                    # noqa: E402
from kivy.uix.widget import Widget                        # noqa: E402

import mido                                                 # noqa: E402

import aparato as A                                         # noqa: E402

Window.size = VENTANA

FONDO = (0.045, 0.05, 0.058, 1)
PANEL = (0.09, 0.10, 0.115, 1)
TENUE = (0.14, 0.155, 0.175, 1)
TEXTO = (0.86, 0.88, 0.90, 1)
APAGADO = (0.42, 0.45, 0.48, 1)
VIVO = (0.36, 0.94, 0.86, 1)      # el mismo cian de `qy100-vida`
PEDIDO = (0.98, 0.72, 0.24, 1)    # ambar: pedido, todavia no confirmado
ALERTA = (0.93, 0.29, 0.36, 1)


class Boton(ButtonBehavior, Label):
    def __init__(self, texto="", fondo=TENUE, borde=None, **kw):
        super().__init__(text=texto, color=TEXTO, **kw)
        self._fondo, self._borde = fondo, borde
        with self.canvas.before:
            self._c = Color(*fondo)
            self._r = RoundedRectangle(radius=[dp(9)])
            self._cb = Color(0, 0, 0, 0)
            self._l = Line(width=dp(1.6))
        self.bind(pos=self._pintar, size=self._pintar)

    def _pintar(self, *_):
        self._r.pos, self._r.size = self.pos, self.size
        x, y, w, h = self.x + 1, self.y + 1, self.width - 2, self.height - 2
        self._l.rounded_rectangle = (x, y, w, h, dp(9))

    def vestir(self, fondo=None, borde=None, color=None):
        if fondo:
            self._c.rgba = fondo
        self._cb.rgba = borde or (0, 0, 0, 0)
        if color:
            self.color = color


def caja(color=PANEL, **kw):
    b = BoxLayout(**kw)
    with b.canvas.before:
        Color(*color)
        r = RoundedRectangle(radius=[dp(12)])
    b.bind(pos=lambda *_: setattr(r, "pos", b.pos),
           size=lambda *_: setattr(r, "size", b.size))
    return b


def texto(t, tam=14, color=TEXTO, **kw):
    return Label(text=t, font_size=dp(tam), color=color, **kw)


# ------------------------------------------------------------------ pantallas

class Pantalla(BoxLayout):
    titulo = "?"
    real = False

    def __init__(self, app, **kw):
        super().__init__(orientation="vertical", padding=dp(18),
                         spacing=dp(12), **kw)
        self.app = app
        self.construir()

    def construir(self):
        pass


class Rejilla(Widget):
    """La rejilla del Game of Life. **El reloj lo manda el QY100.**

    `[M]` Se invirtio la maestria el 2026-08-17. Con Kivy generando el tiempo su
    tambaleo —2,1 ms de mediana y 8,4 de maximo, medido por el propio
    `qy100-vida`— es tambaleo del groove: a 120 BPM un tic de reloj MIDI son
    20,8 ms, o sea que 8,4 es el **40% de un tic**.

    Contando `F8` esa misma desviacion pasa a ser **latencia de respuesta**, que
    es constante y no se oye igual que un tempo que tiembla. Y el generador queda
    enganchado al material del aparato: corre ENCIMA de un patron, no al lado.
    """

    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.mundo = A.AU.Automata()
        self.paso = 0
        self.sonando = []
        self.canal = 0
        self.encendidas = []
        self.bind(pos=self.pintar, size=self.pintar)

    # -- dedos -------------------------------------------------------------

    def on_touch_down(self, touch):
        return self._tocar(touch)

    def on_touch_move(self, touch):
        return self._tocar(touch)

    def _tocar(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        lado, ox, oy = self._geom()
        c = int((touch.x - ox) // lado)
        f = int((touch.y - oy) // lado)
        if 0 <= f < self.mundo.filas and 0 <= c < self.mundo.columnas:
            self.mundo.encender(f, c)
            self.pintar()
        return True

    def _geom(self):
        lado = min(self.width / self.mundo.columnas,
                   self.height / self.mundo.filas)
        return (lado,
                self.x + (self.width - lado * self.mundo.columnas) / 2,
                self.y + (self.height - lado * self.mundo.filas) / 2)

    # -- el paso, EN EL HILO MIDI -----------------------------------------

    def avanzar(self):
        """Lo dispara el reloj del aparato. **Corre en el hilo MIDI**, asi que
        aqui solo va el sonido —lo unico con exigencia de tiempo— y el dibujo se
        agenda. Pintar desde el hilo MIDI funciona a veces y revienta a veces,
        que es la peor clase de fallo."""
        self.sonando = self.mundo.subasta(self.paso)
        self._emitir(self.sonando)
        self.paso = (self.paso + 1) % self.mundo.columnas
        if self.paso == 0:
            # Evolucionar EN LA LINEA DE COMPAS, no a mitad de barrido: asi cada
            # generacion se oye entera una vez.
            self.mundo.evolucionar()
        Clock.schedule_once(lambda _dt: self.pintar())

    def _emitir(self, filas):
        ap = self.app.aparato
        if not ap.salida:
            return
        try:
            for n in self.encendidas:
                ap.salida.send(mido.Message("note_off", channel=self.canal,
                                            note=n, velocity=0))
            self.encendidas = []
            for f in filas:
                n = self.mundo.nota_de(f)
                # La prioridad que gano la subasta se reusa como dinamica en vez
                # de tirarla: mas vecinos, mas fuerte.
                v = max(48, min(118, 48 + self.mundo.vecinos(f, self.paso) * 14))
                ap.salida.send(mido.Message("note_on", channel=self.canal,
                                            note=n, velocity=v))
                self.encendidas.append(n)
        except Exception:
            pass

    def apagar(self):
        ap = self.app.aparato
        if not ap.salida:
            return
        for n in self.encendidas:
            try:
                ap.salida.send(mido.Message("note_off", channel=self.canal,
                                            note=n, velocity=0))
            except Exception:
                return
        self.encendidas = []
        self.sonando = []

    def pintar(self, *_):
        lado, ox, oy = self._geom()
        self.canvas.clear()
        with self.canvas:
            for f in range(self.mundo.filas):
                for c in range(self.mundo.columnas):
                    if c == self.paso and f in self.sonando:
                        Color(*VIVO)
                    elif self.mundo.celdas[f][c]:
                        Color(0.93, 0.29, 0.36, 1)
                    else:
                        Color(0.11, 0.13, 0.15, 1)
                    RoundedRectangle(pos=(ox + c * lado + 1, oy + f * lado + 1),
                                     size=(lado - 2, lado - 2), radius=[dp(2)])
            if self.app.aparato.tocando:
                Color(0.16, 0.42, 0.34, 0.55)
                RoundedRectangle(pos=(ox + self.paso * lado, oy),
                                 size=(lado, lado * self.mundo.filas))


class Tocar(Pantalla):
    """El generador, **dentro de la app**. Antes vivia en `qy100-vida` como
    programa aparte, y eso contradecia el sitemap: `TOCAR` no es un enlace a un
    generador, es el generador."""

    titulo = "TOCAR"
    real = True

    def construir(self):
        self.add_widget(texto(
            "[b]TOCAR[/b] — Game of Life   ·   "
            "[color=5be0d4]el reloj lo manda el QY100[/color]",
            18, markup=True, size_hint_y=None, height=dp(30)))
        self.pie = texto("dale play al QY100 — la rejilla sigue su reloj", 12,
                         color=APAGADO, size_hint_y=None, height=dp(22))

        b = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        self.rejilla = Rejilla(self.app)
        self.app.aparato.al_paso = self.rejilla.avanzar
        self.app.aparato.al_transporte = self._transporte
        for etq, fn in (("SEMBRAR", lambda *_: self.sembrar()),
                        ("RUIDO", lambda *_: self.ruido()),
                        ("LIMPIAR", lambda *_: self.limpiar()),
                        ("EVOLVE", lambda *_: self.evolucionar())):
            k = Boton(etq, font_size=dp(12))
            k.bind(on_release=fn)
            b.add_widget(k)
        self.b_escala = Boton(A.AU.NOMBRES_ESCALA[0].upper(), font_size=dp(11))
        self.b_escala.bind(on_release=lambda *_: self.cambiar_escala())
        b.add_widget(self.b_escala)
        self.b_canal = Boton("CH 1", font_size=dp(12), size_hint_x=None,
                             width=dp(80))
        self.b_canal.bind(on_release=lambda *_: self.cambiar_canal())
        b.add_widget(self.b_canal)
        self.add_widget(b)
        self.add_widget(self.rejilla)
        self.add_widget(self.pie)
        self.i_escala = 0
        self.sembrar()

    def _transporte(self, que):
        def _(_dt):
            if que == "start":
                self.rejilla.paso = 0
            if que == "stop":
                self.rejilla.apagar()
            self.pie.text = {"start": "corriendo desde el compas 1",
                             "continue": "retomado",
                             "stop": "parado por el aparato"}[que]
            self.rejilla.pintar()
        Clock.schedule_once(_)

    def sembrar(self):
        self.rejilla.mundo.limpiar()
        self.rejilla.mundo.sembrar_figura("toad")
        self.rejilla.pintar()

    def ruido(self):
        self.rejilla.mundo.sembrar_ruido()
        self.rejilla.pintar()

    def limpiar(self):
        self.rejilla.mundo.limpiar()
        self.rejilla.apagar()
        self.rejilla.pintar()

    def evolucionar(self):
        self.rejilla.mundo.evolucionar()
        self.rejilla.pintar()

    def cambiar_escala(self):
        self.i_escala = (self.i_escala + 1) % len(A.AU.NOMBRES_ESCALA)
        n = A.AU.NOMBRES_ESCALA[self.i_escala]
        self.rejilla.mundo.escala = n
        self.b_escala.text = n.upper()

    def cambiar_canal(self):
        self.rejilla.canal = (self.rejilla.canal + 1) % 16
        self.b_canal.text = "CH %d" % (self.rejilla.canal + 1)


class ConPestanas(Pantalla):
    """Pantalla con pestañas internas, **copiando como cicla el aparato**:
    `[PATTERN]` recorre `PATTERN -> PATTERN VOICE -> PATTERN EFFECT`. Son tres
    vistas de lo mismo, no tres sitios distintos."""

    def pestanas(self, titulo, pares, aviso="", barra=None):
        self.add_widget(texto(titulo, 17, markup=True, size_hint_y=None,
                              height=dp(28)))
        if aviso:
            self.add_widget(texto(aviso, 11, color=APAGADO, markup=True,
                                  size_hint_y=None, height=dp(30),
                                  halign="center"))
        if barra:
            self.add_widget(barra())
        barra = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
        self._vistas, self._bp = {}, {}
        for nombre, construir in pares:
            b = Boton(nombre, font_size=dp(13))
            b.bind(on_release=lambda _b, n=nombre: self.ver(n))
            barra.add_widget(b)
            self._bp[nombre] = b
            self._vistas[nombre] = construir()
        self.add_widget(barra)
        self._hueco = BoxLayout()
        self.add_widget(self._hueco)
        self.ver(pares[0][0])

    def ver(self, nombre):
        self._hueco.clear_widgets()
        self._hueco.add_widget(self._vistas[nombre])
        for n, b in self._bp.items():
            act = n == nombre
            b.vestir(fondo=(0.16, 0.19, 0.22, 1) if act else TENUE,
                     borde=VIVO if act else None,
                     color=TEXTO if act else APAGADO)


class Patron(ConPestanas):
    """El banco: 8 pistas, y **los envios son dato de la cabecera**.

    `[M]` 2026-08-16: en modo patron `CC 91` no mueve nada — se probo el mismo
    barrido que en cancion, con `PATT OUT CH` ya en `1~8`, y las perillas del
    aparato no se movieron. Por eso aqui hay `LEER` y `APLICAR` y no perillas en
    vivo, y por eso este bloque **no vive en la misma pantalla que el de
    cancion**: son mecanismos distintos, no dos modos de uno.
    """

    titulo = "PATRON"
    real = True

    def construir(self):
        self.patron = 4
        self.cab = self.pistas_msg = None
        self.bloque_mezcla = self.envios = None
        self.nombre = self.compases = None
        self.acordes, self.ac_tocados = {}, set()
        self.pestanas(
            "[b]PATRON[/b] — el banco   ·   8 pistas   ·   "
            "[color=fbb83d]envios diferidos[/color]",
            [("SECCIONES", self._secciones),
             ("MEZCLA", self._mezcla),
             ("ENVIOS", self._envios),
             ("ACORDES", self._acordes)],
            aviso="las secciones SI son en vivo y el aparato las alinea al "
                  "compas; volumen, pan y los envios se guardan en el patron.  "
                  "LEER y APLICAR paran la reproduccion: sonando, el reloj "
                  "ahoga el volcado y las escrituras se ignoran",
            barra=self.barra_patron)

    def _secciones(self):
        c = BoxLayout(orientation="vertical", spacing=dp(10))
        fila = BoxLayout(size_hint_y=None, height=dp(96), spacing=dp(8))
        self.botones = []
        for i, nombre in enumerate(A.SECCIONES):
            b = Boton(nombre, font_size=dp(16))
            b.bind(on_release=lambda _b, k=i: self.app.disparar_seccion(k))
            fila.add_widget(b)
            self.botones.append(b)
        c.add_widget(fila)
        self.pie_sec = texto("toca una seccion — el QY100 la alinea al compas",
                             12, color=APAGADO, size_hint_y=None, height=dp(24))
        c.add_widget(self.pie_sec)
        c.add_widget(Widget())
        return c

    def barra_patron(self):
        """`LEER` y `APLICAR` **para toda la pantalla, no para una pestaña**.

        `[M]` En modo patron la mezcla y los envios son el mismo dato: los cinco
        bloques de cabecera. Un volcado trae las seis filas y una escritura las
        guarda las seis. Repartir el boton por pestaña invitaria a escribir dos
        veces y a que la segunda pisara lo que la primera dejo.
        """
        b = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        b.add_widget(texto("patron", 12, color=APAGADO, size_hint_x=None,
                           width=dp(56), halign="right"))
        for etq, d in (("-", -1), ("+", 1)):
            k = Boton(etq, font_size=dp(15), size_hint_x=None, width=dp(42))
            k.bind(on_release=lambda _b, n=d: self.mover_patron(n))
            b.add_widget(k)
        self.lb_patron = texto(str(self.patron), 16, size_hint_x=None,
                               width=dp(48))
        b.add_widget(self.lb_patron)
        self.lb_nombre = texto("", 13, color=VIVO, markup=True,
                               size_hint_x=None, width=dp(190))
        b.add_widget(self.lb_nombre)
        self.b_leer = Boton("LEER", font_size=dp(13), size_hint_x=None,
                            width=dp(100))
        self.b_leer.bind(on_release=lambda *_: self.leer())
        b.add_widget(self.b_leer)
        self.b_aplicar = Boton("APLICAR", font_size=dp(13), size_hint_x=None,
                               width=dp(116))
        self.b_aplicar.bind(on_release=lambda *_: self.aplicar())
        b.add_widget(self.b_aplicar)
        self.pie = texto("toca LEER para traer los valores del aparato", 11,
                         color=APAGADO)
        b.add_widget(self.pie)
        return b

    def _mezcla(self):
        self.bloque_mezcla = BloqueMezcla(self.app, A.PISTAS_PATRON, vivo=False)
        self.bloque_mezcla.al_cambiar = lambda: self.marcar(False)
        return self.bloque_mezcla

    def _acordes(self):
        """`SOURCE CHORD` por pista — **lo unico de la app que hace algo que el
        aparato no puede hacer solo**: en las frases de fabrica el QY100 no deja
        editarlo desde sus botones (manual p. 120).

        Es por pista y por seccion, asi que vive en el prefijo de cada pista y no
        en la cabecera. De ahi el selector de seccion.
        """
        c = BoxLayout(orientation="vertical", spacing=dp(8))
        c.add_widget(texto(
            "el acorde en el que se GRABO la frase — el QY100 rearmoniza desde "
            "aqui.  [b]Solo M7 y m7 estan medidos[/b]; los demas tipos existen "
            "en el aparato y nadie los ha barrido.",
            11, color=APAGADO, markup=True, size_hint_y=None, height=dp(32),
            halign="center"))

        self.seccion_ac = 1
        f = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(5))
        f.add_widget(texto("seccion", 11, color=APAGADO, size_hint_x=None,
                           width=dp(64), halign="right"))
        self.b_sec_ac = {}
        for i, nombre in enumerate(A.SECCIONES):
            b = Boton(nombre, font_size=dp(11))
            b.bind(on_release=lambda _b, k=i: self.ver_seccion(k))
            f.add_widget(b)
            self.b_sec_ac[i] = b
        c.add_widget(f)

        self.acordes = {}
        self.b_acorde = {}
        rej = BoxLayout(size_hint_y=None, height=dp(64), spacing=dp(5))
        for k, et in enumerate(A.PISTAS_PATRON):
            col = BoxLayout(orientation="vertical", spacing=dp(2))
            col.add_widget(texto(et, 12, color=TEXTO, size_hint_y=None,
                                 height=dp(18)))
            b = Boton("—", font_size=dp(13))
            b.bind(on_release=lambda _b, i=k: self.pedir_acorde(i))
            col.add_widget(b)
            rej.add_widget(col)
            self.b_acorde[k] = b
        c.add_widget(rej)
        c.add_widget(Widget())
        self.ver_seccion(1)
        return c

    def ver_seccion(self, i):
        self.seccion_ac = i
        for k, b in self.b_sec_ac.items():
            act = k == i
            b.vestir(fondo=(0.16, 0.19, 0.22, 1) if act else TENUE,
                     borde=VIVO if act else None,
                     color=TEXTO if act else APAGADO)
        self.pintar_acordes()

    def pintar_acordes(self):
        for k, b in self.b_acorde.items():
            v = self.acordes.get((self.seccion_ac, k))
            if v is None:
                b.text, b.color = "—", APAGADO
            else:
                raiz, tipo = v
                b.text = "%s%s" % (raiz, tipo or "?")
                b.color = PEDIDO if (self.seccion_ac, k) in self.ac_tocados \
                    else VIVO

    def pedir_acorde(self, pista):
        if (self.seccion_ac, pista) not in self.acordes:
            self.pie.text = "primero LEER"
            return
        self.app.hoja_acorde(
            A.PISTAS_PATRON[pista], self.acordes[(self.seccion_ac, pista)],
            lambda raiz, tipo: self.tomar_acorde(pista, raiz, tipo))

    def tomar_acorde(self, pista, raiz, tipo):
        self.acordes[(self.seccion_ac, pista)] = (raiz, tipo)
        self.ac_tocados.add((self.seccion_ac, pista))
        self.pintar_acordes()

    def _envios(self):
        self.envios = BloqueEnvios(self.app, A.PISTAS_PATRON, vivo=False)
        self.envios.al_cambiar = lambda: self.marcar(False)
        return self.envios

    # -- aparato ----------------------------------------------------------

    def mover_patron(self, d):
        self.patron = max(1, min(64, self.patron + d))
        self.lb_patron.text = str(self.patron)
        self.lb_nombre.text = ""
        self.cab = None
        self.pie.text = "patron %d — toca LEER" % self.patron

    def marcar(self, medido):
        col = VIVO if medido else PEDIDO
        for b in (self.envios, self.bloque_mezcla):
            if b:
                b.color_valor(col)

    def leer(self):
        self.pie.text = ("parando y volcando la cabecera del patron %d..."
                         % self.patron)
        def trabajo():
            mz = A.Mezclador(self.app.aparato)
            vals, cab, pistas, nota = mz.leer(self.patron)
            self.nombre, self.compases = mz.nombre, mz.compases
            if vals is None:
                Clock.schedule_once(lambda *_: setattr(
                    self.pie, "text", "no se pudo leer: %s" % nota))
                return
            self.cab, self.pistas_msg = cab, pistas
            self.ac_tocados = set()
            self.acordes = {}
            for sec in range(6):
                for k, v in mz.leer_acordes(pistas, sec).items():
                    self.acordes[(sec, k)] = v
            def pintar(*_a):
                self.envios.poner(vals)
                if self.bloque_mezcla:
                    self.bloque_mezcla.poner(vals)
                self.marcar(True)
                # **El nombre confirma que se leyo el patron que se pidio.**
                # Sin el, un volcado de un patron vacio y uno del patron
                # equivocado se ven exactamente igual.
                self.lb_nombre.text = "[b]%s[/b]  %s" % (
                    self.nombre or "(sin nombre)",
                    "·".join(str(c) for c in (self.compases or [])))
                if self.b_acorde:
                    self.pintar_acordes()
                self.pie.text = ("patron %d — %s  ·  se paro la reproduccion"
                                 % (self.patron, nota))
            Clock.schedule_once(pintar)
        threading.Thread(target=trabajo, daemon=True).start()

    def aplicar(self):
        if self.cab is None:
            self.pie.text = "primero LEER: hay que partir de la cabecera real"
            return
        vals = []
        for k in range(8):
            d = {c: int(self.envios.mandos[(k, c)].valor)
                 for c, _ in A.FILAS_MEZCLA}
            if self.bloque_mezcla:
                d.update(self.bloque_mezcla.valores[k])
            vals.append(d)
        self.pie.text = "parando y escribiendo..."
        # **Los acordes se agrupan por seccion** porque cada pista vive en su
        # propia direccion `tr = seccion*8 + pista`; una escritura por seccion
        # tocada, y el resto de las pistas viaja tal cual.
        por_seccion = {}
        for (sec, k) in self.ac_tocados:
            por_seccion.setdefault(sec, {})[k] = self.acordes[(sec, k)]

        def trabajo():
            mz = A.Mezclador(self.app.aparato)
            sec = next(iter(por_seccion), 1)
            nota = mz.escribir(self.patron, self.cab, self.pistas_msg, vals,
                               acordes=por_seccion.get(sec), seccion=sec)
            Clock.schedule_once(lambda *_: setattr(
                self.pie, "text", "patron %d — %s" % (self.patron, nota)))
        threading.Thread(target=trabajo, daemon=True).start()


class Cancion(ConPestanas):
    """La tarima: 16 pistas, y **todo es en vivo**.

    `[M]` 2026-08-16: en modo cancion pista n = canal n, y el mezclador responde
    a `CC` al instante — medido barriendo un canal, luego otro para descartar que
    hubiera una perilla siguiendo a todo, y despues una onda por los dieciseis.

    Aqui converge lo que los documentos ya decian por otro camino: el set se toca
    en modo cancion porque las transiciones de seccion son automaticas y el
    `Ending` cierra en vez de repetir. La mezcla apunta al mismo sitio.

    ⚠️ **En vivo no es guardado.** Un `CC` mueve el estado actual; lo que
    sobrevive a apagar el aparato es lo que este escrito. Esta pantalla no dice
    «guardado» en ninguna parte.
    """

    titulo = "CANCION"
    real = True

    PISTAS = [str(k + 1) for k in range(16)]

    def construir(self):
        self.pestanas(
            "[b]CANCION[/b] — la tarima   ·   16 pistas   ·   "
            "[color=5be0d4]en vivo[/color]",
            [("ARREGLO", self._arreglo),
             ("MEZCLA", self._mezcla),
             ("ENVIOS", self._envios),
             ("VOZ", self._voz),
             ("BATERIA", self._bateria)],
            aviso="el aparato tiene que estar en modo SONG · en vivo no es "
                  "guardado: el CC mueve el estado, no escribe la cancion")

    def _arreglo(self):
        c = BoxLayout(orientation="vertical", spacing=dp(8))
        c.add_widget(texto("SONG SELECT — F3, dos bytes", 12, color=APAGADO,
                           size_hint_y=None, height=dp(20)))
        g = GridLayout(cols=10, spacing=dp(6), size_hint_y=None, height=dp(90))
        for n in range(20):
            b = Boton(str(n + 1), font_size=dp(14))
            b.bind(on_release=lambda _b, k=n: self.app.aparato.song_select(k))
            g.add_widget(b)
        c.add_widget(g)
        caja_ = caja(orientation="vertical", padding=dp(12), spacing=dp(4))
        caja_.add_widget(texto("el arreglo, hasta 64 compases en 3 bloques", 12,
                               color=APAGADO, size_hint_y=None, height=dp(20)))
        for sec, n in (("Intro", 6), ("Main A", 6), ("Fill AB", 1),
                       ("Main B", 6), ("Fill BA", 1), ("Main A", 6),
                       ("Ending", 6)):
            r = BoxLayout(size_hint_y=None, height=dp(24))
            r.add_widget(texto(sec, 12, halign="left"))
            r.add_widget(texto("%d compases" % n, 12, color=APAGADO))
            caja_.add_widget(r)
        c.add_widget(caja_)
        c.add_widget(Widget())
        return c

    def _mezcla(self):
        return BloqueMezcla(self.app, self.PISTAS, vivo=True)

    def _bateria(self):
        c = BoxLayout(orientation="vertical", spacing=dp(6))
        c.add_widget(texto(
            "cada tambor por separado — NRPN con el [b]numero de nota en el "
            "LSB[/b].  Los pads suenan al tocarlos: asi se sabe cual es cual "
            "sin fiarse de una tabla de nombres.",
            11, color=APAGADO, markup=True, size_hint_y=None, height=dp(34),
            halign="center"))
        c.add_widget(BloqueBateria(self.app))
        return c

    def _voz(self):
        c = BoxLayout(orientation="vertical", spacing=dp(6))
        c.add_widget(texto(
            "filtro y envolvente por pista, como la pantalla VOICE EDIT.  "
            "Todo va por [b]NRPN[/b] con MSB 01 — incluido [b]D[/b], que no "
            "tiene CC.  El centro es «como venia», no «apagado».\n"
            "[color=fbb83d]PB no suena al moverla[/color]: es el MARGEN del "
            "pitch bend (±24 semitonos), no el doblez.",
            11, color=APAGADO, markup=True, size_hint_y=None, height=dp(46),
            halign="center"))
        c.add_widget(BloqueVoz(self.app, self.PISTAS))
        return c

    def _envios(self):
        c = BoxLayout(orientation="vertical", spacing=dp(6))
        c.add_widget(texto(
            "⚠️  [b]VARI.[/b] solo responde con Connection = System — lo dice el "
            "Data List en la propia tabla de control change.  [b]DRY[/b] no "
            "tiene CC: va por SysEx 08 nn 11.",
            11, color=PEDIDO, markup=True, size_hint_y=None, height=dp(34),
            halign="center"))
        c.add_widget(BloqueEnvios(self.app, self.PISTAS, vivo=True))
        return c


class Perilla(Widget):
    """Un mando giratorio, porque **es como lo dibuja el aparato**.

    Manual p. 71: *«El control grafico girara a la posicion correspondiente (a
    la derecha si se eleva el nivel, a la izquierda si se reduce)»*. La maqueta
    empezo con faders verticales y era una traduccion innecesaria: la pantalla
    de envios del QY100 son perillas en una rejilla de 8 pistas x 4 filas, y
    copiarla ahorra tener que aprender dos representaciones de lo mismo.

    Se arrastra en vertical, que es como se manejan las perillas en pantalla —
    girar con el dedo es preciso en un raton y horrible en una tableta.
    """

    def __init__(self, valor=0, cambio=None, **kw):
        super().__init__(**kw)
        self.valor, self.cambio, self._y = valor, cambio, None
        with self.canvas:
            self._cf = Color(0.20, 0.22, 0.25, 1)
            self._arco_f = Line(width=dp(3))
            self._cv = Color(*PEDIDO)
            self._arco = Line(width=dp(3))
            self._ci = Color(*PEDIDO)
            self._ind = Line(width=dp(2))
        self.bind(pos=self._pintar, size=self._pintar)

    def _pintar(self, *_):
        import math
        cx, cy = self.center_x, self.center_y + dp(5)
        r = min(self.width, self.height) * 0.32
        # De -140 a +140 grados, con el cero arriba: el recorrido de una perilla
        # de verdad, que no da la vuelta entera.
        self._arco_f.circle = (cx, cy, r, -140, 140)
        frac = self.valor / 127.0
        self._arco.circle = (cx, cy, r, -140, -140 + 280 * frac)
        ang = math.radians(-140 + 280 * frac)
        self._ind.points = [cx, cy,
                            cx + r * 0.92 * math.sin(ang),
                            cy + r * 0.92 * math.cos(ang)]
        self._cv.a = 1.0 if self.valor else 0.25
        self._ci.a = 1.0 if self.valor else 0.35

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        self._y = touch.y
        return True

    def on_touch_move(self, touch):
        if self._y is None:
            return False
        # 160 dp de recorrido para los 127 pasos: mas corto se vuelve nervioso,
        # mas largo no cabe en la pantalla.
        v = max(0, min(127, self.valor + (touch.y - self._y) * 127.0 / dp(160)))
        self._y = touch.y
        if int(v) != int(self.valor):
            self.valor = v
            self._pintar()
            if self.cambio:
                self.cambio(int(v))
        else:
            self.valor = v
        return True

    def on_touch_up(self, touch):
        self._y = None
        return False

    def poner(self, v):
        self.valor = v
        self._pintar()

    def color_valor(self, rgba):
        """Cian cuando el valor viene leido del aparato, ambar cuando es lo que
        la app pidio y nadie ha confirmado. Es la unica pantalla donde esta app
        puede pintar lo primero."""
        self._cv.rgba = list(rgba[:3]) + [self._cv.a]
        self._ci.rgba = list(rgba[:3]) + [self._ci.a]


class BloqueMezcla(BoxLayout):
    """La pantalla de mezclador del QY100, copiada: `M/S · VOICE · PAN · VOLUME`.

    **Pan en perilla y volumen en fader**, como el aparato los dibuja — no es
    capricho suyo: una perilla dice «centro» de un vistazo y un fader dice
    «cuanto», y el QY100 eligio bien.

    `vivo=True` manda `CC 10` y `CC 7` al tocar. `vivo=False` acumula y espera a
    `APLICAR`, porque en modo patron esto es dato de la cabecera.
    """

    def __init__(self, app, pistas, vivo, base_canal=0, **kw):
        super().__init__(orientation="vertical", spacing=dp(3), **kw)
        self.app, self.pistas, self.vivo, self.base = app, pistas, vivo, base_canal
        self.pan, self.vol, self.ms = {}, {}, {}
        self.al_cambiar = None
        self.valores = [{"volumen": 100, "panoramico": 64}
                        for _ in range(len(pistas))]
        n = len(pistas)

        cab = BoxLayout(size_hint_y=None, height=dp(20), spacing=dp(3))
        cab.add_widget(texto("", 10, size_hint_x=None, width=dp(64)))
        for et in pistas:
            cab.add_widget(texto(et, 11, color=TEXTO))
        self.add_widget(cab)

        f = BoxLayout(size_hint_y=None, height=dp(26), spacing=dp(3))
        f.add_widget(texto("M/S", 11, color=APAGADO, size_hint_x=None,
                           width=dp(64), halign="right"))
        for k in range(n):
            b = Boton("", font_size=dp(9))
            b.bind(on_release=lambda _b, i=k: self.mute(i))
            f.add_widget(b)
            self.ms[k] = b
        self.add_widget(f)

        f = BoxLayout(size_hint_y=None, height=dp(26), spacing=dp(3))
        f.add_widget(texto("VOICE", 11, color=APAGADO, size_hint_x=None,
                           width=dp(64), halign="right"))
        self.voz = {}
        for k in range(n):
            b = Boton("—", font_size=dp(9))
            b.bind(on_release=lambda _b, i=k: self.pedir_voz(i))
            f.add_widget(b)
            self.voz[k] = b
        self.add_widget(f)

        f = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(3))
        f.add_widget(texto("PAN", 11, color=APAGADO, size_hint_x=None,
                           width=dp(64), halign="right"))
        for k in range(n):
            # ⚠️ Arranca en 64 (centro) y no en 0: en XG el `0` del pan de parte
            # es **random**, no izquierda. Ver `NRPN_BATERIA`.
            w = Perilla(valor=64, cambio=lambda v, i=k: self.manda(i, 10, v))
            f.add_widget(w)
            self.pan[k] = w
        self.add_widget(f)

        f = BoxLayout(spacing=dp(3))
        f.add_widget(texto("VOLUME", 11, color=APAGADO, size_hint_x=None,
                           width=dp(64), halign="right"))
        for k in range(n):
            sl = Slider(min=0, max=127, value=100, orientation="vertical")
            sl._ultimo = 100
            sl.bind(value=lambda w, v, i=k: self._quiza(w, i, 7, int(v)))
            f.add_widget(sl)
            self.vol[k] = sl
        self.add_widget(f)

    def mute(self, k):
        b = self.ms[k]
        b._on = not getattr(b, "_on", False)
        b.vestir(fondo=(0.28, 0.10, 0.12, 1) if b._on else TENUE,
                 borde=ALERTA if b._on else None)

    def pedir_voz(self, pista):
        """Abre la hoja **con el contexto de esta pista** — su nombre y si es de
        bateria. Sin eso la hoja ofreceria la tabla equivocada."""
        d = self.valores[pista]
        self.app.hoja_voz(
            self.pistas[pista], bool(d.get("bateria", False)),
            lambda pr, nombre: self.tomar_voz(pista, pr, nombre),
            en_vivo=self.vivo)

    def tomar_voz(self, pista, programa, nombre):
        self.valores[pista]["programa"] = programa
        self.voz[pista].text = nombre
        self.voz[pista].color = PEDIDO
        if self.vivo:
            # **En vivo la voz entra al instante**, con banco y programa. En
            # diferido solo se anota y viaja con el APLICAR, porque en modo
            # patron la voz es dato de la cabecera.
            d = A.voz_direccionable(nombre, self.valores[pista].get("bateria"))
            if d:
                A.cambia_voz(self.app.aparato, self.base + pista, *d)
        elif self.al_cambiar:
            self.al_cambiar()

    def _quiza(self, w, k, cc, v):
        if getattr(w, "_ultimo", None) == v:
            return
        w._ultimo = v
        self.manda(k, cc, v)

    def manda(self, pista, cc, valor):
        """⚠️ **En diferido esto NO manda: acumula.** La primera version no hacia
        ninguna de las dos cosas — las perillas se movian y no pasaba nada, que
        es exactamente la interfaz que miente y que esta maqueta existe para no
        tener. En modo patron volumen y pan son dato de la cabecera, igual que
        los envios, y se guardan con el mismo APLICAR."""
        clave = {7: "volumen", 10: "panoramico"}[cc]
        self.valores[pista][clave] = int(valor)
        if self.vivo:
            self.app.aparato.envio(self.base + pista, cc, int(valor))
        elif self.al_cambiar:
            self.al_cambiar()

    def poner(self, vals):
        for k in range(len(self.pistas)):
            if "programa" in vals[k]:
                self.valores[k]["programa"] = vals[k]["programa"]
                self.valores[k]["bateria"] = vals[k].get("bateria", False)
                self.voz[k].text = A.nombre_voz(vals[k]["programa"],
                                                vals[k]["bateria"])
                self.voz[k].color = VIVO
            if "panoramico" in vals[k]:
                self.pan[k].poner(vals[k]["panoramico"])
                self.valores[k]["panoramico"] = vals[k]["panoramico"]
            if "volumen" in vals[k]:
                self.vol[k].value = vals[k]["volumen"]
                self.vol[k]._ultimo = vals[k]["volumen"]
                self.valores[k]["volumen"] = vals[k]["volumen"]

    def color_valor(self, rgba):
        for w in self.pan.values():
            w.color_valor(rgba)


class BloqueVoz(BoxLayout):
    """La pantalla `VOICE EDIT` del QY100: filtro y envolvente por pista.

    `[M]` Los seis controles del aparato —`PB · CUT · RES · A · D · R`— y todos
    con el mismo rango en pantalla: **−64…0…+63**, salvo `PB` que va en
    semitonos, −24…+24.

    **El centro no es el cero de la perilla, es 64.** Estos parametros son
    desplazamientos sobre lo que la voz ya trae, no valores absolutos: una
    perilla al centro significa «como venia», no «apagado». Pintarlos como los
    envios —que si arrancan en cero— haria creer que todo esta al minimo.
    """

    def __init__(self, app, pistas, base_canal=0, **kw):
        super().__init__(orientation="vertical", spacing=dp(3), **kw)
        self.app, self.base = app, base_canal
        self.mandos = {}
        cab = BoxLayout(size_hint_y=None, height=dp(20), spacing=dp(3))
        cab.add_widget(texto("", 10, size_hint_x=None, width=dp(56)))
        for et in pistas:
            cab.add_widget(texto(et, 11, color=TEXTO))
        self.add_widget(cab)

        # ⚠️ **`PB` no suena al moverla, y eso no es un fallo.** Es el MARGEN del
        # pitch bend —cuanto dobla la rueda, ±24 semitonos— no el doblez. No
        # cambia nada hasta que algo mande pitch bend: el miniteclado del
        # aparato, un teclado externo, o un pad XY. Se marca aqui porque un control que no
        # responde se lee como roto, y llevamos un dia entero pagando silencios
        # con causa propia.
        filas = [("PB", None)] + [(n, lsb) for lsb, n in A.NRPN_VOZ]
        for etq, lsb in filas:
            f = BoxLayout(spacing=dp(3))
            f.add_widget(texto(etq, 11, color=APAGADO, size_hint_x=None,
                               width=dp(56), halign="right"))
            for k in range(len(pistas)):
                # PB arranca en 2 semitonos, que es el valor de fabrica de XG;
                # el resto al centro, que aqui significa «sin desplazar».
                ini = 2 if lsb is None else 64
                w = Perilla(valor=ini,
                            cambio=lambda v, i=k, l=lsb: self.manda(i, l, v))
                f.add_widget(w)
                self.mandos[(k, etq)] = w
            self.add_widget(f)

        self.pie = texto("", 11, color=APAGADO, size_hint_y=None, height=dp(20))
        self.add_widget(self.pie)

    def manda(self, pista, lsb, valor):
        out = self.app.aparato.salida
        if not out:
            return
        canal = self.base + pista
        v = int(valor)
        try:
            if lsb is None:
                # PB: el valor crudo son semitonos. Se acota a 24 porque el
                # manual dice ±24 y mandar mas seria escribir fuera de rango,
                # que es como Shea perdio el 5A.
                v = min(24, v)
                A.manda_rpn(out, canal, *A.RPN_PITCH_BEND, valor=v)
                self.pie.text = "ch%d  PB = %d semitonos" % (canal + 1, v)
            else:
                A.manda_nrpn(out, canal, 0x01, lsb, v)
                self.pie.text = "ch%d  NRPN 01 %02X = %+d" % (canal + 1, lsb, v - 64)
            self.app.aparato.intentos += 3
        except Exception:
            pass


class BloqueBateria(BoxLayout):
    """Edicion **por instrumento de percusion**: cada tambor por separado.

    `[M]` NRPN con `MSB = 0x14`-`0x1F` y **`LSB` = numero de nota** (Data List,
    tabla NRPN): corte, resonancia, ataque, caida, afinacion, nivel, pan y los
    tres envios, de cada tambor.

    **Los pads suenan al tocarlos, y eso no es un extra: es como se sabe cual
    es cual.** El mapa de notas del QY100 esta en la misma tabla del Data List a
    cuatro columnas que ya dio pelea con las voces, y poner nombres sacados de
    ahi seria arriesgar un nombre plausible y falso — el error de los kits, otra
    vez. Un tambor que suena se identifica solo.

    Es el mismo metodo que resolvio el mapa de pads del EP-40 despues de siete
    pruebas mal disenadas: **preguntar por comparacion, no por nombre.** Nadie
    sabe decir «eso es un fa sostenido»; cualquiera sabe decir «ese es el bombo».
    """

    #: El tramo util de la bateria GM: bombo, caja, charles, toms y platos. Se
    #: deja fuera la percusion alta, que casi nunca se retoca.
    NOTAS = list(range(35, 59))

    def __init__(self, app, **kw):
        super().__init__(orientation="vertical", spacing=dp(6), **kw)
        self.app = app
        self.canal = 9                  # canal 10, donde vive la bateria en GM
        self.nota = 36                  # bombo en GM
        self.mandos = {}
        #: `(nota, msb) -> valor` de lo que **esta app ha pedido**. El QY100 no
        #: cuenta el estado de sus tambores, asi que esto es memoria propia, no
        #: lectura — y por eso lo que no esta aqui se pinta como «sin tocar» en
        #: vez de heredar la posicion del tambor anterior.
        self.recordado = {}

        b = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(8))
        b.add_widget(texto("canal", 12, color=APAGADO, size_hint_x=None,
                           width=dp(56), halign="right"))
        self.b_canal = Boton("CH 10", font_size=dp(13), size_hint_x=None,
                             width=dp(90))
        self.b_canal.bind(on_release=lambda *_: self.cambiar_canal())
        b.add_widget(self.b_canal)
        self.lb = texto("nota 36 — tocala para oir cual es", 12, color=APAGADO)
        b.add_widget(self.lb)
        self.add_widget(b)

        g = GridLayout(cols=12, spacing=dp(4), size_hint_y=None, height=dp(84))
        self.pads = {}
        for n in self.NOTAS:
            k = Boton(str(n), font_size=dp(11))
            k.bind(on_release=lambda _b, x=n: self.elegir(x))
            g.add_widget(k)
            self.pads[n] = k
        self.add_widget(g)

        # **Nombre arriba y valor abajo, los dos legibles.** La primera version
        # ponia `DEC` y `TUNE` en 11 dp sobre una fila de diez perillas
        # identicas: no se sabia cual era cual ni en cuanto estaba. Una etiqueta
        # que hay que descifrar es lo mismo que ninguna.
        rej = BoxLayout(spacing=dp(5))
        self.valores = {}
        for msb, etq, centrado in A.NRPN_BATERIA:
            col = BoxLayout(orientation="vertical", spacing=dp(2))
            col.add_widget(texto(etq, 13, size_hint_y=None, height=dp(22)))
            centro = 64 if centrado else (64 if centrado == "pan" else 0)
            w = Perilla(valor=centro,
                        cambio=lambda v, m=msb: self.manda(m, v))
            col.add_widget(w)
            lb = texto("%+d" % 0 if centrado else "0", 12, color=APAGADO,
                       size_hint_y=None, height=dp(22))
            col.add_widget(lb)
            rej.add_widget(col)
            self.mandos[msb] = w
            self.valores[msb] = (lb, centrado)
        self.add_widget(rej)

        self.pie = texto("", 11, color=APAGADO, size_hint_y=None, height=dp(20))
        self.add_widget(self.pie)
        self.elegir(self.nota, sonar=False)

    def cambiar_canal(self):
        self.canal = (self.canal + 1) % 16
        self.b_canal.text = "CH %d" % (self.canal + 1)

    def elegir(self, nota, sonar=True):
        """⚠️ **Cambiar de pad repinta las perillas.**

        Cada tambor tiene sus propios diez parametros —el `LSB` del NRPN es la
        nota—, asi que dejar las perillas donde estaban mostraria los valores del
        tambor anterior sobre el nuevo. Como el aparato no cuenta su estado, la
        app solo puede mostrar lo que ella misma pidio: lo pedido en ambar, lo
        que nadie ha tocado en gris y en su centro.
        """
        self.nota = nota
        for n, k in self.pads.items():
            act = n == nota
            tocado = any((n, m) in self.recordado for m, _e, _c in A.NRPN_BATERIA)
            k.vestir(fondo=(0.20, 0.16, 0.05, 1) if act else TENUE,
                     borde=PEDIDO if act else (VIVO if tocado else None),
                     color=PEDIDO if act else (TEXTO if tocado else APAGADO))
        self.lb.text = "nota %d" % nota
        for msb, _etq, centrado in A.NRPN_BATERIA:
            w = self.mandos[msb]
            lb, _c = self.valores[msb]
            v = self.recordado.get((nota, msb))
            crudo = v if v is not None else (64 if centrado else 0)
            w.poner(crudo)
            w.color_valor(PEDIDO if v is not None else APAGADO)
            lb.text = "—" if v is None else self._etiqueta(crudo, centrado)
        if sonar:
            self.golpear(nota)

    def golpear(self, nota):
        """**El pad suena.** Es la unica forma de saber que tambor es sin un mapa
        de nombres en el que no se puede confiar todavia."""
        out = self.app.aparato.salida
        if not out:
            return
        try:
            out.send(mido.Message("note_on", channel=self.canal,
                                  note=nota, velocity=110))
            Clock.schedule_once(lambda _dt: out.send(mido.Message(
                "note_off", channel=self.canal, note=nota, velocity=0)), 0.25)
        except Exception:
            pass

    @staticmethod
    def _etiqueta(crudo, centrado):
        """⚠️ **El `0` del pan es `random`, no «izquierda del todo».**

        Data List: `00H, 01H-40H-7FH (random, left - center - right)`. Mostrarlo
        como «0» sugiere un extremo del recorrido cuando es un modo aparte — y
        ese modo se oye como un ping-pong, que es como aparecio.
        """
        if centrado == "pan":
            if crudo == 0:
                return "random"
            return "C" if crudo == 64 else ("L%d" % (64 - crudo) if crudo < 64
                                            else "R%d" % (crudo - 64))
        return ("%+d" % (crudo - 64)) if centrado else str(crudo)

    def manda(self, msb, valor):
        out = self.app.aparato.salida
        if not out:
            return
        try:
            # ⚠️ El `LSB` **es la nota**, no un indice de parametro. Ese es el
            # giro de esta familia: el parametro va en el MSB y el instrumento
            # en el LSB, al reves de la edicion de voz.
            A.manda_nrpn(out, self.canal, msb, self.nota, int(valor))
            self.app.aparato.intentos += 3
            self.recordado[(self.nota, msb)] = int(valor)
            self.mandos[msb].color_valor(PEDIDO)
            lb, centrado = self.valores[msb]
            # **Lo que se muestra es lo que dice el aparato, no el byte.** Los
            # centrados van −64…0…+63 en pantalla aunque viajen como 0…127;
            # ensenar el crudo obligaria a restar 64 de cabeza cada vez.
            lb.text = self._etiqueta(int(valor), centrado)
            self.pie.text = ("ch%d  nota %d  NRPN %02X %02X"
                             % (self.canal + 1, self.nota, msb, self.nota))
        except Exception:
            pass


class BloqueEnvios(BoxLayout):
    """La pantalla de envios: `REVERB · CHORUS · VARI. · DRY`, todo en perillas.

    ⚠️ `DRY` **no tiene control change** — no esta en la lista del Data List. Va
    por SysEx (`08 nn 11`), asi que aqui es la unica fila que en modo vivo usa
    un camino distinto que las otras tres.
    """

    def __init__(self, app, pistas, vivo, base_canal=0, **kw):
        super().__init__(orientation="vertical", spacing=dp(3), **kw)
        self.app, self.vivo, self.base = app, vivo, base_canal
        self.mandos = {}
        self.al_cambiar = None
        cab = BoxLayout(size_hint_y=None, height=dp(20), spacing=dp(3))
        cab.add_widget(texto("", 10, size_hint_x=None, width=dp(64)))
        for et in pistas:
            cab.add_widget(texto(et, 11, color=TEXTO))
        self.add_widget(cab)
        for clave, etq in A.FILAS_MEZCLA:
            f = BoxLayout(spacing=dp(3))
            f.add_widget(texto(etq, 11, color=APAGADO, size_hint_x=None,
                               width=dp(64), halign="right"))
            for k in range(len(pistas)):
                w = Perilla(cambio=lambda v, i=k, c=clave: self.manda(i, c, v))
                f.add_widget(w)
                self.mandos[(k, clave)] = w
            self.add_widget(f)

    def manda(self, pista, clave, valor):
        if not self.vivo:
            if self.al_cambiar:
                self.al_cambiar()
            return
        canal = self.base + pista
        if clave == "dry":
            self.app.aparato.parametro((0x08, canal & 0x0F, 0x11), int(valor))
        else:
            cc = {"reverb": 91, "chorus": 93, "variacion": 94}[clave]
            self.app.aparato.envio(canal, cc, int(valor))

    def poner(self, valores):
        for (k, clave), w in self.mandos.items():
            w.poner(valores[k][clave])

    def color_valor(self, rgba):
        for w in self.mandos.values():
            w.color_valor(rgba)

    def leer_todo(self):
        return {(k, c): w.valor for (k, c), w in self.mandos.items()}


class Mezcla(Pantalla):
    """El mezclador del patron: **no es en vivo, y la pantalla lo dice.**

    `[M]` 2026-08-16: en modo patron los envios son **dato de la cabecera**, no
    `CC` por canal. Se probo con una rampa de `CC 91` por los 16 canales y no se
    movio ninguna perilla del aparato.

    Cambiar uno exige volcar, modificar y reescribir — segundos, no
    milisegundos. **Una perilla que tarda dos segundos no es una perilla**, asi
    que estas acumulan y `APLICAR` manda una sola escritura con todo.

    **El tipo de efecto si es en vivo** y por eso esta arriba y marcado distinto:
    entra al instante y desde cualquier pantalla del aparato. En tarima se puede
    cambiar `Hall` por `Distortion` de un toque; lo que no se puede es subirle el
    reverb solo al bajo.

    **Y aqui es donde la app pinta por primera vez estado MEDIDO.** `LEER` trae
    los valores reales del aparato y las perillas se ponen en cian. En cuanto se
    mueve una, pasa a ambar: pedido, sin confirmar. Es la misma convencion que la
    seccion y el `PLAY`, pero al reves — normalmente esta app solo puede pintar
    lo que pidio.
    """

    titulo = "MEZCLA"
    real = True

    def construir(self):
        self.patron = 4              # borrador, no el GALAXY de Shea
        self.cab = self.pistas = None
        self.valores = [{k: 0 for k, _ in A.FILAS_MEZCLA} for _ in range(8)]
        self.sucio = False
        self.ocupado = False
        self.perillas, self.b_efecto = {}, {}

        self.add_widget(texto(
            "[b]MEZCLA[/b] — los envios del patron   "
            "[color=fbb83d]no es en vivo: se acumula y se aplica[/color]",
            18, markup=True, size_hint_y=None, height=dp(30)))

        # --- barra: patron, leer, aplicar ----------------------------------
        b = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        b.add_widget(texto("patron", 12, color=APAGADO, size_hint_x=None,
                           width=dp(60), halign="right"))
        for etq, d in (("-", -1), ("+", 1)):
            k = Boton(etq, font_size=dp(16), size_hint_x=None, width=dp(46))
            k.bind(on_release=lambda _b, n=d: self.mover_patron(n))
            b.add_widget(k)
        self.lb_patron = texto(str(self.patron), 18, size_hint_x=None,
                               width=dp(56))
        b.add_widget(self.lb_patron)
        self.b_leer = Boton("LEER", font_size=dp(14), size_hint_x=None,
                            width=dp(110))
        self.b_leer.bind(on_release=lambda *_: self.leer())
        b.add_widget(self.b_leer)
        self.b_aplicar = Boton("APLICAR", font_size=dp(14), size_hint_x=None,
                               width=dp(130))
        self.b_aplicar.bind(on_release=lambda *_: self.aplicar())
        b.add_widget(self.b_aplicar)
        b.add_widget(Widget())
        self.add_widget(b)

        # --- el tipo: esto SI es en vivo -----------------------------------
        self.add_widget(texto(
            "[color=5be0d4]en vivo[/color] — tipo de variacion, de sistema sobre "
            "las 8 pistas. Con [b]Thru[/b] el envio VARI. no suena.",
            12, color=APAGADO, markup=True, size_hint_y=None, height=dp(20)))
        g = GridLayout(cols=12, spacing=dp(5), size_hint_y=None, height=dp(40))
        for fam, nombre in A.EFECTOS[:12]:
            k = Boton(nombre, font_size=dp(10))
            k.bind(on_release=lambda _b, f=fam: self.efecto(f))
            g.add_widget(k)
            self.b_efecto[fam] = k
        self.add_widget(g)

        # --- la rejilla, como la pantalla del aparato -----------------------
        self.add_widget(texto(
            "[color=fbb83d]diferido[/color] — dato de la cabecera del patron",
            12, color=APAGADO, markup=True, size_hint_y=None, height=dp(20)))
        cab = BoxLayout(size_hint_y=None, height=dp(22), spacing=dp(4))
        cab.add_widget(texto("", 11, size_hint_x=None, width=dp(76)))
        for pi in A.PISTAS_PATRON:
            cab.add_widget(texto(pi, 13))
        self.add_widget(cab)

        for clave, etq in A.FILAS_MEZCLA:
            fila = BoxLayout(spacing=dp(4))
            fila.add_widget(texto(etq, 12, color=APAGADO, size_hint_x=None,
                                  width=dp(76), halign="right"))
            for pista in range(8):
                k = Perilla(cambio=lambda v, p=pista, c=clave: self._mover(p, c, v))
                fila.add_widget(k)
                self.perillas[(pista, clave)] = k
            self.add_widget(fila)

        self.pie = texto("toca LEER para traer los valores del aparato", 11,
                         color=APAGADO, size_hint_y=None, height=dp(22))
        self.add_widget(self.pie)

    # -- estado ------------------------------------------------------------

    def mover_patron(self, d):
        self.patron = max(1, min(64, self.patron + d))
        self.lb_patron.text = str(self.patron)
        self.cab = None
        self.marcar(False)
        self.pie.text = "patron %d — toca LEER" % self.patron

    def marcar(self, medido):
        """Cian = leido del aparato. Ambar = pedido, sin confirmar."""
        col = VIVO if medido else PEDIDO
        for k in self.perillas.values():
            k.color_valor(col)
        self.sucio = not medido

    def _mover(self, pista, clave, valor):
        self.valores[pista][clave] = valor
        if not self.sucio:
            self.marcar(False)
        self.pie.text = ("%s %s = %d   ·   sin aplicar"
                         % (A.PISTAS_PATRON[pista],
                            dict(A.FILAS_MEZCLA)[clave], valor))

    def efecto(self, familia):
        self.app.aparato.conexion_variation(True)
        self.app.aparato.efecto(familia)
        for k, bt in self.b_efecto.items():
            act = k == familia
            bt.vestir(fondo=(0.20, 0.16, 0.05, 1) if act else TENUE,
                      borde=PEDIDO if act else None,
                      color=PEDIDO if act else TEXTO)

    # -- aparato (en hilo: son segundos, y la interfaz no se puede congelar) --

    def _tarea(self, fn):
        if self.ocupado:
            return
        self.ocupado = True
        self.b_leer.vestir(color=APAGADO)
        self.b_aplicar.vestir(color=APAGADO)
        threading.Thread(target=fn, daemon=True).start()

    def _listo(self, texto_pie, medido=None):
        def _(*_a):
            self.ocupado = False
            self.b_leer.vestir(color=TEXTO)
            self.b_aplicar.vestir(color=TEXTO)
            self.pie.text = texto_pie
            if medido is not None:
                self.marcar(medido)
        Clock.schedule_once(_)

    def leer(self):
        self.pie.text = "volcando la cabecera del patron %d..." % self.patron
        def trabajo():
            mz = A.Mezclador(self.app.aparato)
            vals, cab, pistas, nota = mz.leer(self.patron)
            if vals is None:
                self._listo("no se pudo leer: %s" % nota)
                return
            self.cab, self.pistas = cab, pistas
            for p in range(8):
                for clave, _ in A.FILAS_MEZCLA:
                    self.valores[p][clave] = vals[p][clave]
            def pintar(*_a):
                for (p, clave), k in self.perillas.items():
                    k.poner(self.valores[p][clave])
            Clock.schedule_once(pintar)
            self._listo("patron %d — %s" % (self.patron, nota), medido=True)
        self._tarea(trabajo)

    def aplicar(self):
        if self.cab is None:
            self.pie.text = "primero LEER: hay que partir de la cabecera real"
            return
        self.pie.text = "escribiendo..."
        def trabajo():
            mz = A.Mezclador(self.app.aparato)
            nota = mz.escribir(self.patron, self.cab, self.pistas, self.valores)
            self._listo("patron %d — %s" % (self.patron, nota))
        self._tarea(trabajo)


class Conexion(Pantalla):
    titulo = "CONEXION"
    real = True

    def construir(self):
        self.add_widget(texto("[b]CONEXION[/b] — se abre cuando algo se rompe",
                              18, markup=True, size_hint_y=None, height=dp(30)))
        self.lista = BoxLayout(orientation="vertical", size_hint_y=None,
                               height=dp(120), spacing=dp(6))
        self.add_widget(self.lista)
        mc = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        mc.add_widget(texto("MIDI CONTROL", 12, color=APAGADO, size_hint_x=None,
                            width=dp(120), halign="right"))
        for nombre in ("Off", "In", "Out", "In/Out"):
            b = Boton(nombre, font_size=dp(12))
            b.bind(on_release=lambda _b, n=nombre: self.app.poner_mc(n))
            mc.add_widget(b)
        self.add_widget(mc)
        self.add_widget(texto(
            "El volcado funciona en los cuatro. Lo que [b]Off[/b] corta son notas, "
            "CC y transporte — un PLAY que no arranca casi siempre es esto.",
            11, color=APAGADO, markup=True, size_hint_y=None, height=dp(30),
            halign="center"))
        self.add_widget(texto(
            "Tres cosas fallan con el mismo sintoma —silencio— y por eso las tres\n"
            "estan siempre a la vista arriba: el puerto, el modo del aparato y\n"
            "MIDI CONTROL. Verlas es mas barato que diagnosticarlas.\n\n"
            "Un puerto queda obsoleto tras reconectar el cable aunque el nombre\n"
            "no cambie: reconectar aqui cierra y reabre, no reutiliza.",
            13, color=APAGADO, halign="center"))
        self.refrescar()

    def refrescar(self):
        self.lista.clear_widgets()
        ps = A.Aparato.puertos() or ["(no hay puertos)"]
        for p in ps:
            b = Boton("  %s" % p, halign="left", font_size=dp(14),
                      size_hint_y=None, height=dp(34))
            b.bind(on_release=lambda _b, n=p: self.app.conectar(n))
            self.lista.add_widget(b)


# ---------------------------------------------------------------- la hoja FX

class Velo(Widget):
    """El fondo oscurecido detras de una hoja. **Existe para dos cosas**: para
    que se vea que hay una pantalla debajo —que es la diferencia entre una hoja
    y una pantalla nueva— y para cerrarla tocando fuera, que es como se cierran
    las hojas en una tableta."""

    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        with self.canvas.before:
            Color(0, 0, 0, 0.55)
            self._r = RoundedRectangle()
        self.bind(pos=lambda *_: setattr(self._r, "pos", self.pos),
                  size=lambda *_: setattr(self._r, "size", self.size))

    def on_touch_down(self, touch):
        self.app.hoja(None)
        return True


class HojaFX(BoxLayout):
    """La hoja se desliza encima y se va. **No es una pantalla**, y esa es la
    idea que la maqueta esta probando: elegir un efecto no te saca de donde
    estabas.

    Vive fuera de MEZCLA porque el aparato mismo la trata asi — `[M]` el tipo de
    efecto entra con el QY100 en cualquier otra pantalla.

    ⚠️ **Va numerada, y no por pedagogia.** `Variation Part` vale `7F` (off) de
    fabrica: si no se asigna una pista primero, cambiar el tipo **no se oye**, y
    ese silencio se lee identico a «esto no funciona». El orden es el unico que
    da un resultado interpretable.

    La primera version metia enrutado, 18 efectos y 8 parametros en un panel — y
    ademas quedaba mas alta que la ventana, asi que la cabecera con el boton de
    cerrar se salia por arriba. Dos fallos distintos con el mismo sintoma:
    nadie sabia que hacer con ella.
    """

    def __init__(self, app, **kw):
        super().__init__(orientation="vertical", padding=dp(18),
                         spacing=dp(8), **kw)
        self.app = app
        with self.canvas.before:
            Color(0.08, 0.09, 0.105, 1)
            self._r = RoundedRectangle(radius=[dp(18)])
        self.bind(pos=lambda *_: setattr(self._r, "pos", self.pos),
                  size=lambda *_: setattr(self._r, "size", self.size))
        self.b_efecto = {}

        cab = BoxLayout(size_hint_y=None, height=dp(46))
        cab.add_widget(texto("[b]VARIATION[/b]   un efecto, enrutable",
                             17, markup=True, halign="left"))
        x = Boton("CERRAR", size_hint_x=None, width=dp(120), font_size=dp(14))
        x.bind(on_release=lambda *_: self.app.hoja(None))
        cab.add_widget(x)
        self.add_widget(cab)

        # --- 1: a donde va -------------------------------------------------
        self.add_widget(texto(
            "En modo patron esta etapa es [b]siempre de sistema[/b], sobre las 8 "
            "pistas (manual p. 122). Lo que la hace sonar es el envio [b]Var[/b] "
            "de cada canal, en MEZCLA — aqui solo se elige el tipo.\n"
            "Reverb y Chorus no son editables en patron: son HALL1 y CHORUS1.",
            12, color=PEDIDO, markup=True, size_hint_y=None, height=dp(56),
            halign="center"))

        # --- 2: cual --------------------------------------------------------
        self.add_widget(texto("¿que efecto?", 13, color=PEDIDO,
                              markup=True, halign="left",
                              size_hint_y=None, height=dp(24)))
        g = GridLayout(cols=6, spacing=dp(6), size_hint_y=None, height=dp(88))
        for fam, nombre in A.EFECTOS[:12]:
            b = Boton(nombre, font_size=dp(11))
            b.bind(on_release=lambda _b, f=fam: self.efecto(f))
            g.add_widget(b)
            self.b_efecto[fam] = b
        self.add_widget(g)

        # --- 3: cuanto ------------------------------------------------------
        self.add_widget(texto("¿cuanto?", 13, color=PEDIDO,
                              markup=True, halign="left",
                              size_hint_y=None, height=dp(24)))
        # **Las etiquetas se rehacen al cambiar de efecto.** El Data List dice
        # de cada Param «depends on vari. type», y ahora sabemos de que: bajo
        # `Hall` el 3 es Initial Delay y bajo `Delay L,C,R` es Cch Delay.
        self.etiquetas = {}
        for addr, nombre, techo, tam in A.PARAMETROS[:3]:
            r = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(10))
            seguro = addr in A.BIDIRECCIONALES
            lb = texto(
                "%s%s" % (nombre, "" if seguro else "  [color=6b7276]?[/color]"),
                12, markup=True, halign="left", size_hint_x=0.34)
            self.etiquetas[addr] = (lb, nombre, seguro)
            r.add_widget(lb)
            sl = Slider(min=0, max=techo, value=techo // 3)
            sl._ultimo = techo // 3
            sl.bind(value=lambda w, v, a=addr, t=tam: self._quiza(w, a, int(v), t))
            sl.bind(value=lambda *_: self._eco())
            r.add_widget(sl)
            self.add_widget(r)

        # **El eco va DENTRO de la hoja.** La barra de estado queda detras del
        # velo y no se puede leer con la hoja abierta — y sin eco, tocar un
        # boton no produce ninguna senal de que algo paso.
        self.eco = texto("nada mandado aun", 11, color=APAGADO,
                         size_hint_y=None, height=dp(22))
        self.add_widget(self.eco)
        self.add_widget(texto(
            "Los [b]Param 1-10[/b] cambian de significado con cada tipo — el Data "
            "List lo dice: «depends on vari. type». Los envios [b]por canal[/b] "
            "son otros (CC 91/93/94) y van en MEZCLA.",
            11, color=APAGADO, markup=True, size_hint_y=None, height=dp(36),
            halign="center"))

    # -- estado ------------------------------------------------------------
    #
    # **Ambar, nunca cian.** Es el mismo criterio que la seccion pedida y que el
    # PLAY: el QY100 no cuenta que efecto tiene puesto, asi que lo unico que la
    # app puede pintar es lo que PIDIO. Cian se reserva para lo medido.

    def _vestir(self, mapa, clave):
        for k, b in mapa.items():
            act = k == clave
            b.vestir(fondo=(0.20, 0.16, 0.05, 1) if act else TENUE,
                     borde=PEDIDO if act else None,
                     color=PEDIDO if act else TEXTO)

    def efecto(self, familia):
        self.app.aparato.efecto(familia)
        self._vestir(self.b_efecto, familia)
        self.renombrar(familia)
        self._eco()

    def renombrar(self, familia):
        """Pone a cada `Param` su nombre real para ese tipo de efecto.

        ⚠️ **Y apaga el que no existe.** La tabla tiene huecos —`Flanger` no
        tiene param 5— y dejar una perilla viva para un parametro que el aparato
        no tiene es prometer de mas: se moveria y no pasaria nada.
        """
        # `Variation Param N` esta en `02 01 42 + (N-1)*2`.
        for addr, (lb, base, seguro, sl) in self.etiquetas.items():
            if addr[2] < 0x42:
                continue
            n = (addr[2] - 0x42) // 2 + 1
            real = A.nombre_parametro(familia, n)
            if real:
                lb.text = "[b]%s[/b]  [color=6b7276]p%d[/color]" % (real, n)
                lb.color = TEXTO
                sl.disabled = False
            else:
                lb.text = "Param %d  [color=6b7276]no existe con este efecto[/color]" % n
                lb.color = APAGADO
                sl.disabled = True

    def _eco(self):
        self.eco.text = "mandado:  %s" % (self.app.aparato.ultimo or "-")

    def on_touch_down(self, touch):
        """La hoja se come lo que cae dentro. Sin esto, tocar su fondo llegaba
        al velo y la cerraba — un toque fallido cerraba la hoja entera."""
        if self.collide_point(*touch.pos):
            super().on_touch_down(touch)
            return True
        return super().on_touch_down(touch)

    def _quiza(self, widget, addr, valor, tam=1):
        """Manda solo si el entero se movio de verdad."""
        if getattr(widget, "_ultimo", None) == valor:
            return
        widget._ultimo = valor
        self.app.aparato.parametro(addr, valor, tam)


class HojaVoz(BoxLayout):
    """Buscar entre las 525, no `CATEGORY -> BANK -> PROGRAM`.

    **Es el requisito explicito del plan hecho realidad**: en el aparato cambiar
    una voz son cinco menus; aqui son tres toques — la pista, el nombre, listo.
    Y se puede porque los 525 nombres salieron de la ROM del firmware y el banco
    estaba impreso en el Data List.

    ⚠️ **Una pista de bateria ofrece kits, no voces.** Son tablas distintas y
    cruzarlas daria un nombre coherente y falso — `programa 0` es `GrandPno` en
    una y `Standard Kit` en la otra.
    """

    def __init__(self, app, pista, etiqueta, bateria, elegido, en_vivo=False,
                 **kw):
        super().__init__(orientation="vertical", padding=dp(18),
                         spacing=dp(10), **kw)
        self.app, self.elegido, self.bateria = app, elegido, bateria
        #: ⚠️ **En vivo solo se pueden pedir 477 de las 525.** Las otras salen del
        #: ROM con nombre y sin numero de programa, asi que no hay como pedirlas
        #: — y adivinarlo por posicion daria una voz plausible y equivocada. Se
        #: muestran apagadas: **se ven, no se piden.** En diferido da igual,
        #: porque ahi la voz se escribe por su indice en la cabecera.
        self.en_vivo = en_vivo
        with self.canvas.before:
            Color(0.08, 0.09, 0.105, 1)
            self._r = RoundedRectangle(radius=[dp(18)])
        self.bind(pos=lambda *_: setattr(self._r, "pos", self.pos),
                  size=lambda *_: setattr(self._r, "size", self.size))

        cab = BoxLayout(size_hint_y=None, height=dp(42))
        cab.add_widget(texto("[b]VOZ[/b]   pista %s   ·   %s%s" % (
            etiqueta, "kits de bateria" if bateria else "525 voces",
            "   ·   [color=fbb83d]en gris, las 48 sin numero de programa[/color]"
            if (en_vivo and not bateria) else ""),
            16, markup=True, halign="left"))
        x = Boton("CERRAR", size_hint_x=None, width=dp(110), font_size=dp(13))
        x.bind(on_release=lambda *_: self.app.hoja(None))
        cab.add_widget(x)
        self.add_widget(cab)

        # Filtros por familia. **No sustituyen a la busqueda, la acompanan**:
        # para 525 nombres escribir «bass» sigue siendo mas rapido que navegar.
        self.fam = None
        if not bateria:
            fl = GridLayout(cols=9, spacing=dp(4), size_hint_y=None, height=dp(56))
            self.b_fam = {}
            for et in ["todas"] + A.FAMILIAS + ["sin categoria"]:
                b = Boton(et, font_size=dp(10), size_hint_y=None, height=dp(26))
                b.bind(on_release=lambda _b, e=et: self.filtrar(e))
                fl.add_widget(b)
                self.b_fam[et] = b
            self.add_widget(fl)

        self.buscar = TextInput(hint_text="escribe para filtrar...",
                                multiline=False, size_hint_y=None,
                                height=dp(40), font_size=dp(15))
        self.buscar.bind(text=lambda *_: self.pintar())
        self.add_widget(self.buscar)

        sv = ScrollView()
        self.lista = GridLayout(cols=4, spacing=dp(5), size_hint_y=None)
        self.lista.bind(minimum_height=self.lista.setter("height"))
        sv.add_widget(self.lista)
        self.add_widget(sv)
        self.pintar()

    def filtrar(self, etiqueta):
        self.fam = None if etiqueta == "todas" else etiqueta
        for e, b in self.b_fam.items():
            act = e == etiqueta
            b.vestir(fondo=(0.16, 0.19, 0.22, 1) if act else TENUE,
                     borde=VIVO if act else None,
                     color=TEXTO if act else APAGADO)
        self.pintar()

    def _fuente(self):
        if self.bateria:
            return sorted(A.KITS.items())
        return list(enumerate(A.VOCES))

    def pintar(self):
        f = self.buscar.text.strip().lower()
        self.lista.clear_widgets()
        n = 0
        for pr, nombre in self._fuente():
            if f and f not in nombre.lower():
                continue
            if self.fam and not self.bateria:
                fam = A.familia(nombre)
                if self.fam == "sin categoria":
                    if fam is not None:
                        continue
                elif fam != self.fam:
                    continue
            pedible = (not self.en_vivo or self.bateria
                       or A.voz_direccionable(nombre) is not None)
            b = Boton(nombre, font_size=dp(11), size_hint_y=None, height=dp(34))
            if not pedible:
                b.color = (0.32, 0.34, 0.36, 1)
            else:
                b.bind(on_release=lambda _b, p=pr, nm=nombre: self.tomar(p, nm))
            self.lista.add_widget(b)
            n += 1
            if n >= 240:          # el filtro es la navegacion, no el scroll
                break

    def tomar(self, programa, nombre):
        self.elegido(programa, nombre)
        self.app.hoja(None)


class HojaAcorde(BoxLayout):
    """Rueda de raiz y tipo para el `SOURCE CHORD`.

    ⚠️ **Solo `M7` y `m7` estan medidos.** El aparato tiene mas tipos y nadie los
    ha barrido — `SRC_CHORD_TYPES` es lo comprobado, no lo que hay. Ofrecer los
    demas seria inventar bytes.
    """

    def __init__(self, app, etiqueta, actual, elegido, **kw):
        super().__init__(orientation="vertical", padding=dp(18),
                         spacing=dp(10), **kw)
        self.app, self.elegido = app, elegido
        self.raiz, self.tipo = actual if actual else ("C", "M7")
        with self.canvas.before:
            Color(0.08, 0.09, 0.105, 1)
            self._r = RoundedRectangle(radius=[dp(18)])
        self.bind(pos=lambda *_: setattr(self._r, "pos", self.pos),
                  size=lambda *_: setattr(self._r, "size", self.size))

        cab = BoxLayout(size_hint_y=None, height=dp(42))
        cab.add_widget(texto("[b]SOURCE CHORD[/b]   pista %s" % etiqueta,
                             16, markup=True, halign="left"))
        x = Boton("CERRAR", size_hint_x=None, width=dp(110), font_size=dp(13))
        x.bind(on_release=lambda *_: self.app.hoja(None))
        cab.add_widget(x)
        self.add_widget(cab)

        self.add_widget(texto("raiz", 12, color=APAGADO, size_hint_y=None,
                              height=dp(20)))
        g = GridLayout(cols=12, spacing=dp(5), size_hint_y=None, height=dp(46))
        self.b_raiz = {}
        for r in A.F.CHORD_ROOTS:
            b = Boton(r, font_size=dp(13))
            b.bind(on_release=lambda _b, x=r: self.poner(x, None))
            g.add_widget(b)
            self.b_raiz[r] = b
        self.add_widget(g)

        # **Los medidos se marcan distinto.** Cinco de los 27 se comprobaron
        # contra la pantalla del aparato; los otros 22 entran por analogia con la
        # tabla del acorde actual. La hoja no los esconde ni los iguala: los
        # ofrece todos y dice cuales estan comprobados.
        self.add_widget(texto(
            "tipo — [color=5be0d4]en cian los 5 medidos[/color], el resto por "
            "analogia con la tabla del acorde actual",
            12, color=APAGADO, markup=True, size_hint_y=None, height=dp(20)))
        g = GridLayout(cols=9, spacing=dp(4), size_hint_y=None, height=dp(92))
        self.b_tipo = {}
        for t in sorted(A.F.SRC_CHORD_TYPES, key=lambda x: A.F.SRC_CHORD_TYPES[x]):
            b = Boton(t, font_size=dp(11))
            if t in A.F.SRC_CHORD_MEDIDOS:
                b.color = VIVO
            b.bind(on_release=lambda _b, x=t: self.poner(None, x))
            g.add_widget(b)
            self.b_tipo[t] = b
        self.add_widget(g)

        self.lb = texto("", 20, markup=True, size_hint_y=None, height=dp(40))
        self.add_widget(self.lb)
        ok = Boton("PONER", font_size=dp(15), size_hint_y=None, height=dp(46))
        ok.bind(on_release=lambda *_: self.confirmar())
        self.add_widget(ok)
        self.poner(None, None)

    def poner(self, raiz, tipo):
        if raiz:
            self.raiz = raiz
        if tipo:
            self.tipo = tipo
        for mapa, sel in ((self.b_raiz, self.raiz), (self.b_tipo, self.tipo)):
            for k, b in mapa.items():
                act = k == sel
                base = VIVO if k in A.F.SRC_CHORD_MEDIDOS else TEXTO
                b.vestir(fondo=(0.20, 0.16, 0.05, 1) if act else TENUE,
                         borde=PEDIDO if act else None,
                         color=PEDIDO if act else base)
        self.lb.text = "[b]%s%s[/b]" % (self.raiz, self.tipo)

    def confirmar(self):
        self.elegido(self.raiz, self.tipo)
        self.app.hoja(None)


class HojaSimple(BoxLayout):
    def __init__(self, app, nombre, cuerpo, **kw):
        super().__init__(orientation="vertical", padding=dp(20),
                         spacing=dp(12), **kw)
        with self.canvas.before:
            Color(0.07, 0.08, 0.095, 1)
            self._r = RoundedRectangle(radius=[dp(18)])
        self.bind(pos=lambda *_: setattr(self._r, "pos", self.pos),
                  size=lambda *_: setattr(self._r, "size", self.size))
        cab = BoxLayout(size_hint_y=None, height=dp(36))
        cab.add_widget(texto("[b]%s[/b]   hoja global" % nombre, 16,
                             markup=True, halign="left"))
        x = Boton("cerrar", size_hint_x=None, width=dp(90), font_size=dp(13))
        x.bind(on_release=lambda *_: app.hoja(None))
        cab.add_widget(x)
        self.add_widget(cab)
        self.add_widget(texto(cuerpo, 14, color=APAGADO, halign="center",
                              markup=True))


# ---------------------------------------------------------------------- app

class Maqueta(App):
    def build(self):
        self.aparato = A.Aparato()
        self.aparato.abrir()
        self.mc_valor = None
        # **El arranque deja el aparato utilizable, no solo conectado.** Con
        # `MIDI CONTROL` en `Off` el transporte no responde y nada lo dice.
        threading.Thread(target=self._mc_arranque, daemon=True).start()
        self._capas = []

        raiz = FloatLayout()
        col = BoxLayout(orientation="vertical")
        with col.canvas.before:
            Color(*FONDO)
            r = RoundedRectangle()
        col.bind(pos=lambda *_: setattr(r, "pos", col.pos),
                 size=lambda *_: setattr(r, "size", col.size))

        # --- barra de estado: las tres cosas que fallan con el mismo sintoma ---
        self.estado = texto("", 13, halign="center", size_hint_y=None,
                            height=dp(30), markup=True)
        col.add_widget(self.estado)

        self.cuerpo = BoxLayout()
        col.add_widget(self.cuerpo)

        # --- transporte fijo, en las cinco pantallas ---
        tr = caja(size_hint_y=None, height=dp(64), padding=dp(10), spacing=dp(8))
        # transporte: los tres juntos, porque son la misma mano
        self.b_play = Boton("PLAY", size_hint_x=None, width=dp(76),
                            font_size=dp(14))
        self.b_play.bind(on_release=lambda *_: self.play())
        tr.add_widget(self.b_play)
        for t, f in (("STOP", lambda *_: self.stop()),
                     ("CONT", lambda *_: self.aparato.continuar())):
            b = Boton(t, size_hint_x=None, width=dp(70), font_size=dp(13))
            b.bind(on_release=f)
            tr.add_widget(b)

        self.tr_info = texto("", 12, color=APAGADO, halign="center")
        self.tr_info.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        tr.add_widget(self.tr_info)

        # las hojas, al otro extremo: no son transporte
        for nombre in ("VOZ", "FX", "ACORDE"):
            b = Boton(nombre, size_hint_x=None, width=dp(80), font_size=dp(12))
            b.bind(on_release=lambda _b, n=nombre: self.hoja(n))
            tr.add_widget(b)

        # **el panico va aparte y en rojo.** No es un control de transporte: es
        # una valvula. Se usa cuando algo ya salio mal, y tiene que distinguirse
        # de STOP a un metro de distancia y con las manos ocupadas.
        bp = Boton("!", size_hint_x=None, width=dp(46), font_size=dp(18),
                   fondo=(0.24, 0.09, 0.11, 1))
        bp.color = ALERTA
        bp.bind(on_release=lambda *_: self.panico())
        tr.add_widget(bp)
        col.add_widget(tr)

        # --- las cinco, hermanas ---
        self.pantallas, self.pestanas = {}, {}
        barra = BoxLayout(size_hint_y=None, height=dp(58), spacing=dp(6),
                          padding=(dp(6), dp(4)))
        for cls in (Tocar, Patron, Cancion, Conexion):
            p = cls(self)
            self.pantallas[cls.titulo] = p
            b = Boton(cls.titulo, font_size=dp(14))
            b.bind(on_release=lambda _b, n=cls.titulo: self.ir(n))
            barra.add_widget(b)
            self.pestanas[cls.titulo] = b
        col.add_widget(barra)

        raiz.add_widget(col)
        self.raiz = raiz
        self.ir("PATRON")
        Clock.schedule_interval(self.refrescar, 0.25)
        return raiz

    # -- navegacion --------------------------------------------------------

    def ir(self, nombre):
        self.cuerpo.clear_widgets()
        self.cuerpo.add_widget(self.pantallas[nombre])
        for n, b in self.pestanas.items():
            act = n == nombre
            b.vestir(fondo=(0.16, 0.19, 0.22, 1) if act else PANEL,
                     borde=VIVO if act else None,
                     color=TEXTO if act else APAGADO)

    def hoja_voz(self, etiqueta, bateria, elegido, en_vivo=False):
        self.hoja(None)
        w = HojaVoz(self, 0, etiqueta, bateria, elegido, en_vivo=en_vivo,
                    size_hint=(0.86, 0.78), pos_hint={"center_x": 0.5, "y": 0.11})
        velo = Velo(self, size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        self._capas = [velo, w]
        self.raiz.add_widget(velo)
        self.raiz.add_widget(w)

    def hoja_acorde(self, etiqueta, actual, elegido):
        self.hoja(None)
        w = HojaAcorde(self, etiqueta, actual, elegido, size_hint=(0.7, 0.66),
                       pos_hint={"center_x": 0.5, "y": 0.17})
        velo = Velo(self, size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        self._capas = [velo, w]
        self.raiz.add_widget(velo)
        self.raiz.add_widget(w)

    def hoja(self, nombre):
        """Una hoja **se pone encima**, no reemplaza. Por eso la pantalla de
        abajo sigue montada y visible en los bordes: es la diferencia que la
        maqueta quiere que se sienta."""
        for w in getattr(self, "_capas", []):
            self.raiz.remove_widget(w)
        self._capas = []
        if not nombre:
            return
        if nombre == "FX":
            w = HojaFX(self, size_hint=(0.92, 0.66),
                       pos_hint={"center_x": 0.5, "y": 0.16})
        elif nombre == "VOZ":
            w = HojaSimple(self, "VOZ",
                           "Busqueda sobre las [b]525 voces[/b], no\n"
                           "categoria -> banco -> programa.\n\n"
                           "Posible porque el banco estaba impreso en el Data\n"
                           "List: [b]Bank Select MSB=000, LSB=Bank Number[/b].\n\n"
                           "Sin cablear en la maqueta.",
                           size_hint=(0.8, 0.6),
                           pos_hint={"center_x": 0.5, "y": 0.12})
        else:
            w = HojaSimple(self, "ACORDE",
                           "[b]SOURCE CHORD[/b] — rueda de raiz + tipo.\n\n"
                           "Bytes 21-22 del prefijo, escribibles sin tocar el\n"
                           "byte 75. Medido el 2026-08-16: la pantalla del\n"
                           "aparato paso de Cm7 a Fm7.\n\n"
                           "Es lo unico de la app que hace algo que el QY100\n"
                           "[b]no puede hacer solo[/b]: en las frases de fabrica\n"
                           "no deja editarlo desde sus botones.\n\n"
                           "Sin cablear en la maqueta.",
                           size_hint=(0.8, 0.66),
                           pos_hint={"center_x": 0.5, "y": 0.1})
        velo = Velo(self, size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        self._capas = [velo, w]
        self.raiz.add_widget(velo)
        self.raiz.add_widget(w)

    # -- acciones ----------------------------------------------------------

    def ruta_variation(self, parte):
        """Insercion sobre una parte: hay que poner las dos cosas, y en este
        orden — la conexion primero, porque asignar parte con el efecto en modo
        sistema no cambia a que suena."""
        self.aparato.conexion_variation(False)
        self.aparato.parte_variation(parte)

    def _mc_arranque(self):
        mc = A.MidiControl(self.aparato)
        v = mc.leer()
        if v is not None and v not in (0x10, 0x30):
            v = mc.poner("In/Out")
        self.mc_valor = v

    def poner_mc(self, nombre):
        def trabajo():
            self.mc_valor = A.MidiControl(self.aparato).poner(nombre)
        threading.Thread(target=trabajo, daemon=True).start()

    def play(self):
        """`[D]` **Se pinta lo que la app cree, no lo que pasa.** El QY100 no
        avisa que arranco ni que paro, y cualquiera puede pararlo desde el
        panel — asi que el boton se marca en ambar (creencia) y no en cian
        (medido), igual que la seccion pedida."""
        self.aparato.arrancar()

    def stop(self):
        self.aparato.parar()

    def disparar_seccion(self, i):
        self.aparato.seccion_a(i)
        self.pantallas["PATRON"].marcar(i)

    def conectar(self, nombre):
        self.aparato.abrir(nombre)
        self.pantallas["CONEXION"].refrescar()

    def panico(self):
        self.aparato.panico()

    def refrescar(self, _dt):
        a = self.aparato
        puerto = a.nombre or "sin puerto"
        cp = "5be0d4" if a.salida else "ee4a5c"
        modo = {"song": "SONG", "pattern": "PATTERN"}.get(a.modo, "sin saber")
        cm = "5be0d4" if a.modo else "6b7276"
        # **La barra de estado no promete: muestra lo leido.** Decia «MIDI
        # CONTROL lo pone la app» y era falso — la app nunca lo ponia, y el
        # ajuste se quedo en Off de una prueba vieja hasta que el PLAY dejo de
        # funcionar sin decir por que. Justo el fallo silencioso que esta barra
        # existe para evitar.
        mc = getattr(self, "mc_valor", None)
        if mc is None:
            smc, cc = "sin leer", "6b7276"
        else:
            smc = A.MC_NOMBRES.get(mc, "?")
            # ambar si esta en un valor que rompe cosas sin avisar
            cc = "5be0d4" if mc in (0x10, 0x30) else "fbb83d"
        self.estado.text = (
            "[color=%s]%s[/color]   ·   modo [color=%s]%s[/color]   ·   "
            "MIDI CONTROL [color=%s]%s[/color]   ·   %d mensajes"
            % (cp, puerto, cm, modo, cc, smc, a.intentos))
        self.b_play.vestir(
            fondo=(0.20, 0.16, 0.05, 1) if a.tocando else TENUE,
            borde=PEDIDO if a.tocando else None,
            color=PEDIDO if a.tocando else TEXTO)
        sec = ("pedida %s" % A.SECCIONES[a.seccion]) if a.seccion is not None \
            else "sin seccion pedida"
        self.tr_info.text = "el BPM lo lleva el aparato   ·   %s   ·   %s" % (
            sec, a.ultimo or "nada mandado aun")

    def on_stop(self):
        self.aparato.panico()
        self.aparato.cerrar()


if __name__ == "__main__":
    Maqueta().run()
