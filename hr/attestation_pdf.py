"""Attestations RH (papier en-tête LPM) : attestation de travail et de stage."""

from django.utils import timezone

from documents.letterhead import build_letterhead_pdf, user_signature_paths


def _civility(employee):
    g = (employee.gender or "").upper()
    return "Madame" if g == "F" else "Monsieur" if g == "M" else "Madame/Monsieur"


def _recipient(employee):
    return (f"<b>{employee.full_name}</b><br/>Matricule : {employee.matricule}<br/>"
            f"{employee.position.title if employee.position else ''}")


def _signatory(signer):
    role = "La Direction des Ressources Humaines"
    name = signer.get_full_name() if signer else "Service RH"
    sig_path, stamp_path = user_signature_paths(signer)
    return {"role": role, "name": name}, sig_path, stamp_path


def attestation_travail_pdf(employee, signer=None):
    civ = _civility(employee)
    poste = employee.position.title if employee.position else "salarié(e)"
    contrat = employee.get_contract_type_display() if hasattr(employee, "get_contract_type_display") else employee.contract_type
    body = [
        "Nous soussignés, <b>LPM Consulting Group</b>, attestons par la présente que :",
        f"{civ} <b>{employee.full_name}</b>, matricule <b>{employee.matricule}</b>, "
        f"est employé(e) au sein de notre entreprise en qualité de <b>{poste}</b> "
        f"depuis le <b>{employee.hire_date:%d/%m/%Y}</b>, dans le cadre d'un contrat de type "
        f"<b>{contrat}</b>.",
        f"{civ} {employee.full_name} fait partie de nos effectifs et exerce ses fonctions "
        "à notre entière satisfaction.",
        "La présente attestation est délivrée à l'intéressé(e) pour servir et valoir ce que de droit.",
    ]
    signatory, sig_path, stamp_path = _signatory(signer)
    return build_letterhead_pdf(
        title="ATTESTATION DE TRAVAIL",
        reference=f"ATT-TRA-{timezone.localdate():%Y}-{employee.pk:04d}",
        place_date=f"Douala, le {timezone.localdate():%d/%m/%Y}",
        recipient_block=_recipient(employee),
        body_html_blocks=body,
        signatory=signatory, signature_path=sig_path, stamp_path=stamp_path,
    )


def attestation_stage_pdf(employee, signer=None):
    civ = _civility(employee)
    poste = employee.position.title if employee.position else "stagiaire"
    # Période de stage : contrat de stage actif si présent, sinon depuis l'embauche.
    contract = employee.contracts.filter(is_active=True).order_by("-start_date").first()
    start = contract.start_date if contract else employee.hire_date
    end = contract.end_date if (contract and contract.end_date) else None
    periode = (f"du <b>{start:%d/%m/%Y}</b> au <b>{end:%d/%m/%Y}</b>"
               if end else f"depuis le <b>{start:%d/%m/%Y}</b>")
    body = [
        "Nous soussignés, <b>LPM Consulting Group</b>, attestons par la présente que :",
        f"{civ} <b>{employee.full_name}</b> a effectué un stage au sein de notre entreprise "
        f"en qualité de <b>{poste}</b>, {periode}.",
        f"Durant cette période, {civ} {employee.full_name} a fait preuve de sérieux et "
        "d'implication dans les missions qui lui ont été confiées.",
        "La présente attestation est délivrée à l'intéressé(e) pour servir et valoir ce que de droit.",
    ]
    signatory, sig_path, stamp_path = _signatory(signer)
    return build_letterhead_pdf(
        title="ATTESTATION DE STAGE",
        reference=f"ATT-STA-{timezone.localdate():%Y}-{employee.pk:04d}",
        place_date=f"Douala, le {timezone.localdate():%d/%m/%Y}",
        recipient_block=_recipient(employee),
        body_html_blocks=body,
        signatory=signatory, signature_path=sig_path, stamp_path=stamp_path,
    )
