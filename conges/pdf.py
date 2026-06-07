"""Génération de la note de congé (papier en-tête) pour un congé approuvé."""

from django.utils import timezone

from accounts.models import Role
from documents.letterhead import build_letterhead_pdf
from .models import ROLE_LABELS


def leave_note_pdf(leave):
    emp = leave.employee
    place_date = f"Douala, le {timezone.localdate():%d/%m/%Y}"
    recipient = (f"<b>{emp.full_name}</b><br/>Matricule : {emp.matricule}<br/>"
                 f"{emp.position.title if emp.position else ''}")

    # Chaîne de validation effective (depuis les approbations enregistrées).
    approvals = list(leave.approvals.filter(approved=True).select_related("approver"))
    if approvals:
        parts = [f"{ROLE_LABELS.get(a.role, a.role)} ({a.approver.get_full_name() if a.approver else '—'})"
                 for a in approvals]
        validation_txt = "Demande validée successivement par : " + " ; ".join(parts) + "."
    else:
        validation_txt = "Demande validée par la hiérarchie."

    # Signataire = dernier validateur (niveau le plus élevé).
    last = approvals[-1] if approvals else None
    signer_role = ROLE_LABELS.get(last.role, "La Direction") if last else "La Direction"
    signer = last.approver if last else None
    signer_name = (signer.get_full_name() if signer else "Service RH")

    # Signature manuscrite + cachet du signataire (renseignés dans son espace).
    from documents.letterhead import user_signature_paths
    signature_path, stamp_path = user_signature_paths(signer)

    body = [
        f"La Direction des Ressources Humaines de <b>LPM Consulting Group</b> atteste "
        f"que <b>{emp.full_name}</b>, {('occupant le poste de ' + emp.position.title) if emp.position else 'salarié(e) de l’entreprise'}, "
        f"matricule <b>{emp.matricule}</b>, est autorisé(e) à prendre un congé de type "
        f"<b>{leave.leave_type.name}</b>.",

        f"Ce congé d’une durée de <b>{leave.days_count} jour(s) ouvrable(s)</b> court du "
        f"<b>{leave.start_date:%d/%m/%Y}</b> au <b>{leave.end_date:%d/%m/%Y}</b> inclus, "
        f"conformément aux dispositions du Code du Travail camerounais (art. 89 et suivants).",

        validation_txt,

        "En foi de quoi la présente note est délivrée pour servir et valoir ce que de droit.",
    ]
    return build_letterhead_pdf(
        title="ATTESTATION DE CONGÉ",
        reference=leave.reference or f"CONGE-{leave.pk}",
        place_date=place_date,
        recipient_block=recipient,
        body_html_blocks=body,
        signatory={"role": signer_role, "name": signer_name},
        signature_path=signature_path,
        stamp_path=stamp_path,
    )
