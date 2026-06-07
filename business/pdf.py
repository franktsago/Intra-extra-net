"""Génération PDF des devis et factures (papier en-tête LPM)."""

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Spacer, Table, TableStyle

from documents.letterhead import LPM_BLUE, build_letterhead_pdf


def _fcfa(v):
    return f"{int(v):,}".replace(",", " ") + " FCFA"


def _lines_table(doc):
    """Construit le tableau des lignes + totaux pour un devis/facture."""
    data = [["Désignation", "Qté", "P.U.", "Total"]]
    for line in doc.lines.all():
        data.append([line.designation, f"{line.quantity:g}", _fcfa(line.unit_price), _fcfa(line.total)])
    data.append(["", "", "Sous-total HT", _fcfa(doc.subtotal)])
    data.append(["", "", f"TVA ({doc.tax_rate:g}%)", _fcfa(doc.tax_amount)])
    data.append(["", "", "TOTAL TTC", _fcfa(doc.total)])

    t = Table(data, colWidths=[92 * mm, 18 * mm, 32 * mm, 32 * mm])
    n = len(data)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), LPM_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, n - 4), [colors.white, colors.HexColor("#f3f7fd")]),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, LPM_BLUE),
        ("LINEABOVE", (2, n - 3), (-1, n - 3), 0.5, colors.grey),
        ("FONTNAME", (2, n - 1), (-1, n - 1), "Helvetica-Bold"),
        ("TEXTCOLOR", (2, n - 1), (-1, n - 1), LPM_BLUE),
        ("FONTSIZE", (2, n - 1), (-1, n - 1), 11),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def quote_pdf(quote):
    place_date = f"Douala, le {quote.issue_date:%d/%m/%Y}"
    recipient = f"<b>{quote.client.name}</b><br/>{quote.client.contact_name}<br/>{quote.client.city}"
    intro = [f"<b>Objet :</b> {quote.title}"]
    if quote.valid_until:
        intro.append(f"Devis valable jusqu'au <b>{quote.valid_until:%d/%m/%Y}</b>.")
    extras = [Spacer(1, 6), _lines_table(quote)]
    if quote.notes:
        from reportlab.platypus import Paragraph
        from reportlab.lib.styles import getSampleStyleSheet
        extras += [Spacer(1, 10), Paragraph(f"<i>{quote.notes}</i>", getSampleStyleSheet()["Normal"])]
    # Mention de signature électronique (valeur probante).
    if quote.signed_by_name and quote.signed_at:
        from reportlab.platypus import Paragraph
        from reportlab.lib.styles import getSampleStyleSheet
        sig = (f'<b>Bon pour accord — Signé électroniquement</b> par {quote.signed_by_name} '
               f'le {quote.signed_at:%d/%m/%Y à %H:%M}'
               + (f' (IP {quote.signed_ip})' if quote.signed_ip else '') + '.')
        st = getSampleStyleSheet()["Normal"]
        st.fontSize = 9
        extras += [Spacer(1, 10), Paragraph(sig, st)]
    from documents.letterhead import user_signature_paths
    sig_path, stamp_path = user_signature_paths(quote.owner)
    return build_letterhead_pdf(
        title="DEVIS", reference=quote.number or f"DEV-{quote.pk}",
        place_date=place_date, recipient_block=recipient,
        body_html_blocks=intro, extra_flowables=extras,
        signatory={"role": "Pour LPM Consulting Group",
                   "name": quote.owner.get_full_name() if quote.owner else "Service commercial"},
        signature_path=sig_path, stamp_path=stamp_path,
        with_stamp=(quote.status == "SIGNED"))


def invoice_pdf(invoice):
    place_date = f"Douala, le {invoice.issue_date:%d/%m/%Y}"
    who = invoice.client.name if invoice.client else invoice.supplier_name
    recipient = f"<b>{who}</b>"
    if invoice.client and invoice.client.contact_name:
        recipient += f"<br/>{invoice.client.contact_name}"
    intro = [f"<b>Objet :</b> {invoice.title}"]
    if invoice.due_date:
        intro.append(f"Échéance de paiement : <b>{invoice.due_date:%d/%m/%Y}</b>.")
    extras = [Spacer(1, 6), _lines_table(invoice)]
    if invoice.amount_paid:
        from reportlab.platypus import Paragraph
        from reportlab.lib.styles import getSampleStyleSheet
        st = getSampleStyleSheet()["Normal"]
        extras += [Spacer(1, 8),
                   Paragraph(f"Déjà payé : <b>{_fcfa(invoice.amount_paid)}</b> — "
                             f"Reste à payer : <b>{_fcfa(invoice.balance)}</b>", st)]
    from documents.letterhead import user_signature_paths
    sig_path, stamp_path = user_signature_paths(getattr(invoice, "created_by", None))
    return build_letterhead_pdf(
        title="FACTURE", reference=invoice.number or f"FAC-{invoice.pk}",
        place_date=place_date, recipient_block=recipient,
        body_html_blocks=intro, extra_flowables=extras,
        signatory={"role": "Le Service Financier", "name": "LPM Consulting Group"},
        signature_path=sig_path, stamp_path=stamp_path,
        with_stamp=True)
