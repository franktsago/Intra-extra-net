"""Génération du contrat de travail (papier en-tête LPM), adapté au type de contrat.

Couvre CDI, CDD, Stage et Temporaire/Mission. Les éléments variables sont saisis
à la création/édition du contrat (voir ContractForm)."""

from django.utils import timezone

from documents.letterhead import (
    COMPANY, _CACHET, _fit_image, _signature_over_stamp, build_letterhead_pdf,
    user_signature_paths,
)


def _fcfa(v):
    return f"{int(v or 0):,}".replace(",", " ") + " FCFA"


def _civility(employee):
    g = (employee.gender or "").upper()
    return "Madame" if g == "F" else "Monsieur" if g == "M" else "Madame/Monsieur"


TITLES = {
    "CDI": "CONTRAT DE TRAVAIL À DURÉE INDÉTERMINÉE (CDI)",
    "CDD": "CONTRAT DE TRAVAIL À DURÉE DÉTERMINÉE (CDD)",
    "STAGE": "CONTRAT DE STAGE",
    "TEMP": "CONTRAT DE TRAVAIL TEMPORAIRE",
}


def _employer_block():
    cap = f"Capital social : {COMPANY['capital']}<br/>" if COMPANY.get("capital") else ""
    return (
        "<b>ENTRE LES SOUSSIGNÉS :</b><br/><br/>"
        f"<b>{COMPANY['name']}</b>, {COMPANY.get('legal_form', '')}<br/>"
        f"{cap}"
        f"Siège social : {COMPANY['address']}, {COMPANY['bp']}<br/>"
        f"RCCM : {COMPANY['rccm']} — N° Contribuable : {COMPANY['niu']}<br/>"
        f"Représentée par {COMPANY['representative']}, "
        f"agissant en qualité de {COMPANY['representative_title']},<br/>"
        "ci-après dénommée « l'Employeur »,<br/><b>D'UNE PART,</b>"
    )


def _employee_block(contract):
    emp = contract.employee
    naissance = contract.birth_info or "—"
    return (
        "<b>ET</b><br/><br/>"
        f"<b>{emp.full_name}</b><br/>"
        f"Date et lieu de naissance : {naissance}<br/>"
        f"Nationalité : {contract.nationality or '—'}<br/>"
        f"N° CNI / Passeport : {contract.id_number or '—'}<br/>"
        f"Adresse : {emp.address or emp.city or '—'}<br/>"
        f"Téléphone : {emp.phone or '—'}<br/>"
        "ci-après dénommé(e) « le Salarié »,<br/><b>D'AUTRE PART,</b>"
    )


def _articles(contract):
    emp = contract.employee
    typ = contract.type
    poste = contract.title or (emp.position.title if emp.position else "—")
    is_stage = typ == "STAGE"
    qualite = "stagiaire" if is_stage else poste
    blocks = ["Il a été convenu et arrêté ce qui suit :"]

    # Article 1 — Objet
    blocks.append(
        f"<b>ARTICLE 1 — OBJET DU CONTRAT</b><br/>"
        f"L'Employeur engage le Salarié en qualité de <b>{qualite}</b>"
        + (f" (poste : {poste})" if is_stage and poste != '—' else "")
        + ". Le Salarié déclare posséder les compétences et qualifications requises pour ce poste.")

    # Article 2 — Durée / date
    if typ == "CDI":
        a2 = (f"Le présent contrat est conclu pour une <b>durée indéterminée</b> et prend effet "
              f"à compter du <b>{contract.start_date:%d/%m/%Y}</b>.")
    elif typ == "STAGE":
        fin = f" au <b>{contract.end_date:%d/%m/%Y}</b>" if contract.end_date else ""
        a2 = (f"Le présent stage est conclu du <b>{contract.start_date:%d/%m/%Y}</b>{fin}.")
    else:  # CDD / TEMP
        fin = f" et prend fin le <b>{contract.end_date:%d/%m/%Y}</b>" if contract.end_date else ""
        nature = "à durée déterminée" if typ == "CDD" else "temporaire (mission)"
        a2 = (f"Le présent contrat est conclu pour une durée {nature}. Il prend effet "
              f"à compter du <b>{contract.start_date:%d/%m/%Y}</b>{fin}.")
    blocks.append(f"<b>ARTICLE 2 — {'DURÉE DU STAGE' if is_stage else 'DURÉE ET DATE D’EFFET'}</b><br/>{a2}")

    # Article 3 — Lieu de travail
    lieu = contract.work_location or emp.city or "Douala"
    blocks.append(
        f"<b>ARTICLE 3 — LIEU DE TRAVAIL</b><br/>"
        f"Le Salarié exercera ses fonctions principalement à : <b>{lieu}</b>. "
        "En raison des nécessités de service, il pourra être affecté à tout autre site de "
        "l'entreprise situé sur le territoire national.")

    # Article 4 — Période d'essai
    if contract.probation_months and not is_stage:
        a4 = (f"Le présent contrat est assorti d'une période d'essai de "
              f"<b>{contract.probation_months} mois</b>, conformément aux dispositions légales "
              "et conventionnelles en vigueur. Durant cette période, chaque partie peut rompre "
              "le contrat dans les conditions prévues par la réglementation.")
    elif is_stage:
        a4 = "Le présent stage ne comporte pas de période d'essai."
    else:
        a4 = "Le présent contrat n'est assorti d'aucune période d'essai."
    blocks.append(f"<b>ARTICLE 4 — PÉRIODE D'ESSAI</b><br/>{a4}")

    # Article 5 — Fonctions
    duties = [d.strip() for d in (contract.duties or "").splitlines() if d.strip()]
    duties_html = ("<br/>".join(f"• {d}" for d in duties)
                   if duties else "Selon la fiche de poste et les directives de la hiérarchie.")
    blocks.append(
        f"<b>ARTICLE 5 — FONCTIONS ET RESPONSABILITÉS</b><br/>"
        f"Le Salarié exercera notamment les missions suivantes :<br/>{duties_html}<br/>"
        "Cette liste n'est pas limitative.")

    # Article 6 — Durée du travail
    blocks.append(
        f"<b>ARTICLE 6 — DURÉE DU TRAVAIL</b><br/>"
        f"La durée normale du travail est fixée à <b>quarante (40) heures par semaine</b>. "
        f"Horaires : {contract.work_schedule or '—'}. Les heures supplémentaires éventuelles "
        "sont rémunérées conformément aux dispositions légales.")

    # Article 7 — Rémunération
    primes = []
    if contract.transport_allowance:
        primes.append(f"Prime de transport : {_fcfa(contract.transport_allowance)}")
    if contract.housing_allowance:
        primes.append(f"Prime de logement : {_fcfa(contract.housing_allowance)}")
    if contract.performance_allowance:
        primes.append(f"Prime de rendement : {_fcfa(contract.performance_allowance)}")
    if contract.other_allowances:
        primes.append(f"Autres : {contract.other_allowances}")
    primes_html = ("<br/>" + "<br/>".join(f"• {p}" for p in primes)) if primes else ""
    base_label = "Gratification mensuelle de stage" if is_stage else "Salaire de base mensuel"
    blocks.append(
        f"<b>ARTICLE 7 — RÉMUNÉRATION</b><br/>"
        f"{base_label} : <b>{_fcfa(contract.salary)}</b>.{primes_html}<br/>"
        f"<b>Rémunération brute mensuelle : {_fcfa(contract.gross_salary)}</b>. "
        f"Les retenues légales sont appliquées conformément à la réglementation. "
        f"Le salaire est payé au plus tard le {contract.pay_day} de chaque mois.")

    # Article 8 — Congés
    blocks.append(
        "<b>ARTICLE 8 — CONGÉS PAYÉS</b><br/>"
        "Le Salarié bénéficie des congés annuels conformément au Code du Travail du Cameroun "
        "et à la convention collective applicable.")

    # Article 9 — Obligations
    blocks.append(
        "<b>ARTICLE 9 — OBLIGATIONS DU SALARIÉ</b><br/>"
        "Le Salarié s'engage à : exécuter son travail avec diligence et professionnalisme ; "
        "respecter le règlement intérieur ; observer les consignes de sécurité ; préserver les "
        "intérêts de l'entreprise ; respecter la confidentialité des informations.")

    # Article 10 — Discipline
    blocks.append(
        "<b>ARTICLE 10 — DISCIPLINE</b><br/>"
        "Le Salarié est soumis au règlement intérieur de l'entreprise et aux règles "
        "disciplinaires prévues par la législation du travail.")

    # Article 11 — Rupture
    blocks.append(
        "<b>ARTICLE 11 — RUPTURE DU CONTRAT</b><br/>"
        "Le présent contrat peut être rompu dans les conditions prévues par le Code du Travail "
        "du Cameroun, dans le respect des délais de préavis applicables.")

    # Article 12 — Litiges
    blocks.append(
        "<b>ARTICLE 12 — RÈGLEMENT DES LITIGES</b><br/>"
        "Tout différend relatif au présent contrat sera soumis aux procédures de conciliation "
        "prévues par la législation du travail camerounaise avant toute action judiciaire.")

    # Article 13 — Dispositions finales
    blocks.append(
        "<b>ARTICLE 13 — DISPOSITIONS FINALES</b><br/>"
        "Le présent contrat est régi par le Code du Travail du Cameroun et les textes "
        "réglementaires et conventionnels applicables.<br/><br/>"
        f"Fait à {contract.place_signed or 'Douala'}, le {timezone.localdate():%d/%m/%Y}, "
        "en deux exemplaires originaux.")
    return blocks


def _signature_flowables(contract, signer):
    """Bloc signatures : Salarié (gauche, « Lu et approuvé ») / Employeur (droite + cachet)."""
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    base = getSampleStyleSheet()["Normal"]
    st = ParagraphStyle("sig", parent=base, fontSize=10, leading=14)

    party = "STAGIAIRE" if contract.type == "STAGE" else "SALARIÉ"
    salarie = Paragraph(
        f"<b>LE {party}</b><br/>"
        f"{contract.employee.full_name}<br/><br/>"
        "<font size=8 color='#666666'>Signature précédée de la mention<br/>« Lu et approuvé »</font>", st)

    employer_cell = [Paragraph(
        "<b>L'EMPLOYEUR</b><br/>"
        f"{COMPANY['representative']}<br/>"
        f"<font size=8 color='#666666'>{COMPANY['representative_title']}</font>", st)]
    # Cachet (+ signature composée si disponible).
    sig_path, stamp_path = user_signature_paths(signer)
    stamp_src = stamp_path if stamp_path else (str(_CACHET) if _CACHET.exists() else None)
    try:
        if stamp_src and sig_path:
            img = _fit_image(_signature_over_stamp(stamp_src, sig_path), 60 * mm, 40 * mm)
            employer_cell += [Spacer(1, 4), img]
        elif stamp_src:
            employer_cell += [Spacer(1, 4), _fit_image(stamp_src, 46 * mm, 36 * mm)]
    except Exception:
        pass

    tbl = Table([[salarie, employer_cell]], colWidths=[80 * mm, 90 * mm])
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    return [Spacer(1, 16), tbl]


def contract_pdf(contract, signer=None):
    """Génère le PDF du contrat (adapté au type)."""
    emp = contract.employee
    title = TITLES.get(contract.type, "CONTRAT DE TRAVAIL")
    body = [_employer_block(), _employee_block(contract)] + _articles(contract)
    # Pour un stage, on parle du « Stagiaire » et non du « Salarié ».
    if contract.type == "STAGE":
        body = [b.replace("Salarié", "Stagiaire").replace("SALARIÉ", "STAGIAIRE") for b in body]
    return build_letterhead_pdf(
        title=title,
        reference=f"CTR-{contract.type}-{timezone.localdate():%Y}-{contract.pk or 0:04d}",
        place_date=f"{contract.place_signed or 'Douala'}, le {timezone.localdate():%d/%m/%Y}",
        recipient_block=None,
        body_html_blocks=body,
        signatory=None,
        extra_flowables=_signature_flowables(contract, signer),
    )
