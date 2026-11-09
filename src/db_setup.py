"""
db_setup.py — Inicialización y verificación de PostgreSQL para el pipeline.

Crea las tablas e índices necesarios para almacenar alertas y métricas del pipeline,
e inserta registros de prueba para validar conectividad.
"""

import os
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
import psycopg
from psycopg import sql

logger = logging.getLogger(__name__)

load_dotenv()

DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.environ["POSTGRES_DB"]
DB_USER = os.environ["POSTGRES_USER"]
DB_PASSWORD = os.environ["POSTGRES_PASSWORD"]


def get_connection():
    """Retorna una conexión activa hacia la base de datos PostgreSQL."""
    return psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def create_schema(conn):
    """
    Crea las tablas 'alerts' y 'pipeline_runs' junto con sus índices si no existen.
    """
    with conn.cursor() as cur:
        logger.info("Verificando tabla 'alerts' e índices...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id BIGSERIAL PRIMARY KEY,
                detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                source_file VARCHAR(255) NOT NULL,
                destination_port INTEGER,
                flow_duration BIGINT,
                total_fwd_packets INTEGER,
                total_bwd_packets INTEGER,
                flow_bytes_per_s DOUBLE PRECISION,
                flow_packets_per_s DOUBLE PRECISION,
                detector VARCHAR(50) NOT NULL,
                anomaly_score DOUBLE PRECISION,
                label_original VARCHAR(100)
            );
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_alerts_detected_at ON alerts (detected_at);
            CREATE INDEX IF NOT EXISTS idx_alerts_detector ON alerts (detector);
            CREATE INDEX IF NOT EXISTS idx_alerts_dest_port ON alerts (destination_port);
        """)

        logger.info("Verificando tabla 'pipeline_runs'...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id SERIAL PRIMARY KEY,
                run_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                source_file VARCHAR(255) NOT NULL,
                total_flows_processed INTEGER NOT NULL,
                total_anomalies_detected INTEGER NOT NULL,
                processing_time_seconds DOUBLE PRECISION NOT NULL,
                status VARCHAR(200) NOT NULL DEFAULT 'SUCCESS'
            );
        """)

    conn.commit()
    logger.info("Esquema de base de datos verificado exitosamente.")


def setup_database():
    """Asegura la creación del esquema conectándose a PostgreSQL."""
    logger.info("Conectando a PostgreSQL (%s:%s/%s)...", DB_HOST, DB_PORT, DB_NAME)
    with get_connection() as conn:
        create_schema(conn)


def insert_and_verify_test_data(conn):
    """Inserta registros de prueba parametrizados y verifica su lectura."""
    print("\nInsertando registro de prueba en 'alerts'...")

    with conn.cursor() as cur:
        query_alerta = """
            INSERT INTO alerts (
                detected_at,
                source_file,
                destination_port,
                flow_duration,
                total_fwd_packets,
                total_bwd_packets,
                flow_bytes_per_s,
                flow_packets_per_s,
                detector,
                anomaly_score,
                label_original
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """

        datos_prueba_alerta = (
            datetime.now(timezone.utc),
            "Friday-WorkingHours-Afternoon-PortScan_limpio.csv",
            80,
            47,
            1,
            1,
            139534.88,
            42553.19,
            "statistical_rule",
            0.95,
            "PortScan",
        )

        cur.execute(query_alerta, datos_prueba_alerta)
        nuevo_id = cur.fetchone()[0]
        print(f"  ✔ Alerta de prueba insertada con id={nuevo_id}")

        cur.execute("""
            INSERT INTO pipeline_runs (
                source_file,
                total_flows_processed,
                total_anomalies_detected,
                processing_time_seconds,
                status
            ) VALUES (%s, %s, %s, %s, %s)
            RETURNING id;
        """, ("Friday-WorkingHours-Afternoon-PortScan_limpio.csv", 286467, 158930, 2.45, "SUCCESS"))

        run_id = cur.fetchone()[0]
        print(f"  ✔ Métrica de prueba insertada en 'pipeline_runs' con id={run_id}")

    conn.commit()

    print("\nVerificando lectura desde PostgreSQL (SELECT)...")
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, detected_at, detector, destination_port, anomaly_score, label_original
            FROM alerts
            WHERE id = %s;
        """, (nuevo_id,))

        fila = cur.fetchone()
        print(f"  📄 Fila recuperada:")
        print(f"     ID: {fila[0]}")
        print(f"     Fecha: {fila[1]}")
        print(f"     Detector: {fila[2]}")
        print(f"     Puerto destino: {fila[3]}")
        print(f"     Score: {fila[4]}")
        print(f"     Etiqueta: {fila[5]}")

    print("\n🎉 Base de datos PostgreSQL configurada y funcionando correctamente.")


if __name__ == "__main__":
    from logger_config import setup_logging
    setup_logging()

    logger.info("Conectando a PostgreSQL en %s:%s/%s (usuario: %s)...", DB_HOST, DB_PORT, DB_NAME, DB_USER)
    with get_connection() as conexion:
        create_schema(conexion)
        insert_and_verify_test_data(conexion)
