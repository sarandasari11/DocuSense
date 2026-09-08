import os
import io
import fitz  # PyMuPDF
import docx
from PIL import Image
from typing import List, Dict, Any, Tuple
import logging

logger = logging.getLogger("docusense.parser")

class ParsedPage:
    def __init__(self, page_number: int, raw_text: str, sections: List[Dict[str, Any]], ocr_used: bool = False):
        self.page_number = page_number
        self.raw_text = raw_text
        self.sections = sections  # List of {"heading": str, "content": str, "is_table": bool}
        self.ocr_used = ocr_used

class DocumentParser:
    @staticmethod
    def parse_pdf(file_path: str) -> List[ParsedPage]:
        """Extract pages, headings, paragraphs, and tables from a PDF using PyMuPDF."""
        doc = fitz.open(file_path)
        parsed_pages = []

        for page_idx, page in enumerate(doc):
            page_number = page_idx + 1
            raw_text = page.get_text("text").strip()
            ocr_used = False

            # Fallback if page text is essentially empty (scanned PDF)
            if len(raw_text) < 30:
                try:
                    import pytesseract
                    pix = page.get_pixmap(dpi=150)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    ocr_text = pytesseract.image_to_string(img).strip()
                    if len(ocr_text) > len(raw_text):
                        raw_text = ocr_text
                        ocr_used = True
                except Exception as e:
                    logger.debug(f"OCR not available or failed for page {page_number}: {e}")

            # Structure extraction: Analyze text blocks and font sizes for headings
            sections = []
            current_heading = "General"
            current_content = []

            blocks = page.get_text("dict").get("blocks", [])
            for block in blocks:
                if block.get("type") == 0:  # Text block
                    block_text = ""
                    max_font_size = 0.0
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            span_text = span.get("text", "")
                            font_size = span.get("size", 10.0)
                            if font_size > max_font_size:
                                max_font_size = font_size
                            block_text += span_text + " "
                    
                    block_text = block_text.strip()
                    if not block_text:
                        continue

                    # Heuristic: Larger font or short uppercase text denotes section heading
                    is_heading = (max_font_size >= 13.0 and len(block_text) < 120) or (
                        len(block_text) < 60 and block_text.isupper()
                    )

                    if is_heading:
                        if current_content:
                            sections.append({
                                "heading": current_heading,
                                "content": " ".join(current_content),
                                "is_table": False
                            })
                            current_content = []
                        current_heading = block_text
                    else:
                        current_content.append(block_text)

            if current_content:
                sections.append({
                    "heading": current_heading,
                    "content": " ".join(current_content),
                    "is_table": False
                })

            if not sections and raw_text:
                sections.append({
                    "heading": "General",
                    "content": raw_text,
                    "is_table": False
                })

            parsed_pages.append(ParsedPage(
                page_number=page_number,
                raw_text=raw_text,
                sections=sections,
                ocr_used=ocr_used
            ))

        doc.close()
        return parsed_pages

    @staticmethod
    def parse_docx(file_path: str) -> List[ParsedPage]:
        """Extract headings, paragraphs, and tables from a DOCX file."""
        doc = docx.Document(file_path)
        sections = []
        current_heading = "General"
        current_content = []
        full_text_list = []

        for p in doc.paragraphs:
            text = p.text.strip()
            if not text:
                continue
            full_text_list.append(text)
            
            # Check for Heading styles
            if p.style.name.startswith("Heading") or (len(text) < 80 and text.isupper()):
                if current_content:
                    sections.append({
                        "heading": current_heading,
                        "content": " ".join(current_content),
                        "is_table": False
                    })
                    current_content = []
                current_heading = text
            else:
                current_content.append(text)

        # Extract Tables
        for table in doc.tables:
            table_rows = []
            for row in table.rows:
                row_cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                table_rows.append(" | ".join(row_cells))
            if table_rows:
                table_md = "\n".join(table_rows)
                sections.append({
                    "heading": f"{current_heading} (Table)",
                    "content": table_md,
                    "is_table": True
                })
                full_text_list.append(table_md)

        if current_content:
            sections.append({
                "heading": current_heading,
                "content": " ".join(current_content),
                "is_table": False
            })

        raw_text = "\n\n".join(full_text_list)
        return [ParsedPage(page_number=1, raw_text=raw_text, sections=sections, ocr_used=False)]

    @staticmethod
    def parse_txt(file_path: str) -> List[ParsedPage]:
        """Parse raw text files with section heading recognition."""
        import re
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            raw_text = f.read()

        sections = []
        current_heading = "General"
        current_lines = []

        for line in raw_text.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            
            # Check for section headers like '1. GENERAL...', '2. REMOTE...', or 'SECTION X:'
            if re.match(r'^\d+\.\s+[A-Z\s]{3,}', line_str) or re.match(r'^[A-Z\s]{4,}:', line_str):
                if current_lines:
                    sections.append({
                        "heading": current_heading,
                        "content": "\n".join(current_lines),
                        "is_table": False
                    })
                    current_lines = []
                current_heading = line_str
            else:
                current_lines.append(line_str)

        if current_lines:
            sections.append({
                "heading": current_heading,
                "content": "\n".join(current_lines),
                "is_table": False
            })

        if not sections:
            sections.append({
                "heading": "General",
                "content": raw_text,
                "is_table": False
            })

        return [ParsedPage(page_number=1, raw_text=raw_text, sections=sections, ocr_used=False)]

    @classmethod
    def parse_file(cls, file_path: str, file_type: str) -> List[ParsedPage]:
        ext = file_type.lower().strip(".")
        if ext == "pdf":
            return cls.parse_pdf(file_path)
        elif ext in ["docx", "doc"]:
            return cls.parse_docx(file_path)
        else:
            return cls.parse_txt(file_path)
