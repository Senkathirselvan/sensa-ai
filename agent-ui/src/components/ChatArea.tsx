import React, { useRef, useEffect, useState } from 'react';
import {
  Sparkles,
  Briefcase,
  Code2,
  FileSearch,
  Menu,
  ChevronDown,
  BrainCircuit,
  Key,
  ArrowDown
} from 'lucide-react';
import { ChatMessage as ChatMessageType, JobCard as JobCardType, ResumeStatus, AgentMode } from '../types';
import { ChatMessage } from './ChatMessage';
import { ChatInput } from './ChatInput';
import { AgentLiveDock } from './AgentLiveDock';

interface ChatAreaProps {
  messages: ChatMessageType[];
  isStreaming: boolean;
  onSendMessage: (message: string, images?: string[]) => void;
  onStopGeneration: () => void;
  onOpenSettings: () => void;
  selectedModel: string;
  onSelectModel: (model: string) => void;
  onApplyClick: (job: JobCardType) => void;
  onSaveSuccess: () => void;
  onToggleSidebar?: () => void;
  resumeStatus?: ResumeStatus | null;
  onResumeUploaded?: () => void;
  onResumeDeleted?: () => void;
  onRerun?: (messageId: string, content: string, images?: string[]) => void;
  onEdit?: (messageId: string, newContent: string) => void;
  onSwitchVersion?: (messageId: string, versionIndex: number) => void;
  agentMode?: AgentMode;
  onSelectAgentMode?: (mode: AgentMode) => void;
  onTailorClick?: (job: JobCardType) => void;
  onPreviewResume?: (url: string) => void;
  activeSessionId?: string | null;
}

export const ChatArea: React.FC<ChatAreaProps> = ({
  messages,
  isStreaming,
  onSendMessage,
  onStopGeneration,
  onOpenSettings,
  selectedModel,
  onSelectModel,
  onApplyClick,
  onSaveSuccess,
  onToggleSidebar,
  resumeStatus,
  onResumeUploaded,
  onResumeDeleted,
  onRerun,
  onEdit,
  onSwitchVersion,
  onTailorClick,
  onPreviewResume,
  activeSessionId,
}) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const isAtBottomRef = useRef<boolean>(true);
  const [showScrollBottomBtn, setShowScrollBottomBtn] = useState(false);
  const [isModelDropdownOpen, setIsModelDropdownOpen] = useState(false);

  const scrollToBottom = (smooth = true) => {
    if (scrollContainerRef.current) {
      if (smooth) {
        scrollContainerRef.current.scrollTo({
          top: scrollContainerRef.current.scrollHeight,
          behavior: 'smooth'
        });
      } else {
        scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
      }
    } else {
      messagesEndRef.current?.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto' });
    }
    isAtBottomRef.current = true;
    setShowScrollBottomBtn(false);
  };

  const handleScroll = () => {
    if (!scrollContainerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollContainerRef.current;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
    // If within 120px of bottom, consider user as "at bottom"
    const atBottom = distanceFromBottom < 120;
    isAtBottomRef.current = atBottom;
    setShowScrollBottomBtn(!atBottom);
  };

  // Reset scroll on session switch or new chat
  useEffect(() => {
    isAtBottomRef.current = true;
    setShowScrollBottomBtn(false);
    setTimeout(() => scrollToBottom(false), 50);
  }, [activeSessionId]);

  // Smart auto-scroll: ONLY scroll if user is currently at the bottom
  useEffect(() => {
    if (messages.length === 0) return;
    const lastMsg = messages[messages.length - 1];

    // If user just sent a new prompt, snap immediately to bottom
    if (lastMsg && lastMsg.role === 'user') {
      isAtBottomRef.current = true;
      scrollToBottom(false);
      return;
    }

    // During streaming or new assistant token: ONLY scroll if user hasn't scrolled up!
    if (isAtBottomRef.current) {
      if (scrollContainerRef.current) {
        // Use instant scroll (not smooth) during streaming to prevent jitter and scroll fighting
        scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
      }
    }
  }, [messages, isStreaming]);

  const capabilityCards = [
    {
      category: 'Career Intelligence',
      title: 'Find Live Tech Jobs',
      desc: 'Query verified openings across Naukri, LinkedIn, and Indeed with freshness filters',
      prompt: 'Find Python Backend Developer jobs in Chennai posted within the last 3 days',
      icon: <Briefcase className="w-4 h-4 text-blue-400" />,
      badge: 'All Platforms',
      badgeColor: 'border-blue-500/20 text-blue-400 bg-blue-500/10',
    },
    {
      category: 'Profile Matching',
      title: 'Match & Score Resume',
      desc: 'Evaluate your resume profile against jobs with exact skill overlap and gap analysis',
      prompt: 'Analyze my uploaded resume and find top matching jobs in India with score percentages',
      icon: <FileSearch className="w-4 h-4 text-emerald-400" />,
      badge: 'Multi-Factor',
      badgeColor: 'border-emerald-500/20 text-emerald-400 bg-emerald-500/10',
    },
    {
      category: 'Software Architecture',
      title: 'System Design & Code',
      desc: 'Architect scalable FastAPI, Django, Celery backends, REST APIs, and database schemas',
      prompt: 'Design a scalable multi-tenant SaaS architecture with FastAPI, JWT auth, and Redis caching',
      icon: <Code2 className="w-4 h-4 text-purple-400" />,
      badge: 'Engineering',
      badgeColor: 'border-purple-500/20 text-purple-400 bg-purple-500/10',
    },
    {
      category: 'Technical Reasoning',
      title: 'Deep Research & Analysis',
      desc: 'Compare database engines, optimize complex queries, or draft technical engineering specs',
      prompt: 'Compare MySQL vs PostgreSQL performance benchmarks for high-write SaaS applications',
      icon: <BrainCircuit className="w-4 h-4 text-amber-400" />,
      badge: 'Reasoning',
      badgeColor: 'border-amber-500/20 text-amber-400 bg-amber-500/10',
    },
  ];

  const modelItems = [
    {
      id: 'auto',
      name: 'Smart 3-Tier Cascade',
      subtitle: 'Claude ➡️ Gemini ➡️ Local Ollama',
      icon: '🎯',
    },
    {
      id: 'claude-3-5-haiku',
      name: 'Claude 3.5 Haiku',
      subtitle: 'Fast cloud intelligence & reasoning',
      icon: '⚡',
    },
    {
      id: 'gemini-1.5-flash',
      name: 'Gemini 1.5 Flash',
      subtitle: 'Sub-second speed (1500 req/day free)',
      icon: '💎',
    },
    {
      id: 'qwen2.5',
      name: 'Local Ollama (Qwen 2.5)',
      subtitle: '100% private & unlimited offline',
      icon: '🏠',
    },
  ];

  const currentModelLabel = () => {
    if (selectedModel === 'auto') return '🎯 Auto Cascade';
    if (selectedModel.includes('claude')) return '⚡ Claude 3.5';
    if (selectedModel.includes('gemini')) return '💎 Gemini Flash';
    return '🏠 Local Ollama';
  };

  return (
    <main className="flex-1 h-screen flex flex-col bg-[#0e0f16] relative overflow-hidden select-text text-slate-100">
      {/* Top Enterprise App Bar */}
      <header className="h-14 border-b border-[#1f2130] flex items-center justify-between px-4 md:px-6 bg-[#12131d]/90 backdrop-blur-md z-20 shrink-0">
        <div className="flex items-center gap-3">
          {onToggleSidebar && (
            <button
              onClick={onToggleSidebar}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-[#1e202f] md:hidden transition-colors"
              title="Toggle Sidebar"
            >
              <Menu className="w-5 h-5" />
            </button>
          )}

          {/* Workspace Title & Agent Hub Pill */}
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-slate-100 tracking-tight flex items-center gap-2">
              <span className="w-5 h-5 rounded-md bg-gradient-to-tr from-blue-600 via-indigo-600 to-purple-600 flex items-center justify-center text-white shadow-sm shadow-blue-500/20">
                <Sparkles className="w-3 h-3" />
              </span>
              Sensa AI
            </span>
            <span className="text-slate-600 font-light">/</span>
            <span className="text-xs font-medium text-slate-300">Enterprise Agent Hub</span>
          </div>
        </div>

        {/* Right Tools: ONLY Model Selector Dropdown (No + icon, No Settings icon as requested) */}
        <div className="flex items-center gap-2">
          <div className="relative">
            <button
              onClick={() => setIsModelDropdownOpen(!isModelDropdownOpen)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-[#171825] hover:bg-[#1e2030] border border-[#27293d] hover:border-blue-500/40 text-xs font-semibold text-slate-200 transition-all shadow-sm"
            >
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>{currentModelLabel()}</span>
              <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
            </button>

            {isModelDropdownOpen && (
              <>
                <div
                  className="fixed inset-0 z-30"
                  onClick={() => setIsModelDropdownOpen(false)}
                />
                <div className="absolute right-0 mt-1.5 w-64 rounded-xl bg-[#171825] border border-[#2c2f46] shadow-2xl p-1.5 z-40 space-y-1 animate-scale-up">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-2 py-1">
                    Select Execution Tier
                  </div>
                  {modelItems.map((m) => (
                    <button
                      key={m.id}
                      onClick={() => {
                        onSelectModel(m.id);
                        setIsModelDropdownOpen(false);
                      }}
                      className={`w-full text-left px-2.5 py-2 rounded-lg text-xs font-medium transition-colors flex items-start gap-2.5 ${
                        selectedModel === m.id
                          ? 'bg-blue-600/15 text-blue-300 border border-blue-500/30'
                          : 'text-slate-300 hover:bg-[#202235] hover:text-white'
                      }`}
                    >
                      <span className="text-base leading-none">{m.icon}</span>
                      <div className="min-w-0 flex-1">
                        <div className="font-semibold text-slate-200">{m.name}</div>
                        <div className="text-[10px] text-slate-400 truncate">{m.subtitle}</div>
                      </div>
                    </button>
                  ))}
                  <div className="pt-1 border-t border-[#25283c]">
                    <button
                      onClick={() => {
                        setIsModelDropdownOpen(false);
                        onOpenSettings();
                      }}
                      className="w-full text-left px-2.5 py-1.5 rounded-lg text-[11px] font-medium text-blue-400 hover:bg-[#202235] flex items-center justify-between"
                    >
                      <span className="flex items-center gap-1.5">
                        <Key className="w-3 h-3" /> Configure API Keys
                      </span>
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Messages Scroll Area */}
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto relative custom-scrollbar"
      >
        {messages.length === 0 ? (
          <div className="max-w-3xl mx-auto h-full flex flex-col items-center justify-center p-6 text-center">
            {/* Enterprise Logo Badge */}
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-purple-600 p-[1px] mb-5 shadow-xl shadow-blue-500/15">
              <div className="w-full h-full bg-[#13141f] rounded-[15px] flex items-center justify-center text-blue-400">
                <Sparkles className="w-7 h-7 animate-pulse" />
              </div>
            </div>

            {/* Personalized Header */}
            <h2 className="text-2xl md:text-3xl font-bold tracking-tight text-slate-100 mb-2">
              How can I help you today, Senkathirselvan?
            </h2>
            <p className="text-xs md:text-sm text-slate-400 max-w-lg mb-8 leading-relaxed">
              Autonomous multi-agent intelligence for live job discovery across Naukri, LinkedIn, and Indeed,
              full-stack system architecture, and deep technical reasoning.
            </p>

            {/* 4 Multi-Agent Capability Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 w-full text-left">
              {capabilityCards.map((card, idx) => (
                <div
                  key={idx}
                  onClick={() => onSendMessage(card.prompt)}
                  className="p-4 rounded-2xl bg-[#141520] hover:bg-[#1a1c2b] border border-[#232537] hover:border-blue-500/40 cursor-pointer transition-all duration-200 group shadow-md hover:shadow-blue-500/5 hover:-translate-y-0.5"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="w-7 h-7 rounded-xl bg-[#1c1e2d] border border-white/5 flex items-center justify-center group-hover:scale-105 transition-transform">
                      {card.icon}
                    </div>
                    <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border ${card.badgeColor}`}>
                      {card.badge}
                    </span>
                  </div>
                  <h3 className="text-sm font-semibold text-slate-200 group-hover:text-white transition-colors mb-1">
                    {card.title}
                  </h3>
                  <p className="text-xs text-slate-400 group-hover:text-slate-300 transition-colors line-clamp-2 leading-relaxed">
                    {card.desc}
                  </p>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="w-full divide-y divide-[#1b1d2a]">
            {messages.map((msg, index) => (
              <ChatMessage
                key={msg.id || index}
                message={msg}
                isStreaming={isStreaming && index === messages.length - 1 && msg.role === 'assistant'}
                onApplyClick={onApplyClick}
                onSaveSuccess={onSaveSuccess}
                onRerun={onRerun}
                onEdit={onEdit}
                onSwitchVersion={onSwitchVersion}
                onTailorClick={onTailorClick}
                onPreviewResume={onPreviewResume}
              />
            ))}
            <div ref={messagesEndRef} className="h-6" />
          </div>
        )}
      </div>

      {/* Floating Jump to Bottom Button when user scrolls up */}
      {showScrollBottomBtn && (
        <button
          type="button"
          onClick={() => scrollToBottom(true)}
          className={`absolute ${isStreaming ? 'bottom-56' : 'bottom-28'} right-8 z-30 px-3.5 py-1.5 rounded-full bg-[#161726]/95 hover:bg-blue-600 border border-blue-500/30 hover:border-blue-500 text-xs font-semibold text-slate-200 hover:text-white shadow-2xl backdrop-blur-md transition-all flex items-center gap-2 animate-fade-in group cursor-pointer`}
          title="Scroll to latest messages"
        >
          <ArrowDown className="w-3.5 h-3.5 text-blue-400 group-hover:text-white transition-colors" />
          <span>Latest messages</span>
          {isStreaming && (
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          )}
        </button>
      )}

      {/* Pinned Bottom Live Execution Dock during Agent Processing */}
      {(() => {
        const activeAssistantMsg =
          isStreaming && messages.length > 0 && messages[messages.length - 1].role === 'assistant'
            ? messages[messages.length - 1]
            : null;

        if (!activeAssistantMsg) return null;

        return (
          <div className="w-full max-w-3xl mx-auto px-4 z-20">
            <AgentLiveDock
              statusText={activeAssistantMsg.statusText || 'Sensa AI is processing multi-step workflow...'}
              jobCards={activeAssistantMsg.jobCards || []}
              onStop={onStopGeneration}
              onJobClick={(job) => onApplyClick(job)}
            />
          </div>
        );
      })()}

      {/* Floating Chat Input Dock */}
      <ChatInput
        onSendMessage={onSendMessage}
        onStopGeneration={onStopGeneration}
        isStreaming={isStreaming}
        selectedModel={selectedModel}
        activeSessionId={activeSessionId}
        resumeStatus={resumeStatus}
        onResumeUploaded={onResumeUploaded}
        onResumeDeleted={onResumeDeleted}
      />
    </main>
  );
};
