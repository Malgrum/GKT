from __future__ import annotations

import re
from datetime import datetime, timedelta


def extract_user_id_from_entry(entry: str) -> str | None:
    match = re.search(r"<@!?(\d+)>", entry)
    return match.group(1) if match else None


def user_already_registered(tournoi: dict, user_id: str) -> bool:
    all_participants = tournoi.get("inscrits", []) + tournoi.get("attente", [])
    return any(extract_user_id_from_entry(entry) == user_id for entry in all_participants)


def count_valid_inscriptions(inscrits: list[str]) -> int:
    """Compte les inscriptions valides, en excluant les 'Pas Dispo'."""
    return sum(1 for entry in inscrits if "(Pas Dispo)" not in entry)


def parse_event_datetime(date_value: str | None, heure_value: str | None = None) -> datetime | None:
    if not date_value:
        return None

    text = str(date_value).strip()
    if not text:
        return None

    hour = 0
    minute = 0

    time_match = re.search(r"(\d{1,2})\s*(?:h|:)(\d{1,2})?", text, flags=re.IGNORECASE)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or 0)
        text = text[:time_match.start()] + text[time_match.end():]
    elif heure_value:
        heure_match = re.search(r"(\d{1,2})\s*(?:h|:)(\d{1,2})?", str(heure_value), flags=re.IGNORECASE)
        if heure_match:
            hour = int(heure_match.group(1))
            minute = int(heure_match.group(2) or 0)

    parts = re.findall(r"\d+", text)
    if len(parts) < 2:
        return None

    day = int(parts[0])
    month = int(parts[1])
    year = int(parts[2]) if len(parts) >= 3 else datetime.now().year
    if year < 100:
        year += 2000

    try:
        return datetime(year, month, day, hour, minute)
    except ValueError:
        return None


def event_has_explicit_time(date_value: str | None, heure_value: str | None = None) -> bool:
    return bool(
        re.search(r"(\d{1,2})\s*(?:h|:)(\d{1,2})?", str(date_value), flags=re.IGNORECASE)
        or (
            heure_value
            and re.search(r"(\d{1,2})\s*(?:h|:)(\d{1,2})?", str(heure_value), flags=re.IGNORECASE)
        )
    )


def prune_old_events(tournois: dict[int, dict], save_callback=None) -> None:
    threshold = datetime.now() - timedelta(days=30)
    removed_ids: list[int] = []

    for message_id, tournoi in list(tournois.items()):
        event_dt = parse_event_datetime(tournoi.get("date"), tournoi.get("heure"))
        if event_dt and event_dt < threshold:
            del tournois[message_id]
            removed_ids.append(message_id)

    if removed_ids:
        print(f"🧹 {len(removed_ids)} événement(s) supprimé(s), passés depuis plus de 30 jours.")
        if save_callback is not None:
            save_callback()


def build_registered_mentions(tournoi: dict) -> str:
    mentions = []
    seen = set()

    for entry in tournoi.get("inscrits", []):
        user_id = extract_user_id_from_entry(entry)
        if user_id and user_id not in seen:
            seen.add(user_id)
            mentions.append(f"<@{user_id}>")

    return " ".join(mentions)


def generer_tableau_warhammer(tournoi: dict) -> str:
    jeux = {
        "40K": {"emoji": "🚀", "joueurs": []},
        "AOS": {"emoji": "🛡️", "joueurs": []},
        "KT": {"emoji": "🎯", "joueurs": []},
    }

    for entry in tournoi.get("inscrits", []):
        if "(" in entry and ")" in entry:
            mention = entry.split("(")[0].strip()
            jeux_choisis = entry.split("(")[1].split(")")[0].split(", ")
            for jeu in jeux_choisis:
                if jeu in jeux:
                    jeux[jeu]["joueurs"].append(mention)

    tableau = ""
    for jeu_code, info in jeux.items():
        if info["joueurs"]:
            plural = "s" if len(info["joueurs"]) > 1 else ""
            tableau += f"\n{info['emoji']} **{jeu_code}** ({len(info['joueurs'])} joueur{plural})\n"
            tableau += "\n".join([f"• {joueur}" for joueur in info["joueurs"]])
            tableau += "\n"

    return tableau if tableau else "Aucun joueur inscrit"


def generer_tableau_ff14(tournoi: dict) -> str:
    roles = {
        "DPS": {"emoji": "⚔️", "joueurs": []},
        "HEALER": {"emoji": "💉", "joueurs": []},
        "TANK": {"emoji": "🛡️", "joueurs": []},
        "Tout Role": {"emoji": "🎮", "joueurs": []},
        "BENCH": {"emoji": "🪑", "joueurs": []},
        "Pas Dispo": {"emoji": "❌", "joueurs": []},
    }

    for entry in tournoi.get("inscrits", []):
        if "(" in entry and ")" in entry:
            mention = entry.split("(")[0].strip()
            role = entry.split("(")[1].split(")")[0].strip()
            if role in roles:
                roles[role]["joueurs"].append(mention)

    tableau = ""
    for role_code, info in roles.items():
        if info["joueurs"]:
            plural = "s" if len(info["joueurs"]) > 1 else ""
            tableau += f"\n{info['emoji']} **{role_code}** ({len(info['joueurs'])} joueur{plural})\n"
            tableau += "\n".join([f"• {joueur}" for joueur in info["joueurs"]])
            tableau += "\n"

    return tableau if tableau else "Aucun joueur inscrit"
