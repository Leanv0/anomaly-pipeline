"""
main.py — Orquestador central del pipeline de detección de anomalías.

Entrypoint para la ejecución de punta a punta:
1. Configuración de logging dual (consola y archivo logs/pipeline.log).
2. Verificación de infraestructura y esquema en PostgreSQL (alerts, pipeline_runs).
3. Ingesta y ETL: CSVs crudos en RustFS (S3) -> Parquet en bucket 'processed'.
4. Detección de anomalías: calibración de línea base, reglas de firma TCP,
   Isolation Forest y persistencia relacional para Grafana.
"""

import sys
import os
import time
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from logger_config import setup_logging
from db_setup import setup_database
from etl import run_pipeline as run_etl_pipeline
from detector import run_detection_pipeline, get_s3_client

logger = logging.getLogger("main")


def parse_arguments() -> argparse.Namespace:
    """Parsea los argumentos pasados por línea de comandos (CLI)."""
    parser = argparse.ArgumentParser(
        description="Orquestador del Pipeline de Detección de Anomalías (CICIDS2017)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--skip-etl",
        action="store_true",
        help="Saltea las fases de Ingesta y ETL",
    )

    parser.add_argument(
        "--skip-detect",
        action="store_true",
        help="Saltea la fase de Detección de anomalías",
    )

    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Procesa un único archivo Parquet específico en la fase de detección",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Nivel mínimo de severidad para los mensajes de log",
    )

    return parser.parse_args()


def main() -> int:
    """Función principal orquestadora."""
    args = parse_arguments()
    setup_logging(level=args.log_level)

    t_inicio_total = time.time()
    logger.info("=" * 70)
    logger.info("🚀 INICIANDO ANOMALY PIPELINE DE PUNTA A PUNTA")
    logger.info("=" * 70)
    logger.info("Configuración: skip_etl=%s, skip_detect=%s, target_file=%s, log_level=%s",
                args.skip_etl, args.skip_detect, args.file, args.log_level)

    # 1. Base de datos
    try:
        logger.info("\n[1/3] VERIFICANDO INFRAESTRUCTURA DE BASE DE DATOS...")
        setup_database()
        logger.info("✔ Base de datos lista.")
    except Exception as e:
        logger.critical("Error fatal al inicializar la base de datos: %s", e, exc_info=True)
        return 1

    # 2. Ingesta y ETL
    if not args.skip_etl:
        try:
            logger.info("\n[2/3] EJECUTANDO FASE DE INGESTA Y ETL...")
            etl_resultados = run_etl_pipeline()
            logger.info("✔ ETL completado para %d archivos.", len(etl_resultados))
        except Exception as e:
            logger.error("Ocurrió un error en la fase de ETL: %s", e, exc_info=True)
            if args.skip_detect:
                return 1
    else:
        logger.info("\n[2/3] FASE DE ETL: Salteada por flag --skip-etl.")

    # 3. Detección de anomalías
    if not args.skip_detect:
        try:
            logger.info("\n[3/3] EJECUTANDO FASE DE DETECCIÓN DE ANOMALÍAS...")
            target_list = [args.file] if args.file else None
            run_detection_pipeline(target_files=target_list)
            logger.info("✔ Detección completada exitosamente.")
        except Exception as e:
            logger.error("Ocurrió un error en la fase de detección: %s", e, exc_info=True)
            return 1
    else:
        logger.info("\n[3/3] FASE DE DETECCIÓN: Salteada por flag --skip-detect.")

    tiempo_total = time.time() - t_inicio_total
    logger.info("\n" + "=" * 70)
    logger.info("🏁 PIPELINE FINALIZADO CON ÉXITO")
    logger.info("Tiempo total de ejecución: %.2f segundos (~%.1f minutos)",
                tiempo_total, tiempo_total / 60)
    logger.info("Logs guardados en 'logs/pipeline.log'.")
    logger.info("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
