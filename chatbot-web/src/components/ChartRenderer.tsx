"use client";

/**
 * ChartRenderer.tsx — Renderiza gráficos dinámicos según el tipo de visualización.
 *
 * Soporta: bar (barras), pie (torta), stat (tarjetas de métricas).
 * Usa Recharts para los gráficos SVG responsivos.
 */

import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

// Paleta de colores para gráficos (estilo SOC/ciberseguridad)
const COLORS = [
  "#06b6d4", // cyan-500
  "#10b981", // emerald-500
  "#f59e0b", // amber-500
  "#ef4444", // red-500
  "#8b5cf6", // violet-500
  "#ec4899", // pink-500
  "#14b8a6", // teal-500
  "#f97316", // orange-500
  "#6366f1", // indigo-500
  "#84cc16", // lime-500
];

interface Visualization {
  type: "bar" | "pie" | "stat" | "table";
  title: string;
  data: Record<string, unknown>[];
  config: Record<string, string>;
}

// Formato de números grandes: 606769 → "606,769"
function formatNumber(value: unknown): string {
  if (typeof value === "number") {
    return value.toLocaleString("es-AR");
  }
  return String(value ?? "");
}

// Etiquetas legibles para claves de datos
function formatLabel(key: string): string {
  const labels: Record<string, string> = {
    total: "Total",
    total_flows: "Flujos Analizados",
    total_anomalies: "Anomalías Detectadas",
    rate_percentage: "Tasa de Anomalías (%)",
    count: "Cantidad",
    attack_type: "Tipo de Ataque",
    detector: "Detector",
    port: "Puerto",
  };
  return labels[key] || key.replace(/_/g, " ");
}

/** Tooltip personalizado con estilo oscuro. */
function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ value: number; name: string }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 shadow-xl">
      <p className="text-slate-300 text-xs mb-1">{label}</p>
      {payload.map((entry, i) => (
        <p key={i} className="text-cyan-400 font-semibold text-sm">
          {formatNumber(entry.value)}
        </p>
      ))}
    </div>
  );
}

export default function ChartRenderer({ visualization }: { visualization: Visualization }) {
  const { type, title, data, config } = visualization;

  if (!data || data.length === 0) {
    return (
      <div className="bg-slate-700/30 rounded-xl p-4 text-center text-slate-400">
        Sin datos disponibles.
      </div>
    );
  }

  /* ---------- STAT: tarjetas de métricas KPI ---------- */
  if (type === "stat") {
    const entries = Object.entries(data[0]).filter(
      ([, v]) => v !== null && v !== undefined,
    );
    return (
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-2">
        {entries.map(([key, value]) => (
          <div
            key={key}
            className="bg-gradient-to-br from-slate-700/80 to-slate-800/80 border border-slate-600/50 rounded-xl p-4 text-center"
          >
            <p className="text-slate-400 text-xs uppercase tracking-wider mb-1">
              {formatLabel(key)}
            </p>
            <p className="text-2xl font-bold text-cyan-400">
              {typeof value === "number" && key.includes("percentage")
                ? `${value}%`
                : formatNumber(value)}
            </p>
          </div>
        ))}
      </div>
    );
  }

  /* ---------- BAR: gráfico de barras ---------- */
  if (type === "bar") {
    const xKey = config.xKey || Object.keys(data[0])[0];
    const yKey = config.yKey || Object.keys(data[0])[1];

    return (
      <div className="bg-slate-700/30 border border-slate-600/30 rounded-xl p-4 mt-2">
        <h3 className="text-sm font-medium text-slate-300 mb-3">{title}</h3>
        <ResponsiveContainer width="100%" height={320}>
          <BarChart
            data={data}
            margin={{ top: 5, right: 20, left: 10, bottom: 60 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis
              dataKey={xKey}
              tick={{ fill: "#94a3b8", fontSize: 11 }}
              angle={-35}
              textAnchor="end"
              height={80}
              interval={0}
            />
            <YAxis
              tick={{ fill: "#94a3b8", fontSize: 11 }}
              tickFormatter={(v: number) => v.toLocaleString()}
            />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey={yKey} radius={[4, 4, 0, 0]}>
              {data.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }

  /* ---------- PIE: gráfico de torta ---------- */
  if (type === "pie") {
    const nameKey = config.nameKey || Object.keys(data[0])[0];
    const valueKey = config.valueKey || Object.keys(data[0])[1];

    return (
      <div className="bg-slate-700/30 border border-slate-600/30 rounded-xl p-4 mt-2">
        <h3 className="text-sm font-medium text-slate-300 mb-3">{title}</h3>
        <ResponsiveContainer width="100%" height={320}>
          <PieChart>
            <Pie
              data={data}
              dataKey={valueKey}
              nameKey={nameKey}
              cx="50%"
              cy="50%"
              outerRadius={110}
              strokeWidth={2}
              stroke="#0a0e1a"
              label={({ name, percent }: { name: string; percent: number }) =>
                `${name} (${(percent * 100).toFixed(1)}%)`
              }
              labelLine={{ stroke: "#64748b" }}
            >
              {data.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              formatter={(value: number) => formatNumber(value)}
              contentStyle={{
                backgroundColor: "#1e293b",
                border: "1px solid #475569",
                borderRadius: "8px",
                color: "#e2e8f0",
              }}
            />
            <Legend
              wrapperStyle={{ color: "#94a3b8", fontSize: "12px" }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
    );
  }

  return null;
}
