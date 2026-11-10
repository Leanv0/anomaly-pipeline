"""
sync_neon.py — Lee POSTGRES_URL directamente de chatbot-web/.env.local
y migra las tablas alerts y pipeline_runs desde PostgreSQL local (Docker) hacia Neon.
"""

import os
import sys
import time
from pathlib import Path
import psycopg
from dotenv import load_dotenv

# Raíz del proyecto (un nivel arriba de scripts/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Cargar variables locales de anomaly-pipeline (.env)
load_dotenv(PROJECT_ROOT / ".env")
LOCAL_HOST = os.getenv("POSTGRES_HOST", "localhost")
LOCAL_PORT = os.getenv("POSTGRES_PORT", "5432")
LOCAL_DB = os.getenv("POSTGRES_DB", "anomaly_db")
LOCAL_USER = os.getenv("POSTGRES_USER", "anomaly_user")
LOCAL_PASS = os.getenv("POSTGRES_PASSWORD", "")

# Cargar variables de Neon de chatbot-web/.env.local
load_dotenv(PROJECT_ROOT / "chatbot-web" / ".env.local", override=True)
NEON_URL = os.getenv("POSTGRES_URL")

if not NEON_URL or "neon.tech" not in NEON_URL:
    print("❌ Error: No se encontró una POSTGRES_URL válida de Neon en chatbot-web/.env.local")
    sys.exit(1)

source_url = f"postgresql://{LOCAL_USER}:{LOCAL_PASS}@{LOCAL_HOST}:{LOCAL_PORT}/{LOCAL_DB}"

print("=" * 65)
print("🚀 SINCRONIZANDO BASE DE DATOS LOCAL CON NEON.TECH")
print("=" * 65)

t0 = time.time()

with psycopg.connect(source_url) as conn_src, psycopg.connect(NEON_URL) as conn_dest:
    # 1. Crear esquema en Neon
    print("🛠️  Creando tablas e índices en Neon...")
    with conn_dest.cursor() as cur:
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
    print("✔  Esquema verificado en Neon.")

    # 2. Migrar pipeline_runs
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

    # 3. Migrar alerts
    print("\n📦 Migrando tabla 'alerts'...")
    with conn_src.cursor() as cur_src, conn_dest.cursor() as cur_dest:
        cur_src.execute("SELECT COUNT(*) FROM alerts;")
        total_source_alerts = cur_src.fetchone()[0]
        print(f"   Total de alertas en base local: {total_source_alerts:,}")

        cur_src.execute("""
            SELECT detected_at, source_file, destination_port, flow_duration,
                   total_fwd_packets, total_bwd_packets, flow_bytes_per_s,
                   flow_packets_per_s, detector, anomaly_score, label_original
            FROM alerts
            ORDER BY id ASC;
        """)

        cur_dest.execute("TRUNCATE TABLE alerts RESTART IDENTITY CASCADE;")

        print("   Transfiriendo registros hacia Neon vía protocolo streaming COPY...")
        batch_count = 0
        with cur_dest.copy("""
            COPY alerts (detected_at, source_file, destination_port, flow_duration,
                        total_fwd_packets, total_bwd_packets, flow_bytes_per_s,
                        flow_packets_per_s, detector, anomaly_score, label_original)
            FROM STDIN
        """) as copy:
            while True:
                rows = cur_src.fetchmany(15000)
                if not rows:
                    break
                for row in rows:
                    copy.write_row(row)
                batch_count += len(rows)
                print(f"   → {batch_count:,} alertas transferidas a Neon...", end="\r")

        conn_dest.commit()
        print(f"\n✔  {batch_count:,} alertas transferidas con éxito a Neon.")

elapsed = time.time() - t0
print("\n" + "=" * 65)
print(f"🎉 MIGRACIÓN A NEON COMPLETADA EN {elapsed:.2f} SEGUNDOS")
print("=" * 65)
