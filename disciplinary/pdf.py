"""Génération de la lettre de sanction disciplinaire (papier en-tête)."""

from django.utils import timezone

from documents.letterhead import build_letterhead_pdf

TITLES = {
    "WARNING": "AVERTISSEMENT ÉCRIT",
    "REPRIMAND": "BLÂME",
    "SUSPENSION": "NOTIFICATION DE MISE À PIED",
    "DISMISSAL": "NOTIFICATION DE LICENCIEMENT",
}


def sanction_pdf(record):
    emp = record.employee
    place_date = f"Douala, le {timezone.localdate():%d/%m/%Y}"
    recipient = (f"<b>{emp.full_name}</b><br/>Matricule : {emp.matricule}<br/>"
                 f"{emp.position.title if emp.position else ''}")
    objet = TITLES.get(record.sanction_type, "SANCTION DISCIPLINAIRE")

    body = [
        f"Madame, Monsieur <b>{emp.full_name}</b>,",
        f"Nous faisons suite aux faits suivants, portés à notre connaissance : "
        f"<b>{record.facts}</b>"
        + (f" (faits constatés le {record.fault_date:%d/%m/%Y})." if record.fault_date else "."),
    ]
    if record.hearing_date:
        body.append(f"Vous avez été convoqué(e) à un entretien préalable le "
                    f"<b>{record.hearing_date:%d/%m/%Y}</b> afin de recueillir vos explications, "
                    "dans le respect des droits de la défense.")
    if record.employee_defense:
        body.append(f"Vos explications recueillies : « {record.employee_defense} ».")

    if record.sanction_type == "SUSPENSION" and record.suspension_days:
        body.append(
            f"En conséquence, et conformément au Code du Travail camerounais (art. 30), "
            f"nous vous notifions une <b>mise à pied disciplinaire de {record.suspension_days} jour(s)</b>"
            + (f", à compter du <b>{record.suspension_start:%d/%m/%Y}</b>" if record.suspension_start else "")
            + ", durant laquelle votre contrat de travail et votre rémunération sont suspendus.")
    elif record.sanction_type == "WARNING":
        body.append("En conséquence, nous vous notifions par la présente un "
                    "<b>avertissement écrit</b>, versé à votre dossier.")
    elif record.sanction_type == "REPRIMAND":
        body.append("En conséquence, nous vous notifions par la présente un <b>blâme</b>, "
                    "versé à votre dossier.")
    elif record.sanction_type == "DISMISSAL":
        body.append("En conséquence, nous vous notifions votre <b>licenciement</b> dans les "
                    "conditions prévues par la loi et la convention collective applicable.")

    body.append("Nous vous invitons à veiller au strict respect de vos obligations "
                "professionnelles à l’avenir. Nous vous prions d’agréer l’expression de nos salutations distinguées.")

    from documents.letterhead import user_signature_paths
    sig_path, stamp_path = user_signature_paths(getattr(record, "decided_by", None))
    return build_letterhead_pdf(
        title=objet,
        reference=record.reference or f"SANCT-{record.pk}",
        place_date=place_date,
        recipient_block=recipient,
        body_html_blocks=body,
        signatory={"role": "La Direction des Ressources Humaines",
                   "name": record.decided_by.get_full_name() if record.decided_by else "Service RH"},
        signature_path=sig_path, stamp_path=stamp_path,
    )
