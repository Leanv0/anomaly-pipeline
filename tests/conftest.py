"""
conftest.py — Fixtures compartidas para la suite de pruebas con pytest.

En pytest, un archivo llamado `conftest.py` define fixtures que están
disponibles automáticamente para todos los archivos de test del directorio
sin necesidad de importarlas explícitamente en cada uno.

Conceptos de pytest:
- @pytest.fixture: Decorador que convierte una función en proveedora de datos
  o estado inicial para los tests. Si un test tiene como argumento el nombre
  de la fixture, pytest la ejecuta primero y le pasa el resultado.
"""

import pytest
import pandas as pd
import numpy as np


@pytest.fixture
def sample_raw_df() -> pd.DataFrame:
    """
    Genera un DataFrame sintético que imita las anomalías estructurales
    del dataset crudo CICIDS2017:
    - Espacios al inicio en los nombres de columnas (" Source Port").
    - Columnas duplicadas que terminan en ".1" ("Fwd Header Length.1").
    - Columnas identificadoras a descartar ("Flow ID", "Source IP", "Destination IP", "Timestamp").
    - Valores infinitos (np.inf) generados por división por cero.
    - Filas completamente vacías (todas NaN).
    - Caracteres extraños en las etiquetas (\x96 de Web Attack).
    """
    data = {
        " Flow ID": ["192.168.1.1-10.0.0.1", "192.168.1.2-10.0.0.2", np.nan, "192.168.1.3-10.0.0.3"],
        " Source IP": ["192.168.1.1", "192.168.1.2", np.nan, "192.168.1.3"],
        " Destination IP": ["10.0.0.1", "10.0.0.2", np.nan, "10.0.0.3"],
        " Timestamp": ["07/07/2017 8:30", "07/07/2017 8:31", np.nan, "07/07/2017 8:32"],
        " Destination Port": [80, 443, np.nan, 22],
        " Flow Duration": [5000, 45, np.nan, 1200],
        " Total Fwd Packets": [5, 1, np.nan, 10],
        " Total Backward Packets": [4, 1, np.nan, 8],
        " Flow Bytes/s": [1200.5, np.inf, np.nan, 3400.0],
        " Flow Packets/s": [50.0, np.inf, np.nan, 80.0],
        " Fwd Header Length": [100, 20, np.nan, 200],
        " Fwd Header Length.1": [100, 20, np.nan, 200],  # Duplicada idéntica
        " Label": ["BENIGN", "Web Attack \x96 Brute Force", np.nan, "BENIGN"],
    }
    return pd.DataFrame(data)


@pytest.fixture
def sample_clean_traffic_df() -> pd.DataFrame:
    """
    Genera un DataFrame limpio con flujos benignos y maliciosos
    para validar las funciones de detección y métricas de seguridad.
    """
    data = {
        "Destination Port": [80, 21, 443, 8080, 22],
        "Flow Duration": [50000, 400, 120000, 350, 45000],
        "Total Fwd Packets": [10, 1, 25, 2, 8],
        "Total Backward Packets": [8, 0, 20, 0, 7],
        "Flow Packets/s": [200.0, 25000.0, 150.0, 30000.0, 180.0],
        "Flow Bytes/s": [5000.0, 120000.0, 3500.0, 140000.0, 4200.0],
        "PSH Flag Count": [0, 1, 0, 1, 0],
        "ACK Flag Count": [1, 0, 1, 0, 1],
        "Average Packet Size": [500.0, 40.0, 600.0, 40.0, 480.0],
        "Fwd Packet Length Max": [1500, 0, 1400, 0, 1450],
        "Bwd PSH Flags": [0, 0, 0, 0, 0],  # Columna constante (varianza 0)
        "Label": ["BENIGN", "PortScan", "BENIGN", "PortScan", "BENIGN"],
    }
    return pd.DataFrame(data)
