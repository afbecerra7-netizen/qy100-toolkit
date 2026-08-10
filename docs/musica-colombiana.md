# Música colombiana, medida

Las células rítmicas de los géneros que usa el proyecto, sacadas de partituras
y de transcripciones, no de teoría. El código está en
[`qy100-syx/qy100syx/andina.py`](../qy100-syx/qy100syx/andina.py) y las
mediciones se rehacen con
[`analizar_loop.py`](../qy100-syx/analizar_loop.py).

> **Cómo leer las marcas.** Todo lo que hay aquí está en uno de tres estados, y
> distinguirlos es lo que evita repetir errores: casi todos los que ha cometido
> este proyecto viven en la frontera entre el segundo y el primero.
>
> - `[M]` **medido** contra el aparato o contra una fuente primaria. Se puede usar.
> - `[D]` **deducido** de otra cosa que sí está medida. Coherente, sin comprobar.
> - `[V]` **sin verificar**, o comprobado por una vía que no lo demuestra.
>
> Una deducción coherente suena exactamente igual que un hecho. El bambuco salió
> mal tres veces seguidas por eso, y el parámetro de disparo de la DrumBrute se
> atribuyó al byte equivocado por ser el primero de la lista.

### El bambuco, medido sobre partituras — y tres versiones equivocadas antes

**"Papa con yuca"** es la onomatopeya del patron base de la tambora andina y es
la identidad ritmica del genero: sin el, lo demas puede estar bien y no sonar a
bambuco. Felipe lo detecto de oido en la primera version generada.

La celda sale de `te-ofrezco-mi-corazon-bambuco.mid` (coro, guitarra y tambora,
6/8), doblando los ataques por compas:

```
corchea      1      2       3      4       5      6
silaba       PA     PA      CON    YU      CA      ·
tambora     alto   alto    bajo   alto    bajo     ·
guitarra      ·   ACORDE   BAJO  ACORDE   BAJO     ·
```

En 31 compases la guitarra da **31 ataques de acorde en la 2 y 31 en la 4**, y
**31 graves sueltos en la 3 y 31 en la 5**. Uno por compas, sin excepcion. Y el
bajo hace **quinta en la 3, fundamental en la 5** — en ese orden, siempre. Poner
la fundamental primero, que es lo natural, invierte el gesto: la llegada a la
fundamental en la 5 es lo que cierra el compas.

**La corchea 6 esta vacia en todo el acompanamiento.**

**Tres versiones equivocadas antes de esta, cada una por una fuente distinta:**

1. **Bombo en 1 y 4**, deducido de la sesquialtera sobre el papel: los dos grupos
   de `3+3` empiezan ahi. Coherente y falso.
2. **Bombo en 1, 3, 5**, sacado de los grooves de Tribe. Pero aquello es un
   bambuco tocado con **tambores caribeños** —una adaptacion—, no el andino.
   **Una transcripcion real de otro conjunto no es una transcripcion del genero.**
3. **Acordes en 1, 3, 5 y bajo en 4 y 6**, de una descripcion en prosa encontrada
   por internet con precision de corchea. Era de otro patron. Lo que la hizo
   convincente fue justo lo que la hacia peligrosa: venia con detalle suficiente
   para parecer medida.

Para el ritmo de un genero, **una partitura del genero** gana a la teoria
metrica, a la prosa y a una transcripcion de instrumentos que no son los suyos.

**Y las partituras no coinciden entre si, lo cual es el dato.** Cuatro bambucos:

```
te-ofrezco     6/8   acordes 2,4       bajos 3,5
y-un-cafe      6/8   acordes 1,2,4,6   bajos 3,5
brisas         3/4   acordes 1,3,5
```

`te-ofrezco` pone los acordes en la contra y `brisas` en los tres negros. **No es
que uno este mal: uno toca el lado de 6/8 de la sesquialtera y el otro el de
3/4.** Por eso los transcriptores eligieron compases distintos para la misma
musica. El invariante entre los dos de 6/8 es **el bajo en 3 y 5**.

**La melodia no se pega a la celda.** La flauta de `y-un-cafe` reparte 367 notas
casi por igual entre las seis corcheas (64/54/54/76/64/55), con una leve
inclinacion por la 4. Flota por encima del acompanamiento. Es lo contrario de lo
que hace un motor generativo, que alinea todo con la rejilla — y explica por que
una melodia generada suena a maquina aunque las notas sean correctas. Alturas:
la coleccion de La menor natural, con `E` y `A` como las mas frecuentes, ambito
de dos octavas.

**Las diferencias entre partituras son VARIANTES REGIONALES, no criterio del
transcriptor.** El bambuco tiene variantes documentadas —de salon, fiestero,
sureño, sanjuanero, caucano, patiano, del litoral— y el caracter sigue a la
geografia: lento y melancolico en el Cauca, **fiestero en el Tolima y los
Santanderes**, campesino en el altiplano. `brisas-del-pamplonita` es
santandereano (el Pamplonita es un rio de Norte de Santander) y su patron es
otro:

```
corchea      1      2      3      4      5      6
fiestero    BAJO  ACORDE  BAJO  ACORDE  BAJO  ACORDE    santandereano
de salon      ·   ACORDE  BAJO  ACORDE  BAJO    ·       te-ofrezco
```

**El fiestero no deja huecos y empuja; el de salon deja vacias la 1 y la 6 y
respira.** La celda de tambora se comparte: es el mismo genero.

Y con eso **la notacion deja de ser arbitraria**: en el fiestero el bajo cae en
las tres negras, asi que el 3/4 es lo natural; en el de salon el peso esta en las
contras del 6/8. La eleccion de compas es **consecuencia del patron**, no del
gusto de quien transcribe. Hipotesis con dos partituras; confirmarla necesita
mas de cada variante.

`qy100syx/andina.py`. `[V]` **El pasillo del mismo modulo sigue construido por el
metodo 3 y esta sin verificar contra ninguna partitura**: tratarlo como hipotesis
hasta comprobarlo.

### Medir cuan invariante es un genero

De sacar celdas de cuatro partituras salio un metodo que sirve para cualquiera:
**contar que porcentaje de compases repiten exactamente el mismo patron de
ataques.** Separa la celda del genero de las decisiones del arreglista.

```
guabina      97%   (35 de 36 compases, en las tres capas a la vez)
torbellino   97%   (bombo en 1 y 5, 96 de 99 compases)
bambuco      83%
pasillo      60%
vino tinto   58%   (otra celda del mismo genero)
```

Por debajo de la mitad no hay celda que extraer, solo un arreglo. Y el numero
dice algo musical, no tecnico: **cuanto margen tiene el interprete**. En el
torbellino, ninguno; en el pasillo, cuatro de cada diez compases son del
arreglista. Explica por que el pasillo costo tres intentos y el torbellino salio
a la primera.

Celdas medidas, todas en 3/4 sobre seis corcheas:

```
                1      2      3      4       5       6
torbellino    BOMBO    ·      ·    caja   BOMBO    caja
guabina       BAJO     ·   ACORDE    ·    BAJO   ACORDE
bambuco salon   ·   ACORDE  BAJO  ACORDE   BAJO      ·
bambuco fiest BAJO  ACORDE  BAJO  ACORDE   BAJO   ACORDE
pasillo       BAJO     ·      ·   ACORDE  ACORDE     ·
pasillo denso  linea continua en corcheas, velocity plana
```

**Guabina y torbellino comparten el bajo en 1 y 5**; lo que los separa es donde
responde la armonia — el torbellino en los tres negros, la guabina en las contras
detras de cada bajo. Mismo esqueleto, distinto eco. Y **el bambuco fiestero es el
unico que ocupa las seis corcheas**: por eso empuja.

## El currulao — la célula más limpia medida hasta ahora

`[M]` De `bombo-golpeador-o-macho-currulao.mid`: **64 notas en 16 compases, y los
dieciséis idénticos golpe por golpe. 100 % de repetición.** El torbellino daba
97 y el bambuco de salón 83.

```
corchea     1      2      3      4      5      6
sílaba     Con           laor   ques          ta      (y luego de-le-du-ro)
mano       IZQ           IZQ    IZQ           DER
golpe     madera        madera madera        cuero
altura     C#2           C#2    C#2           C2
```

`[M]` **Las dos alturas no son parche agudo y grave: son dos superficies.** La
partitura (*Bombo «gopeador» o Macho-Currulao*, Javier Martínez / Wilmer Vente)
lo dice expreso — «la mano izquierda toca en la madera la X y la derecha el
cuero del bombo». Las cabezas en X son madera.

Y el transcriptor lo escribió con semántica GM, así que el MIDI ya lo traía:
`C#2 = 37` es el **side stick**, el golpe seco en el aro, y `C2 = 36` es el
**bombo**. El primer mapeo lo mandó a dos toms y borró justo lo que distingue el
golpe. **El dato estaba en el archivo y se perdió al interpretarlo**, no al
medirlo.

`[D]` Su onomatopeya es **«Con la orquesta dele duro»**, como el *papa con yuca*
del bambuco: ocho sílabas sobre dos compases de cuatro golpes. El reparto por
corchea es deducido del texto bajo el pentagrama.

Tres golpes altos y **el grave en la sexta corchea**, que es exactamente donde el
bambuco de salón calla. Los dos géneros reparten las mismas seis corcheas y se
separan en esa nota: uno respira ahí y el otro apoya. Eso no es una observación
de oído — sale de comparar dos tablas de ataques medidas por separado.

`[M]` **Es 6/8, y esta vez la notación coincide con la célula**: las cinco
partituras de currulao vienen en 6/8. Se escribe así en el aparato, que lo
admite — el byte 14 codifica el denominador con `2` para `/8`. Antes `cmd_andina`
lo tenía fijo en `/4` y habría escrito 3/4 sobre una célula de seis corcheas:
suena igual, pero la máquina cuenta los compases de otra forma en modo canción.

**Lo melódico no se genera.** La marimba da 13 % de repetición y la guitarra 4 %:
son arreglos, no células, igual que el porro y el chandé. El motor pone la
percusión y la armonía; la marimba entra por el EP–40 desde la partitura o
tocada en vivo.

Pesa **5,2 KB**, el más barato de los ocho géneros andinos.

## El mapalé — un ostinato que oscila de octava

`[M]` De `mapale-ashcolom.mid`, transcripción para piano a dos manos. La celda
del acompañamiento, en semicorcheas de medio compás:

```
semicorchea    1    2    3    4    5    6    7    8
ataques      142    0    0  120   10  120    0    0
```

Ataques en la **1, la 4 y la 6** — intervalos de **3+2+3**. Y las alturas dicen
algo que el recuento por sí solo no ve:

```
compás 71   sc1 D3   sc4 D4   sc6 D3
compás 72   sc1 D4   sc4 D3   sc6 D4
```

**La octava alterna en cada golpe.** Como son tres por compás, el ciclo se
invierte al siguiente y vuelve al tercero. No es un pedal quieto: es una
oscilación de octava sobre una rejilla fija, y ese desfase de dos compases es lo
que lo hace respirar.

`[M]` La armonía casi no se mueve: **126 compases sobre Re, 14 sobre Fa y uno
sobre La**, con 29 cambios en 141 compases. Es un género de ostinato.

`[V]` **El compás y el tempo no cuadran entre fuentes.** La transcripción de
piano va a 100 en 4/4; el catálogo de Tribe da 180 en 2/2; el plan del directo
dice 202,7. La partitura de clarinete de *La Mecedora* (José Camilo Gómez) está
en **compasillo partido**, lo que apoya el 2/2. Lo más probable es que la
transcripción de piano esté escrita a mitad de tiempo — 100 × 2 = 200, cerca de
202,7 — pero no está comprobado.

`[V]` **La percusión no está en ninguna de las dos fuentes.** Lo medido es la
célula del acompañamiento y la armonía, no los tambores, que en este género son
la mitad del asunto.

> **Cuidado con las partituras de clarinete.** *La Mecedora* está escrita para
> **clarinete en si bemol**, que es transpositor: lo escrito suena **una segunda
> mayor más grave**. Tomar sus alturas tal cual pondría la pieza un tono arriba,
> y sonaría perfectamente bien en el tono equivocado — el error no se oye si no
> hay nada con qué comparar.

## El conjunto de marimba, según la fuente académica

De la tesis de **Paz Hernández (2005)**, *Producción musical contemporánea
utilizando las células rítmicas del Pacífico colombiano* (San Buenaventura,
Bogotá) — asesorada por **Javier Martínez Maya**, el mismo que firma la
partitura del bombo golpeador. Está en
`manuales-md/Paz2005_Celulas_Ritmicas_Pacifico.md`.

`[M]` **La marimba de chonta son 24 tablillas y dos instrumentos en uno:**

```
16 tablillas cortas   el TIPLERO      la melodía
 8 tablillas largas   el BORDONERO    el acompañamiento
```

Cuatro bolillos en manos de **dos tocadores**. Eso corrige un intercambio
anterior en el proyecto: al medir 4 voces solapadas en la transcripción de Tribe
se objetó que con dos golpeadores no era posible, y sobre *esa* transcripción era
cierto —solo trae la parte del tiplero, y su máximo de ataques simultáneos es 2—
pero **en el instrumento real cuatro golpes a la vez sí son posibles**. La
objeción era correcta sobre la fuente y equivocada sobre el instrumento.

Consecuencia para el muestreo al EP–40: las 34 tablillas que se muestrearon de
Tribe cubren el ámbito entero, pero **el instrumento tiene dos registros con
funciones distintas**. Al escribirle material conviene tratarlos como dos voces
—melodía arriba, acompañamiento abajo— y no como un teclado uniforme.

`[M]` **El conjunto completo**: marimba de chontas, dos cununos (macho y
hembra), dos bombos (**golpeador** y **arrullador**), redoblante y guasás. La
propia tesis, al producir en estudio, **graba congas emulando los cununos**
—porque el cununo es difícil de conseguir y de microfonear— y usa arrullador y
tambora reales. Es la misma decisión que tenemos delante con el EP–40: qué se
muestrea de verdad y qué se sustituye.

## La matriz métrica — lo que hacíamos tenía nombre

De **`Pitos y tambores`, cartilla de iniciación musical de Victoriano Valencia**
(Plan Nacional de Música para la Convivencia, Ministerio de Cultura).

> *Dos matrices métricas reúnen los diferentes ritmos del eje de pitos y
> tambores. Una, **binaria, de ocho eventos** definidos por acento, pulso,
> primera división y segunda división. La otra, **ternaria, de seis eventos**.*

**Las tablas de ataques que este proyecto lleva midiendo son exactamente eso.**
La ternaria de seis para el bambuco, el currulao y el torbellino; la binaria de
ocho para el mapalé, el chandé y la cumbia. Se llegó al mismo aparato analítico
por medición, sin saber que la pedagogía colombiana ya lo tenía formalizado y le
había puesto nombre.

`[M]` **Y la convención de la X está documentada.** La cartilla da la clave de
notación de la tambora:

```
♩    abierto o cuero — golpe con baqueta en parche
♩̣    tapado — se percute presionando con la punta de la baqueta
✗    MADERA — percusión en el vaso de la tambora
⊗    aro
```

> *«Ejemplo de escritura a dos planos. **Arriba madera y abajo cuero**.»*

Así que la lectura de la partitura del bombo golpeador —cabezas en X para la
madera— **no era una nota al pie de aquel documento sino el estándar**. Eso
respalda el mapeo del currulao con una fuente pedagógica, no con una inferencia.

## La cumbia, de la cartilla del Ministerio

`[M]` Las alineaciones sobre la matriz binaria, tal como las da la cartilla:

```
matriz binaria    1   2   3   4   5   6   7   8
palmas (pulso)    X               X
llamador                  X               X        contratiempo
guacho            X       X       X       X
alegre            X   X   X   X   X   X   X   X    «reproduce la matriz»
```

El alegre tocando los ocho eventos es el patrón básico de **cumbia tipo
soledeña**. El llamador a contratiempo es lo que hace que una cumbia sea una
cumbia.

`[V]` **La tambora necesita «matriz doble»** —dieciséis eventos— y no está
implementada: sus variaciones ocupan una página entera de la cartilla y merecen
medirse aparte.

`[D]` **El bajo no viene en la cartilla**, que es material de percusión. El del
motor es una línea sencilla en el pulso, deducida.

## El Pacífico Sur son DOS sistemas, y el currulao es uno

De **`¡Qué te pasa vo! Canto de piel, semilla y chonta`**, cartilla de Músicas
del Pacífico Sur (Duque, Sánchez y Tascón — Plan Nacional de Música para la
Convivencia). La hermana de *Pitos y tambores*, para marimba, cununos, guasá y
bombos.

`[M]` **La taxonomía**, que cambia cómo hay que pensar el repertorio:

```
sistema bunde       aires en 2/4
sistema currulao    aires en 6/8    currulao, berejú, patacoré, pango, juga
```

No son géneros sueltos que casualmente comparten célula: **son aires de un mismo
sistema**, y por eso la comparten. Confirma el 6/8 del currulao con fuente
pedagógica, no solo con la partitura.

`[M]` **La onomatopeya es «Déle duro», y corrige lo anotado antes.** Cuatro
sílabas, un compás, un golpe cada una:

```
corchea    1     2     3     4     5     6
sílaba    Dé          le    du          ro
golpe   madera     madera madera     cuero
pulso     ●                 ●
```

Se había deducido «Con la orquesta dele duro» del texto bajo el pentagrama de la
partitura del bombo, repartido en ocho sílabas sobre dos compases. La cartilla
dice que **la base simple es un compás**; la frase larga es otra cosa.

Y encaja con lo medido por otra vía: *«cada base simple cuenta con dos pulsos…
los pulsos coinciden con los golpes en la madera»*. En 6/8 los pulsos son las
corcheas 1 y 4, y las dos son madera en la célula medida. La cartilla añade que
se aplaude o zapatea **sobre la sílaba «ro»**, que es el golpe de cuero de la
sexta.

`[V]` **El ciclo son cuatro compases, no uno**: *«base simple del bombo ×3 +
variación»*. La fuente que medimos traía dieciséis compases idénticos porque es
la base aislada; en la práctica **cada cuarto compás lleva variación**. La
variación está notada en la cartilla pero no se ha transcrito — el motor
`Currulao` toca la base sola, que es correcto pero incompleto.
