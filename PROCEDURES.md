# Procédures RH & administratives en vigueur au Cameroun

> Document de référence pour LPM Consulting Group — basé sur la **Loi n° 92/007
> du 14 août 1992 portant Code du Travail** de la République du Cameroun et ses
> textes d'application, la réglementation **CNPS** (Caisse Nationale de
> Prévoyance Sociale) et les usages des conventions collectives.
>
> Ces procédures sont **implémentées dans la plateforme** (modules Congés,
> Discipline, Employés). Les références entre crochets `[…]` renvoient aux
> articles du Code du Travail.

---

## 1. Embauche et contrat de travail

### 1.1 Types de contrats
| Type | Description | Particularités |
|------|-------------|----------------|
| **CDI** | Contrat à durée indéterminée | Forme de droit commun. |
| **CDD** | Contrat à durée déterminée | Durée ≤ 2 ans, renouvelable une fois. Au-delà → requalification en CDI. |
| **Contrat de stage** | Formation / insertion | Convention de stage, gratification. |
| **Temporaire / Mission** | Tâche ponctuelle | Durée liée à la mission. |

### 1.2 Période d'essai [Art. 28]
- Renouvelable une fois, dans la limite de **6 mois** (cadres) selon la catégorie professionnelle.
- Rupture libre pendant l'essai, sous réserve du préavis d'essai.

### 1.3 Formalités obligatoires à l'embauche
1. Établissement du contrat écrit (CDD obligatoirement écrit).
2. **Déclaration du travailleur à la CNPS** dans les 8 jours (immatriculation).
3. Visite médicale d'embauche.
4. Enregistrement au registre de l'employeur.
5. Création du compte intranet et de la **fiche employé** (module Employés) : matricule, département, poste, n° CNPS, date d'embauche.

---

## 2. Congés payés [Art. 89 à 92]

> 📌 **Implémenté** dans le module *Congés* (`conges/cameroon.py`).

### 2.1 Droit de base
- **1,5 jour ouvrable par mois** de service effectif, soit **18 jours ouvrables par an** pour une année complète.
- Le droit s'acquiert progressivement (au prorata des mois travaillés).

### 2.2 Majorations
| Motif | Majoration | Base |
|-------|-----------|------|
| **Ancienneté** | +2 jours ouvrables par tranche de **5 ans** | [Art. 90] |
| **Mère salariée** | +2 jours ouvrables par enfant à charge de **moins de 6 ans** | [Art. 90] |
| **Jeune travailleur (< 18 ans)** | **2,5 jours** ouvrables par mois | Code du Travail |

> *Mères de plus de 21 ans : la majoration s'applique au-delà du 1er enfant.
> Mères de moins de 21 ans : dès le 1er enfant.*

### 2.3 Décompte
- En **jours ouvrables** : tous les jours **sauf les dimanches** et les **jours fériés** légaux.
- Le **samedi** est compté comme jour ouvrable.

### 2.4 Jours fériés légaux (fixes)
1er janvier · 11 février (Jeunesse) · 1er mai (Travail) · 20 mai (Fête Nationale) · 15 août (Assomption) · 25 décembre (Noël).
*Les fêtes mobiles (Vendredi Saint, Lundi de Pâques, Ascension, Aïd el-Fitr, Aïd el-Kébir) sont ajoutées chaque année par le service RH (module Congés → Jours fériés).*

### 2.5 Procédure de demande de congé (workflow plateforme)
1. **L'employé** soumet sa demande (dates + motif). Le système calcule automatiquement les jours ouvrables.
2. **Le responsable hiérarchique** reçoit une notification et **valide ou refuse**.
3. **Le service RH** reçoit la décision et **entérine** (validation finale).
4. **Le solde est mis à jour automatiquement** une fois la demande approuvée.

---

## 3. Congé de maternité et protection de la maternité [Art. 84]

> 📌 Type de congé dédié dans le module *Congés* (non décompté du solde annuel).

- Durée : **14 semaines (98 jours)** — **4 semaines avant** et **10 semaines après** l'accouchement.
- Prolongeable de **6 semaines** en cas de maladie dûment constatée liée à la grossesse/aux couches.
- Indemnité journalière versée par la **CNPS** (prestations familiales / maternité).
- **Interdiction de licenciement** pendant la grossesse et le congé de maternité.
- À la reprise : **repos pour allaitement** (1 heure par jour pendant 15 mois).

---

## 4. Congés et permissions exceptionnels (événements familiaux)

Permissions d'absence rémunérées (usages / conventions collectives), **non déductibles** du congé annuel :
| Événement | Durée indicative |
|-----------|------------------|
| Mariage du travailleur | 3 à 4 jours |
| Décès du conjoint / d'un parent en ligne directe | 3 à 5 jours |
| Naissance d'un enfant (paternité) | 1 à 3 jours |
| Mariage d'un enfant | 1 à 2 jours |
| Déménagement | 1 jour |

> Plafond habituel : **10 jours ouvrables par an**. À ajuster selon la convention collective applicable.

---

## 5. Congé maladie et accidents du travail

- **Maladie** : justifiée par un **certificat médical**. Suspension du contrat ; maintien partiel de salaire selon l'ancienneté et la convention collective.
- **Accident du travail / maladie professionnelle** : déclaration à la **CNPS dans les 3 jours**. Prise en charge des soins et indemnités par la CNPS.
- La maladie n'est **pas décomptée** du congé annuel (type de congé distinct dans la plateforme).

---

## 6. Procédure disciplinaire [Art. 30]

> 📌 **Implémentée** dans le module *Discipline* avec contrôle des durées légales.

### 6.1 Échelle des sanctions (par gravité croissante)
1. **Avertissement écrit**
2. **Blâme**
3. **Mise à pied disciplinaire** — de **1 à 8 jours**, sans solde (maximum légal : 8 jours)
4. **Licenciement** (pour faute)

### 6.2 Droits de la défense (procédure contradictoire)
- Toute sanction **supérieure à l'avertissement** impose la **convocation préalable** du salarié à un **entretien** où il présente ses explications.
- La sanction doit être **notifiée par écrit et motivée**.
- **Non bis in idem** : une même faute ne peut être sanctionnée deux fois.
- Le délai entre la connaissance des faits et la sanction doit être raisonnable.

### 6.3 Étapes dans la plateforme
`Brouillon → Salarié convoqué (entretien préalable) → Sanction notifiée → Clôturée`

---

## 7. Rupture du contrat de travail

### 7.1 Préavis [Art. 34]
Durée fonction de la catégorie professionnelle et de l'ancienneté (de 15 jours à plusieurs mois pour les cadres). À préciser selon la convention collective.

### 7.2 Licenciement
- **Pour motif personnel (faute)** : respect de la procédure disciplinaire (§6).
- **Pour motif économique** : information/consultation des délégués du personnel et de l'inspecteur du travail ; ordre des licenciements.
- **Indemnité de licenciement** : due après **2 ans d'ancienneté** (sauf faute lourde), calculée par tranches d'ancienneté.

### 7.3 Documents de fin de contrat (obligatoires)
1. **Certificat de travail**
2. **Reçu pour solde de tout compte**
3. **Attestation de salaire / cessation** pour la CNPS

---

## 8. Temps de travail et rémunération

- **Durée légale** : **40 heures par semaine** (régime général). Heures au-delà = **heures supplémentaires** majorées.
- **Salaire minimum** : SMIG fixé par décret ; à respecter pour tout poste.
- **Paie** : mensuelle, avec **bulletin de paie** détaillé (salaire de base, primes, retenues CNPS et IRPP).
- **Repos hebdomadaire** : minimum 24 h consécutives (en principe le dimanche).

---

## 9. Cotisations sociales et fiscales (CNPS & impôts)

| Régime | Assiette | Observations |
|--------|----------|--------------|
| **Pensions (vieillesse/invalidité/décès)** | Plafonnée | Part employeur + part salarié |
| **Prestations familiales** | Plafonnée | À la charge de l'employeur |
| **Risques professionnels (AT/MP)** | Salaire | À la charge de l'employeur, taux selon le secteur |
| **IRPP + CAC + taxes** | Salaire imposable | Retenue à la source (précompte) |

> L'employeur **déclare et reverse** mensuellement/trimestriellement les cotisations à la CNPS et les impôts au Trésor.

---

## 10. Représentation du personnel et obligations diverses

- **Délégués du personnel** : élus dès **≥ 11 salariés**.
- **Règlement intérieur** : obligatoire dès **≥ 11 salariés** ; visé par l'inspecteur du travail (hygiène, sécurité, discipline).
- **Registre de l'employeur** et **affichage** des informations légales obligatoires.
- **Médecine du travail** et obligations d'hygiène et sécurité (CHS selon l'effectif).

---

### Avertissement
Ce document est un **guide opérationnel** synthétique destiné à la plateforme.
Il ne se substitue pas aux textes officiels ni à l'avis d'un conseil juridique.
Les durées indicatives (permissions exceptionnelles, préavis, indemnités) doivent
être confirmées au regard de la **convention collective** applicable à LPM
Consulting Group et des textes en vigueur à la date d'application.
