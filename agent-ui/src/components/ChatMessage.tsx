import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { User, Sparkles, Copy, Check, RotateCw, Pencil, X, Maximize2, FileText, Download, ExternalLink, ChevronLeft, ChevronRight, Eye } from 'lucide-react';
import { ChatMessage as ChatMessageType, JobCard as JobCardType } from '../types';
import { JobCard } from './JobCard';
import { ToolBadge } from './ToolBadge';

interface ChatMessageProps {
  message: ChatMessageType;
  isStreaming?: boolean;
  onApplyClick?: (job: JobCardType) => void;
  onSaveSuccess?: () => void;
  onRerun?: (messageId: string, content: string, images?: string[]) => void;
  onEdit?: (messageId: string, newContent: string) => void;
  onSwitchVersion?: (messageId: string, versionIndex: number) => void;
  onTailorClick?: (job: JobCardType) => void;
  onPreviewResume?: (previewUrl: string) => void;
}

function parseResumeContent(text: string): { intro: string; resume: string; outro: string } | null {
  if (!text) return null;

  // Check for the core landmarks of an ATS resume document
  const mSummary = text.match(/(?:^|\n)(?:#{1,3}\s*)?(?:PROFESSIONAL\s+SUMMARY|CAREER\s+SUMMARY|EXECUTIVE\s+SUMMARY|SUMMARY\b)/i);
  const mSkills = text.match(/(?:^|\n)(?:#{1,3}\s*)?(?:CORE\s+TECHNICAL\s+SKILLS|TECHNICAL\s+SKILLS|CORE\s+SKILLS|SKILLS\b)/i);
  const mExp = text.match(/(?:^|\n)(?:#{1,3}\s*)?(?:PROFESSIONAL\s+EXPERIENCE|WORK\s+EXPERIENCE|EMPLOYMENT\s+HISTORY|EXPERIENCE\b)/i);

  if (!mSummary || (!mSkills && !mExp)) {
    return null;
  }

  const summaryIdx = mSummary.index ?? 0;
  const preText = text.slice(0, summaryIdx).trim();

  // Determine where the conversational intro ends and the candidate's resume header starts
  let resumeStart = 0;
  const introEndMatch = text.slice(0, summaryIdx).match(/(?:here is|below is|certainly|sure|based on your resume)[^\n]+\n+/i);
  if (introEndMatch && introEndMatch.index !== undefined) {
    resumeStart = introEndMatch.index + introEndMatch[0].length;
  } else {
    const dividerMatch = preText.match(/(?:^|\n)---\s*\n/);
    if (dividerMatch && dividerMatch.index !== undefined) {
      resumeStart = dividerMatch.index + dividerMatch[0].length;
    }
  }

  // Determine where the resume ends and any outro/guidance notes begin
  let resumeEnd = text.length;
  let outro = '';
  const outroMatch = text.slice(summaryIdx).match(
    /\n(?:---\s*\n)?(?:#{1,3}\s*)?(?:Formatting\s+tips|Tips\s+to\s+keep|How\s+to\s+finalize|Tailoring\s+notes|Availability:|Reminder:|Would\s+you\s+like\s+me|Next\s+Steps:|\*\*Availability:\*\*|>\s*\*\*Reminder:\*\*)/i
  );
  if (outroMatch && outroMatch.index !== undefined) {
    resumeEnd = summaryIdx + outroMatch.index;
    outro = text.slice(resumeEnd).trim();
  }

  const intro = text.slice(0, resumeStart).trim();
  const resume = text.slice(resumeStart, resumeEnd).trim();

  if (resume.length > 250) {
    return { intro, resume, outro };
  }
  return null;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({
  message,
  isStreaming,
  onApplyClick,
  onSaveSuccess,
  onRerun,
  onEdit,
  onSwitchVersion,
  onTailorClick,
  onPreviewResume,
}) => {
  const isUser = message.role === 'user';
  const [copied, setCopied] = useState(false);
  const [copiedResume, setCopiedResume] = useState(false);
  const [copiedCodeIdx, setCopiedCodeIdx] = useState<number | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editDraft, setEditDraft] = useState(message.content);
  const [selectedImageModal, setSelectedImageModal] = useState<string | null>(null);

  React.useEffect(() => {
    setEditDraft(message.content);
  }, [message.content]);

  const handleCopyMessage = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleCopyResume = (resumeText: string) => {
    navigator.clipboard.writeText(resumeText);
    setCopiedResume(true);
    setTimeout(() => setCopiedResume(false), 2000);
  };

  const handleDownloadMarkdown = (resumeText: string) => {
    const blob = new Blob([resumeText], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'Tailored_ATS_Resume.md';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleOpenInStudio = (resumeText: string) => {
    if (!onTailorClick) return;
    let targetJob: JobCardType | undefined = undefined;

    if (message.jobCards && message.jobCards.length > 0) {
      targetJob = message.jobCards.find((j) =>
        message.content.toLowerCase().includes((j.company || '').toLowerCase()) ||
        message.content.toLowerCase().includes((j.title || '').toLowerCase())
      );
      if (!targetJob) targetJob = message.jobCards[0];
    }

    if (!targetJob) {
      // Clean markdown asterisks, backticks, hashes before parsing
      const cleanContent = message.content.replace(/[*_`#]/g, '');

      let extractedTitle = '';
      let extractedCompany = '';

      // Pattern 1: for the [Title] role at [Company]
      const mMatch = cleanContent.match(/for (?:the\s+)?([A-Za-z0-9\s.,\-/]+?)\s+role at\s+([A-Za-z0-9\s.,\-]+?)(?:\s*\(|\s*\.|\s*,|\s*built|\s*for|\n)/i);
      if (mMatch) {
        extractedTitle = mMatch[1].trim();
        extractedCompany = mMatch[2].trim();
      } else {
        const mTitle = cleanContent.match(/for (?:the\s+)?([A-Za-z0-9\s.,\-/]+?)\s+role/i);
        const mComp = cleanContent.match(/role at\s+([A-Za-z0-9\s.,\-]+?)(?:\s*\(|\s*\.|\s*,|\s*built|\s*for|\n)/i);
        if (mTitle) extractedTitle = mTitle[1].trim();
        if (mComp) extractedCompany = mComp[1].trim();
      }

      // Sanitize placeholder or invalid phrases
      const invalidWords = ['this', 'specific', 'attached', 'given', 'above', 'below', 'your', 'my'];
      if (!extractedTitle || invalidWords.includes(extractedTitle.toLowerCase()) || extractedTitle.length < 3) {
        extractedTitle = 'Python Developer';
      }
      if (!extractedCompany || invalidWords.includes(extractedCompany.toLowerCase()) || extractedCompany.length < 3) {
        extractedCompany = cleanContent.toLowerCase().includes('tekskills') ? 'Tekskills India Pvt Ltd' : 'General Profile';
      }

      targetJob = {
        title: extractedTitle,
        company: extractedCompany,
        url: '',
        snippet: resumeText.slice(0, 800),
      };
    }

    // Determine target page length and generation mode based on conversation text
    const isSinglePage = /(?:1[\s-]page|one[\s-]page|single[\s-]page)/i.test(message.content);
    // Check if the resume text belongs to the master candidate (Senkathir) or a synthetic/benchmark scratch profile
    const isMasterCandidate = /senkathir/i.test(resumeText);
    const hasPlaceholders = /(?:\[YOUR FULL NAME\]|\[City|\[Phone Number\]|\[Email Address\])/i.test(resumeText);
    const isScratch = !isMasterCandidate || hasPlaceholders || /(?:new resume|from scratch|scratch|fresh resume)/i.test(message.content);
    targetJob = {
      ...targetJob,
      target_pages: isSinglePage ? 1 : 2,
      generation_mode: isScratch ? 'scratch' : 'tailor',
      initial_markdown: resumeText,
    } as any;

    if (targetJob) {
      onTailorClick(targetJob);
    }
  };

  const handleCopyCode = (code: string, idx: number) => {
    navigator.clipboard.writeText(code);
    setCopiedCodeIdx(idx);
    setTimeout(() => setCopiedCodeIdx(null), 2000);
  };

  const handleSaveEdit = () => {
    if (!editDraft.trim()) return;
    setIsEditing(false);
    if (onEdit) {
      onEdit(message.id, editDraft.trim());
    } else if (onRerun) {
      onRerun(message.id, editDraft.trim(), message.images);
    }
  };

  const formatRelativeTime = (isoString?: string) => {
    if (!isoString) return '';
    try {
      let s = isoString.trim();
      if (!s.endsWith('Z') && !/[+-]\d{2}(?::?\d{2})?$/.test(s)) {
        s = s.replace(' ', 'T') + 'Z';
      }
      const parsedTime = new Date(s).getTime();
      if (isNaN(parsedTime)) return '';
      const diffMs = Math.max(0, Date.now() - parsedTime);
      const diffSec = Math.floor(diffMs / 1000);
      if (diffSec < 60) return 'Just now';
      const diffMin = Math.floor(diffSec / 60);
      if (diffMin < 60) return `${diffMin}m ago`;
      const diffHour = Math.floor(diffMin / 60);
      if (diffHour < 24) return `${diffHour}h ago`;
      const diffDay = Math.floor(diffHour / 24);
      return `${diffDay}d ago`;
    } catch {
      return '';
    }
  };

  if (isUser) {
    return (
      <div className="py-3 px-4 md:px-6 w-full max-w-3xl mx-auto flex justify-end group">
        <div className="flex gap-3 max-w-[85%] items-start">
          <div className="flex flex-col items-end w-full">
            {/* User Message Bubble or Edit Mode */}
            {isEditing ? (
              <div className="bg-[#191f33] border border-blue-500/50 rounded-2xl p-3 shadow-xl w-full min-w-[320px] transition-all">
                <div className="text-xs font-semibold text-blue-300 mb-1.5 flex items-center justify-between">
                  <span>Edit your message</span>
                  <button
                    onClick={() => {
                      setEditDraft(message.content);
                      setIsEditing(false);
                    }}
                    className="text-slate-400 hover:text-slate-200"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
                <textarea
                  value={editDraft}
                  onChange={(e) => setEditDraft(e.target.value)}
                  className="w-full bg-[#121626] text-slate-100 text-[14px] p-2.5 rounded-xl border border-[#2b3353] focus:outline-none focus:border-blue-500 resize-none leading-relaxed"
                  rows={3}
                  autoFocus
                />
                <div className="flex items-center justify-end gap-2 mt-2.5">
                  <button
                    onClick={() => {
                      setEditDraft(message.content);
                      setIsEditing(false);
                    }}
                    className="px-3 py-1 text-xs font-medium text-slate-400 hover:text-slate-200 hover:bg-[#232a45] rounded-lg transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSaveEdit}
                    disabled={!editDraft.trim()}
                    className="px-3.5 py-1 text-xs font-semibold bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 text-white rounded-lg shadow-md transition-all flex items-center gap-1.5"
                  >
                    <RotateCw className="w-3 h-3" /> Save & Rerun
                  </button>
                </div>
              </div>
            ) : (
              <div className="bg-[#1c2237] border border-blue-500/30 text-slate-100 rounded-2xl rounded-tr-sm px-4 py-3 shadow-md">
                <div className="text-xs font-bold text-blue-300 mb-1.5 flex items-center gap-1.5">
                  <span>You</span>
                </div>

                {/* Render Attached Images if present */}
                {message.images && message.images.length > 0 && (
                  <div className="mb-2.5 flex flex-wrap gap-2.5">
                    {message.images.map((imgSrc, idx) => (
                      <div
                        key={idx}
                        onClick={() => setSelectedImageModal(imgSrc)}
                        className="relative group/img cursor-pointer rounded-xl overflow-hidden border border-[#2b3353] hover:border-blue-400 bg-black/50 transition-all max-w-[280px] shadow-md"
                        title="Click to expand full image"
                      >
                        <img
                          src={imgSrc}
                          alt={`Attached Job Screenshot ${idx + 1}`}
                          className="w-full max-h-48 object-cover object-top transition-transform duration-200 group-hover/img:scale-[1.02]"
                        />
                        <div className="absolute inset-0 bg-black/0 group-hover/img:bg-black/40 transition-colors flex items-center justify-center opacity-0 group-hover/img:opacity-100">
                          <span className="bg-black/75 backdrop-blur-sm text-white text-xs px-2.5 py-1 rounded-md flex items-center gap-1.5 shadow-md font-medium">
                            <Maximize2 className="w-3 h-3 text-blue-400" /> View Image
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {message.content && (
                  <div className="text-[14px] leading-relaxed whitespace-pre-wrap text-slate-100">
                    {message.content}
                  </div>
                )}
              </div>
            )}

            {/* Action Bar (Time • Rerun • Edit • Copy) */}
            {!isEditing && (
              <div className="flex items-center gap-2 mt-1.5 px-1 text-slate-400 text-xs">
                {message.createdAt && (
                  <span className="text-[11px] text-slate-500 font-medium">
                    {formatRelativeTime(message.createdAt)}
                  </span>
                )}

                {/* Rerun Button */}
                {onRerun && (
                  <button
                    onClick={() => onRerun(message.id, message.content, message.images)}
                    className="p-1 rounded-md hover:bg-[#1f253d] hover:text-slate-200 transition-colors"
                    title="Rerun message in-place"
                  >
                    <RotateCw className="w-3.5 h-3.5" />
                  </button>
                )}

                {/* Edit Button */}
                <button
                  onClick={() => {
                    setEditDraft(message.content);
                    setIsEditing(true);
                  }}
                  className="p-1 rounded-md hover:bg-[#1f253d] hover:text-slate-200 transition-colors"
                  title="Edit message"
                >
                  <Pencil className="w-3.5 h-3.5" />
                </button>

                {/* Copy Button */}
                <button
                  onClick={handleCopyMessage}
                  className="p-1 rounded-md hover:bg-[#1f253d] hover:text-slate-200 transition-colors"
                  title="Copy message"
                >
                  {copied ? (
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                  ) : (
                    <Copy className="w-3.5 h-3.5" />
                  )}
                </button>

                {/* Claude-style Version Switcher: < 1/2 > */}
                {message.versions && message.versions.length > 1 && (
                  <div className="flex items-center gap-0.5 text-[11px] text-slate-400 ml-1 select-none bg-[#131728] border border-[#2b3353] rounded-md px-1 py-0.5 shadow-sm">
                    <button
                      onClick={() => onSwitchVersion && onSwitchVersion(message.id, (message.versionIndex ?? 0) - 1)}
                      disabled={(message.versionIndex ?? 0) <= 0}
                      className="p-0.5 rounded hover:bg-[#202742] hover:text-slate-200 disabled:opacity-25 disabled:hover:bg-transparent transition-colors"
                      title="Previous prompt version"
                    >
                      <ChevronLeft className="w-3.5 h-3.5" />
                    </button>
                    <span className="px-1 font-medium tabular-nums text-slate-300">
                      {(message.versionIndex ?? 0) + 1}/{message.versions.length}
                    </span>
                    <button
                      onClick={() => onSwitchVersion && onSwitchVersion(message.id, (message.versionIndex ?? 0) + 1)}
                      disabled={(message.versionIndex ?? 0) >= message.versions.length - 1}
                      className="p-0.5 rounded hover:bg-[#202742] hover:text-slate-200 disabled:opacity-25 disabled:hover:bg-transparent transition-colors"
                      title="Next prompt version"
                    >
                      <ChevronRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* User Avatar */}
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center shrink-0 text-white shadow-md shadow-blue-500/20 text-xs font-bold mt-0.5">
            <User className="w-4 h-4" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="py-4 px-4 md:px-6 w-full max-w-3xl mx-auto">
      <div className="p-4 md:p-5 rounded-2xl bg-[#13141f]/80 border border-[#212335] shadow-lg flex gap-4">
        {/* Assistant Avatar */}
        <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-purple-600 p-[1px] shrink-0 shadow-md shadow-blue-500/15 mt-0.5">
          <div className="w-full h-full bg-[#13141f] rounded-[11px] flex items-center justify-center text-blue-400">
            <Sparkles className="w-4 h-4" />
          </div>
        </div>

        {/* Assistant Content Container */}
        <div className="flex-1 min-w-0">
          {/* Header Row */}
          <div className="flex items-center justify-between mb-2 pb-2 border-b border-[#1f2132]">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-slate-100">Sensa AI Assistant</span>
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
                Autonomous Agent
              </span>
            </div>

            {message.content && (
              <button
                onClick={handleCopyMessage}
                className="text-slate-400 hover:text-slate-100 transition-colors px-2 py-1 rounded-md hover:bg-[#1e2030] flex items-center gap-1 text-[11px]"
                title="Copy entire response"
              >
                {copied ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    <span className="text-emerald-400 font-medium">Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5" />
                    <span>Copy</span>
                  </>
                )}
              </button>
            )}
          </div>

          {/* Active Tool Execution Pill (shown only when not actively streaming in bottom dock) */}
          {message.statusText && !isStreaming && (
            <div className="mb-3">
              <ToolBadge statusText={message.statusText} isThinking={false} />
            </div>
          )}

          {/* Differentiated Rendering: Tailored ATS Resume Artifact Card vs Standard Content */}
          {(() => {
            const parsedResume = !isUser && message.content ? parseResumeContent(message.content) : null;

            if (parsedResume) {
              return (
                <div className="space-y-4">
                  {/* Conversational Intro from Assistant */}
                  {parsedResume.intro && (
                    <div className="text-slate-200 text-[14px] leading-relaxed">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {parsedResume.intro}
                      </ReactMarkdown>
                    </div>
                  )}

                  {/* Dedicated ATS Resume Document Artifact Box */}
                  <div className="rounded-2xl overflow-hidden border border-purple-500/40 bg-[#0d0e18] shadow-2xl transition-all">
                    {/* Document Header Bar with Actions */}
                    <div className="px-4 py-3 bg-[#151726] border-b border-[#23263b] flex flex-wrap items-center justify-between gap-2.5">
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-lg bg-purple-600/20 border border-purple-500/40 flex items-center justify-center text-purple-400">
                          <FileText className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-bold text-slate-100">Tailored ATS Resume Document</span>
                            <span className="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded-full bg-purple-500/15 text-purple-300 border border-purple-500/30">
                              2-Page Standard
                            </span>
                          </div>
                          <span className="text-[11px] text-slate-400">Grounded in candidate profile • ATS optimized</span>
                        </div>
                      </div>

                      {/* Action Buttons */}
                      <div className="flex items-center gap-1.5 flex-wrap">
                        {/* Copy Clean Resume Button */}
                        <button
                          onClick={() => handleCopyResume(parsedResume.resume)}
                          className="px-2.5 py-1.5 rounded-lg text-xs font-semibold text-slate-300 hover:text-white bg-[#1e2136] hover:bg-[#272b44] border border-[#2e3352] flex items-center gap-1.5 transition-all shadow-sm"
                          title="Copy clean resume text to clipboard"
                        >
                          {copiedResume ? (
                            <>
                              <Check className="w-3.5 h-3.5 text-emerald-400" />
                              <span className="text-emerald-400">Copied</span>
                            </>
                          ) : (
                            <>
                              <Copy className="w-3.5 h-3.5 text-slate-300" />
                              <span>Copy Resume</span>
                            </>
                          )}
                        </button>

                        {/* Download Markdown (.md) */}
                        <button
                          onClick={() => handleDownloadMarkdown(parsedResume.resume)}
                          className="px-2.5 py-1.5 rounded-lg text-xs font-semibold text-slate-300 hover:text-white bg-[#1e2136] hover:bg-[#272b44] border border-[#2e3352] flex items-center gap-1.5 transition-all shadow-sm"
                          title="Download resume as markdown file"
                        >
                          <Download className="w-3.5 h-3.5 text-purple-300" />
                          <span>Download .md</span>
                        </button>

                        {/* Open in Dedicated ATS Studio */}
                        {onTailorClick && (
                          <button
                            onClick={() => handleOpenInStudio(parsedResume.resume)}
                            className="px-3 py-1.5 rounded-lg text-xs font-bold text-white bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 flex items-center gap-1.5 shadow-md shadow-purple-600/20 transition-all"
                            title="Open in ATS Studio for instant PDF/DOCX downloads and keyword checklist"
                          >
                            <Sparkles className="w-3.5 h-3.5 text-yellow-300" />
                            <span>Open in ATS Studio</span>
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Formatted Document Canvas */}
                    <div className="p-5 md:p-7 bg-[#0b0c14] overflow-x-auto text-slate-100 text-xs md:text-sm leading-relaxed font-sans border-t border-black/30">
                      <div className="max-w-none prose prose-invert prose-headings:text-purple-200 prose-headings:font-bold prose-headings:border-b prose-headings:border-slate-800/80 prose-headings:pb-1 prose-headings:mt-4 prose-hr:border-slate-800 prose-li:my-0.5">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {parsedResume.resume}
                        </ReactMarkdown>
                      </div>
                    </div>
                  </div>

                  {/* Outro / Tailoring Notes from Assistant */}
                  {parsedResume.outro && (
                    <div className="pt-3 border-t border-[#1f2132] text-slate-300 text-xs md:text-[13px] leading-relaxed">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {parsedResume.outro}
                      </ReactMarkdown>
                    </div>
                  )}
                </div>
              );
            }

            return (
              <div className="prose prose-invert max-w-none text-slate-200 text-[14px] leading-relaxed">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    code({ node, inline, className, children, ...props }: any) {
                      const match = /language-(\w+)/.exec(className || '');
                      const codeString = String(children).replace(/\n$/, '');
                      const codeIndex = Math.floor(Math.random() * 10000);

                      if (!inline && (match || codeString.includes('\n'))) {
                        const lang = match ? match[1] : 'code';
                        return (
                          <div className="my-3 rounded-xl overflow-hidden border border-[#26283b] bg-[#0c0d15] shadow-xl">
                            <div className="flex items-center justify-between px-3.5 py-1.5 bg-[#141521] border-b border-[#242639] text-xs text-slate-400">
                              <span className="font-mono text-[11px] font-semibold text-blue-400 uppercase tracking-wider">
                                {lang}
                              </span>
                              <button
                                onClick={() => handleCopyCode(codeString, codeIndex)}
                                className="flex items-center gap-1 text-[11px] hover:text-slate-200 p-1 rounded hover:bg-[#202235] transition-colors"
                                title="Copy code"
                              >
                                {copiedCodeIdx === codeIndex ? (
                                  <>
                                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                                    <span className="text-emerald-400 font-medium">Copied</span>
                                  </>
                                ) : (
                                  <>
                                    <Copy className="w-3.5 h-3.5" />
                                    <span>Copy Code</span>
                                  </>
                                )}
                              </button>
                            </div>
                            <pre className="p-3.5 overflow-x-auto text-xs font-mono text-slate-200 leading-relaxed bg-[#0c0d15]">
                              <code>{children}</code>
                            </pre>
                          </div>
                        );
                      }

                      return (
                        <code className="px-1.5 py-0.5 rounded-md bg-[#1f2030] text-blue-300 font-mono text-[13px] border border-[#2d2f44]" {...props}>
                          {children}
                        </code>
                      );
                    },
                    table({ children }) {
                      return (
                        <div className="overflow-x-auto my-3 border border-[#242639] rounded-xl bg-[#141521]">
                          <table className="w-full text-left text-xs border-collapse">{children}</table>
                        </div>
                      );
                    },
                    th({ children }) {
                      return (
                        <th className="px-3.5 py-2.5 font-bold text-slate-200 bg-[#1b1c2b] border-b border-[#242639]">
                          {children}
                        </th>
                      );
                    },
                    td({ children }) {
                      return (
                        <td className="px-3.5 py-2 border-b border-[#1f2132] text-slate-300">
                          {children}
                        </td>
                      );
                    },
                    a({ href, children, ...props }: any) {
                      const isDownload = href?.includes('/download/');
                      const isPreview = href?.includes('/preview/');
                      if (isPreview) {
                        return (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.preventDefault();
                              if (onPreviewResume) {
                                onPreviewResume(href);
                              } else {
                                window.open(href, '_blank');
                              }
                            }}
                            className="inline-flex items-center gap-1.5 px-3 py-1 my-1 rounded-lg text-xs font-bold text-white bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 shadow-md shadow-blue-600/30 transition-all cursor-pointer"
                          >
                            <Eye className="w-3.5 h-3.5" />
                            <span>{children}</span>
                          </button>
                        );
                      }
                      return (
                        <a
                          href={href}
                          target={isPreview ? '_blank' : undefined}
                          rel={isPreview ? 'noopener noreferrer' : undefined}
                          download={isDownload ? true : undefined}
                          className="inline-flex items-center gap-1 font-semibold text-blue-400 hover:text-blue-300 underline underline-offset-4 decoration-blue-500/40 hover:decoration-blue-400 transition-colors"
                          {...props}
                        >
                          {children}
                        </a>
                      );
                    },
                  }}
                >
                  {message.content}
                </ReactMarkdown>

                {isStreaming && !message.content && (
                  <div className="flex items-center gap-2 text-xs text-blue-400 py-1 font-medium">
                    <span className="w-2 h-2 rounded-full bg-blue-500 animate-ping inline-block" />
                    <span className="text-slate-300">Agent executing at bottom dock...</span>
                  </div>
                )}
              </div>
            );
          })()}

          {/* Interactive Structured Artifacts (Job Cards settled upon completion) */}
          {message.jobCards && message.jobCards.length > 0 && !isStreaming && (
            <div className="mt-5 space-y-3 pt-3 border-t border-[#1f2132]">
              <div className="flex items-center justify-between">
                <div className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
                  Top Matched Opportunities ({message.jobCards.length})
                </div>
                <span className="text-[11px] text-slate-500">Live multi-platform results</span>
              </div>
              <div className="grid grid-cols-1 gap-3">
                {message.jobCards.map((job, idx) => (
                  <JobCard
                    key={idx}
                    job={job}
                    onApplyClick={onApplyClick}
                    onSaveSuccess={onSaveSuccess}
                    onTailorClick={onTailorClick}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Fullscreen Image Preview Lightbox Modal */}
      {selectedImageModal && (
        <div
          className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-4"
          onClick={() => setSelectedImageModal(null)}
        >
          <div
            className="relative max-w-4xl max-h-[90vh] bg-[#12141f] border border-slate-700/80 rounded-2xl overflow-hidden shadow-2xl flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-[#232738] bg-[#171a29]">
              <span className="text-xs font-semibold text-slate-300">Attached Image Preview</span>
              <button
                onClick={() => setSelectedImageModal(null)}
                className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-700/50 rounded-lg transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-3 overflow-auto flex items-center justify-center bg-black/40">
              <img
                src={selectedImageModal}
                alt="Enlarged screenshot preview"
                className="max-h-[75vh] w-auto max-w-full object-contain rounded-lg shadow-lg"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
