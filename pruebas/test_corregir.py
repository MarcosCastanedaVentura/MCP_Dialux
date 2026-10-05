"""Corregir un trabajo contra la norma, con el trabajo de clase de Marcos.

Los valores exigidos salen de su PDF de la norma y los medidos de las tablas del DWG, así que
esta prueba necesita los dos ficheros de material/ y se salta si no están.
"""

from pathlib import Path

import pytest

from dialux.corregir import corregir

RAIZ = Path(__file__).resolve().parents[1]
TRABAJO = RAIZ / "material" / "exportados" / "trabajo2-clase-2d.dwg"

if not TRABAJO.is_file() or not list((RAIZ / "material" / "norma").glob("*.pdf")):
    pytest.skip("falta el trabajo exportado o el PDF de la norma", allow_module_level=True)


@pytest.fixture(scope="module")
def corregido() -> dict:
    return corregir(TRABAJO, {"Aula 1": "44.1"})


def test_el_aula_cumple_la_iluminancia_y_no_la_uniformidad(corregido):
    (aula,) = corregido["corregidas"]
    assert aula["referencia"] == "44.1" and aula["planta"] == "Planta 1"
    assert aula["medido"]["e_media_lx"] == 596 and aula["medido"]["u0"] == 0.53
    assert aula["exigido"]["Em_requerido_lx"] == 500 and aula["exigido"]["Uo"] == 0.6
    assert aula["cumple"] == ["Ēm requerido: 596 lx de 500 lx"]
    assert aula["veredicto"].startswith("NO cumple") and "U0" in aula["veredicto"]
    # La corrección cita de dónde sale el valor exigido, para poder revisarla.
    assert "fila 44.1, página 70" in aula["fuente"]


def test_fallar_solo_el_em_modificado_no_es_suspender(corregido):
    """La norma da los dos Ēm y en clase no está decidido cuál se usa: se dice, no se elige."""
    aula = corregido["corregidas"][0]
    assert "Ēm modificado: 596 lx de 1000 lx" in aula["no_cumple"]
    solo_requerido = corregir(TRABAJO, {"Aula 1": "44.1"}, usar="requerido")["corregidas"][0]
    assert solo_requerido["no_cumple"] == ["U0: 0.53 de 0.6"]


def test_sin_la_zona_marginal_del_enunciado_no_se_juzga(corregido):
    """La práctica pedía 0,5 m y DIALux calculó sobre el plano útil entero: no es lo mismo.

    El fallo de U0 puede desaparecer al dejar fuera la banda de los bordes, que es la más oscura,
    así que dar la sala por suspensa sería corregir mal.
    """
    con_zona = corregir(TRABAJO, {"Aula 1": "44.1"}, zona_marginal_m=0.5)["corregidas"][0]
    assert con_zona["veredicto"].startswith("No se puede juzgar todavía")
    assert con_zona["zona_marginal"]["margen_del_calculo_m"] == 0.195
    assert "U0: 0.53 de 0.6" in con_zona["veredicto"]
    # Si el enunciado no pide zona marginal, el veredicto es el que sale de los números.
    assert corregido["corregidas"][0]["veredicto"].startswith("NO cumple")
    assert "zona_marginal" not in corregido["corregidas"][0]


def test_las_salas_sin_luminarias_no_se_corrigen(corregido):
    assert len(corregido["sin_calcular"]) == 14
    pasillo = next(s for s in corregido["sin_calcular"] if s["sala"] == "Local 18")
    # DIALux le da 0,37 lx, que es luz que se cuela del aula: no es alumbrado de esa sala.
    assert pasillo["e_media_lx"] == 0.37 and "otra sala" in pasillo["ojo"]


def test_sin_fila_de_la_norma_se_pregunta_y_no_se_elige(corregido):
    """Si no se da la referencia de una sala calculada, se devuelven candidatas, no una decisión."""
    sin_referencia = corregir(TRABAJO)["sin_referencia_de_norma"]
    assert [s["sala"] for s in sin_referencia] == ["Aula 1"]
    assert any(c["referencia"] == "44.1" for c in sin_referencia[0]["candidatas"])
    assert not corregir(TRABAJO)["corregidas"]


def test_el_rendimiento_del_local_sale_de_sus_propios_numeros(corregido):
    """Ēm = n·Φ·FM·η/S despejando η: el dato que falta para calcular, deducido de su trabajo."""
    assert corregido["corregidas"][0]["rendimiento_del_local_implicito"] == 0.83


def test_un_stf_no_se_puede_corregir(tmp_path):
    fichero = tmp_path / "x.stf"
    fichero.write_text("")
    with pytest.raises(ValueError, match="no lleva resultados"):
        corregir(fichero)
