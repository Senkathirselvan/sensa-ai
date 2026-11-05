from tools.resume_tool import read_my_resume
from tools.search_tool import search_web_jobs
from tools.naukri_tool import search_naukri_multi_city
from tools.scorer_tool import score_and_rank_jobs
from tools.apply_tool import queue_job_for_apply
from tools.db_tool import save_job_to_db, get_saved_jobs, update_job_status

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "read_my_resume",
            "description": "Reads the user's uploaded local resume file ('data/resume.pdf') and extracts their skills, target roles, experience, and projects. Call this IMMEDIATELY whenever the user asks to analyze their resume or find jobs matching their background.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web_jobs",
            "description": "Searches for live job postings from LinkedIn and Indeed using python-jobspy. Automatically resolves broad locations like 'India' into specific cities via Ollama.",
            "parameters": {
                "type": "object",
                "properties": {
                    "role": {"type": "string", "description": "The job title to search for, e.g. 'Python Developer'."},
                    "location": {"type": "string", "description": "Location like 'India', 'Bengaluru', or 'Remote'."},
                    "limit": {"type": "integer", "description": "Max number of job results. Default 6."}
                },
                "required": ["role"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_naukri_jobs",
            "description": "Scrapes live job postings from Naukri.com using a real headless browser. Use for Naukri-specific searches.",
            "parameters": {
                "type": "object",
                "properties": {
                    "role": {"type": "string", "description": "The job title to search for."},
                    "cities": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of specific Indian cities e.g. ['Bengaluru', 'Hyderabad']."
                    },
                    "limit": {"type": "integer", "description": "Max number of results."}
                },
                "required": ["role", "cities"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "score_and_rank_jobs",
            "description": "Scores a list of job postings against the user's resume using local Ollama. Returns jobs ranked by match score 0-100.",
            "parameters": {
                "type": "object",
                "properties": {
                    "jobs": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "List of job dicts from search_web_jobs or search_naukri_jobs."
                    },
                    "min_score": {"type": "integer", "description": "Minimum score threshold. Default 70."}
                },
                "required": ["jobs"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "queue_job_for_apply",
            "description": "Queues a job for application. Shows a confirmation in the UI before submitting. Use when user says 'apply to this job'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "job": {"type": "object", "description": "The job dict with title, company, url."}
                },
                "required": ["job"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_job_to_db",
            "description": "Saves a job into the local SQLite tracker database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "company": {"type": "string"},
                    "url": {"type": "string"},
                    "description": {"type": "string"},
                    "status": {"type": "string", "enum": ["SAVED", "APPLIED"]}
                },
                "required": ["title", "company", "url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_saved_jobs",
            "description": "Retrieves previously saved or applied jobs from the local database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["SAVED", "APPLIED", "INTERVIEW", "REJECTED"]}
                }
            }
        }
    }
]

TOOL_MAP = {
    "read_my_resume": read_my_resume,
    "search_web_jobs": search_web_jobs,
    "search_naukri_jobs": search_naukri_multi_city,
    "score_and_rank_jobs": score_and_rank_jobs,
    "queue_job_for_apply": queue_job_for_apply,
    "save_job_to_db": save_job_to_db,
    "get_saved_jobs": get_saved_jobs,
    "update_job_status": update_job_status,
}
