/**
 * gemini.ts — Integración con la API de Google Gemini.
 *
 * Configura el modelo con function calling: Gemini recibe las funciones
 * disponibles como "tools" y decide cuáles invocar según la pregunta
 * del usuario. El resultado de cada función se envía de vuelta a Gemini
 * para que formule una respuesta natural en español.
 */

import {
  GoogleGenerativeAI,
  SchemaType,
  type FunctionDeclaration,
  type Content,
  type Part,
} from "@google/generative-ai";
import * as queries from "./queries";

/* ------------------------------------------------------------------ */
/*  Cliente Gemini y System Instruction                                */
/* ------------------------------------------------------------------ */

const SYSTEM_INSTRUCTION = `Sos un asistente de ciberseguridad especializado en análisis de detección de anomalías en tráfico de red. Trabajás sobre la base de datos del Anomaly Pipeline, que procesó el dataset CICIDS2017 con un sistema de detección de dos capas: reglas de firma TCP + Isolation Forest (ML no supervisado).

Base de datos PostgreSQL — Esquema:
• Tabla "alerts" (606,769 registros): id, detected_at, source_file, destination_port, flow_duration, total_fwd_packets, total_bwd_packets, flow_bytes_per_s, flow_packets_per_s, detector, anomaly_score, label_original.
• Tabla "pipeline_runs": id, run_at, source_file, total_flows_processed, total_anomalies_detected, processing_time_seconds, status.

Valores del campo "detector":
- "ensemble": detectado por AMBOS métodos (regla de firma + Isolation Forest).
- "isolation_forest": detectado solo por el modelo ML.
- "signature_rule": detectado solo por la regla de firma TCP.

Tipos de ataque en "label_original": PortScan, DDoS, DoS Hulk, DoS GoldenEye, DoS slowloris, DoS Slowhttptest, FTP-Patator, SSH-Patator, Web Attack - Brute Force, Web Attack - XSS, Web Attack - Sql Injection, Infiltration, Heartbleed, Bot.

Reglas:
1. Respondé SIEMPRE en español.
2. Cuando el usuario pregunte algo que necesite datos, usá las funciones disponibles. NUNCA inventes datos.
3. Sé conciso pero informativo. Usá números formateados (ej: 606,769 en vez de 606769).
4. Si los datos muestran algo interesante o preocupante, mencionalo proactivamente.
5. Podés usar la función run_custom_query para consultas que no cubran las otras funciones, siempre con SELECT.
6. Si el usuario pide un "dashboard" o "resumen general", usá varias funciones para dar una visión completa.`;

/* ------------------------------------------------------------------ */
/*  Declaración de funciones (tools para Gemini)                       */
/* ------------------------------------------------------------------ */

const functionDeclarations: FunctionDeclaration[] = [
  {
    name: "get_attack_type_distribution",
    description:
      "Obtiene la distribución de tipos de ataque detectados (label_original), excluyendo tráfico BENIGN. Devuelve cada tipo con su conteo, ordenado de mayor a menor.",
    parameters: {
      type: SchemaType.OBJECT,
      properties: {},
    },
  },
  {
    name: "get_total_alerts",
    description:
      "Obtiene la cantidad total de alertas de seguridad registradas en la base de datos.",
    parameters: {
      type: SchemaType.OBJECT,
      properties: {},
    },
  },
  {
    name: "get_anomaly_rate",
    description:
      "Calcula la tasa global de anomalías: total de flujos procesados, total de anomalías detectadas y el porcentaje.",
    parameters: {
      type: SchemaType.OBJECT,
      properties: {},
    },
  },
  {
    name: "get_alerts_by_detector",
    description:
      "Obtiene la cantidad de alertas agrupadas por tipo de detector (ensemble, isolation_forest, signature_rule).",
    parameters: {
      type: SchemaType.OBJECT,
      properties: {},
    },
  },
  {
    name: "get_top_attacked_ports",
    description:
      "Obtiene los puertos de destino más atacados, ordenados por cantidad de alertas.",
    parameters: {
      type: SchemaType.OBJECT,
      properties: {
        limit: {
          type: SchemaType.NUMBER,
          description:
            "Cantidad máxima de puertos a devolver (default: 10).",
        },
      },
    },
  },
  {
    name: "get_recent_alerts",
    description:
      "Obtiene las alertas más recientes con todos sus atributos de red (puerto, duración, detector, score, etiqueta).",
    parameters: {
      type: SchemaType.OBJECT,
      properties: {
        limit: {
          type: SchemaType.NUMBER,
          description:
            "Cantidad de alertas recientes a devolver (default: 10).",
        },
      },
    },
  },
  {
    name: "get_pipeline_runs",
    description:
      "Obtiene el historial de ejecuciones del pipeline con flujos procesados, anomalías detectadas, tiempo y estado.",
    parameters: {
      type: SchemaType.OBJECT,
      properties: {},
    },
  },
  {
    name: "run_custom_query",
    description:
      "Ejecuta una consulta SQL SELECT personalizada sobre la base de datos. Útil para análisis que no cubren las otras funciones. Solo permite SELECT (lectura), máximo 100 filas. Las tablas disponibles son: alerts (id, detected_at, source_file, destination_port, flow_duration, total_fwd_packets, total_bwd_packets, flow_bytes_per_s, flow_packets_per_s, detector, anomaly_score, label_original) y pipeline_runs (id, run_at, source_file, total_flows_processed, total_anomalies_detected, processing_time_seconds, status).",
    parameters: {
      type: SchemaType.OBJECT,
      properties: {
        sql: {
          type: SchemaType.STRING,
          description: "Consulta SQL SELECT a ejecutar.",
        },
      },
      required: ["sql"],
    },
  },
];

/* ------------------------------------------------------------------ */
/*  Mapa de implementaciones                                           */
/* ------------------------------------------------------------------ */

type FnArgs = Record<string, unknown>;

const functionImplementations: Record<
  string,
  (args: FnArgs) => Promise<unknown>
> = {
  get_attack_type_distribution: () => queries.getAttackTypeDistribution(),
  get_total_alerts: () => queries.getTotalAlerts(),
  get_anomaly_rate: () => queries.getAnomalyRate(),
  get_alerts_by_detector: () => queries.getAlertsByDetector(),
  get_top_attacked_ports: (args) =>
    queries.getTopAttackedPorts(Number(args.limit) || 10),
  get_recent_alerts: (args) =>
    queries.getRecentAlerts(Number(args.limit) || 10),
  get_pipeline_runs: () => queries.getPipelineRuns(),
  run_custom_query: (args) => queries.runCustomQuery(String(args.sql)),
};

/* ------------------------------------------------------------------ */
/*  Mapa de visualizaciones                                            */
/* ------------------------------------------------------------------ */

export interface Visualization {
  type: "bar" | "pie" | "table" | "stat";
  title: string;
  data: Record<string, unknown>[];
  config: Record<string, string>;
}

const visualizationMap: Record<
  string,
  { type: Visualization["type"]; title: string; [k: string]: string }
> = {
  get_attack_type_distribution: {
    type: "bar",
    title: "Distribución de Tipos de Ataque",
    xKey: "attack_type",
    yKey: "count",
  },
  get_alerts_by_detector: {
    type: "pie",
    title: "Alertas por Detector",
    nameKey: "detector",
    valueKey: "count",
  },
  get_top_attacked_ports: {
    type: "bar",
    title: "Top Puertos Atacados",
    xKey: "port",
    yKey: "count",
  },
  get_recent_alerts: {
    type: "table",
    title: "Alertas Recientes",
  },
  get_pipeline_runs: {
    type: "table",
    title: "Ejecuciones del Pipeline",
  },
  get_total_alerts: {
    type: "stat",
    title: "Total de Alertas",
  },
  get_anomaly_rate: {
    type: "stat",
    title: "Tasa de Anomalías",
  },
  run_custom_query: {
    type: "table",
    title: "Resultado de Consulta",
  },
};

/* ------------------------------------------------------------------ */
/*  Procesamiento del chat                                             */
/* ------------------------------------------------------------------ */

export interface ChatResult {
  message: string;
  visualizations: Visualization[];
}

/**
 * Procesa un mensaje del usuario a través de Gemini con function calling.
 *
 * Flujo:
 * 1. Envía el mensaje a Gemini con el historial de conversación.
 * 2. Si Gemini responde con una function call, ejecuta la función contra PostgreSQL.
 * 3. Envía el resultado de vuelta a Gemini para que formule la respuesta final.
 * 4. Retorna el texto + datos de visualización para el frontend.
 */
export async function processChat(
  userMessage: string,
  history: Content[],
  customApiKey?: string,
): Promise<ChatResult> {
  const apiKey = customApiKey?.trim() || process.env.GEMINI_API_KEY;
  if (!apiKey) {
    throw new Error(
      "No se encontró GEMINI_API_KEY. Podés ingresarla en la configuración (⚙️) o configurarla en las variables de entorno de Vercel.",
    );
  }

  const genAI = new GoogleGenerativeAI(apiKey);
  const primaryModelName = process.env.GEMINI_MODEL || "gemini-3-flash-preview";

  let model = genAI.getGenerativeModel({
    model: primaryModelName,
    systemInstruction: SYSTEM_INSTRUCTION,
    tools: [{ functionDeclarations }],
  });

  let chat = model.startChat({ history });
  let result;
  try {
    result = await chat.sendMessage(userMessage);
  } catch (error: unknown) {
    const fallbackModelName =
      primaryModelName === "gemini-3-flash-preview"
        ? "gemini-3.1-flash-lite"
        : "gemini-3-flash-preview";
    console.warn(
      `[Gemini] Falló el modelo '${primaryModelName}'. Intentando con fallback '${fallbackModelName}'...`,
      error instanceof Error ? error.message : error,
    );
    model = genAI.getGenerativeModel({
      model: fallbackModelName,
      systemInstruction: SYSTEM_INSTRUCTION,
      tools: [{ functionDeclarations }],
    });
    chat = model.startChat({ history });
    result = await chat.sendMessage(userMessage);
  }

  let response = result.response;

  const visualizations: Visualization[] = [];

  // Loop de function calling: máximo 3 llamadas encadenadas para evitar timeouts
  let iterations = 0;
  const MAX_ITERATIONS = 3;

  while (response.functionCalls()?.length && iterations < MAX_ITERATIONS) {
    iterations++;
    const functionCalls = response.functionCalls()!;
    const functionResponses: Part[] = [];

    for (const fc of functionCalls) {
      try {
        const impl = functionImplementations[fc.name];
        if (!impl) {
          throw new Error(`Función desconocida: ${fc.name}`);
        }

        const data = await impl(fc.args as FnArgs);

        // Asociar visualización según la función invocada
        const vizConfig = visualizationMap[fc.name];
        if (vizConfig && data != null) {
          const dataArray = Array.isArray(data) ? data : [data];
          if (dataArray.length > 0) {
            visualizations.push({
              type: vizConfig.type,
              title: vizConfig.title,
              data: dataArray as Record<string, unknown>[],
              config: vizConfig,
            });
          }
        }

        functionResponses.push({
          functionResponse: {
            name: fc.name,
            response: { result: data },
          },
        } as Part);
      } catch (error: unknown) {
        const errMsg =
          error instanceof Error ? error.message : "Error desconocido";
        functionResponses.push({
          functionResponse: {
            name: fc.name,
            response: { error: errMsg },
          },
        } as Part);
      }
    }

    result = await chat.sendMessage(functionResponses);
    response = result.response;
  }

  return {
    message: response.text(),
    visualizations,
  };
}
