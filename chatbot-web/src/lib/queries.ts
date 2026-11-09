/**
 * queries.ts — Funciones de consulta SQL contra PostgreSQL.
 *
 * Cada función corresponde a un "tool" que Gemini puede invocar
 * para obtener datos reales de la base de datos del pipeline.
 */

import { query } from "./db";

/* ------------------------------------------------------------------ */
/*  Interfaces de resultado                                            */
/* ------------------------------------------------------------------ */

export interface AttackTypeCount {
  attack_type: string;
  count: number;
}

export interface DetectorCount {
  detector: string;
  count: number;
}

export interface PortCount {
  port: number;
  count: number;
}

export interface AlertRecord {
  id: number;
  detected_at: string;
  source_file: string;
  destination_port: number;
  flow_duration: number;
  detector: string;
  anomaly_score: number;
  label_original: string;
}

export interface PipelineRun {
  id: number;
  run_at: string;
  source_file: string;
  total_flows_processed: number;
  total_anomalies_detected: number;
  processing_time_seconds: number;
  status: string;
}

export interface AnomalyStats {
  total_flows: number;
  total_anomalies: number;
  rate_percentage: number;
}

/* ------------------------------------------------------------------ */
/*  Funciones de consulta (una por tool de Gemini)                     */
/* ------------------------------------------------------------------ */

/** Distribución de tipos de ataque detectados. */
export async function getAttackTypeDistribution(): Promise<AttackTypeCount[]> {
  return query<AttackTypeCount>(`
    SELECT label_original AS attack_type, COUNT(*)::int AS count
    FROM alerts
    WHERE label_original IS NOT NULL
      AND label_original != 'BENIGN'
    GROUP BY label_original
    ORDER BY count DESC
  `);
}

/** Cantidad total de alertas registradas. */
export async function getTotalAlerts(): Promise<{ total: number }> {
  const rows = await query<{ total: number }>(
    "SELECT COUNT(*)::int AS total FROM alerts",
  );
  return rows[0];
}

/** Tasa global de anomalías (anomalías / flujos analizados). */
export async function getAnomalyRate(): Promise<AnomalyStats> {
  const rows = await query<AnomalyStats>(`
    SELECT
      SUM(total_flows_processed)::int        AS total_flows,
      SUM(total_anomalies_detected)::int     AS total_anomalies,
      ROUND(
        (SUM(total_anomalies_detected)::numeric
         / NULLIF(SUM(total_flows_processed), 0)) * 100,
        2
      )::float AS rate_percentage
    FROM pipeline_runs
    WHERE status = 'SUCCESS'
  `);
  return rows[0];
}

/** Cantidad de alertas agrupadas por tipo de detector. */
export async function getAlertsByDetector(): Promise<DetectorCount[]> {
  return query<DetectorCount>(`
    SELECT detector, COUNT(*)::int AS count
    FROM alerts
    GROUP BY detector
    ORDER BY count DESC
  `);
}

/** Top N puertos de destino más atacados. */
export async function getTopAttackedPorts(
  limit: number = 10,
): Promise<PortCount[]> {
  return query<PortCount>(
    `SELECT destination_port AS port, COUNT(*)::int AS count
     FROM alerts
     GROUP BY destination_port
     ORDER BY count DESC
     LIMIT $1`,
    [limit],
  );
}

/** Últimas N alertas registradas (más recientes primero). */
export async function getRecentAlerts(
  limit: number = 10,
): Promise<AlertRecord[]> {
  return query<AlertRecord>(
    `SELECT id, detected_at::text, source_file, destination_port,
            flow_duration, detector,
            ROUND(anomaly_score::numeric, 4)::float AS anomaly_score,
            label_original
     FROM alerts
     ORDER BY detected_at DESC
     LIMIT $1`,
    [limit],
  );
}

/** Historial completo de ejecuciones del pipeline. */
export async function getPipelineRuns(): Promise<PipelineRun[]> {
  return query<PipelineRun>(`
    SELECT id, run_at::text, source_file,
           total_flows_processed, total_anomalies_detected,
           ROUND(processing_time_seconds::numeric, 2)::float AS processing_time_seconds,
           status
    FROM pipeline_runs
    ORDER BY run_at DESC
  `);
}

/**
 * Ejecuta una consulta SQL personalizada (solo SELECT, read-only).
 *
 * Medidas de seguridad:
 * - Solo permite sentencias SELECT.
 * - Rechaza palabras clave DML/DDL (INSERT, UPDATE, DELETE, DROP, etc.).
 * - Limita resultados a 100 filas máximo.
 */
export async function runCustomQuery(
  sql: string,
): Promise<Record<string, unknown>[]> {
  const normalized = sql.trim().toUpperCase();

  if (!normalized.startsWith("SELECT")) {
    throw new Error("Solo se permiten consultas SELECT.");
  }

  const forbidden = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
    "CREATE", "GRANT", "REVOKE", "EXECUTE", "COPY",
  ];
  const afterSelect = normalized.substring(6);
  for (const keyword of forbidden) {
    const regex = new RegExp(`\\b${keyword}\\b`);
    if (regex.test(afterSelect)) {
      throw new Error(
        `Operación no permitida: ${keyword}. Solo consultas de lectura.`,
      );
    }
  }

  // Agregar LIMIT si el usuario no lo especificó
  if (!normalized.includes("LIMIT")) {
    sql = sql.replace(/;?\s*$/, "") + " LIMIT 100";
  }

  return query(sql);
}
