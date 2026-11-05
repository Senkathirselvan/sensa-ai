import React, { useState, useEffect } from 'react';
import { X, FileText, Image, Cpu, UploadCloud, CheckCircle2, Key, Sparkles, ExternalLink } from 'lucide-react';
import { api } from '../services/api';

interface AttachmentModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedModel: string;
  onModelChange: (model: string) => void;
  onResumeUploaded?: () => void;
}

export const AttachmentModal: React.FC<AttachmentModalProps> = ({
  isOpen,
  onClose,
  selectedModel,
  onModelChange,
  onResumeUploaded,
}) => {
  const [activeTab, setActiveTab] = useState<'resume' | 'media' | 'model'>('resume');
  const [uploading, setUploading] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Cloud API Keys
  const [anthropicKey, setAnthropicKey] = useState('');
  const [geminiKey, setGeminiKey] = useState('');
  const [savedKeyMsg, setSavedKeyMsg] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setAnthropicKey(api.getAnthropicKey());
      setGeminiKey(api.getGeminiKey());
      setSavedKeyMsg(null);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setUploading(true);
      setUploadError(null);
      setUploadSuccess(null);
      const res = await api.uploadResume(file);
      setUploadSuccess(`Saved "${file.name}" (${res.size_kb} KB) as active resume!`);
      if (onResumeUploaded) onResumeUploaded();
    } catch (err: any) {
      setUploadError(err.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const updateAnthropicKey = (val: string) => {
    setAnthropicKey(val);
    api.setAnthropicKey(val);
  };

  const updateGeminiKey = (val: string) => {
    setGeminiKey(val);
    api.setGeminiKey(val);
  };

  const handleSaveKeys = () => {
    api.setAnthropicKey(anthropicKey);
    api.setGeminiKey(geminiKey);
    setSavedKeyMsg('API keys saved locally in browser!');
    setTimeout(() => setSavedKeyMsg(null), 2500);
  };

  const handleClose = () => {
    handleSaveKeys();
    onClose();
  };

  const modelOptions = [
    {
      id: 'auto',
      name: '🎯 Smart 3-Tier Auto Cascade (Recommended)',
      desc: 'Tries Claude ➡️ Falls back to Gemini ➡️ Guaranteed fallback to Local Ollama.',
      badge: 'Best Experience',
    },
    {
      id: 'claude-3-5-haiku',
      name: '⚡ Claude 3.5 Haiku (Anthropic API)',
      desc: 'Lightning fast response & high reasoning quality.',
      badge: 'Cloud',
    },
    {
      id: 'gemini-1.5-flash',
      name: '💎 Google Gemini 1.5 Flash (Google AI)',
      desc: 'Huge 1,500 free requests/day with sub-second latency.',
      badge: 'Free Cloud',
    },
    {
      id: 'qwen2.5',
      name: '🏠 Qwen 2.5 7B (Local Ollama)',
      desc: '100% local, unlimited, runs offline on your machine.',
      badge: 'Local',
    },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div className="bg-[#181820] border border-[#2e2e3e] w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#292936]">
          <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
            📎 Attach & Model Configuration
          </h3>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-[#252532] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-[#292936] bg-[#14141a]">
          <button
            onClick={() => setActiveTab('resume')}
            className={`flex-1 py-2.5 text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors border-b-2 ${
              activeTab === 'resume'
                ? 'border-blue-500 text-blue-400 bg-[#1e1e28]'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <FileText className="w-3.5 h-3.5" /> Resume
          </button>
          <button
            onClick={() => setActiveTab('media')}
            className={`flex-1 py-2.5 text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors border-b-2 ${
              activeTab === 'media'
                ? 'border-blue-500 text-blue-400 bg-[#1e1e28]'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Image className="w-3.5 h-3.5" /> Screenshot
          </button>
          <button
            onClick={() => setActiveTab('model')}
            className={`flex-1 py-2.5 text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors border-b-2 ${
              activeTab === 'model'
                ? 'border-blue-500 text-blue-400 bg-[#1e1e28]'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Cpu className="w-3.5 h-3.5" /> Model & Keys
          </button>
        </div>

        {/* Tab Body */}
        <div className="p-5 overflow-y-auto space-y-4">
          {activeTab === 'resume' && (
            <div>
              <p className="text-xs text-slate-400 mb-3">
                Upload your candidate resume (PDF, DOCX, or TXT) to match with live jobs:
              </p>
              <label className="border-2 border-dashed border-[#343446] hover:border-blue-500/60 rounded-xl p-6 flex flex-col items-center justify-center gap-2 cursor-pointer transition-all bg-[#1b1b24] hover:bg-[#1e1e2a] text-center">
                <UploadCloud className="w-8 h-8 text-blue-400" />
                <span className="text-xs font-semibold text-slate-200">
                  {uploading ? 'Processing resume...' : 'Click to select or drag & drop'}
                </span>
                <span className="text-[11px] text-slate-500">PDF, DOCX up to 10MB</span>
                <input
                  type="file"
                  accept=".pdf,.docx,.txt"
                  onChange={handleFileUpload}
                  disabled={uploading}
                  className="hidden"
                />
              </label>

              {uploadSuccess && (
                <div className="mt-3 p-2.5 rounded-lg bg-emerald-950/40 border border-emerald-800/40 text-emerald-300 text-xs flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 shrink-0" />
                  <span>{uploadSuccess}</span>
                </div>
              )}

              {uploadError && (
                <div className="mt-3 p-2.5 rounded-lg bg-rose-950/40 border border-rose-800/40 text-rose-300 text-xs">
                  {uploadError}
                </div>
              )}
            </div>
          )}

          {activeTab === 'media' && (
            <div>
              <p className="text-xs text-slate-400 mb-3">
                Upload a screenshot of a job posting or LinkedIn feed to analyze:
              </p>
              <label className="border-2 border-dashed border-[#343446] hover:border-blue-500/60 rounded-xl p-6 flex flex-col items-center justify-center gap-2 cursor-pointer transition-all bg-[#1b1b24] hover:bg-[#1e1e2a] text-center">
                <Image className="w-8 h-8 text-blue-400" />
                <span className="text-xs font-semibold text-slate-200">
                  Upload screenshot (PNG, JPG, WebP)
                </span>
                <input type="file" accept="image/*" className="hidden" />
              </label>
            </div>
          )}

          {activeTab === 'model' && (
            <div className="space-y-4">
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-2">
                  Select Execution Strategy:
                </label>
                <div className="space-y-2">
                  {modelOptions.map((m) => (
                    <div
                      key={m.id}
                      onClick={() => onModelChange(m.id)}
                      className={`p-3 rounded-xl border cursor-pointer transition-all ${
                        selectedModel === m.id
                          ? 'border-blue-500 bg-blue-500/10 text-white'
                          : 'border-[#2d2d3c] bg-[#1a1a24] text-slate-300 hover:border-[#3e3e50]'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold">{m.name}</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#252536] text-blue-400 border border-blue-500/20">
                          {m.badge}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400 mt-1">{m.desc}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Optional Cloud API Keys */}
              <div className="p-3.5 rounded-xl bg-[#14141c] border border-[#2b2b3a] space-y-3">
                <div className="flex items-center gap-1.5 text-xs font-bold text-slate-200">
                  <Key className="w-3.5 h-3.5 text-amber-400" /> Cloud API Keys (Optional)
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-[11px] text-slate-400">Anthropic Claude API Key:</label>
                    <span className="text-[10px] text-slate-500 font-mono">sk-ant-...</span>
                  </div>
                  <input
                    type="password"
                    value={anthropicKey}
                    onChange={(e) => updateAnthropicKey(e.target.value)}
                    placeholder="Enter Claude API key for tier 1"
                    className="w-full bg-[#1b1b24] border border-[#2e2e40] rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-blue-500 font-mono"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-[11px] text-slate-400">Google Gemini API Key:</label>
                    <a
                      href="https://aistudio.google.com/app/apikey"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[10px] text-blue-400 hover:underline flex items-center gap-0.5"
                    >
                      Get free key <ExternalLink className="w-2.5 h-2.5" />
                    </a>
                  </div>
                  <input
                    type="password"
                    value={geminiKey}
                    onChange={(e) => updateGeminiKey(e.target.value)}
                    placeholder="Enter Gemini API key for tier 2"
                    className="w-full bg-[#1b1b24] border border-[#2e2e40] rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-blue-500 font-mono"
                  />
                </div>

                <div className="flex items-center justify-between pt-1">
                  <span className="text-[10px] text-emerald-400">✓ Auto-saved directly to your browser</span>
                  <button
                    onClick={handleSaveKeys}
                    className="px-3 py-1 rounded-lg bg-[#272738] hover:bg-[#34344a] text-xs font-semibold text-slate-200 border border-[#3e3e52] transition-colors"
                  >
                    Save Keys
                  </button>
                </div>

                {savedKeyMsg && (
                  <p className="text-[11px] text-emerald-400 font-medium">{savedKeyMsg}</p>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-[#292936] flex justify-end bg-[#15151c]">
          <button
            onClick={handleClose}
            className="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold transition-colors"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
