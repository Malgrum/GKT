from __future__ import annotations

import json
import os

from .formatting import prune_old_events
from .state import TOURNOIS_FILE, tournois


def charger_tournois() -> None:
    if not os.path.exists(TOURNOIS_FILE):
        return

    try:
        if os.path.getsize(TOURNOIS_FILE) == 0:
            tournois.clear()
            print("ℹ️ Fichier tournois vide, initialisation d'un état propre.")
            return

        with open(TOURNOIS_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
            tournois.clear()
            tournois.update({int(key): value for key, value in data.items()})
            prune_old_events(tournois, sauvegarder_tournois)
            print(f"✅ {len(tournois)} tournois chargés.")
    except Exception as error:
        tournois.clear()
        print(f"❌ Erreur chargement: {error}")


def sauvegarder_tournois() -> None:
    try:
        data = {str(key): value for key, value in tournois.items()}
        with open(TOURNOIS_FILE, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
    except Exception as error:
        print(f"❌ Erreur sauvegarde: {error}")
