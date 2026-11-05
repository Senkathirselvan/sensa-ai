import os
from pypdf import PdfReader

RESUME_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "resume.pdf")


def read_my_resume() -> str:
    if not os.path.exists(RESUME_PATH):
        return f"Error: resume.pdf not found at {RESUME_PATH}. Please place your resume at data/resume.pdf."
    try:
        reader = PdfReader(RESUME_PATH)
        full_text = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                full_text.append(f"--- Page {i+1} ---\n{text}")
        extracted = "\n".join(full_text)
        return extracted[:3500] if extracted else "Resume file appears empty."
    except Exception as e:
        return f"Failed to parse resume: {str(e)}"
