"""El QY100 visto desde la app: lo que se le puede mandar y lo que cuenta de si.

Aparte de la interfaz **a proposito**, que es como esta armado `qy100-vida`: asi
esto se prueba sin pantalla y sin aparato, y la maqueta no lleva protocolo
adentro.

Todo lo de aqui esta medido. Las referencias, para que se pueda auditar:

    SECTION CONTROL   F0 43 7E 00 ss dd F7      service manual p. 58
                      medido 2026-08-16 contra el patron 1 sonando
                      seis secciones, alineadas al compas por el aparato
    XG param change   F0 43 10 4C aa bb cc dd F7
                      mapeado por Shea Kennedy (doffu0000) escuchando el
                      puerto mientras movia el panel, agosto 2026
    SONG SELECT       F3 nn                     service manual p. 57
    SPP               F2 ll mm — solo lo emite SONG mode

⚠️ **Regla de la casa, y aqui aplica entera**: que un envio se reporte exitoso
no prueba nada. Esta clase **no dice «enviado» en ninguna parte** — cuenta lo
que intento. Lo unico que prueba estado es oirlo o releerlo.
"""

import os
import sys
import time

try:
    import mido
except ImportError:                       # pragma: no cover
    mido = None

# **El codec no se duplica: se importa del proyecto que ya lo tiene probado.**
# `qy100-syx` lleva 182 comprobaciones y las reglas de escritura aprendidas a
# golpes; copiar aqui 2.100 lineas seria garantizar que las dos copias se
# separen. Comparten interprete (3.9), asi que basta con la ruta.
_SYX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "qy100-syx")
if _SYX not in sys.path:
    sys.path.insert(0, _SYX)

_VIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "qy100-vida")
if _VIDA not in sys.path:
    sys.path.insert(0, _VIDA)

try:
    import automata as AU
except ImportError:                       # pragma: no cover
    AU = None

try:
    from qy100syx import patternfmt as F
    from qy100syx import protocol as PR
    from qy100syx import transfer
except ImportError:                       # pragma: no cover
    F = PR = transfer = None

# --------------------------------------------------------------- secciones

#: `ss` = indice + 0x08. `Blank` (0x0E) esta en el mapa del manual pero **se
#: ignoro en los dos estados probados** el 2026-08-16 — detras del `Ending` y
#: sobre un `Main A` sonando. Dos estados no son todos, asi que se conserva la
#: constante y se deja fuera de la lista que la interfaz ofrece.
SECCIONES = ["Intro", "Main A", "Main B", "Fill AB", "Fill BA", "Ending"]
SECCION_BASE = 0x08
BLANK = 0x0E

#: El manual dice «dd=on» y **nunca dice cuanto vale on**. 0x7F es el «on» de
#: Yamaha en el resto del protocolo, y es el que se midio funcionando.
ON = 0x7F

# ---------------------------------------------------------------- efectos

#: Familia de efecto, byte alto de `02 01 40`. Del mapeo de Shea, que a su vez
#: coincide con la especificacion publica XG — tiene sentido, esta familia de
#: direcciones **no es especifica del QY100**.
#:
#: ⚠️ El corte en 0x40 es real y estructural: `00`-`3F` es el bloque de efecto de
#: sistema, cuyo bypass se llama `No Effect`, y `40`-`7F` el de insercion, cuyo
#: bypass es `Thru`. Un barrido completo de los ~100 valores sin mapear no
#: encontro nada oculto: cada bloque cae a su propio default.
EFECTOS = [
    (0x00, "No Effect"), (0x01, "Hall"), (0x02, "Room"), (0x03, "Stage"),
    (0x04, "Plate"), (0x07, "Echo"), (0x09, "Early Ref"),
    (0x40, "Thru"), (0x41, "Chorus"), (0x42, "Celeste"), (0x43, "Flanger"),
    (0x45, "Rotary SP"), (0x46, "Tremolo"), (0x47, "Auto Pan"),
    (0x48, "Phaser"), (0x49, "Distortion"), (0x4A, "Overdrive"),
    (0x4E, "Auto Wah"),
]

#: `[M]` **Este bloque entero es el de VARIATION, y eso cambia lo que significa.**
#: Data List p. 59, contra el mapeo de Shea, que lo etiqueto como si fueran los
#: efectos generales:
#:
#:     40  Variation Type        2 bytes (MSB tipo, LSB variante)
#:     42  Variation Param 1     2 bytes · «depends on vari. type»
#:     44..54  Param 2..10
#:     56  Variation Return
#:     58  Send Variation To Rev.      <- su «Reverb Send»
#:     59  Send Variation To Cho.      <- su «Chorus Send»
#:     5A  Variation Connection  00..01   0:insertion, 1:system
#:     5B  Variation Part        part1..32 (0..31), off (127)   default 7F
#:
#: Tres consecuencias, y ninguna es cosmetica:
#:
#: 1. **Los parametros 1-5 no son «Reverb Time, Diffusion, HPF...»** — son
#:    Param 1..5, y el Data List dice literalmente *depends on vari. type*. Shea
#:    los midio bajo Hall 1 y dejo abierto si significan lo mismo con otro tipo.
#:    **La respuesta esta impresa: no.**
#: 2. **`5A` si es un parametro real.** Shea le mando `0x7F` y concluyo que no
#:    existia o no estaba enrutado. Su rango es `00..01`: probo fuera de rango.
#:    Es la leccion del barrido parcial de este proyecto, al reves.
#: 3. ⚠️ **`Variation Part` vale `7F` (off) de fabrica.** Si nadie asigno una
#:    parte, cambiar el tipo **no se oye**, y ese silencio se lee igual que «no
#:    funciona». Por eso la hoja lo expone en vez de esconderlo.
#:
#: **Y los efectos por canal son otros.** Reverb, chorus y variation tienen un
#: send por canal —`CC 91`, `CC 93`, `CC 94`— que es lo que quiere un mezclador.
#: Este bloque es UN efecto, no dieciseis.
DIR_EFECTO = (0x02, 0x01, 0x40)
DIR_PARTE = (0x02, 0x01, 0x5B)
DIR_CONEXION = (0x02, 0x01, 0x5A)

#: (direccion, nombre, tope, bytes). El tamano importa: mandar un byte a un
#: parametro de dos **no es un valor pequeno, es otro mensaje**.
PARAMETROS = [
    ((0x02, 0x01, 0x58), "Send Var -> Reverb", 0x7F, 1),
    ((0x02, 0x01, 0x59), "Send Var -> Chorus", 0x7F, 1),
    ((0x02, 0x01, 0x56), "Variation Return",   0x7F, 1),
    ((0x02, 0x01, 0x42), "Variation Param 1",  0x7F, 2),
    ((0x02, 0x01, 0x44), "Variation Param 2",  0x7F, 2),
    ((0x02, 0x01, 0x46), "Variation Param 3",  0x7F, 2),
    ((0x02, 0x01, 0x48), "Variation Param 4",  0x7F, 2),
    ((0x02, 0x01, 0x4A), "Variation Param 5",  0x7F, 2),
]

#: `[M]` Comprobados en las dos direcciones por Shea: el tipo, el `58` y el `42`.
#: Los demas se asumen por familia, **y eso es una suposicion** que la hoja marca.
BIDIRECCIONALES = {DIR_EFECTO, (0x02, 0x01, 0x58), (0x02, 0x01, 0x42)}

#: `[M]` Los envios por canal, **contra el Data List del QY100** y no por
#: analogia con XG. En modo cancion son EN VIVO: pista n = canal n, medido el
#: 2026-08-16 barriendo un canal, luego otro, y luego los dieciseis en cascada.
#:
#: ⚠️ El `94` trae condicion impresa: *«Only when Connection = 1 (System)»*.
CC_ENVIOS = [(7, "Volumen"), (10, "Pan"), (91, "Reverb"), (93, "Chorus"),
             (94, "Variation")]

#: `[M]` **`DRY` no tiene control change** — no esta en la lista del Data List.
#: Se alcanza por el `Dry Level` del bloque Multi Part de XG, `08 nn 11`, medido
#: el 2026-08-16. **Y eso identifica una direccion que Shea capturo sin
#: explicar**: su rafaga de Undo/Redo lleva `08 0N 11` por canal, anotada como
#: sin decodificar.
def msg_dry(parte: int, valor: int) -> bytes:
    return msg_xg((0x08, parte & 0x0F, 0x11), valor)


def msg_seccion(indice: int, on: int = ON) -> bytes:
    """`F0 43 7E 00 ss dd F7`. Otra familia: el byte 3 es `7E`, «Style»."""
    if not 0 <= indice < len(SECCIONES):
        raise ValueError("seccion fuera de rango: %d" % indice)
    return bytes([0xF0, 0x43, 0x7E, 0x00, SECCION_BASE + indice, on, 0xF7])


def msg_xg(addr, valor, dev: int = 0) -> bytes:
    """`F0 43 1n 4C aa bb cc dd.. F7`. Sin checksum: es cambio de parametro.

    ⚠️ **`valor` puede ser varios bytes, y eso no es un detalle.** En este bloque
    `40` y `42..54` miden **2 bytes** (MSB, LSB) segun el Data List. La primera
    version de esto mandaba siempre uno — no es «un valor mas pequeno», es un
    mensaje distinto, de largo distinto, y el aparato lo puede tomar como otra
    cosa o descartarlo. Se paso por alto porque un byte «funcionaba» en los
    sends, que si son de uno.
    """
    a, b, c = addr
    datos = [valor & 0x7F] if isinstance(valor, int) else [v & 0x7F for v in valor]
    return bytes([0xF0, 0x43, 0x10 | (dev & 0x0F), 0x4C, a, b, c] +
                 datos + [0xF7])


class Aparato:
    """Un puerto de ida, uno de vuelta, y lo poco que el QY100 cuenta de si.

    **Lo que el aparato NO dice, y por que hay tan poco estado aqui:** medido el
    2026-08-16, navegar sus menus no emite un solo SysEx. Asi que la app no
    puede leer en que pantalla esta, ni que voz tiene puesta, ni —lo que mas
    duele— si esta en modo song o pattern. Lo unico que llega solo es un Song
    Position Pointer al entrar a SONG, y de ahi sale `self.modo`.
    """

    def __init__(self):
        self.salida = None
        self.entrada = None
        self.nombre = None
        self.modo = None            # "song" | "pattern" | None (no se sabe aun)
        self.seccion = None         # lo ULTIMO QUE PEDIMOS, no lo que suena
        self.intentos = 0
        self.error = None
        self.ultimo = None          # ultimo mensaje mandado, para la pantalla
        #: `[D]` **Lo que la app CREE** — no lo que pasa. El QY100 no avisa que
        #: paro, y alguien puede pararlo desde el panel. Se pinta como creencia.
        self.tocando = False
        #: `[M]` **El reloj del QY100, contado y no medido.** 24 `F8` por negra,
        #: uno de cada 6 es una semicorchea. Aqui no hay `sleep`, ni intervalo,
        #: ni compensacion de deriva: toda la precision la pone el aparato, que
        #: la tiene. Con Kivy generando el tiempo su tambaleo —2,1 ms de mediana
        #: y 8,4 de maximo, medido en `qy100-vida`— seria tambaleo del groove: a
        #: 120 BPM un tic son 20,8 ms, o sea el 40% de un tic.
        #:
        #: **Entra por el puerto que ya esta abierto**, no por uno propio. Dos
        #: entradas sobre el mismo aparato es pedir que una se quede sin
        #: mensajes segun quien los consuma primero.
        self.tics = 0
        self.por_paso = 6
        self.al_paso = None          # se llama en el HILO MIDI
        self.al_transporte = None
        self.llegadas = []
        self._ultimo_tic = None

    # -- conexion ----------------------------------------------------------

    @staticmethod
    def puertos():
        if mido is None:
            return []
        try:
            return sorted(set(mido.get_output_names()) & set(mido.get_input_names()))
        except Exception:
            return []

    def abrir(self, nombre=None):
        """⚠️ **Un puerto puede quedar obsoleto tras reconectar el cable** aunque
        el nombre no cambie — lo midio Shea, y se lee identico a «el aparato no
        manda nada». Por eso reabrir siempre cierra primero."""
        self.cerrar()
        if mido is None:
            self.error = "falta mido"
            return False
        try:
            libres = mido.get_output_names()
            self.nombre = nombre or (libres[0] if libres else None)
            if not self.nombre:
                self.error = "no hay puertos"
                return False
            self.salida = mido.open_output(self.nombre)
            self.entrada = mido.open_input(self.nombre, callback=self._entra)
            self.error = None
            return True
        except Exception as e:
            self.error = str(e)
            return False

    def cerrar(self):
        for p in (self.salida, self.entrada):
            try:
                if p:
                    p.close()
            except Exception:
                pass
        self.salida = self.entrada = None

    # -- lo que llega ------------------------------------------------------

    def _entra(self, msg):
        """`[D]` **El SPP es la firma del modo.** El manual (p. 57) lo describe
        como «transmitted when you move to a different measure in the SONG PLAY
        Mode», y la medida coincidio: llego uno por vuelta de SONG⇄PATTERN, no
        uno por pulsacion. Entrar a SONG lo dispara; entrar a PATTERN no.

        Asi que **esto detecta 'song' con certeza y 'pattern' nunca**. Que no
        llegue nada no prueba que este en pattern: puede estar en pattern, o
        apagado, o con MIDI CONTROL en Off. Por eso el estado arranca en None y
        la pantalla dice «sin saber» en vez de adivinar."""
        t = msg.type
        if t == "songpos":
            self.modo = "song"
        elif t == "clock":
            import time as _t
            ahora = _t.perf_counter()
            if self._ultimo_tic is not None:
                self.llegadas.append(ahora - self._ultimo_tic)
                if len(self.llegadas) > 480:
                    del self.llegadas[:240]
            self._ultimo_tic = ahora
            if self.tocando:
                self.tics += 1
                if self.tics % self.por_paso == 0 and self.al_paso:
                    self.al_paso()
        elif t in ("start", "continue", "stop"):
            # ⚠️ **`FA` vuelve al principio y `FB` no.** Confundirlos haria que
            # el generador reenganchara a destiempo, y sonaria como si el reloj
            # fuera malo cuando el malo seria el codigo.
            if t == "start":
                self.tics = 0
            self.tocando = t != "stop"
            if self.al_transporte:
                self.al_transporte(t)

    # -- lo que se manda ---------------------------------------------------

    def _mandar(self, raw: bytes, etiqueta: str):
        self.ultimo = etiqueta
        if not self.salida:
            return False
        try:
            self.salida.send(mido.Message("sysex", data=raw[1:-1]))
            self.intentos += 1
            return True
        except Exception as e:
            self.error = str(e)
            return False

    def seccion_a(self, indice: int):
        """`[M]` **El aparato lo alinea al compas**, igual que el boton fisico.

        Por eso `self.seccion` se pinta como «pedida» y no como «sonando»: entre
        el toque y el cambio pasa hasta un compas entero, y una interfaz que se
        marque al instante estaria mintiendo durante ese rato. Fue justamente el
        codigo que NO hubo que escribir — si el aparato cortara en seco, la app
        tendria que encolar hasta el borde del compas y llevar su propio tempo.
        """
        self.seccion = indice
        return self._mandar(msg_seccion(indice), "seccion %s" % SECCIONES[indice])

    def efecto(self, familia: int, variante: int = 0):
        """Variation Type. **Dos bytes**: MSB familia, LSB variante.

        `[M]` Entra **aunque el QY100 este en otra pantalla** — no hay que
        llevarlo a la pagina de FX primero. De ahi sale la regla de la maqueta:
        lo que el aparato acepta desde donde sea, la app lo ofrece desde donde
        sea, y por eso FX es una hoja global y no un hijo de MEZCLA.

        ⚠️ El LSB **no es un contador**: Chorus y Celeste van `00, 01, 02, 08`,
        Flanger `00, 01, 08`, Phaser `00, 08`. Medido por Shea. No suponer una
        secuencia para una familia que nadie barrio."""
        return self._mandar(msg_xg(DIR_EFECTO, (familia, variante)),
                            "variation %02X %02X" % (familia, variante))

    def parametro(self, addr, valor: int, tam: int = 1):
        v = valor if tam == 1 else (valor >> 7, valor & 0x7F)
        return self._mandar(msg_xg(addr, v),
                            "%02X%02X%02X = %d" % (addr + (valor,)))

    def parte_variation(self, parte):
        """Que parte pasa por el efecto. `None` = off (`0x7F`), que es el
        valor de fabrica — y con off **no se oye nada** por mucho que se
        cambie el tipo."""
        v = 0x7F if parte is None else (parte & 0x1F)
        return self._mandar(msg_xg(DIR_PARTE, v),
                            "variation part %s" % ("off" if parte is None
                                                   else parte + 1))

    def conexion_variation(self, sistema: bool):
        """`00` insercion (una sola parte) · `01` sistema (todas)."""
        return self._mandar(msg_xg(DIR_CONEXION, 1 if sistema else 0),
                            "variation %s" % ("system" if sistema else "insertion"))

    def envio(self, canal: int, cc: int, valor: int):
        """Los sends **por canal**: `CC 91` reverb, `93` chorus, `94` variation.
        Esto si es de mezclador — dieciseis mandos, no uno."""
        self.ultimo = "ch%d CC%d = %d" % (canal + 1, cc, valor)
        if not self.salida:
            return False
        try:
            self.salida.send(mido.Message("control_change", channel=canal,
                                          control=cc, value=valor & 0x7F))
            self.intentos += 1
            return True
        except Exception as e:
            self.error = str(e)
            return False

    def song_select(self, n: int):
        """`F3 nn`, dos bytes. En modo pattern **cambia el patron** (p. 57)."""
        self.ultimo = "song select %d" % (n + 1)
        if not self.salida:
            return False
        try:
            self.salida.send(mido.Message("song_select", song=n & 0x7F))
            self.intentos += 1
            return True
        except Exception as e:
            self.error = str(e)
            return False

    # -- transporte --------------------------------------------------------
    #
    # **Dos condiciones distintas, y confundirlas cuesta el groove.** La tabla
    # de implementacion MIDI (service manual p. 71) las separa en dos notas:
    #
    #     System Real Time :Commands   *1 if MIDI control is in or in/out
    #     System :Clock                *3 if MIDI sync is external
    #
    # O sea: **START/STOP/CONTINUE solo necesitan `MIDI CONTROL`**. `MIDI SYNC`
    # no entra. Y conviene dejarlo en `Internal` aunque `External` suene a lo
    # correcto: con `External` el QY100 «no funcionara por si solo» (manual de
    # usuario p. 127) y la app tendria que mandar F8 a 24 PPQN — un tic cada
    # 20,8 ms a 120 BPM, contra los **8,4 ms de jitter maximo** que se midieron
    # en Kivy en `qy100-vida`. El 40% de un tic. **El tempo se volveria el pulso
    # de la tableta.**
    #
    # Asi que la app es un control remoto y no un metronomo, y el reloj se queda
    # donde el aparato lo sabe llevar.
    #
    # ⚠️ `MIDI SYNC` **no vive en el bloque de setup** — dos volcados que solo
    # difieren en Internal/External salen identicos byte a byte. Es de panel,
    # como el modo. La app puede pedirlo, no ponerlo.

    def _realtime(self, tipo: str, etiqueta: str):
        self.ultimo = etiqueta
        if not self.salida:
            return False
        try:
            self.salida.send(mido.Message(tipo))
            self.intentos += 1
            return True
        except Exception as e:
            self.error = str(e)
            return False

    def arrancar(self):
        """`FA`. Arranca desde el principio."""
        self.tocando = True
        return self._realtime("start", "start")

    def continuar(self):
        """`FB`. Retoma donde se quedo, sin volver al principio."""
        self.tocando = True
        return self._realtime("continue", "continue")

    def parar(self):
        """`FC`."""
        self.tocando = False
        return self._realtime("stop", "stop")

    def panico(self):
        """Todo apagado. Un prototipo se reinicia veinte veces y deja notas."""
        if not self.salida:
            return
        for ch in range(16):
            for cc in (123, 120):
                try:
                    self.salida.send(mido.Message("control_change", channel=ch,
                                                  control=cc, value=0))
                except Exception:
                    return


# ------------------------------------------------------- mezclador del patron

#: Las seis filas de la pantalla de envios, con su offset medido el 2026-08-16.
#: El orden aqui es el de la PANTALLA, no el de la memoria — quien mira la app
#: esta mirando el aparato, no el volcado.
FILAS_MEZCLA = [("reverb", "REVERB"), ("chorus", "CHORUS"),
                ("variacion", "VARI."), ("dry", "DRY")]

#: `[M]` **En modo patron el mezclador y los envios son el MISMO dato.** Volumen
#: (170), panoramico (178) y las cuatro filas de envios viven en los mismos cinco
#: bloques de cabecera: un volcado trae las seis y una escritura las guarda las
#: seis. Por eso `LEER`/`APLICAR` es uno solo para las dos vistas — tenerlo por
#: separado invitaria a escribir dos veces y a pisar lo que la otra vista tenia.
FILAS_NIVEL = [("volumen", "VOLUME"), ("panoramico", "PAN")]
TODAS_LAS_FILAS = FILAS_NIVEL + FILAS_MEZCLA

PISTAS_PATRON = ["D1", "D2", "PC", "BA", "C1", "C2", "C3", "C4"]


def _cargar_voces():
    """Los 525 nombres sacados de la ROM del firmware, mas los kits.

    **El volcado ya trae el numero de voz de cada pista** (`programa`) y si usa
    kit de bateria; lo unico que faltaba era traducirlo. Un dato leido y no
    mostrado es trabajo hecho y tirado.
    """
    import json
    ruta = os.path.join(_SYX, "voces.json")
    try:
        v = json.load(open(ruta))
        # **Los kits no son una lista paralela**: son 22 diccionarios con su
        # propio `programa`, salteados (Pgm# 1,2,3,4,9,10,17,18,25...). Indexar
        # por posicion daria el kit equivocado.
        #
        # ⚠️ **Y la clave real es (banco, programa), no el programa solo.** Los
        # programas 0 y 1 estan dos veces: banco 127 es `Standard Kit` y
        # `Standard Kit 2`, banco 126 es `SFX Kit 1` y `SFX Kit 2`. Un
        # diccionario indexado por programa se queda con el ultimo — y la
        # primera version de esto mostraba `SFX Kit 1` donde el aparato tiene
        # `Standard Kit`. **Un nombre plausible y falso es peor que ninguno**,
        # que es la leccion de la casa aplicada a una tabla de nombres.
        #
        # La cabecera del patron **no guarda el banco**: solo el programa y la
        # bandera de bateria. Asi que se prefiere el 127, el banco de kits, y
        # los del 126 quedan indistinguibles — lo dice `nombre_voz`.
        kits = {}
        for k in v.get("kits", []):
            if not (isinstance(k, dict) and "programa" in k):
                continue
            pr, banco = k["programa"], k.get("banco", 127)
            if pr not in kits or banco > kits[pr][0]:
                kits[pr] = (banco, k["nombre"])
        return v.get("normales_por_programa", []), {p: n for p, (_b, n) in kits.items()}
    except Exception:
        return [], {}


VOCES, KITS = _cargar_voces()

#: Las 16 familias GM, de ocho programas cada una. `[M]` El QY100 usa sus propias
#: abreviaturas de dos letras —`Pf001`, `Ba033`, `Dr001`— y sus limites coinciden
#: con estas: en el Data List `Pf` abre en 1, `Cp` en 9, `Or` en 17, `Ba` en 33,
#: `En` en 49, `Pi` en 73, `Ld` en 81, `Pd` en 89, `Fx` en 97, `Pc` en 113 y
#: `Se` en 121.
#:
#: ⚠️ **Los nombres largos son de GM, no del QY100.** Sacar las abreviaturas del
#: propio Data List no salio: la tabla va a cuatro columnas entrelazadas y el
#: intento cazaba fragmentos de nombres de voz (`Br` dentro de `RezSynBr`).
#: Completarlas «por logica» seria un mapa coherente y sin comprobar, que es
#: justo lo que fallo con los kits. Asi que se usan los nombres GM, que si son
#: exactos, y las abreviaturas quedan pendientes.
FAMILIAS = ["Piano", "Perc. cromatica", "Organo", "Guitarra",
            "Bajo", "Cuerdas", "Conjunto", "Metales",
            "Canas", "Tubos", "Lead", "Pad",
            "Efectos synth", "Etnico", "Percusivo", "Efectos"]


def voz_direccionable(nombre, bateria=False):
    """`(programa, banco)` para pedir esa voz, o `None` si no se puede.

    **477 de 525.** Las otras 48 salen del ROM con nombre pero sin numero de
    programa —la seccion «Other wave» del Data List las lista en columna, sin
    repetir programa ni banco— y adivinarlo por posicion daria una voz
    plausible y equivocada. La interfaz las muestra apagadas: **se ven, no se
    piden.**
    """
    if bateria:
        # Los kits viven en MSB 127, y `KITS` ya esta indexado por programa.
        return (nombre_programa_kit(nombre), 127, 0)
    k = nombre.replace(" ", "").lower()
    pr = PROG_POR_NOMBRE.get(k)
    if pr is None:
        return None
    # `[M]` **El MSB no siempre es 0.** 0 normales, 64 efectos, 126 kits de
    # efectos, 127 kits de bateria — declarado en el Data List y confirmado por
    # el QY70 Controller de Ilya Orange. Suponer 0 pedia la voz normal de ese
    # programa en vez de la de efectos: otra voz, sin error.
    return (pr, MSB_POR_NOMBRE.get(k, 0), BANCO_POR_NOMBRE.get(k, 0))


def nombre_programa_kit(nombre):
    for pr, n in KITS.items():
        if n == nombre:
            return pr + 1
    return 1


def _cargar_bancos():
    """`nombre normalizado -> programa`, de `bancos.json`.

    **477 de 525**, confirmadas contra la ROM por dos fuentes independientes.
    Las 48 restantes viven en la seccion «Other wave» del Data List, listadas en
    columna sin repetir programa ni banco; inferirlos por posicion daria numeros
    plausibles y sin comprobar. Esas voces salen **sin categoria**, que es la
    verdad, en vez de con una inventada.
    """
    import json
    try:
        b = json.load(open(os.path.join(_SYX, "bancos.json")))
        prog, banco, msb = {}, {}, {}
        for v in b.get("voces", []):
            k = v["nombre"].replace(" ", "").lower()
            prog.setdefault(k, v["programa"])
            banco.setdefault(k, v["banco"])
            msb.setdefault(k, v.get("msb", 0))
        return prog, banco, msb
    except Exception:
        return {}, {}, {}


PROG_POR_NOMBRE, BANCO_POR_NOMBRE, MSB_POR_NOMBRE = _cargar_bancos()


def familia(nombre: str):
    """Familia GM de una voz por su nombre, o `None` si no se pudo confirmar."""
    pr = PROG_POR_NOMBRE.get(nombre.replace(" ", "").lower())
    if pr is None:
        return None
    return FAMILIAS[min(15, (pr - 1) // 8)]


def nombre_voz(programa: int, bateria: bool) -> str:
    """`programa` es base cero: el numero de pantalla menos uno.

    ⚠️ **Los kits van por una tabla distinta.** Una pista de bateria con
    `programa 0` no es `GrandPno`; traducirla con la tabla de voces normales
    daria un nombre coherente y falso, que es la clase de error que este
    proyecto ya conoce.
    """
    if bateria:
        # `[V]` Sin el banco no se puede distinguir el kit de bateria del de
        # efectos con el mismo programa. Se asume el banco 127, que es el que
        # usa una pista de bateria de un patron.
        return KITS.get(programa, "kit #%d" % (programa + 1))
    if 0 <= programa < len(VOCES):
        return VOCES[programa]
    return "#%d" % (programa + 1)


class Mezclador:
    """Lee y escribe el mezclador del patron, que **no es un control en vivo**.

    `[M]` Medido el 2026-08-16: en modo patron los envios de efecto son **dato de
    la cabecera del patron**, no `CC` por canal. Mandar `CC 91/93/94` no mueve
    esas perillas — se probo con una rampa por los 16 canales y no se movio
    ninguna.

    Eso tiene una consecuencia de interfaz que no se puede disimular: cambiar un
    envio exige **volcar la cabecera, modificarla y reescribirla**, con su marco
    de bulk mode. Son segundos, no milisegundos. Una perilla que tarda dos
    segundos en responder no es una perilla, asi que la pantalla acumula los
    cambios y los manda de una sola vez.

    ⚠️ **La lectura tambien va enmarcada en `bulk mode ON -> peticion -> OFF`.**
    Sin el marco el aparato **no contesta nunca**, y ese silencio se lee igual
    que «esta en el modo equivocado» o «se colgo» — costo una hora el
    2026-08-16, incluido apagar y prender el aparato sin necesidad.

    ⚠️ Y **falla de forma intermitente**: unas veces contesta al primer intento y
    otras falla varios seguidos. Por eso reintenta.
    """

    INTENTOS = 5

    def __init__(self, aparato):
        self.ap = aparato
        self.nombre, self.compases = None, None

    def _parar(self):
        """`FC` antes de volcar o escribir. **Siempre, sin preguntar.**

        No es cortesia, son dos requisitos medidos:

        1. Con `MIDI CONTROL` en `In/Out` y el aparato tocando, el QY100
           transmite **72 relojes por segundo**, y esa avalancha ahoga la
           respuesta al volcado. Es el mismo motivo por el que `collect()`
           captura por callback en vez de sondear.
        2. **El QY100 ignora las escrituras mientras suena.** Se reportarian
           enviadas y no pasaria nada.

        ⚠️ **Y se manda incondicionalmente a proposito.** La app no puede saber
        si esta sonando —el aparato no lo cuenta, y el play pudo darse desde el
        panel— asi que consultar `self.ap.tocando` seria fiarse de una creencia.
        `FC` sobre un aparato parado no hace nada; omitirlo sobre uno sonando
        cuesta un volcado mudo que se lee como fallo de enlace.
        """
        if not self.ap.salida:
            return
        self.ap.parar()
        time.sleep(0.4)

    def _con_marco(self, addr):
        out, inn = self.ap.salida, self.ap.entrada
        for intento in range(1, self.INTENTOS + 1):
            out.send(mido.Message("sysex", data=PR.bulk_mode(True)[1:-1]))
            time.sleep(0.3)
            try:
                blob, _ = transfer.request(out, inn, addr, 1.2, 10,
                                           log=lambda *a: None)
            finally:
                out.send(mido.Message("sysex", data=PR.bulk_mode(False)[1:-1]))
                time.sleep(0.3)
            msgs, _e = PR.parse_all(blob)
            dumps = [m for m in msgs if m.sub == PR.SUB_DUMP]
            if dumps:
                return dumps, intento
            time.sleep(0.5)
        return None, self.INTENTOS

    def leer(self, patron):
        """Devuelve (valores, cabecera, pistas, nota). `valores` es lo que el
        aparato tiene AHORA — la unica parte de esta app que puede pintar estado
        medido en vez de estado pedido.

        ⚠️ `[M]` **Un volcado multibloque exige `MIDI CONTROL` en `Off`**, y esto
        lo pone y lo devuelve. Medido el 2026-08-17 con una comparacion limpia —
        mismo codigo, mismo patron, dos valores:

            Off      -> leido del aparato
            In/Out   -> cabecera incompleta (2 de 5)

        **El matiz importa porque el proyecto lo tenia mal escrito.** `CLAUDE.md`
        decia que `MIDI CONTROL` no tiene nada que ver con SysEx, citando una
        transferencia completa sin tocarlo. Eso vale para **un bloque suelto** —
        el setup se lee bien en cualquier valor— y **no vale para multibloque**:
        con el aparato transmitiendo, unos bloques llegan y otros no.

        Y esto es justo lo que la app prometia hacer y no hacia: **poner el
        ajuste donde tiene que estar y devolverlo**, para que nadie tenga que
        acordarse. Cuesta unos segundos mas y ahorra el fallo mudo.
        """
        if not (F and self.ap.salida and self.ap.entrada):
            return None, None, None, "sin puerto o sin codec"
        mc = MidiControl(self.ap)
        previo = mc.leer()
        if previo is not None and previo != 0x00:
            mc.poner("Off")
        self._parar()
        try:
            dumps, intentos = self._con_marco(
                PR.Addr.pattern(patron - 1, F.HEADER_TR))
        finally:
            if previo is not None and previo != 0x00:
                mc.poner(MC_NOMBRES[previo])
        if not dumps:
            return None, None, None, ("sin respuesta en %d intentos — "
                                      "¿pattern play y parado?" % intentos)
        cab = [m for m in dumps if m.addr[2] == F.HEADER_TR]
        pistas = [m for m in dumps if m.addr[2] != F.HEADER_TR]
        if len(cab) != 5:
            return None, None, None, ("cabecera incompleta (%d de 5)" % len(cab))
        payloads = [bytes(m.data) for m in cab]
        # El nombre y las longitudes salen del PRIMER bloque, no de los cinco
        # juntos — `decode_header` recibe un payload, no la lista. Confundirlo
        # devuelve un nombre de basura en vez de fallar, que es peor.
        nombre, compases = F.decode_header(payloads[0])
        nota = "leido del aparato" + (" (intento %d)" % intentos
                                      if intentos > 1 else "")
        self.nombre, self.compases = nombre, compases
        return F.decode_mixer(payloads), payloads, pistas, nota

    def leer_acordes(self, pistas, seccion=1):
        """`{pista -> (raiz, tipo)}` del acorde fuente de una seccion.

        `[M]` **Es por pista y vive en el prefijo de 26 bytes**, no en la
        cabecera: bytes 21 (raiz, semitonos desde Do) y 22 (tipo). Por eso hace
        falta el volcado de pistas y no basta con los cinco bloques de cabecera.

        Solo el **primer** bloque de cada pista lleva el prefijo; los siguientes
        son continuacion. Como el aparato vuelca en orden, la primera aparicion
        de cada `tr` es la buena.
        """
        fuera, vistos = {}, set()
        for m in pistas:
            tr = m.addr[2]
            if tr in vistos or tr // 8 != seccion:
                continue
            vistos.add(tr)
            try:
                fuera[tr % 8] = F.decode_source_chord(bytes(m.data))
            except Exception:
                pass
        return fuera

    def escribir(self, patron, cab, pistas, valores, acordes=None, seccion=1):
        """`valores[pista][fila]`. Una sola escritura con todo.

        ⚠️ **El patron va entero y en el orden en que el aparato lo volco**:
        pistas primero, los 5 bloques de cabecera al final. Reordenarlo lo borra.
        """
        if not (F and self.ap.salida):
            return "sin puerto o sin codec"
        self._parar()
        for pista in range(8):
            # La voz va por su propia funcion: escribe programa y la bandera de
            # kit, que son dos bytes distintos del mezclador.
            v = valores[pista]
            if "programa" in v:
                cab = F.set_mixer_voice(cab, pista, v["programa"],
                                        bool(v.get("bateria", False)))
            cab = F.set_mixer(cab, pista,
                              **{k: valores[pista][k] for k, _ in TODAS_LAS_FILAS
                                 if k in valores[pista]})
        addr = PR.Addr.pattern(patron - 1, F.HEADER_TR)

        # Las pistas se reenvian tal cual **salvo las que cambiaron de acorde**.
        # Y solo el primer bloque de cada una: es el que lleva el prefijo.
        crudas, tocados = [], set()
        for m in pistas:
            tr = m.addr[2]
            cambio = (acordes or {}).get(tr % 8) if tr // 8 == seccion else None
            if cambio and tr not in tocados:
                tocados.add(tr)
                raiz, tipo = cambio
                nueva = F.set_source_chord(bytes(m.data), raiz, tipo)
                crudas.append(PR.build_dump(PR.Addr.pattern(patron - 1, tr),
                                            nueva))
            else:
                crudas.append(m.raw)
        salida = crudas + [PR.build_dump(addr, b) for b in cab]
        transfer.send_pattern(self.ap.salida, salida, log=lambda *a: None)
        self.ap.intentos += len(salida)
        # **Que se reporte enviado no prueba nada.** Lo unico que prueba estado
        # es releer, y por eso la pantalla ofrece LEER al lado de APLICAR.
        return "escrito — verifica con LEER"


# --------------------------------------------------------------- MIDI CONTROL

#: `[M]` Byte 11 del bloque de setup, bits 4-5. Mapa medido entero el 2026-08-15
#: comprobando cada valor por su efecto, no releyendo el byte:
#:
#:     Off     0x00   no responde a control externo, ni al transporte
#:     In      0x10   recibe
#:     Out     0x20   transmite (72 relojes/s al tocar)
#:     In/Out  0x30
#:
#: **El volcado funciona en cualquiera de los cuatro** — medido el 2026-08-16
#: leyendo el setup con `Off` puesto. Lo que `Off` corta son notas, CC y
#: transporte. Ese matiz costo media hora: un `PLAY` que no arrancaba se leyo
#: como fallo del codigo cuando era este ajuste, dejado en `Off` por una prueba
#: de dos horas antes.
MC_OFFSET, MC_MASCARA = 11, 0x30
MC_NOMBRES = {0x00: "Off", 0x10: "In", 0x20: "Out", 0x30: "In/Out"}
MC_VALORES = {v: k for k, v in MC_NOMBRES.items()}


class MidiControl:
    """Lee y escribe `MIDI CONTROL` sin ir al panel.

    ⚠️ **Se escribe el bloque ENTERO de setup, enmarcado en bulk mode.** Sin el
    marco la escritura se ignora **en silencio**: el envio reporta exito y nada
    cambia.
    """

    INTENTOS = 4

    def __init__(self, aparato):
        self.ap = aparato

    def _leer_bloque(self):
        out, inn = self.ap.salida, self.ap.entrada
        if not (out and inn and PR):
            return None
        for _ in range(self.INTENTOS):
            out.send(mido.Message("sysex", data=PR.bulk_mode(True)[1:-1]))
            time.sleep(0.3)
            try:
                blob, n = transfer.request(out, inn, PR.Addr.SETUP, 1.2, 10,
                                           log=lambda *a: None)
            finally:
                out.send(mido.Message("sysex", data=PR.bulk_mode(False)[1:-1]))
                time.sleep(0.3)
            if n:
                return bytearray(blob)
            time.sleep(0.6)
        return None

    def leer(self):
        b = self._leer_bloque()
        if b is None:
            return None
        return b[9 + MC_OFFSET] & MC_MASCARA

    def poner(self, nombre):
        """Devuelve el valor **releido del aparato**, no el que se pidio.

        Que una escritura se reporte exitosa no prueba nada; aqui eso no es una
        frase hecha, es el fallo concreto que tiene este bloque sin bulk mode.
        """
        destino = MC_VALORES[nombre]
        b = self._leer_bloque()
        if b is None:
            return None
        if (b[9 + MC_OFFSET] & MC_MASCARA) == destino:
            return destino
        b[9 + MC_OFFSET] = (b[9 + MC_OFFSET] & ~MC_MASCARA) | destino
        b[-2] = PR.checksum(b[4:-2])
        out = self.ap.salida
        out.send(mido.Message("sysex", data=PR.bulk_mode(True)[1:-1]))
        time.sleep(0.3)
        out.send(mido.Message("sysex", data=bytes(b[1:-1])))
        time.sleep(0.3)
        out.send(mido.Message("sysex", data=PR.bulk_mode(False)[1:-1]))
        time.sleep(0.3)
        return self.leer()


    # -- el reloj, para mostrarlo -----------------------------------------

def bpm_medido(aparato):
    """BPM **deducido** del intervalo entre tics, no leido.

    El QY100 no dice su tempo por MIDI, asi que esto hereda el ruido de la
    medida: sirve para mostrar, **no para sincronizar nada**. Lo que sincroniza
    es contar `F8`, que no necesita saber el tempo.
    """
    ll = aparato.llegadas[-24:]
    if len(ll) < 24:
        return None
    medio = sum(ll) / len(ll)
    return 60.0 / (medio * 24) if medio > 0 else None


# ------------------------------------------------------ edicion de voz (NRPN)

#: `[M]` **Los seis controles de la pantalla VOICE EDIT, y todos por NRPN.**
#: Data List, tabla NRPN, con `MSB = 0x01`. El rango es el mismo en los cinco:
#: `00–40–7F`, que la pantalla muestra como **−64…0…+63**.
#:
#:     0x20  FILTER CUTOFF FREQ.  -> CUT
#:     0x21  FILTER RESONANCE     -> RES
#:     0x63  AEG ATTACK TIME      -> A
#:     0x64  AEG DECAY TIME       -> D
#:     0x66  AEG RELEASE TIME     -> R
#:
#: **Que sean todos del mismo mecanismo no es casualidad, es el hallazgo.** Los
#: CC 71-74 tambien mueven cuatro de ellos, pero `D` **no tiene CC** — igual que
#: `DRY` en el mezclador. Mezclar dos vias para una pantalla habria dejado un
#: control comportandose distinto sin motivo visible.
NRPN_VOZ = [(0x20, "CUT"), (0x21, "RES"),
            (0x63, "A"), (0x64, "D"), (0x66, "R")]

#: `PB` va por RPN, no NRPN, y su rango es otro: −24…+24 semitonos, o sea que el
#: valor crudo son los semitonos directos y no lleva el desplazamiento de 64.
RPN_PITCH_BEND = (0x00, 0x00)

#: `[V]` **La edicion de bateria, por instrumento.** NRPN con `MSB = 0x14`-`0x1F`
#: y `LSB = numero de nota`: corte, resonancia, ataque, caida, afinacion, nivel,
#: pan y los tres envios, **de cada tambor por separado**. Sale del mismo Data
#: List y nadie lo ha probado todavia.
#: (msb, etiqueta corta, si es desplazamiento centrado en 64). **Los nombres
#: van completos y no abreviados**: `DEC` y `TUNE` no le dicen nada a nadie
#: mirando una fila de diez perillas iguales, y una etiqueta que hay que
#: descifrar es lo mismo que ninguna.
#: ⚠️ `[M]` **El pan de percusion tiene un `0` que no es un valor, es un modo.**
#: Data List: `1CH rrH mmH — DRUM INST PANPOT  00H, 01H-40H-7FH (random, left -
#: center - right)`. Con `0` el QY100 **reparte cada golpe a un lado distinto**,
#: y en un tambor repetido eso se oye como un delay ping-pong.
#:
#: La primera version de esta tabla puso el pan a arrancar en 0 junto al nivel y
#: los envios, asi que **cada tambor salia en aleatorio**. Lo encontro el oido
#: antes que el documento. Ahora arranca centrado y el `0` se muestra como
#: `random` y no como un numero: ensenarlo como «0» sugiere «minimo» cuando
#: significa otra cosa.
#:
#: Y lo mismo vale para el pan de PARTE (`nn 0E` en Multi Part, tambien
#: `0:random`), que es donde cae el `CC 10` del mezclador.
NRPN_BATERIA = [(0x14, "corte", True), (0x15, "reso", True),
                (0x16, "ataque", True), (0x17, "caida", True),
                (0x18, "afina", True), (0x1A, "nivel", False),
                (0x1C, "pan", "pan"), (0x1D, "reverb", False),
                (0x1E, "chorus", False), (0x1F, "vari", False)]


def _cc(out, canal, control, valor):
    out.send(mido.Message("control_change", channel=canal,
                          control=control, value=valor & 0x7F))


def manda_nrpn(out, canal, msb, lsb, valor):
    """`Bn 63 msb · Bn 62 lsb · Bn 06 valor`.

    ⚠️ **Van los tres mensajes y en ese orden.** El aparato recuerda el ultimo
    NRPN seleccionado, asi que mandar solo el data entry mueve *lo que se
    hubiera seleccionado antes* — un fallo que no da error y cambia el
    parametro equivocado.
    """
    _cc(out, canal, 99, msb)      # NRPN MSB
    _cc(out, canal, 98, lsb)      # NRPN LSB
    _cc(out, canal, 6, valor)     # data entry MSB


def manda_rpn(out, canal, msb, lsb, valor):
    """Igual pero con `64`/`65`, y **se cierra con RPN Reset**.

    El Data List lista `Bn 64 7F 65 7F` como *RPN RESET*: deja la seleccion en
    «ninguno» para que un data entry suelto posterior no caiga en el ultimo RPN.
    Sin eso, mover una rueda cualquiera despues podria reescribir el pitch bend.
    """
    _cc(out, canal, 101, msb)     # RPN MSB
    _cc(out, canal, 100, lsb)     # RPN LSB
    _cc(out, canal, 6, valor)
    _cc(out, canal, 101, 0x7F)
    _cc(out, canal, 100, 0x7F)


def cambia_voz(aparato, canal, programa, msb, banco):
    """Bank Select + Program Change, **y en ese orden**.

    `[M]` Data List, cabecera de la tabla de voces: `Bank Select MSB=000,
    LSB=Bank Number`. El MSB va en 0 para las voces normales y el banco real en
    el LSB; los kits de bateria viven en el banco 127.

    ⚠️ **El banco antes que el programa.** El aparato aplica el banco que tenga
    seleccionado cuando llega el program change, asi que mandarlos al reves
    carga la voz correcta del banco anterior — otra voz, sin error, y con nombre
    plausible en pantalla.

    `programa` viene 1-128 como en el Data List y en la pantalla del aparato; el
    program change de MIDI va 0-127. Restar ese uno es de los errores que no
    fallan: cargan la voz de al lado.
    """
    out = aparato.salida
    if not out:
        return False
    try:
        out.send(mido.Message("control_change", channel=canal,
                              control=0, value=msb & 0x7F))
        out.send(mido.Message("control_change", channel=canal,
                              control=32, value=banco & 0x7F))
        out.send(mido.Message("program_change", channel=canal,
                              program=max(0, min(127, programa - 1))))
        aparato.intentos += 3
        aparato.ultimo = ("ch%d voz %d  MSB %d LSB %d"
                          % (canal + 1, programa, msb, banco))
        return True
    except Exception as e:
        aparato.error = str(e)
        return False


# ------------------------------------------- nombres de parametro por efecto

#: `[M]` Familia de efecto -> bloque de la Effect Parameter List del Data List
#: (paginas 11-14). **Un mismo bloque cubre varios tipos** porque comparten la
#: tabla: `Hall`, `Room`, `Stage` y `Plate` usan la misma.
BLOQUE_POR_FAMILIA = {
    0x01: "HALL1,2, ROOM1,2,3, STAGE1,2, PLATE",
    0x02: "HALL1,2, ROOM1,2,3, STAGE1,2, PLATE",
    0x03: "HALL1,2, ROOM1,2,3, STAGE1,2, PLATE",
    0x04: "HALL1,2, ROOM1,2,3, STAGE1,2, PLATE",
    0x05: "DELAY L,C,R", 0x06: "DELAY L,R",
    0x07: "ECHO", 0x08: "CROSS DELAY", 0x09: "EARLY REF1,2",
    0x0A: "GATE REVERB, REVERSE GATE", 0x0B: "GATE REVERB, REVERSE GATE",
    0x14: "KARAOKE1,2,3",
    0x41: "CHORUS1,2,3,4, CELESTE1,2,3,4",
    0x42: "CHORUS1,2,3,4, CELESTE1,2,3,4",
    0x43: "FLANGER1,2,3", 0x44: "SYMPHONIC", 0x45: "ROTARY SPEAKER",
    0x46: "TREMOLO", 0x47: "AUTO PAN", 0x48: "PHASER1,2",
    0x49: "DISTORTION, OVERDRIVE", 0x4A: "DISTORTION, OVERDRIVE",
    0x4B: "GUITAR AMP SIMULATOR", 0x4E: "AUTO WAH",
}


def _cargar_parametros():
    import json
    try:
        d = json.load(open(os.path.join(_SYX, "parametros_efecto.json")))
        return {k: {int(n): v for n, v in ps.items()}
                for k, ps in d["bloques"].items()}
    except Exception:
        return {}


PARAMS_EFECTO = _cargar_parametros()


def nombre_parametro(familia, n):
    """Como se llama el `Param n` con esa familia puesta, o `None`.

    **El Data List solo dice «depends on vari. type»**, y esa frase deja una
    interfaz ofreciendo «Parametro 3» — correcto y sin utilidad, porque bajo
    `Hall` es el retardo inicial y bajo `Delay L,C,R` es el canal central.

    ⚠️ Devuelve `None` cuando ese numero **no existe** para ese tipo: la tabla
    tiene huecos —el 6 al 9 estan vacios en los bloques de reverb— y ensenar una
    perilla para un parametro que el aparato no tiene es prometer de mas.
    """
    bloque = PARAMS_EFECTO.get(BLOQUE_POR_FAMILIA.get(familia, ""), {})
    return bloque.get(n)
