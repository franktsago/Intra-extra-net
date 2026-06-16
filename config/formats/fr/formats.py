"""Formats français personnalisés pour LPM.

Objectif : rendre les champs HTML5 ``<input type="date">`` et
``<input type="datetime-local">`` compatibles avec la locale française.

Un input date HTML5 n'accepte QUE la valeur ISO ``AAAA-MM-JJ`` ; or Django
affiche par défaut le 1er format de ``DATE_INPUT_FORMATS`` (``JJ/MM/AAAA`` en
français), que le navigateur rejette → le champ apparaît vide à l'édition.
En plaçant le format ISO en tête, la valeur enregistrée se réaffiche bien,
tout en continuant d'accepter la saisie au format français.
"""

# Affichage (lecture seule) — on conserve l'usage français.
DATE_FORMAT = "j F Y"
DATETIME_FORMAT = "j F Y H:i"
TIME_FORMAT = "H:i"
SHORT_DATE_FORMAT = "d/m/Y"
SHORT_DATETIME_FORMAT = "d/m/Y H:i"
FIRST_DAY_OF_WEEK = 1  # lundi

# Saisie — ISO d'abord (pour les inputs HTML5), puis les formats français usuels.
DATE_INPUT_FORMATS = [
    "%Y-%m-%d",   # 2026-01-15 (input type=date HTML5)
    "%d/%m/%Y",   # 15/01/2026
    "%d/%m/%y",   # 15/01/26
    "%d.%m.%Y",   # 15.01.2026
    "%d.%m.%y",   # 15.01.26
]
DATETIME_INPUT_FORMATS = [
    "%Y-%m-%dT%H:%M",     # 2026-01-15T08:30 (input type=datetime-local)
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
]
TIME_INPUT_FORMATS = [
    "%H:%M",
    "%H:%M:%S",
]
