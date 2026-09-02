import os
import json
import asyncio
import secrets
from datetime import datetime

from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from dotenv import load_dotenv
import httpx

from agent import process_query

load_dotenv()
app = FastAPI(title="PluriLang Barranquilla Assistant")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")

security = HTTPBasic()

def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    # Lee las credenciales del .env o usa un valor por defecto seguro
    admin_user = os.getenv("ADMIN_USER", "admin")
    admin_pass = os.getenv("ADMIN_PASS", "plurilang2026")
    
    is_correct_username = secrets.compare_digest(credentials.username, admin_user)
    is_correct_password = secrets.compare_digest(credentials.password, admin_pass)
    
    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# ---------------------------------------------------------
# Persistencia de Métricas
# ---------------------------------------------------------
METRICS_FILE = "metrics.json"

def load_metrics():
    if os.path.exists(METRICS_FILE):
        try:
            with open(METRICS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "total_queries": 0, "escalated_queries": 0,
        "total_input_tokens": 0, "total_output_tokens": 0, "total_tokens": 0
    }

metrics_data = load_metrics()

def save_metrics():
    with open(METRICS_FILE, "w") as f:
        json.dump(metrics_data, f)

def update_metrics(requiere_escalamiento, usage):
    metrics_data["total_queries"] += 1
    if requiere_escalamiento:
        metrics_data["escalated_queries"] += 1
    metrics_data["total_input_tokens"] += usage.get("input_tokens", 0)
    metrics_data["total_output_tokens"] += usage.get("output_tokens", 0)
    metrics_data["total_tokens"] += usage.get("total_tokens", 0)
    save_metrics()

# ---------------------------------------------------------
# Telegram & n8n helpers
# ---------------------------------------------------------
async def notify_n8n(chat_id: int, user_question: str):
    if not N8N_WEBHOOK_URL:
        return
    payload = {
        "user_question": user_question,
        "chat_id": str(chat_id),
        "message": "Escalamiento requerido por el asistente virtual.",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    async with httpx.AsyncClient() as client:
        try:
            await client.post(N8N_WEBHOOK_URL, json=payload, timeout=5.0)
        except Exception:
            pass

async def send_message(chat_id: int, text: str, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    async with httpx.AsyncClient() as client:
        await client.post(f"{TELEGRAM_API_URL}/sendMessage", json=payload)

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

async def handle_menu_option(chat_id: int, option: str, user_question: str = "Solicitud vía menú"):
    if option == "human":
        await send_message(chat_id, "🔄 Transfiriendo con un asesor...")
        asyncio.create_task(notify_n8n(chat_id, user_question))
        await asyncio.sleep(1.5)
        await send_message(chat_id, "Lo sentimos, pero en este momento no tenemos un asesor humano disponible para atenderte.\n Un miembro de nuestro equipo se pondrá en contacto contigo por este mismo medio tan pronto como sea posible.\n Mientras tanto, ¿te gustaría hacer otra pregunta?")
        await send_main_menu(chat_id)
        return

    if option not in MENU_QUESTIONS:
        return

    question = MENU_QUESTIONS[option]
    answer, requiere_escalamiento, usage = process_query(question)
    
    update_metrics(requiere_escalamiento, usage)
    await send_message(chat_id, answer)

    if requiere_escalamiento:
        await handle_menu_option(chat_id, "human", user_question=question)
        return
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
            :root { --primary: #c90042; --text-light: #ffffff; --bg-light: #f4f7f6; }
            * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
            body { background-color: var(--bg-light); color: #333; }
            
            .navbar { position: absolute; top: 0; width: 100%; padding: 20px 50px; display: flex; justify-content: space-between; align-items: center; background: linear-gradient(rgba(0,0,0,0.7), transparent); z-index: 10; }
            .navbar .logo { color: var(--text-light); font-size: 24px; font-weight: bold; }
            .nav-links a { color: var(--text-light); text-decoration: none; margin: 0 15px; font-size: 14px; }
            .nav-btn { background-color: var(--primary); color: var(--text-light); padding: 8px 20px; border-radius: 20px; text-decoration: none; font-weight: bold; cursor: pointer; border: none; }
            
            .hero { height: 100vh; background: linear-gradient(to right, rgba(15, 23, 42, 0.9) 30%, rgba(15, 23, 42, 0.4) 100%), url('https://images.unsplash.com/photo-1523240795612-9a054b0db644?ixlib=rb-4.0.3&auto=format&fit=crop&w=1920&q=80') center/cover; display: flex; align-items: center; padding: 0 10%; }
            .hero-content { max-width: 600px; color: var(--text-light); }
            .hero-content h1 { font-size: 3.5rem; margin-bottom: 20px; line-height: 1.1; }
            .hero-content p { font-size: 1.1rem; margin-bottom: 30px; opacity: 0.9; }
            .btn-main { display: inline-block; background-color: var(--primary); color: var(--text-light); padding: 15px 35px; text-decoration: none; border-radius: 30px; font-weight: bold; font-size: 1.1rem; cursor: pointer; border: none; }
            
            .info-section { padding: 60px 10%; display: grid; grid-template-columns: repeat(3, 1fr); gap: 30px; }
            .info-card { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 5px 15px rgba(0,0,0,0.05); }
            .info-card h3 { color: var(--primary); margin-bottom: 15px; }
            
            .floating-bot { position: fixed; bottom: 30px; left: 30px; background-color: #0088cc; color: white; width: 60px; height: 60px; border-radius: 50%; display: flex; justify-content: center; align-items: center; font-size: 30px; text-decoration: none; box-shadow: 0 4px 10px rgba(0,0,0,0.3); z-index: 100; transition: transform 0.3s; cursor: pointer; border: none; }
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
                <button onclick="openBot()" class="nav-btn">Contacto</button>
            </div>
        </nav>

        <section class="hero">
            <div class="hero-content">
                <h1>Aprende Idiomas Con Docentes Expertos</h1>
                <p>Abre las puertas a un mundo de oportunidades con nuestros programas de idiomas. Aprende con metodología innovadora, desde Inglés hasta Italiano. Inscríbete hoy y domina un nuevo idioma.</p>
                <button onclick="openBot()" class="btn-main">¡Hablar con el Asistente!</button>
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

        <button onclick="openBot()" class="floating-bot" title="Chatea con nuestro bot">
            <i class="fab fa-telegram-plane"></i>
        </button>

        <script>
            function openBot() {
                const botUsername = "multilang_barranquilla_bot";
                const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
                
                if (isMobile) {
                    window.location.href = `https://t.me/${botUsername}`;
                } else {
                    window.open(`https://web.telegram.org/k/#@${botUsername}`, '_blank');
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(username: str = Depends(verify_credentials)):
    # Costos gpt-4o-mini: $0.150/1M input, $0.600/1M output
    costo_input = (metrics_data["total_input_tokens"] / 1_000_000) * 0.150
    costo_output = (metrics_data["total_output_tokens"] / 1_000_000) * 0.600
    costo_total = costo_input + costo_output
    
    tasa_escalamiento = 0
    if metrics_data["total_queries"] > 0:
        tasa_escalamiento = (metrics_data["escalated_queries"] / metrics_data["total_queries"]) * 100

    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <title>Admin | PluriLang</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, sans-serif; background: #f4f7f6; padding: 40px; color: #333; }}
            h2 {{ color: #2c3e50; text-align: center; margin-bottom: 30px; }}
            .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 20px; max-width: 900px; margin: 0 auto; }}
            .card {{ background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); text-align: center; border-top: 4px solid #c90042; }}
            .card h3 {{ margin-top: 0; color: #7f8c8d; font-size: 1rem; text-transform: uppercase; }}
            .value {{ font-size: 2.5rem; font-weight: bold; color: #2c3e50; }}
            .subtext {{ font-size: 0.9rem; color: #95a5a6; margin-top: 5px; }}
        </style>
    </head>
    <body>
        <h2>📊 Panel de Control y Costos API</h2>
        <div class="grid">
            <div class="card">
                <h3>Consultas Procesadas</h3>
                <div class="value">{metrics_data['total_queries']}</div>
            </div>
            <div class="card">
                <h3>Tasa de Escalamiento</h3>
                <div class="value">{tasa_escalamiento:.1f}%</div>
                <div class="subtext">Derivadas a n8n</div>
            </div>
            <div class="card">
                <h3>Tokens Consumidos</h3>
                <div class="value">{metrics_data['total_tokens']:,}</div>
                <div class="subtext">Ahorro activo por caché</div>
            </div>
            <div class="card">
                <h3>Costo Acumulado</h3>
                <div class="value">${costo_total:.5f}</div>
                <div class="subtext">USD (gpt-4o-mini)</div>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    if "message" in data and "chat" in data["message"]:
        chat_id = data["message"]["chat"]["id"]
        user_text = data["message"].get("text", "").strip()

        if user_text.lower() == "/start":
            await send_start_message(chat_id)
            return {"ok": True}

        if user_text.lower() in ["opciones", "menu", "ayuda"]:
            await send_main_menu(chat_id)
            return {"ok": True}

        if not user_text:
            return {"ok": True}

        answer, requiere_escalamiento, usage = process_query(user_text)
        update_metrics(requiere_escalamiento, usage)
        
        await send_message(chat_id, answer)
        if requiere_escalamiento:
            await handle_menu_option(chat_id, "human", user_question=user_text)
            
    elif "callback_query" in data:
        cb = data["callback_query"]
        chat_id = cb["message"]["chat"]["id"]
        async with httpx.AsyncClient() as client:
            await client.post(f"{TELEGRAM_API_URL}/answerCallbackQuery", json={"callback_query_id": cb["id"]})
        await handle_menu_option(chat_id, cb["data"])

    return {"ok": True}