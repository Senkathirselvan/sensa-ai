import re
from typing import List, Dict, Any, Tuple, Optional
from backend.app.api.schemas import ATSScoreReport, ATSCategoryScores, BulletAudit

ACTION_VERBS: Tuple[str, ...] = (
    "accelerated", "achieved", "administered", "analyzed", "architected", "automated",
    "budgeted", "built", "centralized", "championed", "collaborated", "condensed",
    "consolidated", "contracted", "converted", "coordinated", "decreased", "delivered",
    "deployed", "designed", "developed", "directed", "eliminated", "engineered",
    "enhanced", "established", "evaluated", "executed", "expanded", "expedited",
    "formulated", "generated", "implemented", "improved", "increased", "initiated",
    "instituted", "integrated", "launched", "lead", "led", "maintained", "managed",
    "maximized", "mentored", "minimized", "modernized", "negotiated", "optimized",
    "orchestrated", "overhauled", "pioneered", "reduced", "reengineered", "restructured",
    "revitalized", "saved", "scaled", "spearheaded", "standardized", "streamlined",
    "strengthened", "transformed", "upgraded"
)

COMMON_STOP_WORDS: Tuple[str, ...] = (
    "the", "and", "for", "with", "from", "this", "that", "your", "will", "have",
    "we", "you", "they", "our", "are", "must", "nice", "senior", "junior", "lead",
    "developer", "engineer", "looking", "experience", "years", "role", "team",
    "work", "join", "opportunity", "about", "responsibilities", "requirements",
    "skills", "ability", "strong", "good", "salary", "location", "apply",
    "qualifications", "preferred", "knowledge", "using", "into", "over", "each",
    "such", "when", "then", "both", "well", "plus", "also", "able",
    # Conversational & directive stopwords
    "audit", "check", "resume", "attached", "attachment", "against", "formula",
    "google", "xyz", "pdf", "docx", "file", "please", "draft", "candidate",
    "intake", "profile", "compliance", "score", "review", "evaluate", "dimension",
    "scorecard", "rate", "points", "pts", "percent", "status", "senkathirselvan"
)

UNIVERSAL_PROFESSIONAL_KEYWORDS: Tuple[str, ...] = (
    "leadership", "management", "operations", "strategy", "collaboration",
    "communication", "analytics", "compliance", "budgeting", "project management",
    "cross-functional", "client relations", "process improvement"
)

METRIC_PATTERNS = [
    re.compile(r'\b\d+(?:\.\d+)?%\b', re.IGNORECASE),                               # 25%, 99.9%
    re.compile(r'(?:\$|€|£|₹|Rs\.?)\s*\d+(?:,\d+)*(?:\.\d+)?[kKmMbB]?', re.IGNORECASE), # $50k, ₹10L
    re.compile(r'\b\d+\s*(?:x|times|fold)\b', re.IGNORECASE),                         # 5x, 3 times
    re.compile(r'\b\d+(?:,\d+)*\+?\s*(?:users|customers|clients|requests|req/s|rps|tps|queries|endpoints|microservices|servers|nodes|gb|tb|pb|ms|seconds|minutes|hours|days|weeks|months|years)\b', re.IGNORECASE),
    re.compile(r'\b(?:reduced|increased|improved|saved|scaled)\s+(?:by\s+)?\d+', re.IGNORECASE),
    re.compile(r'\b[1-9]\d{1,6}\b')                                                 # Non-trivial numbers (e.g., 50, 500, 10000)
]

class ATSScorer:
    @staticmethod
    def extract_keywords_from_jd(jd_text: str) -> List[str]:
        """Extracts key technical, architectural, and procedural keywords from a Job Description."""
        if not jd_text:
            return []

        # If text looks like a user prompt or audit directive rather than a job description
        is_prompt_like = any(p in jd_text.lower() for p in [
            "audit my resume", "check my bullets", "attached resume", "check against google xyz",
            "score my resume", "evaluate my resume", "review my resume", "audit my bullets"
        ])
        if is_prompt_like and len(jd_text.split()) < 35:
            return []

        keywords_bank = [
            # Backend & Languages
            "python", "fastapi", "django", "flask", "golang", "java", "c++", "c#", "rust",
            "typescript", "javascript", "nodejs", "sql", "nosql",
            # Databases & Caches
            "postgresql", "postgres", "mysql", "mongodb", "redis", "elasticsearch", "cassandra",
            # Architecture & Messaging
            "rest", "restful", "graphql", "grpc", "microservices", "celery", "kafka", "rabbitmq",
            "event-driven", "system design", "distributed systems",
            # Cloud & DevOps
            "docker", "kubernetes", "k8s", "aws", "gcp", "azure", "ci/cd", "terraform", "linux",
            # Testing & Scraping
            "pytest", "unit testing", "playwright", "selenium", "scraping", "beautifulsoup",
            # AI / ML
            "llm", "langchain", "prompt engineering", "agent", "rag", "pytorch", "tensorflow", "pandas"
        ]

        found = []
        for kw in keywords_bank:
            pattern = r'\b' + re.escape(kw) + r'\b'
            if re.search(pattern, jd_text, re.IGNORECASE):
                found.append(kw.title() if len(kw) > 3 else kw.upper())

        # Extract capitalized technical terms & acronyms (excluding stopwords)
        custom_terms = re.findall(r'\b[A-Z][a-zA-Z0-9\+\#]{1,15}\b', jd_text)
        for term in set(custom_terms):
            if term.lower() not in [k.lower() for k in found] and term.lower() not in COMMON_STOP_WORDS:
                if len(term) >= 2 and not term.isdigit():
                    found.append(term)

        # Tokenize top frequent terms > 3 chars
        cleaned_words = [
            w for w in re.sub(r'[^a-zA-Z0-9#+.\s]', ' ', jd_text.lower()).split()
            if len(w) > 3 and w not in COMMON_STOP_WORDS
        ]
        freq: Dict[str, int] = {}
        for w in cleaned_words:
            freq[w] = freq.get(w, 0) + 1
        
        top_frequent = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:15]
        for w, _ in top_frequent:
            canonical = w.title() if len(w) > 3 else w.upper()
            if canonical.lower() not in [k.lower() for k in found]:
                found.append(canonical)

        return sorted(list(set(found)))[:30]

    @staticmethod
    def audit_bullet(bullet: str) -> BulletAudit:
        """
        Audits an individual bullet point against Google's XYZ formula:
        Accomplished [X] measured by [Y] by doing [Z].
        Checks for active power verbs and quantifiable metrics.
        """
        clean_bullet = bullet.strip().lstrip("-*•+0123456789. ")
        words = clean_bullet.lower().split()
        first_few_words = words[:4] if words else []

        # 1. Action Verb Detection
        found_action_verb: Optional[str] = None
        for w in first_few_words:
            # Strip trailing punctuation
            w_clean = re.sub(r'[^a-z]', '', w)
            if w_clean in ACTION_VERBS:
                found_action_verb = w_clean
                break

        if not found_action_verb:
            for v in ACTION_VERBS:
                if re.search(r'\b' + re.escape(v) + r'\b', clean_bullet, re.IGNORECASE):
                    found_action_verb = v
                    break

        # 2. Metric / Quantifiable Result Detection
        found_metric: Optional[str] = None
        for pat in METRIC_PATTERNS:
            m = pat.search(clean_bullet)
            if m:
                found_metric = m.group(0).strip()
                break

        has_av = bool(found_action_verb)
        has_met = bool(found_metric)

        if has_av and has_met:
            score = "strong"
            feedback = f"Strong Google XYZ impact: Uses active verb '{found_action_verb}' with measurable metric '{found_metric}'."
        elif has_av and not has_met:
            score = "moderate"
            feedback = f"Good action verb ('{found_action_verb}'); consider adding a quantifiable metric (e.g. %, hours saved, user counts)."
        elif not has_av and has_met:
            score = "moderate"
            feedback = f"Contains measurable metric ('{found_metric}'); start the bullet with an active power verb."
        else:
            score = "weak"
            feedback = "Passive phrasing without measurable results. Use Google's XYZ formula: Accomplished [X] measured by [Y] by doing [Z]."

        return BulletAudit(
            bullet=clean_bullet,
            score=score,
            has_action_verb=has_av,
            action_verb=found_action_verb,
            has_metric=has_met,
            metric_found=found_metric,
            feedback=feedback
        )

    @classmethod
    def evaluate_match(
        cls,
        resume_text: str,
        jd_keywords: Optional[List[str]] = None,
        target_role: Optional[str] = None
    ) -> ATSScoreReport:
        """
        Evaluates resume against 4 distinct mathematical ATS categories (25 points each):
        1. Contact Score (25 pts): Name, email, phone, location, LinkedIn link.
        2. Formatting & Structure (25 pts): Standard ATS section headers, semantic ordering.
        3. Impact & Google XYZ Formula (25 pts): Action verbs & quantifiable metrics per bullet.
        4. Keyword Relevance (25 pts): Matching against target JD or industry baselines.
        Total Score: 0 - 100.
        """
        if not resume_text:
            return ATSScoreReport(
                score=0,
                matched_skills=[],
                missing_skills=jd_keywords or [],
                recommendations=["Resume text is empty."]
            )

        text_lower = resume_text.lower()
        recommendations: List[str] = []

        # =====================================================================
        # 1. Contact Score (max 25)
        # =====================================================================
        contact_score = 0
        has_email = bool(re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', resume_text))
        has_phone = bool(re.search(r'(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}|\b\d{10}\b', resume_text))
        has_location = bool(re.search(r'\b(?:chennai|bengaluru|bangalore|hyderabad|mumbai|pune|delhi|california|san francisco|new york|remote|hybrid|india|usa)\b', text_lower))
        has_linkedin = bool(re.search(r'linkedin\.com/in/|linkedin:\s*\S+', text_lower))
        has_github_or_web = bool(re.search(r'github\.com/|https?://[^\s]+', text_lower))

        if has_email: contact_score += 7
        if has_phone: contact_score += 6
        if has_location: contact_score += 4
        if has_linkedin: 
            contact_score += 5
        else:
            recommendations.append("Add your LinkedIn profile URL in contact details — 94% of recruiters cross-reference it.")

        if has_github_or_web: contact_score += 3
        contact_score = min(25, contact_score)

        # =====================================================================
        # 2. Formatting & Structure Score (max 25)
        # =====================================================================
        formatting_score = 0
        has_exp_sec = bool(re.search(r'(?:^|\n)#*\s*(?:work\s+experience|professional\s+experience|experience|employment\s+history)\b', text_lower))
        has_skills_sec = bool(re.search(r'(?:^|\n)#*\s*(?:technical\s+skills|core\s+competencies|skills|technologies)\b', text_lower))
        has_edu_sec = bool(re.search(r'(?:^|\n)#*\s*(?:education|academic\s+background|qualifications)\b', text_lower))
        has_sum_sec = bool(re.search(r'(?:^|\n)#*\s*(?:professional\s+summary|summary|profile|about\s+me)\b', text_lower))

        if has_exp_sec: formatting_score += 8
        if has_skills_sec: formatting_score += 7
        if has_edu_sec: formatting_score += 5
        if has_sum_sec: formatting_score += 5
        formatting_score = min(25, formatting_score)

        if not has_exp_sec or not has_skills_sec:
            recommendations.append("Ensure standard ATS section headers (e.g., 'Work Experience', 'Skills', 'Education') are clearly defined.")

        # =====================================================================
        # 3. Impact & Google XYZ Formula Score (max 25)
        # =====================================================================
        # Isolate Work Experience section if present to avoid treating skill lists as bullets
        exp_match = re.search(
            r'(?:^|\n)(?:#{1,3}\s*)?(?:work\s+experience|professional\s+experience|experience|employment\s+history)\b\s*\n(.*?)(?=\n(?:#{1,3}\s*)?(?:education|projects|certifications|skills|academic)\b|\Z)',
            resume_text,
            re.DOTALL | re.IGNORECASE
        )
        section_to_scan = exp_match.group(1) if exp_match else resume_text

        # Stitch multi-line wrapped bullets together
        bullet_lines: List[str] = []
        curr_bullet_parts: List[str] = []
        for line in section_to_scan.splitlines():
            s = line.strip()
            if not s:
                continue
            if re.match(r'^[-*•+]\s+', s) or re.match(r'^\d+\.\s+', s):
                if curr_bullet_parts:
                    bullet_lines.append(" ".join(curr_bullet_parts))
                curr_bullet_parts = [s]
            elif curr_bullet_parts:
                curr_bullet_parts.append(s)

        if curr_bullet_parts:
            bullet_lines.append(" ".join(curr_bullet_parts))

        # Fallback if markdown bullets are omitted: capture substantive sentences
        if not bullet_lines:
            for l in section_to_scan.splitlines():
                s = l.strip()
                if len(s) > 35 and any(w in s.lower() for w in ("developed", "built", "managed", "implemented", "engineered", "designed")):
                    bullet_lines.append(s)

        bullet_audits: List[BulletAudit] = []
        action_verbs_found_set = set()
        quantified_bullets_count = 0
        strong_bullets_count = 0

        for b in bullet_lines:
            audit = cls.audit_bullet(b)
            bullet_audits.append(audit)
            if audit.action_verb:
                action_verbs_found_set.add(audit.action_verb)
            if audit.has_metric:
                quantified_bullets_count += 1
            if audit.score == "strong":
                strong_bullets_count += 1

        total_bullets = len(bullet_audits)
        action_verbs_count = len(action_verbs_found_set)

        if total_bullets > 0:
            impact_ratio = (quantified_bullets_count * 0.6 + len([a for a in bullet_audits if a.has_action_verb]) * 0.4) / total_bullets
            impact_score = min(25, round(impact_ratio * 25))
            xyz_compliance_rate = round((strong_bullets_count / total_bullets) * 100, 1)
        else:
            impact_score = 12
            xyz_compliance_rate = 50.0

        if total_bullets > 0 and quantified_bullets_count < total_bullets * 0.5:
            recommendations.append("Quantify at least 50% of your bullet points with measurable metrics (e.g., %, latency ms, user counts, scale).")

        # =====================================================================
        # 4. Keyword Relevance Score (max 25)
        # =====================================================================
        matched_keywords: List[str] = []
        missing_keywords: List[str] = []

        if jd_keywords and len(jd_keywords) > 0:
            for kw in jd_keywords:
                pattern = r'\b' + re.escape(kw.lower()) + r'\b'
                if re.search(pattern, text_lower):
                    matched_keywords.append(kw)
                else:
                    missing_keywords.append(kw)

            ratio = len(matched_keywords) / max(len(jd_keywords), 1)
            keywords_score = min(25, round(ratio * 25))
        else:
            # Baseline domain keyword evaluation based on role
            tech_baseline = [
                "Python", "FastAPI", "RESTful APIs", "PostgreSQL", "Redis",
                "Docker", "Microservices", "CI/CD", "Asynchronous", "Unit Testing",
                "System Design", "Performance Optimization"
            ]
            baseline = tech_baseline if any(w in (target_role or "").lower() for w in ["python", "backend", "software", "engineer", "developer"]) else list(UNIVERSAL_PROFESSIONAL_KEYWORDS)
            for kw in baseline:
                if kw.lower() in text_lower:
                    matched_keywords.append(kw)
                else:
                    missing_keywords.append(kw)

            ratio = len(matched_keywords) / max(len(baseline), 1)
            keywords_score = min(25, max(18, round(ratio * 25)))

        if missing_keywords and jd_keywords:
            recommendations.insert(0, f"Incorporate high-priority keywords: {', '.join(missing_keywords[:4])}.")
        elif missing_keywords and len(missing_keywords) > 2:
            recommendations.append(f"Consider highlighting core competency keywords: {', '.join(missing_keywords[:3])}.")

        # =====================================================================
        # Final Aggregate Score (0 to 100)
        # =====================================================================
        overall_score = min(100, max(20, contact_score + formatting_score + impact_score + keywords_score))

        if not recommendations:
            recommendations.append("Excellent profile! Your resume demonstrates strong ATS keyword alignment and quantifiable achievements.")

        categories = ATSCategoryScores(
            contact=contact_score,
            formatting=formatting_score,
            impact=impact_score,
            keywords=keywords_score
        )

        return ATSScoreReport(
            score=overall_score,
            matched_skills=matched_keywords,
            missing_skills=missing_keywords,
            keyword_density_score=min(100, round((keywords_score / 25) * 100)),
            experience_relevance_score=min(100, round(((impact_score + formatting_score) / 50) * 100)),
            recommendations=recommendations,
            categories=categories,
            bullet_audits=bullet_audits,
            total_bullets=total_bullets,
            quantified_bullets_count=quantified_bullets_count,
            action_verbs_count=action_verbs_count,
            action_verbs_found=sorted(list(action_verbs_found_set)),
            xyz_compliance_rate=xyz_compliance_rate
        )
