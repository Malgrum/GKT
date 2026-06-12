import os
from dotenv import load_dotenv

load_dotenv()

from gkt_bot.commands import register_bot_features
from gkt_bot.keep_alive import keep_alive
from gkt_bot.state import bot


def main() -> None:
    register_bot_features()
    keep_alive()

    token = os.getenv("DISCORD_TOKEN") or os.getenv("TON_TOKEN_ICI")
    if not token:
        raise RuntimeError("Token Discord introuvable. Définis DISCORD_TOKEN (ou TON_TOKEN_ICI).")

    bot.run(token)


if __name__ == "__main__":
    main()