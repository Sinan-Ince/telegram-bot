import subprocess
from config import REPOS
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from config import BOT_TOKEN, ALLOWED_USER_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return  # yabancıya cevap verme
    await update.message.reply_text("Bot çalışıyor ✅")

def git(repo_path, *args):
    sonuc = subprocess.run(
        ["git", *args],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return (sonuc.stdout + sonuc.stderr).strip()


async def durum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return
    if not context.args or context.args[0] not in REPOS:
        await update.message.reply_text("Kullanım: /durum <repo>\nRepolar: " + ", ".join(REPOS))
        return
    cikti = git(REPOS[context.args[0]], "status", "-sb")
    await update.message.reply_text(cikti)

app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("durum", durum))
app.run_polling()
