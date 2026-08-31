import os
import asyncio

from fastapi import FastAPI, Request
from dotenv import load_dotenv
import httpx

from agent import process_query


# Load environment variables
load_dotenv()

app = FastAPI(title="PluriLang Barranquilla Assistant")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


# ---------------------------------------------------------
# Metrics
# ---------------------------------------------------------

total_queries = 0
escalated_queries = 0

total_input_tokens = 0
total_output_tokens = 0
total_tokens = 0


# ---------------------------------------------------------
# Telegram helpers
# ---------------------------------------------------------

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
                {
                    "text": "💰 Precios y descuentos",
                    "callback_data": "prices"
                },
                {
                    "text": "📚 Idiomas y niveles",
                    "callback_data": "languages"
                }
            ],
            [
                {
                    "text": "🕐 Horarios y modalidades",
                    "callback_data": "schedules"
                },
                {
                    "text": "📝 Inscripciones",
                    "callback_data": "enrollment"
                }
            ],
            [
                {
                    "text": "🎓 Certificaciones",
                    "callback_data": "certifications"
                }
            ],
            [
                {
                    "text": "👨‍💼 Hablar con un asesor",
                    "callback_data": "human"
                }
            ]
        ]
    }

    await send_message(
        chat_id,
        welcome_message,
        keyboard
    )


async def send_main_menu(chat_id: int):
    """Send the main menu."""

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "💰 Precios y descuentos",
                    "callback_data": "prices"
                },
                {
                    "text": "📚 Idiomas y niveles",
                    "callback_data": "languages"
                }
            ],
            [
                {
                    "text": "🕐 Horarios y modalidades",
                    "callback_data": "schedules"
                },
                {
                    "text": "📝 Inscripciones",
                    "callback_data": "enrollment"
                }
            ],
            [
                {
                    "text": "🎓 Certificaciones",
                    "callback_data": "certifications"
                }
            ],
            [
                {
                    "text": "👨‍💼 Hablar con un asesor",
                    "callback_data": "human"
                }
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


async def handle_menu_option(chat_id: int, option: str):
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

    # Token usage
    total_input_tokens += usage.get("input_tokens", 0)
    total_output_tokens += usage.get("output_tokens", 0)
    total_tokens += usage.get("total_tokens", 0)

    await send_message(
        chat_id,
        answer
    )

    # If RAG requires escalation, perform the human transfer flow.
    if requiere_escalamiento:
        await handle_menu_option(chat_id, "human")
        return

    await send_message(
        chat_id,
        "¿Te gustaría hacer otra pregunta o consultar otro tema?"
    )

    await send_main_menu(chat_id)


# ---------------------------------------------------------
# FastAPI endpoints
# ---------------------------------------------------------

@app.get("/")
def home():
    return {
        "status": "PluriLang Barranquilla Assistant is online 🚀"
    }


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

        # -------------------------------------------------
        # /start
        # -------------------------------------------------

        if user_text.lower() == "/start":
            await send_start_message(chat_id)
            return {"ok": True}

        # -------------------------------------------------
        # Main menu commands
        # -------------------------------------------------

        if user_text.lower() in [
            "opciones",
            "opcion",
            "menú",
            "menu",
            "ayuda"
        ]:
            await send_main_menu(chat_id)
            return {"ok": True}

        # Ignore messages without text.
        if not user_text:
            return {"ok": True}

        # -------------------------------------------------
        # Normal user question -> RAG pipeline
        # -------------------------------------------------

        total_queries += 1

        respuesta_ia, requiere_escalamiento, usage = process_query(
            user_text
        )

        if requiere_escalamiento:
            escalated_queries += 1

        # Token usage
        total_input_tokens += usage.get("input_tokens", 0)
        total_output_tokens += usage.get("output_tokens", 0)
        total_tokens += usage.get("total_tokens", 0)

        # First send the RAG response.
        await send_message(
            chat_id,
            respuesta_ia
        )

        # If the RAG response requires human assistance,
        # continue with the transfer simulation.
        if requiere_escalamiento:
            await handle_menu_option(chat_id, "human")

        return {"ok": True}

    # -----------------------------------------------------
    # Telegram inline keyboard callback
    # -----------------------------------------------------

    if "callback_query" in data:

        callback_query = data["callback_query"]

        callback_id = callback_query["id"]
        callback_data = callback_query.get("data")
        chat_id = callback_query["message"]["chat"]["id"]

        # Acknowledge the callback to Telegram
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{TELEGRAM_API_URL}/answerCallbackQuery",
                json={
                    "callback_query_id": callback_id
                }
            )

        if callback_data == "menu":
            await send_main_menu(chat_id)

        else:
            await handle_menu_option(
                chat_id,
                callback_data
            )

        return {"ok": True}

    return {"ok": True}
