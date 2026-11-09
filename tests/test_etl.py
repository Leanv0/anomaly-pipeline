"""
test_etl.py — Pruebas unitarias para las transformaciones del módulo ETL.

Estas pruebas son puras: no requieren Docker ni conexión a RustFS ni a PostgreSQL.
Validan que las funciones de limpieza de datos produzcan el formato, las columnas
y los tipos esperados para el pipeline de detección de anomalías.
"""

import sys
from pathlib import Path
import pytest
import numpy as np
import pandas as pd

# Agregamos src/ al PYTHONPATH para importar etl directamente
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from etl import transform, COLUMNS_TO_DROP


def test_transform_strips_column_names(sample_raw_df):
    """
    Verifica que transform() elimine los espacios iniciales y finales
    en los nombres de las columnas (ej: ' Flow ID' -> 'Flow ID').
    """
    df_clean = transform(sample_raw_df)
    for col in df_clean.columns:
        assert col == col.strip(), f"La columna '{col}' contiene espacios al inicio o al final."


def test_transform_drops_empty_rows(sample_raw_df):
    """
    Verifica que transform() descarte las filas donde todas las celdas sean NaN.
    En sample_raw_df hay 4 filas iniciales, de las cuales 1 es completamente vacía.
    """
    df_clean = transform(sample_raw_df)
    assert len(df_clean) == 3, f"Se esperaban 3 filas luego de dropna(how='all'), pero quedaron {len(df_clean)}."


def test_transform_removes_identifier_columns(sample_raw_df):
    """
    Verifica que se eliminen las columnas de identificación especificadas en COLUMNS_TO_DROP
    (Flow ID, Source IP, Destination IP, Timestamp).
    """
    df_clean = transform(sample_raw_df)
    for col in COLUMNS_TO_DROP:
        assert col not in df_clean.columns, f"La columna identificadora '{col}' no fue eliminada."


def test_transform_removes_duplicate_columns(sample_raw_df):
    """
    Verifica que se eliminen las columnas duplicadas terminadas en '.1'
    (ej: 'Fwd Header Length.1' si es idéntica a 'Fwd Header Length').
    """
    df_clean = transform(sample_raw_df)
    assert "Fwd Header Length" in df_clean.columns
    assert "Fwd Header Length.1" not in df_clean.columns


def test_transform_normalizes_labels(sample_raw_df):
    """
    Verifica que el caracter especial Windows-1252 (\\x96) presente en las etiquetas
    de Web Attack sea reemplazado por un guión estándar '-' limpio.
    """
    df_clean = transform(sample_raw_df)
    labels = df_clean["Label"].unique()
    assert "Web Attack - Brute Force" in labels
    assert "Web Attack \x96 Brute Force" not in labels


def test_transform_handles_inf_and_nans(sample_raw_df):
    """
    Verifica que los valores infinitos (np.inf, -np.inf) sean reemplazados
    y que tras rellenar con la mediana no quede ningún valor NaN en el DataFrame.
    """
    df_clean = transform(sample_raw_df)

    # Verificar que no queden infinitos
    assert not np.isinf(df_clean["Flow Bytes/s"]).any()
    assert not np.isinf(df_clean["Flow Packets/s"]).any()

    # Verificar que no queden nulos
    assert df_clean.isna().sum().sum() == 0, "Aún quedan valores NaN luego de la transformación."
