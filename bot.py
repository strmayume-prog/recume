from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from fastapi import FastAPI, Request
import requests, os, asyncio, threading
from requests.auth import HTTPBasicAuth
import logging

# 🔑 Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 🔑 Variáveis de ambiente
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
GROUP_ID = os.getenv("GROUP_ID", "").strip()
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "").strip()
PAYPAL_SECRET = os.getenv("PAYPAL_SECRET", "").strip()
PAYPAL_API = "https://api-m.sandbox.paypal.com"

# Global variable to hold the application instance
telegram_app = None

# ---------- TELEGRAM BOT ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Comando /start recebido de {update.effective_user.id}")
    await update.message.reply_text("👋 Olá! Use /assinar para adquirir sua assinatura.")

async def assinar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        logger.info(f"Comando /assinar recebido de {user_id}")

        # Verificar se as variáveis de ambiente estão carregadas
        if not all([BOT_TOKEN, PAYPAL_CLIENT_ID, PAYPAL_SECRET]):
            await update.message.reply_text("❌ Erro de configuração. Tente novamente mais tarde.")
            return

        # Obter token PayPal
        res = requests.post(
            f"{PAYPAL_API}/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            auth=HTTPBasicAuth(PAYPAL_CLIENT_ID, PAYPAL_SECRET)
        )
        
        if res.status_code != 200:
            logger.error(f"Erro PayPal Auth: {res.status_code} - {res.text}")
            await update.message.reply_text("❌ Erro no processamento. Tente novamente.")
            return
            
        access_token = res.json().get("access_token")
        if not access_token:
            await update.message.reply_text("❌ Erro de autenticação.")
            return

        # Criar ordem PayPal
        order_data = {
            "intent": "CAPTURE",
            "purchase_units": [{
                "amount": {"currency_code": "BRL", "value": "18.99"},
                "custom_id": str(user_id)
            }],
            "application_context": {
                "return_url": "https://recume-1.onrender.com/success",
                "cancel_url": "https://recume-1.onrender.com/cancel"
            }
        }

        res = requests.post(
            f"{PAYPAL_API}/v2/checkout/orders",
            json=order_data,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            }
        )

        if res.status_code != 201:
            logger.error(f"Erro PayPal Order: {res.status_code} - {res.text}")
            await update.message.reply_text("❌ Erro ao criar pedido.")
            return

        order = res.json()
        link_pagamento = None
        for link in order.get("links", []):
            if link.get("rel") == "approve":
                link_pagamento = link.get("href")
                break

        if not link_pagamento:
            await update.message.reply_text("❌ Erro ao gerar link de pagamento.")
            return

        await update.message.reply_text(
            f"💳 **Assinatura Premium**\n\n"
            f"Valor: R$ 18,99\n"
            f"Clique no link abaixo para pagar:\n"
            f"{link_pagamento}\n\n"
            f"Após o pagamento, você será adicionado automaticamente ao grupo VIP!"
        )
        logger.info(f"Link de pagamento enviado para {user_id}")

    except Exception as e:
        logger.error(f"Erro em /assinar: {e}")
        await update.message.reply_text("❌ Ocorreu um erro. Tente novamente.")

# Função para inicializar e rodar o bot
async def initialize_bot():
    global telegram_app
    try:
        logger.info("Iniciando bot Telegram...")
        
        # Criar a aplicação
        telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()
        
        # Adicionar handlers
        telegram_app.add_handler(CommandHandler("start", start))
        telegram_app.add_handler(CommandHandler("assinar", assinar))
        
        # Inicializar
        await telegram_app.initialize()
        await telegram_app.start()
        
        # Usar polling para receber mensagens
        await telegram_app.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )
        
        logger.info("✅ Bot Telegram iniciado com sucesso com polling!")
        
    except Exception as e:
        logger.error(f"❌ Erro ao iniciar bot: {e}")

# Função para rodar em thread
def run_bot():
    asyncio.run(initialize_bot())

# ---------- FASTAPI SETUP ----------
fastapi_app = FastAPI()

@fastapi_app.get("/")
def home():
    return {"status": "ok", "message": "Bot está rodando!"}

@fastapi_app.get("/health")
def health():
    bot_status = "running" if telegram_app else "stopped"
    return {"status": "ok", "bot": bot_status}

@fastapi_app.get("/success")
def success():
    return """
    <html>
        <body>
            <h1>Pagamento Aprovado! ✅</h1>
            <p>Seu pagamento foi aprovado com sucesso!</p>
            <p>Você será adicionado ao grupo VIP em instantes.</p>
            <p>Volte ao Telegram e aguarde a confirmação.</p>
        </body>
    </html>
    """

@fastapi_app.get("/cancel")
def cancel():
    return """
    <html>
        <body>
            <h1>Pagamento Cancelado ❌</h1>
            <p>Seu pagamento foi cancelado.</p>
            <p>Você pode tentar novamente quando quiser.</p>
        </body>
    </html>
    """

@fastapi_app.post("/paypal-webhook")
async def paypal_webhook(request: Request):
    try:
        data = await request.json()
        event_type = data.get("event_type")
        logger.info(f"Webhook recebido: {event_type}")

        if event_type == "PAYMENT.CAPTURE.COMPLETED":
            custom_id = data.get("resource", {}).get("custom_id")
            if custom_id:
                user_id = int(custom_id)
                
                # Adicionar usuário ao grupo
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/approveChatJoinRequest"
                response = requests.post(
                    url,
                    json={
                        "chat_id": GROUP_ID,
                        "user_id": user_id
                    }
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ Usuário {user_id} aprovado no grupo")
                    
                    # Tentar enviar mensagem direta também
                    try:
                        requests.post(
                            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                            json={
                                "chat_id": user_id,
                                "text": "✅ Pagamento confirmado! Você foi adicionado ao grupo VIP. Acesse: https://t.me/c/2114282154/1"
                            }
                        )
                    except:
                        pass
                else:
                    logger.error(f"Erro ao adicionar usuário: {response.text}")
            
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Erro no webhook: {e}")
        return {"status": "error"}

# ---------- INÍCIO DO SERVIÇO ----------
if __name__ == "__main__":
    logger.info("🚀 Iniciando aplicação...")
    
    # Verificar variáveis de ambiente
    required_vars = ["BOT_TOKEN", "GROUP_ID", "PAYPAL_CLIENT_ID", "PAYPAL_SECRET"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Variáveis faltando: {missing_vars}")
    else:
        logger.info("Todas as variáveis de ambiente estão presentes")
    
    # Inicia o bot em uma thread separada
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    logger.info("Thread do bot iniciada")

    # Inicia o FastAPI
    import uvicorn
    uvicorn.run(fastapi_app, host="0.0.0.0", port=10000, log_level="info")
