import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ["BOT_TOKEN"]
ALLOWED_USER_ID = int(os.environ["ALLOWED_USER_ID"])

REPOS = {
    "365": Path.home() / "365-gun-yazilim",
    "bot": Path.home() / "telegram-bot",
}
