"""Short advice to finish a camo challenge faster, by kind of challenge (general game advice, not map-specific data)."""

import re

from trackcod.readers.common import norm

# (pattern on the normalized challenge, tip). First match wins: specific patterns before general ones.
_TIPS = [
    (r"LONGUE DISTANCE", "Prends une grande carte et tiens une longue ligne de vue ; un viseur grossissant aide."),
    (r"BOUT PORTANT", "Joue sur une petite carte, au contact, dans les bâtiments et les couloirs."),
    (r"SANS RELACHER", "Garde la gâchette appuyée sur des groupes ; le plus gros chargeur possible."),
    (r"SANS RECHARGER", "Monte le plus gros chargeur et joue sur une petite carte pour enchaîner."),
    (r"SANS SUBIR", "Prends les ennemis à revers, par surprise, et finis vite."),
    (r"SANS MOURIR", "Joue prudemment sur une carte moyenne : couvert, recharge et change de place après chaque élimination."),
    (r"DOUBLES? ELIMINATIONS|FOIS 2 JOUEURS", "Va où les ennemis se regroupent : zones à tenir des modes à objectif."),
    (r"FOIS 3 JOUEURS", "Tiens une zone d'objectif avec un gros chargeur : les ennemis y arrivent les uns après les autres."),
    (r"FOIS 10 JOUEURS", "Mode rapide sur une petite carte, et reste toute la partie : 10 éliminations par partie au lanceur."),
    (r"MEME PARTIE","Choisis un mode rapide sur une petite carte, avec beaucoup d'ennemis à portée."),
    (r"TIR AU JUGE", "Petite carte et tir sans viser ; un laser améliore la précision au jugé."),
    (r"VISEE RAPIDE", "Vise et tire aussitôt, sans attendre que la visée se stabilise."),
    (r"DANS LE VISEUR", "Fais simplement tes éliminations en visant : ça avance dans tous les modes."),
    (r"DANS LA TETE|TIRS? DANS LA TETE", "Vise la tête sur une carte moyenne, en tir précis plutôt qu'en rafale."),
    (r"EN UN TIR", "Vise le haut du corps avec une arme qui tue en un tir ; joue posé."),
    (r"EN APPUI", "Pose ton arme sur un rebord ou un mur et tiens un couloir."),
    (r"ALLONGE", "Allonge-toi face à une longue ligne de vue ou à un objectif."),
    (r"ACCROUPI", "Accroupis-toi derrière un couvert qui donne sur un passage."),
    (r"EN MOUVEMENT", "Continue à te déplacer en tirant ; les accessoires de précision en mouvement aident."),
    (r"EN SAUTANT", "Petite carte : saute en passant un angle, l'ennemi est souvent pris de court."),
    (r"SUSPENDU|REBORD", "Accroche-toi à un rebord au-dessus d'un passage et tire de là."),
    (r"PAR DERRIERE", "Contourne par les flancs : en mode à objectif, les ennemis regardent l'objectif."),
    (r"SILENCIEUX", "Monte un silencieux : toutes tes éliminations comptent alors."),
    (r"SECONDES", "Petite carte et mode rapide, là où les ennemis arrivent en groupe."),
    (r"SERIES D.ELIMINATIONS|VEHICULES", "Garde un lanceur pour abattre drones, séries et véhicules ennemis."),
    (r"TIR DIRECT", "Touche la cible directement, sans compter sur l'explosion à côté."),
    (r"CONCENTRE", "Active la concentration en visant avant de tirer."),
    (r"AKIMBO", "Monte l'accessoire Akimbo sur l'arme."),
    (r"ACHEVEMENT LOURD|CORPS A CORPS", "Utilise l'attaque lourde, en arrivant par un angle mort."),
]
_COMPILED = [(re.compile(p), t) for p, t in _TIPS]


def tip(challenge: str | None) -> str | None:
    text = norm(challenge or "")
    return next((t for p, t in _COMPILED if p.search(text)), None)
