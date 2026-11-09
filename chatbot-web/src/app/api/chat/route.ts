/**
 * POST /api/chat — Endpoint del chatbot con rate limiting y prevención de fuga de información.
 */

import { NextRequest, NextResponse } from "next/server";
import { processChat } from "@/lib/gemini";
import { checkRateLimit } from "@/lib/rateLimit";

// Permitir hasta 30 segundos de ejecución (function calling + DB queries)
export const maxDuration = 30;

export async function POST(request: NextRequest) {
  try {
    // 1. Rate Limiting por IP (20 peticiones por minuto)
    const forwarded = request.headers.get("x-forwarded-for");
    const ip = forwarded ? forwarded.split(",")[0].trim() : "127.0.0.1";

    const rateResult = checkRateLimit(ip, 20, 60_000);
    if (!rateResult.allowed) {
      const waitSeconds = Math.ceil(rateResult.resetInMs / 1000);
      return NextResponse.json(
        {
          error: `Has superado el límite de consultas permitidas. Por favor, aguardá ${waitSeconds} segundos antes de intentar nuevamente.`,
        },
        {
          status: 429,
          headers: {
            "Retry-After": waitSeconds.toString(),
          },
        },
      );
    }

    const body = await request.json();
    const { message, history, apiKey: bodyApiKey } = body;

    const headerApiKey = request.headers.get("x-gemini-key") || undefined;
    const resolvedApiKey = (bodyApiKey || headerApiKey || process.env.GEMINI_API_KEY)?.trim();

    // 2. Validación de variables esenciales
    if (!resolvedApiKey) {
      return NextResponse.json(
        {
          error:
            "GEMINI_API_KEY no está configurada. Podés agregarla en el botón de Configuración (⚙️) o en las variables de entorno de Vercel.",
        },
        { status: 400 },
      );
    }
    if (!process.env.POSTGRES_URL) {
      return NextResponse.json(
        {
          error:
            "POSTGRES_URL no está configurada en las variables de entorno.",
        },
        { status: 500 },
      );
    }

    if (!message || typeof message !== "string" || !message.trim()) {
      return NextResponse.json(
        { error: "El mensaje es requerido." },
        { status: 400 },
      );
    }

    // 3. Procesamiento seguro con Gemini y PostgreSQL
    const result = await processChat(message.trim(), history || [], resolvedApiKey);

    return NextResponse.json(result, {
      headers: {
        "X-RateLimit-Remaining": rateResult.remaining.toString(),
      },
    });
  } catch (error: unknown) {
    // Registro detallado en logs internos del servidor (seguro, no visible al público)
    console.error("[SECURITY] Error interno en /api/chat:", error);

    // Respuesta sanitizada al cliente para prevenir Information Disclosure
    const userSafeMessage =
      error instanceof Error && error.message.includes("GEMINI_API_KEY")
        ? error.message
        : "Ocurrió un error al procesar tu consulta con el sistema de análisis. Por favor, reintentá en unos momentos.";

    return NextResponse.json(
      { error: userSafeMessage },
      { status: 500 },
    );
  }
}
