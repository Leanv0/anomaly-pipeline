/**
 * rateLimit.ts — Limitador de tasa (Rate Limiting) en memoria por IP.
 *
 * Protege los endpoints serverless contra ataques de denegación de servicio (DoS)
 * y abuso de cuota de la API de Gemini (Denial of Wallet).
 */

interface RateLimitRecord {
  count: number;
  resetTime: number;
}

const ipRequestMap = new Map<string, RateLimitRecord>();

// Limpiar periódicamente registros expirados de memoria cada 5 minutos
if (typeof setInterval !== "undefined") {
  setInterval(() => {
    const now = Date.now();
    ipRequestMap.forEach((record, ip) => {
      if (now > record.resetTime) {
        ipRequestMap.delete(ip);
      }
    });
  }, 5 * 60 * 1000);
}

/**
 * Valida si la IP del cliente superó el límite de peticiones permitido.
 *
 * @param ip Dirección IP del cliente.
 * @param limit Cantidad máxima de peticiones permitidas por ventana.
 * @param windowMs Duración de la ventana de tiempo en milisegundos (default: 60s).
 */
export function checkRateLimit(
  ip: string,
  limit: number = 20,
  windowMs: number = 60_000,
): { allowed: boolean; remaining: number; resetInMs: number } {
  const now = Date.now();
  const record = ipRequestMap.get(ip);

  if (!record || now > record.resetTime) {
    ipRequestMap.set(ip, {
      count: 1,
      resetTime: now + windowMs,
    });
    return { allowed: true, remaining: limit - 1, resetInMs: windowMs };
  }

  if (record.count >= limit) {
    return {
      allowed: false,
      remaining: 0,
      resetInMs: Math.max(0, record.resetTime - now),
    };
  }

  record.count += 1;
  return {
    allowed: true,
    remaining: limit - record.count,
    resetInMs: Math.max(0, record.resetTime - now),
  };
}
