import json
import os
import subprocess

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from config import ALLOWED_USER_ID, BOT_TOKEN, REPOS

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
        timeout=60,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    basarili = sonuc.returncode == 0
    return basarili, (sonuc.stdout + sonuc.stderr).strip()


async def durum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return
    if not context.args or context.args[0] not in REPOS:
        await update.message.reply_text("Kullanım: /durum <repo>\nRepolar: " + ", ".join(REPOS))
        return
    _, cikti = git(REPOS[context.args[0]], "status", "-sb")
    await update.message.reply_text(cikti)


async def onayla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return

    repo = REPOS["365"]
    plan_yolu = repo / ".bot" / "plan.json"
    if not plan_yolu.exists():
        await update.message.reply_text("Onay bekleyen gün yok.")
        return

    plan = json.loads(plan_yolu.read_text())

    # Güvenlik: plandaki her dosya repo içinde olmalı ve var olmalı
    for commit in plan["commits"]:
        for dosya in commit["files"]:
            yol = (repo / dosya).resolve()
            if not yol.is_relative_to(repo.resolve()) or not yol.exists():
                await update.message.reply_text(f"❌ Plan hatalı: {dosya}")
                return

    sonuclar = []
    for commit in plan["commits"]:
        for dosya in commit["files"]:
            if dosya.endswith(".sh"):
                (repo / dosya).chmod(0o755)

        git(repo, "add", "--", *commit["files"])
        basarili, cikti = git(repo, "commit", "-m", commit["mesaj"])
        if not basarili:
            await update.message.reply_text(f"❌ Commit başarısız:\n{cikti}")
            return

        basarili, cikti = git(repo, "push")
        if not basarili:
            await update.message.reply_text(f"⚠️ Commit atıldı ama push başarısız:\n{cikti}")
            return

        _, kisa_hash = git(repo, "rev-parse", "--short", "HEAD")
        sonuclar.append(f"{kisa_hash} {commit['mesaj']}")

    plan_yolu.rename(plan_yolu.with_suffix(".onaylandi.json"))
    await update.message.reply_text(
        f"✅ Gün {plan['gun']} push'landı ({len(sonuclar)} push)\n\n" + "\n".join(sonuclar)
    )


app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("durum", durum))
app.add_handler(CommandHandler("onayla", onayla))
app.run_polling()
