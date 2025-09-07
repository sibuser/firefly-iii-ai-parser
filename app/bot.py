import os
import tempfile
from pathlib import Path
from decimal import Decimal
from dotenv import load_dotenv
import telebot

from app.log import get_logger
from app.processor import process_file

# --------- ENVIRONMENT ---------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

log = get_logger(__name__)

# --------- TELEGRAM HANDLER ---------
@bot.message_handler(content_types=['document', 'photo'])
def handle_file(message):
    user = message.from_user.username or message.from_user.id
    log_ctx = log.bind(user=user)

    try:
        log_ctx.info("received_file")

        file_info = bot.get_file(
            message.document.file_id if message.document else message.photo[-1].file_id
        )
        downloaded = bot.download_file(file_info.file_path)
        suffix = Path(file_info.file_path).suffix or ".jpg"

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(downloaded)
            tmp_path = Path(tmp.name)

        log_ctx.info("file_saved", path=str(tmp_path))
        log_ctx.info("firefly_enabled", enabled=bool(os.getenv("FIREFLY_ENABLED")))
        payload = process_file(tmp_path, send_firefly=os.getenv("FIREFLY_ENABLED"))
        transactions = payload["transactions"]
        count = len(transactions)
        log_ctx.info("receipt_parsed", transactions=count)

        # --------- FORMAT REPLY ---------
        lines = [f"🧾 <b>{payload.get('group_title', 'Receipt')}</b>"]
        total = Decimal("0.00")

        for tx in transactions:
            amount = Decimal(tx["amount"])
            total += amount
            lines.append(
                f"• {tx['description']}: <b>{tx['amount']} {tx['currency_code']}</b> on {tx['date']}"
            )

        lines.append(f"\n✅ Parsed <b>{count}</b> transaction(s).")
        lines.append(f"💰 Total: <b>{total:.2f} SEK</b>")

        reply = "\n".join(lines)
        bot.reply_to(message, reply, parse_mode="HTML")

    except Exception as e:
        log_ctx.error("receipt_parse_failed", error=str(e), exc_info=True)
        bot.reply_to(message, f"❌ Failed: {str(e)}")