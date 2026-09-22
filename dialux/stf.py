"""Escribir ficheros STF para importarlos en DIALux evo (Archivo → Importar → Archivo STF…).

STF es el formato de intercambio de DIAL para la envolvente del edificio: estancias con su
contorno, altura, plano de trabajo, reflectancias, puertas y ventanas, y luminarias colocadas.
Se eligió frente a IFC porque **IFC en DIALux evo 14 es de la versión PRO** (visto en el menú de
Marcos el 20/9/2026) y STF no.

**La especificación no es pública, pero DIAL la manda por correo a quien la pide**: Marcos la
recibió el 22/9/2026 (STF 1.0.5, marzo de 2009) y está en `material/`, fuera de git porque el
documento va marcado como confidencial. Lo que este módulo escribe sigue esa especificación;
antes estaba deducido de dos exportadores de código abierto y por eso el factor de mantenimiento
se escribía con un nombre inventado y DIALux lo ignoraba.

Dos límites del formato, ya confirmados por el documento y no por sondeos: una sala es un
polígono 2D con suelo y techo planos, **sin nivel de planta**, y **no hay zona marginal**. Los
muebles corrientes (una columna) se escriben pero DIALux no los lee al importar; las ventanas y
las puertas sí.

Unidades: metros y grados. El origen es la esquina de la planta.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

VERSION_STF = "1.0.5"

# Material de ventanas y puertas: reflexión y color RGB, en el formato de la especificación.
COLOR_HUECO = "52 215 164 63"


@dataclass
class Luminaria:
    nombre: str
    posicion: tuple[float, float, float]
    rotacion: tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass
class Abertura:
    """Una ventana o una puerta en una pared de la sala.

    En STF son "muebles" con nombre reservado (`win`, `door`, `skylight`), y son lo único de los
    muebles que DIALux lee al importar. Su origen es el punto medio de su anchura, a ras del
    suelo del hueco, y DIALux los pega a la pared más cercana: la rotación la ignora.
    """
    tipo: str            # "ventana" o "puerta"
    centro_m: tuple[float, float]
    ancho_m: float
    alto_m: float
    alfeizar_m: float = 0.0

    @property
    def palabra(self) -> str:
        return "win" if self.tipo == "ventana" else "door"


@dataclass
class Estancia:
    nombre: str
    contorno: list[tuple[float, float]]
    altura_m: float
    plano_trabajo_m: float = 0.85
    reflectancia_techo: float | None = None
    reflectancia_paredes: float | None = None
    reflectancia_suelo: float | None = None
    factor_mantenimiento: float | None = None
    luminarias: list[Luminaria] = field(default_factory=list)
    aberturas: list[Abertura] = field(default_factory=list)

    def validar(self) -> None:
        if len(self.contorno) < 3:
            raise ValueError(f"La estancia '{self.nombre}' necesita al menos 3 puntos de contorno.")
        if self.altura_m <= 0:
            raise ValueError(f"La altura de '{self.nombre}' tiene que ser mayor que 0.")
        if self.plano_trabajo_m >= self.altura_m:
            raise ValueError(
                f"En '{self.nombre}' el plano de trabajo ({self.plano_trabajo_m} m) no puede estar "
                f"por encima del techo ({self.altura_m} m).")


# Distancia por debajo de la cual un vértice de otra sala se considera "sobre" esta pared.
TOLERANCIA = 0.001  # m


def _vertices_de_vecinos(estancias: list[Estancia]) -> None:
    """Parte cada pared por los vértices de las salas vecinas que caen encima.

    Medido en DIALux evo 14 el 20/9/2026: con tres salas en un rectángulo, el pasillo cuya pared
    inferior tocaba a la oficina Y a los aseos se importaba con una diagonal cruzándolo de esquina
    a esquina. La forma era correcta; lo que faltaba era un vértice en (8, 6), donde acaba la
    pared entre las dos salas de abajo. Con ese punto, la planta entra limpia.
    """
    ajenos = {p for e in estancias for p in e.contorno}
    for estancia in estancias:
        contorno = estancia.contorno
        nuevo: list[tuple[float, float]] = []
        for (ax, ay), (bx, by) in zip(contorno, contorno[1:] + contorno[:1]):
            nuevo.append((ax, ay))
            dx, dy = bx - ax, by - ay
            largo2 = dx * dx + dy * dy
            if largo2 == 0:
                continue
            encima = []
            for (px, py) in ajenos:
                t = ((px - ax) * dx + (py - ay) * dy) / largo2
                if not 0 < t < 1:
                    continue
                if abs((px - ax) - t * dx) < TOLERANCIA and abs((py - ay) - t * dy) < TOLERANCIA:
                    encima.append((t, (px, py)))
            nuevo += [punto for _, punto in sorted(encima)]
        estancia.contorno = nuevo


def _num(valor: float) -> str:
    return f"{valor:.3f}".rstrip("0").rstrip(".") or "0"


def escribir(estancias: list[Estancia], destino: str | Path, proyecto: str = "MCP_Dialux",
             autor: str = "MCP_Dialux") -> Path:
    """Escribe el STF y devuelve su ruta. Una sección [ROOM.Rn] por estancia."""
    if not estancias:
        raise ValueError("No hay ninguna estancia que escribir.")
    for e in estancias:
        e.validar()
    _vertices_de_vecinos(estancias)

    claves = [f"ROOM.R{i}" for i, _ in enumerate(estancias, start=1)]
    materiales: list[list[str]] = []
    lineas = ["[VERSION]", f"STFF={VERSION_STF}", "Progname=MCP_Dialux", "Progvers=0.1", "",
              "[Project]", f"Name={proyecto}", f"Date={date.today():%Y-%m-%d}",
              f"Operator={autor}", f"NrRooms={len(estancias)}"]
    lineas += [f"Room{i}={clave}" for i, clave in enumerate(claves, start=1)]

    for clave, e in zip(claves, estancias):
        lineas += ["", f"[{clave}]", f"Name={e.nombre}", f"Height={_num(e.altura_m)}",
                   f"WorkingPlane={_num(e.plano_trabajo_m)}", f"NrPoints={len(e.contorno)}"]
        lineas += [f"Point{i}={_num(x)} {_num(y)}" for i, (x, y) in enumerate(e.contorno, start=1)]
        for etiqueta, valor in (("R_Ceiling", e.reflectancia_techo),
                                ("R_Floor", e.reflectancia_suelo)):
            if valor is not None:
                lineas.append(f"{etiqueta}={_num(valor)}")
        if e.reflectancia_paredes is not None:
            # R_Wall<n> es la pared entre el punto n y el n+1: una por tramo, no una para todas.
            for i in range(1, len(e.contorno) + 1):
                lineas.append(f"R_Wall{i}={_num(e.reflectancia_paredes)}")
        if e.factor_mantenimiento is not None:
            # "MF", no "MaintenanceFactor": ese nombre me lo inventé y DIALux lo ignoraba en
            # silencio, así que las salas entraban con el factor por defecto (0,8) y no con el
            # del enunciado. Corregido el 22/9/2026 con la especificación oficial delante.
            lineas.append(f"MF={_num(e.factor_mantenimiento)}")
        lineas.append(f"NrLums={len(e.luminarias)}")
        for i, lum in enumerate(e.luminarias, start=1):
            lineas += [f"Lum{i}={lum.nombre}",
                       f"Lum{i}.Pos={' '.join(_num(v) for v in lum.posicion)}",
                       f"Lum{i}.Rot={' '.join(_num(v) for v in lum.rotacion)}"]
        lineas.append("NrStruct=0")
        lineas.append(f"NrFurns={len(e.aberturas)}")
        for i, hueco in enumerate(e.aberturas, start=1):
            x, y = hueco.centro_m
            lineas += [f"Furn{i}={hueco.palabra}",
                       f"Furn{i}.Ref={clave}.F{i}",
                       f"Furn{i}.Pos={_num(x)} {_num(y)} {_num(hueco.alfeizar_m)}",
                       f"Furn{i}.Rot=0 0 0",
                       # El tamaño en z de una ventana o una puerta se ignora, pero la
                       # especificación pide escribirlo igualmente.
                       f"Furn{i}.Size={_num(hueco.ancho_m)} {_num(hueco.alto_m)} 0"]
            materiales.append([f"[{clave}.F{i}]", f"Poly.Color={COLOR_HUECO}"])

    for material in materiales:
        lineas += [""] + material

    ruta = Path(destino).expanduser().with_suffix(".stf")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    # Fin de línea de Windows y latin-1: es un formato de intercambio antiguo y DIALux evo corre
    # en Windows. Si algún acento se ve mal al importar, aquí es donde se cambia.
    ruta.write_text("\r\n".join(lineas) + "\r\n", encoding="latin-1", errors="replace")
    return ruta


def rectangulo(ancho_m: float, largo_m: float, x0: float = 0.0, y0: float = 0.0
               ) -> list[tuple[float, float]]:
    return [(x0, y0), (x0 + ancho_m, y0), (x0 + ancho_m, y0 + largo_m), (x0, y0 + largo_m)]
