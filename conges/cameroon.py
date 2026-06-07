"""Moteur de calcul des congés selon le droit du travail camerounais.

Références légales :
  • Loi n° 92/007 du 14 août 1992 portant Code du Travail de la République du Cameroun.
  • Décret n° 75/28 du 10 janvier 1975 (modalités des congés payés).

Règles principales encodées ici
--------------------------------
1.  CONGÉ ANNUEL PAYÉ (art. 89) :
    Droit acquis à raison de **1,5 jour ouvrable par mois de service effectif**,
    soit **18 jours ouvrables** pour une année complète de travail.

2.  MAJORATION POUR ANCIENNETÉ (art. 90) :
    + **2 jours ouvrables** par période entière de **5 ans** d'ancienneté.

3.  MAJORATION POUR MÈRES SALARIÉES (art. 90) :
    + **2 jours ouvrables** par enfant à charge de **moins de 6 ans**
    (au-delà du premier enfant pour les mères de plus de 21 ans ; dès le premier
    enfant pour les mères de moins de 21 ans).

4.  JEUNES TRAVAILLEURS (moins de 18 ans) :
    droit porté à **2,5 jours ouvrables par mois**.

5.  CONGÉ DE MATERNITÉ (art. 84) :
    **14 semaines** (98 jours), dont 4 avant et 10 après l'accouchement,
    prolongeable de 6 semaines en cas de maladie dûment constatée.

6.  JOURS OUVRABLES :
    tous les jours de la semaine **sauf le dimanche** et les **jours fériés**
    légaux. (Le samedi est compté comme jour ouvrable.)

Ces constantes sont centralisées pour faciliter toute mise à jour réglementaire.
"""

from datetime import date, timedelta

# --- Constantes légales ---
JOURS_PAR_MOIS = 1.5          # art. 89
JOURS_PAR_MOIS_MINEUR = 2.5   # jeunes travailleurs < 18 ans
CONGE_ANNUEL_BASE = 18        # 1,5 × 12
MAJORATION_ANCIENNETE = 2     # jours / tranche de 5 ans
TRANCHE_ANCIENNETE = 5        # années
MAJORATION_ENFANT = 2         # jours / enfant < 6 ans (mères)
MATERNITE_SEMAINES = 14
MATERNITE_JOURS = 98


def jours_feries_cameroun(annee):
    """Jours fériés légaux camerounais à date fixe pour une année donnée.

    Les fêtes religieuses mobiles (Vendredi Saint, Lundi de Pâques, Ascension,
    Aïd el-Fitr, Aïd el-Kébir) ne sont pas calculées ici : elles peuvent être
    ajoutées dans la table « Holiday » par le service RH chaque année.
    """
    return {
        date(annee, 1, 1): "Jour de l'An",
        date(annee, 2, 11): "Fête de la Jeunesse",
        date(annee, 5, 1): "Fête du Travail",
        date(annee, 5, 20): "Fête Nationale de l'Unité",
        date(annee, 8, 15): "Assomption",
        date(annee, 12, 25): "Noël",
    }


def compter_jours_ouvrables(debut, fin, feries=None):
    """Nombre de jours ouvrables entre deux dates incluses.

    Exclut les dimanches et les jours fériés fournis (set de `date`).
    """
    if fin < debut:
        return 0
    feries = feries or set()
    # Complète automatiquement avec les fériés fixes des années concernées.
    feries = set(feries)
    for an in range(debut.year, fin.year + 1):
        feries |= set(jours_feries_cameroun(an).keys())

    total = 0
    jour = debut
    while jour <= fin:
        if jour.weekday() != 6 and jour not in feries:  # 6 = dimanche
            total += 1
        jour += timedelta(days=1)
    return total


def droit_annuel(mois_service, anciennete_annees=0, est_mineur=False,
                 est_mere=False, enfants_moins_6_ans=0, mere_moins_21_ans=False):
    """Calcule le droit à congé annuel acquis (en jours ouvrables).

    Args:
        mois_service: nombre de mois de service effectif sur la période de référence.
        anciennete_annees: ancienneté totale en années.
        est_mineur: travailleur de moins de 18 ans.
        est_mere: salariée concernée par la majoration pour enfants.
        enfants_moins_6_ans: nombre d'enfants à charge de moins de 6 ans.
        mere_moins_21_ans: True si la mère a moins de 21 ans.
    """
    taux = JOURS_PAR_MOIS_MINEUR if est_mineur else JOURS_PAR_MOIS
    base = mois_service * taux

    # Majoration ancienneté : +2 jours / tranche de 5 ans.
    base += (anciennete_annees // TRANCHE_ANCIENNETE) * MAJORATION_ANCIENNETE

    # Majoration mères salariées.
    if est_mere and enfants_moins_6_ans > 0:
        enfants_comptes = enfants_moins_6_ans if mere_moins_21_ans else max(enfants_moins_6_ans - 1, 0)
        base += enfants_comptes * MAJORATION_ENFANT

    return round(base, 1)
