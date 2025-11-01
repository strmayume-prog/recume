from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from fastapi import FastAPI, Request
import requests, os, asyncio, threading
from requests.auth import HTTPBasicAuth

# 🔑 Variáveis de ambiente - removendo espaços em branco
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
GROUP_ID = os.getenv("GROUP_ID", "").strip()
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "").strip()
PAYPAL_SECRET = os.getenv("PAYPAL_SECRET", "").strip()
PAYPAL_API = "https://api-m.sandbox.paypal.com"

# ---------- TELEGRAM BOT ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Olá! Use /assinar para adquirir sua assinatura.")

async def assinar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        print(f"Usuário {user_id} solicitou assinatura")

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
            print(f"Erro PayPal Auth: {res.status_code} - {res.text}")
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
                "Content-Type": "application/json"
            }
        )

        if res.status_code != 201:
            print(f"Erro PayPal Order: {res.status_code} - {res.text}")
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
            f"💳 Pague sua assinatura de R$18,99 aqui:\n{link_pagamento}"
        )

    except Exception as e:
        print(f"Erro em /assinar: {e}")
        await update.message.reply_text("❌ Ocorreu um erro. Tente novamente.")

# Função para rodar o bot
async def start_telegram_bot():
    try:
        print("Iniciando bot Telegram...")
        print(f"Token: {BOT_TOKEN[:10]}...")  # Log parcial do token
        
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("assinar", assinar))
        
        await app.initialize()
        await app.start()
        print("Bot iniciado com sucesso!")
        await app.updater.start_polling()
        
    except Exception as e:
        print(f"Erro ao iniciar bot: {e}")

def run_bot():
    asyncio.run(start_telegram_bot())

# ---------- FASTAPI SETUP ----------
fastapi_app = FastAPI()

@fastapi_app.get("/")
def home():
    return {"status": "ok", "message": "Bot está rodando!"}

@fastapi_app.get("/success")
def success():
    return {"status": "success", "message": "Pagamento aprovado!"}

@fastapi_app.get("/cancel")
def cancel():
    return {"status": "cancel", "message": "Pagamento cancelado!"}

@fastapi_app.post("/paypal-webhook")
async def paypal_webhook(request: Request):
    try:
        data = await request.json()
        event_type = data.get("event_type")
        print(f"Webhook recebido: {event_type}")

        if event_type == "PAYMENT.CAPTURE.COMPLETED":
            user_id = int(data["resource"]["custom_id"])
            # Adicionar usuário ao grupo
            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/inviteChatMember",
                json={"chat_id": GROUP_ID, "user_id": user_id}
            )
            print(f"✅ Usuário {user_id} adicionado ao grupo. Status: {response.status_code}")
            
        return {"status": "ok"}
    except Exception as e:
        print(f"Erro no webhook: {e}")
        return {"status": "error"}

# ---------- INÍCIO DO SERVIÇO ----------
if __name__ == "__main__":
    print("Iniciando aplicação...")
    # Inicia o bot em uma thread separada
    threading.Thread(target=run_bot, daemon=True).start()

    # Inicia o FastAPI
    import uvicorn
    uvicorn.run(fastapi_app, host="0.0.0.0", port=10000)
