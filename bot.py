from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from fastapi import FastAPI, Request
import requests, asyncio, os
from requests.auth import HTTPBasicAuth

# 🔑 Variáveis de ambiente
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
PAYPAL_SECRET = os.getenv("PAYPAL_SECRET")
PAYPAL_API = "https://api-m.sandbox.paypal.com"  # modo teste

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

    await update.message.reply_text(
        f"💳 Pague sua assinatura de R$18,99 aqui:\n{link_pagamento}"
    )

# --- BOT SETUP ---
def start_bot():
    asyncio.set_event_loop(asyncio.new_event_loop())
    loop = asyncio.get_event_loop()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("assinar", assinar))
    loop.run_until_complete(app.initialize())
    loop.create_task(app.start())
    loop.run_forever()

# --- FASTAPI SETUP ---
@fastapi_app.get("/")
def home():
    return {"status": "ok", "message": "Bot está rodando no Render!"}

if __name__ == "__main__":
    # Inicia o bot em uma thread paralela
    threading.Thread(target=start_bot, daemon=True).start()

    # Inicia FastAPI (Render precisa disso para manter o serviço ativo)
    import uvicorn
    uvicorn.run(fastapi_app, host="0.0.0.0", port=10000)
