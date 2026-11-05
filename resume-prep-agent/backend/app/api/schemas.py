from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class TailorRequest(BaseModel):
    job_id: Optional[str] = None
    job_title: Optional[str] = None
    company: Optional[str] = None
    job_description: Optional[str] = None
    master_resume_text: Optional[str] = None
    model: Optional[str] = "auto"
    session_id: Optional[str] = None
    target_pages: Optional[int] = 2
    template_id: Optional[str] = None
    palette_id: Optional[str] = None
    font_id: Optional[str] = "modern_inter"
    generate_cover_letter: bool = True
    generation_mode: Optional[str] = "tailor" # 'tailor' (Mode 1) or 'scratch' (Mode 2)
    anthropic_key: Optional[str] = None
    gemini_key: Optional[str] = None
    nvidia_key: Optional[str] = None

class RecompileRequest(BaseModel):
    markdown_text: str
    target_job_title: Optional[str] = "Python Backend Developer"
    target_company: Optional[str] = "Target Company"
    job_description: Optional[str] = None
    target_pages: Optional[int] = 2
    template_id: Optional[str] = "grid_matrix"
    palette_id: Optional[str] = "enterprise_blue"
    font_id: Optional[str] = "modern_inter"

class RefineRequest(BaseModel):
    user_instruction: str
    current_markdown: Optional[str] = ""
    job_id: Optional[str] = None
    job_title: Optional[str] = "Python Backend Developer"
    company: Optional[str] = "Target Company"
    job_description: Optional[str] = ""
    template_id: Optional[str] = None
    palette_id: Optional[str] = None
    font_id: Optional[str] = "modern_inter"
    target_pages: Optional[int] = None
    model: Optional[str] = "auto"
    anthropic_key: Optional[str] = None
    gemini_key: Optional[str] = None
    nvidia_key: Optional[str] = None

class JDAuditResult(BaseModel):
    title: str
    company: str
    required_skills: List[str] = []
    bonus_skills: List[str] = []
    experience_level: str = "Mid-Senior"
    key_responsibilities: List[str] = []
    ats_keywords: List[str] = []

class BulletAudit(BaseModel):
    bullet: str
    score: str # "strong" | "moderate" | "weak"
    has_action_verb: bool
    action_verb: Optional[str] = None
    has_metric: bool
    metric_found: Optional[str] = None
    feedback: str

class ATSCategoryScores(BaseModel):
    contact: int = 0
    formatting: int = 0
    impact: int = 0
    keywords: int = 0

class ATSScoreReport(BaseModel):
    score: int = Field(..., ge=0, le=100)
    matched_skills: List[str] = []
    missing_skills: List[str] = []
    keyword_density_score: int = 0
    experience_relevance_score: int = 0
    recommendations: List[str] = []
    categories: Optional[ATSCategoryScores] = None
    bullet_audits: List[BulletAudit] = []
    total_bullets: int = 0
    quantified_bullets_count: int = 0
    action_verbs_count: int = 0
    action_verbs_found: List[str] = []
    xyz_compliance_rate: float = 0.0

class AuditRequest(BaseModel):
    resume_text: str = ""
    job_description: Optional[str] = None
    target_role: Optional[str] = None

class TailorResponse(BaseModel):
    id: str
    job_id: Optional[str] = None
    target_job_title: str
    target_company: str
    original_score: int
    tailored_score: int
    matched_keywords: List[str] = []
    missing_keywords: List[str] = []
    markdown_content: str
    pdf_url: Optional[str] = None
    docx_url: Optional[str] = None
    cover_letter: Optional[str] = None
    recruiter_outreach_msg: Optional[str] = None

class CoverLetterRequest(BaseModel):
    tailored_resume_id: str
    company: str
    job_title: str
    hiring_manager_name: Optional[str] = None
    custom_notes: Optional[str] = None

class DiffChange(BaseModel):
    section: str = Field(..., description="Section that changed, e.g. Work Experience, Skills, Summary, Basics")
    target_entity: Optional[str] = Field(None, description="Company, Role, or Skill group modified")
    before: str = Field(..., description="Original snippet before modification")
    after: str = Field(..., description="Updated snippet after modification")
    description: str = Field(..., description="Clear explanation of the change applied")

class PrecisionEditRequest(BaseModel):
    instruction: str = Field(..., description="Specific surgical instruction (e.g. 'Update title at SagaSoft to Lead Backend Engineer')")
    current_markdown: Optional[str] = Field(None, description="Current resume markdown. If omitted, uses master resume.")
    target_role: Optional[str] = None
    target_company: Optional[str] = None
    model: Optional[str] = "auto"
    recompile_documents: bool = True
    template_id: Optional[str] = None
    palette_id: Optional[str] = None
    font_id: Optional[str] = "modern_inter"
    target_pages: Optional[int] = 2

class PrecisionEditResponse(BaseModel):
    status: str = "success"
    instruction: str
    diff: DiffChange
    updated_markdown: str
    ats_score: Optional[int] = None
    pdf_filename: Optional[str] = None
    html_filename: Optional[str] = None
    docx_filename: Optional[str] = None
    suggested_power_words: List[str] = []

class PaginateRequest(BaseModel):
    target_pages: int = Field(..., ge=1, le=5, description="Target page count (1, 2, or 3)")
    current_markdown: Optional[str] = Field(None, description="Current markdown resume text. If omitted, uses master resume.")
    target_role: Optional[str] = "Senior Python Backend Developer"
    target_company: Optional[str] = "Target Company"
    template_id: Optional[str] = None
    palette_id: Optional[str] = None
    font_id: Optional[str] = "modern_inter"
    model: Optional[str] = "auto"

class PaginateResponse(BaseModel):
    status: str = "success"
    target_pages: int
    calibrated_markdown: str
    word_count: int
    summary_of_adjustments: str
    ats_score: int
    pdf_filename: Optional[str] = None
    html_filename: Optional[str] = None
    docx_filename: Optional[str] = None

class ParseTextRequest(BaseModel):
    raw_text: str
    target_role: Optional[str] = None
    save_as_master: bool = False

class ParseResumeResponse(BaseModel):
    status: str = "success"
    filename: str
    parsed_profile: Dict[str, Any]
    raw_text: str
    ats_score: int
    char_count: int
    word_count: int
    master_saved: bool = False

class DraftResumeRequest(BaseModel):
    candidate_name: str
    target_role: str
    target_company: Optional[str] = None
    is_fresher: bool = False
    summary_notes: Optional[str] = None
    experience: List[Dict[str, Any]] = []
    education: List[Dict[str, Any]] = []
    skills: List[str] = []
    projects: List[Dict[str, Any]] = []
    certifications: List[str] = []
    template_id: Optional[str] = "grid_matrix"
    palette_id: Optional[str] = "enterprise_blue"
    font_id: Optional[str] = "modern_inter"
    target_pages: Optional[int] = 2

class DraftResumeResponse(BaseModel):
    status: str = "success"
    candidate_name: str
    target_role: str
    markdown_content: str
    executive_summary: str
    ats_score: int
    pdf_filename: Optional[str] = None
    html_filename: Optional[str] = None
    docx_filename: Optional[str] = None
    suggested_power_words: List[str] = []

