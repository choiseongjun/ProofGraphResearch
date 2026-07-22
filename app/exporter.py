from io import BytesIO
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from xml.sax.saxutils import escape


def report_as_pdf(title: str, markdown: str) -> bytes:
    """Small, dependency-light Markdown-to-PDF export optimized for research reports."""
    buffer = BytesIO()
    font_name = "Helvetica"
    font_path = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"
    try:
        pdfmetrics.registerFont(TTFont("NanumGothic", font_path))
        font_name = "NanumGothic"
    except Exception:
        pass
    styles = getSampleStyleSheet()
    body = ParagraphStyle("ReportBody", parent=styles["BodyText"], fontName=font_name, fontSize=9.5, leading=15, spaceAfter=7)
    heading = ParagraphStyle("ReportHeading", parent=styles["Heading2"], fontName=font_name, fontSize=15, leading=20, spaceBefore=12, spaceAfter=8)
    document = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm, title=title)
    story = [Paragraph(escape(title), ParagraphStyle("Title", parent=styles["Title"], fontName=font_name)), Spacer(1, 8)]
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line: continue
        if line.startswith("#"):
            story.append(Paragraph(escape(line.lstrip("# ")), heading))
        else:
            story.append(Paragraph(escape(line).replace("\n", "<br/>"), body))
    document.build(story)
    return buffer.getvalue()
