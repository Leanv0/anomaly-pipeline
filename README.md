# Anomaly Pipeline — End-to-End Data, ML & Cloud Analytics Pipeline

[![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Next.js](https://img.shields.io/badge/Next.js-14_App_Router-000000?logo=next.js&logoColor=white)](https://nextjs.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16_&_Neon-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Scikit-Learn](https://img.shields.io/badge/scikit--learn-Isolation_Forest-F7931E?logo=scikitlearn&logoColor=white)](https://scikit-learn.org/)
[![Google Gemini](https://img.shields.io/badge/Google_Gemini-Function_Calling-8E75C2?logo=google&logoColor=white)](https://aistudio.google.com/)
[![Vercel](https://img.shields.io/badge/Vercel-Serverless_Deploy-000000?logo=vercel&logoColor=white)](https://vercel.com/)

Pipeline de ingeniería de datos, machine learning y observabilidad de punta a punta. Procesa, transforma y analiza flujos masivos de red (dataset CICIDS2017) mediante almacenamiento columnar S3/Parquet, un motor de detección de anomalías en dos capas (reglas de firma TCP + Isolation Forest no supervisado), persistencia optimizada en PostgreSQL y dos interfaces de consulta: un **SOC Dashboard en Grafana** y un **Chatbot Analítico con IA (Google Gemini)** desplegable en **Vercel**.

---

## 🏗️ Arquitectura del Sistema

```
[ CICIDS2017 Raw Traffic ] (~3.1M flows, 8 CSVs)
             │
             ▼
   [ Ingestion & Datalake ] ── RustFS / Object Storage S3-compatible (Bucket 'raw')
             │
             ▼
      [ Streaming ETL ] ────── Clean names, null/inf imputation, drop identifiers
             │                 PyArrow + Snappy compression (~71% storage reduction)
             ▼
     [ Datalake Processed ] ── 8 Parquet files (Bucket 'processed')
             │
             ▼
 [ Detection & ML Engine ] ─── Layer 1: TCP Signature Rule (PortScan)
             │                 Layer 2: Isolation Forest (Trained on pure Monday baseline)
             │                 Ensemble: Defense in Depth (99.47% Recall, 0.0008% FPR)
             ▼
   [ High-Speed Storage ] ──── Native PostgreSQL COPY protocol (606,768 alerts in ~1.8s)
             │
      ┌──────┴──────────────────────────────────────┐
      ▼                                             ▼
[ Grafana SOC Dashboard ]                 [ Cloud Web & AI Chatbot ]
• Provisioning as Code (Docker)           • Next.js 14 App Router + Tailwind CSS
• 9 Analytic & Forensic Panels            • Google Gemini (Function Calling)
• Port, detector & attack distribution    • Dynamic dashboards & charts (Recharts)
                                          • Neon Serverless Postgres + Vercel
```

---

## 📊 Métricas Clave del Pipeline

* **Volumen Procesado**: 3.119.345 flujos crudos depurados a **2.830.743 flujos limpios** distribuidos en 8 datasets Parquet.
* **Eficiencia de Almacenamiento**: De ~1.150 MB (CSV) a **329 MB (Parquet columnar)**, logrando un **~71% de compresión** sin pérdida de información.
* **Calibración sin Data Leakage**: Entrenamiento de línea base puramente benigna (Lunes, 529.918 flujos, 0 ataques vistos) para validar detección en días posteriores.
* **Rendimiento del Ensamble**:
  * **Regla de Firma TCP**: Precisión quirúrgica del 99,99% y FPR de solo 0,0008% en escaneos de puertos.
  * **Isolation Forest**: Detección no supervisada generalizable sobre ataques volumétricos y anómalos.
  * **Ensamble (Regla OR ML)**: **99,47% Recall**, atrapando ataques que eluden firmas estáticas.
* **Carga Relacional Ultrarrápida**: Inserción en streaming mediante el protocolo nativo `COPY` de PostgreSQL (más de 160.000 registros por segundo).

---

## 💻 Interfaces de Observabilidad

### 1. Dashboard Ejecutivo en Grafana
* Configurado declarativamente como **Dashboard-as-Code** y **Datasource-as-Code**.
* 9 paneles interactivos: KPIs ejecutivos, Donut de defensa en profundidad por detector, Top 10 puertos atacados, tipos de ataque confirmados (DoS Hulk, PortScan, DDoS, Botnet, Infiltration, Web Attacks) y tabla forense en tiempo real.

### 2. Chatbot Web con IA (Google Gemini + Neon + Vercel)
* Aplicación web en [`chatbot-web/`](chatbot-web/) construida con **Next.js 14** y **Tailwind CSS**.
* **Function Calling**: Gemini interpreta consultas en lenguaje natural y genera queries SQL automáticas contra PostgreSQL para responder datos exactos.
* **Dashboards Dinámicos Inline**: Si se pregunta por *"tipos de ataques"*, *"puertos"* o *"métricas"*, la interfaz renderiza gráficos de barras, gráficos circulares o tarjetas KPI interactivas con **Recharts**.

---

## 🔒 Arquitectura de Seguridad (Threat Modeling)

Para el despliegue cloud en **Vercel** y **Neon**, se implementó una estrategia de **Defensa en Profundidad**:

1. **Principio de Menor Privilegio (DB Level)**: El chatbot se conecta con el rol `chatbot_readonly`, que tiene **estrictamente permiso `SELECT`** sobre `alerts` y `pipeline_runs`. Cualquier intento de modificación (`INSERT`, `UPDATE`, `DELETE`, `DROP`) es rechazado directamente por el motor de PostgreSQL.
2. **Prevención de DoS**: Parámetro `statement_timeout = '5000ms'` a nivel de rol para cancelar automáticamente cualquier consulta que supere los 5 segundos.
3. **Rate Limiting**: Limitador de tasa por IP en la API de chat (máximo 20 peticiones por minuto por cliente) para evitar abuso de cuota y ataques de fuerza bruta.
4. **Prevención de Fuga de Información**: Manejo de errores sanitizado para que ningún detalle interno de infraestructura, tablas o credenciales sea expuesto al cliente.
5. **Arquitectura Serverless Scale-to-Zero**: Base de datos en Neon que se auto-suspende tras 5 minutos de inactividad, evitando servidores ocesos desatendidos.

---

## 🚀 Inicio Rápido (Local)

### Requisitos
* Docker y Docker Compose
* Python 3.12+ (recomendado en virtual environment)
* Node.js 18+ (para el frontend)

### 1. Clonar y configurar variables de entorno
```bash
git clone https://github.com/Leanv0/anomaly-pipeline.git
cd anomaly-pipeline

cp .env.example .env
# Completar credenciales seguras en .env
```

### 2. Levantar la infraestructura base
```bash
docker compose up -d
# Servicios activos: RustFS (puerto 9000/9001), PostgreSQL (5432), Grafana (3000)
```

### 3. Ejecutar el pipeline de datos
```bash
# Inicializar base de datos y buckets
python src/db_setup.py
python src/storage_setup.py

# Ejecutar pipeline completo de punta a punta (ETL + Detección)
python src/main.py
```

### 4. Tests Unitarios
```bash
pytest tests/
# 12 tests unitarios (transformación, firma TCP, Isolation Forest, métricas) pasando en verde (~2s)
```

### 5. Iniciar la aplicación web del Chatbot
```bash
cd chatbot-web
cp .env.local.example .env.local
# Configurar POSTGRES_URL y GEMINI_API_KEY

npm install
npm run dev
# Abrir http://localhost:3000
```

---

## ☁️ Despliegue en Vercel

Consultá la guía detallada paso a paso en [**`chatbot-web/DEPLOY_VERCEL.md`**](chatbot-web/DEPLOY_VERCEL.md).

---

## 🛠️ Tecnologías Utilizadas

* **Lenguaje & Datos**: Python 3.14, pandas, NumPy, PyArrow (Apache Parquet).
* **Machine Learning**: scikit-learn (Isolation Forest), SciPy.
* **Bases de Datos & Storage**: PostgreSQL 16, Neon Serverless Postgres, RustFS (S3 API), psycopg v3, pg.
* **Monitoreo & Visualización**: Grafana (Dashboard as Code), Recharts, Tailwind CSS.
* **Frontend & Serverless**: Next.js 14 (App Router), TypeScript, Vercel.
* **Inteligencia Artificial**: Google Generative AI SDK (Gemini Flash, Function Calling).
* **Testing & Calidad**: pytest, unittest.mock, flake8.
