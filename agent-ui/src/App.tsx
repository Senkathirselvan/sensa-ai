import React, { useState, useEffect, useRef } from "react";
import { Sidebar } from "./components/Sidebar";
import { ChatArea } from "./components/ChatArea";
import { SettingsModal } from "./components/SettingsModal";
import { ApplyConfirmModal } from "./components/ApplyConfirmModal";
import { PlatformLoginModal, SupportedPlatform } from "./components/PlatformLoginModal";
import { ResumeTailorModal } from "./components/ResumeTailorModal";
import { ResumePreviewModal } from "./components/ResumePreviewModal";
import { TrackerModal } from "./components/TrackerModal";
import { api } from "./services/api";
import { ChatSession, ChatMessage, ChatMessageVersion, ResumeStatus, JobCard, JobCounts, PlatformAuthStatus, AgentMode, AutoApplySettings } from "./types";

export const App: React.FC = () => {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [selectedModel, setSelectedModel] = useState("auto");
  const [agentMode, setAgentMode] = useState<AgentMode>("all");
  const [resumeStatus, setResumeStatus] = useState<ResumeStatus | null>(null);
  const [jobCounts, setJobCounts] = useState<JobCounts>({ SAVED: 0, APPLIED: 0, INTERVIEW: 0 });
  const [autoApplySettings, setAutoApplySettings] = useState<AutoApplySettings>(api.getAutoApplySettings());
  const [naukriStatus, setNaukriStatus] = useState<PlatformAuthStatus>({ platform: "naukri", connected: false });
  const [platformStatuses, setPlatformStatuses] = useState<Record<SupportedPlatform, PlatformAuthStatus>>({
    linkedin: { platform: "linkedin", connected: false },
    indeed: { platform: "indeed", connected: false },
    naukri: { platform: "naukri", connected: false },
  });

  // Sidebar & Modals state
  const [isDesktopSidebarOpen, setIsDesktopSidebarOpen] = useState(true);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [confirmJob, setConfirmJob] = useState<JobCard | null>(null);
  const [tailorJob, setTailorJob] = useState<JobCard | null>(null);
  const [resumePreviewUrl, setResumePreviewUrl] = useState<string | null>(null);
  const [isStudioOpen, setIsStudioOpen] = useState(false);
  const [studioPreviewUrl, setStudioPreviewUrl] = useState<string | null>(null);
  const [platformModal, setPlatformModal] = useState<{
    isOpen: boolean;
    platform: SupportedPlatform;
    pendingQuery?: string;
  }>({
    isOpen: false,
    platform: "naukri",
  });
  const [trackerModal, setTrackerModal] = useState<{
    isOpen: boolean;
    initialTab: 'ALL' | 'SAVED' | 'APPLIED' | 'INTERVIEW';
  }>({
    isOpen: false,
    initialTab: 'ALL',
  });

  const handleOpenTracker = (tab?: 'ALL' | 'SAVED' | 'APPLIED' | 'INTERVIEW') => {
    setTrackerModal({
      isOpen: true,
      initialTab: tab || 'ALL',
    });
  };

  const handleQuickClearTrackedJobs = async (status?: string) => {
    try {
      await api.clearTrackedJobs(status);
      await loadJobCounts();
    } catch (e) {
      console.error('Failed to clear tracked jobs:', e);
    }
  };

  const abortControllerRef = useRef<AbortController | null>(null);

  // Global Keyboard Shortcuts (Cmd+K / Ctrl+K for New Chat)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        startNewChat();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Load initial data
  useEffect(() => {
    loadSessions();
    loadResumeStatus();
    loadJobCounts();
    loadPlatformStatuses();
  }, []);

  const loadSessions = async () => {
    try {
      const data = await api.getSessions();
      setSessions(data);
      if (data.length > 0 && !activeSessionId) {
        selectSession(data[0].id);
      } else if (data.length === 0) {
        startNewChat();
      }
    } catch (e) {
      console.error("Failed to load sessions", e);
      startNewChat();
    }
  };

  const loadResumeStatus = async () => {
    try {
      const status = await api.getResumeStatus();
      setResumeStatus(status);
    } catch (e) {
      console.error("Failed to load resume status", e);
    }
  };

  const loadJobCounts = async () => {
    try {
      const counts = await api.getJobCounts();
      setJobCounts(counts);
    } catch (e) {
      console.error("Failed to load job counts", e);
    }
  };

  const loadPlatformStatuses = async () => {
    try {
      const [li, ind, nk] = await Promise.all([
        api.getPlatformAuthStatus("linkedin"),
        api.getPlatformAuthStatus("indeed"),
        api.getPlatformAuthStatus("naukri"),
      ]);
      setPlatformStatuses({
        linkedin: li,
        indeed: ind,
        naukri: nk,
      });
      setNaukriStatus(nk);
    } catch (e) {
      console.error("Failed to load platform auth statuses", e);
    }
  };

  const selectSession = async (id: string) => {
    try {
      setActiveSessionId(id);
      const detail = await api.getSession(id);
      setMessages(detail.messages || []);
      setIsMobileSidebarOpen(false);
    } catch (e) {
      console.error("Failed to select session", e);
    }
  };

  const startNewChat = () => {
    const newId = crypto.randomUUID();
    setActiveSessionId(newId);
    setMessages([]);
    setIsMobileSidebarOpen(false);
  };

  const handleDeleteSession = async (id: string) => {
    try {
      await api.deleteSession(id);
      setSessions((prev) => prev.filter((s) => s.id !== id));
      if (activeSessionId === id) {
        startNewChat();
      }
    } catch (e) {
      console.error("Failed to delete session", e);
    }
  };

  const executeTurn = (
    text: string,
    images?: string[],
    editUserMsgId?: string,
    isRerun: boolean = false
  ) => {
    const sessionId = activeSessionId || crypto.randomUUID();
    if (!activeSessionId) setActiveSessionId(sessionId);

    // Immediate session creation & display in sidebar if not already present
    const sessionExists = sessions.some((s) => s.id === sessionId);
    if (!sessionExists) {
      const trimmed = text.trim();
      const title = (trimmed.slice(0, 36) || "New Conversation") + (trimmed.length > 36 ? "..." : "");
      const optimisticSession: ChatSession = {
        id: sessionId,
        title,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      setSessions((prev) => [optimisticSession, ...prev.filter((s) => s.id !== sessionId)]);
      api.createSession(title, sessionId).catch((e) => console.error("Failed to create session immediately", e));
    }

    const assistantMsgId = crypto.randomUUID();
    let targetUserMsgId = editUserMsgId;
    let activeVersions: ChatMessageVersion[] | undefined = undefined;
    let activeVersionIdx: number | undefined = undefined;

    if (editUserMsgId) {
      const userMsgIdx = messages.findIndex((m) => m.id === editUserMsgId);
      if (userMsgIdx !== -1) {
        const existingUserMsg = messages[userMsgIdx];
        const existingAssistantMsg = messages[userMsgIdx + 1];

        // Ensure previous versions capture the current assistant response before branching
        const currentVerIdx = existingUserMsg.versionIndex ?? 0;
        const prevVersions: ChatMessageVersion[] = existingUserMsg.versions && existingUserMsg.versions.length > 0
          ? existingUserMsg.versions.map((v, i) =>
              i === currentVerIdx && existingAssistantMsg
                ? {
                    ...v,
                    assistantResponse: {
                      content: existingAssistantMsg.content,
                      jobCards: existingAssistantMsg.jobCards,
                      createdAt: existingAssistantMsg.createdAt,
                    },
                  }
                : v
            )
          : [
              {
                content: existingUserMsg.content,
                images: existingUserMsg.images || [],
                assistantResponse: existingAssistantMsg
                  ? {
                      content: existingAssistantMsg.content,
                      jobCards: existingAssistantMsg.jobCards,
                      createdAt: existingAssistantMsg.createdAt,
                    }
                  : undefined,
              },
            ];

        const newVersion: ChatMessageVersion = {
          content: text,
          images: images || existingUserMsg.images || [],
          assistantResponse: {
            content: "",
            jobCards: [],
            createdAt: new Date().toISOString(),
          },
        };

        const updatedVersions = [...prevVersions, newVersion];
        const newVersionIdx = updatedVersions.length - 1;
        activeVersions = updatedVersions;
        activeVersionIdx = newVersionIdx;

        const updatedUserMsg: ChatMessage = {
          ...existingUserMsg,
          content: text,
          images: images || existingUserMsg.images || [],
          versions: updatedVersions,
          versionIndex: newVersionIdx,
        };

        const assistantMsg: ChatMessage = {
          id: assistantMsgId,
          role: "assistant",
          content: "",
          statusText: "Sensa AI is reasoning...",
          jobCards: [],
          createdAt: new Date().toISOString(),
        };

        // In-place replacement: keep earlier messages, replace user + assistant, truncate subsequent
        setMessages([...messages.slice(0, userMsgIdx), updatedUserMsg, assistantMsg]);
      } else {
        // Fallback: append normally
        const userMsg: ChatMessage = {
          id: crypto.randomUUID(),
          role: "user",
          content: text,
          images: images || [],
          createdAt: new Date().toISOString(),
          versions: [{ content: text, images: images || [] }],
          versionIndex: 0,
        };
        targetUserMsgId = userMsg.id;
        const assistantMsg: ChatMessage = {
          id: assistantMsgId,
          role: "assistant",
          content: "",
          statusText: "Sensa AI is reasoning...",
          jobCards: [],
          createdAt: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, userMsg, assistantMsg]);
      }
    } else {
      const userMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: text,
        images: images || [],
        createdAt: new Date().toISOString(),
        versions: [{ content: text, images: images || [] }],
        versionIndex: 0,
      };
      targetUserMsgId = userMsg.id;
      const assistantMsg: ChatMessage = {
        id: assistantMsgId,
        role: "assistant",
        content: "",
        statusText: "Sensa AI is reasoning...",
        jobCards: [],
        createdAt: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMsg, assistantMsg]);
    }

    setIsStreaming(true);

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    api.streamChat(
      sessionId,
      text,
      selectedModel,
      {
        onStatus: (statusText) => {
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantMsgId ? { ...m, statusText } : m))
          );
        },
        onToken: (token) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId ? { ...m, content: m.content + token } : m
            )
          );
        },
        onJobCards: (cards) => {
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantMsgId ? { ...m, jobCards: cards } : m))
          );
        },
        onAuthRequired: (authData) => {
          setIsStreaming(false);
          const platRaw = (authData.platform || "naukri").toLowerCase();
          const targetPlat: SupportedPlatform =
            platRaw === "linkedin" ? "linkedin" : platRaw === "indeed" ? "indeed" : "naukri";
          setPlatformModal({
            isOpen: true,
            platform: targetPlat,
            pendingQuery: authData.query,
          });
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId
                ? {
                    ...m,
                    content: authData.message || `Authentication required on ${targetPlat} to continue.`,
                    statusText: undefined,
                  }
                : m
            )
          );
        },
        onDone: (data) => {
          setIsStreaming(false);
          setMessages((prev) =>
            prev.map((m) => {
              if (m.id === assistantMsgId) {
                return {
                  ...m,
                  content: data.content || m.content,
                  jobCards: data.job_cards || m.jobCards,
                  statusText: undefined,
                };
              }
              if (m.id === targetUserMsgId && m.versions && m.versionIndex !== undefined) {
                const vIdx = m.versionIndex;
                const vCopy = [...m.versions];
                if (vCopy[vIdx]) {
                  vCopy[vIdx] = {
                    ...vCopy[vIdx],
                    assistantResponse: {
                      content: data.content || "",
                      jobCards: data.job_cards || [],
                      createdAt: new Date().toISOString(),
                    },
                  };
                  return { ...m, versions: vCopy };
                }
              }
              return m;
            })
          );
          loadSessions();
          loadJobCounts();
        },
        onError: (err) => {
          setIsStreaming(false);
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId
                ? { ...m, content: `Error: ${err.message || "Connection interrupted"}`, statusText: undefined }
                : m
            )
          );
        },
      },
      abortControllerRef.current.signal,
      images,
      editUserMsgId,
      isRerun,
      activeVersions,
      activeVersionIdx
    );
  };

  const handleSendMessage = (text: string, images?: string[]) => {
    executeTurn(text, images);
  };

  const handleStopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setIsStreaming(false);
    }
  };

  const handleRerun = (messageId: string, content: string, images?: string[]) => {
    executeTurn(content, images, messageId, true);
  };

  const handleEditMessage = (messageId: string, newContent: string) => {
    const targetMsg = messages.find((m) => m.id === messageId);
    executeTurn(newContent, targetMsg?.images, messageId, false);
  };

  const handleSwitchVersion = (messageId: string, targetVersionIndex: number) => {
    setMessages((prev) => {
      const userMsgIdx = prev.findIndex((m) => m.id === messageId);
      if (userMsgIdx === -1) return prev;
      const userMsg = prev[userMsgIdx];
      if (!userMsg.versions || !userMsg.versions[targetVersionIndex]) return prev;

      const targetVersion = userMsg.versions[targetVersionIndex];
      const assistantMsg = prev[userMsgIdx + 1];

      // Save current assistant response into the current version before switching
      const currentVerIdx = userMsg.versionIndex ?? 0;
      const versions = [...userMsg.versions];
      if (assistantMsg && versions[currentVerIdx]) {
        versions[currentVerIdx] = {
          ...versions[currentVerIdx],
          assistantResponse: {
            content: assistantMsg.content,
            jobCards: assistantMsg.jobCards,
            createdAt: assistantMsg.createdAt,
          },
        };
      }

      // Updated user message with swapped version
      const updatedUserMsg: ChatMessage = {
        ...userMsg,
        content: targetVersion.content,
        images: targetVersion.images || [],
        versions,
        versionIndex: targetVersionIndex,
      };

      // Updated assistant message with swapped response
      const updatedAssistantMsg: ChatMessage = assistantMsg
        ? {
            ...assistantMsg,
            content: targetVersion.assistantResponse?.content || "",
            jobCards: targetVersion.assistantResponse?.jobCards || [],
            statusText: undefined,
          }
        : {
            id: crypto.randomUUID(),
            role: "assistant",
            content: targetVersion.assistantResponse?.content || "",
            jobCards: targetVersion.assistantResponse?.jobCards || [],
            createdAt: targetVersion.assistantResponse?.createdAt || new Date().toISOString(),
          };

      const nextMessages = [...prev];
      nextMessages[userMsgIdx] = updatedUserMsg;
      if (userMsgIdx + 1 < nextMessages.length && nextMessages[userMsgIdx + 1].role === "assistant") {
        nextMessages[userMsgIdx + 1] = updatedAssistantMsg;
      } else {
        nextMessages.splice(userMsgIdx + 1, 0, updatedAssistantMsg);
      }
      return nextMessages;
    });
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#0d0e14] font-sans antialiased text-slate-100">
      {/* Desktop Collapsible Sidebar */}
      <div className={`${isDesktopSidebarOpen ? 'block' : 'hidden'} md:block transition-all duration-200`}>
        <Sidebar
          sessions={sessions}
          activeSessionId={activeSessionId}
          onSelectSession={selectSession}
          onNewChat={startNewChat}
          onDeleteSession={handleDeleteSession}
          jobCounts={jobCounts}
          onOpenSettings={() => setIsSettingsOpen(true)}
          platformStatuses={platformStatuses}
          onOpenPlatformModal={(p) => setPlatformModal({ isOpen: true, platform: p })}
          onRefreshPlatformStatuses={loadPlatformStatuses}
          onOpenNaukriModal={() => setPlatformModal({ isOpen: true, platform: "naukri" })}
          isNaukriConnected={platformStatuses.naukri.connected}
          onRefreshNaukriStatus={() => loadPlatformStatuses()}
          onQueryJobStatus={(q) => handleSendMessage(q)}
          isAutoApplyEnabled={autoApplySettings.enabled}
          autoApplyBatchSize={autoApplySettings.maxBatchSize}
          onOpenTracker={handleOpenTracker}
          onClearTrackedJobs={handleQuickClearTrackedJobs}
        />
      </div>

      {/* Mobile Drawer Sidebar */}
      {isMobileSidebarOpen && (
        <div className="fixed inset-0 z-40 flex md:hidden">
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setIsMobileSidebarOpen(false)}
          />
          <div className="relative z-50 flex w-72 flex-col bg-[#11121a]">
            <Sidebar
              sessions={sessions}
              activeSessionId={activeSessionId}
              onSelectSession={selectSession}
              onNewChat={startNewChat}
              onDeleteSession={handleDeleteSession}
              jobCounts={jobCounts}
              onOpenSettings={() => setIsSettingsOpen(true)}
              platformStatuses={platformStatuses}
              onOpenPlatformModal={(p) => setPlatformModal({ isOpen: true, platform: p })}
              onRefreshPlatformStatuses={loadPlatformStatuses}
              onOpenNaukriModal={() => setPlatformModal({ isOpen: true, platform: "naukri" })}
              isNaukriConnected={platformStatuses.naukri.connected}
              onRefreshNaukriStatus={() => loadPlatformStatuses()}
              onQueryJobStatus={(q) => handleSendMessage(q)}
              isAutoApplyEnabled={autoApplySettings.enabled}
              autoApplyBatchSize={autoApplySettings.maxBatchSize}
              onOpenTracker={handleOpenTracker}
              onClearTrackedJobs={handleQuickClearTrackedJobs}
            />
          </div>
        </div>
      )}

      {/* Main Enterprise Chat Interface Area */}
      <ChatArea
        messages={messages}
        activeSessionId={activeSessionId}
        isStreaming={isStreaming}
        onSendMessage={handleSendMessage}
        onStopGeneration={handleStopGeneration}
        onOpenSettings={() => setIsSettingsOpen(true)}
        selectedModel={selectedModel}
        onSelectModel={setSelectedModel}
        onApplyClick={(job) => setConfirmJob(job)}
        onSaveSuccess={() => loadJobCounts()}
        onToggleSidebar={() => {
          setIsMobileSidebarOpen(!isMobileSidebarOpen);
          setIsDesktopSidebarOpen(!isDesktopSidebarOpen);
        }}
        resumeStatus={resumeStatus}
        onResumeUploaded={() => loadResumeStatus()}
        onResumeDeleted={() => loadResumeStatus()}
        onRerun={handleRerun}
        onEdit={handleEditMessage}
        onSwitchVersion={handleSwitchVersion}
        agentMode={agentMode}
        onSelectAgentMode={setAgentMode}
        onTailorClick={(job) => {
          setTailorJob(job);
          setStudioPreviewUrl(null);
          setIsStudioOpen(true);
        }}
        onPreviewResume={(url) => {
          setTailorJob(null);
          setStudioPreviewUrl(url);
          setIsStudioOpen(true);
        }}
      />

      {/* Sensa AI Resume Preparation Studio Modal (Agent 2) */}
      <ResumeTailorModal
        job={tailorJob}
        previewUrl={studioPreviewUrl}
        isOpen={isStudioOpen}
        onClose={() => {
          setIsStudioOpen(false);
          setTailorJob(null);
          setStudioPreviewUrl(null);
        }}
        onProceedToApply={(job) => {
          setIsStudioOpen(false);
          setTailorJob(null);
          setStudioPreviewUrl(null);
          setConfirmJob(job);
        }}
        selectedModel={selectedModel}
      />

      {/* Sensa AI ATS Resume Studio Direct Live Preview Modal */}
      <ResumePreviewModal
        isOpen={!!resumePreviewUrl}
        onClose={() => setResumePreviewUrl(null)}
        previewUrl={resumePreviewUrl}
        onOpenInStudio={(url) => {
          setResumePreviewUrl(null);
          setTailorJob(null);
          setStudioPreviewUrl(url);
          setIsStudioOpen(true);
        }}
      />

      {/* Dedicated AI Models & API Keys Settings Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        selectedModel={selectedModel}
        onModelChange={setSelectedModel}
        onSettingsSaved={(newSettings) => setAutoApplySettings(newSettings)}
      />

      {/* Unified Multi-Platform Session & Login Modal */}
      <PlatformLoginModal
        isOpen={platformModal.isOpen}
        platform={platformModal.platform}
        onClose={() => setPlatformModal((prev) => ({ ...prev, isOpen: false }))}
        pendingQuery={platformModal.pendingQuery}
        onSuccess={(_plat, query) => {
          setPlatformModal((prev) => ({ ...prev, isOpen: false }));
          loadPlatformStatuses();
          if (query) {
            handleSendMessage(query);
          }
        }}
      />

      {/* Human-in-the-Loop Apply Confirmation Modal */}
      <ApplyConfirmModal
        job={confirmJob}
        isOpen={!!confirmJob}
        onClose={() => setConfirmJob(null)}
        onSuccess={() => {
          loadJobCounts();
          setConfirmJob(null);
        }}
      />

      {/* Interactive Job Applications Tracker Manager & Delete/Clear Modal */}
      <TrackerModal
        isOpen={trackerModal.isOpen}
        initialTab={trackerModal.initialTab}
        jobCounts={jobCounts}
        onClose={() => setTrackerModal((prev) => ({ ...prev, isOpen: false }))}
        onCountsUpdated={() => loadJobCounts()}
      />
    </div>
  );
};

export default App;
