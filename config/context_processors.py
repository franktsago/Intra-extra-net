"""Variables de marque (charte graphique LPM) disponibles dans tous les templates."""


def branding(request):
    return {
        "BRAND": {
            "name": "LPM Consulting Group",
            "short": "LPM Consulting",
            # Charte graphique — couleurs issues du logo officiel.
            "blue_light": "#0196F2",
            "blue": "#0073DE",
            "blue_dark": "#0057CA",
            "gradient": "linear-gradient(135deg, #0196F2 0%, #0073DE 50%, #0057CA 100%)",
        }
    }
