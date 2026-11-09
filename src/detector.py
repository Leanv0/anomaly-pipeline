"""
detector.py — Módulo de detección de anomalías (Reglas + Isolation Forest).

Flujo:
1. Carga datasets Parquet desde el bucket 'processed' de S3 (RustFS).
2. Prepara matrices de características y etiquetas reales (ground truth).
3. Aplica reglas heurísticas de firma TCP (PortScan).
4. Entrena e infiere anomalías con Isolation Forest (scikit-learn).
5. Construye la capa Ensamble (Defensa en Profundidad).
6. Persiste alertas en streaming en PostgreSQL (tabla 'alerts') y métricas en 'pipeline_runs'.
"""

import os
import io
import time
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
import boto3
import pandas as pd
import numpy as np
import psycopg
from sklearn.metrics import (
    confusion_matrix,
    precision_score,
    recall_score,
    f1_score,
)
from sklearn.ensemble import IsolationForest

logger = logging.getLogger(__name__)

load_dotenv()

# Configuración S3
STORAGE_ENDPOINT = os.getenv("STORAGE_ENDPOINT", "http://localhost:9000")
STORAGE_ACCESS_KEY = os.getenv("STORAGE_ACCESS_KEY", "rustfsadmin")
STORAGE_SECRET_KEY = os.getenv("STORAGE_SECRET_KEY", "rustfsadmin")
BUCKET_PROCESSED = "processed"
BUCKET_ALERTS = "alerts"

# Configuración PostgreSQL
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "anomalydb")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

# Columnas con varianza cero en la línea base normal
CONSTANT_COLUMNS = [
    "Bwd PSH Flags",
    "Fwd URG Flags",
    "Bwd URG Flags",
    "CWE Flag Count",
    "Fwd Avg Bytes/Bulk",
    "Fwd Avg Packets/Bulk",
    "Fwd Avg Bulk Rate",
    "Bwd Avg Bytes/Bulk",
    "Bwd Avg Packets/Bulk",
    "Bwd Avg Bulk Rate",
]

# Variables nucleares de red seleccionadas para el modelo
DEFAULT_MODEL_FEATURES = [
    "Destination Port",
    "Flow Duration",
    "Total Fwd Packets",
    "Total Backward Packets",
    "Flow Packets/s",
    "Flow Bytes/s",
    "PSH Flag Count",
    "ACK Flag Count",
    "Average Packet Size",
]


def get_s3_client():
    """Inicializa y devuelve el cliente S3 configurado."""
    return boto3.client(
        "s3",
        endpoint_url=STORAGE_ENDPOINT,
        aws_access_key_id=STORAGE_ACCESS_KEY,
        aws_secret_access_key=STORAGE_SECRET_KEY,
    )


def load_parquet_from_s3(s3_client, bucket_name: str, file_key: str, columns: list = None) -> pd.DataFrame:
    """
    Descarga un archivo Parquet desde S3 a memoria RAM y lo carga en DataFrame.
    """
    logger.info("Descargando '%s' desde bucket '%s'...", file_key, bucket_name)
    buffer = io.BytesIO()
    s3_client.download_fileobj(bucket_name, file_key, buffer)
    buffer.seek(0)

    df = pd.read_parquet(buffer, columns=columns)
    logger.info("Cargado: %s filas × %d columnas", f"{df.shape[0]:,}", df.shape[1])
    return df


def prepare_features_and_labels(df: pd.DataFrame, drop_constants: bool = True):
    """
    Separa el DataFrame en la matriz de features X y el vector binario de etiquetas y.
    (0 = BENIGN, 1 = Ataque/Anomalía).
    """
    if "Label" not in df.columns:
        raise ValueError("El DataFrame no contiene la columna obligatoria 'Label'.")

    y = (df["Label"] != "BENIGN").astype(int)

    cols_a_descartar = ["Label"]
    if drop_constants:
        cols_a_descartar.extend([col for col in CONSTANT_COLUMNS if col in df.columns])

    X = df.drop(columns=cols_a_descartar)
    return X, y


def detect_rules(X: pd.DataFrame, strategy: str = "signature") -> pd.Series:
    """
    Aplica reglas heurísticas o de firma de tráfico (PortScan).

    Estrategias:
    - 'signature': Flujos cortos (< 1000 µs), pocos paquetes (<= 2), PSH=1 y ACK=0.
    - 'volumetric': Duración < 500 µs, paquetes <= 2, payload <= 10 bytes.
    """
    if strategy == "signature":
        mask = (
            (X["Flow Duration"] < 1000)
            & (X["Total Fwd Packets"] <= 2)
            & (X["PSH Flag Count"] == 1)
            & (X["ACK Flag Count"] == 0)
        )
    elif strategy == "volumetric":
        mask = (
            (X["Flow Duration"] < 500)
            & (X["Total Fwd Packets"] <= 2)
            & (X["Fwd Packet Length Max"] <= 10)
        )
    else:
        raise ValueError(f"Estrategia desconocida: '{strategy}'. Usar 'signature' o 'volumetric'.")

    return mask.astype(int)


def evaluate_detector(y_true: pd.Series, y_pred: pd.Series, detector_name: str = "Detector") -> dict:
    """
    Calcula la matriz de confusión y las métricas clave de ciberseguridad:
    Precisión, Recall, F1-score y False Positive Rate (FPR).
    """
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()

    prec = precision_score(y_true, y_pred, zero_division=0)
    rec = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

    logger.info("=" * 65)
    logger.info("EVALUACIÓN: %s", detector_name.upper())
    logger.info("=" * 65)
    logger.info("Muestras evaluadas: %s flujos", f"{len(y_true):,}")
    logger.info("[ Matriz de Confusión ]")
    logger.info("  TP: %s | FP: %s | FN: %s | TN: %s",
                f"{tp:,}", f"{fp:,}", f"{fn:,}", f"{tn:,}")
    logger.info("[ Métricas de Rendimiento ]")
    logger.info("  Precisión: %.4f%% | Recall: %.4f%% | F1: %.4f | FPR: %.4f%%",
                prec * 100, rec * 100, f1, fpr * 100)
    logger.info("=" * 65)

    return {
        "detector": detector_name,
        "total_samples": len(y_true),
        "true_positives": int(tp),
        "false_positives": int(fp),
        "false_negatives": int(fn),
        "true_negatives": int(tn),
        "precision": float(prec),
        "recall": float(rec),
        "f1_score": float(f1),
        "fpr": float(fpr),
    }


def train_isolation_forest(
    X_train: pd.DataFrame,
    features: list = None,
    contamination: float = 0.05,
    n_estimators: int = 100,
    max_samples: int = 1024,
    random_state: int = 42,
) -> tuple:
    """
    Entrena el modelo no supervisado Isolation Forest sobre tráfico normal.
    """
    if features is None:
        features = DEFAULT_MODEL_FEATURES

    features_presentes = [col for col in features if col in X_train.columns]
    X_sub = X_train[features_presentes]

    logger.info("Entrenando Isolation Forest con %s flujos normales...", f"{len(X_sub):,}")
    logger.info("Features (%d): %s", len(features_presentes), features_presentes)

    iso = IsolationForest(
        n_estimators=n_estimators,
        max_samples=max_samples,
        contamination=contamination,
        random_state=random_state,
        n_jobs=-1,
    )

    t0 = time.time()
    iso.fit(X_sub)
    t_entrenamiento = time.time() - t0

    logger.info("Entrenamiento completado en %.2f segundos (offset: %.4f).",
                t_entrenamiento, iso.offset_)

    return iso, features_presentes


def predict_isolation_forest(
    model: IsolationForest,
    X: pd.DataFrame,
    features: list = None,
) -> tuple:
    """
    Genera predicciones binarias (1=anomalía, 0=normal) y scores continuos.
    """
    if features is None:
        features = DEFAULT_MODEL_FEATURES

    X_sub = X[features]
    preds_raw = model.predict(X_sub)

    y_pred = pd.Series((preds_raw == -1).astype(int), index=X.index)
    scores = model.decision_function(X_sub)

    return y_pred, scores


def get_db_connection():
    """Retorna una conexión activa hacia PostgreSQL."""
    return psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def save_alerts_to_s3(s3_client, df_alerts: pd.DataFrame, source_file: str) -> str:
    """
    Guarda las alertas en formato Parquet en el bucket 'alerts' de S3.
    """
    alerts_key = source_file.replace(".parquet", "_alerts.parquet")

    buffer = io.BytesIO()
    df_alerts.to_parquet(buffer, index=False, engine="pyarrow", compression="snappy")
    size_mb = len(buffer.getvalue()) / 1024 / 1024
    buffer.seek(0)

    s3_client.upload_fileobj(buffer, BUCKET_ALERTS, alerts_key)
    logger.info("Alertas guardadas en S3 (bucket '%s'): '%s' (%.2f MB)",
                BUCKET_ALERTS, alerts_key, size_mb)
    return alerts_key


def save_results_to_db(
    df: pd.DataFrame,
    y_pred_sig: pd.Series,
    y_pred_iso: pd.Series,
    scores_iso: np.ndarray,
    source_file: str,
    processing_time: float,
    s3_client=None,
) -> dict:
    """
    Persiste las alertas en la tabla 'alerts' (vía COPY) y la métrica en 'pipeline_runs'.
    """
    mask_alert = (y_pred_sig == 1) | (y_pred_iso == 1)
    total_anomalias = int(mask_alert.sum())
    total_flujos = len(df)

    logger.info("Persistiendo resultados en PostgreSQL (%s:%s/%s)...", DB_HOST, DB_PORT, DB_NAME)
    logger.info("Total de flujos analizados: %s | Alertas: %s",
                f"{total_flujos:,}", f"{total_anomalias:,}")

    if total_anomalias == 0:
        logger.info("No se registraron anomalías para persistir.")
        return {"total_alerts": 0, "run_id": None}

    df_alerts = df[mask_alert].copy()

    # Clasificar detector de origen
    sig_subset = y_pred_sig[mask_alert] == 1
    iso_subset = y_pred_iso[mask_alert] == 1

    detector_labels = np.where(
        sig_subset & iso_subset,
        "ensemble",
        np.where(sig_subset, "signature_rule", "isolation_forest"),
    )

    now_utc = datetime.now(timezone.utc)
    df_alerts["detected_at"] = now_utc
    df_alerts["source_file"] = source_file
    df_alerts["detector"] = detector_labels
    df_alerts["anomaly_score"] = scores_iso[mask_alert]

    # Tipado explícito para protocolo COPY
    df_alerts["Destination Port"] = df_alerts["Destination Port"].fillna(0).astype(int)
    df_alerts["Flow Duration"] = df_alerts["Flow Duration"].fillna(0).astype("int64")
    df_alerts["Total Fwd Packets"] = df_alerts["Total Fwd Packets"].fillna(0).astype(int)
    df_alerts["Total Backward Packets"] = df_alerts["Total Backward Packets"].fillna(0).astype(int)

    if s3_client is not None:
        save_alerts_to_s3(s3_client, df_alerts, source_file)

    cols_para_db = [
        "detected_at",
        "source_file",
        "Destination Port",
        "Flow Duration",
        "Total Fwd Packets",
        "Total Backward Packets",
        "Flow Bytes/s",
        "Flow Packets/s",
        "detector",
        "anomaly_score",
        "Label",
    ]

    t0 = time.time()
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Idempotencia: limpiar registros previos del mismo archivo
            cur.execute("DELETE FROM alerts WHERE source_file = %s;", (source_file,))
            filas_borradas = cur.rowcount
            if filas_borradas > 0:
                logger.info("Idempotencia: eliminadas %s alertas previas de '%s'.",
                            f"{filas_borradas:,}", source_file)

            # Volcado masivo streaming con protocolo COPY
            logger.info("Volcando %s alertas con protocolo COPY...", f"{total_anomalias:,}")
            with cur.copy("""
                COPY alerts (
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
                ) FROM STDIN
            """) as copy:
                for row in df_alerts[cols_para_db].itertuples(index=False, name=None):
                    copy.write_row(row)

            # Registro histórico de corrida
            cur.execute("""
                INSERT INTO pipeline_runs (
                    source_file,
                    total_flows_processed,
                    total_anomalies_detected,
                    processing_time_seconds,
                    status
                ) VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
            """, (
                source_file,
                total_flujos,
                total_anomalias,
                round(processing_time, 2),
                "SUCCESS",
            ))
            run_id = cur.fetchone()[0]

        conn.commit()

    t_db = time.time() - t0
    logger.info("Inserción completada en %.2f segundos (run_id=%s).", t_db, run_id)

    return {
        "run_id": run_id,
        "total_alerts": total_anomalias,
        "db_insert_time_seconds": round(t_db, 2),
    }


def record_pipeline_run_error(source_file: str, error_message: str) -> None:
    """Registra una corrida con error en 'pipeline_runs' (Fail-Soft)."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO pipeline_runs (
                        source_file,
                        total_flows_processed,
                        total_anomalies_detected,
                        processing_time_seconds,
                        status
                    ) VALUES (%s, %s, %s, %s, %s);
                """, (
                    source_file,
                    0,
                    0,
                    0.0,
                    f"ERROR: {error_message[:200]}",
                ))
            conn.commit()
        logger.info("Estado de error registrado en 'pipeline_runs' para '%s'.", source_file)
    except Exception as db_err:
        logger.error("No se pudo registrar el error en la base de datos: %s", db_err)


def detect_file(
    s3_client,
    file_key: str,
    iso_model: IsolationForest,
    model_features: list,
) -> dict:
    """
    Ejecuta el ciclo de detección completo sobre un archivo Parquet individual.
    """
    t_start = time.time()
    logger.info("=" * 60)
    logger.info("Iniciando detección en archivo: %s", file_key)
    logger.info("=" * 60)

    # 1. Carga de datos
    df = load_parquet_from_s3(s3_client, BUCKET_PROCESSED, file_key)
    X, y = prepare_features_and_labels(df)

    # 2. Regla de firma TCP
    y_pred_sig = detect_rules(X, strategy="signature")
    metrics_sig = evaluate_detector(y, y_pred_sig, detector_name=f"Regla Firma TCP ({file_key})")

    # 3. Isolation Forest
    y_pred_iso, scores_iso = predict_isolation_forest(iso_model, X, features=model_features)
    metrics_iso = evaluate_detector(y, y_pred_iso, detector_name=f"Isolation Forest ({file_key})")

    # 4. Ensamble (Defensa en Profundidad)
    y_pred_ensemble = ((y_pred_sig == 1) | (y_pred_iso == 1)).astype(int)
    metrics_ensemble = evaluate_detector(y, y_pred_ensemble, detector_name=f"Ensemble ({file_key})")

    total_time = time.time() - t_start

    # 5. Persistencia
    db_resumen = save_results_to_db(
        df=df,
        y_pred_sig=y_pred_sig,
        y_pred_iso=y_pred_iso,
        scores_iso=scores_iso,
        source_file=file_key,
        processing_time=total_time,
        s3_client=s3_client,
    )

    return {
        "source_file": file_key,
        "total_flows": len(df),
        "total_alerts": db_resumen.get("total_alerts", 0),
        "run_id": db_resumen.get("run_id"),
        "processing_time": round(total_time, 2),
        "metrics_ensemble": metrics_ensemble,
    }


def run_detection_pipeline(
    s3_client=None,
    target_files: list = None,
    baseline_file: str = "Monday-WorkingHours.parquet",
) -> list[dict]:
    """
    Orquesta la detección:
    1. Calibra Isolation Forest con la línea base limpia (Lunes).
    2. Ejecuta la detección sobre los archivos objetivo de prueba.
    """
    if s3_client is None:
        s3_client = get_s3_client()

    logger.info("=" * 60)
    logger.info("PASO 1: ENTRENAMIENTO DE LÍNEA BASE CON ISOLATION FOREST")
    logger.info("=" * 60)

    df_train = load_parquet_from_s3(s3_client, BUCKET_PROCESSED, baseline_file)
    X_train, y_train = prepare_features_and_labels(df_train)

    iso_model, features_usadas = train_isolation_forest(
        X_train,
        contamination=0.05,
        max_samples=1024,
        random_state=42,
    )

    y_pred_train, _ = predict_isolation_forest(iso_model, X_train, features=features_usadas)
    evaluate_detector(y_train, y_pred_train, detector_name=f"Línea Base ({baseline_file})")

    del df_train, X_train, y_train

    if target_files is None:
        resp = s3_client.list_objects_v2(Bucket=BUCKET_PROCESSED)
        todos_los_objetos = resp.get("Contents", [])
        target_files = [
            obj["Key"]
            for obj in todos_los_objetos
            if obj["Key"].endswith(".parquet")
            and obj["Key"] != baseline_file
            and not obj["Key"].endswith("_alerts.parquet")
        ]
        target_files.sort()

    logger.info("=" * 60)
    logger.info("PASO 2: DETECCIÓN EN ARCHIVOS OBJETIVO (%d archivos)", len(target_files))
    logger.info("=" * 60)

    resultados = []
    exitosos = 0
    fallidos = 0

    for i, file_key in enumerate(target_files, start=1):
        logger.info("[%d/%d] Procesando: %s", i, len(target_files), file_key)
        try:
            resumen = detect_file(
                s3_client=s3_client,
                file_key=file_key,
                iso_model=iso_model,
                model_features=features_usadas,
            )
            resultados.append(resumen)
            exitosos += 1
        except Exception as e:
            fallidos += 1
            logger.error("Error procesando detección en '%s': %s", file_key, e, exc_info=True)
            record_pipeline_run_error(file_key, str(e))

    logger.info("=" * 60)
    logger.info("RESUMEN DE DETECCIÓN")
    logger.info("=" * 60)
    logger.info("Archivos analizados con éxito : %d", exitosos)
    logger.info("Archivos fallidos            : %d", fallidos)
    total_alertas = sum(r.get("total_alerts", 0) for r in resultados)
    logger.info("Total acumulado de alertas   : %s", f"{total_alertas:,}")

    return resultados


if __name__ == "__main__":
    from logger_config import setup_logging
    setup_logging()
    logger.info("Ejecutando detector.py de forma independiente...")
    run_detection_pipeline()
