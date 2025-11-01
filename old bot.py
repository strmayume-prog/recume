from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import datetime
import asyncio
import threading
import os
import socket
import time

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
    pago = True  # simulação — futuramente via API Mercado Pago
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

# 🔹 Cria um servidor fake ANTES de iniciar o bot
def iniciar_fake_server():
    port = int(os.environ.get("PORT", 10000))
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", port))
    s.listen(1)
    print(f"🌐 Servidor fake ouvindo na porta {port} (Render detectará como ativo)")
    while True:
        conn, addr = s.accept()
        conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nBot ativo no Render!")
        conn.close()

threading.Thread(target=iniciar_fake_server, daemon=True).start()

# 🔹 Agora inicia o bot Telegram normalmente
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("confirmar", confirmar))
app.job_queue.run_repeating(verificar_vencimentos, interval=86400, first=10)

print("🤖 Bot rodando no Render Free com servidor fake ativo...")
app.run_polling()
