import React from 'react';
import {
  Sparkles,
  Square,
  Loader2,
  Send,
  FileText,
  Search,
  CheckCircle2,
  ExternalLink,
  Building2,
  Zap
} from 'lucide-react';
import { JobCard } from '../types';

interface AgentLiveDockProps {
  statusText: string;
  jobCards?: JobCard[];
  onStop: () => void;
  onJobClick?: (job: JobCard) => void;
}

export const AgentLiveDock: React.FC<AgentLiveDockProps> = ({
  statusText,
  jobCards = [],
  onStop,
  onJobClick,
}) => {
  // Infer progress percentage from [x/y] pattern or keywords
  let progressPercent = 35;
  const ratioMatch = statusText.match(/\[(\d+)\/(\d+)\]/);
  if (ratioMatch) {
    const cur = parseInt(ratioMatch[1], 10);
    const tot = parseInt(ratioMatch[2], 10);
    if (tot > 0) {
      progressPercent = Math.min(Math.round((cur / tot) * 90), 95);
    }
  } else if (statusText.toLowerCase().includes('submitting') || statusText.toLowerCase().includes('apply')) {
    progressPercent = 75;
  } else if (statusText.toLowerCase().includes('tailor') || statusText.toLowerCase().includes('resume')) {
    progressPercent = 50;
  } else if (statusText.toLowerCase().includes('search') || statusText.toLowerCase().includes('query')) {
    progressPercent = 25;
  }

  // Detect platform pill
  const textLower = statusText.toLowerCase();
  const platformName = textLower.includes('naukri')
    ? 'Naukri.com'
    : textLower.includes('linkedin')
    ? 'LinkedIn'
    : textLower.includes('indeed')
    ? 'Indeed'
    : null;

  // Detect stage
  const stageBadge = textLower.includes('submitting') || textLower.includes('apply')
    ? { label: 'Autonomous Apply', color: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20', icon: <Send className="w-3 h-3" /> }
    : textLower.includes('tailor') || textLower.includes('resume')
    ? { label: 'Resume Tailoring', color: 'bg-purple-500/10 text-purple-400 border-purple-500/20', icon: <FileText className="w-3 h-3" /> }
    : textLower.includes('score') || textLower.includes('rank')
    ? { label: 'Match Scoring', color: 'bg-amber-500/10 text-amber-400 border-amber-500/20', icon: <Zap className="w-3 h-3" /> }
    : { label: 'Job Intelligence', color: 'bg-blue-500/10 text-blue-400 border-blue-500/20', icon: <Search className="w-3 h-3" /> };

  return (
    <div className="w-full mb-3 rounded-2xl bg-[#13141f]/95 border border-blue-500/25 shadow-2xl shadow-blue-900/10 backdrop-blur-xl overflow-hidden transition-all animate-fade-in">
      
      {/* Top Header Row */}
      <div className="px-4 py-2.5 bg-[#171929]/70 border-b border-[#22253a] flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-6 h-6 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400 shrink-0">
            <Sparkles className="w-3.5 h-3.5 animate-pulse" />
          </div>
          <span className="text-xs font-bold text-slate-200 tracking-tight flex items-center gap-1.5">
            Agent Execution in Progress
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping inline-block" />
          </span>

          {/* Dynamic Stage Pill */}
          <span className={`hidden sm:inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full border ${stageBadge.color}`}>
            {stageBadge.icon}
            {stageBadge.label}
          </span>

          {platformName && (
            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
              {platformName}
            </span>
          )}
        </div>

        {/* Right Action: Progress & Stop Button */}
        <div className="flex items-center gap-2.5 shrink-0">
          <span className="text-[11px] font-mono font-semibold text-blue-400">
            {progressPercent}%
          </span>
          <button
            type="button"
            onClick={onStop}
            className="px-2.5 py-1 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 text-rose-300 hover:text-white text-[11px] font-medium transition-all flex items-center gap-1.5 group"
            title="Stop agent generation"
          >
            <Square className="w-2.5 h-2.5 fill-current text-rose-400 group-hover:scale-110 transition-transform" />
            <span>Stop</span>
          </button>
        </div>
      </div>

      {/* Middle Status & Telemetry Row */}
      <div className="p-3 sm:px-4 flex items-center gap-3">
        <Loader2 className="w-4 h-4 text-blue-400 animate-spin shrink-0" />
        <span className="text-xs sm:text-[13px] text-slate-200 font-medium truncate flex-1">
          {statusText || 'Sensa AI is processing multi-step workflow...'}
        </span>
      </div>

      {/* Progress Bar Line */}
      <div className="w-full bg-[#1b1c2b] h-1">
        <div
          className="h-full bg-gradient-to-r from-blue-500 via-indigo-500 to-emerald-400 transition-all duration-300"
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      {/* Live Discovered Jobs Shelf (Horizontal Mini-Cards) */}
      {jobCards.length > 0 && (
        <div className="p-2 sm:px-4 bg-[#0f1019]/90 border-t border-[#1d1f30] flex items-center gap-2.5 overflow-x-auto custom-scrollbar">
          <div className="flex items-center gap-1.5 shrink-0">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-300">
              Live Matches ({jobCards.length}):
            </span>
          </div>
          <div className="flex items-center gap-2 flex-nowrap">
            {jobCards.map((job, jIdx) => (
              <button
                key={jIdx}
                type="button"
                onClick={() => onJobClick?.(job)}
                className="px-2.5 py-1.5 rounded-xl bg-[#17192a] hover:bg-[#1f2238] border border-[#262840] hover:border-blue-500/50 text-left shrink-0 transition-all group flex items-center gap-2 shadow-sm"
                title={`Click to review: ${job.title} at ${job.company}`}
              >
                {job.platform && (
                  <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-blue-500/15 text-blue-300 border border-blue-500/25 uppercase shrink-0 font-bold">
                    {job.platform.slice(0, 3)}
                  </span>
                )}
                <div className="min-w-0 flex flex-col">
                  <span className="text-[11px] font-semibold text-slate-200 group-hover:text-blue-300 truncate max-w-[130px] leading-tight">
                    {job.title}
                  </span>
                  <span className="text-[9.5px] text-slate-400 truncate max-w-[130px] leading-tight">
                    {job.company}
                  </span>
                </div>
                {job.score && (
                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-md bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 shrink-0">
                    {job.score}%
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      )}

    </div>
  );
};
