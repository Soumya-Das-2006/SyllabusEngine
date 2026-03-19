import pdfplumber
import re
import os

def extract_text(file_path):
    """
    Extract text from PDF. Returns (text, ocr_used).
    Falls back to Tesseract OCR for scanned pages.
    """
    text = ""
    ocr_used = False

    try:
        with pdfplumber.open(file_path) as pdf:
            page_texts = []
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    page_texts.append(page_text)
                else:
                    # Try OCR fallback for this page
                    ocr_text = _ocr_page(page)
                    if ocr_text:
                        page_texts.append(ocr_text)
                        ocr_used = True

            text = '\n'.join(page_texts)
    except Exception as e:
        # Try full OCR fallback
        try:
            text = _ocr_entire_pdf(file_path)
            ocr_used = True
        except Exception:
            raise ValueError(f"Could not extract text from PDF: {e}")

    return clean_text(text), ocr_used


def _ocr_page(page):
    """Attempt OCR on a single pdfplumber page object."""
    try:
        import pytesseract
        from PIL import Image
        import io
        img = page.to_image(resolution=200).original
        text = pytesseract.image_to_string(img)
        return text
    except Exception:
        return ""


def _ocr_entire_pdf(file_path):
    """Full OCR fallback using pdf2image + Tesseract."""
    try:
        from pdf2image import convert_from_path
        import pytesseract
        pages = convert_from_path(file_path, dpi=200)
        texts = [pytesseract.image_to_string(page) for page in pages]
        return '\n'.join(texts)
    except Exception:
        return ""


def clean_text(text):
    """Normalize extracted text for AI processing."""
    if not text:
        return ""
    # Remove excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    # Remove common PDF artifacts
    text = re.sub(r'Page \d+ of \d+', '', text, flags=re.IGNORECASE)
    text = text.strip()
    return text
