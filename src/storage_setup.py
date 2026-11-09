"""
storage_setup.py — Configuración del datalake S3 local (RustFS).

Crea los buckets raw/processed/alerts, sube un CSV de prueba,
lo lista y lo descarga de vuelta para verificar la conectividad y funcionamiento.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError

load_dotenv()

ENDPOINT = os.environ["STORAGE_ENDPOINT"]
ACCESS_KEY = os.environ["STORAGE_ACCESS_KEY"]
SECRET_KEY = os.environ["STORAGE_SECRET_KEY"]

# Cliente S3 compatible
s3 = boto3.client(
    "s3",
    endpoint_url=ENDPOINT,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
)

BUCKETS = ["raw", "processed", "alerts"]

for nombre in BUCKETS:
    try:
        s3.create_bucket(Bucket=nombre)
        print(f"  ✔ Bucket '{nombre}' creado")
    except ClientError as e:
        codigo = e.response["Error"]["Code"]
        if codigo in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
            print(f"  → Bucket '{nombre}' ya existía, sigo de largo")
        else:
            raise

respuesta = s3.list_buckets()
print("\nBuckets en el datalake:")
for bucket in respuesta["Buckets"]:
    print(f"  📦 {bucket['Name']}")

carpeta_raw = Path("data/raw/TrafficLabelling")
archivos = sorted(carpeta_raw.glob("*.csv"))

if not archivos:
    print("\n⚠ No se encontraron CSVs en data/raw/TrafficLabelling")
else:
    archivo = archivos[0]
    key = archivo.name

    print(f"\nSubiendo '{key}' al bucket 'raw'...")
    s3.upload_file(str(archivo), "raw", key)
    print(f"  ✔ Subido ({archivo.stat().st_size / 1024 / 1024:.1f} MB)")

    contenido = s3.list_objects_v2(Bucket="raw")
    print("\nObjetos en el bucket 'raw':")
    for obj in contenido.get("Contents", []):
        tamano_mb = obj["Size"] / 1024 / 1024
        print(f"  📄 {obj['Key']}  ({tamano_mb:.1f} MB)")

    descarga = Path("data") / "test_descarga.csv"
    s3.download_file("raw", key, str(descarga))

    tamano_original = archivo.stat().st_size
    tamano_descarga = descarga.stat().st_size

    if tamano_original == tamano_descarga:
        print(f"\n✔ Verificación OK: el archivo descargado tiene el mismo tamaño ({tamano_original:,} bytes)")
    else:
        print(f"\n✘ Los tamaños no coinciden: original={tamano_original}, descarga={tamano_descarga}")

    descarga.unlink()
    print("  Archivo de prueba borrado.")

print("\n🎉 Datalake S3 listo para usar.")
