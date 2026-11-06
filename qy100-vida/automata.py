"""El automata y el mapeo a notas, **sin una linea de Kivy**.

Separado a proposito: la interfaz no se puede probar sin pantalla, y esto si.
La regla de la casa aplica igual aqui — un test que no puede fallar es un
comentario, asi que `test_automata.py` mete cada defecto conocido de vuelta.

La rejilla es un piano roll: **columna = tiempo, fila = grado de la escala.**
"""

from collections import deque

COLUMNAS = 16          # pasos por vuelta; una vuelta = un compas de 16
FILAS = 16             # grados de la escala, de abajo hacia arriba

#: Cuantas notas pueden sonar a la vez. **Lo unico que se trajo de Terrario
#: Sonoro**, y resuelve un problema que esta rejilla tiene seguro: una columna
#: con doce celulas vivas le manda un acorde de doce notas al QY100.
MAX_VOCES = 4

#: Life no suele morir: se asienta en *still lifes* — las mismas notas para
#: siempre, sin avisar. Los osciladores en cambio son buenisimos (un blinker es
#: literalmente un riff), asi que hay que distinguirlos.
#:
#: **La primera version de esto estaba mal razonada** y el test lo cazo: guardaba
#: las ultimas 6 huellas y marcaba estancada si la nueva aparecia entre ellas.
#: Eso hace exactamente lo contrario de lo que se queria — un blinker de periodo
#: 2 repite dentro de esas 6 y quedaba declarado muerto.
#:
#: Lo correcto es mas simple: **un still life es identico a la generacion
#: INMEDIATAMENTE anterior; un oscilador vuelve a un estado previo pero nunca al
#: ultimo.** Y como Life es determinista, si no cambio una vez no cambia nunca:
#: una sola comparacion basta. Tambien cuenta como estancada la rejilla vacia.
#:
#: **Y eso todavia mide la unidad equivocada.** Visto en el aparato el 2026-08-15:
#: la rejilla llego a la generacion 18 con dos bloques 2x2 y un blinker, o sea
#: musicalmente muerta — pero como el blinker cambia la huella cada generacion,
#: nada se declaraba estancado. La rejilla se movia y la musica no.
#:
#: Por eso ahora se compara **el compas de notas**, no la rejilla: lo que
#: produciria una vuelta entera de la barra.
#:
#: **Y ahi la comparacion se invierte, que es la ironia de todo esto.** La
#: configuracion real que se midio —dos bloques y un blinker, 11 vivas— no estaba
#: muerta ni rala: alternaba 5 y 7 columnas sonando con 3 cambios por vuelta, o
#: sea **un loop de dos compases**. Para la REJILLA comparar contra las ultimas N
#: esta mal, porque marca un blinker sano. Para la MUSICA esta bien, porque un
#: ciclo corto ES el final: la premisa del instrumento es no volver al mismo
#: sitio. Misma comparacion, dos unidades, dos respuestas opuestas.

#: Cuantos compases atras se busca el ciclo. Con 8 se detecta cualquier periodo
#: de 1 a 8 vueltas, que cubre de sobra lo que Life produce al converger.
COMPASES_RECORDADOS = 8

#: Fraccion minima de pasos con nota antes de avisar que la rejilla esta rala.
#: Con 11 celulas vivas en 16 columnas la mayoria de las columnas quedan mudas, y
#: eso no es estancamiento —cambia— pero tampoco es musica.
DENSIDAD_MINIMA = 0.25

#: Semitonos sobre la tonica. Las filas mapean a GRADOS, no a semitonos: con
#: mapeo cromatico Life da ruido atonal; con escala suena a musica desde la
#: primera generacion. Es la diferencia entre demo e instrumento.
ESCALAS = {
    "pentatonica menor": [0, 3, 5, 7, 10],
    "menor natural": [0, 2, 3, 5, 7, 8, 10],
    "mayor": [0, 2, 4, 5, 7, 9, 11],
    "dorico": [0, 2, 3, 5, 7, 9, 10],
    "mixolidio": [0, 2, 4, 5, 7, 9, 10],
}
NOMBRES_ESCALA = list(ESCALAS)

#: `C3` en la convencion del QY100. **Ojo con esto**: el manual del MTD-1024 usa
#: `C4 = 60` y el QY100 usa `C3 = 60`. Los numeros de nota no son ambiguos; los
#: nombres si. Aqui siempre se trabaja con numeros.
NOTA_BASE = 48

#: Las figuras del juego, con sus nombres de siempre. El video de referencia
#: sembraba con `STAMP-TOAD`, y el "glide" de su titulo son los *gliders*.
FIGURAS = {
    "glider":  [(0, 1), (1, 2), (2, 0), (2, 1), (2, 2)],
    "toad":    [(1, 1), (1, 2), (1, 3), (2, 0), (2, 1), (2, 2)],
    "blinker": [(1, 0), (1, 1), (1, 2)],
    "beacon":  [(0, 0), (0, 1), (1, 0), (3, 3), (2, 3), (3, 2)],
}
NOMBRES_FIGURA = list(FIGURAS)


class Automata:
    """Rejilla de Conway leida como piano roll."""

    def __init__(self, filas=FILAS, columnas=COLUMNAS, semilla=None):
        self.filas = filas
        self.columnas = columnas
        self.celdas = [[False] * columnas for _ in range(filas)]
        self.generacion = 0
        self.escala = 0
        self._anterior = None
        self._compases = deque(maxlen=COMPASES_RECORDADOS)
        self.rejilla_quieta = False
        self.estancada = False
        self.rala = False
        self.periodo = 0          # en cuantos compases se cierra el ciclo
        self.pasos_con_nota = 0
        import random
        self._rnd = random.Random(semilla)

    # -- el automata --------------------------------------------------------

    def vecinos(self, fila, col):
        """Toroidal: los bordes se pegan, asi los gliders no se caen del mundo."""
        n = 0
        for df in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if df or dc:
                    n += self.celdas[(fila + df) % self.filas][(col + dc) % self.columnas]
        return n

    def evolucionar(self):
        """Una generacion. B3/S23, las reglas de siempre."""
        nueva = [[False] * self.columnas for _ in range(self.filas)]
        for f in range(self.filas):
            for c in range(self.columnas):
                n = self.vecinos(f, c)
                nueva[f][c] = n == 3 or (self.celdas[f][c] and n == 2)
        self.celdas = nueva
        self.generacion += 1

        huella = self.huella()
        # Still life o muerte de la REJILLA. Un oscilador vuelve a un estado
        # previo pero nunca al inmediatamente anterior, asi que no cae aqui — y
        # no debe: un blinker es un riff, no un problema.
        # Dos senales SEPARADAS, y hay que poder mirarlas por separado: cada una
        # tiene su comprobacion y cada una puede fallar sola.
        self.rejilla_quieta = huella == self._anterior or self.vivas() == 0
        self._anterior = huella
        self.estancada = self.rejilla_quieta or self.musica_quieta()
        return self.estancada

    def huella(self):
        return tuple(tuple(f) for f in self.celdas)

    def alternar(self, fila, col):
        self.celdas[fila][col] = not self.celdas[fila][col]
        self._olvidar()

    def encender(self, fila, col):
        self.celdas[fila][col] = True
        self._olvidar()

    # -- estancamiento musical ----------------------------------------------

    def compas(self, max_voces=None):
        """Las notas que produciria una vuelta entera de la barra.

        Es la unidad correcta para preguntar si esta pasando algo: la rejilla
        puede moverse mientras la musica no cambia.
        """
        mv = MAX_VOCES if max_voces is None else max_voces
        return tuple(tuple(self.notas_de_columna(c, mv))
                     for c in range(self.columnas))

    def musica_quieta(self, max_voces=None):
        """¿La vuelta que viene suena igual que la anterior? ¿O casi no suena?

        Dos senales distintas, y las dos importan mientras se toca:

        - **estancada**: el compas se repite identico. Cubre los still lifes y
          tambien el caso que se vio en el aparato — un blinker moviendose en
          una zona que no cambia ninguna nota.
        - **rala**: cambia, pero suenan tan pocos pasos que no hay musica.

        No se compara contra las ultimas N sino **contra la anterior**, por la
        misma razon que arriba: una alternancia de dos compases es un groove, no
        un problema.
        """
        c = self.compas(max_voces)
        self.pasos_con_nota = sum(1 for paso in c if paso)
        self.rala = self.pasos_con_nota < self.columnas * DENSIDAD_MINIMA
        # Buscar el compas entre los ultimos: si aparece, la musica cerro un
        # ciclo y `periodo` dice de cuantas vueltas.
        self.periodo = 0
        for atras, viejo in enumerate(reversed(self._compases), start=1):
            if c == viejo:
                self.periodo = atras
                break
        self._compases.append(c)
        return self.periodo > 0

    def _olvidar(self):
        """Cualquier intervencion humana reinicia la deteccion: la rejilla ya
        no es la que se estaba repitiendo."""
        self._anterior = None
        self._compases.clear()
        self.rejilla_quieta = False
        self.estancada = False
        self.rala = False
        self.periodo = 0

    def sembrar_ruido(self, densidad=0.28):
        self.celdas = [[self._rnd.random() < densidad for _ in range(self.columnas)]
                       for _ in range(self.filas)]
        self.generacion = 0
        self._olvidar()

    def sembrar_figura(self, nombre, fila=None, col=None):
        """Siembra una figura conocida sin borrar lo que ya hay."""
        f0 = self._rnd.randrange(self.filas) if fila is None else fila
        c0 = self._rnd.randrange(self.columnas) if col is None else col
        for df, dc in FIGURAS[nombre]:
            self.celdas[(f0 + df) % self.filas][(c0 + dc) % self.columnas] = True
        self._olvidar()

    def limpiar(self):
        self.celdas = [[False] * self.columnas for _ in range(self.filas)]
        self.generacion = 0
        self._olvidar()

    def vivas(self):
        return sum(sum(f) for f in self.celdas)

    # -- el secuenciador ----------------------------------------------------

    def nota_de(self, fila):
        """Fila -> numero de nota MIDI, por grados de la escala y su octava."""
        grados = ESCALAS[NOMBRES_ESCALA[self.escala]]
        octava, grado = divmod(fila, len(grados))
        return NOTA_BASE + 12 * octava + grados[grado]

    def subasta(self, col, max_voces=MAX_VOCES):
        """Que celulas de la columna suenan, con tope de voces.

        Prioridad = vecinos vivos, o sea **estabilidad**: una celula rodeada
        pesa mas que una que va a morir el proximo paso. Desempata la mas grave,
        que es la que sostiene el acorde.

        Devuelve las filas ordenadas de grave a agudo, para que el orden de
        salida no dependa del de la subasta.
        """
        vivas = [(self.vecinos(f, col), -f, f) for f in range(self.filas)
                 if self.celdas[f][col]]
        vivas.sort(reverse=True)
        return sorted(f for _, _, f in vivas[:max_voces])

    def notas_de_columna(self, col, max_voces=MAX_VOCES):
        return [self.nota_de(f) for f in self.subasta(col, max_voces)]
