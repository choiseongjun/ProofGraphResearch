from io import BytesIO
from pypdf import PdfReader
from app.exporter import report_as_pdf


def test_report_pdf_is_valid_and_contains_title() -> None:
    document = PdfReader(stream=BytesIO(report_as_pdf("Test report", "# Summary\nEvidence [1]")))
    assert len(document.pages) == 1
    assert "Test report" in document.pages[0].extract_text()


def test_report_pdf_has_a4_page_size() -> None:
    document = PdfReader(stream=BytesIO(report_as_pdf("Report", "본문")))
    page = document.pages[0]
    assert round(float(page.mediabox.width)) == 595
    assert round(float(page.mediabox.height)) == 842
