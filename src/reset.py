"""
reset.py — Script para reiniciar el estado de los datos del pipeline.

Permite vaciar las tablas de PostgreSQL y los buckets de RustFS (processed y alerts)
para volver a ejecutar el pipeline completo de punta a punta como si fuera la primera vez.

Uso:
    python src/reset.py                # Limpia DB y buckets 'processed' y 'alerts'
    python src/reset.py --include-raw  # Limpia también el bucket 'raw' para re-subir los CSVs
"""

import os
import argparse
import logging
from dotenv import load_dotenv
import psycopg
import boto3

load_dotenv()

STORAGE_ENDPOINT = os.environ["STORAGE_ENDPOINT"]
STORAGE_ACCESS_KEY = os.environ["STORAGE_ACCESS_KEY"]
STORAGE_SECRET_KEY = os.environ["STORAGE_SECRET_KEY"]

DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.environ["POSTGRES_DB"]
DB_USER = os.environ["POSTGRES_USER"]
DB_PASSWORD = os.environ["POSTGRES_PASSWORD"]


def reset_database():
    """Trunca las tablas alerts y pipeline_runs en PostgreSQL reiniciando los IDs."""
    print("🧹 [1/2] Limpiando base de datos PostgreSQL...")
    with psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE alerts, pipeline_runs RESTART IDENTITY;")
        conn.commit()
    print("  ✔ Tablas 'alerts' y 'pipeline_runs' truncadas (IDs reiniciados en 1).")


def reset_storage(include_raw: bool = False):
    """Elimina los objetos en los buckets de S3."""
    print("🧹 [2/2] Limpiando buckets en RustFS (S3)...")
    s3 = boto3.client(
        "s3",
        endpoint_url=STORAGE_ENDPOINT,
        aws_access_key_id=STORAGE_ACCESS_KEY,
        aws_secret_access_key=STORAGE_SECRET_KEY,
    )

    buckets_to_clean = ["processed", "alerts"]
    if include_raw:
        buckets_to_clean.append("raw")

    for bucket in buckets_to_clean:
        try:
            resp = s3.list_objects_v2(Bucket=bucket)
            objetos = resp.get("Contents", [])
            if not objetos:
                print(f"  → Bucket '{bucket}' ya estaba vacío.")
                continue

            borrados = 0
            for obj in objetos:
                s3.delete_object(Bucket=bucket, Key=obj["Key"])
                borrados += 1
            print(f"  ✔ Eliminados {borrados} objetos del bucket '{bucket}'.")
        except Exception as e:
            print(f"  ⚠ Error al limpiar bucket '{bucket}': {e}")


def main():
    parser = argparse.ArgumentParser(description="Reinicia los datos de PostgreSQL y S3.")
    parser.add_argument(
        "--include-raw",
        action="store_true",
        help="Elimina también los CSVs crudos del bucket 'raw'",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("REINICIO DE ESTADO DE DATOS (RESET PIPELINE)")
    print("=" * 60)

    reset_database()
    reset_storage(include_raw=args.include_raw)

    print("\n🎉 Entorno reiniciado con éxito.")
    print("Para volver a ejecutar el pipeline completo, ejecutá:")
    print("    python src/main.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
