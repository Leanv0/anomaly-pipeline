"""
etl.py — Pipeline ETL para el dataset CICIDS2017.

Flujo:
  1. Ingesta: Sube los CSVs crudos locales al bucket 'raw' de S3 (RustFS).
  2. Extract: Descarga el CSV desde S3 a memoria (BytesIO) y lo carga en pandas.
  3. Transform: Limpieza de nombres, eliminación de identificadores y vacíos,
     normalización de etiquetas e imputación de infinitos/nulos.
  4. Load: Serializa a Apache Parquet (PyArrow + Snappy) y sube al bucket 'processed'.
"""

import os
import logging
from pathlib import Path
from io import BytesIO
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

load_dotenv()

ENDPOINT = os.environ["STORAGE_ENDPOINT"]
ACCESS_KEY = os.environ["STORAGE_ACCESS_KEY"]
SECRET_KEY = os.environ["STORAGE_SECRET_KEY"]

LOCAL_RAW = Path("data/raw/TrafficLabelling")
BUCKET_RAW = "raw"
BUCKET_PROCESSED = "processed"

# Columnas identificadoras a descartar
COLUMNS_TO_DROP = ["Flow ID", "Source IP", "Destination IP", "Timestamp"]

# Corrección de codificación en etiquetas
LABEL_FIXES = {
    "Web Attack \x96 Brute Force": "Web Attack - Brute Force",
    "Web Attack \x96 XSS": "Web Attack - XSS",
    "Web Attack \x96 Sql Injection": "Web Attack - Sql Injection",
}


def get_s3_client():
    """Inicializa y retorna el cliente boto3 para S3."""
    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
    )


def ingest_raw(s3):
    """
    Sube los CSVs locales al bucket 'raw' de S3 de manera idempotente.
    """
    respuesta = s3.list_objects_v2(Bucket=BUCKET_RAW)
    existentes = {
        obj["Key"]: obj["Size"]
        for obj in respuesta.get("Contents", [])
    }

    archivos_locales = sorted(LOCAL_RAW.glob("*.csv"))
    if not archivos_locales:
        logger.warning("No se encontraron CSVs en %s", LOCAL_RAW)
        return

    logger.info("Ingesta: %d CSVs locales, %d ya en bucket '%s'",
                len(archivos_locales), len(existentes), BUCKET_RAW)

    subidos = 0
    for archivo in archivos_locales:
        key = archivo.name
        tamano_local = archivo.stat().st_size

        if key in existentes and existentes[key] == tamano_local:
            logger.debug("'%s' ya existe con el mismo tamaño, se saltea.", key)
            continue

        tamano_mb = tamano_local / 1024 / 1024
        logger.info("Subiendo '%s' (%.1f MB)...", key, tamano_mb)
        s3.upload_file(str(archivo), BUCKET_RAW, key)
        subidos += 1

    logger.info("Ingesta finalizada: %d subidos, %d ya existentes.",
                subidos, len(archivos_locales) - subidos)


def extract(s3, key: str) -> pd.DataFrame:
    """
    Descarga un CSV desde S3 a un buffer en memoria RAM y lo carga en DataFrame.
    """
    buffer = BytesIO()
    s3.download_fileobj(BUCKET_RAW, key, buffer)
    buffer.seek(0)

    try:
        df = pd.read_csv(buffer, low_memory=False)
    except UnicodeDecodeError:
        logger.info("Fallo en UTF-8 para '%s', reintentando con latin-1...", key)
        buffer.seek(0)
        df = pd.read_csv(buffer, encoding="latin-1", low_memory=False)

    logger.info("Extraído '%s': %s filas × %d columnas", key, f"{df.shape[0]:,}", df.shape[1])
    return df


def transform(df: pd.DataFrame, source_file: str = "") -> pd.DataFrame:
    """
    Limpia y estandariza el DataFrame de tráfico:
    - Normaliza nombres de columnas eliminando espacios.
    - Elimina filas vacías e identificadores no generalizables.
    - Deduplica columnas redundantes y normaliza etiquetas.
    - Reemplaza infinitos por NaN e imputa con la mediana de cada columna.
    """
    filas_antes = len(df)

    # Limpiar espacios en nombres de columnas
    df.columns = df.columns.str.strip()

    # Eliminar filas completamente vacías
    df = df.dropna(how="all")
    filas_vacias = filas_antes - len(df)
    if filas_vacias > 0:
        logger.info("Filas vacías eliminadas: %d", filas_vacias)

    # Eliminar columnas duplicadas terminadas en '.1'
    for col in [c for c in df.columns if c.endswith(".1")]:
        original = col[:-2]
        if original in df.columns and df[original].equals(df[col]):
            df = df.drop(columns=[col])

    # Descartar identificadores
    df = df.drop(columns=COLUMNS_TO_DROP, errors="ignore")

    # Normalizar etiquetas de ataques
    if "Label" in df.columns:
        df["Label"] = df["Label"].replace(LABEL_FIXES).str.strip()

    # Manejar infinitos e imputar nulos con la mediana
    df = df.replace([np.inf, -np.inf], np.nan)
    cols_numericas = df.select_dtypes(include="number").columns

    for col in cols_numericas:
        if df[col].isna().sum() > 0:
            df[col] = df[col].fillna(df[col].median())

    nans_restantes = df.isna().sum().sum()
    logger.info("Transformado: %s filas × %d columnas | NaNs restantes: %d",
                f"{df.shape[0]:,}", df.shape[1], nans_restantes)

    return df


def load(s3, df: pd.DataFrame, key_original: str) -> str:
    """
    Serializa el DataFrame a formato Apache Parquet y lo sube al bucket 'processed'.
    """
    nombre_limpio = key_original.replace(".pcap_ISCX.csv", "").replace(".csv", "")
    key_parquet = f"{nombre_limpio}.parquet"

    buffer = BytesIO()
    df.to_parquet(buffer, engine="pyarrow", index=False, compression="snappy")
    tamano_parquet_mb = buffer.tell() / 1024 / 1024
    buffer.seek(0)

    s3.upload_fileobj(buffer, BUCKET_PROCESSED, key_parquet)
    logger.info("Cargado '%s' en bucket '%s' (%.1f MB)",
                key_parquet, BUCKET_PROCESSED, tamano_parquet_mb)

    return key_parquet


def run_pipeline():
    """
    Ejecuta el pipeline ETL completo: ingesta, extracción, transformación y carga.
    """
    s3 = get_s3_client()

    logger.info("=" * 60)
    logger.info("FASE 1: INGESTA")
    logger.info("=" * 60)
    ingest_raw(s3)

    logger.info("=" * 60)
    logger.info("FASE 2: ETL (Extract → Transform → Load)")
    logger.info("=" * 60)

    respuesta = s3.list_objects_v2(Bucket=BUCKET_RAW)
    csvs = [obj for obj in respuesta.get("Contents", []) if obj["Key"].endswith(".csv")]
    logger.info("%d CSVs encontrados en bucket '%s'.", len(csvs), BUCKET_RAW)

    resultados = []
    for i, obj in enumerate(csvs, start=1):
        key = obj["Key"]
        tamano_mb = obj["Size"] / 1024 / 1024
        logger.info("[%d/%d] %s (%.1f MB)", i, len(csvs), key, tamano_mb)

        df = extract(s3, key)
        filas_crudas = len(df)

        df = transform(df, key)
        filas_limpias = len(df)

        key_parquet = load(s3, df, key)

        resultados.append({
            "csv": key,
            "parquet": key_parquet,
            "filas_crudas": filas_crudas,
            "filas_limpias": filas_limpias,
            "columnas": df.shape[1],
        })

        del df

    logger.info("=" * 60)
    logger.info("RESUMEN ETL")
    logger.info("=" * 60)
    total_crudas = sum(r["filas_crudas"] for r in resultados)
    total_limpias = sum(r["filas_limpias"] for r in resultados)
    logger.info("Archivos procesados: %d", len(resultados))
    logger.info("Filas totales crudas: %s", f"{total_crudas:,}")
    logger.info("Filas totales limpias: %s", f"{total_limpias:,}")
    logger.info("Filas eliminadas: %s", f"{total_crudas - total_limpias:,}")

    return resultados


if __name__ == "__main__":
    from logger_config import setup_logging
    setup_logging()
    run_pipeline()
