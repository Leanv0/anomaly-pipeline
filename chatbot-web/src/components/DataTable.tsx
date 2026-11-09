"use client";

/**
 * DataTable.tsx — Tabla responsiva para datos tabulares del pipeline.
 *
 * Formatea números, trunca textos largos y soporta scroll horizontal.
 */

interface DataTableProps {
  data: Record<string, unknown>[];
  title: string;
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") {
    // Si tiene decimales, mostrar hasta 4
    if (!Number.isInteger(value)) {
      return value.toLocaleString("es-AR", { maximumFractionDigits: 4 });
    }
    return value.toLocaleString("es-AR");
  }
  const str = String(value);
  // Truncar strings muy largos
  return str.length > 40 ? str.substring(0, 37) + "…" : str;
}

function formatHeader(key: string): string {
  // Convertir snake_case a título legible
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function DataTable({ data, title }: DataTableProps) {
  if (!data || data.length === 0) {
    return (
      <div className="bg-slate-700/30 rounded-xl p-4 text-center text-slate-400 mt-2">
        Sin datos disponibles.
      </div>
    );
  }

  const columns = Object.keys(data[0]);

  return (
    <div className="bg-slate-700/30 border border-slate-600/30 rounded-xl p-4 mt-2 overflow-hidden">
      <h3 className="text-sm font-medium text-slate-300 mb-3">{title}</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead>
            <tr className="border-b border-slate-600">
              {columns.map((col) => (
                <th
                  key={col}
                  className="px-3 py-2 text-xs font-semibold text-slate-400 uppercase tracking-wider whitespace-nowrap"
                >
                  {formatHeader(col)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => (
              <tr
                key={i}
                className="border-b border-slate-700/50 hover:bg-slate-600/20 transition-colors"
              >
                {columns.map((col) => (
                  <td
                    key={col}
                    className="px-3 py-2 text-slate-200 whitespace-nowrap font-mono text-xs"
                  >
                    {formatCell(row[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-slate-500 mt-2 text-right">
        {data.length} {data.length === 1 ? "fila" : "filas"}
      </p>
    </div>
  );
}
