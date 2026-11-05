import React, { useState, useEffect } from 'react';
import {
  X,
  Cpu,
  Key,
  CheckCircle2,
  Sparkles,
  ExternalLink,
  Eye,
  EyeOff,
  ShieldCheck,
  Check,
  Zap,
  Sliders,
  Shield,
  Clock,
  Layers,
} from 'lucide-react';
import { api } from '../services/api';
import { AutoApplySettings } from '../types';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedModel: string;
  onModelChange: (model: string) => void;
  onSettingsSaved?: (settings: AutoApplySettings) => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  selectedModel,
  onModelChange,
  onSettingsSaved,
}) => {
  const [activeTab, setActiveTab] = useState<'models' | 'auto_apply'>('models');
  const [anthropicKey, setAnthropicKey] = useState('');
  const [geminiKey, setGeminiKey] = useState('');
  const [nvidiaKey, setNvidiaKey] = useState('');
  const [showAnthropicKey, setShowAnthropicKey] = useState(false);
  const [showGeminiKey, setShowGeminiKey] = useState(false);
  const [showNvidiaKey, setShowNvidiaKey] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [localModel, setLocalModel] = useState(selectedModel);

  // Auto-Apply Mode Settings State
  const [autoApplySettings, setAutoApplySettings] = useState<AutoApplySettings>({
    enabled: false,
    maxBatchSize: 5,
    minMatchScore: 75,
    stealthDelaySeconds: 45,
    allowedPlatforms: {
      naukri: true,
      linkedin: true,
      indeed: false,
    },
  });

  useEffect(() => {
    if (isOpen) {
      setAnthropicKey(api.getAnthropicKey());
      setGeminiKey(api.getGeminiKey());
      setNvidiaKey(api.getNvidiaKey());
      setLocalModel(selectedModel);
      setAutoApplySettings(api.getAutoApplySettings());
      setSavedSuccess(false);
    }
  }, [isOpen, selectedModel]);

  if (!isOpen) return null;

  const handleSave = () => {
    api.setAnthropicKey(anthropicKey);
    api.setGeminiKey(geminiKey);
    api.setNvidiaKey(nvidiaKey);
    api.setAutoApplySettings(autoApplySettings);
    onModelChange(localModel);
    if (onSettingsSaved) {
      onSettingsSaved(autoApplySettings);
    }
    setSavedSuccess(true);
    setTimeout(() => {
      setSavedSuccess(false);
      onClose();
    }, 1000);
  };

  const modelOptions = [
    {
      id: 'auto',
      name: '🎯 Smart Auto Cascade (NVIDIA 120B ➡️ Claude ➡️ Gemini ➡️ Ollama)',
      desc: 'Prioritizes NVIDIA Nemotron 120B reasoning, cascading seamlessly to Claude, Gemini & Ollama.',
      badge: 'High Reliability',
      badgeColor: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    },
    {
      id: 'nvidia',
      name: '🟢 NVIDIA Nemotron 3.5 (120B Super - Job Agent Only)',
      desc: 'NVIDIA NIM deep reasoning model with live thinking tokens and tool execution.',
      badge: 'Job Scout LLM',
      badgeColor: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    },
    {
      id: 'claude-3-5-haiku',
      name: '⚡ Claude 3.5 Haiku (Anthropic API)',
      desc: 'Top-tier code generation and complex multi-step reasoning.',
      badge: 'Cloud Intelligence',
      badgeColor: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
    },
    {
      id: 'gemini-1.5-flash',
      name: '💎 Google Gemini 1.5 Flash (Google AI)',
      desc: 'Generous 1,500 free daily requests with sub-second response times.',
      badge: 'Free Tier',
      badgeColor: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    },
    {
      id: 'qwen2.5',
      name: '🏠 Local Ollama (Qwen 2.5 7B)',
      desc: 'Runs 100% locally on your machine. Zero cost, complete data privacy.',
      badge: 'Private & Offline',
      badgeColor: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md animate-fade-in">
      <div className="bg-[#14151f] border border-[#26283b] w-full max-w-xl rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-[#222436] bg-[#11121a]">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-blue-600/15 border border-blue-500/30 flex items-center justify-center text-blue-400">
                <Sparkles className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-100 tracking-tight">System Settings & Automation</h3>
                <p className="text-[11px] text-slate-400">Configure AI models, API keys, and autonomous apply modes</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-[#1f2030] transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Navigation Tabs */}
          <div className="flex items-center gap-2 bg-[#0d0e15] p-1 rounded-xl border border-[#1f2132]">
            <button
              type="button"
              onClick={() => setActiveTab('models')}
              className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-all ${
                activeTab === 'models'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-[#161824]'
              }`}
            >
              <Cpu className="w-3.5 h-3.5" />
              <span>AI Models & Keys</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('auto_apply')}
              className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-all ${
                activeTab === 'auto_apply'
                  ? 'bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-[#161824]'
              }`}
            >
              <Zap className="w-3.5 h-3.5 text-yellow-300" />
              <span>Batch Auto-Apply Mode</span>
              {autoApplySettings.enabled && (
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse ml-0.5" />
              )}
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6">
          {activeTab === 'models' ? (
            <>
              {/* Section 1: Model Selection */}
              <div>
                <div className="flex items-center justify-between mb-2.5">
                  <label className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                    <Cpu className="w-3.5 h-3.5 text-blue-400" /> Execution Model
                  </label>
                  <span className="text-[10px] text-slate-400">Select active engine</span>
                </div>

                <div className="space-y-2">
                  {modelOptions.map((opt) => (
                    <div
                      key={opt.id}
                      onClick={() => setLocalModel(opt.id)}
                      className={`p-3 rounded-xl border cursor-pointer transition-all ${
                        localModel === opt.id
                          ? 'bg-blue-600/10 border-blue-500/50 shadow-sm shadow-blue-500/5'
                          : 'bg-[#181926] border-[#25273a] hover:border-[#353852] hover:bg-[#1c1d2c]'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-bold text-slate-100 flex items-center gap-2">
                          <span className={`w-2 h-2 rounded-full ${localModel === opt.id ? 'bg-blue-400 animate-pulse' : 'bg-slate-600'}`} />
                          {opt.name}
                        </span>
                        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded border ${opt.badgeColor}`}>
                          {opt.badge}
                        </span>
                      </div>
                      <p className="text-[11.5px] text-slate-400 pl-4">{opt.desc}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Section 2: API Keys */}
              <div className="pt-2 border-t border-[#222436] space-y-4">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                    <Key className="w-3.5 h-3.5 text-indigo-400" /> Cloud Provider API Keys
                  </label>
                  <span className="text-[10px] text-slate-400 flex items-center gap-1">
                    <ShieldCheck className="w-3 h-3 text-emerald-400" /> Stored locally in browser
                  </span>
                </div>

                {/* NVIDIA NIM Key */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-medium text-slate-300">NVIDIA NIM API Key</label>
                    <a
                      href="https://build.nvidia.com/"
                      target="_blank"
                      rel="noreferrer"
                      className="text-[11px] text-emerald-400 hover:text-emerald-300 flex items-center gap-1 transition-colors"
                    >
                      Get NVIDIA key <ExternalLink className="w-2.5 h-2.5" />
                    </a>
                  </div>
                  <div className="relative">
                    <input
                      type={showNvidiaKey ? 'text' : 'password'}
                      value={nvidiaKey}
                      onChange={(e) => setNvidiaKey(e.target.value)}
                      placeholder="nvapi-..."
                      className="w-full bg-[#181926] border border-[#2a2c40] rounded-xl px-3 py-2 pr-10 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-emerald-500 font-mono transition-colors"
                    />
                    <button
                      type="button"
                      onClick={() => setShowNvidiaKey(!showNvidiaKey)}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 p-1"
                    >
                      {showNvidiaKey ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                </div>

                {/* Google Gemini Key */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-medium text-slate-300">Google Gemini API Key</label>
                    <a
                      href="https://aistudio.google.com/app/apikey"
                      target="_blank"
                      rel="noreferrer"
                      className="text-[11px] text-blue-400 hover:text-blue-300 flex items-center gap-1 transition-colors"
                    >
                      Get Gemini key <ExternalLink className="w-2.5 h-2.5" />
                    </a>
                  </div>
                  <div className="relative">
                    <input
                      type={showGeminiKey ? 'text' : 'password'}
                      value={geminiKey}
                      onChange={(e) => setGeminiKey(e.target.value)}
                      placeholder="AIzaSy..."
                      className="w-full bg-[#181926] border border-[#2a2c40] rounded-xl px-3 py-2 pr-10 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 font-mono transition-colors"
                    />
                    <button
                      type="button"
                      onClick={() => setShowGeminiKey(!showGeminiKey)}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 p-1"
                    >
                      {showGeminiKey ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                </div>

                {/* Anthropic Key */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-medium text-slate-300">Anthropic Claude API Key</label>
                    <a
                      href="https://console.anthropic.com/"
                      target="_blank"
                      rel="noreferrer"
                      className="text-[11px] text-purple-400 hover:text-purple-300 flex items-center gap-1 transition-colors"
                    >
                      Get Claude key <ExternalLink className="w-2.5 h-2.5" />
                    </a>
                  </div>
                  <div className="relative">
                    <input
                      type={showAnthropicKey ? 'text' : 'password'}
                      value={anthropicKey}
                      onChange={(e) => setAnthropicKey(e.target.value)}
                      placeholder="sk-ant-api03-..."
                      className="w-full bg-[#181926] border border-[#2a2c40] rounded-xl px-3 py-2 pr-10 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-purple-500 font-mono transition-colors"
                    />
                    <button
                      type="button"
                      onClick={() => setShowAnthropicKey(!showAnthropicKey)}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 p-1"
                    >
                      {showAnthropicKey ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                </div>
              </div>
            </>
          ) : (
            /* TAB 2: BATCH AUTO-APPLY MODE CONFIGURATION */
            <div className="space-y-5 animate-fade-in">
              {/* Master Toggle Card */}
              <div
                className={`p-4 rounded-2xl border transition-all ${
                  autoApplySettings.enabled
                    ? 'bg-gradient-to-br from-emerald-950/40 via-[#151a24] to-[#12131d] border-emerald-500/40 shadow-lg shadow-emerald-500/5'
                    : 'bg-[#161724] border-[#282a3e]'
                }`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-3">
                    <div
                      className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 mt-0.5 ${
                        autoApplySettings.enabled
                          ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                          : 'bg-slate-800 text-slate-400 border border-slate-700'
                      }`}
                    >
                      <Zap className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="text-sm font-bold text-slate-100">Batch Auto-Apply Mode</h4>
                        <span
                          className={`text-[9.5px] font-extrabold px-2 py-0.5 rounded-full border ${
                            autoApplySettings.enabled
                              ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                              : 'bg-slate-700/50 text-slate-400 border-slate-600/50'
                          }`}
                        >
                          {autoApplySettings.enabled ? 'ACTIVE • AUTONOMOUS' : 'DISABLED • SAFE MODE'}
                        </span>
                      </div>
                      <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                        When enabled, the multi-agent system automatically tailors resumes and submits applications for qualifying matches without requiring a manual click on each card.
                      </p>
                    </div>
                  </div>

                  {/* Toggle Switch */}
                  <button
                    type="button"
                    onClick={() =>
                      setAutoApplySettings((prev) => ({ ...prev, enabled: !prev.enabled }))
                    }
                    className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                      autoApplySettings.enabled ? 'bg-emerald-500' : 'bg-slate-700'
                    }`}
                  >
                    <span
                      className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out ${
                        autoApplySettings.enabled ? 'translate-x-5' : 'translate-x-0'
                      }`}
                    />
                  </button>
                </div>

                {!autoApplySettings.enabled && (
                  <div className="mt-3.5 pt-3 border-t border-[#25283c] flex items-center gap-2 text-[11px] text-slate-400">
                    <Shield className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                    <span>Safe mode active: You review each job card and click Apply manually.</span>
                  </div>
                )}
              </div>

              {/* Sub-settings (only active/interactive when enabled) */}
              <div
                className={`space-y-4 transition-opacity ${
                  autoApplySettings.enabled ? 'opacity-100' : 'opacity-50 pointer-events-none'
                }`}
              >
                {/* 1. Maximum Batch Size */}
                <div className="p-3.5 rounded-xl bg-[#171927] border border-[#26283b] space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                      <Layers className="w-3.5 h-3.5 text-indigo-400" /> Maximum Applications per Run
                    </label>
                    <span className="text-xs font-bold text-emerald-400">
                      {autoApplySettings.maxBatchSize} Positions
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Limits how many qualifying openings the agent will apply for in a single session.
                  </p>
                  <div className="grid grid-cols-3 gap-2 pt-1">
                    {[3, 5, 10].map((num) => (
                      <button
                        key={num}
                        type="button"
                        onClick={() =>
                          setAutoApplySettings((prev) => ({ ...prev, maxBatchSize: num }))
                        }
                        className={`py-1.5 px-3 rounded-lg text-xs font-semibold border transition-all ${
                          autoApplySettings.maxBatchSize === num
                            ? 'bg-blue-600/20 border-blue-500 text-blue-300 shadow-sm'
                            : 'bg-[#12131e] border-[#222436] text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        Top {num} {num === 5 ? '(Recommended)' : ''}
                      </button>
                    ))}
                  </div>
                </div>

                {/* 2. Minimum ATS Match Filter */}
                <div className="p-3.5 rounded-xl bg-[#171927] border border-[#26283b] space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                      <Sliders className="w-3.5 h-3.5 text-emerald-400" /> Minimum ATS Match Score
                    </label>
                    <span className="text-xs font-bold text-emerald-400">
                      ≥ {autoApplySettings.minMatchScore}% Match
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Positions scoring below this percentage will be skipped to protect application relevance.
                  </p>
                  <div className="grid grid-cols-4 gap-2 pt-1">
                    {[70, 75, 80, 85].map((score) => (
                      <button
                        key={score}
                        type="button"
                        onClick={() =>
                          setAutoApplySettings((prev) => ({ ...prev, minMatchScore: score }))
                        }
                        className={`py-1.5 px-2 rounded-lg text-xs font-semibold border transition-all ${
                          autoApplySettings.minMatchScore === score
                            ? 'bg-emerald-600/20 border-emerald-500 text-emerald-300 shadow-sm'
                            : 'bg-[#12131e] border-[#222436] text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        {score}% {score === 75 ? '★' : ''}
                      </button>
                    ))}
                  </div>
                </div>

                {/* 3. Anti-Bot Stealth Delay */}
                <div className="p-3.5 rounded-xl bg-[#171927] border border-[#26283b] space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5 text-amber-400" /> Stealth Cooldown Interval
                    </label>
                    <span className="text-xs font-bold text-amber-400">
                      {autoApplySettings.stealthDelaySeconds}s Delay
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Randomized delay between submissions to emulate human speed and bypass Akamai bot detection.
                  </p>
                  <div className="grid grid-cols-3 gap-2 pt-1">
                    {[30, 45, 60].map((sec) => (
                      <button
                        key={sec}
                        type="button"
                        onClick={() =>
                          setAutoApplySettings((prev) => ({ ...prev, stealthDelaySeconds: sec }))
                        }
                        className={`py-1.5 px-3 rounded-lg text-xs font-semibold border transition-all ${
                          autoApplySettings.stealthDelaySeconds === sec
                            ? 'bg-amber-600/20 border-amber-500 text-amber-300 shadow-sm'
                            : 'bg-[#12131e] border-[#222436] text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        {sec}s {sec === 45 ? '(Optimal)' : ''}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-4 border-t border-[#222436] bg-[#11121a] flex items-center justify-between">
          <div className="text-[11px]">
            {savedSuccess ? (
              <span className="text-emerald-400 font-medium flex items-center gap-1.5 animate-fade-in">
                <CheckCircle2 className="w-3.5 h-3.5" /> Preferences saved successfully!
              </span>
            ) : (
              <span className="text-slate-500">
                {activeTab === 'auto_apply'
                  ? autoApplySettings.enabled
                    ? '⚡ Batch apply will execute autonomously'
                    : '🛡️ Safe mode: manual confirmation active'
                  : 'API keys remain strictly in browser storage'}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="px-3.5 py-1.5 rounded-xl text-xs font-medium text-slate-300 hover:text-white hover:bg-[#1f2030] transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              className="px-4 py-1.5 rounded-xl text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white shadow-md shadow-blue-600/20 transition-all flex items-center gap-1.5"
            >
              <Check className="w-3.5 h-3.5" /> Save Changes
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
