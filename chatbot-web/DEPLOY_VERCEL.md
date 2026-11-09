# 🚀 Guía de Despliegue en Vercel — Chatbot Anomaly Pipeline

Esta aplicación web construida con **Next.js 14** y **Tailwind CSS** integra **Google Gemini (con Function Calling)** para consultar directamente los resultados de ciberseguridad en **PostgreSQL** y mostrar respuestas numéricas y **dashboards interactivos** (gráficos de barras, tortas, tablas forenses y métricas).

---

## 📋 Requisitos Previos

1. **Cuenta en Vercel** (gratuita): [vercel.com](https://vercel.com)
2. **API Key de Gemini** (gratuita): [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
3. **Base de Datos PostgreSQL accesible desde Internet**:
   - Vercel corre en la nube (serverless). Para que Vercel pueda consultar tu base de datos, ésta debe ser accesible desde la red.
   - **Opción recomendada (100% gratuita y en 2 minutos):** Crear una base en [Neon.tech](https://neon.tech) o [Supabase](https://supabase.com).

---

## 🛠️ Paso 1: Configurar la Base de Datos en la Nube (Neon / Supabase)

Si tus datos están actualmente en el contenedor Docker local (`localhost:5432`), podés replicar el esquema y las alertas a una base gratuita en la nube como **Neon** (servidor serverless diseñado específicamente para Vercel):

1. Creá una cuenta en [Neon.tech](https://neon.tech) y creá un proyecto nuevo (ej: `anomaly-db`).
2. Copiá la cadena de conexión (Connection String) que te da Neon, tiene este formato:
   ```env
   postgresql://usuario:password@ep-xyz.us-east-2.aws.neon.tech/anomaly-db?sslmode=require
   ```
3. Ejecutá el script de migración rápida incluido en este proyecto:
   ```bash
   # Desde la raíz del proyecto anomaly-pipeline:
   python scripts/migrate_to_cloud_db.py --dest "TU_URL_DE_NEON"
   ```
   *(Este script copia la estructura de `alerts` y `pipeline_runs` y transfiere los datos automáticamente).*

---

## 🌐 Paso 2: Desplegar en Vercel

### Opción A: Desde la Web de Vercel (Recomendado)

1. Subí tus cambios a tu repositorio de GitHub:
   ```bash
   git add .
   git commit -m "feat: add chatbot web app with gemini and vercel support"
   git push origin main
   ```
2. Entrá a tu panel de [Vercel](https://vercel.com/new).
3. Hacé clic en **"Add New..."** → **"Project"** e importá tu repositorio `anomaly-pipeline`.
4. En la configuración del proyecto:
   - **Framework Preset**: Next.js
   - **Root Directory**: Hacé clic en `Edit` y seleccioná `chatbot-web`.
5. En la sección **Environment Variables**, agregá las siguientes variables:
   - `GEMINI_API_KEY`: Tu clave de API de Google AI Studio.
   - `POSTGRES_URL`: La URL de tu base de datos PostgreSQL (ej: la de Neon o Supabase con `?sslmode=require`).
   - `POSTGRES_SSL`: `true` (para bases en la nube que requieren SSL).
   - *(Opcional)* `GEMINI_MODEL`: `gemini-3.1-flash-lite` (por defecto usa `gemini-3.1-flash-lite`, ultra rápido y con soporte completo de function calling).
6. Hacé clic en **"Deploy"**. En ~1 minuto tendrás tu URL pública (ej: `https://anomaly-pipeline-chatbot.vercel.app`).

---

### Opción B: Mediante Vercel CLI

Si preferís desplegar desde la terminal:
```bash
# Instalar Vercel CLI globalmente
npm i -g vercel

# Entrar al directorio de la web
cd chatbot-web

# Desplegar
vercel
```

---

## 💻 Probando Localmente

También podés correr la aplicación web en tu computadora conectada al PostgreSQL de Docker:

1. Creá un archivo `.env.local` en `chatbot-web/`:
   ```bash
   cd chatbot-web
   cp .env.local.example .env.local
   ```
2. Completá los valores:
   ```env
   GEMINI_API_KEY=tu_api_key_aqui
   POSTGRES_URL=postgresql://anomaly_user:TU_PASSWORD_LOCAL@localhost:5432/anomaly_db
   POSTGRES_SSL=false
   ```
3. Iniciá el servidor de desarrollo:
   ```bash
   npm run dev
   ```
4. Abrí tu navegador en [http://localhost:3000](http://localhost:3000).

---

## 🛡️ Características del Chatbot

- **Function Calling Inteligente**: Gemini decide autónomamente qué consultas SQL ejecutar según la pregunta.
- **Dashboards Dinámicos**:
  - Preguntas sobre *"tipos de ataques"* → Genera gráfico de barras con la distribución exacta.
  - Preguntas sobre *"detectores"* → Genera gráfico circular (Pie chart) comparando Ensemble vs Isolation Forest vs Firma.
  - Preguntas sobre *"puertos más atacados"* → Genera ranking visual de puertos.
  - Preguntas sobre *"tasa de anomalías"* o *"total"* → Genera tarjetas KPI con formato numérico.
  - Preguntas sobre *"últimas alertas"* → Genera tabla forense detallada.
- **Seguridad Read-Only**: La función `run_custom_query` está blindada contra SQL Injection y solo permite consultas `SELECT`.
- **Selector de API Key en el Cliente**: Podés configurar la clave en el botón `⚙️ Configuración` directamente en la web sin re-desplegar.
