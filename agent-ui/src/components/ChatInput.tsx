import React, { useState, useRef, useEffect } from 'react';
import {
  ArrowUp,
  Square,
  Plus,
  Sparkles,
  FileText,
  Image as ImageIcon,
  Paperclip,
  X,
  CheckCircle2,
  Loader2,
  Trash2
} from 'lucide-react';
import { api } from '../services/api';
import { ResumeStatus } from '../types';

interface AttachedMedia {
  id: string;
  type: 'image' | 'file';
  name: string;
  sizeKb: number;
  dataUrl?: string;
  content?: string;
}

interface ChatInputProps {
  onSendMessage: (message: string, images?: string[]) => void;
  onStopGeneration?: () => void;
  isStreaming?: boolean;
  selectedModel: string;
  activeSessionId?: string | null;
  resumeStatus?: ResumeStatus | null;
  onResumeUploaded?: () => void;
  onResumeDeleted?: () => void;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  onSendMessage,
  onStopGeneration,
  isStreaming,
  selectedModel,
  activeSessionId,
  resumeStatus,
  onResumeUploaded,
  onResumeDeleted,
}) => {
  const [input, setInput] = useState('');
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isUploadingResume, setIsUploadingResume] = useState(false);
  const [isDeletingResume, setIsDeletingResume] = useState(false);
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);
  const [attachedMedia, setAttachedMedia] = useState<AttachedMedia[]>([]);
  const [pendingResume, setPendingResume] = useState<{ filename: string; size_kb: number } | null>(null);

  // Clear any legacy persistent session attachments from localStorage
  useEffect(() => {
    try {
      localStorage.removeItem('sensa_session_attachments');
    } catch {}
  }, []);

  // Reset drafting state when switching sessions
  useEffect(() => {
    setPendingResume(null);
    setAttachedMedia([]);
    setInput('');
  }, [activeSessionId]);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const resumeInputRef = useRef<HTMLInputElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const docInputRef = useRef<HTMLInputElement>(null);

  // Auto-resize textarea height
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  }, [input]);

  // Close plus menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setIsMenuOpen(false);
      }
    };
    if (isMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isMenuOpen]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSend = () => {
    if ((!input.trim() && attachedMedia.length === 0 && !pendingResume) || isStreaming) return;

    let fullPrompt = input.trim();
    const images: string[] = [];

    // Process attached documents and images
    if (attachedMedia.length > 0) {
      const docAttachments: string[] = [];
      for (const m of attachedMedia) {
        if (m.type === 'image' && m.dataUrl) {
          images.push(m.dataUrl);
        } else if (m.type === 'file' && m.content) {
          docAttachments.push(`\n\n--- Attached File: ${m.name} ---\n${m.content}\n--- End Attached File ---`);
        }
      }
      if (docAttachments.length > 0) {
        fullPrompt = (fullPrompt + docAttachments.join('')).trim();
      }
    }

    if (pendingResume) {
      fullPrompt = (fullPrompt + `\n\n[Attached Resume: ${pendingResume.filename}]`).trim();
    }

    onSendMessage(fullPrompt, images.length > 0 ? images : undefined);
    setInput('');
    setAttachedMedia([]);
    setPendingResume(null);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  // Upload Resume handler (saves to server profile AND queues for the current draft)
  const handleResumeFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsMenuOpen(false);

    try {
      setIsUploadingResume(true);
      setActionFeedback(null);
      const res = await api.uploadResume(file);
      setActionFeedback(`Saved "${file.name}" (${res.size_kb} KB) and attached to message`);
      setPendingResume({
        filename: file.name,
        size_kb: res.size_kb,
      });
      if (onResumeUploaded) onResumeUploaded();
      setTimeout(() => setActionFeedback(null), 5000);
    } catch (err: any) {
      alert(`Resume upload failed: ${err.message || 'Network error'}`);
    } finally {
      setIsUploadingResume(false);
      if (resumeInputRef.current) resumeInputRef.current.value = '';
    }
  };

  // Delete Resume from server handler (with explicit confirmation prompt)
  const handleDeleteResume = async (e: React.MouseEvent) => {
    e.stopPropagation();
    const confirmed = window.confirm(
      'Are you sure you want to permanently delete your resume from the server?\n\n' +
      'This will delete your Candidate Master Profile across all agents.'
    );
    if (!confirmed) return;

    try {
      setIsDeletingResume(true);
      await api.deleteResume();
      setPendingResume(null);
      setActionFeedback('Master resume profile deleted from server.');
      if (onResumeDeleted) onResumeDeleted();
      if (onResumeUploaded) onResumeUploaded();
      setIsMenuOpen(false);
      setTimeout(() => setActionFeedback(null), 4000);
    } catch (err: any) {
      alert(`Failed to delete resume: ${err.message || 'Network error'}`);
    } finally {
      setIsDeletingResume(false);
    }
  };

  // Upload Image handler
  const handleImageFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsMenuOpen(false);

    const reader = new FileReader();
    reader.onload = (event) => {
      setAttachedMedia((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          type: 'image',
          name: file.name,
          sizeKb: Math.round(file.size / 1024),
          dataUrl: event.target?.result as string,
        },
      ]);
    };
    reader.readAsDataURL(file);
    if (imageInputRef.current) imageInputRef.current.value = '';
  };

  // Upload Document handler (Universal for code, pdf, docx, txt, csv, json)
  const handleDocFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsMenuOpen(false);

    const reader = new FileReader();
    reader.onload = (event) => {
      setAttachedMedia((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          type: 'file',
          name: file.name,
          sizeKb: Math.round(file.size / 1024),
          content: typeof event.target?.result === 'string' ? event.target.result : undefined,
        },
      ]);
    };
    reader.readAsText(file);
    if (docInputRef.current) docInputRef.current.value = '';
  };

  const removeMedia = (id: string) => {
    setAttachedMedia((prev) => prev.filter((m) => m.id !== id));
  };

  return (
    <div className="w-full max-w-3xl mx-auto px-4 pb-4">
      {/* Hidden file inputs */}
      <input
        ref={resumeInputRef}
        type="file"
        accept=".pdf,.docx,.txt"
        onChange={handleResumeFileSelect}
        className="hidden"
      />
      <input
        ref={imageInputRef}
        type="file"
        accept="image/*"
        onChange={handleImageFileSelect}
        className="hidden"
      />
      <input
        ref={docInputRef}
        type="file"
        accept=".pdf,.docx,.txt,.md,.py,.json,.csv,.ts,.js,.yaml,.sql"
        onChange={handleDocFileSelect}
        className="hidden"
      />

      {/* Input container dock */}
      <div className="relative flex flex-col bg-[#151622] border border-[#27293d] focus-within:border-blue-500/70 focus-within:ring-4 focus-within:ring-blue-500/10 rounded-2xl p-2.5 transition-all duration-200 shadow-xl">
        {/* Loading / Action Feedback Banner */}
        {isUploadingResume && (
          <div className="mb-2 px-3 py-1.5 rounded-xl bg-blue-950/40 border border-blue-800/40 text-blue-300 text-xs flex items-center gap-2 animate-pulse">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            <span>Parsing & saving resume to profile...</span>
          </div>
        )}

        {isDeletingResume && (
          <div className="mb-2 px-3 py-1.5 rounded-xl bg-rose-950/40 border border-rose-800/40 text-rose-300 text-xs flex items-center gap-2 animate-pulse">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            <span>Deleting resume from disk and database...</span>
          </div>
        )}

        {actionFeedback && (
          <div className="mb-2 px-3 py-1.5 rounded-xl bg-emerald-950/40 border border-emerald-800/40 text-emerald-300 text-xs flex items-center justify-between animate-fade-in">
            <span className="flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>{actionFeedback}</span>
            </span>
            <button
              onClick={() => setActionFeedback(null)}
              className="text-emerald-400 hover:text-emerald-200 p-0.5"
            >
              <X className="w-3 h-3" />
            </button>
          </div>
        )}

        {/* Attached Items Previews (Images, Docs & Pending Resume for THIS draft) */}
        {(attachedMedia.length > 0 || pendingResume) && (
          <div className="flex flex-wrap gap-2 mb-2 px-1">
            {pendingResume && (
              <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-xl bg-blue-950/40 border border-blue-800/40 text-xs text-blue-200 shadow-sm animate-fade-in">
                <FileText className="w-3.5 h-3.5 text-blue-400" />
                <div className="max-w-[190px] truncate">
                  <span className="font-semibold text-slate-100">{pendingResume.filename}</span>
                  <span className="text-[10px] text-blue-300/80 ml-1.5 font-mono">({pendingResume.size_kb} KB)</span>
                </div>
                <button
                  type="button"
                  onClick={() => setPendingResume(null)}
                  className="p-1 rounded-md text-slate-400 hover:text-rose-400 hover:bg-[#25283f] transition-colors ml-0.5"
                  title="Remove attached resume from this message"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            )}
            {attachedMedia.map((m) => (
              <div
                key={m.id}
                className="flex items-center gap-2 px-2.5 py-1.5 rounded-xl bg-[#1d1f30] border border-[#2e314a] text-xs text-slate-200 shadow-sm"
              >
                {m.type === 'image' && m.dataUrl ? (
                  <img
                    src={m.dataUrl}
                    alt={m.name}
                    className="w-7 h-7 rounded-lg object-cover border border-white/10"
                  />
                ) : (
                  <Paperclip className="w-3.5 h-3.5 text-blue-400" />
                )}
                <div className="max-w-[140px] truncate">
                  <span className="font-medium text-slate-200">{m.name}</span>
                  <span className="text-[10px] text-slate-400 block">{m.sizeKb} KB</span>
                </div>
                <button
                  type="button"
                  onClick={() => removeMedia(m.id)}
                  className="p-1 rounded-md text-slate-400 hover:text-rose-400 hover:bg-[#25283f] transition-colors"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Main Input Row */}
        <div className="flex items-end gap-1.5">
          {/* Plus Icon Button with Popover Menu */}
          <div className="relative shrink-0" ref={menuRef}>
            <button
              type="button"
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              title="Attach documents, images, or manage files"
              className={`w-8 h-8 min-w-[32px] min-h-[32px] rounded-xl border flex items-center justify-center transition-all duration-150 mb-0.5 shadow-sm ${
                isMenuOpen
                  ? 'bg-blue-600 text-white border-blue-500 rotate-45'
                  : 'bg-[#202234] hover:bg-[#282a40] border-[#31344e] text-slate-300 hover:text-white'
              }`}
            >
              <Plus className="w-4 h-4 transition-transform duration-200" />
            </button>

            {/* Plus Popover Menu (Universal Common UI for All Agents) */}
            {isMenuOpen && (
              <div className="absolute left-0 bottom-10 mb-2 w-72 rounded-2xl bg-[#171825] border border-[#2c2f46] shadow-2xl p-2 z-50 space-y-1.5 animate-scale-up">
                <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-2 py-0.5 border-b border-[#24263a] flex items-center justify-between">
                  <span>Attach to Message</span>
                  <span className="text-[9px] text-slate-500 font-normal">Message Draft</span>
                </div>

                {/* Universal Option 1: Attach Document / Files */}
                <button
                  type="button"
                  onClick={() => docInputRef.current?.click()}
                  className="w-full text-left px-3 py-2 rounded-xl text-xs font-medium text-slate-200 hover:bg-[#222438] hover:text-white flex items-center gap-2.5 transition-colors group"
                >
                  <div className="w-7 h-7 rounded-lg bg-blue-500/15 border border-blue-500/30 flex items-center justify-center text-blue-400 group-hover:scale-105 transition-transform">
                    <Paperclip className="w-3.5 h-3.5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-slate-100">Attach Document / File</div>
                    <div className="text-[10.5px] text-slate-400 truncate">PDF, DOCX, TXT, Code, Data</div>
                  </div>
                </button>

                {/* Universal Option 2: Upload Screenshot / Image */}
                <button
                  type="button"
                  onClick={() => imageInputRef.current?.click()}
                  className="w-full text-left px-3 py-2 rounded-xl text-xs font-medium text-slate-200 hover:bg-[#222438] hover:text-white flex items-center gap-2.5 transition-colors group"
                >
                  <div className="w-7 h-7 rounded-lg bg-purple-500/15 border border-purple-500/30 flex items-center justify-center text-purple-400 group-hover:scale-105 transition-transform">
                    <ImageIcon className="w-3.5 h-3.5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-slate-100">Upload Image</div>
                    <div className="text-[10.5px] text-slate-400 truncate">PNG, JPG screenshot or diagram</div>
                  </div>
                </button>

                {/* Career Agent Integration: Resume Profile in Popover */}
                <div className="pt-1.5 border-t border-[#24263a]">
                  {resumeStatus?.uploaded ? (
                    <div className="p-2.5 rounded-xl bg-[#171826] border border-[#2c2f46] space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-[10.5px] font-bold text-slate-300 flex items-center gap-1.5">
                          <FileText className="w-3.5 h-3.5 text-blue-400" /> Resume Profile
                        </span>
                        <span className="text-[9px] font-medium text-emerald-400 bg-emerald-500/10 px-1.5 py-0.2 rounded border border-emerald-500/20">
                          Ready
                        </span>
                      </div>

                      <div className="flex items-center justify-between text-xs px-0.5">
                        <span className="text-slate-200 font-medium truncate max-w-[155px]" title={resumeStatus.filename || 'resume.pdf'}>
                          {resumeStatus.filename || 'resume.pdf'}
                        </span>
                        <span className="text-[10.5px] text-slate-400 font-mono">
                          {resumeStatus.size_kb} KB
                        </span>
                      </div>

                      <div className="flex items-center justify-between gap-2 pt-1.5 border-t border-[#26293f]">
                        <button
                          type="button"
                          onClick={() => {
                            setPendingResume({
                              filename: resumeStatus.filename || 'resume.pdf',
                              size_kb: resumeStatus.size_kb,
                            });
                            setIsMenuOpen(false);
                          }}
                          className="px-2.5 py-1 rounded-lg text-[11px] font-semibold text-blue-300 bg-blue-500/15 hover:bg-blue-500/25 border border-blue-500/30 flex items-center gap-1 transition-all"
                          title="Attach resume to current message draft"
                        >
                          <Plus className="w-3 h-3" />
                          <span>Attach to Message</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => resumeInputRef.current?.click()}
                          className="text-[11px] font-medium text-slate-400 hover:text-slate-200 transition-colors"
                          title="Upload new file to replace resume"
                        >
                          Replace
                        </button>
                        <button
                          type="button"
                          onClick={handleDeleteResume}
                          disabled={isDeletingResume}
                          className="text-[10px] text-rose-400 hover:text-rose-300 transition-colors"
                          title="Permanently delete from server"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => resumeInputRef.current?.click()}
                      className="w-full text-left px-3 py-1.5 rounded-xl text-xs font-medium text-slate-400 hover:bg-[#202235] hover:text-slate-200 flex items-center gap-2.5 transition-colors group"
                    >
                      <div className="w-7 h-7 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 group-hover:scale-105 transition-transform">
                        <FileText className="w-3.5 h-3.5" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="font-semibold text-slate-200">Upload Candidate Resume</div>
                        <div className="text-[10.5px] text-slate-500 truncate">Attach to message & profile</div>
                      </div>
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Textarea */}
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Message Sensa AI... (e.g. search jobs, evaluate resume, write code)"
            rows={1}
            className="flex-1 bg-transparent text-slate-100 placeholder-slate-500 text-[14px] px-3 py-1.5 focus:outline-none resize-none max-h-44 leading-relaxed"
          />

          {/* Right Action Button (Send / Stop) */}
          {isStreaming ? (
            <button
              type="button"
              onClick={onStopGeneration}
              title="Stop generation"
              className="w-8 h-8 min-w-[32px] min-h-[32px] rounded-xl bg-rose-600 hover:bg-rose-500 text-white flex items-center justify-center transition-all shrink-0 mb-0.5 shadow-md shadow-rose-600/20 hover:scale-105"
            >
              <Square className="w-3.5 h-3.5 fill-current" />
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSend}
              disabled={!input.trim() && attachedMedia.length === 0}
              title="Send message (Enter)"
              className={`w-8 h-8 min-w-[32px] min-h-[32px] rounded-xl flex items-center justify-center transition-all shrink-0 mb-0.5 shadow-md ${
                input.trim() || attachedMedia.length > 0
                  ? 'bg-blue-600 hover:bg-blue-500 text-white hover:scale-105 shadow-blue-600/25'
                  : 'bg-[#222334] text-slate-600 cursor-not-allowed'
              }`}
            >
              <ArrowUp className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Micro-caption below input */}
      <div className="flex items-center justify-between text-[11px] text-slate-500 mt-2 px-1">
        <span className="flex items-center gap-1.5">
          <Sparkles className="w-3 h-3 text-blue-400" />
          Sensa AI • Claude 3.5 • Gemini Flash • Local Ollama
        </span>
        <span className="hidden sm:inline-block font-mono text-[10px] text-slate-500">
          Enter to send • Shift + Enter for newline
        </span>
      </div>
    </div>
  );
};
