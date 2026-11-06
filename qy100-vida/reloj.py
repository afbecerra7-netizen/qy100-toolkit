"""El reloj externo: el paso lo manda el QY100, no Kivy.

Aparte de la interfaz **a proposito**, igual que `automata.py` y `salida.py`:
esto se prueba sin pantalla.

**Por que se invirtio la maestria.** Con Kivy generando el tiempo, su tambaleo
—medido en este mismo programa: **2,1 ms de mediana y 8,4 de maximo**— es
tambaleo del groove. A 120 BPM un tic de reloj MIDI son 20,8 ms, asi que 8,4 es
el **40% de un tic**: el tempo del aparato se volveria el pulso de la tableta.

Escuchando, esa misma desviacion pasa a ser **latencia de respuesta** en vez de
error de tempo. Una latencia constante no se oye como tambaleo; un tempo que
tiembla si. Y de paso el generador queda enganchado al material del QY100: el
Game of Life corre **encima** de un patron, no al lado.

    F8   timing clock, 24 por negra
    FA   start      -> vuelve al paso 0
    FB   continue   -> sigue donde iba
    FC   stop

⚠️ **Hace falta `MIDI CONTROL` en `Out` o `In/Out`** para que el QY100
transmita. Con `Off` no llega ni un `F8` y el silencio se lee igual que «el
reloj externo no funciona». Ver `qy100-syx/ajustar_midi_control.py`.

⚠️ **Y `MIDI SYNC` en `Internal`**, que es lo contrario de lo que suena: es el
QY100 el que manda el reloj, asi que su reloj tiene que ser el suyo propio. Con
`External` se queda esperando un reloj que nadie manda y no arranca.
"""

import time

try:
    import mido
except ImportError:                       # pragma: no cover
    mido = None

PPQN = 24                    # tics de reloj MIDI por negra, fijo en el estandar
POR_SEMICORCHEA = PPQN // 4  # 6


class RelojExterno:
    """Cuenta `F8` y avisa cada `por_paso` tics.

    **Lo que NO hace es medir el tiempo**, y ese es el punto: no hay `sleep`, ni
    intervalo, ni compensacion de deriva. Solo cuenta. Toda la precision la pone
    el aparato, que la tiene.
    """

    def __init__(self, por_paso=POR_SEMICORCHEA):
        self.por_paso = por_paso
        self.puerto = None
        self.nombre = None
        self.error = None
        self.tics = 0
        self.corriendo = False
        self.al_paso = None       # se llama en el HILO MIDI
        self.al_transporte = None
        #: Llegada de cada tic, para poder comparar con el reloj interno. El
        #: programa se sigue midiendo a si mismo; solo cambia que ahora mide al
        #: aparato en vez de a Kivy.
        self.llegadas = []
        self._ultimo = None

    @staticmethod
    def puertos():
        if mido is None:
            return []
        try:
            return mido.get_input_names()
        except Exception:
            return []

    def abrir(self, nombre=None):
        self.cerrar()
        if mido is None:
            self.error = "falta mido"
            return False
        libres = self.puertos()
        if not libres:
            self.error = "no hay puertos de entrada"
            return False
        self.nombre = nombre or libres[0]
        try:
            self.puerto = mido.open_input(self.nombre, callback=self._entra)
            self.error = None
            return True
        except Exception as e:
            self.error = str(e)
            return False

    def cerrar(self):
        try:
            if self.puerto:
                self.puerto.close()
        except Exception:
            pass
        self.puerto = None
        self.corriendo = False

    # -- lo que llega ------------------------------------------------------

    def _entra(self, msg):
        t = msg.type
        if t == "clock":
            ahora = time.perf_counter()
            if self._ultimo is not None:
                self.llegadas.append(ahora - self._ultimo)
            self._ultimo = ahora
            if not self.corriendo:
                return
            self.tics += 1
            if self.tics % self.por_paso == 0 and self.al_paso:
                self.al_paso()
        elif t == "start":
            # **`FA` vuelve al principio y `FB` no.** Confundirlos es el fallo
            # clasico: el generador reengancharia a destiempo y sonaria como si
            # el reloj fuera malo.
            self.tics = 0
            self.corriendo = True
            self._avisar("start")
        elif t == "continue":
            self.corriendo = True
            self._avisar("continue")
        elif t == "stop":
            self.corriendo = False
            self._avisar("stop")

    def _avisar(self, que):
        if self.al_transporte:
            self.al_transporte(que)

    # -- medida ------------------------------------------------------------

    def bpm(self):
        """BPM deducido de los ultimos tics, o `None` si aun no hay bastantes.

        **Deducido, no leido**: el QY100 no dice su tempo por MIDI. Se calcula
        del intervalo entre tics, asi que hereda su ruido — sirve para mostrar,
        no para sincronizar nada.
        """
        if len(self.llegadas) < PPQN:
            return None
        ultimos = self.llegadas[-PPQN:]
        medio = sum(ultimos) / len(ultimos)
        return 60.0 / (medio * PPQN) if medio > 0 else None

    def jitter(self):
        """(n, mediana, p95, max) en ms del intervalo entre tics del APARATO."""
        if len(self.llegadas) < 24:
            return None
        d = sorted(self.llegadas)
        medio = sum(d) / len(d)
        ms = sorted(abs(x - medio) * 1000 for x in d)
        return (len(ms), ms[len(ms) // 2], ms[int(len(ms) * 0.95)], ms[-1])

    def reiniciar_medicion(self):
        self.llegadas.clear()
        self._ultimo = None
