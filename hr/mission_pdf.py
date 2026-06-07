"""Génération de l'ordre de mission (papier en-tête LPM)."""

from django.utils import timezone

from documents.letterhead import build_letterhead_pdf, user_signature_paths


def mission_reference(mission):
    return f"OM-{mission.start_date:%Y}-{mission.pk:04d}"


def mission_order_pdf(mission):
    emp = mission.employee
    place_date = f"Douala, le {timezone.localdate():%d/%m/%Y}"
    recipient = (f"<b>{emp.full_name}</b><br/>Matricule : {emp.matricule}<br/>"
                 f"{emp.position.title if emp.position else ''}")
    lieu = mission.destination or "—"

    body = [
        f"La Direction de <b>LPM Consulting Group</b> donne ordre à "
        f"<b>{emp.full_name}</b>, "
        f"{('occupant le poste de ' + emp.position.title) if emp.position else 'collaborateur(trice) de l’entreprise'}, "
        f"matricule <b>{emp.matricule}</b>, d’effectuer une mission professionnelle.",

        f"<b>Destination :</b> {lieu}.",

        f"<b>Période :</b> du <b>{mission.start_date:%d/%m/%Y}</b> au "
        f"<b>{mission.end_date:%d/%m/%Y}</b> inclus, soit <b>{mission.days} jour(s)</b>.",
    ]
    if mission.objet:
        body.append(f"<b>Objet de la mission :</b> {mission.objet}")
    body.append(
        "Toutes les autorités civiles et militaires sont priées de faciliter "
        "l’accomplissement de cette mission à l’intéressé(e). "
        "Le présent ordre de mission est délivré pour servir et valoir ce que de droit.")

    signer = getattr(mission, "created_by", None)
    sig_path, stamp_path = user_signature_paths(signer)
    return build_letterhead_pdf(
        title="ORDRE DE MISSION",
        reference=mission_reference(mission),
        place_date=place_date,
        recipient_block=recipient,
        body_html_blocks=body,
        signatory={"role": "La Direction",
                   "name": signer.get_full_name() if signer else "LPM Consulting Group"},
        signature_path=sig_path, stamp_path=stamp_path,
    )
