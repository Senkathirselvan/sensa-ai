import io
import re
from typing import Dict, Any, List, Optional
from pypdf import PdfReader
import docx
import pdfplumber

class DocumentParserService:
    @staticmethod
    def extract_text(file_bytes: bytes, filename: str) -> str:
        """
        Extracts clean text layer from PDF, DOCX, or plain text files.
        Detects scanned PDFs with zero extractable characters.
        """
        lower = filename.lower()
        if lower.endswith(".pdf"):
            text = ""
            try:
                reader = PdfReader(io.BytesIO(file_bytes))
                for page in reader.pages:
                    text += (page.extract_text() or "") + "\n"
            except Exception as e:
                print(f"[DocumentParser] PyPDF extraction failed, attempting pdfplumber: {e}")
                try:
                    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                        for page in pdf.pages:
                            text += (page.extract_text() or "") + "\n"
                except Exception as e2:
                    raise ValueError(f"Failed to read PDF document: {e2}")

            clean_chars = re.sub(r'[\s\r\n\t]', '', text)
            if len(clean_chars) < 20:
                raise ValueError("Scanned or image-only PDF detected with no readable text layer. Please upload a text-based document or paste resume text.")
            return text.strip()

        elif lower.endswith(".docx") or lower.endswith(".doc"):
            try:
                doc = docx.Document(io.BytesIO(file_bytes))
                paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                # Extract text from tables as well
                for table in doc.tables:
                    for row in table.rows:
                        row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                        if row_text:
                            paragraphs.append(row_text)
                text = "\n".join(paragraphs)
            except Exception as e:
                raise ValueError(f"Failed to read DOCX document: {e}")

            if len(re.sub(r'[\s\r\n\t]', '', text)) < 15:
                raise ValueError("The DOCX file appears to be empty or contains unreadable text.")
            return text.strip()

        elif lower.endswith(".txt") or lower.endswith(".md"):
            return file_bytes.decode("utf-8", errors="ignore").strip()

        raise ValueError(f"Unsupported document format '{filename}'. Please upload .pdf, .docx, or .txt.")

    @staticmethod
    def heuristic_parse_resume(raw_text: str) -> Dict[str, Any]:
        """
        Fast heuristic extractor for contact info, skills, and sections.
        """
        lines = [l.strip() for l in raw_text.splitlines() if l.strip()]

        # Contact info regexes
        email_m = re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', raw_text)
        phone_m = re.search(r'(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}|\b\d{10}\b', raw_text)
        linkedin_m = re.search(r'linkedin\.com/in/([a-zA-Z0-9_-]+)', raw_text, re.IGNORECASE)
        github_m = re.search(r'github\.com/([a-zA-Z0-9_-]+)', raw_text, re.IGNORECASE)
        loc_m = re.search(r'\b([A-Z][a-zA-Z\s]+,\s*[A-Z][a-zA-Z\s]+)\b', raw_text)

        # Detect candidate name from first 4 lines
        candidate_name = "Candidate Name"
        headline = "Software Engineer"
        for line in lines[:6]:
            clean_l = re.sub(r'^[#*_\-\s]+|[#*_\-\s]+$', '', line).strip()
            if len(clean_l) > 2 and len(clean_l) < 120 and "@" not in clean_l and "http" not in clean_l and "resume" not in clean_l.lower():
                if candidate_name == "Candidate Name":
                    candidate_name = clean_l
                elif headline == "Software Engineer" and any(k in clean_l.lower() for k in ["developer", "engineer", "architect", "lead", "specialist", "backend", "full stack"]):
                    headline = clean_l

        # Extract verified technical skills
        common_tech = [
            "Python", "FastAPI", "Django", "Flask", "PostgreSQL", "MySQL", "MongoDB", "Redis",
            "Docker", "Kubernetes", "AWS", "GCP", "Celery", "Kafka", "RabbitMQ", "Git", "CI/CD",
            "REST API", "GraphQL", "Linux", "Playwright", "Selenium", "Pandas", "NumPy",
            "LangChain", "LLM", "Generative AI", "React", "TypeScript", "JavaScript", "HTML/CSS",
            "Node.js", "Go", "Java", "C++", "C#", "Rust", "SQL", "NoSQL"
        ]
        found_skills = [s for s in common_tech if re.search(r'\b' + re.escape(s) + r'\b', raw_text, re.IGNORECASE)]

        return {
            "name": candidate_name,
            "headline": headline,
            "email": email_m.group(0) if email_m else None,
            "phone": phone_m.group(0) if phone_m else None,
            "location": loc_m.group(0) if loc_m else None,
            "linkedin": f"https://linkedin.com/in/{linkedin_m.group(1)}" if linkedin_m else None,
            "github": f"https://github.com/{github_m.group(1)}" if github_m else None,
            "skills": found_skills,
            "raw_text": raw_text
        }

