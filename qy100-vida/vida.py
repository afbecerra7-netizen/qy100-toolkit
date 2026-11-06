"""El juego de la vida como secuenciador — prototipo para medir, no para tocar.

La rejilla es un piano roll: **columna = tiempo, fila = grado de la escala**.
La barra recorre las columnas; las celulas vivas de la columna suenan.

Existe para contestar cuatro preguntas en una noche, no para ser el instrumento:

  1. ¿El modelo tactil de Kivy se siente bien para una rejilla?
  2. **¿El `Clock` de Kivy aguanta un paso musical, o el tiempo se tambalea?**
  3. ¿Dibujar se mantiene fluido?
  4. ¿El stack MIDI se molesta por compartir proceso con una interfaz?

La 2 es la que decide, y por eso este programa **se mide a si mismo**: guarda el
intervalo real entre pasos y muestra desviacion media y maxima contra el pedido.
Si el tambaleo es audible, **la respuesta no es comprar hardware** — es invertir
la maestria de reloj y esclavizar el paso al MIDI clock que ya manda el QY100.

La logica vive en `automata.py`, que no importa Kivy y por eso si se puede
probar sin pantalla. Aqui solo hay dibujo, dedos y reloj.

El MIDI sale por `salida.py`, que se abre y se cierra con el boton `MIDI`.
La velocity la ponen los vecinos vivos de cada celula.

    .venv/bin/python vida.py
"""

import os
import time
from collections import deque

os.environ.setdefault("KIVY_NO_ARGS", "1")

from kivy.app import App                                          # noqa: E402
from kivy.clock import Clock                                      # noqa: E402

import reloj as R                                                # noqa: E402
from kivy.core.window import Window                               # noqa: E402
from kivy.graphics import Color, Rectangle                        # noqa: E402
from kivy.uix.boxlayout import BoxLayout                          # noqa: E402
from kivy.uix.button import Button                                # noqa: E402
from kivy.uix.label import Label                                  # noqa: E402
from kivy.uix.widget import Widget                                # noqa: E402

import automata as A                                              # noqa: E402
from salida import Salida                                         # noqa: E402

FONDO = (0.04, 0.05, 0.06)
MUERTA = (0.11, 0.13, 0.15)
VIVA = (0.93, 0.29, 0.36)
SONANDO = (0.36, 0.94, 0.86)
BARRA = (0.16, 0.42, 0.34, 0.55)
GRIS = (0.16, 0.18, 0.2, 1)


class Rejilla(Widget):
    """Dibujo, dedos y reloj. La regla y las notas las pone `automata.py`."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.mundo = A.Automata()
        self.salida = Salida()
        self.mundo.sembrar_ruido()
        self.paso = 0
        self.sonando = []                  # filas que suenan en el paso actual
        self.corriendo = False
        self.bpm = 96

        # Lo unico que este prototipo tiene que probar.
        #
        # **Se acumulan TODOS los intervalos desde que se le dio a TOCAR**, no
        # una ventana movil. Una media sobre las ultimas N baila con cada paso y
        # no se puede citar: es una lectura de un instante disfrazada de
        # medicion, el mismo error que cometio `medir_audio.py` en su primera
        # version. Aqui se muestra el REPARTO —n, mediana, p95, maximo— que es lo
        # que se puede escribir en un documento.
        self._ultimo = None
        self.intervalos = []

        self.bind(pos=lambda *a: self.pintar(), size=lambda *a: self.pintar())

    # -- geometria ----------------------------------------------------------

    def metrica(self):
        """Lado de celda y origen, centrando la rejilla cuadrada en el widget."""
        lado = min(self.width / self.mundo.columnas, self.height / self.mundo.filas)
        return lado, (self.x + (self.width - lado * self.mundo.columnas) / 2,
                      self.y + (self.height - lado * self.mundo.filas) / 2)

    # -- dedos --------------------------------------------------------------

    def on_touch_down(self, touch):
        """Kivy despacha un `touch` por dedo, asi que el multitactil sale gratis."""
        return self._tocar(touch)

    def on_touch_move(self, touch):
        return self._tocar(touch, arrastrando=True)

    def _tocar(self, touch, arrastrando=False):
        if not self.collide_point(*touch.pos):
            return False
        lado, (ox, oy) = self.metrica()
        col = int((touch.x - ox) // lado)
        fila = int((touch.y - oy) // lado)
        if not (0 <= col < self.mundo.columnas and 0 <= fila < self.mundo.filas):
            return False
        # Arrastrar dibuja y no borra: si alternara, pasar el dedo por encima de
        # lo ya dibujado lo apagaria y no se puede trazar una linea.
        if arrastrando:
            self.mundo.encender(fila, col)
        else:
            self.mundo.alternar(fila, col)
        self.pintar()
        return True

    # -- el secuenciador ----------------------------------------------------

    def emitir(self, filas):
        """La costura del MIDI. Ver `salida.py`.

        La velocity sale de los vecinos vivos: la celula mas arraigada suena
        mas fuerte. Es la misma prioridad que gano la subasta, reutilizada como
        dinamica en vez de tirarla.
        """
        self.salida.tocar([self.mundo.nota_de(f) for f in filas],
                          [self.mundo.vecinos(f, (self.paso)) for f in filas])

    def avanzar_externo(self):
        """Un paso disparado por el reloj del QY100. **Corre en el hilo MIDI.**

        El sonido se manda aqui mismo, que es lo unico con exigencia de tiempo;
        el dibujo se agenda en el hilo de Kivy. Pintar desde el hilo MIDI
        funciona a veces y revienta a veces, que es la peor clase de fallo.
        """
        self.sonando = self.mundo.subasta(self.paso)
        self.emitir(self.sonando)
        self.paso = (self.paso + 1) % self.mundo.columnas
        if self.paso == 0:
            self.mundo.evolucionar()
        Clock.schedule_once(lambda _dt: self.pintar())

    def avanzar(self, _dt):
        """Un paso. Al cerrar la vuelta, evoluciona."""
        ahora = time.perf_counter()
        if self._ultimo is not None:
            self.intervalos.append(ahora - self._ultimo)
        self._ultimo = ahora

        self.sonando = self.mundo.subasta(self.paso)
        self.emitir(self.sonando)

        self.paso = (self.paso + 1) % self.mundo.columnas
        if self.paso == 0:
            # Evolucionar EN LA LINEA DE COMPAS, no a mitad de barrido: asi cada
            # generacion se oye entera una vez. La otra opcion —evolucionar bajo
            # la barra— es mas viva, pero ninguna generacion se llega a oir.
            self.mundo.evolucionar()
        self.pintar()

    def intervalo(self):
        return 60.0 / (self.bpm * 4)       # semicorcheas

    def jitter(self):
        """Reparto de la desviacion contra el intervalo pedido, en ms.

        Devuelve (n, mediana, p95, maximo) o None si aun no hay muestras.
        **Mediana y no media**: un solo tropiezo del sistema arrastra la media y
        no dice nada del comportamiento normal. El p95 es el que responde "cada
        cuanto se sale", y el maximo el peor caso, que es lo que se oye.
        """
        if len(self.intervalos) < 16:
            return None
        objetivo = self.intervalo()
        d = sorted(abs(i - objetivo) * 1000 for i in self.intervalos)
        n = len(d)
        return n, d[n // 2], d[min(n - 1, int(n * 0.95))], d[-1]

    def reiniciar_medicion(self):
        self.intervalos.clear()
        self._ultimo = None

    # -- dibujo -------------------------------------------------------------

    def pintar(self):
        lado, (ox, oy) = self.metrica()
        col_actual = (self.paso - 1) % self.mundo.columnas
        sonando = set(self.sonando)
        self.canvas.clear()
        with self.canvas:
            Color(*FONDO)
            Rectangle(pos=self.pos, size=self.size)
            for f in range(self.mundo.filas):
                for c in range(self.mundo.columnas):
                    if c == col_actual and f in sonando and self.corriendo:
                        Color(*SONANDO)
                    elif self.mundo.celdas[f][c]:
                        Color(*VIVA)
                    else:
                        Color(*MUERTA)
                    Rectangle(pos=(ox + c * lado + 1, oy + f * lado + 1),
                              size=(lado - 2, lado - 2))
            if self.corriendo:
                Color(*BARRA)
                Rectangle(pos=(ox + col_actual * lado, oy),
                          size=(lado, lado * self.mundo.filas))


class VidaApp(App):
    title = "Vida — secuenciador"

    def build(self):
        Window.clearcolor = FONDO
        raiz = BoxLayout(orientation="vertical")
        self.rejilla = Rejilla()
        self.i_figura = 1                       # empieza en `toad`, como el video
        #: `externo` = el paso lo manda el QY100. `armado` = la app esta lista y
        #: **esperando el `FA` del aparato**, que no es lo mismo que sonando.
        self.externo = False
        self.armado = False
        self.reloj = R.RelojExterno()

        barra = BoxLayout(size_hint_y=None, height=52, padding=6, spacing=6)
        self.b_tocar = self._boton("TOCAR", self.alternar)
        self.b_escala = self._boton(A.NOMBRES_ESCALA[0].upper(), self.cambiar_escala)
        self.b_figura = self._boton("SEMBRAR TOAD", self.sembrar)
        self.b_midi = self._boton("MIDI OFF", self.alternar_midi)
        self.b_canal = self._boton("CH 1", self.cambiar_canal)
        self.b_reporte = self._boton("REPORTE", self.escribir_reporte)
        self.b_reloj = self._boton("reloj: interno", self.alternar_reloj)
        for w in (self.b_tocar,
                  self._boton("EVOLVE", self.evolucionar_una),
                  self.b_escala, self.b_figura,
                  self._boton("RUIDO", self.rejilla.mundo.sembrar_ruido),
                  self._boton("LIMPIAR", self.limpiar),
                  self._boton("- BPM", lambda: self.cambiar_bpm(-4)),
                  self._boton("+ BPM", lambda: self.cambiar_bpm(4)),
                  self.b_midi, self.b_canal, self.b_reloj, self.b_reporte):
            barra.add_widget(w)

        self.estado = Label(size_hint_y=None, height=36, font_size=13,
                            halign="left", valign="middle",
                            color=(0.6, 0.66, 0.7, 1))
        self.estado.bind(size=lambda w, s: setattr(w, "text_size", s))

        raiz.add_widget(barra)
        raiz.add_widget(self.rejilla)
        raiz.add_widget(self.estado)
        Clock.schedule_interval(self.refrescar, 0.2)
        return raiz

    def _boton(self, texto, accion):
        b = Button(text=texto, font_size=13, background_color=GRIS)
        b.bind(on_release=lambda *_: (accion(), self.rejilla.pintar()))
        return b

    # -- controles ----------------------------------------------------------

    def alternar(self):
        """⚠️ Con el reloj EXTERNO este boton **arma**, no arranca.

        Quien arranca es el QY100 con su `FA`. Marcarlo como «tocando» al
        pulsarlo seria mentir durante el rato que va hasta que alguien le da
        play al aparato — el mismo criterio de la maqueta: se pinta lo que se
        sabe, no lo que se espera.
        """
        r = self.rejilla
        if r.corriendo or self.armado:
            Clock.unschedule(r.avanzar)
            r.corriendo = False
            self.armado = False
            r.sonando = []
            r.salida.apagar_todo()
            r.reiniciar_medicion()
            self.b_tocar.text = "TOCAR"
        elif self.externo:
            self.armado = True
            self.b_tocar.text = "ARMADO"
        else:
            r.corriendo = True
            r.reiniciar_medicion()
            Clock.schedule_interval(r.avanzar, r.intervalo())
            self.b_tocar.text = "PARAR"

    def alternar_reloj(self):
        """Interno (Kivy genera el tiempo) contra externo (el QY100 lo manda).

        `[M]` **El externo es el bueno para tocar.** Con Kivy de maestro su
        tambaleo —2,1 ms de mediana, 8,4 de maximo— es tambaleo del groove: a
        120 BPM un tic son 20,8 ms, o sea el 40% de un tic. Escuchando, esa
        misma desviacion es latencia constante, que no se oye igual.

        El interno se queda porque **sirve para probar sin aparato** y porque
        permite comparar los dos, que es para lo que este programa se mide.
        """
        r = self.rejilla
        if r.corriendo or self.armado:
            self.alternar()
        self.externo = not self.externo
        if self.externo:
            if not self.reloj.abrir():
                self.externo = False
                self.b_reloj.text = "reloj: interno"
                return
            self.reloj.al_paso = r.avanzar_externo
            self.reloj.al_transporte = self._transporte
        else:
            self.reloj.cerrar()
        self.b_reloj.text = "reloj: %s" % ("QY100" if self.externo else "interno")

    def _transporte(self, que):
        """Lo manda el hilo MIDI: se agenda todo lo que toque la interfaz."""
        def _(_dt):
            r = self.rejilla
            if que in ("start", "continue"):
                if not self.armado:
                    return
                if que == "start":
                    r.paso = 0
                r.corriendo = True
                self.b_tocar.text = "PARAR"
            else:
                r.corriendo = False
                r.sonando = []
                r.salida.apagar_todo()
                self.b_tocar.text = "ARMADO" if self.armado else "TOCAR"
            r.pintar()
        Clock.schedule_once(_)

    def alternar_midi(self):
        s = self.rejilla.salida
        if s.abierta:
            s.cerrar()
            self.b_midi.text = "MIDI OFF"
        elif s.abrir():
            self.b_midi.text = "MIDI " + s.nombre[:10].upper()
        else:
            self.b_midi.text = "SIN PUERTO"

    def cambiar_canal(self):
        s = self.rejilla.salida
        s.apagar_todo()
        s.canal = (s.canal + 1) % 16
        self.b_canal.text = "CH %d" % (s.canal + 1)

    def evolucionar_una(self):
        self.rejilla.mundo.evolucionar()

    def limpiar(self):
        self.rejilla.mundo.limpiar()
        self.rejilla.sonando = []

    def cambiar_escala(self):
        m = self.rejilla.mundo
        m.escala = (m.escala + 1) % len(A.NOMBRES_ESCALA)
        self.b_escala.text = A.NOMBRES_ESCALA[m.escala].upper()

    def sembrar(self):
        self.rejilla.mundo.sembrar_figura(A.NOMBRES_FIGURA[self.i_figura])
        self.i_figura = (self.i_figura + 1) % len(A.NOMBRES_FIGURA)
        self.b_figura.text = "SEMBRAR " + A.NOMBRES_FIGURA[self.i_figura].upper()

    def cambiar_bpm(self, d):
        r = self.rejilla
        r.bpm = max(40, min(220, r.bpm + d))
        if r.corriendo:                       # reprogramar al nuevo intervalo
            Clock.unschedule(r.avanzar)
            r.reiniciar_medicion()
            Clock.schedule_interval(r.avanzar, r.intervalo())

    def escribir_reporte(self):
        """Vuelca el reparto entero a `medicion-reloj.txt`.

        Existe porque el numero de la barra de estado, aunque ya no sea una media
        movil, sigue siendo una lectura de pantalla. Un fichero con el histograma
        y el n se puede citar en un documento y se puede volver a generar.
        """
        r = self.rejilla
        if len(r.intervalos) < 16:
            self.b_reporte.text = "POCOS DATOS"
            return
        objetivo = r.intervalo() * 1000
        d = sorted(abs(i - objetivo) * 1000 for i in r.intervalos)
        n = len(d)
        lineas = [
            "Medicion del reloj de Kivy — %s" % self.title,
            "",
            "  bpm            %d  (semicorchea = %.2f ms)" % (r.bpm, objetivo),
            "  pasos medidos  %d" % n,
            "  minimo         %.2f ms" % d[0],
            "  mediana        %.2f ms" % d[n // 2],
            "  p95            %.2f ms" % d[min(n - 1, int(n * 0.95))],
            "  maximo         %.2f ms" % d[-1],
            "",
            "  Reparto (ms de desviacion contra el intervalo pedido):",
        ]
        cortes = [1, 2, 4, 6, 8, 10, 15, 20, 1e9]
        prev = 0.0
        for c in cortes:
            cuantos = sum(1 for x in d if prev <= x < c)
            etiq = "%4.0f-%-4.0f" % (prev, c) if c < 1e9 else ">%-8.0f" % prev
            barra = "#" * int(60 * cuantos / n)
            lineas.append("    %s %5d  %4.1f%%  %s"
                          % (etiq, cuantos, 100 * cuantos / n, barra))
            prev = c
        lineas += [
            "",
            "  Para comparar: un mensaje MIDI de 3 bytes son 0.96 ms en el cable,",
            "  y cada paso manda hasta %d note-off + %d note-on = %.1f ms solo en" %
            (A.MAX_VOCES, A.MAX_VOCES, 2 * A.MAX_VOCES * 0.96),
            "  salir. El umbral de microtiempo ronda los 6 ms; la asincronia de un",
            "  baterista humano entre bombo, caja y charles, 19-24 ms.",
            "",
        ]
        texto = "\n".join(lineas)
        with open("medicion-reloj.txt", "w") as f:
            f.write(texto)
        print(texto)
        self.b_reporte.text = "ESCRITO n=%d" % n

    def on_stop(self):
        self.reloj.cerrar()
        """Sin esto queda una nota colgada sonando en el QY100 hasta apagarlo."""
        self.rejilla.salida.cerrar()

    def refrescar(self, _dt):
        r, m = self.rejilla, self.rejilla.mundo
        j = r.jitter()
        pedido = r.intervalo() * 1000
        reloj = ("reloj —" if j is None else
                 "reloj %.1f ms · n=%d · mediana %.1f · p95 %.1f · max %.1f"
                 % (pedido, j[0], j[1], j[2], j[3]))
        notas = " ".join(str(m.nota_de(f)) for f in r.sonando) or "—"
        if m.periodo:
            aviso = "    ⚠ CICLO DE %d COMPAS%s — siembra algo" % (
                m.periodo, "" if m.periodo == 1 else "ES")
        elif m.rejilla_quieta:
            aviso = "    ⚠ QUIETA — siembra algo"
        elif m.rala:
            aviso = "    · rala, %d/%d pasos suenan" % (m.pasos_con_nota, m.columnas)
        else:
            aviso = ""
        if r.salida.abierta:
            aviso += "    midi %s ch%d · %d notas" % (
                r.salida.nombre, r.salida.canal + 1, r.salida.enviados)
        elif r.salida.error:
            aviso += "    midi: " + r.salida.error
        self.estado.text = (
            "  %d bpm · paso %2d/%d · gen %d · %d vivas · %d voces    notas %s"
            "        %s%s"
            % (r.bpm, (r.paso if r.paso else m.columnas), m.columnas,
               m.generacion, m.vivas(), len(r.sonando), notas, reloj, aviso)
        )


if __name__ == "__main__":
    VidaApp().run()
