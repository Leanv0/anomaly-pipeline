"""
logger_config.py — Configuración centralizada del sistema de logging del pipeline.

Configura salida dual (consola y archivo logs/pipeline.log) con formato uniforme
y niveles de severidad configurables.
"""

import logging
from pathlib import Path


def setup_logging(level: str = "INFO", log_dir: str = "logs") -> None:
    """
    Configura el sistema de logging con salida dual: consola + archivo.

    Parameters
    ----------
    level : str
        Nivel mínimo de severidad ("DEBUG", "INFO", "WARNING", "ERROR").
    log_dir : str
        Directorio donde se almacenará el archivo de log.
    """
    root_logger = logging.getLogger()
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    # Evitar duplicación de handlers si se invoca múltiples veces
    if root_logger.handlers:
        return

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)-15s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler para salida por consola
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Handler para persistencia en archivo
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    log_file = log_path / "pipeline.log"

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
