from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from fastapi import FastAPI
import requests
import os
import logging
import asyncio
from contextlib import asynccontextmanager

# 🔧 Configuração de Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 🔑 Variáveis de Ambiente - COM VALORES DIRETOS PARA TESTE
BOT_TOKEN = os.getenv("BOT_TOKEN", "7602116178:AAGgcZtmvISxyK8WcCmQVyG9ra8e_SPHWc4").strip()
GROUP_ID = os.getenv("GROUP_ID", "-1002114282154").strip()
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "AS4GJYXde9JWZsuocnMO62bn509mmeFM5kycHj-gDvEzCONCXuzCeoU6Kx7I1K2tKRCQrbR_jH8-PwrB").strip()
PAYPAL_SECRET = os.getenv("PAYPAL_SECRET", "EEGEKpyQSO0FKtEmLmJtJObWaUQstYsemwXcDLAjD0tZ8pWbvGW1Hvur4Oh6BDNx6jXnMaS32DLo4RO6").strip()
PAYPAL_API = "https://api-m.sandbox.paypal.com"

# Verificar se as variáveis estão carregadas
logger.info(f"BOT_TOKEN: {BOT_TOKEN[:10]}...")
logger.info(f"GROUP_ID: {GROUP_ID}")
logger.info(f"PAYPAL_CLIENT_ID: {PAYPAL_CLIENT_ID[:10]}...")

# 🌟 Telegram Bot Functions
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para o comando /start"""
    user = update.effective_user
    logger.info(f"Usuário {user.id} usou /start")
    
    welcome_text = (
        "👋 *Bem-vindo ao Shinmeta28 Bot!*\n\n"
        "Para adquirir acesso ao grupo VIP, use o comando:\n"
        "`/assinar`\n\n"
        "Valor: R$ 18,99/mês"
    )
    
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def assinar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para o comando /assinar"""
    try:
        user_id = update.effective_user.id
        logger.info(f"Usuário {user_id} solicitou assinatura")

        # 1. Obter Access Token do PayPal
        auth_response = requests.post(
            f"{PAYPAL_API}/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET),
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if auth_response.status_code != 200:
            logger.error(f"Falha na autenticação PayPal: {auth_response.text}")
            await update.message.reply_text("❌ Erro temporário. Tente novamente em alguns instantes.")
            return
        
        access_token = auth_response.json()["access_token"]
        logger.info("Token PayPal obtido com sucesso")

        # 2. Criar Ordem no PayPal
        order_payload = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "amount": {
                        "currency_code": "BRL",
                        "value": "18.99"
                    },
                    "custom_id": str(user_id)
                }
            ],
            "application_context": {
                "brand_name": "Shinmeta28 VIP",
                "return_url": "https://recume.onrender.com/success",
                "cancel_url": "https://recume.onrender.com/cancel",
                "user_action": "PAY_NOW"
            }
        }

        order_response = requests.post(
            f"{PAYPAL_API}/v2/checkout/orders",
            json=order_payload,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            }
        )

        if order_response.status_code != 201:
            logger.error(f"Falha ao criar ordem: {order_response.text}")
            await update.message.reply_text("❌ Erro ao processar pagamento.")
            return

        order_data = order_response.json()
        
        # 3. Encontrar link de aprovação
        approval_link = None
        for link in order_data.get("links", []):
            if link.get("rel") == "approve":
                approval_link = link.get("href")
                break

        if not approval_link:
            await update.message.reply_text("❌ Erro ao gerar link de pagamento.")
            return

        # 4. Enviar mensagem com o link
        message_text = (
            "💳 *ASSINATURA VIP*\n\n"
            "• Acesso ao grupo exclusivo\n"
            "• Valor: R$ 18,99\n"
            "• Pagamento único\n\n"
            f"[👉 CLIQUE AQUI PARA PAGAR]({approval_link})\n\n"
            "_Após o pagamento, você será adicionado automaticamente ao grupo VIP._"
        )
        
        await update.message.reply_text(
            message_text, 
            parse_mode='Markdown',
            disable_web_page_preview=False
        )
        
        logger.info(f"Link de pagamento enviado para usuário {user_id}")

    except Exception as e:
        logger.error(f"Erro no comando /assinar: {str(e)}")
        await update.message.reply_text("❌ Erro interno. Tente novamente mais tarde.")

# 🔄 Inicialização do Bot
async def start_bot():
    """Inicia o bot Telegram em background"""
    try:
        logger.info("🔄 Iniciando Telegram Bot...")
        
        # Verificar token
        if not BOT_TOKEN or " " in BOT_TOKEN:
            logger.error("Token inválido ou vazio")
            return None
            
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Adicionar handlers
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("assinar", assinar_command))
        
        # Inicializar
        await application.initialize()
        await application.start()
        await application.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )
        
        logger.info("✅ Bot Telegram iniciado com sucesso!")
        return application
        
    except Exception as e:
        logger.error(f"❌ Falha ao iniciar bot: {str(e)}")
        return None

# 🌟 FastAPI Lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Iniciando aplicação...")
    asyncio.create_task(start_bot())
    yield
    # Shutdown
    logger.info("🛑 Parando aplicação...")

# 🌟 FastAPI App
app = FastAPI(title="Shinmeta28 Bot", lifespan=lifespan)

# 🚀 Rotas FastAPI
@app.get("/")
async def root():
    return {
        "status": "online", 
        "service": "Shinmeta28 Bot",
        "bot": "shinmeta28_bot",
        "bot_status": "running"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "bot": "running"}

@app.get("/success")
async def success_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Pagamento Aprovado - Shinmeta28</title>
        <meta charset="UTF-8">
        <style>
            body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
            .success { color: #22c55e; font-size: 24px; }
            .info { color: #666; margin-top: 20px; }
        </style>
    </head>
    <body>
        <div class="success">✅ Pagamento Aprovado!</div>
        <div class="info">Você será adicionado ao grupo VIP em instantes.</div>
        <div class="info">Volte ao Telegram para acessar o conteúdo exclusivo.</div>
    </body>
    </html>
    """

@app.get("/cancel")
async def cancel_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Pagamento Cancelado - Shinmeta28</title>
        <meta charset="UTF-8">
        <style>
            body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
            .cancel { color: #ef4444; font-size: 24px; }
            .info { color: #666; margin-top: 20px; }
        </style>
    </head>
    <body>
        <div class="cancel">❌ Pagamento Cancelado</div>
        <div class="info">Você pode tentar novamente quando quiser.</div>
        <div class="info">Use /assinar no bot para reiniciar o processo.</div>
    </body>
    </html>
    """

@app.post("/paypal-webhook")
async def paypal_webhook(request: dict):
    """Webhook para processar pagamentos do PayPal"""
    try:
        event_type = request.get("event_type")
        logger.info(f"Webhook PayPal recebido: {event_type}")

        if event_type == "PAYMENT.CAPTURE.COMPLETED":
            resource = request.get("resource", {})
            custom_id = resource.get("custom_id")
            
            if custom_id:
                user_id = int(custom_id)
                logger.info(f"Pagamento confirmado para usuário {user_id}")
                
                # Adicionar usuário ao grupo
                telegram_url = f"https://api.telegram.org/bot{BOT_TOKEN}/approveChatJoinRequest"
                response = requests.post(
                    telegram_url,
                    json={
                        "chat_id": GROUP_ID,
                        "user_id": user_id
                    }
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ Usuário {user_id} adicionado ao grupo VIP")
                    
                    # Notificar usuário via Telegram
                    try:
                        requests.post(
                            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                            json={
                                "chat_id": user_id,
                                "text": "✅ *Pagamento confirmado!*\\n\\nAgora você faz parte do grupo VIP!\\n\\nAcesse: https://t.me/c/2114282154/1",
                                "parse_mode": "Markdown"
                            }
                        )
                    except Exception as e:
                        logger.error(f"Erro ao notificar usuário: {e}")
                else:
                    logger.error(f"Falha ao adicionar usuário: {response.text}")
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Erro no webhook: {str(e)}")
        return {"status": "error"}

# ⚠️ Execução Principal
if __name__ == "__main__":
    import uvicorn
    
    logger.info("=== INICIANDO SERVIDOR ===")
    logger.info(f"BOT_TOKEN presente: {bool(BOT_TOKEN)}")
    logger.info(f"PAYPAL_CLIENT_ID presente: {bool(PAYPAL_CLIENT_ID)}")
    
    # Iniciar servidor
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=10000,
        log_level="info"
    )
