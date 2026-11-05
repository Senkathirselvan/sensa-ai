import re
from typing import Dict, Any, Optional, Tuple

class FormMapper:
    """Semantic mapping engine to match HTML form fields with candidate profile data."""

    PATTERNS = {
        "email": [r"email", r"e-mail", r"mail_id"],
        "first_name": [r"first.*name", r"fname", r"given.*name"],
        "last_name": [r"last.*name", r"lname", r"surname", r"family.*name"],
        "full_name": [r"full.*name", r"candidate.*name", r"name"],
        "phone": [r"phone", r"mobile", r"contact.*number", r"cell", r"telephone"],
        "linkedin_url": [r"linkedin", r"linked-in"],
        "github_url": [r"github", r"git"],
        "portfolio_url": [r"portfolio", r"website", r"personal.*site"],
        "location": [r"location", r"city", r"address", r"residence"],
        "years_of_experience": [r"experience.*year", r"total.*exp", r"years.*exp"],
        "notice_period": [r"notice.*period", r"notice.*day", r"availability"],
        "current_ctc": [r"current.*ctc", r"current.*salary", r"current.*compensation"],
        "expected_ctc": [r"expected.*ctc", r"expected.*salary", r"expected.*compensation"]
    }

    @classmethod
    def match_field(
        cls,
        name: str = "",
        label: str = "",
        placeholder: str = "",
        aria_label: str = "",
        candidate: Dict[str, Any] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Determines the semantic field type and returns (field_key, value_to_fill).
        """
        if not candidate:
            return None, None

        combined_text = f"{name} {label} {placeholder} {aria_label}".lower().strip()

        for field_key, regex_list in cls.PATTERNS.items():
            for pat in regex_list:
                if re.search(pat, combined_text):
                    val = candidate.get(field_key)
                    if val is not None:
                        return field_key, str(val)

        return None, None

    @classmethod
    def answer_screening_question(cls, question: str, candidate: Dict[str, Any]) -> str:
        """Heuristic answer generator for common ATS screening prompts."""
        q_lower = question.lower()

        if "authorized to work" in q_lower or "legally authorized" in q_lower:
            return "Yes"
        if "sponsorship" in q_lower:
            return "No"
        if "notice period" in q_lower or "how soon can you start" in q_lower:
            return str(candidate.get("notice_period", "15"))
        if "lacs" in q_lower or "lakh" in q_lower:
            if "expected" in q_lower:
                return "9"
            if "current" in q_lower:
                return "6"
            return "9"
        if "company" in q_lower or "employer" in q_lower:
            return str(candidate.get("current_company", "SagaSoft Technologies Pvt. Ltd."))
        if "current ctc" in q_lower or "current salary" in q_lower:
            return str(candidate.get("current_ctc", "600000"))
        if "expected ctc" in q_lower or "expected salary" in q_lower:
            return str(candidate.get("expected_ctc", "900000"))
        if "years of experience" in q_lower or "total experience" in q_lower or "experience do you have" in q_lower:
            return str(candidate.get("years_of_experience", "2"))
        if "preferred" in q_lower and "location" in q_lower:
            return str(candidate.get("city", "Chennai"))
        if "location" in q_lower or "city" in q_lower:
            return str(candidate.get("city", "Chennai"))
        if "relocate" in q_lower or "open to relocate" in q_lower:
            return "Yes"
        if "remote" in q_lower or "hybrid" in q_lower:
            return "Yes"

        return "Yes"

