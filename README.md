<div align="center">

# 🔵 Intranet & Extranet — LPM Consulting Group

**Plateforme collaborative d'entreprise** · Django 6 · UI française · charte LPM

</div>

---

## Présentation

Plateforme web professionnelle, sécurisée et responsive pour **LPM Consulting Group**, conforme au cahier des charges et au **droit du travail camerounais**. Elle réunit :

- 🏠 **Intranet** — espace de travail des employés : actualités, documents, congés, tâches, calendrier, annuaire.
- 🤝 **Extranet** — portail sécurisé pour les clients et partenaires : suivi de projets, partage de fichiers, messagerie.

## Fonctionnalités

| Module | Description |
|--------|-------------|
| 🔐 **Comptes & sécurité** | Connexion, récupération de mot de passe, rôles & permissions, déconnexion auto par inactivité, **journal d'activité**. |
| 📊 **Tableau de bord** | Vue d'ensemble adaptée au rôle (actualités, solde de congés, tâches, agenda, validations en attente). |
| 👥 **Employés** | Annuaire, fiches détaillées, départements, **organigramme**. |
| 📁 **Documents** | Dépôt, catégories, recherche, **contrôle d'accès par visibilité**, archivage, compteur de téléchargements. |
| 📰 **Communication** | Actualités, bannière épinglée, commentaires, **calendrier & événements**. |
| 🌴 **Congés** | Demande, **workflow responsable → RH**, calcul automatique en jours ouvrables, soldes — *conforme au Code du Travail camerounais*. |
| ✅ **Tâches** | Tableau (À faire / En cours / Terminé), priorités, échéances. |
| ⚖️ **Discipline** | Dossiers disciplinaires, entretien préalable, sanctions encadrées par la loi. |
| 🔔 **Notifications** | Notifications in-app temps réel (badge). |
| 🤝 **Extranet** | Espaces projets clients, partage de fichiers bidirectionnel, messagerie. |

## Stack technique

`Python 3` · `Django 6` · `Django REST Framework` · `PostgreSQL` (prod) / `SQLite` (dev) · `Tailwind CSS` · `Nginx + Gunicorn` (déploiement).

## Démarrage rapide

```powershell
# 1. Environnement
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. Configuration
copy .env.example .env        # puis éditer .env

# 3. Base de données + données de démo
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo

# 4. Lancer
.\.venv\Scripts\python.exe manage.py runserver
```

Ouvrir **http://127.0.0.1:8000**.

### Comptes de démonstration (mot de passe : `Lpm@2026`)

| Identifiant | Rôle |
|-------------|------|
| `admin` | Administrateur principal |
| `r.ndjigue` | Responsable RH |
| `p.bosseck` | Responsable de service |
| `d.saksak` | Employé |
| `client.kribi` | Client (extranet) |

## Sécurité

HTTPS forcé en production, protection CSRF/XSS (Django), permissions par rôle, cloisonnement intranet/extranet, mots de passe chiffrés, journalisation des connexions, expiration de session, en-têtes HSTS/secure cookies activés automatiquement quand `DEBUG=False`.

## Documentation

- 📘 [`PROCEDURES.md`](PROCEDURES.md) — procédures RH & administratives **en vigueur au Cameroun** (Code du Travail, CNPS).
- 🤖 [`CLAUDE.md`](CLAUDE.md) — architecture technique détaillée.

## Déploiement (production)

1. `.env` : `DJANGO_DEBUG=False`, `DJANGO_SECRET_KEY` aléatoire, `DJANGO_ALLOWED_HOSTS`, `DB_ENGINE=postgresql` + identifiants, SMTP.
2. `python manage.py collectstatic`
3. **Gunicorn** (`gunicorn config.wsgi`) derrière **Nginx** (TLS) sur un **VPS Linux**.
4. Sauvegardes automatiques de la base et des médias.

---

<div align="center"><sub>© LPM Consulting Group — Douala, Cameroun</sub></div>
