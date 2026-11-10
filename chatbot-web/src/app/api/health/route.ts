/**
 * GET /api/health — Endpoint de diagnóstico del estado del servicio.
 *
 * Verifica la conectividad con PostgreSQL y cuenta las alertas registradas.
 */

import { NextResponse } from "next/server";
import { query } from "@/lib/db";

export const dynamic = "force-dynamic";
export const maxDuration = 30;

export async function GET() {
  const hasEnvPostgres = Boolean(process.env.POSTGRES_URL);
  const hasEnvGemini = Boolean(process.env.GEMINI_API_KEY);

  if (!hasEnvPostgres) {
    return NextResponse.json(
      {
        status: "misconfigured",
        postgresConnected: false,
        geminiConfigured: hasEnvGemini,
        error: "POSTGRES_URL no está configurada en las variables de entorno de Vercel.",
      },
      { status: 503 },
    );
  }

  try {
    const alertsRes = await query<{ count: number }>(
      "SELECT COUNT(*)::int AS count FROM alerts",
    );
    const runsRes = await query<{ count: number }>(
      "SELECT COUNT(*)::int AS count FROM pipeline_runs",
    );

    const alertsCount = alertsRes[0]?.count ?? 0;
    const runsCount = runsRes[0]?.count ?? 0;

    return NextResponse.json({
      status: "healthy",
      postgresConnected: true,
      geminiConfigured: hasEnvGemini,
      alertsCount,
      runsCount,
      timestamp: new Date().toISOString(),
    });
  } catch (error: unknown) {
    console.error("[SECURITY] Error en health check de PostgreSQL:", error);

    const safeMessage =
      error instanceof Error ? error.message : "Error al conectar a PostgreSQL";

    return NextResponse.json(
      {
        status: "database_error",
        postgresConnected: false,
        geminiConfigured: hasEnvGemini,
        error: safeMessage,
      },
      { status: 500 },
    );
  }
}
