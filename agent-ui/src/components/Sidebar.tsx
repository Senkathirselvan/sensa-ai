import React, { useState } from 'react';
import {
  MessageSquare,
  Plus,
  Trash2,
  Settings,
  Search,
  Sparkles,
  ChevronDown,
  ChevronRight,
  Briefcase,
  BookmarkCheck,
  Send,
  CalendarCheck,
  LogOut,
  CheckCircle2
} from 'lucide-react';
import { ChatSession, JobCounts, PlatformAuthStatus } from '../types';
import { api } from '../services/api';
import { SupportedPlatform } from './PlatformLoginModal';

interface SidebarProps {
  sessions: ChatSession[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
  onDeleteSession: (id: string) => void;
  jobCounts: JobCounts;
  onOpenSettings: () => void;
  platformStatuses?: Record<SupportedPlatform, PlatformAuthStatus>;
  onOpenPlatformModal?: (platform: SupportedPlatform) => void;
  onRefreshPlatformStatuses?: () => void;
  onOpenNaukriModal?: () => void;
  isNaukriConnected?: boolean;
  onRefreshNaukriStatus?: () => void;
  onQueryJobStatus?: (query: string) => void;
  isAutoApplyEnabled?: boolean;
  autoApplyBatchSize?: number;
  onOpenTracker?: (tab?: 'ALL' | 'SAVED' | 'APPLIED' | 'INTERVIEW') => void;
  onClearTrackedJobs?: (status?: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  jobCounts,
  onOpenSettings,
  platformStatuses,
  onOpenPlatformModal,
  onRefreshPlatformStatuses,
  onOpenNaukriModal,
  isNaukriConnected,
  onRefreshNaukriStatus,
  onQueryJobStatus,
  isAutoApplyEnabled,
  autoApplyBatchSize,
  onOpenTracker,
  onClearTrackedJobs,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [isToolsExpanded, setIsToolsExpanded] = useState(true);
  const [disconnectingPlatform, setDisconnectingPlatform] = useState<string | null>(null);

  // Filter conversations
  const filteredSessions = sessions.filter((s) =>
    (s.title || 'Untitled Chat').toLowerCase().includes(searchQuery.toLowerCase())
  );

  const platformsConfig: Array<{
    id: SupportedPlatform;
    name: string;
    icon: string;
    iconClass: string;
    connected: boolean;
  }> = [
    {
      id: 'naukri',
      name: 'Naukri.com Scraper',
      icon: 'N',
      iconClass: 'bg-amber-500/15 text-amber-300 border-amber-500/25',
      connected: platformStatuses?.naukri?.connected ?? !!isNaukriConnected,
    },
    {
      id: 'linkedin',
      name: 'LinkedIn Easy Apply',
      icon: 'in',
      iconClass: 'bg-[#0A66C2]/20 text-[#70b5f9] border-[#0A66C2]/40',
      connected: !!platformStatuses?.linkedin?.connected,
    },
    {
      id: 'indeed',
      name: 'Indeed Instant Apply',
      icon: 'I',
      iconClass: 'bg-[#2164f3]/20 text-[#60a5fa] border-[#2164f3]/40',
      connected: !!platformStatuses?.indeed?.connected,
    },
  ];

  // Clear Platform session handler
  const handleClearPlatformSession = async (e: React.MouseEvent, platId: SupportedPlatform) => {
    e.stopPropagation();
    const platName = platId === 'linkedin' ? 'LinkedIn' : platId === 'indeed' ? 'Indeed' : 'Naukri';
    if (!confirm(`Are you sure you want to clear your active ${platName} session?`)) return;
    try {
      setDisconnectingPlatform(platId);
      await api.disconnectPlatform(platId);
      if (onRefreshPlatformStatuses) onRefreshPlatformStatuses();
      if (onRefreshNaukriStatus) onRefreshNaukriStatus();
    } catch (err: any) {
      alert(`Failed to clear session: ${err.message || 'Error'}`);
    } finally {
      setDisconnectingPlatform(null);
    }
  };

  const handleConnectPlatform = (platId: SupportedPlatform) => {
    if (onOpenPlatformModal) {
      onOpenPlatformModal(platId);
    } else if (platId === 'naukri' && onOpenNaukriModal) {
      onOpenNaukriModal();
    }
  };

  // Group conversations by recency
  const groupSessionsByDate = () => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    const sevenDaysAgo = new Date(today);
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

    const groups: { [key: string]: ChatSession[] } = {
      Today: [],
      Yesterday: [],
      'Previous 7 Days': [],
      Older: [],
    };

    filteredSessions.forEach((s) => {
      const date = new Date(s.updated_at || s.created_at || Date.now());
      if (date >= today) {
        groups.Today.push(s);
      } else if (date >= yesterday) {
        groups.Yesterday.push(s);
      } else if (date >= sevenDaysAgo) {
        groups['Previous 7 Days'].push(s);
      } else {
        groups.Older.push(s);
      }
    });

    return groups;
  };

  const grouped = groupSessionsByDate();

  return (
    <aside className="w-64 md:w-72 h-screen flex flex-col bg-[#11121a] border-r border-[#1f2130] text-slate-300 select-none shrink-0 z-30">
      {/* Brand Header */}
      <div className="p-3.5 pb-2 border-b border-[#1f2130] flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-purple-600 flex items-center justify-center text-white shadow-md shadow-blue-500/20 font-bold text-sm">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="font-bold text-sm text-slate-100 tracking-tight">Sensa AI</span>
              <span className="text-[9px] font-extrabold uppercase px-1.5 py-0.2 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
                Enterprise
              </span>
            </div>
            <span className="text-[10.5px] text-slate-400 font-medium">Universal Agent Hub</span>
          </div>
        </div>
      </div>

      {/* New Conversation Button & Search */}
      <div className="p-3 space-y-2">
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl bg-[#181926] hover:bg-[#202235] border border-[#27293d] hover:border-blue-500/40 text-xs font-semibold text-slate-100 transition-all group shadow-sm"
        >
          <span className="flex items-center gap-2">
            <Plus className="w-4 h-4 text-blue-400 group-hover:scale-110 transition-transform" />
            New Conversation
          </span>
          <span className="text-[10px] font-mono text-slate-500 bg-[#12131d] px-1.5 py-0.5 rounded border border-white/5">
            ⌘K
          </span>
        </button>

        {/* Search Bar */}
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-2.5" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search conversations..."
            className="w-full bg-[#151622] border border-[#232537] rounded-xl pl-8 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
          />
        </div>
      </div>

      {/* Conversations List Grouped by Recency */}
      <div className="flex-1 overflow-y-auto px-2 space-y-4">
        {filteredSessions.length === 0 ? (
          <div className="h-44 flex flex-col items-center justify-center text-center p-4">
            <MessageSquare className="w-6 h-6 text-slate-600 mb-2 stroke-[1.5]" />
            <span className="text-xs font-medium text-slate-400">No conversations found</span>
            <span className="text-[11px] text-slate-600">Start a new chat to begin</span>
          </div>
        ) : (
          Object.entries(grouped).map(([category, items]) => {
            if (items.length === 0) return null;
            return (
              <div key={category} className="space-y-1">
                <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500 px-3 py-1">
                  {category}
                </div>
                {items.map((session) => {
                  const isActive = activeSessionId === session.id;
                  return (
                    <div
                      key={session.id}
                      onClick={() => onSelectSession(session.id)}
                      className={`group relative flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium cursor-pointer transition-all ${
                        isActive
                          ? 'bg-[#1e2032] text-slate-100 border border-blue-500/30 shadow-sm'
                          : 'text-slate-400 hover:text-slate-200 hover:bg-[#161724]'
                      }`}
                    >
                      <div className="flex items-center gap-2.5 min-w-0 flex-1">
                        <MessageSquare
                          className={`w-3.5 h-3.5 shrink-0 ${
                            isActive ? 'text-blue-400' : 'text-slate-500 group-hover:text-slate-300'
                          }`}
                        />
                        <span className="truncate">{session.title || 'New Conversation'}</span>
                      </div>

                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onDeleteSession(session.id);
                        }}
                        className="opacity-0 group-hover:opacity-100 p-1 text-slate-500 hover:text-rose-400 hover:bg-[#25283f] rounded transition-all"
                        title="Delete chat"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  );
                })}
              </div>
            );
          })
        )}
      </div>

      {/* Dedicated Career Agent Tools (Collapsible Drawer for Job Finding & Apply Agent) */}
      <div className="border-t border-[#1f2130] bg-[#0f1017]">
        <button
          onClick={() => setIsToolsExpanded(!isToolsExpanded)}
          className="w-full flex items-center justify-between px-3.5 py-2.5 text-xs font-bold text-slate-400 hover:text-slate-200 hover:bg-[#151624] transition-colors"
        >
          <span className="flex items-center gap-1.5">
            <Briefcase className="w-3.5 h-3.5 text-blue-400" /> Career Agent Tools
          </span>
          <div className="flex items-center gap-1.5">
            <span className="text-[9px] px-1.5 py-0.2 rounded bg-blue-500/10 text-blue-400 font-semibold border border-blue-500/20">
              Job Agent
            </span>
            {isToolsExpanded ? (
              <ChevronDown className="w-3.5 h-3.5 text-slate-500" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5 text-slate-500" />
            )}
          </div>
        </button>

        {isToolsExpanded && (
          <div className="px-3 pb-3 space-y-2">
            {/* Multi-Platform Authenticated Connectors */}
            {platformsConfig.map((plat) => (
              <div
                key={plat.id}
                className={`p-2 rounded-xl bg-[#151622] border transition flex items-center justify-between ${
                  plat.connected
                    ? 'border-emerald-500/30'
                    : 'border-[#232537] hover:border-blue-500/30'
                }`}
              >
                <div className="flex items-center gap-2 min-w-0">
                  <div
                    className={`h-6 w-6 rounded-lg border flex items-center justify-center text-[10.5px] font-bold shrink-0 ${plat.iconClass}`}
                  >
                    {plat.icon}
                  </div>
                  <div className="min-w-0">
                    <div className="text-[11px] font-semibold text-slate-200 truncate">{plat.name}</div>
                    <div className="text-[9.5px] text-slate-400 flex items-center gap-1">
                      {plat.connected ? (
                        <span className="text-emerald-400 font-medium flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                          Authenticated
                        </span>
                      ) : (
                        <span>Not Connected</span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Action buttons (Clear / Connect) */}
                <div className="flex items-center gap-1 shrink-0">
                  {plat.connected ? (
                    <button
                      type="button"
                      onClick={(e) => handleClearPlatformSession(e, plat.id)}
                      disabled={disconnectingPlatform === plat.id}
                      className="px-2 py-0.5 rounded-lg text-[10px] font-semibold text-rose-400 hover:text-rose-100 hover:bg-rose-500/20 border border-rose-500/30 flex items-center gap-1 transition-all shadow-sm"
                      title="Clear saved session cookies & logout"
                    >
                      <LogOut className="w-2.5 h-2.5" />
                      <span>Clear</span>
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => handleConnectPlatform(plat.id)}
                      className="text-[10px] px-2 py-0.5 rounded-lg font-semibold bg-blue-600 hover:bg-blue-500 text-white shadow-sm transition-colors"
                    >
                      Connect
                    </button>
                  )}
                </div>
              </div>
            ))}

            {/* Career Metrics - Specifically for Job Finding & Apply Agent */}
            <div>
              <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-slate-400 px-1 mb-1.5">
                <div className="flex items-center gap-1.5">
                  <span>Job Applications Tracker</span>
                  <button
                    type="button"
                    onClick={() => onOpenTracker?.('ALL')}
                    className="text-[9px] px-1.5 py-0.5 rounded bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 border border-blue-500/20 transition-colors font-medium flex items-center gap-0.5"
                    title="Open Tracker Manager & Delete/Clear Counts"
                  >
                    Manage
                  </button>
                </div>
                {isAutoApplyEnabled ? (
                  <span className="text-[9px] font-bold text-emerald-400 flex items-center gap-1 bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20 animate-fade-in" title="Batch Auto-Apply Mode is Active">
                    ⚡ Auto ({autoApplyBatchSize || 5})
                  </span>
                ) : (
                  <button
                    type="button"
                    onClick={() => onOpenTracker?.('ALL')}
                    className="text-[9px] text-slate-500 hover:text-slate-300 transition-colors font-normal"
                  >
                    Click to manage
                  </button>
                )}
              </div>
              <div className="grid grid-cols-3 gap-1.5">
                <div className="relative group">
                  <button
                    type="button"
                    onClick={() => onOpenTracker ? onOpenTracker('SAVED') : onQueryJobStatus?.("Show my saved jobs")}
                    className="w-full p-2 rounded-xl bg-[#151622] hover:bg-[#1a1b2a] border border-[#232537] hover:border-blue-500/30 text-center transition-all"
                    title="View & Manage Saved Jobs"
                  >
                    <span className="text-[9.5px] font-semibold text-slate-400 flex items-center justify-center gap-1 group-hover:text-blue-400">
                      <BookmarkCheck className="w-3 h-3 text-blue-400" /> Saved
                    </span>
                    <span className="text-sm font-bold text-slate-200 mt-0.5 block">{jobCounts.SAVED}</span>
                  </button>
                  {jobCounts.SAVED > 0 && onClearTrackedJobs && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onClearTrackedJobs('SAVED');
                      }}
                      className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 p-1 rounded-md text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-all"
                      title="Clear saved count"
                    >
                      <Trash2 className="w-2.5 h-2.5" />
                    </button>
                  )}
                </div>

                <div className="relative group">
                  <button
                    type="button"
                    onClick={() => onOpenTracker ? onOpenTracker('APPLIED') : onQueryJobStatus?.("Show my applied jobs and their application status")}
                    className="w-full p-2 rounded-xl bg-[#151622] hover:bg-[#1a1b2a] border border-[#232537] hover:border-emerald-500/30 text-center transition-all"
                    title="View & Manage Applied Jobs"
                  >
                    <span className="text-[9.5px] font-semibold text-slate-400 flex items-center justify-center gap-1 group-hover:text-emerald-400">
                      <Send className="w-3 h-3 text-emerald-400" /> Applied
                    </span>
                    <span className="text-sm font-bold text-slate-200 mt-0.5 block">{jobCounts.APPLIED}</span>
                  </button>
                  {jobCounts.APPLIED > 0 && onClearTrackedJobs && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onClearTrackedJobs('APPLIED');
                      }}
                      className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 p-1 rounded-md text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-all"
                      title="Clear applied count"
                    >
                      <Trash2 className="w-2.5 h-2.5" />
                    </button>
                  )}
                </div>

                <div className="relative group">
                  <button
                    type="button"
                    onClick={() => onOpenTracker ? onOpenTracker('INTERVIEW') : onQueryJobStatus?.("Show my interview scheduled jobs")}
                    className="w-full p-2 rounded-xl bg-[#151622] hover:bg-[#1a1b2a] border border-[#232537] hover:border-purple-500/30 text-center transition-all"
                    title="View & Manage Interviews"
                  >
                    <span className="text-[9.5px] font-semibold text-slate-400 flex items-center justify-center gap-1 group-hover:text-purple-400">
                      <CalendarCheck className="w-3 h-3 text-purple-400" /> Interview
                    </span>
                    <span className="text-sm font-bold text-slate-200 mt-0.5 block">{jobCounts.INTERVIEW}</span>
                  </button>
                  {jobCounts.INTERVIEW > 0 && onClearTrackedJobs && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onClearTrackedJobs('INTERVIEW');
                      }}
                      className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 p-1 rounded-md text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-all"
                      title="Clear interview count"
                    >
                      <Trash2 className="w-2.5 h-2.5" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* User Profile & Workspace Footer (Settings Gear strictly here) */}
      <div className="p-3 border-t border-[#1f2130] bg-[#0d0e14] flex items-center justify-between">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-7 h-7 rounded-lg bg-blue-600/20 border border-blue-500/30 text-blue-400 flex items-center justify-center text-xs font-bold shrink-0">
            SS
          </div>
          <div className="min-w-0">
            <div className="text-xs font-semibold text-slate-200 truncate">S. Senkathirselvan</div>
            <div className="text-[10px] text-emerald-400 font-medium flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              Enterprise Workspace
            </div>
          </div>
        </div>

        {/* Left Side Settings Icon (The only place settings is opened from) */}
        <button
          onClick={onOpenSettings}
          className="p-1.5 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-[#1a1b29] transition-colors"
          title="AI Models & API Keys Settings"
        >
          <Settings className="w-4 h-4" />
        </button>
      </div>
    </aside>
  );
};
