# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Projet

Intranet + Extranet de **LPM Consulting Group** (entreprise camerounaise). Application web Django 6, rendu serveur, UI **en français**, charte graphique bleue issue du logo (`#0196F2 → #0073DE → #0057CA`). Deux périmètres cloisonnés : **intranet** (employés) et **extranet** (clients/partenaires/fournisseurs/consultants). La logique métier RH encode le **droit du travail camerounais** (voir `PROCEDURES.md`).

## Commandes

venv à la racine (`.venv`, Python 3.14). PowerShell Windows :

```powershell
.\.venv\Scripts\python.exe manage.py runserver           # http://127.0.0.1:8000
.\.venv\Scripts\python.exe manage.py makemigrations
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo            # données de démo (idempotent)
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py test                # tests
.\.venv\Scripts\python.exe manage.py test conges          # tests d'une app
```

Dépendances dans `requirements.txt` (Django, DRF, Pillow, python-dotenv). Config via `.env` (copier `.env.example`). Sous Windows, exporter `PYTHONUTF8=1` pour éviter les erreurs d'encodage console (accents/emoji).

Comptes de démo (mot de passe `Lpm@2026`) : `admin`, `r.ndjigue` (RH), `p.bosseck` (responsable), `d.saksak` (employé), `client.kribi` (extranet).

## Architecture

- **`config/`** — projet Django. `settings.py` lit l'environnement via `python-dotenv` : SQLite par défaut, **PostgreSQL** si `DB_ENGINE=postgresql`. Locale `fr` / `Africa/Douala`. `context_processors.branding` injecte la charte (`BRAND`) dans tous les templates. Durcissement sécurité automatique quand `DEBUG=False` (HSTS, cookies secure, SSL redirect).
- **10 apps métier** correspondant au cahier des charges : `accounts`, `employees`, `documents`, `communication`, `conges`, `dashboard`, `tasks`, `disciplinary`, `notifications`, `extranet`.

### Concepts transverses (à connaître avant d'éditer)

- **Modèle utilisateur** : `accounts.User` (= `AUTH_USER_MODEL`) avec un champ `role` (`accounts.Role`). Le cloisonnement intranet/extranet est porté par le rôle. Propriétés clés : `is_internal`, `is_external`, `is_admin_lpm`, `is_rh`, `is_manager`, `can_validate_leave`. **Utiliser ces propriétés** plutôt que de tester le rôle en dur.
- **Contrôle d'accès** : décorateurs dans `accounts/utils.py` — `@role_required(*roles)`, `@internal_required`. L'admin/superuser passe toujours. Les vues les utilisent systématiquement ; un externe sur une URL intranet reçoit un 403 (comportement voulu).
- **Journalisation** : `accounts.ActivityLog` + `accounts/middleware.py` (déconnexion auto par inactivité, `SESSION_EXPIRE_SECONDS`) + `accounts/signals.py` (login/logout/échec). Helper `log_activity(request, action, desc)`.
- **Notifications** : `notifications.notify(recipient, title, message, level, url)` crée une notif in-app. Le badge non-lu est exposé partout par `notifications.context_processors`.
- **Profil RH** : `employees.Employee` est en **OneToOne** avec `User`. Les soldes de congés, l'ancienneté, etc. dépendent de l'`Employee`, pas du `User`. Un `User` interne peut ne pas avoir d'`Employee` (les vues le gèrent).

### Logique métier camerounaise (le cœur du projet)

- **`conges/cameroon.py`** — moteur légal **isolé et documenté** : constantes (1,5 j/mois, +2 j/5 ans, maternité 14 sem.), `compter_jours_ouvrables()` (exclut dimanches + fériés fixes + `Holiday`), `droit_annuel()`. Toute évolution réglementaire se fait ici.
- **`conges/models.py`** — `solde_conges(employee)` = droits acquis + ajustements − congés approuvés. `LeaveRequest.save()` recalcule `days_count` automatiquement.
- **Workflow congés** (`conges/views.py`) : `SUBMITTED → MANAGER_APPROVED → APPROVED` (ou `REJECTED`). `_can_decide()` détermine qui peut agir à chaque étape (responsable de l'employé puis RH). Chaque transition notifie les parties.
- **`disciplinary/models.py`** — échelle de sanctions [Art. 30] ; `clean()` plafonne la mise à pied à 8 jours ; `requires_hearing` impose l'entretien préalable au-delà de l'avertissement.

## Templates & UI

- `templates/base.html` — shell **intranet** (sidebar + topbar, nav conditionnée par rôle). `templates/base_extranet.html` — shell **extranet** simplifié. Les templates extranet choisissent le shell via `{% extends user.is_external|yesno:"base_extranet.html,base.html" %}`.
- **Tailwind via CDN** (pas d'étape de build) + couleur `lpm` configurée inline. Composants réutilisables : `includes/form.html` (rendu générique d'un form), `includes/pagination.html`.
- Les formulaires héritent de `accounts.forms.StyledFormMixin` qui applique les classes CSS aux widgets — réutiliser ce mixin pour tout nouveau form.

## Conventions

- **Tout le texte visible est en français** (labels de modèles, messages, UI).
- Nouveau modèle → `makemigrations` + `migrate` + enregistrement dans `admin.py` de l'app.
- Données de démo : étendre `accounts/management/commands/seed_demo.py` (idempotent via `get_or_create`).
- Ne pas committer `.env`, `db.sqlite3`, `media/`, `.venv/` (voir `.gitignore`).

## Phases du cahier des charges

- **Phase 1 (fait)** : auth, tableau de bord, employés, documents, actualités.
- **Phase 2 (fait)** : congés, messagerie (extranet), notifications, calendrier.
- **Phase 3 (à venir)** : statistiques avancées, reporting, application mobile, API REST externe (DRF est déjà installé et configuré dans `settings.REST_FRAMEWORK`).
