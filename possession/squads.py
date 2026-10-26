"""Both clubs' 2024-25 first-team squads, as commentators say the names.

Public, season-level information (Wikipedia's 2024-25 season pages, read 2026-10-26), not data
about our match: every player registered during the season is here, whether or not he played.
It lets local code tell which team a commentary line is about ("Pedri finds Lamine Yamal" is
Barcelona) without anyone labelling the match.

Only names that point to exactly one team are used: "Iñigo" is on both sides (Iñigo Martínez;
Iñigo Lekue, Iñigo Ruiz de Galarreta), so is "García" and "Unai", and "Williams" is two Athletic
players, which is still one team.
"""

import re
import unicodedata

HOME, AWAY = 0, 1

TEAM_WORDS = {
    HOME: ["barcelona", "barca", "blaugrana", "catalans", "catalan side", "flick's side"],
    AWAY: ["athletic", "bilbao", "athletic club", "basques", "basque side", "los leones",
           "valverde's side"],
}

PLAYERS = {
    HOME: ["Marc-André ter Stegen", "Pau Cubarsí", "Alejandro Balde", "Ronald Araújo",
           "Iñigo Martínez", "Gavi", "Ferran Torres", "Pedri", "Robert Lewandowski", "Ansu Fati",
           "Raphinha", "Iñaki Peña", "Pablo Torre", "Andreas Christensen", "Fermín López",
           "Marc Casadó", "Pau Víctor", "Lamine Yamal", "Dani Olmo", "Frenkie de Jong",
           "Jules Koundé", "Eric García", "Wojciech Szczęsny", "Sergiño Dest", "Marc Guiu",
           "Oriol Romeu", "Julián Araujo", "Ilkay Gündoğan", "Mikayil Faye", "Vitor Roque",
           "Clément Lenglet", "Álex Valle", "Unai Hernández", "Sergi Roberto"],
    AWAY: ["Unai Simón", "Andoni Gorosabel", "Dani Vivian", "Aitor Paredes", "Yeray Álvarez",
           "Mikel Vesga", "Álex Berenguer", "Oihan Sancet", "Iñaki Williams", "Nico Williams",
           "Álvaro Djaló", "Gorka Guruzeta", "Julen Agirrezabala", "Unai Nuñez", "Iñigo Lekue",
           "Iñigo Ruiz de Galarreta", "Yuri Berchiche", "Óscar de Marcos", "Unai Gómez",
           "Maroan Sannadi", "Mikel Jauregizar", "Beñat Prados", "Peio Canales", "Adama Boiro",
           "Raúl García", "Iker Muniain", "Jon Morcillo", "Dani García", "Unai Vencedor",
           "Asier Villalibre", "Urko Izeta", "Hugo Rincón", "Ander Herrera", "Nico Serrano"],
}

# Short forms commentators use that the full names do not produce.
EXTRA = {HOME: ["ter stegen", "lewy", "yamal", "lamine", "de jong", "frenkie", "kounde",
                "cubarsi", "casado", "fermin", "olmo", "araujo", "szczesny"],
         AWAY: ["simon", "sancet", "guruzeta", "vivian", "yuri", "de marcos", "prados",
                "berenguer", "djalo", "vesga", "jauregizar", "galarreta", "williams"]}


def fold(text):
    """Lower case, accents removed: what the matching compares."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def _name_tokens():
    """Every name and name part, mapped to the one team it belongs to (shared ones dropped)."""
    owners = {}
    for team, names in PLAYERS.items():
        for name in names:
            folded = fold(name)
            for token in [folded] + folded.replace("-", " ").split():
                if len(token) >= 4:
                    owners.setdefault(token, set()).add(team)
    for team, words in EXTRA.items():
        for word in words:
            owners.setdefault(word, set()).add(team)
    return {token: teams.pop() for token, teams in owners.items() if len(teams) == 1}


NAME_TEAM = _name_tokens()
_TEAM_PATTERNS = {team: re.compile(r"\b(" + "|".join(map(re.escape, words)) + r")\b")
                  for team, words in TEAM_WORDS.items()}
_NAME_PATTERN = re.compile(r"\b(" + "|".join(sorted(map(re.escape, NAME_TEAM), key=len,
                                                       reverse=True)) + r")\b")


def teams_mentioned(text):
    """{team: count} of team words and one-team player names in a line of commentary."""
    folded = fold(text)
    counts = {HOME: 0, AWAY: 0}
    for team, pattern in _TEAM_PATTERNS.items():
        counts[team] += len(pattern.findall(folded))
    for match in _NAME_PATTERN.findall(folded):
        counts[NAME_TEAM[match]] += 1
    return counts
