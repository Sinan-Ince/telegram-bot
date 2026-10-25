import asyncio
import json
import os
import subprocess
from pathlib import Path

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import Application, CommandHandler, ContextTypes

from config import ALLOWED_USER_ID, BOT_TOKEN, REPOS

# /gun komutunun çalıştırdığı Claude komutu. Bash aracı bilerek yok:
# Claude sadece dosya okuyup yazabilir, git/push yetkisi botta kalır.
CLAUDE_KOMUTU = [
    "claude", "-p", "Günlük adımı tamamla",
    "--allowedTools", "Read,Write,Edit,Glob",
    "--add-dir", str(Path.home() / "Notlar"),
]
CLAUDE_ZAMAN_ASIMI = 15 * 60  # saniye

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


async def gun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return

    repo = REPOS["365"]
    plan_yolu = repo / ".bot" / "plan.json"
    ozet_yolu = repo / ".bot" / "telegram.html"

    if plan_yolu.exists():
        await update.message.reply_text("Onay bekleyen bir gün var. Önce /onayla de.")
        return
    if context.bot_data.get("gun_calisiyor"):
        await update.message.reply_text("Zaten çalışıyor, bitmesini bekle ⏳")
        return

    context.bot_data["gun_calisiyor"] = True
    try:
        # Eski özet kalırsa Claude başarısız olduğunda dünkünü gönderirdik
        ozet_yolu.unlink(missing_ok=True)
        await update.message.reply_text("Başladım ⏳ Claude günü hazırlıyor, 5-10 dakika sürebilir.")

        surec = await asyncio.create_subprocess_exec(
            *CLAUDE_KOMUTU,
            cwd=repo,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(surec.communicate(), timeout=CLAUDE_ZAMAN_ASIMI)
        except asyncio.TimeoutError:
            surec.kill()
            await surec.wait()
            await update.message.reply_text("❌ Claude 15 dakikada bitiremedi, durduruldu.")
            return

        if surec.returncode != 0 or not plan_yolu.exists() or not ozet_yolu.exists():
            son_cikti = (stdout + stderr).decode(errors="replace")[-1500:]
            await update.message.reply_text(
                f"❌ Gün hazırlanamadı (çıkış kodu {surec.returncode}).\n\n{son_cikti}"
            )
            return

        try:
            await update.message.reply_text(ozet_yolu.read_text(), parse_mode="HTML")
        except BadRequest:
            await update.message.reply_text("⚠️ Özet mesaj olarak gönderilemedi, dosya olarak geliyor.")
            await update.message.reply_document(ozet_yolu)

        plan = json.loads(plan_yolu.read_text())
        for ek in plan.get("ekler", []):
            yol = (repo / ek).resolve()
            if yol.is_relative_to(repo.resolve()) and yol.is_file():
                await update.message.reply_document(yol)

        await update.message.reply_text("Okuyup onaylamak için /onayla 👍")
    finally:
        context.bot_data["gun_calisiyor"] = False


app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("durum", durum))
app.add_handler(CommandHandler("onayla", onayla))
app.add_handler(CommandHandler("gun", gun, block=False))
app.run_polling()
