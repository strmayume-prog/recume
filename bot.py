from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from fastapi import FastAPI, Request
import requests, asyncio, os
from requests.auth import HTTPBasicAuth
from threading import Thread

# 🔑 VARIÁVEIS DE AMBIENTE
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
PAYPAL_SECRET = os.getenv("PAYPAL_SECRET")
PAYPAL_API = "https://api-m.sandbox.paypal.com"  # usar produção depois

# ---------- TELEGRAM BOT ----------
async def assinar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Obter token PayPal
    res = requests.post(
        f"{PAYPAL_API}/v1/oauth2/token",
        data={"grant_type": "client_credentials"},
        auth=HTTPBasicAuth(PAYPAL_CLIENT_ID, PAYPAL_SECRET)
    )
    access_token = res.json()["access_token"]

    # Criar ordem PayPal
    order_data = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {"currency_code": "BRL", "value": "18.99"},
            "custom_id": str(user_id)
        }],
        "application_context": {
            "return_url": "https://seuapp.onrender.com/success",
            "cancel_url": "https://seuapp.onrender.com/cancel"
        }
    }

    res = requests.post(
        f"{PAYPAL_API}/v2/checkout/orders",
        json=order_data,
        headers={"Authorization": f"Bearer {access_token}"}
    )

    order = res.json()
    link_pagamento = next(l["href"] for l in order["links"] if l["rel"] == "approve")

    await update.message.reply_text(
        f"💳 Pague sua assinatura de R$18,99 aqui:\n{link_pagamento}"
    )

def run_telegram():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("assinar", assinar))
    app.run_polling()

# ---------- FASTAPI SERVIDOR ----------
fastapi_app = FastAPI()

@fastapi_app.post("/paypal-webhook")
async def paypal_webhook(request: Request):
    data = await request.json()
    event_type = data.get("event_type")

    if event_type == "PAYMENT.CAPTURE.COMPLETED":
        user_id = int(data["resource"]["custom_id"])
        # adicionar usuário ao grupo
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/inviteChatMember",
            json={"chat_id": GROUP_ID, "user_id": user_id}
        )
        print(f"✅ Usuário {user_id} pago e adicionado ao grupo")
    return {"status": "ok"}

@fastapi_app.get("/")
async def home():
    return {"status": "online"}

# ---------- EXECUÇÃO ----------
def start_all():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    run_telegram()

Thread(target=start_all).start()
