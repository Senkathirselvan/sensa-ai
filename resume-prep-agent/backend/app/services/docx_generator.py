import os
import re
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from backend.app.config import settings

class DOCXResumeGenerator:
    @staticmethod
    def generate_docx(markdown_text: str, filename_prefix: str = "tailored_resume", font_name: str = "Calibri") -> str:
        """Converts tailored markdown resume into an ATS-friendly editable DOCX document."""
        safe_prefix = "".join(c for c in filename_prefix if c.isalnum() or c in ('_', '-')).strip() or "tailored_resume"
        output_filename = f"{safe_prefix}.docx"
        output_path = os.path.join(settings.EXPORTS_DIR, output_filename)

        doc = Document()

        # Set 0.5 inch margins
        for section in doc.sections:
            section.top_margin = Inches(0.5)
            section.bottom_margin = Inches(0.5)
            section.left_margin = Inches(0.5)
            section.right_margin = Inches(0.5)

        lines = markdown_text.splitlines()

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue

            # Header 1: Candidate Name
            if line_str.startswith("# "):
                name = line_str.replace("# ", "").replace("**", "")
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = p.add_run(name)
                run.font.name = font_name
                run.font.size = Pt(18)
                run.font.bold = True
                run.font.color.rgb = RGBColor(17, 24, 39)
                p.paragraph_format.space_after = Pt(2)
                continue

            # Header 2: Section Title
            if line_str.startswith("## "):
                sec = line_str.replace("## ", "").replace("**", "").upper()
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(8)
                p.paragraph_format.space_after = Pt(2)
                run = p.add_run(sec)
                run.font.name = font_name
                run.font.size = Pt(11)
                run.font.bold = True
                run.font.color.rgb = RGBColor(31, 41, 55)
                continue

            # Header 3: Role / Company / Dates
            if line_str.startswith("### "):
                role_line = line_str.replace("### ", "").replace("**", "")
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(4)
                p.paragraph_format.space_after = Pt(1)
                run = p.add_run(role_line)
                run.font.name = font_name
                run.font.size = Pt(10)
                run.font.bold = True
                continue

            # Bullet points
            if line_str.startswith("- ") or line_str.startswith("* "):
                bullet_content = line_str[2:].strip()
                p = doc.add_paragraph(style='List Bullet')
                p.paragraph_format.space_after = Pt(2)
                DOCXResumeGenerator._add_formatted_runs(p, bullet_content, font_name=font_name)
                continue

            # General paragraph
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(2)
            if "@" in line_str or "|" in line_str:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            DOCXResumeGenerator._add_formatted_runs(p, line_str, font_name=font_name)

        doc.save(output_path)
        return output_path

    @staticmethod
    def _add_formatted_runs(paragraph, text: str, font_name: str = "Calibri"):
        """Splits markdown bold formatting into runs."""
        parts = re.split(r'(\*\*.*?\*\*)', text)
        for part in parts:
            if part.startswith("**") and part.endswith("**"):
                run = paragraph.add_run(part[2:-2])
                run.font.name = font_name
                run.font.size = Pt(9.5)
                run.font.bold = True
            else:
                run = paragraph.add_run(part)
                run.font.name = font_name
                run.font.size = Pt(9.5)

