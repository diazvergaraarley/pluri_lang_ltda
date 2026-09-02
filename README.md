# PluriLang Barranquilla AI Assistant

This project implements an intelligent virtual assistant for **PluriLang Barranquilla Ltda.**, a language academy located in Barranquilla, Atlántico, Colombia.

The assistant uses a **Retrieval-Augmented Generation (RAG)** architecture to answer frequently asked questions using information retrieved exclusively from the academy's official business documents.

It also features workflow automation via **n8n** for human escalation, persistent usage metrics with real-time cost tracking, a semantic-aware caching system to reduce API costs, and a smart landing page with deep-linking capabilities.

## Architecture

The current implementation follows this architecture:

```text
User
  │
  ├──► Web Landing Page (Smart User-Agent Deep Linking)
  │
  ▼
Telegram Bot
  │
  ▼
FastAPI Backend
  │
  ├──► In-Memory Cache (Intercepts repeated queries)
  │
  ├──► RAG Pipeline
  │     ├── ChromaDB (Vector Search)
  │     └── OpenAI (gpt-4o-mini & text-embedding-3-small)
  │
  ├──► Persistent Metrics (metrics.json)
  │
  └──► Escalation Trigger
        └── n8n Webhook -> Email Notification to Human Staff
```

### Technology Stack

* **Backend Framework:** FastAPI (Python)
* **AI & Orchestration:** LangChain, OpenAI (`gpt-4o-mini`, `text-embedding-3-small`)
* **Vector Database:** ChromaDB
* **Document Processing:** PyPDF + Recursive Character Text Splitter
* **Integration & Automation:** Telegram Bot API, n8n (Webhooks)
* **Security:** HTTP Basic Auth (`secrets` module)
* **Frontend:** HTML/CSS/JS (Served directly via FastAPI)
* **Cloud Hosting:** Render (Web Service)

## Core Features

### 1. RAG Pipeline & Caching

Documents in the `data/` directory are loaded, chunked, and embedded into a local ChromaDB instance. When a user asks a question:

1. The system first checks a **local cache** for identical previous queries. If found, it returns the answer instantly (0 tokens consumed).
2. If not cached, it retrieves the top 3 relevant document chunks from ChromaDB.
3. Context is passed to `gpt-4o-mini` with strict instructions to answer *only* based on the context and avoid hallucinations.

### 2. Human Escalation (n8n Integration)

If the RAG assistant determines that a question cannot be answered from the available documents, it triggers an internal `ESCALAR_HUMANO` signal.

1. The user receives a message explaining the limitation and simulating a transfer.
2. The FastAPI backend sends an asynchronous `POST` request to an **n8n Production Webhook**.
3. n8n processes the payload (`user_question`, `chat_id`, `timestamp`) and routes an email notification to the academy's staff.

### 3. Smart Landing Page

The root endpoint (`/`) serves a modern, responsive HTML landing page. It utilizes **User-Agent Sniffing** via JavaScript to seamlessly route users who click "Talk to Assistant":

* **Mobile Devices:** Triggers the deep link (`tg://resolve`) to open the native Telegram app.
* **Desktop Devices:** Routes to Telegram Web (`web.telegram.org`) to prevent dead links if the desktop app is not installed.

### 4. Admin Dashboard & Persistent Metrics

The system tracks query volume, escalation rates, and token usage, persisting this data in a local `metrics.json` file to survive server restarts.

A protected dashboard is available at `/admin`:

* Secured via **HTTP Basic Authentication**.
* Displays total queries, escalation rate, and calculates exact API costs in USD based on OpenAI's current pricing.

## Project Structure

```text
pluri_lang_ltda/
│
├── agent.py            # RAG logic, cache, and token extraction
├── ingest.py           # Document chunking and ChromaDB generation
├── main.py             # FastAPI server, Telegram/n8n webhooks, UI endpoints
├── metrics.json        # Persistent metrics storage (auto-generated)
├── requirements.txt
├── README.md
├── .env.example
│
├── data/
│   ├── Oferta_Academica.pdf
│   ├── Modalidades_y_Horarios.pdf
│   └── Precios_y_Descuentos.pdf
│
└── chroma_db/          # Vector database files (auto-generated)
```

## Environment Variables

API credentials are stored in environment variables. Create a `.env` file in the project root:

```env
OPENAI_API_KEY="your_openai_api_key_here"
TELEGRAM_BOT_TOKEN="your_telegram_bot_token_here"
N8N_WEBHOOK_URL="your_n8n_production_webhook_here"
ADMIN_USER="admin"
ADMIN_PASS="your_secure_password"
```

## Local Setup

### 1. Clone the Repository & Create Virtual Environment

```bash
git clone https://github.com/diazvergaraarley/pluri_lang_ltda.git
cd pluri_lang_ltda
git checkout localserver
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment & Ingest Data

Create your `.env` file, then build the vector database:

```bash
python ingest.py
```

### 3. Start the Application

Start the FastAPI server:

```bash
uvicorn main:app --reload
```

The server will be available at `http://127.0.0.1:8000`. You can visit the root URL to see the Landing Page, or `/admin` to view the protected dashboard.

## Cloud Deployment (Render)

This project is optimized for deployment on Render as a Web Service.

1. **Build Command:** `pip install -r requirements.txt && python ingest.py`
2. **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
3. **Environment Variables:** Add all variables from your `.env` to the Render dashboard.
4. **Webhook Registration:** Once deployed, register your public Render URL with Telegram:

```text
https://api.telegram.org/bot<YOUR_TELEGRAM_TOKEN>/setWebhook?url=https://<YOUR_RENDER_APP>.onrender.com/webhook
```

## Local Telegram Testing (ngrok)

For local development without Render, use ngrok to expose the FastAPI server:

1. Start the server: `uvicorn main:app --reload`
2. In another terminal: `ngrok http 8000`
3. Register the webhook:

```text
https://api.telegram.org/bot<YOUR_TELEGRAM_TOKEN>/setWebhook?url=<YOUR_NGROK_HTTPS_URL>/webhook
```

## Security Notes

* API keys and Admin credentials must be stored in environment variables.
* Never commit `.env` or `metrics.json` (if it contains sensitive historical data) to version control.
* The `/admin` route utilizes `secrets.compare_digest` to mitigate timing attacks during authentication.

## License

This project was developed as a technical assessment and prototype for PluriLang Barranquilla Ltda.
