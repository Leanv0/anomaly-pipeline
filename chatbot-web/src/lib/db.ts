/**
 * db.ts — Pool de conexiones a PostgreSQL.
 *
 * Usa la variable POSTGRES_URL (connection string) y soporta
 * SSL configurable para proveedores cloud (Neon, Supabase, etc.).
 */

import { Pool, QueryResultRow } from "pg";

let rawConnectionString = (process.env.POSTGRES_URL || "").trim().replace(/^["']|["']$/g, "");
// Remover channel_binding ya que node-postgres en serverless puede fallar en SCRAM
const connectionString = rawConnectionString
  .replace(/([?&])channel_binding=[^&]+(&|$)/, "$1")
  .replace(/[?&]$/, "");

const isCloudOrSsl =
  process.env.POSTGRES_SSL === "true" ||
  connectionString.includes("sslmode=require") ||
  connectionString.includes("neon.tech") ||
  connectionString.includes("supabase.co") ||
  connectionString.includes("supabase.com");

const sslConfig = isCloudOrSsl ? { rejectUnauthorized: false } : false;

const pool = new Pool({
  connectionString,
  ssl: sslConfig,
  max: 3,
  idleTimeoutMillis: 10_000,
  connectionTimeoutMillis: 20_000,
});

// Evitar que errores no capturados en conexiones inactivas terminen el proceso en Node.js/Vercel
pool.on("error", (err) => {
  console.warn("[PostgreSQL Pool] Advertencia en conexión inactiva:", err.message);
});

/**
 * Ejecuta una consulta SQL parametrizada y devuelve las filas resultantes.
 */
export async function query<T extends QueryResultRow = QueryResultRow>(
  text: string,
  params?: unknown[],
): Promise<T[]> {
  const client = await pool.connect();
  try {
    const result = await client.query<T>(text, params);
    return result.rows;
  } finally {
    client.release();
  }
}

export default pool;
