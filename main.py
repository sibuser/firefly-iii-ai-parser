import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv
from app.log import get_logger

from app.processor import process_file
from app.bot import bot

log = get_logger(__name__)

load_dotenv()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser()
        parser.add_argument("input", help="Image or PDF path")
        parser.add_argument("--firefly", action="store_true", help="Send to Firefly III")
        args = parser.parse_args()

        p = Path(args.input)
        if not p.exists():
            print("File not found.")
            sys.exit(1)

        payload = process_file(p, send_firefly=args.firefly)
    else:
        log.info("[bot] Starting Telegram polling...")
        bot.infinity_polling()