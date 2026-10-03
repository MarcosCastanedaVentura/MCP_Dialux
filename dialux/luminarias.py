"""Repartir luminarias en retícula dentro de una sala.

Esto es la MITAD del trabajo con luminarias: **dónde van**, no **cuántas hacen falta**. El número
sale del cálculo luminotécnico, y para eso hace falta la fotometría de la luminaria (.ldt o .ies),
que todavía no está (ver `progress.md`). Aquí se recibe el número y se coloca.

El reparto es el de siempre en un alumbrado general: la sala se divide en `nx` × `ny` casillas
iguales y la luminaria va en el centro de cada una. Eso deja las filas de los bordes a media
separación del muro (`e/2`), que es la regla clásica para que la iluminación no se caiga en los
extremos.

Cuando el número pedido no forma una retícula (7, por ejemplo), se sube al `nx` × `ny` más cuadrado
que lo contenga y **se avisa**: con más luminarias de las calculadas sale más luz de la prevista, y
eso hay que saberlo antes de comparar con lo que exige la norma.

Lo que aquí NO se decide: si la separación que sale es admisible. Eso depende de la curva de
distribución de la luminaria (de su fichero fotométrico), así que se devuelve la relación entre la
separación y la altura útil y se deja el juicio a quien tenga la curva delante.
"""

from __future__ import annotations

import math

from shapely import Point, Polygon

# Margen para no dar por buena una posición que cae justo encima de un muro al recortar una sala
# que no es rectangular.
TOLERANCIA = 0.01  # m


def reparto(ancho_m: float, largo_m: float, cuantas: int) -> tuple[int, int]:
    """Cuántas filas y columnas para repartir `cuantas` luminarias en una sala de ese tamaño.

    Se busca la retícula que cumpla dos cosas a la vez: que las casillas salgan lo más cuadradas
    posible (separación parecida en x y en y) y que sobren las menos luminarias posibles. Las dos
    medidas son relativas, así que el resultado no cambia con las unidades ni con el tamaño de la
    sala: en una sala de 10 × 4 m, 12 luminarias salen 6 × 2 y no 5 × 3, que dejaría tres de más.
    """
    if cuantas < 1:
        raise ValueError("Hacen falta al menos 1 luminaria para repartirlas.")
    if ancho_m <= 0 or largo_m <= 0:
        raise ValueError("La sala tiene que medir algo en los dos lados.")

    mejor: tuple[float, tuple[int, int]] | None = None
    for nx in range(1, cuantas + 1):
        ny = math.ceil(cuantas / nx)
        ex, ey = ancho_m / nx, largo_m / ny
        coste = (nx * ny / cuantas) * (max(ex, ey) / min(ex, ey))
        if mejor is None or coste < mejor[0] - 1e-9:
            mejor = (coste, (nx, ny))
    assert mejor is not None
    return mejor[1]


def reticula(contorno: list[tuple[float, float]], cuantas: int, altura_montaje_m: float,
             plano_trabajo_m: float = 0.0, zona_marginal_m: float = 0.0) -> dict:
    """Las posiciones de `cuantas` luminarias repartidas por una sala, y qué revisar del reparto.

    `contorno` en metros y en las mismas coordenadas que va a llevar el fichero STF, para que las
    posiciones que salen se puedan escribir tal cual. `altura_montaje_m` es la altura a la que
    cuelgan, medida desde el suelo de la sala.
    """
    sala = Polygon(contorno)
    if not sala.is_valid or sala.area <= 0:
        raise ValueError("El contorno de la sala no encierra ninguna superficie.")
    altura_util = altura_montaje_m - plano_trabajo_m
    if altura_util <= 0:
        raise ValueError(
            f"Las luminarias ({altura_montaje_m} m) tienen que quedar por encima del plano de "
            f"trabajo ({plano_trabajo_m} m).")

    x0, y0, x1, y1 = sala.bounds
    nx, ny = reparto(x1 - x0, y1 - y0, cuantas)
    ex, ey = (x1 - x0) / nx, (y1 - y0) / ny

    # Una sala en L no llena su rectángulo: las posiciones que caen en el trozo que falta se
    # quitan, porque una luminaria fuera de la sala la mete DIALux en el muro de al lado.
    dentro = sala.buffer(-TOLERANCIA)
    posiciones, fuera = [], 0
    for j in range(ny):
        for i in range(nx):
            x, y = x0 + (i + 0.5) * ex, y0 + (j + 0.5) * ey
            if dentro.contains(Point(x, y)):
                posiciones.append((round(x, 3), round(y, 3), round(altura_montaje_m, 3)))
            else:
                fuera += 1

    avisos = []
    if nx * ny != cuantas:
        avisos.append(
            f"{cuantas} luminarias no forman una retícula en esta sala; la más cuadrada que las "
            f"contiene es {nx} × {ny} = {nx * ny}. Van {nx * ny}, así que habrá MÁS luz de la "
            f"calculada para {cuantas}: rehaz el cálculo con {nx * ny} antes de darlo por bueno.")
    if fuera:
        avisos.append(
            f"La sala no es rectangular: {fuera} posicion(es) de la retícula caían fuera y se han "
            f"quitado, así que quedan {len(posiciones)} y el reparto ya no es regular. Míralo en "
            "DIALux antes de calcular.")
    if zona_marginal_m and min(ex, ey) / 2 < zona_marginal_m:
        avisos.append(
            f"Las luminarias de los bordes quedan a {min(ex, ey) / 2:.2f} m del muro, dentro de la "
            f"zona marginal de {zona_marginal_m:g} m. Es correcto (la zona marginal es de la "
            "superficie de cálculo, no de las luminarias), pero compruébalo con el enunciado.")

    return {
        "pedidas": cuantas,
        "colocadas": len(posiciones),
        "reticula": f"{nx} × {ny}",
        "separacion_x_m": round(ex, 3),
        "separacion_y_m": round(ey, 3),
        "distancia_a_pared_x_m": round(ex / 2, 3),
        "distancia_a_pared_y_m": round(ey / 2, 3),
        "altura_montaje_m": round(altura_montaje_m, 3),
        "altura_util_m": round(altura_util, 3),
        # Separación mayor dividida por la altura útil: es lo que se compara con el criterio de
        # separación de la luminaria, que viene en su fotometría. Aquí solo se da el número.
        "separacion_entre_altura_util": round(max(ex, ey) / altura_util, 2),
        "posiciones_m": posiciones,
        "avisos": avisos,
    }
