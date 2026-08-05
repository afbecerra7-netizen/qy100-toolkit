"""Extrae la lista de frases preset del Data List (QY100E2.pdf, pp. 16-34).

La pagina no es una tabla lineal: cada categoria se subdivide por *beat*
(8 beat, 16 beat, 3/4 beat...), y **los bloques de beat van uno al lado del
otro en columnas**, cada uno con su numeracion empezando de nuevo en 001. Un
bloque puede ocupar varias columnas `No./Name`.

    Beat=3/4 beat        Beat=8 beat                           Beat=16 beat
     No.   Name           No.   Name       No.   Name           No.   Name
     001   JzWlz-I        001   70sRk-E    065   Ska -2c        001   FnkRk-I

Leer el texto por lineas sin mirar la posicion horizontal mezcla los tres
bloques y, al indexar por (categoria, numero), las numeraciones repetidas se
pisan unas a otras: salen 2.197 frases en vez de 4.285.

La solucion es geometrica. Cada cabecera `Beat=` marca el borde izquierdo de
su bloque, asi que cada par `No. Name` pertenece al beat cuya cabecera es la
mas cercana por la izquierda. Con `pdftotext -layout` las columnas conservan
su posicion en caracteres, que es toda la geometria que hace falta.

**La cabecera `Phrase Category=` tampoco manda sobre la pagina entera**: no
esta arriba a la izquierda sino justo encima del bloque `8 beat`, y cuando el
bloque `3/4 beat` de una categoria no cabe se desborda a la columna izquierda
de la pagina siguiente, *antes* de esa cabecera. Un bloque situado a la
izquierda de la cabecera pertenece por tanto a la categoria **anterior**. Pasa
en tres sitios: p19 (3/4 de Bb), p20 (3/4 de BR) y p28 (3/4 de GR).

Leerlo como "la categoria de la pagina" mete esos tres bloques en la categoria
equivocada, donde chocan con el 3/4 que esa categoria ya tiene: 13 frases se
pisan en silencio. El manual del usuario (p. 54) confirma que la terna
categoria + tiempo de compas + numero es la direccion con la que el equipo
selecciona una frase, asi que no puede haber dos bloques con la misma clave.

La comprobacion de que el reparto es correcto es que cada bloque quede
numerado 001..N sin huecos ni repeticiones: si una frase cae en el bloque
equivocado, deja un agujero en uno y un duplicado en el otro.
"""
import os
import json
import re
import subprocess
import sys

PDF = os.environ.get("QY100_DATALIST", "QY100E2.pdf")   # no incluido: es de Yamaha
PRIMERA, ULTIMA = 16, 34

CAT_RE = re.compile(r"Phrase Category=(\w+):\s*(.+?)\s*$")
BEAT_RE = re.compile(r"Beat=(\S+(?:\s+beat)?)")
# Un par "No. Name": el numero, espacios, y el nombre hasta la siguiente
# columna (dos o mas espacios seguidos de otro numero) o el fin de linea.
#
# Se admiten dos digitos ademas de tres por una errata del propio manual: la
# primera frase del bloque GR / 3/4 beat (p. 28, `R&BWz-I`) esta impresa como
# `01` y no como `001`. Exigiendo tres digitos se pierde, y con ella la unica
# frase que separaba el recuento extraido de las 4.285 que declara Yamaha.
PAR_RE = re.compile(r"(\d{2,3})\s+(\S.{0,9}?)(?=\s{2,}\d{2,3}\s|\s*$)")
TOLERANCIA = 3          # margen en caracteres al asignar columna a bloque


def texto(pagina):
    return subprocess.run(
        ["pdftotext", "-f", str(pagina), "-l", str(pagina), "-layout", PDF, "-"],
        capture_output=True, text=True, check=True).stdout


def extraer():
    """Devuelve [(categoria, descripcion, beat, numero, nombre), ...]."""
    filas = []
    actual = None                       # (codigo, descripcion) vigente
    for pagina in range(PRIMERA, ULTIMA + 1):
        lineas = texto(pagina).splitlines()

        # La cabecera de categoria de esta pagina, si la hay, con su posicion:
        # solo abre categoria para los bloques que quedan a su derecha.
        nueva, nueva_x = None, None
        for linea in lineas:
            m = CAT_RE.search(linea)
            if m:
                nueva, nueva_x = (m.group(1), m.group(2)), m.start()
                break

        bloques = []                    # (x, beat, categoria) de esta pagina
        for linea in lineas:
            if CAT_RE.search(linea):
                continue
            encontrados = [(m.start(), m.group(1)) for m in BEAT_RE.finditer(linea)]
            if encontrados:
                bloques = []
                for x, beat in sorted(encontrados):
                    # A la izquierda de la cabecera => categoria anterior.
                    if nueva and x + TOLERANCIA >= nueva_x:
                        bloques.append((x, beat, nueva))
                    elif actual:
                        bloques.append((x, beat, actual))
                continue
            if not bloques:
                continue
            for m in PAR_RE.finditer(linea):
                nombre = m.group(2).strip()
                if not nombre or nombre.isdigit():
                    continue
                # El bloque cuya cabecera queda mas cerca por la izquierda.
                x = m.start()
                candidatos = [b for b in bloques if b[0] <= x + TOLERANCIA]
                if not candidatos:
                    continue
                _x, beat, (cat, desc) = candidatos[-1]
                filas.append((cat, desc, beat, int(m.group(1)), nombre))

        # Una categoria puede continuar en la pagina siguiente sin repetir su
        # cabecera (Ba sigue en la 17, KC en la 29...).
        if nueva:
            actual = nueva
    return filas


def validar(filas):
    """Cada bloque (categoria, beat) tiene que ir 001..N sin huecos.

    Los duplicados se comprueban aparte porque un numero repetido no deja
    hueco: una frase mal atribuida se limita a pisar a otra, y el recuento
    sigue pareciendo correcto. Es como se colaron 13 durante la extraccion.
    """
    bloques = {}
    for cat, _desc, beat, num, nombre in filas:
        bloques.setdefault((cat, beat), {}).setdefault(num, []).append(nombre)
    problemas = []
    for (cat, beat), numeros in sorted(bloques.items()):
        faltan = sorted(set(range(1, max(numeros) + 1)) - set(numeros))
        if faltan:
            problemas.append("%s / %s: faltan %s de %d"
                             % (cat, beat, faltan[:6], max(numeros)))
        for num, nombres in sorted(numeros.items()):
            if len(nombres) > 1:
                problemas.append("%s / %s / %03d: repetida -> %s"
                                 % (cat, beat, num, nombres))
    plano = {k: {n: v[0] for n, v in d.items()} for k, d in bloques.items()}
    return plano, problemas


if __name__ == "__main__":
    filas = extraer()
    bloques, problemas = validar(filas)

    print("%-4s %-32s %-12s %s" % ("cat", "descripcion", "beat", "frases"))
    total = 0
    for (cat, beat), numeros in bloques.items():
        desc = next(f[1] for f in filas if f[0] == cat)
        total += len(numeros)
        print("%-4s %-32s %-12s %4d" % (cat, desc, beat, len(numeros)))
    print("\nTOTAL %d frases en %d bloques" % (total, len(bloques)))

    if problemas:
        print("\nHUECOS EN LA NUMERACION:")
        for p in problemas:
            print("  " + p)
        sys.exit(1)
    print("numeracion contigua en los %d bloques" % len(bloques))

    if "--md" in sys.argv:
        import collections
        orden = ["8 beat", "16 beat", "3/4 beat"]
        cats = collections.OrderedDict()
        for cat, desc, beat, num, nombre in filas:
            cats.setdefault((cat, desc), {}).setdefault(beat, {})[num] = nombre

        L = []
        L.append("# QY100 — Lista de frases predefinidas\n")
        L.append("Conversion de la *Preset Phrase List* del **Data List** "
                 "(`QY100E2.pdf`, pp. %d-%d),\ngenerada por "
                 "[`extraer_frases.py`](../qy100-syx/extraer_frases.py). "
                 "**%d frases** en %d bloques.\n" % (PRIMERA, ULTIMA, total, len(bloques)))
        L.append("## Como se selecciona una frase\n")
        L.append("El numero de frase tiene **tres campos** y el cursor se "
                 "posa en cualquiera de ellos\n(manual del usuario p. 54):\n")
        L.append("    categoria  +  tiempo de compas  +  numero\n")
        L.append("El tiempo de compas solo toma tres valores — `8 beat`, "
                 "`16 beat`, `3/4 beat` — y el\nrango del numero **cambia con "
                 "cada combinacion**: no es una lista plana de 1 a 4.285.\n")
        L.append("Para llevar una frase predefinida a una pista se usa el "
                 "**Job 15, *Copiar frase***,\nque la copia como frase de "
                 "usuario en D1, D2, PC, BA o C1-C4. Si es mas corta que el\n"
                 "patron se repite hasta llenarlo; si es mas larga se corta; "
                 "y **borra lo que hubiera**\nen la pista de destino.\n")
        L.append("Eso la convierte en el puente con el trabajo por SysEx de "
                 "este repositorio: copiar una\nfrase de fabrica a una pista y "
                 "volcarla permite leer los eventos que Yamaha escribio,\ncon "
                 "el formato ya descifrado en "
                 "[`patternfmt.py`](../qy100-syx/qy100syx/patternfmt.py).\n")

        L.append("## El sufijo dice para que seccion es la frase\n")
        L.append("Los nombres terminan siempre en uno de seis sufijos, y "
                 "coinciden en numero con las\nseis secciones del QY100:\n")
        L.append("| Sufijo | Seccion |\n| --- | --- |")
        for s, sec in (("-I", "INTRO"), ("-a", "MAIN A"), ("-b", "MAIN B"),
                       ("-c", "FILL AB"), ("-d", "FILL BA"), ("-E", "ENDING")):
            L.append("| `%s` | %s |" % (s, sec))
        L.append("\nNo es una lectura de los nombres sino un resultado de los "
                 "datos: las categorias de\n**relleno** (`Fa`, `Fb`) son casi "
                 "exclusivamente `-c` y `-d`, mientras que las de bateria\n"
                 "principal (`Da`, `Db`) son casi exclusivamente `-I`, `-a`, "
                 "`-b` y `-E`. Si el sufijo no\nindicara la seccion, no habria "
                 "razon para que se repartieran asi.\n")
        L.append("Un sufijo puede llevar delante un digito (`-1a`, `-2a`, "
                 "`-3a`) cuando el estilo ofrece\nvarias frases para la misma "
                 "seccion. De los 863 estilos, 283 traen el juego completo\n"
                 "de seis; el resto solo algunas secciones.\n")
        L.append("Los nombres ocupan **8 caracteres** rellenados con espacios "
                 "(`Mixt -I`, `R&B -I`), que es\nlo que cabe en la pantalla.\n")

        L.append("## Categorias\n")
        L.append("| Cod | Categoria | 8 beat | 16 beat | 3/4 beat | Total |")
        L.append("| --- | --- | ---: | ---: | ---: | ---: |")
        for (cat, desc), beats in cats.items():
            n = [len(beats.get(b, {})) for b in orden]
            L.append("| `%s` | %s | %s | **%d** |"
                     % (cat, desc, " | ".join(str(x) if x else "—" for x in n),
                        sum(n)))
        L.append("")
        L.append("> El bloque `GR` / `3/4 beat` empieza en `01` y no en `001` "
                 "en el PDF original\n> (p. 28). Es una errata del manual; "
                 "aqui va normalizada a `001`.\n")

        L.append("## Listado completo\n")
        for (cat, desc), beats in cats.items():
            L.append("### %s — %s\n" % (cat, desc))
            for beat in orden:
                fr = beats.get(beat)
                if not fr:
                    continue
                L.append("#### %s (%d)\n" % (beat, len(fr)))
                L.append("```")
                fila = []
                for num in sorted(fr):
                    fila.append("%03d %-8s" % (num, fr[num]))
                    if len(fila) == 4:
                        L.append("   ".join(fila).rstrip()); fila = []
                if fila:
                    L.append("   ".join(fila).rstrip())
                L.append("```\n")

        destino = "QY100_Frases_Preset.md"
        with open(destino, "w") as fh:
            fh.write("\n".join(L) + "\n")
        print("escrito %s" % destino)

    if "--json" in sys.argv:
        salida = {
            "fuente": "QY100E2.pdf (Data List) pp. %d-%d" % (PRIMERA, ULTIMA),
            "total": total,
            "categorias": {},
        }
        for cat, desc, beat, num, nombre in filas:
            c = salida["categorias"].setdefault(cat, {"nombre": desc, "beats": {}})
            c["beats"].setdefault(beat, {})["%03d" % num] = nombre
        destino = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frases.json")
        with open(destino, "w") as fh:
            json.dump(salida, fh, indent=1, ensure_ascii=False, sort_keys=True)
        print("escrito %s" % destino)
