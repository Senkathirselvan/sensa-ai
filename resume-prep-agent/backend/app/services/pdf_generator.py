import os
import re
from typing import Optional
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from backend.app.config import settings

class PDFResumeGenerator:
    @staticmethod
    def _safe_xml(text: str) -> str:
        """Safely encodes XML entities while preserving bold tags for ReportLab."""
        bold_tokens = []
        def repl(m):
            bold_tokens.append(m.group(1))
            return f"__BOLD_{len(bold_tokens)-1}__"
        t = re.sub(r'\*\*(.*?)\*\*', repl, text)
        t = t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        for i, val in enumerate(bold_tokens):
            clean_val = val.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            t = t.replace(f"__BOLD_{i}__", f"<b>{clean_val}</b>")
        return t

    @staticmethod
    def generate_pdf(markdown_text: str, filename_prefix: str = "tailored_resume") -> str:
        """Converts tailored markdown resume into an ATS-friendly, clean single/two-page PDF."""
        # Sanitize filename prefix
        safe_prefix = "".join(c for c in filename_prefix if c.isalnum() or c in ('_', '-')).strip() or "tailored_resume"
        output_filename = f"{safe_prefix}.pdf"
        output_path = os.path.join(settings.EXPORTS_DIR, output_filename)

        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()

        # Custom ATS Typography (Clean, high contrast, readable)
        title_style = ParagraphStyle(
            'ATSTitle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=18,
            leading=22,
            textColor=colors.HexColor('#111827'),
            alignment=1 # Centered
        )

        subtitle_style = ParagraphStyle(
            'ATSSubtitle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=11,
            leading=14,
            textColor=colors.HexColor('#2563eb'), # Accent blue
            alignment=1
        )

        contact_style = ParagraphStyle(
            'ATSContact',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#4b5563'),
            alignment=1
        )

        heading_style = ParagraphStyle(
            'ATSHeading',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=12,
            leading=16,
            textColor=colors.HexColor('#1f2937'),
            spaceBefore=10,
            spaceAfter=4,
            keepWithNext=True
        )

        job_title_style = ParagraphStyle(
            'ATSJobTitle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=10,
            leading=13,
            textColor=colors.HexColor('#111827'),
            spaceBefore=4
        )

        body_style = ParagraphStyle(
            'ATSBody',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9.5,
            leading=13.5,
            textColor=colors.HexColor('#374151')
        )

        bullet_style = ParagraphStyle(
            'ATSBullet',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9.5,
            leading=13.5,
            textColor=colors.HexColor('#374151'),
            leftIndent=15,
            firstLineIndent=-10,
            spaceAfter=3
        )

        story = []
        lines = markdown_text.splitlines()
        is_first_h1 = True

        for line in lines:
            line_str = line.strip()
            if not line_str:
                story.append(Spacer(1, 4))
                continue

            # Header 1: Candidate Name
            if line_str.startswith("# "):
                name = line_str.replace("# ", "").replace("**", "")
                story.append(Paragraph(name, title_style))
                story.append(Spacer(1, 2))
                continue

            # Header 2: Sections
            if line_str.startswith("## "):
                sec_title = line_str.replace("## ", "").replace("**", "").upper()
                story.append(Spacer(1, 6))
                story.append(Paragraph(sec_title, heading_style))
                story.append(HRFlowable(width="100%", thickness=0.75, color=colors.HexColor('#cbd5e1'), spaceBefore=1, spaceAfter=4))
                continue

            # Header 3: Job Title / Company / Dates
            if line_str.startswith("### "):
                title_line = PDFResumeGenerator._safe_xml(line_str.replace("### ", ""))
                story.append(Paragraph(title_line, job_title_style))
                continue

            # Bullet points
            if line_str.startswith("- ") or line_str.startswith("* "):
                bullet_content = line_str[2:].strip()
                formatted_bullet = PDFResumeGenerator._safe_xml(bullet_content)
                story.append(Paragraph(f"• {formatted_bullet}", bullet_style))
                continue

            # General paragraph lines (Summary, Contact info, Skills row)
            formatted_line = PDFResumeGenerator._safe_xml(line_str)
            if "@" in line_str or "|" in line_str:
                story.append(Paragraph(formatted_line, contact_style))
            else:
                story.append(Paragraph(formatted_line, body_style))

        doc.build(story)
        return output_path

