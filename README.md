# PluriLang Barranquilla AI Assistant

This project implements an intelligent virtual assistant for **PluriLang Barranquilla Ltda.**, a language academy located in Barranquilla, Atlántico, Colombia.

The assistant uses a **Retrieval-Augmented Generation (RAG)** architecture to answer frequently asked questions using information retrieved exclusively from the academy's official business documents.

The assistant is designed to provide information about:

* Language programs
* Available languages and proficiency levels
* Prices and discounts
* Study modalities
* Schedules
* Enrollment
* Certificates and international exam preparation

When a question cannot be answered reliably using the available documentation, the assistant avoids generating unsupported information and initiates a simulated escalation to a human advisor.

## Architecture

The current implementation follows this architecture:

```text
User
  │
  ▼
Telegram Bot
  │
  ▼
FastAPI Webhook
  │
  ▼
RAG Pipeline
  │
  ├── ChromaDB
  │     └── Relevant document chunks
  │
  └── OpenAI
        └── GPT-4o-mini
  │
  ▼
Response
  │
  ▼
Telegram Bot
```

### Technology Stack

* **Backend:** FastAPI
* **Language:** Python
* **AI framework:** LangChain
* **LLM:** OpenAI `gpt-4o-mini`
* **Embeddings:** OpenAI `text-embedding-3-small`
* **Vector database:** ChromaDB
* **Document processing:** PyPDF + Recursive Character Text Splitter
* **Messaging platform:** Telegram Bot API
* **HTTP client:** HTTPX
* **Local tunneling for development:** ngrok

## RAG Pipeline

The assistant follows a Retrieval-Augmented Generation workflow.

### 1. Document ingestion

The PDF documents located in the `data/` directory are loaded using `PyPDFDirectoryLoader`.

The documents are then divided into smaller chunks using:

```python
RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50
)
```

The overlap helps preserve context between adjacent chunks.

### 2. Embeddings

Each document chunk is converted into a vector embedding using:

```text
text-embedding-3-small
```

### 3. Vector database

The generated embeddings and their associated document chunks are stored locally in ChromaDB.

The database is created in:

```text
./chroma_db
```

Running the ingestion script again removes the previous database and rebuilds it from the current documents.

### 4. Retrieval

When a user asks a question, the system retrieves the three most relevant document chunks from ChromaDB.

```python
search_kwargs={"k": 3}
```

### 5. Generation

The retrieved context is passed to `gpt-4o-mini` together with a strict system prompt.

The assistant is instructed to:

* Answer only using the retrieved context.
* Avoid inventing information.
* Maintain a friendly and professional tone.
* Escalate questions that cannot be answered from the official documentation.

## Human Escalation

If the RAG assistant determines that a question cannot be answered from the available documents, it returns an internal escalation signal.

The Telegram interface then presents a two-step escalation flow:

1. Explain that the requested information is not available in the official documentation.
2. Simulate the transfer to a human advisor.
3. Inform the user that no advisor is currently available and that a member of the team will contact them through the same channel.
4. Return the user to the main menu.

The same escalation flow can also be triggered directly through the **"Talk to an advisor"** Telegram button.

## Telegram Interface

The Telegram bot provides an interactive interface.

When a user sends:

```text
/start
```

the assistant sends a welcome message and displays the main menu.

Available menu categories include:

* 💰 Prices and discounts
* 📚 Languages and levels
* 🕐 Schedules and modalities
* 📝 Enrollment
* 🎓 Certifications
* 👨‍💼 Talk to an advisor

Users can also bypass the menu and ask questions directly.

The following commands can be used to display the menu:

```text
opciones
opcion
menu
menú
ayuda
```

## Project Structure

```text
plurilang-barranquilla-assistant/
│
├── agent.py
├── ingest.py
├── main.py
├── requirements.txt
├── README.md
├── .env.example
│
├── data/
│   ├── Oferta_Academica.pdf
│   ├── Modalidades_y_Horarios.pdf
│   └── Precios_y_Descuentos.pdf
│
└── chroma_db/
    └── Generated vector database files
```

## Environment Variables

API credentials are stored in environment variables and are never hardcoded into the application.

Create a `.env` file in the project root:

```env
OPENAI_API_KEY="your_openai_api_key_here"
TELEGRAM_BOT_TOKEN="your_telegram_bot_token_here"
```

Never commit the `.env` file to the repository.

The required variables are documented in `.env.example`.

## Local Setup

### 1. Clone the repository

Clone the project repository and enter the project directory.

### 2. Create the virtual environment

```bash
python3 -m venv .venv
```

Activate it:

**Linux/macOS**

```bash
source .venv/bin/activate
```

**Windows**

```powershell
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file using `.env.example` as a template and add the required OpenAI and Telegram credentials.

### 5. Build the vector database

Run:

```bash
python ingest.py
```

The script will:

1. Load the PDFs from `data/`.
2. Split the documents into overlapping chunks.
3. Generate embeddings.
4. Create the local ChromaDB database.

A successful ingestion should report the number of pages and chunks processed.

### 6. Test the RAG agent locally

The RAG pipeline can be tested directly from the terminal:

```bash
python agent.py
```

The assistant will start an interactive terminal session.

Type:

```text
salir
```

to exit.

### 7. Start the FastAPI server

Run:

```bash
uvicorn main:app --reload
```

The local server will be available at:

```text
http://127.0.0.1:8000
```

The root endpoint can be used to verify that the server is running.

## Telegram Webhook - Local Testing

Telegram requires a publicly accessible HTTPS endpoint to send webhook updates.

For local development, ngrok can be used to expose the FastAPI server.

Start the FastAPI server:

```bash
uvicorn main:app --reload
```

Then, in another terminal:

```bash
ngrok http 8000
```

ngrok will provide a public HTTPS URL similar to:

```text
https://example-name.ngrok-free.app
```

Register the Telegram webhook using:

```text
https://api.telegram.org/bot<YOUR_TELEGRAM_TOKEN>/setWebhook?url=<YOUR_NGROK_HTTPS_URL>/webhook
```

Replace:

```text
<YOUR_TELEGRAM_TOKEN>
```

with the Telegram bot token and:

```text
<YOUR_NGROK_HTTPS_URL>
```

with the HTTPS forwarding URL generated by ngrok.

Once registered, Telegram will send incoming bot messages to:

```text
POST /webhook
```

## Testing Checklist

The following scenarios should be tested before deployment:

### Basic interaction

* Send `/start`.
* Confirm that the welcome message appears.
* Confirm that the main menu is displayed.
* Send a direct question without using the menu.

### RAG questions

Test questions related to:

* Available languages
* Language levels
* Program prices
* Discounts
* Study modalities
* Schedules
* Enrollment
* Certifications

### Out-of-scope questions

Ask questions that are not covered by the official documents.

The assistant should not invent an answer and should trigger the human escalation flow.

### Menu

Test every available menu button and confirm that each option retrieves information through the same RAG pipeline.

### Human escalation

Press:

```text
👨‍💼 Hablar con un asesor
```

The assistant should:

1. Display the transfer message.
2. Simulate the transfer.
3. Explain that no advisor is currently available.
4. Return to the main menu.

## Current Limitations

The current version intentionally focuses on the core RAG assistant and Telegram integration.

Human escalation is currently simulated. The system does not yet maintain a queue or connect the user to a real-time human Telegram account.

The local ChromaDB database is generated from the business documents during ingestion.

A future production deployment can rebuild the vector database during the deployment process.

## Potential Improvements

Possible future extensions include:

* n8n integration for workflow automation.
* Email notifications when human escalation is triggered.
* Persistent conversation history.
* Usage and cost metrics.
* Frequently asked question caching.
* Production deployment using Render.
* Real human-agent routing.
* Migration from deprecated LangChain integrations to their current standalone packages.

## Security Notes

* API keys must be stored in environment variables.
* Never commit `.env` to version control.
* Never expose the Telegram bot token publicly.
* If a Telegram bot token is accidentally exposed, revoke it through Telegram's BotFather and generate a new token.

## License

This project was developed as a technical assessment and prototype for PluriLang Barranquilla Ltda.

```
```
