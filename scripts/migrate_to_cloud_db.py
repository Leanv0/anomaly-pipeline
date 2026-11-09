"""
migrate_to_cloud_db.py — Migra o replica las tablas de alertas y métricas
desde el PostgreSQL local (Docker) hacia una base de datos en la nube (ej: Neon, Supabase).

Uso:
    python scripts/migrate_to_cloud_db.py --dest "postgresql://user:pass@ep-xyz.neon.tech/neondb?sslmode=require"
"""

import os
import sys
import argparse
import time
import psycopg
from dotenv import load_dotenv

load_dotenv()

# Conexión local origen (desde .env)
LOCAL_HOST = os.getenv("POSTGRES_HOST", "localhost")
LOCAL_PORT = os.getenv("POSTGRES_PORT", "5432")
LOCAL_DB = os.getenv("POSTGRES_DB", "anomaly_db")
LOCAL_USER = os.getenv("POSTGRES_USER", "anomaly_user")
LOCAL_PASS = os.getenv("POSTGRES_PASSWORD", "")


def create_schema(conn_dest):
    """Crea las tablas alerts y pipeline_runs en la base destino si no existen."""
    with conn_dest.cursor() as cur:
        print("🛠️  Creando tablas e índices en la base de datos destino...")
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

            CREATE INDEX IF NOT EXISTS idx_alerts_detected_at ON alerts (detected_at);
            CREATE INDEX IF NOT EXISTS idx_alerts_detector ON alerts (detector);
            CREATE INDEX IF NOT EXISTS idx_alerts_dest_port ON alerts (destination_port);

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
    conn_dest.commit()
    print("✔  Esquema verificado en destino.")


def migrate_data(source_url: str, dest_url: str, limit_alerts: int = None):
    """Copia los datos de origen a destino usando streaming COPY."""
    t0 = time.time()
    print("=" * 65)
    print("🚀 INICIANDO MIGRACIÓN A POSTGRESQL CLOUD")
    print("=" * 65)

    with psycopg.connect(source_url) as conn_src, psycopg.connect(dest_url) as conn_dest:
        create_schema(conn_dest)

        # 1. Migrar pipeline_runs
        print("\n📦 Migrando tabla 'pipeline_runs'...")
        with conn_src.cursor() as cur_src, conn_dest.cursor() as cur_dest:
            cur_src.execute("""
                SELECT source_file, total_flows_processed, total_anomalies_detected,
                       processing_time_seconds, status, run_at
                FROM pipeline_runs
                ORDER BY id ASC;
            """)
            runs = cur_src.fetchall()

            cur_dest.execute("TRUNCATE TABLE pipeline_runs RESTART IDENTITY CASCADE;")
            with cur_dest.copy("""
                COPY pipeline_runs (source_file, total_flows_processed, total_anomalies_detected,
                                   processing_time_seconds, status, run_at)
                FROM STDIN
            """) as copy:
                for row in runs:
                    copy.write_row(row)
            conn_dest.commit()
            print(f"✔  {len(runs)} ejecuciones migradas a 'pipeline_runs'.")

        # 2. Migrar alerts
        print("\n📦 Migrando tabla 'alerts'...")
        with conn_src.cursor() as cur_src, conn_dest.cursor() as cur_dest:
            cur_src.execute("SELECT COUNT(*) FROM alerts;")
            total_source_alerts = cur_src.fetchone()[0]
            print(f"   Total de alertas en origen: {total_source_alerts:,}")

            limit_clause = f"LIMIT {limit_alerts}" if limit_alerts else ""
            query_alerts = f"""
                SELECT detected_at, source_file, destination_port, flow_duration,
                       total_fwd_packets, total_bwd_packets, flow_bytes_per_s,
                       flow_packets_per_s, detector, anomaly_score, label_original
                FROM alerts
                ORDER BY id ASC
                {limit_clause};
            """

            cur_src.execute(query_alerts)
            cur_dest.execute("TRUNCATE TABLE alerts RESTART IDENTITY CASCADE;")

            print("   Transfiriendo registros con protocolo COPY...")
            batch_count = 0
            with cur_dest.copy("""
                COPY alerts (detected_at, source_file, destination_port, flow_duration,
                            total_fwd_packets, total_bwd_packets, flow_bytes_per_s,
                            flow_packets_per_s, detector, anomaly_score, label_original)
                FROM STDIN
            """) as copy:
                while True:
                    rows = cur_src.fetchmany(10000)
                    if not rows:
                        break
                    for row in rows:
                        copy.write_row(row)
                    batch_count += len(rows)
                    print(f"   → {batch_count:,} alertas transferidas...", end="\r")

            conn_dest.commit()
            print(f"\n✔  {batch_count:,} alertas migradas exitosamente a 'alerts'.")

    elapsed = time.time() - t0
    print("\n" + "=" * 65)
    print(f"🎉 MIGRACIÓN COMPLETADA EN {elapsed:.2f} SEGUNDOS")
    print("=" * 65)


def main():
    parser = argparse.ArgumentParser(
        description="Migra los datos de PostgreSQL local a PostgreSQL en la nube."
    )
    parser.add_argument(
        "--dest",
        type=str,
        required=True,
        help="Cadena de conexión destino (ej: postgresql://user:pass@ep-xyz.neon.tech/dbname?sslmode=require)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Límite opcional de alertas a transferir (por defecto transfiere todas)",
    )
    args = parser.parse_args()

    source_url = f"postgresql://{LOCAL_USER}:{LOCAL_PASS}@{LOCAL_HOST}:{LOCAL_PORT}/{LOCAL_DB}"
    migrate_data(source_url, args.dest, limit_alerts=args.limit)


if __name__ == "__main__":
    main()
