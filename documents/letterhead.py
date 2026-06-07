"""Génération de documents officiels sur papier en-tête LPM Consulting Group.

Builder réutilisable (congés, sanctions disciplinaires, attestations…).
Produit un PDF A4 avec en-tête (logo + coordonnées), pied de page légal,
référence, lieu/date, corps, et bloc signature avec cachet officiel.
"""

import os
from io import BytesIO

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)


def _fit_image(src, max_w, max_h):
    """Image redimensionnée pour TENIR dans max_w×max_h en conservant ses proportions.

    `src` : chemin de fichier ou objet fichier (BytesIO)."""
    iw, ih = ImageReader(src).getSize()
    ratio = min(max_w / iw, max_h / ih)
    if hasattr(src, "seek"):
        src.seek(0)  # ImageReader a consommé le flux : on le rembobine pour Image
    return Image(src, width=iw * ratio, height=ih * ratio)


def _whiten_to_alpha(im):
    """Rend transparent le fond clair (blanc) d'une image, en préservant l'alpha
    déjà présent. Idéal pour une signature scannée sur fond blanc (JPG)."""
    from PIL import ImageChops
    im = im.convert("RGBA")
    r, g, b = im.convert("RGB").split()
    whiteness = ImageChops.darker(ImageChops.darker(r, g), b)  # min des canaux
    wa = whiteness.point(lambda v: 0 if v >= 250 else (255 if v <= 210 else int(255 * (250 - v) / 40)))
    existing = im.split()[3]
    im.putalpha(ImageChops.darker(existing, wa))  # min(alpha existant, fond-blanc→0)
    return im


def _transparent_signature_bytes(sig_path):
    """BytesIO PNG d'une signature avec fond rendu transparent."""
    from io import BytesIO
    from PIL import Image as PILImage
    sig = _whiten_to_alpha(PILImage.open(sig_path))
    bio = BytesIO()
    sig.save(bio, "PNG")
    bio.seek(0)
    return bio


def _signature_over_stamp(stamp_path, sig_path):
    """Compose la signature (fond transparent) qui COMMENCE à l'extrémité droite
    du cachet et DÉBORDE vers la droite, centrée verticalement.

    Le canevas est élargi pour laisser dépasser la signature. Retourne un BytesIO PNG."""
    from io import BytesIO
    from PIL import Image as PILImage
    stamp = PILImage.open(stamp_path).convert("RGBA")
    sig = _whiten_to_alpha(PILImage.open(sig_path))
    # Signature dimensionnée à ~60 % de la largeur du cachet.
    target_w = max(1, int(stamp.width * 0.60))
    ratio = target_w / sig.width
    sig = sig.resize((target_w, max(1, int(sig.height * ratio))), PILImage.LANCZOS)
    # La signature démarre vers le bord droit du cachet (léger chevauchement) et déborde.
    sig_x = int(stamp.width * 0.85)
    canvas_w = sig_x + sig.width
    canvas_h = max(stamp.height, sig.height)
    canvas = PILImage.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    canvas.alpha_composite(stamp, (0, (canvas_h - stamp.height) // 2))
    canvas.alpha_composite(sig, (sig_x, (canvas_h - sig.height) // 2))
    bio = BytesIO()
    canvas.save(bio, "PNG")
    bio.seek(0)
    return bio

# Coordonnées légales — configurables via le fichier .env (voir .env.example).
COMPANY = {
    "name": os.getenv("LPM_NAME", "LPM CONSULTING GROUP"),
    "tagline": os.getenv("LPM_TAGLINE", "L'expression de votre marque"),
    "subtitle": os.getenv("LPM_SUBTITLE", "Votre agence panafricaine"),
    "address": os.getenv("LPM_ADDRESS", "Akwa-Nord, 100 m après la pharmacie, immeuble rose, 3ème niveau"),
    "bp": os.getenv("LPM_BP", "B.P. Douala – Cameroun"),
    "phone": os.getenv("LPM_PHONE", "+237 233 410 029"),
    "email": os.getenv("LPM_EMAIL", "lucprosper.moni@lpmconsultinggroup.com"),
    "website": os.getenv("LPM_WEBSITE", "www.lpmconsultinggroup.com"),
    "rccm": os.getenv("LPM_RCCM", "RC/DLA/2014/B/4112"),
    "niu": os.getenv("LPM_NIU", "M101412172020J"),
    # Mentions juridiques pour les contrats.
    "legal_form": os.getenv("LPM_LEGAL_FORM", "SARL"),
    "capital": os.getenv("LPM_CAPITAL", ""),
    "representative": os.getenv("LPM_REPRESENTANT", "Luc Prosper MONI"),
    "representative_title": os.getenv("LPM_REPRESENTANT_TITRE", "Directeur Général"),
}

# Bleu UNIQUE du logo LPM (échantillonné sur le papier en-tête officiel).
LPM_BLUE = colors.HexColor("#0C71B4")
LPM_DARK = colors.HexColor("#0C71B4")

_LOGO = settings.BASE_DIR / "static" / "img" / "logo.png"
_CACHET = settings.BASE_DIR / "static" / "img" / "cachet.png"


def user_signature_paths(user):
    """Chemins (signature, cachet) uploadés par un signataire, sinon (None, None)."""
    def _path(field):
        try:
            return field.path if field else None
        except (ValueError, NotImplementedError):
            return None
    if not user:
        return None, None
    return _path(getattr(user, "signature", None)), _path(getattr(user, "stamp", None))


def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("LPMTitle", parent=s["Title"], fontSize=15, textColor=LPM_DARK,
                         spaceAfter=2, alignment=TA_CENTER))
    s.add(ParagraphStyle("LPMRef", parent=s["Normal"], fontSize=9, textColor=colors.grey))
    s.add(ParagraphStyle("LPMRight", parent=s["Normal"], fontSize=10, alignment=TA_RIGHT))
    s.add(ParagraphStyle("LPMBody", parent=s["Normal"], fontSize=11, leading=17,
                         alignment=TA_JUSTIFY, spaceAfter=8))
    return s


def _header_footer(canvas, doc):
    """En-tête + pied de page LPM dessinés (s'adaptent à tout contenu)."""
    canvas.saveState()
    w, h = A4
    canvas.setFillColor(LPM_BLUE)
    canvas.rect(0, h - 4 * mm, w, 4 * mm, fill=1, stroke=0)
    try:
        canvas.drawImage(str(_LOGO), 18 * mm, h - 33 * mm, width=23 * mm, height=23 * mm,
                         mask="auto", preserveAspectRatio=True)
    except Exception:
        pass
    canvas.setFont("Helvetica-Bold", 14)
    canvas.setFillColor(LPM_DARK)
    canvas.drawString(45 * mm, h - 17 * mm, COMPANY["name"])
    canvas.setFont("Helvetica-Oblique", 8.5)
    canvas.setFillColor(LPM_BLUE)
    canvas.drawString(45 * mm, h - 22 * mm, COMPANY["tagline"])
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.grey)
    canvas.drawString(45 * mm, h - 27 * mm, f'{COMPANY["address"]} · {COMPANY["bp"]}')
    canvas.drawString(45 * mm, h - 31 * mm, f'Tél. : {COMPANY["phone"]} · {COMPANY["email"]}')
    canvas.setStrokeColor(LPM_BLUE)
    canvas.setLineWidth(0.8)
    canvas.line(18 * mm, 20 * mm, w - 18 * mm, 20 * mm)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(LPM_DARK)
    canvas.drawCentredString(w / 2, 16 * mm, f'{COMPANY["name"]} — {COMPANY["subtitle"]}')
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.grey)
    canvas.drawCentredString(w / 2, 12.5 * mm,
                             f'RCCM : {COMPANY["rccm"]} · N° Contribuable : {COMPANY["niu"]} · {COMPANY["website"]}')
    canvas.drawCentredString(w / 2, 9 * mm,
                             "Document généré électroniquement via l'intranet LPM — fait foi de sa traçabilité.")
    canvas.restoreState()


def build_letterhead_pdf(*, title, reference, place_date, body_html_blocks,
                         recipient_block=None, signatory=None, with_stamp=True,
                         signature_path=None, stamp_path=None, extra_flowables=None):
    """Construit un PDF sur papier en-tête.

    Args:
        title: titre du document (ex. "ATTESTATION DE CONGÉ").
        reference: référence unique (ex. "CONGE-2026-0001").
        place_date: ex. "Douala, le 03/06/2026".
        body_html_blocks: liste de chaînes (HTML simple : <b>, <br/>…).
        recipient_block: chaîne optionnelle (destinataire, aligné à droite).
        signatory: dict {name, role} pour le bloc signature.
        with_stamp: appose le cachet + signature officiels si disponible.
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=40 * mm, bottomMargin=26 * mm,
                            leftMargin=18 * mm, rightMargin=18 * mm,
                            title=title, author=COMPANY["name"])
    s = _styles()
    story = []

    story.append(Paragraph(f"Réf. : {reference}", s["LPMRef"]))
    if recipient_block:
        story.append(Spacer(1, 4))
        story.append(Paragraph(recipient_block, s["LPMRight"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(place_date, s["LPMRight"]))
    story.append(Spacer(1, 14))

    story.append(Paragraph(title, s["LPMTitle"]))
    line = Table([[""]], colWidths=[60 * mm])
    line.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 1.4, LPM_BLUE)]))
    story.append(line)
    story.append(Spacer(1, 16))

    for block in body_html_blocks:
        story.append(Paragraph(block, s["LPMBody"]))

    for flow in (extra_flowables or []):
        story.append(flow)

    story.append(Spacer(1, 18))
    if signatory:
        sig_text = (f'<b>{signatory.get("role", "")}</b><br/>{signatory.get("name", "")}')
        cell = [Paragraph(sig_text, s["LPMRight"])]
        drew = False

        # Sources disponibles.
        sig_src = str(signature_path) if (signature_path and os.path.exists(str(signature_path))) else None
        stamp_src = None
        if stamp_path and os.path.exists(str(stamp_path)):
            stamp_src = str(stamp_path)
        elif with_stamp and _CACHET.exists():
            stamp_src = str(_CACHET)
        # Même fichier (image combinée cachet+signature) → ne pas dupliquer.
        if (sig_src and stamp_src
                and os.path.normcase(os.path.abspath(sig_src))
                == os.path.normcase(os.path.abspath(stamp_src))):
            sig_src = None

        try:
            if sig_src and stamp_src:
                # Cachet + signature qui démarre à son extrémité droite et déborde.
                composite = _signature_over_stamp(stamp_src, sig_src)
                cell.append(Spacer(1, 3))
                img = _fit_image(composite, 74 * mm, 44 * mm)
                img.hAlign = "RIGHT"
                cell.append(img)
                drew = True
            elif stamp_src:
                cell.append(Spacer(1, 2))
                img = _fit_image(stamp_src, 52 * mm, 42 * mm)
                img.hAlign = "RIGHT"
                cell.append(img)
                drew = True
            elif sig_src:
                cell.append(Spacer(1, 3))
                img = _fit_image(_transparent_signature_bytes(sig_src), 45 * mm, 22 * mm)
                img.hAlign = "RIGHT"
                cell.append(img)
                drew = True
        except Exception:
            drew = False

        if not drew:
            cell.append(Paragraph('<font size=8 color="#888888">Signature &amp; cachet</font>', s["LPMRight"]))
        sig_tbl = Table([[cell]], colWidths=[85 * mm])
        sig_tbl.hAlign = "RIGHT"
        story.append(sig_tbl)

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    buf.seek(0)
    return buf
