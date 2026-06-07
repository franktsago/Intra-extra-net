# HANDOVER — Intranet & Extranet LPM Consulting Group

> ⚠️ **Nature de ce document** : ceci est un **handover d'ONBOARDING** établi par
> **exploration du code**, PAS un journal de travail. **Aucune modification n'a été
> faite sur ce projet durant la session** où ce fichier a été créé (la session portait
> sur un AUTRE projet, `lpm_consulting`, un site vitrine séparé). Les sections
> « Journal », « Bugs corrigés », « Validation » sont donc marquées **n/a (pas de
> travail de session)** ; le reste documente le projet pour qu'un agent puisse le reprendre.
> Source de vérité complémentaire : **`CLAUDE.md`**, **`README.md`**, **`PROCEDURES.md`**,
> **`cdc_rest.txt`** à la racine.

---

## 1. TL;DR & état actuel

- **Projet** : Intranet + Extranet de **LPM Consulting Group** (entreprise camerounaise). Django 6, rendu serveur, UI **française**, charte bleue.
- **Chemin** : `C:\Users\Mr T\OneDrive\Desktop\Intra extra lpm`.
- **Git** : ⚠️ **PAS sous git** (aucun dépôt initialisé). Pas de branche, pas de remote.
- **DB** : SQLite `db.sqlite3` (~1,3 Mo) ; `media/` ~10 Mo. **Non versionnés** (et pas encore versionnables, faute de dépôt).
- **Prochaine action probable** : aucune demande en cours sur ce projet. Si reprise : initialiser git (cf. §11), puis poursuivre la **Phase 3** du cahier des charges (stats/reporting, API REST externe) — voir `CLAUDE.md`.

---

## 2. Contexte & objectif

Application web interne de LPM Consulting Group, deux périmètres **cloisonnés par rôle** :
- **Intranet** : employés (RH, congés, documents, tâches, disciplinaire, actualités, messagerie, projets, marketing, business…).
- **Extranet** : clients/partenaires/fournisseurs/consultants (périmètre restreint).

La logique métier RH encode le **droit du travail camerounais** (congés, sanctions). Voir `PROCEDURES.md` (procédures métier) et `cdc_rest.txt` (cahier des charges / specs REST).

---

## 3. Environnement & accès

- **OS** : Windows. Shell : **PowerShell**.
- **Python** : **3.14.5**, venv = **`.venv`** (racine). Binaire : `C:\Users\Mr T\OneDrive\Desktop\Intra extra lpm\.venv\Scripts\python.exe`.
- **Dépendances** (`requirements.txt`) : `Django==6.0.5`, `djangorestframework==3.17.1`, `pillow==12.2.0`, `python-dotenv==1.2.2` (+ asgiref, sqlparse, tzdata).
- **Config** : via `.env` (copier `.env.example`). `settings.py` lit l'environnement avec `python-dotenv`.
- **⚠️ Piège encodage** : sous Windows, **exporter `PYTHONUTF8=1`** (`$env:PYTHONUTF8=1`) pour éviter les erreurs console sur accents/emoji.
- **Base** : SQLite par défaut ; **PostgreSQL** si `DB_ENGINE=postgresql` (vars `DB_NAME/USER/PASSWORD/HOST/PORT`).
- **Locale** : `fr` / `Africa/Douala`.
- **Lancer** :
  ```powershell
  Set-Location "C:\Users\Mr T\OneDrive\Desktop\Intra extra lpm"
  $env:PYTHONUTF8=1
  .\.venv\Scripts\python.exe manage.py migrate
  .\.venv\Scripts\python.exe manage.py seed_demo      # données de démo (idempotent)
  .\.venv\Scripts\python.exe manage.py runserver      # http://127.0.0.1:8000
  ```
- **Comptes de démo** (mot de passe **`Lpm@2026`**) : `admin`, `r.ndjigue` (RH), `p.bosseck` (responsable), `d.saksak` (employé), `client.kribi` (extranet).
- **Coordonnées légales** (papier en-tête PDF) + **géo-clôture pointage** configurés dans `.env` (voir `.env.example` : `LPM_*`, `LPM_GEOFENCE_*`, `LPM_OFFICE_LAT/LNG/RADIUS`).

---

## 4. Journal chronologique

**n/a — aucun travail effectué sur ce projet durant la session.** (Document d'onboarding par exploration.)

---

## 5. Fichiers touchés (cette session)

**n/a — aucun fichier modifié sur ce projet.** Pour la structure existante, voir §6 et `CLAUDE.md`.

Fichiers de référence à la racine : `CLAUDE.md`, `README.md`, `PROCEDURES.md`, `cdc_rest.txt`, `requirements.txt`, `.env.example`, `manage.py`.

Volontairement **non versionnables / non committables** (cf. `.gitignore`) : `.env`, `db.sqlite3`, `media/` (~10 Mo), `.venv/`.

---

## 6. Architecture & décisions techniques

- **`config/`** — projet Django. `settings.py` lit l'env via dotenv ; SQLite/PostgreSQL ; durcissement sécurité auto si `DEBUG=False` (HSTS, cookies secure, SSL redirect). `config/context_processors.py::branding` injecte la charte `BRAND` dans tous les templates.
- **16 apps locales** (`config/settings.py::LOCAL_APPS`) :
  `accounts`, `employees`, `documents`, `communication`, `conges`, `dashboard`, `tasks`, `disciplinary`, `notifications`, `messaging`, `extranet`, `business`, `projects`, `marketing`, `hr`, `api`.
  > ⚠️ **`CLAUDE.md` dit « 10 apps » — c'est STALE** : il y en a **16** (le projet a grossi : `business`, `projects`, `marketing`, `hr`, `api`, `messaging` se sont ajoutées). Se fier au code/`settings.py`.
- **Modèle utilisateur** : `accounts.User` (= `AUTH_USER_MODEL`) avec champ `role` (`accounts.Role`). Cloisonnement intranet/extranet **porté par le rôle**. Propriétés à utiliser (ne PAS tester le rôle en dur) : `is_internal`, `is_external`, `is_admin_lpm`, `is_rh`, `is_manager`, `can_validate_leave`.
- **Contrôle d'accès** : décorateurs `accounts/utils.py` — `@role_required(*roles)`, `@internal_required`. Admin/superuser passe toujours. Un externe sur une URL intranet → **403** (voulu).
- **Journalisation** : `accounts.ActivityLog` + `accounts/middleware.py` (déconnexion auto inactivité, `SESSION_EXPIRE_SECONDS`, défaut 1800 s) + `accounts/signals.py`. Helper `log_activity(request, action, desc)`.
- **Notifications** : `notifications.notify(recipient, title, message, level, url)`. Badge non-lu via `notifications.context_processors`.
- **Profil RH** : `employees.Employee` en **OneToOne** avec `User` (soldes congés, ancienneté dépendent de l'`Employee`, pas du `User` ; un interne peut ne pas avoir d'`Employee`).
- **Génération PDF** (modules dédiés) : `business/pdf.py`, `conges/pdf.py`, `disciplinary/pdf.py`, `documents/letterhead.py`, `hr/contract_pdf.py`, `hr/mission_pdf.py`, `hr/attestation_pdf.py`.
- **API REST** : app `api/` (DRF installé/configuré, `settings.REST_FRAMEWORK`) — destinée à la Phase 3 / mobile.
- **UI** : `templates/base.html` (shell intranet : sidebar + topbar, nav par rôle) ; `templates/base_extranet.html` (shell extranet). Choix du shell : `{% extends user.is_external|yesno:"base_extranet.html,base.html" %}`. **Tailwind via CDN** (pas de build). Composants : `includes/form.html`, `includes/pagination.html`. Forms héritent de `accounts.forms.StyledFormMixin`.

### Logique métier camerounaise (cœur du projet)
- **`conges/cameroon.py`** — moteur légal **isolé** : 1,5 j/mois, +2 j/5 ans, maternité 14 sem., `compter_jours_ouvrables()` (exclut dimanches + fériés + `Holiday`), `droit_annuel()`. **Toute évolution réglementaire se fait ici.**
- **`conges/models.py`** — `solde_conges(employee)` = droits acquis + ajustements − congés approuvés. `LeaveRequest.save()` recalcule `days_count`.
- **Workflow congés** (`conges/views.py`) : `SUBMITTED → MANAGER_APPROVED → APPROVED` (ou `REJECTED`). `_can_decide()` = qui agit à chaque étape (responsable puis RH). Chaque transition notifie.
- **`disciplinary/models.py`** — échelle de sanctions [Art. 30] ; `clean()` plafonne la mise à pied à 8 jours ; `requires_hearing` impose l'entretien préalable au-delà de l'avertissement.

---

## 7. Connaissances domaine & gotchas

- ⚠️ **Projet PAS sous git** — toute reprise sérieuse devrait commencer par `git init` (+ `.gitignore` déjà présent, qui exclut `.env`/`db.sqlite3`/`media/`/`.venv/`).
- ⚠️ **`PYTHONUTF8=1` obligatoire** sous Windows sinon erreurs d'encodage console.
- ⚠️ **`CLAUDE.md` partiellement périmé** (10 vs 16 apps) — vérifier dans `settings.py`.
- **Cloisonnement par rôle** : toujours passer par les propriétés `is_internal/is_external/...` et les décorateurs `accounts/utils.py`.
- **Congés** : ne jamais coder la logique légale ailleurs que dans `conges/cameroon.py`.
- **`Employee` ≠ `User`** : les données RH pendent de `Employee` (OneToOne, parfois absent).
- **Pointage** : géo-clôture GPS (`LPM_GEOFENCE_*`) + restriction IP optionnelle (`LPM_IP_RESTRICTION`, `LPM_OFFICE_IPS`).
- **`seed_demo`** est idempotent (`get_or_create`) — l'étendre pour de nouvelles données de démo.
- Mêmes pièges génériques que les autres projets LPM : Windows/PowerShell, venv à chemin avec espaces, OneDrive.

---

## 8. Commandes exactes

```powershell
Set-Location "C:\Users\Mr T\OneDrive\Desktop\Intra extra lpm"
$env:PYTHONUTF8=1
.\.venv\Scripts\python.exe manage.py runserver
.\.venv\Scripts\python.exe manage.py makemigrations
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py test            # tous les tests
.\.venv\Scripts\python.exe manage.py test conges      # tests d'une app
```

---

## 9. Bugs

**n/a (pas de travail de session).** Aucun bug recherché ni corrigé ici. (Le projet a une suite de tests : `manage.py test`.)

---

## 10. Validation & preuves

**n/a (pas de travail de session).** Rien n'a été lancé/testé sur ce projet ; infos issues de la lecture de `CLAUDE.md`/`settings.py`/`requirements.txt`/`.env.example` et de l'arborescence.

---

## 11. Items ouverts / next actions

1. **Mettre sous git** si ce n'est pas fait ailleurs (`git init -b main`, commit, éventuellement push GitHub). `.gitignore` est déjà prêt.
2. **Phase 3 du cahier des charges** (cf. `CLAUDE.md`) : statistiques avancées, reporting, **API REST externe** (DRF prêt), appli mobile.
3. **Production** : passer `DB_ENGINE=postgresql`, `DJANGO_DEBUG=False`, renseigner `.env` (clé, hosts, SMTP, coordonnées légales), `collectstatic`, servir media/static.
4. Lire `PROCEDURES.md` et `cdc_rest.txt` pour les règles métier et specs API.

---

## 12. Coordination & personnes

- Propriétaire : LPM Consulting Group (même client que les autres projets `lpm_consulting`, `rise_football`). Compte GitHub probable : `franktsago`.
- Coordonnées légales dans `.env.example` : `LPM_EMAIL=lucprosper.moni@lpmconsultinggroup.com`, tél `+237 233 410 029`, RCCM `RC/DLA/2014/B/4112`, NIU `M101412172020J`.

---

## 13. Références externes

- `CLAUDE.md`, `README.md`, `PROCEDURES.md`, `cdc_rest.txt` (racine du projet).
- Domaine pressenti : `intranet.lpmconsulting.cm` (cf. `DJANGO_CSRF_TRUSTED_ORIGINS` dans `.env.example`).
- Projets frères : `lpm_consulting` (site vitrine, voir son propre `HANDOVER.md`), `rise_football` (voir son `HANDOVER.md`).

---

## 14. Mes préférences & instructions (VERBATIM)

Aucune instruction spécifique à CE projet durant la session. Préférences **transverses** du même utilisateur (établies sur `lpm_consulting`) :
- « **répond moi en français stp** » → réponses en français.
- Toujours **proposer/preview avant** gros changements ; **commit + push** seulement sur accord (qu'il donne facilement : « oui », « VAS-y »).
- Tout le **texte visible en français**.

---

## 15. Glossaire

- **Intranet / Extranet** : périmètres internes (employés) / externes (clients-partenaires), cloisonnés par `role`.
- **conges** : module congés (droit camerounais).
- **disciplinary** : sanctions disciplinaires [Art. 30 du code du travail].
- **pointage** : présence au bureau (géo-clôture GPS + IP).
- **branding / BRAND** : charte injectée dans les templates par `config/context_processors.py`.
- **seed_demo** : commande de données de démo.
- **StyledFormMixin** : mixin qui stylise les widgets de formulaire.

---

## 16. Comment reprendre

1. `Set-Location "C:\Users\Mr T\OneDrive\Desktop\Intra extra lpm"`, `$env:PYTHONUTF8=1`, copier `.env.example`→`.env`, `migrate`, `seed_demo`, `runserver`.
2. Lire `CLAUDE.md` (architecture), `PROCEDURES.md` (métier), `cdc_rest.txt` (specs).
3. **Phrase à dire à l'utilisateur** : « **lis HANDOVER.md de l'intranet et continue** ».

---

### Note d'honnêteté
Ce handover reflète **l'état observé du code** (exploration + docs existantes), pas un travail réalisé. Pour des détails non couverts ici (modèles précis, vues, URLs par app), lire directement les fichiers de l'app concernée — chaque app suit le même squelette (`models.py`, `views.py`, `forms.py`, `urls.py`, `admin.py`, `migrations/`).
