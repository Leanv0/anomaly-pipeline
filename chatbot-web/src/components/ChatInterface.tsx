"use client";

/**
 * ChatInterface.tsx — Componente principal del chat con soporte para visualizaciones,
 * métricas en tiempo real, configuración de API Key y monitoreo del estado de PostgreSQL.
 */

import { useState, useRef, useEffect, useCallback } from "react";
import ChatMessage, { type Message } from "./ChatMessage";

/** Sugerencias rápidas para el usuario. */
const QUICK_SUGGESTIONS = [
  "¿Cuántas alertas hay en total?",
  "Mostrame los tipos de ataques",
  "¿Cuál es la tasa de anomalías?",
  "Top 10 puertos atacados",
  "Alertas por detector",
  "Últimas alertas registradas",
  "Resumen de ejecuciones del pipeline",
];

interface HealthData {
  status: string;
  postgresConnected: boolean;
  geminiConfigured: boolean;
  alertsCount?: number;
  runsCount?: number;
  error?: string;
}

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "¡Hola! 👋 Soy tu asistente de ciberseguridad para el **Anomaly Pipeline**.\n\nPuedo consultar directamente la base de datos de alertas en PostgreSQL y generar dashboards interactivos. Preguntame por ejemplo:\n- *\"¿Cuántos tipos de ataques se detectaron?\"*\n- *\"Mostrame un dashboard de puertos atacados\"*\n- *\"¿Cuál es la tasa de anomalías del modelo?\"*",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [showConfig, setShowConfig] = useState(false);
  const [health, setHealth] = useState<HealthData | null>(null);
  const [isCheckingHealth, setIsCheckingHealth] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  /** Comprobar estado del backend y base de datos */
  const checkHealth = useCallback(async () => {
    setIsCheckingHealth(true);
    try {
      const res = await fetch("/api/health");
      const contentType = res.headers.get("content-type");
      if (contentType && contentType.includes("application/json")) {
        const data = await res.json();
        setHealth(data);
      } else {
        const text = await res.text();
        setHealth({
          status: "offline",
          postgresConnected: false,
          geminiConfigured: false,
          error: text || `Error HTTP ${res.status}`,
        });
      }
    } catch {
      setHealth({
        status: "offline",
        postgresConnected: false,
        geminiConfigured: false,
        error: "No se pudo conectar con el servidor",
      });
    } finally {
      setIsCheckingHealth(false);
    }
  }, []);

  /** Cargar API Key guardada de localStorage al montar */
  useEffect(() => {
    const saved = localStorage.getItem("gemini_api_key");
    if (saved) setApiKey(saved);
    checkHealth();
  }, [checkHealth]);

  /** Guardar API Key en localStorage */
  const handleSaveApiKey = (key: string) => {
    setApiKey(key);
    if (key.trim()) {
      localStorage.setItem("gemini_api_key", key.trim());
    } else {
      localStorage.removeItem("gemini_api_key");
    }
  };

  /** Auto-scroll al último mensaje */
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(scrollToBottom, [messages, scrollToBottom]);

  /** Auto-resize del textarea según contenido */
  const adjustTextareaHeight = () => {
    const textarea = inputRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 150)}px`;
    }
  };

  /** Envía un mensaje a la API del chatbot */
  const sendMessage = async (text?: string) => {
    const messageText = (text || input).trim();
    if (!messageText || isLoading) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: "user",
      content: messageText,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");

    if (inputRef.current) {
      inputRef.current.style.height = "auto";
    }

    setIsLoading(true);

    try {
      const history = messages
        .filter((m) => m.id !== "welcome" && !m.id.startsWith("error-"))
        .map((m) => ({
          role: m.role === "assistant" ? "model" : "user",
          parts: [{ text: m.content }],
        }));

      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: messageText,
          history,
          apiKey: apiKey.trim() || undefined,
        }),
      });

      const contentType = response.headers.get("content-type");
      let data: any = null;

      if (contentType && contentType.includes("application/json")) {
        data = await response.json();
      } else {
        const text = await response.text();
        throw new Error(
          text || `El servidor respondió con código ${response.status} (${response.statusText})`
        );
      }

      if (!response.ok) {
        throw new Error(data?.error || data?.details || "Error en la consulta");
      }

      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: data.message,
        visualizations: data.visualizations,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error: unknown) {
      const errMsg =
        error instanceof Error ? error.message : "Error desconocido";
      const errorMessage: Message = {
        id: `error-${Date.now()}`,
        role: "assistant",
        content: `❌ **Error:** ${errMsg}\n\n💡 *Consejo:* Revisá la configuración con el botón ⚙️ en la esquina superior para verificar la conexión a PostgreSQL o ingresar tu clave de Gemini.`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  /** Enter para enviar, Shift+Enter para nueva línea */
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  /** Limpiar historial del chat */
  const clearChat = () => {
    setMessages([
      {
        id: "welcome-new",
        role: "assistant",
        content:
          "Chat reiniciado. 🔄 ¿Qué información sobre los resultados del pipeline te gustaría consultar?",
        timestamp: new Date(),
      },
    ]);
  };

  return (
    <div className="flex flex-col h-screen bg-soc-dark text-slate-100">
      {/* ─── Header ─── */}
      <header className="flex-shrink-0 bg-soc-panel border-b border-soc-border px-4 py-3 shadow-md">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20 text-white font-bold">
              <span className="text-xl">🛡️</span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base sm:text-lg font-bold text-slate-100">
                  Anomaly Pipeline SOC
                </h1>
                {health?.postgresConnected ? (
                  <span className="inline-flex items-center gap-1 text-[11px] font-medium bg-emerald-950/80 text-emerald-400 border border-emerald-700/50 px-2 py-0.5 rounded-full">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    DB Conectada ({health.alertsCount?.toLocaleString("es-AR")} alertas)
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-[11px] font-medium bg-amber-950/80 text-amber-400 border border-amber-700/50 px-2 py-0.5 rounded-full">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                    DB No Conectada
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400">
                CICIDS2017 · Gemini Flash AI · PostgreSQL Analytics
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowConfig(true)}
              className="text-xs text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 border border-slate-700 px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5"
              title="Configuración de API y Conexión"
            >
              <span>⚙️</span>
              <span className="hidden sm:inline">Configuración</span>
            </button>
            <button
              onClick={clearChat}
              className="text-xs text-slate-400 hover:text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 px-3 py-1.5 rounded-lg transition-colors"
              title="Limpiar historial"
            >
              🗑️ <span className="hidden sm:inline">Limpiar</span>
            </button>
          </div>
        </div>
      </header>

      {/* ─── Mensajes ─── */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-5xl mx-auto">
          {messages.map((msg) => (
            <ChatMessage key={msg.id} message={msg} />
          ))}

          {/* Indicador de carga */}
          {isLoading && (
            <div className="flex justify-start mb-4">
              <div className="flex-shrink-0 mr-3 mt-1">
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center animate-pulse shadow-lg shadow-cyan-500/20">
                  🛡️
                </div>
              </div>
              <div className="bg-slate-800/80 border border-slate-700/50 rounded-2xl rounded-bl-md px-5 py-4">
                <div className="loading-dots">
                  <span />
                  <span />
                  <span />
                </div>
                <p className="text-xs text-cyan-300/80 mt-2">
                  Gemini está analizando la consulta y ejecutando SQL en PostgreSQL...
                </p>
              </div>
            </div>
          )}

          {/* Sugerencias rápidas */}
          {messages.length <= 1 && !isLoading && (
            <div className="mt-8 p-6 bg-slate-900/60 border border-slate-800 rounded-2xl">
              <p className="text-xs uppercase tracking-wider text-slate-400 mb-3 text-center font-semibold">
                Consultas sugeridas para empezar
              </p>
              <div className="flex flex-wrap gap-2 justify-center">
                {QUICK_SUGGESTIONS.map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => sendMessage(suggestion)}
                    className="text-xs bg-slate-800/90 hover:bg-cyan-950/60 border border-slate-700 hover:border-cyan-500/50 text-slate-300 hover:text-cyan-300 px-3.5 py-2 rounded-xl transition-all shadow-sm"
                  >
                    💬 {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* ─── Input ─── */}
      <div className="flex-shrink-0 bg-soc-panel border-t border-soc-border px-4 py-3">
        <div className="max-w-5xl mx-auto flex gap-3 items-end">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => {
              setInput(e.target.value);
              adjustTextareaHeight();
            }}
            onKeyDown={handleKeyDown}
            placeholder="Preguntá sobre tipos de ataques, total de alertas, puertos, anomalías..."
            rows={1}
            disabled={isLoading}
            className="flex-1 bg-slate-800 border border-slate-700 focus:border-cyan-500 text-slate-100 placeholder-slate-500 rounded-xl px-4 py-3 resize-none input-glow outline-none transition-colors disabled:opacity-50 text-sm"
          />
          <button
            onClick={() => sendMessage()}
            disabled={!input.trim() || isLoading}
            className="flex-shrink-0 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 disabled:from-slate-700 disabled:to-slate-700 text-white font-medium px-5 py-3 rounded-xl transition-all disabled:cursor-not-allowed shadow-lg shadow-cyan-500/20 disabled:shadow-none flex items-center justify-center"
            title="Enviar mensaje"
          >
            {isLoading ? (
              <svg
                className="animate-spin h-5 w-5"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
            ) : (
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="currentColor"
                className="w-5 h-5"
              >
                <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
              </svg>
            )}
          </button>
        </div>
        <div className="max-w-5xl mx-auto flex items-center justify-between text-[11px] text-slate-500 mt-1.5 px-1">
          <span>Enter para enviar · Shift+Enter para salto de línea</span>
          <span>Desplegado en Vercel · Gemini Function Calling</span>
        </div>
      </div>

      {/* ─── Modal de Configuración ─── */}
      {showConfig && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-lg w-full p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-4 border-b border-slate-800 pb-3">
              <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                <span>⚙️</span> Configuración del Sistema
              </h2>
              <button
                onClick={() => setShowConfig(false)}
                className="text-slate-400 hover:text-white text-lg p-1"
              >
                ✕
              </button>
            </div>

            {/* Estado de PostgreSQL */}
            <div className="mb-5 bg-slate-800/60 p-4 rounded-xl border border-slate-700/60">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs uppercase tracking-wider text-slate-400 font-semibold">
                  Estado de PostgreSQL
                </span>
                <button
                  onClick={checkHealth}
                  disabled={isCheckingHealth}
                  className="text-xs text-cyan-400 hover:text-cyan-300 disabled:opacity-50"
                >
                  {isCheckingHealth ? "Verificando..." : "🔄 Probar conexión"}
                </button>
              </div>

              {health?.postgresConnected ? (
                <div className="space-y-1">
                  <div className="flex items-center gap-2 text-emerald-400 text-sm font-medium">
                    <span className="w-2 h-2 rounded-full bg-emerald-400" />
                    Conectado a la base de datos
                  </div>
                  <p className="text-xs text-slate-400">
                    Total de alertas registradas:{" "}
                    <strong className="text-slate-200">
                      {health.alertsCount?.toLocaleString("es-AR")}
                    </strong>
                  </p>
                  <p className="text-xs text-slate-400">
                    Corridas del pipeline:{" "}
                    <strong className="text-slate-200">
                      {health.runsCount?.toLocaleString("es-AR")}
                    </strong>
                  </p>
                </div>
              ) : (
                <div className="space-y-1">
                  <div className="flex items-center gap-2 text-rose-400 text-sm font-medium">
                    <span className="w-2 h-2 rounded-full bg-rose-400" />
                    Sin conexión a PostgreSQL
                  </div>
                  <p className="text-xs text-rose-300/80">
                    {health?.error ||
                      "Verificá que POSTGRES_URL esté configurada en las variables de entorno de Vercel o en .env.local."}
                  </p>
                </div>
              )}
            </div>

            {/* Configuración de Gemini API Key */}
            <div className="mb-5">
              <label className="block text-xs uppercase tracking-wider text-slate-400 font-semibold mb-2">
                Gemini API Key
              </label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => handleSaveApiKey(e.target.value)}
                placeholder="AIzaSy..."
                className="w-full bg-slate-800 border border-slate-700 focus:border-cyan-500 text-slate-100 rounded-xl px-4 py-2.5 text-sm outline-none font-mono"
              />
              <p className="text-[11px] text-slate-400 mt-2 leading-relaxed">
                Si no la ingresás acá, se usará la variable{" "}
                <code className="text-cyan-400">GEMINI_API_KEY</code> configurada en
                el servidor o en Vercel. Podés obtener una clave gratuita en{" "}
                <a
                  href="https://aistudio.google.com/apikey"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-cyan-400 underline"
                >
                  Google AI Studio
                </a>
                .
              </p>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
              <button
                onClick={() => setShowConfig(false)}
                className="bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold px-4 py-2 rounded-xl transition-colors"
              >
                Listo
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
