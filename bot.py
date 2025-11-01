from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from fastapi import FastAPI
import requests, os
from requests.auth import HTTPBasicAuth
import asyncio

# Variáveis
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
PAYPAL_SECRET = os.getenv("PAYPAL_SECRET")
PAYPAL_API = "https://api-m.sandbox.paypal.com"

# Telegram bot handler
async def assinar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    res = requests.post(
        f"{PAYPAL_API}/v1/oauth2/token",
        data={"grant_type": "client_credentials"},
        auth=HTTPBasicAuth(PAYPAL_CLIENT_ID, PAYPAL_SECRET)
    )
    access_token = res.json()["access_token"]
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
        headers={"Authorization": f"Bearer {access_token}"}
    )
    order = res.json()
    link_pagamento = next(l["href"] for l in order["links"] if l["rel"] == "approve")
    await update.message.reply_text(f"💳 Pague sua assinatura de R$18,99 aqui:\n{link_pagamento}")

# Cria FastAPI
fastapi_app = FastAPI()
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()
telegram_app.add_handler(CommandHandler("assinar", assinar))

# Roda o bot como tarefa do FastAPI
@fastapi_app.on_event("startup")
async def start_telegram_bot():
    asyncio.create_task(telegram_app.run_polling())

# Rota teste
@fastapi_app.get("/")
async def home():
    return {"status": "ok", "message": "Bot está rodando"}
