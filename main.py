import os
import asyncio
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
import httpx

from agent import process_query

# Load environment variables
load_dotenv()

app = FastAPI(title="PluriLang Barranquilla Assistant")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")

# ---------------------------------------------------------
# Metrics
# ---------------------------------------------------------

total_queries = 0
escalated_queries = 0

total_input_tokens = 0
total_output_tokens = 0
total_tokens = 0

# ---------------------------------------------------------
# Telegram & n8n helpers
# ---------------------------------------------------------

async def notify_n8n(chat_id: int, user_question: str):
    """Send escalation payload to n8n webhook."""
    if not N8N_WEBHOOK_URL:
        print("⚠️ Advertencia: N8N_WEBHOOK_URL no está configurado en el .env")
        return

    payload = {
        "user_question": user_question,
        "chat_id": str(chat_id),
        "message": "Escalamiento requerido por el asistente virtual.",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

    print(f"🚀 Disparando webhook hacia n8n: {N8N_WEBHOOK_URL}")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(N8N_WEBHOOK_URL, json=payload, timeout=5.0)
            print(f"📡 Status n8n: {response.status_code}")
            print(f"📡 Respuesta n8n: {response.text}")
        except Exception as e:
            print(f"❌ Error de conexión: {e}")

async def send_message(chat_id: int, text: str, reply_markup=None):
    """Send a message to a Telegram chat."""
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            json=payload
        )
        response.raise_for_status()

async def send_start_message(chat_id: int):
    """Send the welcome message and main menu."""
    welcome_message = (
        "👋 ¡Hola! Bienvenido a PluriLang Barranquilla Ltda.\n\n"
        "Soy el asistente virtual de PluriLang. 🤖\n\n"
        "Puedo ayudarte con información sobre nuestros programas de idiomas, "
        "precios, horarios, modalidades de estudio, inscripciones y "
        "certificaciones, basándome únicamente en la información oficial "
        "de la academia.\n\n"
        "Puedes hacerme una pregunta específica en cualquier momento o "
        "seleccionar una de las opciones para consultar nuestros temas "
        "más frecuentes.\n\n"
        "¿Cómo puedo ayudarte?"
    )

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "💰 Precios y descuentos", "callback_data": "prices"},
                {"text": "📚 Idiomas y niveles", "callback_data": "languages"}
            ],
            [
                {"text": "🕐 Horarios y modalidades", "callback_data": "schedules"},
                {"text": "📝 Inscripciones", "callback_data": "enrollment"}
            ],
            [
                {"text": "🎓 Certificaciones", "callback_data": "certifications"}
            ],
            [
                {"text": "👨‍💼 Hablar con un asesor", "callback_data": "human"}
            ]
        ]
    }

    await send_message(chat_id, welcome_message, keyboard)

async def send_main_menu(chat_id: int):
    """Send the main menu."""
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "💰 Precios y descuentos", "callback_data": "prices"},
                {"text": "📚 Idiomas y niveles", "callback_data": "languages"}
            ],
            [
                {"text": "🕐 Horarios y modalidades", "callback_data": "schedules"},
                {"text": "📝 Inscripciones", "callback_data": "enrollment"}
            ],
            [
                {"text": "🎓 Certificaciones", "callback_data": "certifications"}
            ],
            [
                {"text": "👨‍💼 Hablar con un asesor", "callback_data": "human"}
            ]
        ]
    }

    await send_message(
        chat_id,
        "¿Qué te gustaría consultar sobre PluriLang?\n\n"
        "También puedes escribir tu pregunta directamente.",
        keyboard
    )

# ---------------------------------------------------------
# Menu option handlers
# ---------------------------------------------------------

MENU_QUESTIONS = {
    "prices": "¿Cuáles son los precios y descuentos de los programas de idiomas?",
    "languages": "¿Qué idiomas y niveles ofrece PluriLang?",
    "schedules": "¿Qué modalidades de estudio y horarios están disponibles?",
    "enrollment": "¿Cómo puedo inscribirme en PluriLang?",
    "certifications": "¿Qué certificaciones y certificados ofrece PluriLang?"
}

async def handle_menu_option(chat_id: int, option: str, user_question: str = "Solicitud directa de asesor vía menú"):
    """Process a menu option through the same RAG pipeline."""
    global total_queries
    global escalated_queries
    global total_input_tokens
    global total_output_tokens
    global total_tokens

    # -----------------------------------------------------
    # Human advisor
    # -----------------------------------------------------
    if option == "human":
        await send_message(
            chat_id,
            "🔄 Te estoy transfiriendo con un asesor humano..."
        )
        
        # Disparamos el webhook hacia n8n sin pausar el bot de Telegram
        asyncio.create_task(notify_n8n(chat_id, user_question))

        await asyncio.sleep(1.5)

        await send_message(
            chat_id,
            "Lo sentimos, pero en este momento no tenemos un asesor "
            "humano disponible para atenderte.\n\n"
            "Un miembro de nuestro equipo se pondrá en contacto contigo "
            "por este mismo medio tan pronto como sea posible.\n\n"
            "Mientras tanto, ¿te gustaría hacer otra pregunta?"
        )

        await send_main_menu(chat_id)
        return

    # -----------------------------------------------------
    # Invalid menu option
    # -----------------------------------------------------
    if option not in MENU_QUESTIONS:
        return

    # -----------------------------------------------------
    # RAG query
    # -----------------------------------------------------
    question = MENU_QUESTIONS[option]
    total_queries += 1

    answer, requiere_escalamiento, usage = process_query(question)

    if requiere_escalamiento:
        escalated_queries += 1

    total_input_tokens += usage.get("input_tokens", 0)
    total_output_tokens += usage.get("output_tokens", 0)
    total_tokens += usage.get("total_tokens", 0)

    await send_message(chat_id, answer)

    if requiere_escalamiento:
        await handle_menu_option(chat_id, "human", user_question=question)
        return

    await send_message(
        chat_id,
        "¿Te gustaría hacer otra pregunta o consultar otro tema?"
    )
    await send_main_menu(chat_id)

# ---------------------------------------------------------
# FastAPI endpoints
# ---------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def home():
    html_content = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>PluriLang Barranquilla | Academia de Idiomas</title>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <style>
            :root {
                --primary: #c90042;
                --text-light: #ffffff;
                --bg-light: #f4f7f6;
            }
            * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
            body { background-color: var(--bg-light); color: #333; }
            
            /* Navbar */
            .navbar {
                position: absolute; top: 0; width: 100%; padding: 20px 50px;
                display: flex; justify-content: space-between; align-items: center;
                background: linear-gradient(rgba(0,0,0,0.7), transparent); z-index: 10;
            }
            .navbar .logo { color: var(--text-light); font-size: 24px; font-weight: bold; }
            .nav-links a { color: var(--text-light); text-decoration: none; margin: 0 15px; font-size: 14px; }
            .nav-btn { background-color: var(--primary); color: var(--text-light); padding: 8px 20px; border-radius: 20px; text-decoration: none; font-weight: bold; }
            
            /* Hero Section */
            .hero {
                height: 100vh;
                background: linear-gradient(to right, rgba(15, 23, 42, 0.9) 30%, rgba(15, 23, 42, 0.4) 100%), 
                            url('https://images.unsplash.com/photo-1523240795612-9a054b0db644?ixlib=rb-4.0.3&auto=format&fit=crop&w=1920&q=80') center/cover;
                display: flex; align-items: center; padding: 0 10%;
            }
            .hero-content { max-width: 600px; color: var(--text-light); }
            .hero-content h1 { font-size: 3.5rem; margin-bottom: 20px; line-height: 1.1; }
            .hero-content p { font-size: 1.1rem; margin-bottom: 30px; opacity: 0.9; }
            .btn-main {
                display: inline-block; background-color: var(--primary); color: var(--text-light);
                padding: 15px 35px; text-decoration: none; border-radius: 30px; font-weight: bold; font-size: 1.1rem;
            }
            
            /* Data Section */
            .info-section { padding: 60px 10%; display: grid; grid-template-columns: repeat(3, 1fr); gap: 30px; }
            .info-card { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 5px 15px rgba(0,0,0,0.05); }
            .info-card h3 { color: var(--primary); margin-bottom: 15px; }
            
            /* Floating Bot Button */
            .floating-bot {
                position: fixed; bottom: 30px; left: 30px;
                background-color: #0088cc; color: white; width: 60px; height: 60px;
                border-radius: 50%; display: flex; justify-content: center; align-items: center;
                font-size: 30px; text-decoration: none; box-shadow: 0 4px 10px rgba(0,0,0,0.3);
                z-index: 100; transition: transform 0.3s;
            }
            .floating-bot:hover { transform: scale(1.1); }
        </style>
    </head>
    <body>

        <nav class="navbar">
            <div class="logo">PluriLang <span style="font-weight: 300; font-size: 18px;">Barranquilla</span></div>
            <div class="nav-links">
                <a href="#">Inicio</a>
                <a href="#">Acerca De</a>
                <a href="#">Programas</a>
                <a href="#" class="nav-btn">Contacto</a>
            </div>
        </nav>

        <section class="hero">
            <div class="hero-content">
                <h1>Aprende Idiomas Con Docentes Expertos</h1>
                <p>Abre las puertas a un mundo de oportunidades con nuestros programas de idiomas. Aprende con metodología innovadora, desde Inglés hasta Italiano. Inscríbete hoy y domina un nuevo idioma.</p>
                <a href="t.me/multilang_barranquilla_bot" class="btn-main" target="_blank">¡Hablar con el Asistente!</a>
            </div>
        </section>

        <section class="info-section">
            <div class="info-card">
                <h3><i class="fas fa-globe"></i> 5 Idiomas Disponibles</h3>
                <p>Ofrecemos programas estructurados en Inglés, Francés, Portugués, Alemán e Italiano desde el nivel A1.</p>
            </div>
            <div class="info-card">
                <h3><i class="fas fa-laptop-house"></i> 3 Modalidades</h3>
                <p>Estudia a tu ritmo eligiendo entre modalidad Presencial, Virtual en vivo o Híbrida.</p>
            </div>
            <div class="info-card">
                <h3><i class="fas fa-tag"></i> Descuentos Especiales</h3>
                <p>Mensualidades desde $280.000 COP. Aprovecha hasta un 15% de descuento inscribiéndote en grupo.</p>
            </div>
        </section>

        <a href="t.me/multilang_barranquilla_bot" class="floating-bot" target="_blank" title="Chatea con nuestro bot">
            <i class="fab fa-telegram-plane"></i>
        </a>

    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/metrics")
def metrics():
    escalation_rate = (
        (escalated_queries / total_queries) * 100
        if total_queries > 0
        else 0
    )
    return {
        "total_queries": total_queries,
        "escalated_queries": escalated_queries,
        "escalation_rate": round(escalation_rate, 2),
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_tokens": total_tokens,
        "status": "online"
    }

@app.post("/webhook")
async def telegram_webhook(request: Request):
    """Receive Telegram webhook updates."""
    global total_queries
    global escalated_queries
    global total_input_tokens
    global total_output_tokens
    global total_tokens

    data = await request.json()

    # -----------------------------------------------------
    # Standard Telegram message
    # -----------------------------------------------------
    if "message" in data:
        message = data["message"]
        if "chat" not in message:
            return {"ok": True}

        chat_id = message["chat"]["id"]
        user_text = message.get("text", "").strip()

        if user_text.lower() == "/start":
            await send_start_message(chat_id)
            return {"ok": True}

        if user_text.lower() in ["opciones", "opcion", "menú", "menu", "ayuda"]:
            await send_main_menu(chat_id)
            return {"ok": True}

        if not user_text:
            return {"ok": True}

        # -------------------------------------------------
        # Normal user question -> RAG pipeline
        # -------------------------------------------------
        total_queries += 1

        respuesta_ia, requiere_escalamiento, usage = process_query(user_text)

        if requiere_escalamiento:
            escalated_queries += 1

        total_input_tokens += usage.get("input_tokens", 0)
        total_output_tokens += usage.get("output_tokens", 0)
        total_tokens += usage.get("total_tokens", 0)

        await send_message(chat_id, respuesta_ia)

        if requiere_escalamiento:
            # Pasamos el texto real del usuario para que n8n sepa qué preguntó
            await handle_menu_option(chat_id, "human", user_question=user_text)

        return {"ok": True}

    # -----------------------------------------------------
    # Telegram inline keyboard callback
    # -----------------------------------------------------
    if "callback_query" in data:
        callback_query = data["callback_query"]
        callback_id = callback_query["id"]
        callback_data = callback_query.get("data")
        chat_id = callback_query["message"]["chat"]["id"]

        async with httpx.AsyncClient() as client:
            await client.post(
                f"{TELEGRAM_API_URL}/answerCallbackQuery",
                json={"callback_query_id": callback_id}
            )

        if callback_data == "menu":
            await send_main_menu(chat_id)
        else:
            await handle_menu_option(chat_id, callback_data)

        return {"ok": True}

    return {"ok": True}