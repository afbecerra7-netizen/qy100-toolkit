"""La salida MIDI, aislada del automata y de la interfaz.

Aparte a proposito: asi `automata.py` sigue probandose sin aparato, y esto se
puede probar sin pantalla.

**Regla de la casa que aplica entera aqui**: que un envio se reporte exitoso no
prueba nada. `mido` no tiene forma de saber si el QY100 recibio; lo unico que
prueba estado es oirlo o releerlo. Por eso esta clase no dice "enviado" en
ninguna parte — cuenta lo que intento y ya.
"""

try:
    import mido
except ImportError:                       # pragma: no cover
    mido = None

VELOCIDAD_MIN = 48
VELOCIDAD_MAX = 118


class Salida:
    """Un puerto y las notas que estan sonando ahora.

    Lleva la cuenta de lo encendido para poder apagarlo: una nota colgada en el
    QY100 se queda sonando hasta que alguien lo apaga, y en un prototipo que se
    reinicia veinte veces eso pasa seguro.
    """

    def __init__(self, canal=0):
        self.puerto = None
        self.nombre = None
        self.canal = canal
        self.encendidas = []
        self.enviados = 0
        self.error = None

    # -- conexion -----------------------------------------------------------

    @staticmethod
    def puertos():
        if mido is None:
            return []
        try:
            return mido.get_output_names()
        except Exception:
            return []

    def abrir(self, nombre=None):
        """Abre el primer puerto disponible, o el que se le pida."""
        self.cerrar()
        if mido is None:
            self.error = "mido no esta instalado"
            return False
        libres = self.puertos()
        if not libres:
            self.error = "no hay puertos MIDI"
            return False
        nombre = nombre or libres[0]
        try:
            self.puerto = mido.open_output(nombre)
        except Exception as e:                       # puerto ocupado, etc.
            self.error = str(e)
            return False
        self.nombre = nombre
        self.error = None
        return True

    def cerrar(self):
        self.apagar_todo()
        if self.puerto is not None:
            try:
                self.puerto.close()
            except Exception:
                pass
        self.puerto = None
        self.nombre = None

    @property
    def abierta(self):
        return self.puerto is not None

    # -- notas --------------------------------------------------------------

    def tocar(self, notas, pesos=None):
        """Apaga lo anterior y enciende lo nuevo. Un paso de secuenciador.

        `pesos` son los vecinos vivos de cada celula, de 0 a 8: la celula mas
        arraigada suena mas fuerte. **Y esto no es adorno** — el MTD-1024
        convierte la velocity en intensidad de luz con `DMX = MIDI x 2.01`, asi
        que la dinamica que se escriba aqui es la que despues sale por las
        luces sin escribir un dato nuevo.
        """
        if self.puerto is None:
            return
        for n in self.encendidas:
            self.puerto.send(mido.Message("note_off", note=n,
                                          channel=self.canal, velocity=0))
        self.encendidas = []
        pesos = pesos or [4] * len(notas)
        for n, p in zip(notas, pesos):
            vel = VELOCIDAD_MIN + int(
                (VELOCIDAD_MAX - VELOCIDAD_MIN) * min(p, 8) / 8)
            self.puerto.send(mido.Message("note_on", note=n,
                                          channel=self.canal, velocity=vel))
            self.encendidas.append(n)
            self.enviados += 1

    def apagar_todo(self):
        """Apaga nota por nota, y ademas manda `all notes off` (CC 123).

        Las dos cosas: el CC 123 es lo correcto, pero no todos los aparatos lo
        obedecen y el QY100 no esta comprobado en eso. Apagar una por una si
        funciona siempre.
        """
        if self.puerto is None:
            return
        for n in self.encendidas:
            try:
                self.puerto.send(mido.Message("note_off", note=n,
                                              channel=self.canal, velocity=0))
            except Exception:
                break
        self.encendidas = []
        try:
            self.puerto.send(mido.Message("control_change", channel=self.canal,
                                          control=123, value=0))
        except Exception:
            pass
