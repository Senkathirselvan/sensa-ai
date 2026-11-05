export interface JobCard {
  id?: string;
  title: string;
  company: string;
  location?: string;
  experience?: string;
  salary?: string;
  posted_date?: string;
  url: string;
  snippet?: string;
  platform?: string;
  score?: number;
  match_reasons?: string[];
  missing_skills?: string[];
  apply?: boolean;
  status?: 'SAVED' | 'APPLIED' | 'INTERVIEW' | 'REJECTED';
  target_pages?: number;
  screenshot_url?: string;
  screenshot_filename?: string;
  applied_at?: string;
  submission_status?: string;
}

export interface ChatMessageVersion {
  content: string;
  images?: string[];
  assistantResponse?: {
    content: string;
    jobCards?: JobCard[];
    createdAt?: string;
  };
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  images?: string[];
  statusText?: string;
  toolCalls?: string[];
  jobCards?: JobCard[];
  createdAt?: string;
  provider?: string;
  versions?: ChatMessageVersion[];
  versionIndex?: number;
}

export type AgentMode = 'all' | 'career' | 'coding' | 'general';

export interface ChatSession {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ResumeStatus {
  uploaded: boolean;
  filename: string | null;
  size_kb: number;
  skills: string[];
}

export interface JobCounts {
  SAVED: number;
  APPLIED: number;
  INTERVIEW: number;
}

export interface AuthRequiredEvent {
  platform: string;
  message: string;
  query?: string;
}

export interface PlatformAuthStatus {
  platform: string;
  connected: boolean;
  cookie_count?: number;
  path?: string;
  session_file?: string | null;
}

export interface AutoApplySettings {
  enabled: boolean;
  maxBatchSize: number;        // e.g. 5
  minMatchScore: number;       // e.g. 75
  stealthDelaySeconds: number; // e.g. 45
  allowedPlatforms: {
    naukri: boolean;
    linkedin: boolean;
    indeed: boolean;
  };
}
