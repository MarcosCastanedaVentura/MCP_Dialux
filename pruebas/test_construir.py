"""Del examen al STF, con los planos reales de clase."""

from pathlib import Path

import pytest

from dialux.construir import plano_a_stf

EXAMENES = Path(__file__).resolve().parents[1] / "material" / "examenes"


def _plano(nombre: str):
    ruta = EXAMENES / nombre
    if not ruta.is_file():
        pytest.skip(f"falta {ruta.name} en material/examenes/")
    return ruta


def test_sin_la_altura_no_se_escribe_nada(tmp_path):
    # El examen de junio no dice la altura en ningún texto: inventarla es el invariante 3.
    salida = plano_a_stf(_plano("ExamenFinal-Junio-Dialux-26.dwg"), carpeta_destino=tmp_path)
    assert salida["escrito"] is False
    assert len(salida["faltan"]) == 7
    assert not list(tmp_path.glob("*.stf"))


def test_las_plantas_van_en_un_stf_y_separadas(tmp_path):
    """Importar un segundo STF sustituye el proyecto en vez de añadirse (evo 14, 20/9/2026), y
    dejadas en su sitio real las plantas se solaparían: por eso una al lado de otra."""
    salida = plano_a_stf(_plano("ExamenFinal-Junio-Dialux-26.dwg"), altura_m=3,
                         carpeta_destino=tmp_path)
    assert salida["escrito"] and salida["cotas"] == "6 de 6"
    assert [p["planta"] for p in salida["plantas"]] == ["SEGUNDA PLANTA", "TERCERA PLANTA"]
    assert len(salida["plantas"][0]["estancias"]) == 5
    assert len(list(tmp_path.glob("*.stf"))) == 1

    segunda, tercera = salida["plantas"]
    assert segunda["desplazada_x_m"] == 0.0
    # 23,365 de ancho + 5 de separación = 28,365, redondeado a 30 para restarlo a mano sin errar.
    assert tercera["desplazada_x_m"] == 30.0

    texto = Path(salida["ruta_stf"]).read_text(encoding="latin-1")
    assert "NrRooms=7" in texto
    # Cada sala dice de qué planta es: al duplicar la planta en DIALux hay que borrar las otras.
    assert "Name=Archivos [segunda]" in texto
    assert "Name=Ascensor [segunda]" in texto and "Name=Ascensor [tercera]" in texto
    assert any("plantas" in a for a in salida["avisos"])

    # Lo que el STF no lleva sale como tarea a mano, con los números ya puestos.
    archivos = next(t for t in salida["plantas"][0]["a_mano"] if t["sala"] == "Archivos")
    assert archivos["zona_marginal_m"] == 0.2
    assert archivos["columnas"][0]["ancho_x_m"] == 0.657
    banos = next(t for t in salida["plantas"][0]["a_mano"] if t["sala"] == "Baños")
    assert banos["zona_marginal_m"] == 0.1 and "columnas" not in banos

    oficina = salida["plantas"][1]["estancias"][0]
    assert oficina["nombre"].startswith("Oficina") and oficina["plano_trabajo_m"] == 0.85


def test_el_parcial_usa_la_altura_del_enunciado(tmp_path):
    salida = plano_a_stf(_plano("Examen-parcial.dwg"), carpeta_destino=tmp_path)
    (sala,) = salida["plantas"][0]["estancias"]
    assert sala["altura_m"] == 5.0 and sala["plano_trabajo_m"] == 0.8


def test_altura_distinta_para_una_sala(tmp_path):
    salida = plano_a_stf(_plano("ExamenFinal-Junio-Dialux-26.dwg"), altura_m=3,
                         alturas={"Archivos": 4.5}, carpeta_destino=tmp_path)
    # Los nombres llevan la planta detrás ("Archivos [segunda]"), así que se busca por el principio.
    alturas = {e["nombre"].split(" [")[0]: e["altura_m"] for e in salida["plantas"][0]["estancias"]}
    assert alturas["Archivos"] == 4.5 and alturas["Baños"] == 3


def test_nombres_genericos_como_los_de_dialux(tmp_path):
    salida = plano_a_stf(_plano("ExamenFinal-Junio-Dialux-26.dwg"), altura_m=3,
                         nombres_genericos=True, nombre_proyecto="Ejercicio 3",
                         carpeta_destino=tmp_path)
    nombres = [e["nombre"] for p in salida["plantas"] for e in p["estancias"]]
    assert nombres == [f"Local {i}" for i in range(1, 8)]
    texto = Path(salida["ruta_stf"]).read_text(encoding="latin-1")
    assert "Name=Ejercicio 3" in texto
    # Sin rastro del uso ni de la planta en los nombres de las salas.
    assert "Archivos" not in texto and "[segunda]" not in texto
