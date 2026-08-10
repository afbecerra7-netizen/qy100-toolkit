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

