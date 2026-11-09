"use client";

/**
 * ChatMessage.tsx — Renderiza un mensaje individual del chat.
 *
 * Soporta:
 * - Mensajes de texto con formato Markdown.
 * - Visualizaciones inline (gráficos y tablas) debajo del texto.
 * - Estilos diferenciados para usuario vs. asistente.
 */

import ReactMarkdown from "react-markdown";
import ChartRenderer from "./ChartRenderer";
import DataTable from "./DataTable";

interface Visualization {
  type: "bar" | "pie" | "table" | "stat";
  title: string;
  data: Record<string, unknown>[];
  config: Record<string, string>;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  visualizations?: Visualization[];
  timestamp: Date;
}

export default function ChatMessage({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      {/* Avatar del asistente */}
      {!isUser && (
        <div className="flex-shrink-0 mr-3 mt-1">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-white text-sm font-bold shadow-lg shadow-cyan-500/20">
            🛡️
          </div>
        </div>
      )}

      <div
        className={`max-w-[85%] lg:max-w-[75%] ${
          isUser
            ? "bg-gradient-to-br from-cyan-600 to-cyan-700 text-white rounded-2xl rounded-br-md"
            : "bg-slate-800/80 border border-slate-700/50 text-slate-100 rounded-2xl rounded-bl-md"
        } px-4 py-3 shadow-lg`}
      >
        {/* Texto del mensaje con Markdown */}
        <div className={`markdown-body ${isUser ? "text-white" : ""}`}>
          <ReactMarkdown>{message.content}</ReactMarkdown>
        </div>

        {/* Visualizaciones (gráficos, tablas, stats) */}
        {message.visualizations?.map((viz, i) => (
          <div key={i} className="mt-3">
            {viz.type === "table" ? (
              <DataTable data={viz.data} title={viz.title} />
            ) : (
              <ChartRenderer visualization={viz} />
            )}
          </div>
        ))}

        {/* Timestamp */}
        <p
          className={`text-[10px] mt-2 ${
            isUser ? "text-cyan-200/60" : "text-slate-500"
          }`}
        >
          {message.timestamp.toLocaleTimeString("es-AR", {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </p>
      </div>

      {/* Avatar del usuario */}
      {isUser && (
        <div className="flex-shrink-0 ml-3 mt-1">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center text-white text-sm font-bold shadow-lg">
            👤
          </div>
        </div>
      )}
    </div>
  );
}
