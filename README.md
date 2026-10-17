# Pipeline de datos para detección de anomalías en tráfico de red

Pipeline de datos de punta a punta: ingesta a un datalake S3-compatible,
ETL en Python con salida en Parquet, detección de anomalías y dashboard.
Corre con Docker Compose y está pensado para desplegarse en Oracle Cloud.

## Caso de uso
Detección de comportamiento sospechoso (escaneos de puertos, picos de
conexiones) sobre un dataset público etiquetado (CICIDS2017).

## Estado
En desarrollo. Fase actual: estructura del proyecto.

## Stack
Python, pandas, Docker, S3-compatible, PostgreSQL, Grafana.
