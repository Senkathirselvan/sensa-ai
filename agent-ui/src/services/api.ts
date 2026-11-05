import { ChatSession, ChatMessage, ChatMessageVersion, ResumeStatus, JobCard, JobCounts, AuthRequiredEvent, PlatformAuthStatus, AutoApplySettings } from '../types';

const API_BASE = '/api';

export function normalizeIsoUtc(ts?: string): string | undefined {
  if (!ts) return undefined;
  let s = ts.trim();
  if (s && !s.endsWith('Z') && !/[+-]\d{2}(?::?\d{2})?$/.test(s)) {
    s = s.replace(' ', 'T') + 'Z';
  }
  return s;
}

export function consolidateSessionMessages(rawMessages: ChatMessage[]): ChatMessage[] {
  if (!rawMessages || rawMessages.length === 0) return [];
  const consolidated: ChatMessage[] = [];

  for (let i = 0; i < rawMessages.length; i++) {
    const msg = rawMessages[i];
    if (msg.role !== 'user') {
      consolidated.push(msg);
      continue;
    }

    // If message already has explicit populated versions (>1 or single with populated version list):
    if (msg.versions && msg.versions.length > 0) {
      consolidated.push(msg);
      continue;
    }

    const prevMsg = consolidated[consolidated.length - 1];
    const prevAssistant = consolidated.length >= 2 ? consolidated[consolidated.length - 1] : null;
    const prevUser = consolidated.length >= 2 ? consolidated[consolidated.length - 2] : null;

    // Pattern A: Consecutive user messages in a row (e.g. repeated clicks on rerun before assistant finished)
    if (prevMsg && prevMsg.role === 'user' && (prevMsg.content.trim() === msg.content.trim() || !prevMsg.content || !msg.content)) {
      const currentVersions = prevMsg.versions && prevMsg.versions.length > 0
        ? [...prevMsg.versions]
        : [{ content: prevMsg.content, images: prevMsg.images || [] }];
      currentVersions.push({ content: msg.content, images: msg.images || [] });
      prevMsg.versions = currentVersions;
      prevMsg.versionIndex = currentVersions.length - 1;
      prevMsg.content = msg.content;
      prevMsg.images = msg.images;
      prevMsg.createdAt = msg.createdAt || prevMsg.createdAt;
      continue;
    }

    // Pattern B: Alternating user rerun turns (User1 -> Assistant1 -> User2 [same prompt] -> Assistant2)
    if (
      prevUser &&
      prevUser.role === 'user' &&
      prevAssistant &&
      prevAssistant.role === 'assistant' &&
      prevUser.content.trim() === msg.content.trim()
    ) {
      const currentVersions = prevUser.versions && prevUser.versions.length > 0
        ? [...prevUser.versions]
        : [{ content: prevUser.content, images: prevUser.images || [] }];

      // Record the previous assistant response into the last version
      const lastVerIdx = currentVersions.length - 1;
      if (!currentVersions[lastVerIdx].assistantResponse) {
        currentVersions[lastVerIdx].assistantResponse = {
          content: prevAssistant.content,
          jobCards: prevAssistant.jobCards,
          createdAt: prevAssistant.createdAt,
        };
      }

      let nextAssistant: ChatMessage | null = null;
      if (i + 1 < rawMessages.length && rawMessages[i + 1].role === 'assistant') {
        nextAssistant = rawMessages[i + 1];
        i++;
      }

      currentVersions.push({
        content: msg.content,
        images: msg.images || [],
        assistantResponse: nextAssistant
          ? {
              content: nextAssistant.content,
              jobCards: nextAssistant.jobCards,
              createdAt: nextAssistant.createdAt,
            }
          : undefined,
      });

      prevUser.versions = currentVersions;
      prevUser.versionIndex = currentVersions.length - 1;
      prevUser.content = msg.content;
      prevUser.images = msg.images;
      prevUser.createdAt = msg.createdAt || prevUser.createdAt;

      if (nextAssistant) {
        consolidated[consolidated.length - 1] = nextAssistant;
      }
      continue;
    }

    const initialVersion: ChatMessageVersion = {
      content: msg.content,
      images: msg.images || [],
    };
    consolidated.push({
      ...msg,
      versions: [initialVersion],
      versionIndex: 0,
    });
  }

  // Ensure user messages preceding an assistant message capture the assistant response in their active version
  for (let j = 0; j < consolidated.length; j++) {
    const cur = consolidated[j];
    const nxt = consolidated[j + 1];
    if (cur.role === 'user' && cur.versions && cur.versions.length > 0 && nxt && nxt.role === 'assistant') {
      const activeIdx = cur.versionIndex ?? (cur.versions.length - 1);
      if (cur.versions[activeIdx] && !cur.versions[activeIdx].assistantResponse) {
        cur.versions[activeIdx].assistantResponse = {
          content: nxt.content,
          jobCards: nxt.jobCards,
          createdAt: nxt.createdAt,
        };
      }
    }
  }

  return consolidated;
}

export const api = {
  // Session APIs
  async getSessions(): Promise<ChatSession[]> {
    const res = await fetch(`${API_BASE}/sessions`);
    if (!res.ok) throw new Error('Failed to fetch sessions');
    const data = await res.json();
    return (data || []).map((s: any) => ({
      ...s,
      created_at: normalizeIsoUtc(s.created_at) || s.created_at,
      updated_at: normalizeIsoUtc(s.updated_at) || s.updated_at,
    }));
  },

  async createSession(title: string = 'New Job Search', id?: string): Promise<ChatSession> {
    const res = await fetch(`${API_BASE}/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, id }),
    });
    if (!res.ok) throw new Error('Failed to create session');
    return res.json();
  },

  async getSession(id: string): Promise<ChatSession & { messages: ChatMessage[] }> {
    const res = await fetch(`${API_BASE}/sessions/${id}`);
    if (!res.ok) throw new Error('Failed to fetch session detail');
    const data = await res.json();
    const rawMessages: ChatMessage[] = (data.messages || []).map((m: any) => ({
      id: m.id,
      role: m.role,
      content: m.content,
      images: m.images || [],
      toolCalls: m.tool_calls || [],
      jobCards: m.job_cards || [],
      versions: Array.isArray(m.versions) && m.versions.length > 0 ? m.versions : undefined,
      versionIndex: typeof m.version_index === 'number' ? m.version_index : undefined,
      createdAt: normalizeIsoUtc(m.created_at),
    }));
    return {
      ...data,
      created_at: normalizeIsoUtc(data.created_at) || data.created_at,
      updated_at: normalizeIsoUtc(data.updated_at) || data.updated_at,
      messages: consolidateSessionMessages(rawMessages),
    };
  },

  async deleteSession(id: string): Promise<void> {
    await fetch(`${API_BASE}/sessions/${id}`, { method: 'DELETE' });
  },

  // Resume APIs
  async getResumeStatus(): Promise<ResumeStatus> {
    const res = await fetch(`${API_BASE}/resume/status`);
    if (!res.ok) throw new Error('Failed to fetch resume status');
    return res.json();
  },

  async uploadResume(file: File): Promise<any> {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_BASE}/resume/upload`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) throw new Error('Failed to upload resume');

    // Also synchronize candidate master profile to Resume Prep Agent (Port 8001)
    try {
      const prepFormData = new FormData();
      prepFormData.append('file', file);
      prepFormData.append('save_as_master', 'true');
      await fetch('http://localhost:8001/api/resume/parse', {
        method: 'POST',
        body: prepFormData,
      });
    } catch (e) {
      console.warn('Sync to resume-prep-agent failed:', e);
    }

    return res.json();
  },

  async deleteResume(): Promise<any> {
    const res = await fetch(`${API_BASE}/resume`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error('Failed to delete resume');
    return res.json();
  },

  // Job Tracker APIs
  async getJobCounts(): Promise<JobCounts> {
    const res = await fetch(`${API_BASE}/jobs/counts`);
    if (!res.ok) return { SAVED: 0, APPLIED: 0, INTERVIEW: 0 };
    return res.json();
  },

  async getTrackedJobs(status?: string): Promise<JobCard[]> {
    const url = status ? `${API_BASE}/jobs?status=${status}` : `${API_BASE}/jobs`;
    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to fetch tracked jobs');
    return res.json();
  },

  async clearTrackedJobs(status?: string): Promise<{ success: boolean; deleted_count: number; message: string }> {
    const url = status && status !== "ALL" ? `${API_BASE}/jobs/clear?status=${status}` : `${API_BASE}/jobs/clear`;
    const res = await fetch(url, { method: "DELETE" });
    if (!res.ok) throw new Error("Failed to clear tracked jobs");

    // If clearing APPLIED or ALL, also sync-clear apply agent audit log
    if (!status || status === "ALL" || status === "APPLIED") {
      try {
        await fetch(`/api/apply/history/clear`, { method: "DELETE" });
      } catch (e) {
        console.warn("Could not clear audit log:", e);
      }
    }

    return res.json();
  },

  async deleteTrackedJob(jobId: string): Promise<{ success: boolean; message: string }> {
    const res = await fetch(`${API_BASE}/jobs/${jobId}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Failed to delete tracked job");
    return res.json();
  },

  async saveJob(job: JobCard): Promise<any> {
    const res = await fetch(`${API_BASE}/jobs/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: job.title,
        company: job.company,
        location: job.location || 'Remote',
        url: job.url,
        snippet: job.snippet || '',
        score: job.score || 0,
        match_reasons: job.match_reasons || [],
        missing_skills: job.missing_skills || [],
        status: job.status || 'SAVED',
      }),
    });
    return res.json();
  },

  async getPendingApply(): Promise<any> {
    const res = await fetch(`${API_BASE}/jobs/pending-apply`);
    if (!res.ok) return {};
    return res.json();
  },

  async confirmApply(job: JobCard): Promise<any> {
    const res = await fetch(`${API_BASE}/jobs/confirm-apply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job }),
    });
    return res.json();
  },

  async cancelApply(): Promise<void> {
    await fetch(`${API_BASE}/jobs/cancel-apply`, { method: 'POST' });
  },

  // Multi-Platform Authentication APIs (LinkedIn, Indeed, Naukri)
  async getPlatformAuthStatus(platform: string): Promise<PlatformAuthStatus> {
    try {
      const res = await fetch(`/api/apply/auth/${platform.toLowerCase()}/status`);
      if (!res.ok) return { platform, connected: false };
      return res.json();
    } catch {
      return { platform, connected: false };
    }
  },

  async loginPlatform(platform: string, username?: string, password?: string, headless: boolean = true): Promise<any> {
    try {
      const res = await fetch(`/api/apply/auth/${platform.toLowerCase()}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password, headless }),
      });
      const text = await res.text();
      try {
        return JSON.parse(text);
      } catch {
        return { success: false, message: text || `Server returned error (${res.status})` };
      }
    } catch (e: any) {
      return { success: false, message: e.message || 'Network connection failed' };
    }
  },

  async loginPlatformInteractive(platform: string, username?: string): Promise<any> {
    try {
      const res = await fetch(`/api/apply/auth/${platform.toLowerCase()}/interactive`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username }),
      });
      const text = await res.text();
      try {
        return JSON.parse(text);
      } catch {
        return { success: false, message: text || `Server returned error (${res.status})` };
      }
    } catch (e: any) {
      return { success: false, message: e.message || 'Network connection failed' };
    }
  },

  async pastePlatformCookies(platform: string, cookies: any[]): Promise<any> {
    try {
      const res = await fetch(`/api/apply/auth/${platform.toLowerCase()}/paste-cookies`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cookies }),
      });
      const text = await res.text();
      try {
        return JSON.parse(text);
      } catch {
        return { success: false, message: text || `Server returned error (${res.status})` };
      }
    } catch (e: any) {
      return { success: false, message: e.message || 'Network connection failed' };
    }
  },

  async disconnectPlatform(platform: string): Promise<any> {
    try {
      const res = await fetch(`/api/apply/auth/${platform.toLowerCase()}/disconnect`, {
        method: 'POST',
      });
      const text = await res.text();
      try {
        return JSON.parse(text);
      } catch {
        return { success: false, message: text || `Server returned error (${res.status})` };
      }
    } catch (e: any) {
      return { success: false, message: e.message || 'Network connection failed' };
    }
  },

  // Legacy wrappers for Naukri backwards compatibility
  async getNaukriAuthStatus(): Promise<PlatformAuthStatus> {
    return this.getPlatformAuthStatus('naukri');
  },

  async loginNaukri(username?: string, password?: string): Promise<any> {
    if (!username && !password) {
      return this.loginPlatformInteractive('naukri');
    }
    return this.loginPlatform('naukri', username, password);
  },

  async pasteNaukriCookies(cookies: any[]): Promise<any> {
    return this.pastePlatformCookies('naukri', cookies);
  },

  async disconnectNaukri(): Promise<any> {
    return this.disconnectPlatform('naukri');
  },

  // Key Storage Helpers
  getAnthropicKey(): string {
    return localStorage.getItem('anthropic_api_key') || '';
  },
  setAnthropicKey(key: string): void {
    localStorage.setItem('anthropic_api_key', key.trim());
  },
  getGeminiKey(): string {
    return localStorage.getItem('gemini_api_key') || '';
  },
  setGeminiKey(key: string): void {
    localStorage.setItem('gemini_api_key', key.trim());
  },
  getNvidiaKey(): string {
    return localStorage.getItem('nvidia_api_key') || '';
  },
  setNvidiaKey(key: string): void {
    localStorage.setItem('nvidia_api_key', key.trim());
  },

  // Autonomous Batch Auto-Apply Preferences
  getAutoApplySettings(): AutoApplySettings {
    const raw = localStorage.getItem('auto_apply_settings');
    if (raw) {
      try {
        return JSON.parse(raw);
      } catch (e) {
        // fallback
      }
    }
    return {
      enabled: false,
      maxBatchSize: 5,
      minMatchScore: 75,
      stealthDelaySeconds: 45,
      allowedPlatforms: {
        naukri: true,
        linkedin: true,
        indeed: false,
      },
    };
  },
  setAutoApplySettings(settings: AutoApplySettings): void {
    localStorage.setItem('auto_apply_settings', JSON.stringify(settings));
  },

  // Real-time SSE Chat Stream
  streamChat(
    sessionId: string,
    message: string,
    model: string,
    callbacks: {
      onStatus: (status: string) => void;
      onToken: (token: string) => void;
      onJobCards: (cards: JobCard[]) => void;
      onDone: (data: { content: string; job_cards: JobCard[] }) => void;
      onAuthRequired?: (data: AuthRequiredEvent) => void;
      onError: (err: any) => void;
    },
    abortSignal?: AbortSignal,
    images?: string[],
    editMessageId?: string,
    isRerun?: boolean,
    versions?: ChatMessageVersion[],
    versionIndex?: number
  ) {
    const anthropicKey = this.getAnthropicKey();
    const geminiKey = this.getGeminiKey();
    const nvidiaKey = this.getNvidiaKey();
    const autoApplySettings = this.getAutoApplySettings();

    fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        message,
        images: images && images.length > 0 ? images : undefined,
        model,
        anthropic_key: anthropicKey || undefined,
        gemini_key: geminiKey || undefined,
        nvidia_key: nvidiaKey || undefined,
        auto_apply_settings: autoApplySettings,
        edit_message_id: editMessageId,
        is_rerun: isRerun,
        versions: versions,
        version_index: versionIndex,
      }),
      signal: abortSignal,
    })
      .then(async (response) => {
        if (!response.ok || !response.body) {
          throw new Error(`HTTP Error: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let hasFinished = false;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split(/\r?\n\r?\n/);
          buffer = parts.pop() || '';

          for (const part of parts) {
            if (!part.trim()) continue;

            let eventType = 'message';
            let dataStr = '';

            const lines = part.split(/\r?\n/);
            for (const line of lines) {
              if (line.startsWith('event:')) {
                eventType = line.slice(6).trim();
              } else if (line.startsWith('data:')) {
                let payloadStr = line.slice(5);
                if (payloadStr.startsWith(' ')) payloadStr = payloadStr.slice(1);
                dataStr += payloadStr;
              }
            }

            if (dataStr) {
              let parsedData: any = dataStr;
              try {
                parsedData = JSON.parse(dataStr);
              } catch (e) {
                parsedData = dataStr;
              }

              if (eventType === 'status') callbacks.onStatus(parsedData);
              else if (eventType === 'token') callbacks.onToken(parsedData);
              else if (eventType === 'job_cards') callbacks.onJobCards(parsedData);
              else if (eventType === 'auth_required' && callbacks.onAuthRequired) {
                hasFinished = true;
                callbacks.onAuthRequired(parsedData);
              } else if (eventType === 'done') {
                hasFinished = true;
                callbacks.onDone(parsedData);
              }
            }
          }
        }

        if (!hasFinished) {
          callbacks.onError(new Error("The AI server connection closed unexpectedly."));
        }
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          callbacks.onError(err);
        }
      });
  },

  // ── Agent 2: Resume Preparation Agent APIs ───────────────────────────────
  async getTailoredResumeForJob(jobId: string): Promise<any> {
    const res = await fetch(`${API_BASE}/resume/tailored/${jobId}`);
    if (!res.ok) return { exists: false };
    return res.json();
  },

  getDownloadUrl(filename: string): string {
    return `${API_BASE}/resume/download/${filename}`;
  },

  getPreviewUrl(filename: string): string {
    return `${API_BASE}/resume/preview/${filename}`;
  },

  async getResumeTemplates(): Promise<{ templates: any[]; palettes: any[] }> {
    try {
      const res = await fetch(`${API_BASE}/resume/templates`);
      if (!res.ok) return { templates: [], palettes: [] };
      return res.json();
    } catch {
      return { templates: [], palettes: [] };
    }
  },

  async recompileResume(payload: {
    markdown_text: string;
    target_job_title?: string;
    target_company?: string;
    job_description?: string;
    target_pages?: number;
    template_id?: string;
    palette_id?: string;
    font_id?: string;
  }): Promise<any> {
    const res = await fetch(`${API_BASE}/resume/recompile`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`HTTP Error: ${res.status}`);
    return res.json();
  },

  streamRefineResume(
    payload: {
      user_instruction: string;
      current_markdown: string;
      job_id?: string;
      job_title?: string;
      company?: string;
      job_description?: string;
      target_pages?: number;
      template_id?: string;
      palette_id?: string;
      font_id?: string;
      model?: string;
      anthropic_key?: string;
      gemini_key?: string;
      nvidia_key?: string;
    },
    callbacks: {
      onStatus: (status: string) => void;
      onModel?: (model: string) => void;
      onToken: (token: string) => void;
      onDone: (data: any) => void;
      onError: (err: any) => void;
    },
    abortSignal?: AbortSignal
  ) {
    const anthropicKey = payload.anthropic_key || this.getAnthropicKey();
    const geminiKey = payload.gemini_key || this.getGeminiKey();
    const nvidiaKey = payload.nvidia_key || this.getNvidiaKey();

    fetch(`${API_BASE}/resume/refine/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...payload,
        anthropic_key: anthropicKey || undefined,
        gemini_key: geminiKey || undefined,
        nvidia_key: nvidiaKey || undefined,
      }),
      signal: abortSignal,
    })
      .then(async (response) => {
        if (!response.ok || !response.body) {
          throw new Error(`HTTP Error: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let hasFinished = false;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split(/\r?\n\r?\n/);
          buffer = parts.pop() || '';

          for (const part of parts) {
            if (!part.trim()) continue;

            let eventType = 'message';
            let dataStr = '';

            const lines = part.split(/\r?\n/);
            for (const line of lines) {
              if (line.startsWith('event:')) {
                eventType = line.slice(6).trim();
              } else if (line.startsWith('data:')) {
                let payloadStr = line.slice(5);
                if (payloadStr.startsWith(' ')) payloadStr = payloadStr.slice(1);
                dataStr += payloadStr;
              }
            }

            if (dataStr) {
              let parsedData: any = dataStr;
              try {
                parsedData = JSON.parse(dataStr);
              } catch (e) {
                parsedData = dataStr;
              }

              if (eventType === 'status') callbacks.onStatus(parsedData);
              else if (eventType === 'model' && callbacks.onModel) callbacks.onModel(parsedData);
              else if (eventType === 'token') callbacks.onToken(parsedData);
              else if (eventType === 'done') {
                hasFinished = true;
                callbacks.onDone(parsedData);
              } else if (eventType === 'error') {
                hasFinished = true;
                callbacks.onError(new Error(parsedData));
              }
            }
          }
        }

        if (!hasFinished) {
          callbacks.onError(new Error("Refinement connection interrupted."));
        }
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          callbacks.onError(err);
        }
      });
  },

  streamTailorResume(
    payload: {
      job_id?: string;
      job_title: string;
      company: string;
      job_description: string;
      target_pages?: number;
      model?: string;
      template_id?: string;
      palette_id?: string;
      font_id?: string;
      generation_mode?: 'tailor' | 'scratch';
      anthropic_key?: string;
      gemini_key?: string;
      nvidia_key?: string;
    },
    callbacks: {
      onStatus: (status: string) => void;
      onBaseline?: (baseline: any) => void;
      onModel?: (model: string) => void;
      onToken: (token: string) => void;
      onDone: (data: any) => void;
      onError: (err: any) => void;
    },
    abortSignal?: AbortSignal
  ) {
    const anthropicKey = payload.anthropic_key || this.getAnthropicKey();
    const geminiKey = payload.gemini_key || this.getGeminiKey();
    const nvidiaKey = payload.nvidia_key || this.getNvidiaKey();

    fetch(`${API_BASE}/resume/tailor/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...payload,
        anthropic_key: anthropicKey || undefined,
        gemini_key: geminiKey || undefined,
        nvidia_key: nvidiaKey || undefined,
      }),
      signal: abortSignal,
    })
      .then(async (response) => {
        if (!response.ok || !response.body) {
          throw new Error(`HTTP Error: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let hasFinished = false;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split(/\r?\n\r?\n/);
          buffer = parts.pop() || '';

          for (const part of parts) {
            if (!part.trim()) continue;

            let eventType = 'message';
            let dataStr = '';

            const lines = part.split(/\r?\n/);
            for (const line of lines) {
              if (line.startsWith('event:')) {
                eventType = line.slice(6).trim();
              } else if (line.startsWith('data:')) {
                let payloadStr = line.slice(5);
                if (payloadStr.startsWith(' ')) payloadStr = payloadStr.slice(1);
                dataStr += payloadStr;
              }
            }

            if (dataStr) {
              let parsedData: any = dataStr;
              try {
                parsedData = JSON.parse(dataStr);
              } catch (e) {
                parsedData = dataStr;
              }

              if (eventType === 'status') callbacks.onStatus(parsedData);
              else if (eventType === 'ats_baseline' && callbacks.onBaseline) callbacks.onBaseline(parsedData);
              else if (eventType === 'model' && callbacks.onModel) callbacks.onModel(parsedData);
              else if (eventType === 'token') callbacks.onToken(parsedData);
              else if (eventType === 'done') {
                hasFinished = true;
                callbacks.onDone(parsedData);
              } else if (eventType === 'error') {
                hasFinished = true;
                callbacks.onError(new Error(parsedData));
              }
            }
          }
        }

        if (!hasFinished) {
          callbacks.onError(new Error("Tailoring connection interrupted."));
        }
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          callbacks.onError(err);
        }
      });
  },

  // =========================================================================
  // AGENT 3: JOB APPLY AGENT APIS (PORT 8002)
  // =========================================================================
  streamApplyJob(
    payload: {
      job_url: string;
      job_title: string;
      company: string;
      job_id?: string;
      tailored_resume_path?: string;
      cover_letter_text?: string;
      headless?: boolean;
      session_id?: string;
    },
    callbacks: {
      onStatus: (status: string) => void;
      onTelemetry?: (telemetry: { stage: string; progress: number }) => void;
      onReviewReady?: (reviewData: any) => void;
      onDone: (data: any) => void;
      onError: (err: any) => void;
    },
    abortSignal?: AbortSignal
  ) {
    fetch(`${API_BASE}/apply/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: abortSignal,
    })
      .then(async (response) => {
        if (!response.ok || !response.body) {
          throw new Error(`HTTP Error: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let hasFinished = false;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n\n');
          buffer = lines.pop() || '';

          for (const block of lines) {
            const trimmed = block.trim();
            if (!trimmed) continue;

            let eventType = 'message';
            let dataStr = '';

            const blockLines = trimmed.split('\n');
            for (const bl of blockLines) {
              if (bl.startsWith('event: ')) {
                eventType = bl.replace('event: ', '').trim();
              } else if (bl.startsWith('data: ')) {
                dataStr = bl.replace('data: ', '').trim();
              }
            }

            if (dataStr) {
              let parsedData: any = dataStr;
              try {
                parsedData = JSON.parse(dataStr);
              } catch {
                parsedData = dataStr;
              }

              if (eventType === 'status') callbacks.onStatus(parsedData);
              else if (eventType === 'telemetry' && callbacks.onTelemetry) callbacks.onTelemetry(parsedData);
              else if (eventType === 'review_ready' && callbacks.onReviewReady) callbacks.onReviewReady(parsedData);
              else if (eventType === 'done') {
                hasFinished = true;
                callbacks.onDone(parsedData);
              } else if (eventType === 'error') {
                hasFinished = true;
                callbacks.onError(new Error(parsedData));
              }
            }
          }
        }

        if (!hasFinished) {
          callbacks.onError(new Error("Apply connection closed."));
        }
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          callbacks.onError(err);
        }
      });
  },

  async confirmApplyStep(sessionId: string): Promise<any> {
    const res = await fetch(`${API_BASE}/apply/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId }),
    });
    return res.json();
  },

  async abortApply(sessionId: string): Promise<any> {
    const res = await fetch(`${API_BASE}/apply/abort`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId }),
    });
    return res.json();
  },

  async getApplySessions(): Promise<any[]> {
    const res = await fetch(`${API_BASE}/apply/sessions/status`);
    if (!res.ok) return [];
    return res.json();
  },

  async getApplyHistory(): Promise<any[]> {
    const res = await fetch(`${API_BASE}/apply/history`);
    if (!res.ok) return [];
    return res.json();
  },

  getApplyScreenshotUrl(filename: string): string {
    return `${API_BASE}/apply/screenshot/${filename}`;
  },
};
