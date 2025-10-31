from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import datetime
import asyncio
import threading
import time
import os
import socket

TOKEN = "7602116178:AAGgcZtmvISxyK8WcCmQVyG9ra8e_SPHWc4"
GROUP_ID = -1002114282154
LINK_PAGAMENTO = "https://mpago.la/1hfmodA"
assinaturas = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Olá! 👋\n\n"
        "Para acessar o grupo exclusivo, realize o pagamento da assinatura mensal (R$18,99):\n"
        f"{LINK_PAGAMENTO}\n\n"
        "Assim que o pagamento for confirmado, você será adicionado automaticamente ao grupo."
    )

async def confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    pago = True  # simulação — depois você coloca integração real
    if pago:
        expiracao = datetime.datetime.now() + datetime.timedelta(days=30)
        assinaturas[user.id] = expiracao
        await context.bot.add_chat_members(GROUP_ID, [user.id])
        await update.message.reply_text("✅ Pagamento confirmado! Você foi adicionado ao grupo.")
    else:
        await update.message.reply_text("❌ Pagamento não encontrado. Tente novamente após pagar o link.")

async def verificar_vencimentos(context: ContextTypes.DEFAULT_TYPE):
    agora = datetime.datetime.now()
    expirados = [uid for uid, exp in assinaturas.items() if exp < agora]
    for uid in expirados:
        try:
            await context.bot.ban_chat_member(GROUP_ID, uid)
            await context.bot.unban_chat_member(GROUP_ID, uid)
        except Exception as e:
            print(f"Erro ao remover {uid}: {e}")
        del assinaturas[uid]

# Configura o bot
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("confirmar", confirmar))
app.job_queue.run_repeating(verificar_vencimentos, interval=86400, first=10)

# 🔹 Fake server para o Render não encerrar o serviço
def manter_vivo():
    port = int(os.environ.get("PORT", 10000))
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("0.0.0.0", port))
    s.listen(1)
    print(f"Fake server ouvindo na porta {port}")
    while True:
        time.sleep(60)

threading.Thread(target=manter_vivo, daemon=True).start()

print("🤖 Bot rodando no Render Free...")
app.run_polling()

