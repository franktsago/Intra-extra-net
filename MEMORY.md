# MEMORY — Intranet & Extranet LPM Consulting Group

> Mémoire persistante. Détail dans **`HANDOVER.md`** + **`CLAUDE.md`** (même dossier).
> Langue de travail : **français**.

## ⚠️ Session 2026-06-07 — AUCUN travail de code sur ce projet
La session de cette date portait sur un AUTRE projet (`lpm_consulting`, site vitrine).
Sur CE projet, **rien n'a été modifié** : seul un **`HANDOVER.md` d'onboarding** a été créé
(par exploration du code) + ce `MEMORY.md`. Pas de commit (le projet n'est pas sous git).

## Identité projet
- **Intranet + Extranet LPM Consulting Group** (entreprise camerounaise). Django **6.0.5**, UI **française**, charte bleue.
- Chemin : `C:\Users\Mr T\OneDrive\Desktop\Intra extra lpm`. Venv : **`.venv`** (Python 3.14.5).
- Lancer : `$env:PYTHONUTF8=1` puis `.\.venv\Scripts\python.exe manage.py runserver`.
- ⚠️ **Pas sous git.** DB SQLite (~1,3 Mo), `media/` ~10 Mo (non versionnés).

## Faits clés (issus de l'exploration)
- **16 apps** (`config/settings.py::LOCAL_APPS`) : accounts, employees, documents, communication, conges, dashboard, tasks, disciplinary, notifications, messaging, extranet, business, projects, marketing, hr, api. ⚠️ **`CLAUDE.md` dit « 10 apps » = PÉRIMÉ.**
- `accounts.User` (= AUTH_USER_MODEL) + `role` → cloisonnement intranet/extranet. Utiliser les propriétés `is_internal/is_external/is_rh/...` et les décorateurs `accounts/utils.py` (`@role_required`, `@internal_required`).
- **Droit du travail camerounais** : moteur isolé `conges/cameroon.py` (congés) + `disciplinary/models.py` (sanctions, plafond mise à pied 8 j). Voir `PROCEDURES.md`, `cdc_rest.txt`.
- Génération **PDF** : `business/pdf.py`, `conges/pdf.py`, `disciplinary/pdf.py`, `documents/letterhead.py`, `hr/{contract,mission,attestation}_pdf.py`.
- **DRF** installé (app `api/`) pour Phase 3.
- Config via `.env` (`python-dotenv`) ; SQLite/PostgreSQL (`DB_ENGINE`) ; déconnexion auto (`SESSION_EXPIRE_SECONDS=1800`) ; géo-clôture pointage (`LPM_GEOFENCE_*`) ; coordonnées légales PDF (`LPM_*`).
- **`seed_demo`** (idempotent). Comptes démo (mdp `Lpm@2026`) : `admin`, `r.ndjigue` (RH), `p.bosseck` (resp.), `d.saksak` (employé), `client.kribi` (extranet).
- Tailwind via CDN ; `templates/base.html` (intranet) / `base_extranet.html` (extranet) ; `StyledFormMixin`.

## Gotchas
- ⚠️ **`PYTHONUTF8=1`** obligatoire (Windows) sinon erreurs d'encodage.
- ⚠️ **Pas sous git** → initialiser avant tout travail sérieux (`.gitignore` déjà prêt).
- `CLAUDE.md` partiellement périmé (apps) → se fier au code.
- `Employee` ≠ `User` (OneToOne, parfois absent) ; logique RH pend de `Employee`.

## Next actions
1. (Si reprise) `git init` + commit.
2. **Phase 3** du cahier des charges : stats/reporting, **API REST externe** (DRF prêt), mobile.
3. Prod : `DB_ENGINE=postgresql`, `DJANGO_DEBUG=False`, `.env` complet, `collectstatic`.

## Préférences utilisateur (transverses, verbatim)
- « répond moi en français stp ». Tout le texte visible **en français**. Proposer/preview avant gros changements ; commit/push sur accord.
