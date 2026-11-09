/**
 * db.ts — Pool de conexiones a PostgreSQL.
 *
 * Usa la variable POSTGRES_URL (connection string) y soporta
 * SSL configurable para proveedores cloud (Neon, Supabase, etc.).
 */

import { Pool, QueryResultRow } from "pg";

const sslConfig =
  process.env.POSTGRES_SSL === "true"
    ? { rejectUnauthorized: false }
    : false;

const pool = new Pool({
  connectionString: process.env.POSTGRES_URL,
  ssl: sslConfig,
  max: 5,
  idleTimeoutMillis: 30_000,
  connectionTimeoutMillis: 10_000,
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
