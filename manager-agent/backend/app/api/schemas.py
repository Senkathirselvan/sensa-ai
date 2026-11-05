from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

class TargetAgent(str, Enum):
    JOB_FIND = "job-find-agent"          # Search, list, tracker status, saved jobs, cookies
    RESUME_PREP = "resume-prep-agent"    # Tailor, refine, recompile, templates, colors, styling
    JOB_APPLY = "job-apply-agent"        # Portal application submission, browser actions, proofs
    MULTI_STEP = "multi-step-workflow"   # Compound execution (Find -> Tailor -> Apply)
    GENERAL_CHAT = "general-chat"        # Coding, architecture, technical reasoning, casual

class WorkflowStep(BaseModel):
    step_number: int = Field(description="Step sequence index starting at 1")
    target_agent: TargetAgent = Field(description="Worker responsible for this step")
    action: str = Field(description="Specific action name (e.g. 'search_jobs', 'tailor_resume', 'apply_job')")
    input_payload: Dict[str, Any] = Field(default_factory=dict, description="Arguments to pass to the worker")

class ManagerRoutingDecision(BaseModel):
    target_agent: TargetAgent = Field(description="Primary agent or workflow assigned to handle request")
    confidence: float = Field(default=0.95, description="Confidence score between 0.0 and 1.0")
    intent_summary: str = Field(description="Brief explanation of detected user intention")
    extracted_params: Dict[str, Any] = Field(default_factory=dict, description="Parsed parameters from prompt")
    pipeline_steps: Optional[List[WorkflowStep]] = Field(default=None, description="Sequence of steps if MULTI_STEP")
    requires_human_confirmation: bool = Field(default=False, description="True if workflow triggers real submission")

class ChatStreamRequest(BaseModel):
    session_id: str
    message: str
    model: Optional[str] = "auto"
    images: Optional[List[str]] = []
    auto_apply_settings: Optional[Dict[str, Any]] = None
    edit_message_id: Optional[str] = None
    is_rerun: Optional[bool] = False
    versions: Optional[List[Dict[str, Any]]] = None
    version_index: Optional[int] = None

class DispatchRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

class DispatchResponse(BaseModel):
    routing_decision: ManagerRoutingDecision
    status: str
    message: str

