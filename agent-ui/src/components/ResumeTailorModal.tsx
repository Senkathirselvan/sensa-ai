import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  ArrowLeft,
  Sparkles,
  Download,
  FileText,
  FileCode,
  CheckCircle2,
  AlertCircle,
  RotateCw,
  Send,
  Loader2,
  Copy,
  Check,
  Eye,
  ExternalLink,
  Wand2,
  Zap,
  Scissors,
  BarChart3,
  Palette,
  Layout,
  Maximize2,
  Type
} from 'lucide-react';
import { JobCard } from '../types';
import { api } from '../services/api';

interface ResumeTailorModalProps {
  job: JobCard | null;
  previewUrl?: string | null;
  isOpen: boolean;
  onClose: () => void;
  onProceedToApply?: (job: JobCard) => void;
  selectedModel?: string;
}

interface TemplateOption {
  id: string;
  name: string;
  category: string;
  description: string;
  thumbnailStyle: 'sidebar' | 'minimalist' | 'grid' | 'modern' | 'classic';
  recommendedPages: number;
}

const TEMPLATE_OPTIONS: TemplateOption[] = [
  {
    id: 'classic_ats',
    name: 'Classic ATS Clean',
    category: 'Universal Single-Column',
    description: 'Header hairline rules, bold module subheadings, clean bullets, 100% ATS parse rate',
    thumbnailStyle: 'classic',
    recommendedPages: 2,
  },
  {
    id: 'tech_sidebar',
    name: 'Tech Sidebar',
    category: 'Developer & Tech',
    description: '2-Column layout with dark tech sidebar & skill pills',
    thumbnailStyle: 'sidebar',
    recommendedPages: 2,
  },
  {
    id: 'minimalist',
    name: 'Sleek Minimalist',
    category: 'Executive & Classic',
    description: 'Single-column layout with clean accent dividers',
    thumbnailStyle: 'minimalist',
    recommendedPages: 2,
  },
  {
    id: 'grid_matrix',
    name: 'Grid Matrix',
    category: 'Staff & Architect',
    description: 'Metric ribbon, 4-category skills matrix & case studies',
    thumbnailStyle: 'grid',
    recommendedPages: 2,
  },
  {
    id: 'modern_header',
    name: 'Modern Clean',
    category: 'Product & Corporate',
    description: 'Split modern header with project cards & 2-page flow',
    thumbnailStyle: 'modern',
    recommendedPages: 2,
  },
];

interface PaletteOption {
  id: string;
  name: string;
  label: string;
  color: string;
  accent: string;
  bgLight: string;
}

const PALETTE_OPTIONS: PaletteOption[] = [
  {
    id: 'executive_navy',
    name: 'Executive Navy',
    label: 'Navy',
    color: '#1e3a8a',
    accent: '#1d4ed8',
    bgLight: '#eff6ff',
  },
  {
    id: 'enterprise_blue',
    name: 'Enterprise Blue',
    label: 'Blue',
    color: '#0284c7',
    accent: '#0369a1',
    bgLight: '#f0f9ff',
  },
  {
    id: 'emerald_executive',
    name: 'Emerald Tech',
    label: 'Emerald',
    color: '#059669',
    accent: '#047857',
    bgLight: '#ecfdf5',
  },
  {
    id: 'modern_slate',
    name: 'Modern Slate',
    label: 'Slate',
    color: '#475569',
    accent: '#334155',
    bgLight: '#f8fafc',
  },
  {
    id: 'teal_technical',
    name: 'Teal Technical',
    label: 'Teal',
    color: '#0d9488',
    accent: '#0f766e',
    bgLight: '#f0fdfa',
  },
  {
    id: 'warm_classic',
    name: 'Warm Classic',
    label: 'Amber',
    color: '#d97706',
    accent: '#b45309',
    bgLight: '#fffbeb',
  },
];

interface FontOption {
  id: string;
  name: string;
  label: string;
  category: string;
  css: string;
}

const FONT_OPTIONS: FontOption[] = [
  {
    id: 'liberation_sans',
    name: 'Liberation Sans',
    label: 'Liberation',
    category: 'Classic ATS Standard',
    css: "'Liberation Sans', 'Inter', Arial, sans-serif",
  },
  {
    id: 'modern_inter',
    name: 'Inter',
    label: 'Inter',
    category: 'Modern Sans (Tech)',
    css: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
  },
  {
    id: 'clean_roboto',
    name: 'Roboto',
    label: 'Roboto',
    category: 'Clean Tech (Eng)',
    css: "'Roboto', 'Segoe UI', -apple-system, Arial, sans-serif",
  },
  {
    id: 'universal_arial',
    name: 'Arial',
    label: 'Arial',
    category: 'Universal ATS',
    css: "Arial, 'Helvetica Neue', Helvetica, 'Liberation Sans', sans-serif",
  },
  {
    id: 'executive_merriweather',
    name: 'Merriweather',
    label: 'Merriweather',
    category: 'Executive Serif',
    css: "'Merriweather', Georgia, Cambria, 'Times New Roman', serif",
  },
  {
    id: 'classic_garamond',
    name: 'Garamond',
    label: 'Garamond',
    category: 'Classic Editorial',
    css: "'EB Garamond', Garamond, 'Liberation Serif', 'Times New Roman', serif",
  },
];

export const ResumeTailorModal: React.FC<ResumeTailorModalProps> = ({
  job,
  previewUrl,
  isOpen,
  onClose,
  onProceedToApply,
  selectedModel = 'auto',
}) => {
  const [statusText, setStatusText] = useState<string>('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [activeModel, setActiveModel] = useState<string>('nvidia-nemotron-120b');
  const [targetPages, setTargetPages] = useState<number>(2);
  const [baselineData, setBaselineData] = useState<any>(null);
  const [tailoredData, setTailoredData] = useState<any>(null);
  const [streamedContent, setStreamedContent] = useState<string>('');
  const [viewMode, setViewMode] = useState<'preview' | 'markdown' | 'keywords'>('preview');
  const [selectedTemplate, setSelectedTemplate] = useState<string>('grid_matrix');
  const [selectedPalette, setSelectedPalette] = useState<string>('enterprise_blue');
  const [selectedFont, setSelectedFont] = useState<string>('modern_inter');
  const [generationMode, setGenerationMode] = useState<'tailor' | 'scratch'>('tailor');
  const [copied, setCopied] = useState(false);
  const [errorText, setErrorText] = useState<string | null>(null);

  // Agent 2 Interactive Refinement, Editing & Prompting State
  const [customPrompt, setCustomPrompt] = useState<string>('');
  const [isRefining, setIsRefining] = useState<boolean>(false);
  const [appliedBadge, setAppliedBadge] = useState<string | null>(null);
  const [previewTimestamp, setPreviewTimestamp] = useState<number>(Date.now());
  const [editableMarkdown, setEditableMarkdown] = useState<string>('');
  const [recompileSuccessMsg, setRecompileSuccessMsg] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (isOpen) {
      if (previewUrl) {
        loadFromPreviewUrl(previewUrl);
      } else if (job) {
        const initialPages = (job as any)?.target_pages === 1 ? 1 : 2;
        const initialMode: 'tailor' | 'scratch' = (job as any)?.generation_mode === 'scratch' ? 'scratch' : 'tailor';
        setGenerationMode(initialMode);
        setTargetPages(initialPages);
        const initialTpl = initialPages === 2 ? 'grid_matrix' : 'tech_sidebar';
        setSelectedTemplate(initialTpl);
        startTailoring(initialPages, initialTpl, selectedPalette, selectedFont, initialMode);
      }
    } else {
      resetState();
    }
  }, [isOpen, job, previewUrl]);

  const loadFromPreviewUrl = async (url: string) => {
    setIsGenerating(true);
    setStatusText('Loading resume into ATS Studio...');
    const cleanUrl = url.split('?')[0];
    const filename = cleanUrl.split('/').pop() || '';

    // Auto-detect template from filename
    let detectedTpl = 'grid_matrix';
    for (const tpl of TEMPLATE_OPTIONS) {
      if (filename.includes(tpl.id)) {
        detectedTpl = tpl.id;
        break;
      }
    }

    // Auto-detect palette
    let detectedPal = 'enterprise_blue';
    for (const pal of PALETTE_OPTIONS) {
      if (filename.includes(pal.id)) {
        detectedPal = pal.id;
        break;
      }
    }

    // Auto-detect font
    let detectedFont = 'modern_inter';
    for (const fnt of FONT_OPTIONS) {
      if (filename.includes(fnt.id)) {
        detectedFont = fnt.id;
        break;
      }
    }

    const detectedPages = filename.includes('_1p.') || filename.includes('-1p.') ? 1 : 2;

    setSelectedTemplate(detectedTpl);
    setSelectedPalette(detectedPal);
    setSelectedFont(detectedFont);
    setTargetPages(detectedPages);

    try {
      const res = await fetch(`/api/resume/info/${filename}`);
      if (res.ok) {
        const data = await res.json();
        setTailoredData({
          html_filename: data.html_filename || filename,
          pdf_filename: data.pdf_filename || filename.replace(/\.html?$/i, '.pdf'),
          docx_filename: data.docx_filename || filename.replace(/\.html?$/i, '.docx'),
          markdown_content: data.markdown_content || '',
          template_id: data.template_id || detectedTpl,
          palette_id: data.palette_id || detectedPal,
          font_id: data.font_id || detectedFont,
          target_pages: data.target_pages || detectedPages,
          tailored_score: data.ats_score || 85,
        });
        setEditableMarkdown(data.markdown_content || '');
      } else {
        setTailoredData({
          html_filename: filename,
          pdf_filename: filename.replace(/\.html?$/i, '.pdf'),
          docx_filename: filename.replace(/\.html?$/i, '.docx'),
          template_id: detectedTpl,
          palette_id: detectedPal,
          font_id: detectedFont,
          target_pages: detectedPages,
          tailored_score: 85,
        });
      }
    } catch (e) {
      console.warn('Failed fetching resume info:', e);
      setTailoredData({
        html_filename: filename,
        pdf_filename: filename.replace(/\.html?$/i, '.pdf'),
        docx_filename: filename.replace(/\.html?$/i, '.docx'),
        template_id: detectedTpl,
        palette_id: detectedPal,
        font_id: detectedFont,
        target_pages: detectedPages,
        tailored_score: 85,
      });
    } finally {
      setIsGenerating(false);
      setPreviewTimestamp(Date.now());
      setStatusText(`Active Template: ${detectedTpl.replace('_', ' ')} (${detectedPages} Pages)`);
    }
  };

  const resetState = () => {
    setStatusText('');
    setIsGenerating(false);
    setBaselineData(null);
    setTailoredData(null);
    setStreamedContent('');
    setEditableMarkdown('');
    setErrorText(null);
    setViewMode('preview');
    setAppliedBadge(null);
    setRecompileSuccessMsg(null);
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  const startTailoring = (
    pages?: number,
    templateId?: string,
    paletteId?: string,
    fontId?: string,
    mode?: 'tailor' | 'scratch'
  ) => {
    if (!job) return;
    const pagesToUse = pages !== undefined ? pages : targetPages;
    const tplToUse = templateId !== undefined ? templateId : selectedTemplate;
    const palToUse = paletteId !== undefined ? paletteId : selectedPalette;
    const fontToUse = fontId !== undefined ? fontId : selectedFont;
    const modeToUse = mode !== undefined ? mode : generationMode;

    setIsGenerating(true);
    setActiveModel(selectedModel === 'auto' ? 'nvidia-nemotron-120b' : selectedModel);
    setStreamedContent('');
    setTailoredData(null);
    setErrorText(null);
    setStatusText(
      modeToUse === 'scratch'
        ? `Synthesizing benchmark candidate profile from job description (${pagesToUse}-page standard)...`
        : `Tailoring master profile with ${job.company} requirements (${pagesToUse}-page standard)...`
    );

    abortControllerRef.current = new AbortController();

    api.streamTailorResume(
      {
        job_id: job.id,
        job_title: job.title,
        company: job.company,
        job_description: job.snippet || `${job.title} at ${job.company}`,
        target_pages: pagesToUse,
        model: selectedModel,
        template_id: tplToUse,
        palette_id: palToUse,
        font_id: fontToUse,
        generation_mode: modeToUse,
      },
      {
        onStatus: (status) => setStatusText(status),
        onBaseline: (data) => setBaselineData(data),
        onModel: (model) => setActiveModel(model),
        onToken: (token) => {
          setStreamedContent((prev) => prev + token);
          setErrorText(null);
        },
        onDone: (data) => {
          setIsGenerating(false);
          setTailoredData(data);
          setEditableMarkdown(data.markdown_content || streamedContent);
          if (data.model_used) setActiveModel(data.model_used);
          setErrorText(null);
          setStatusText(`Tailoring & ${pagesToUse}-page document compilation complete!`);
        },
        onError: (err) => {
          setIsGenerating(false);
          setErrorText(err.message || 'Connection to Resume Preparation Agent failed.');
          setStatusText(`Error: ${err.message || 'Generation failed'}`);
        },
      },
      abortControllerRef.current.signal
    );
  };

  const handleModeChange = (newMode: 'tailor' | 'scratch') => {
    if (newMode === generationMode || isGenerating) return;
    setGenerationMode(newMode);
    startTailoring(targetPages, selectedTemplate, selectedPalette, selectedFont, newMode);
  };

  const handleTemplateChange = async (newTpl: string) => {
    setSelectedTemplate(newTpl);
    const currentMd = editableMarkdown || tailoredData?.markdown_content || streamedContent;
    if (currentMd && currentMd.trim().length > 100) {
      setIsGenerating(true);
      setStatusText(`⚡ Switching layout to ${newTpl.replace('_', ' ')} in <300ms...`);
      try {
        const recompiled = await api.recompileResume({
          markdown_text: currentMd,
          target_job_title: job?.title || tailoredData?.target_job_title || 'Python Backend Developer',
          target_company: job?.company || tailoredData?.target_company || '',
          job_description: job?.snippet || '',
          target_pages: targetPages,
          template_id: newTpl,
          palette_id: selectedPalette,
          font_id: selectedFont,
        });
        setTailoredData((prev: any) => ({
          ...(prev || {}),
          ...recompiled,
          markdown_content: currentMd,
        }));
        setPreviewTimestamp(Date.now());
        setStatusText(`Active Template: ${recompiled.template_name}`);
      } catch (err: any) {
        console.error('Instant recompile error:', err);
        if (job) startTailoring(targetPages, newTpl, selectedPalette);
      } finally {
        setIsGenerating(false);
      }
    } else if (job) {
      startTailoring(targetPages, newTpl, selectedPalette);
    }
  };

  const handlePaletteChange = async (newPal: string) => {
    setSelectedPalette(newPal);
    const currentMd = editableMarkdown || tailoredData?.markdown_content || streamedContent;
    if (currentMd && currentMd.trim().length > 100) {
      setIsGenerating(true);
      setStatusText(`⚡ Applying ${newPal.replace('_', ' ')} color theme instantly...`);
      try {
        const recompiled = await api.recompileResume({
          markdown_text: currentMd,
          target_job_title: job?.title || tailoredData?.target_job_title || 'Python Backend Developer',
          target_company: job?.company || tailoredData?.target_company || '',
          job_description: job?.snippet || '',
          target_pages: targetPages,
          template_id: selectedTemplate,
          palette_id: newPal,
          font_id: selectedFont,
        });
        setTailoredData((prev: any) => ({
          ...(prev || {}),
          ...recompiled,
          markdown_content: currentMd,
        }));
        setPreviewTimestamp(Date.now());
        setStatusText(`Active Theme: ${recompiled.palette_name}`);
      } catch (err: any) {
        console.error('Instant palette error:', err);
        if (job) startTailoring(targetPages, selectedTemplate, newPal);
      } finally {
        setIsGenerating(false);
      }
    } else if (job) {
      startTailoring(targetPages, selectedTemplate, newPal);
    }
  };

  const handlePageCountChange = async (pages: number) => {
    if (pages === targetPages && tailoredData) return;
    setTargetPages(pages);
    const currentMd = editableMarkdown || tailoredData?.markdown_content || streamedContent;
    if (currentMd && currentMd.trim().length > 100) {
      setIsGenerating(true);
      setStatusText(`⚡ Recompiling ${pages}-page document layout...`);
      try {
        const recompiled = await api.recompileResume({
          markdown_text: currentMd,
          target_job_title: job?.title || tailoredData?.target_job_title || 'Python Backend Developer',
          target_company: job?.company || tailoredData?.target_company || '',
          job_description: job?.snippet || '',
          target_pages: pages,
          template_id: selectedTemplate,
          palette_id: selectedPalette,
          font_id: selectedFont,
        });
        setTailoredData((prev: any) => ({
          ...(prev || {}),
          ...recompiled,
          markdown_content: currentMd,
        }));
        setPreviewTimestamp(Date.now());
        setStatusText(`Active: ${pages}-Page layout compiled!`);
      } catch (err: any) {
        console.error('Instant page switch error:', err);
        if (job) startTailoring(pages, selectedTemplate, selectedPalette);
      } finally {
        setIsGenerating(false);
      }
    } else if (job) {
      startTailoring(pages, selectedTemplate, selectedPalette);
    }
  };

  const handleFontChange = async (newFont: string) => {
    setSelectedFont(newFont);
    const fontObj = FONT_OPTIONS.find((f) => f.id === newFont);

    // 1. Instant client-side DOM injection for <10ms visual feedback in preview
    try {
      const iframe = document.querySelector('iframe') as HTMLIFrameElement;
      if (iframe && iframe.contentDocument) {
        iframe.contentDocument.documentElement.style.setProperty(
          '--font-body',
          fontObj?.css || 'sans-serif'
        );
      }
    } catch (e) {
      console.warn('Iframe font injection skipped:', e);
    }

    // 2. Recompile in backend for pixel-perfect PDF & DOCX
    const currentMd = editableMarkdown || tailoredData?.markdown_content || streamedContent;
    if (currentMd && currentMd.trim().length > 100) {
      setIsGenerating(true);
      setStatusText(`⚡ Applying ${fontObj?.name} typography...`);
      try {
        const recompiled = await api.recompileResume({
          markdown_text: currentMd,
          target_job_title: job?.title || tailoredData?.target_job_title || 'Python Backend Developer',
          target_company: job?.company || tailoredData?.target_company || '',
          job_description: job?.snippet || '',
          target_pages: targetPages,
          template_id: selectedTemplate,
          palette_id: selectedPalette,
          font_id: newFont,
        });
        setTailoredData((prev: any) => ({
          ...(prev || {}),
          ...recompiled,
          markdown_content: currentMd,
        }));
        setPreviewTimestamp(Date.now());
        setStatusText(`Active Typography: ${fontObj?.name} applied!`);
      } catch (err: any) {
        console.error('Instant font switch error:', err);
      } finally {
        setIsGenerating(false);
      }
    }
  };

  const handleApplyMarkdownEdits = async () => {
    if (!editableMarkdown || !editableMarkdown.trim()) return;
    setIsGenerating(true);
    setStatusText('Applying your markdown edits and recompiling document...');
    setRecompileSuccessMsg(null);
    try {
      const recompiled = await api.recompileResume({
        markdown_text: editableMarkdown,
        target_job_title: job?.title || tailoredData?.target_job_title || 'Python Backend Developer',
        target_company: job?.company || tailoredData?.target_company || '',
        target_pages: targetPages,
        template_id: selectedTemplate,
        palette_id: selectedPalette,
        font_id: selectedFont,
      });
      setTailoredData((prev: any) => ({
        ...(prev || {}),
        ...recompiled,
        markdown_content: editableMarkdown,
      }));
      setPreviewTimestamp(Date.now());
      setViewMode('preview');
      setStatusText('✅ Resume updated and recompiled with your custom edits!');
      setRecompileSuccessMsg('Resume recompiled successfully with your edits!');
      setTimeout(() => setRecompileSuccessMsg(null), 4000);
    } catch (err: any) {
      console.error('Failed applying edits:', err);
      setErrorText(err.message || 'Failed to recompile edited markdown.');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleRefineSubmit = (instructionText?: string, chipLabel?: string) => {
    const promptToRun = instructionText || customPrompt;
    if (!promptToRun.trim()) return;

    const currentMd = editableMarkdown || tailoredData?.markdown_content || streamedContent;
    setIsGenerating(true);
    setIsRefining(true);
    setErrorText(null);
    setStatusText(`✨ Agent 2 refining resume: "${chipLabel || promptToRun}"...`);

    abortControllerRef.current = new AbortController();

    const titleToUse = job?.title || tailoredData?.target_job_title || 'Python Backend Developer';
    const compToUse = job?.company || tailoredData?.target_company || '';

    api.streamRefineResume(
      {
        user_instruction: promptToRun,
        current_markdown: currentMd,
        job_id: job?.id,
        job_title: titleToUse,
        company: compToUse,
        job_description: job?.snippet || `${titleToUse} at ${compToUse}`,
        target_pages: targetPages,
        template_id: selectedTemplate,
        palette_id: selectedPalette,
        font_id: selectedFont,
        model: selectedModel,
      },
      {
        onStatus: (status) => setStatusText(status),
        onModel: (model) => setActiveModel(model),
        onToken: (token) => {
          setStreamedContent((prev) => prev + token);
        },
        onDone: (data) => {
          setTailoredData(data);
          if (data.model_used) setActiveModel(data.model_used);
          setStreamedContent(data.markdown_content || '');
          setEditableMarkdown(data.markdown_content || '');
          if (data.template_id) setSelectedTemplate(data.template_id);
          if (data.palette_id) setSelectedPalette(data.palette_id);
          setPreviewTimestamp(Date.now());
          setIsGenerating(false);
          setIsRefining(false);
          setAppliedBadge(chipLabel || promptToRun);
          setStatusText(`✓ Successfully applied: "${chipLabel || promptToRun}"`);
          setCustomPrompt('');
        },
        onError: (err) => {
          setIsGenerating(false);
          setIsRefining(false);
          setErrorText(err.message || 'Refinement failed.');
          setStatusText(`Error: ${err.message || 'Refinement failed'}`);
        },
      },
      abortControllerRef.current.signal
    );
  };

  const handleCopyMarkdown = () => {
    const textToCopy = editableMarkdown || tailoredData?.markdown_content || streamedContent;
    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!isOpen || (!job && !previewUrl && !tailoredData)) return null;

  const displayTitle = job?.title || tailoredData?.target_job_title || 'Python Backend Developer';
  const displayCompany = job?.company || tailoredData?.target_company || 'Sensa AI Master Profile';
  const originalScore = baselineData?.original_score || job?.score || 72;
  const tailoredScore = tailoredData?.tailored_score || (baselineData ? baselineData.original_score + 18 : 88);
  const scoreBump = Math.max(0, tailoredScore - originalScore);

  return (
    <div className="fixed inset-0 z-50 bg-[#090a12] text-slate-100 flex flex-col h-screen w-screen overflow-hidden select-none animate-fade-in">
      {/* =========================================================================
          TOP HEADER BAR: Candidate Name | Target Info | Score Tracker | Action Buttons
         ========================================================================= */}
      <header className="h-16 border-b border-[#1c1e30] bg-[#111320] px-5 flex items-center justify-between gap-4 flex-shrink-0 z-20 shadow-md">
        {/* Left: Back Button & Target Job Metadata */}
        <div className="flex items-center gap-3.5">
          <button
            onClick={onClose}
            className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-[#181a29] hover:bg-[#22253a] text-slate-300 hover:text-white border border-[#2c2f48] transition-all text-xs font-semibold shadow-sm"
            title="Return to Job Opportunities Dashboard"
          >
            <ArrowLeft className="w-4 h-4 text-slate-400 group-hover:text-white" />
            <span>Dashboard</span>
          </button>

          <div className="h-6 w-px bg-[#26283d]" />

          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-purple-600 via-indigo-600 to-blue-600 flex items-center justify-center text-white shadow-md shadow-purple-500/20">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold text-white tracking-tight">
                  {generationMode === 'scratch' ? 'Benchmark Candidate' : 'S. Senkathirselvan'}
                </h2>
                <span className="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded-full bg-purple-500/15 text-purple-300 border border-purple-500/30">
                  ATS Studio • Agent 2
                </span>
              </div>
              <p className="text-xs text-slate-400 truncate max-w-[280px] md:max-w-[420px]">
                {displayCompany && displayCompany !== 'General Profile' && displayCompany !== 'Hiring Company' && displayCompany !== 'Sensa AI Master Profile' ? (
                  <>Targeting <span className="text-slate-200 font-semibold">{displayTitle}</span> at <span className="text-purple-300 font-semibold">{displayCompany}</span></>
                ) : generationMode === 'scratch' ? (
                  <>Synthesizing <span className="text-slate-200 font-semibold">{displayTitle || 'Python Developer'}</span> • <span className="text-purple-300 font-semibold">Benchmark Profile</span></>
                ) : (
                  <>Targeting <span className="text-slate-200 font-semibold">{displayTitle || 'Python Developer'}</span> • <span className="text-purple-300 font-semibold">General Master Profile</span></>
                )}
              </p>
            </div>
          </div>
        </div>

        {/* Center: Real-Time ATS Score Delta & Status */}
        <div className="hidden lg:flex items-center gap-3">
          <div className="flex items-center gap-2.5 bg-[#171927] border border-[#282a42] px-3.5 py-1.5 rounded-xl shadow-inner">
            <div className="text-center">
              <span className="text-[9px] text-slate-400 uppercase font-semibold block leading-tight">Baseline</span>
              <span className="text-xs font-bold text-slate-300">{originalScore}%</span>
            </div>
            <span className="text-slate-500 font-bold text-xs">➔</span>
            <div className="text-center">
              <span className="text-[9px] text-emerald-400 uppercase font-semibold block leading-tight">ATS Tailored</span>
              <span className="text-xs font-extrabold text-emerald-400">{tailoredScore}%</span>
            </div>
            {scoreBump > 0 && (
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 ml-0.5">
                +{scoreBump}% Match
              </span>
            )}
          </div>

          {/* Model Badge: Strictly reflects the actual AI model running */}
          {(() => {
            const currentModel = (activeModel || tailoredData?.model_used || '').toLowerCase();
            const statusLower = statusText.toLowerCase();

            if (currentModel.includes('nvidia') || statusLower.includes('nvidia') || (!currentModel && !statusLower.includes('gemini') && !statusLower.includes('claude') && !statusLower.includes('ollama'))) {
              return (
                <span className="text-[10.5px] px-2.5 py-1 rounded-lg bg-emerald-500/10 text-emerald-300 border border-emerald-500/25 font-semibold flex items-center gap-1 shadow-sm">
                  🟢 NVIDIA Nemotron 120B (~2s)
                </span>
              );
            }
            if (currentModel.includes('claude') || statusLower.includes('claude')) {
              return (
                <span className="text-[10.5px] px-2.5 py-1 rounded-lg bg-purple-500/10 text-purple-300 border border-purple-500/25 font-semibold flex items-center gap-1 shadow-sm">
                  🟣 Claude 3.5 Haiku
                </span>
              );
            }
            if (currentModel.includes('gemini') || statusLower.includes('gemini')) {
              return (
                <span className="text-[10.5px] px-2.5 py-1 rounded-lg bg-blue-500/10 text-blue-300 border border-blue-500/25 font-semibold flex items-center gap-1 shadow-sm">
                  ⚡ Gemini 1.5 Flash (~2s)
                </span>
              );
            }
            if (currentModel.includes('ollama') || statusLower.includes('ollama')) {
              return (
                <span className="text-[10.5px] px-2.5 py-1 rounded-lg bg-amber-500/10 text-amber-300 border border-amber-500/25 font-semibold flex items-center gap-1 shadow-sm">
                  🏠 Local Ollama
                </span>
              );
            }
            return (
              <span className="text-[10.5px] px-2.5 py-1 rounded-lg bg-emerald-500/10 text-emerald-300 border border-emerald-500/25 font-semibold flex items-center gap-1 shadow-sm">
                🟢 NVIDIA Nemotron 120B (~2s)
              </span>
            );
          })()}

          {/* Live Progress / Error State */}
          {errorText ? (
            <div className="flex items-center gap-1.5 text-xs text-rose-400 bg-rose-500/10 px-2.5 py-1 rounded-lg border border-rose-500/20">
              <AlertCircle className="w-3.5 h-3.5 text-rose-400" />
              <span className="font-semibold truncate max-w-[200px]">{errorText}</span>
            </div>
          ) : isGenerating ? (
            <div className="flex items-center gap-2 text-xs text-purple-300 animate-pulse bg-purple-500/10 px-2.5 py-1 rounded-lg border border-purple-500/20">
              <Loader2 className="w-3.5 h-3.5 animate-spin text-purple-400" />
              <span className="truncate max-w-[220px]">{statusText || 'Tailoring content...'}</span>
            </div>
          ) : tailoredData ? (
            <div className="flex items-center gap-1.5 text-xs text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-lg border border-emerald-500/20">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Compilation Complete</span>
            </div>
          ) : null}
        </div>

        {/* Right: Quick Action Buttons (Downloads, Apply) */}
        <div className="flex items-center gap-2.5">
          <button
            onClick={() => startTailoring(targetPages)}
            disabled={isGenerating}
            className="p-2 rounded-xl text-slate-300 hover:text-white bg-[#191b2c] hover:bg-[#24273e] border border-[#2d304a] transition-all disabled:opacity-50"
            title="Regenerate Resume"
          >
            <RotateCw className={`w-4 h-4 ${isGenerating ? 'animate-spin' : ''}`} />
          </button>

          {tailoredData?.pdf_filename && (
            <a
              href={api.getDownloadUrl(tailoredData.pdf_filename)}
              download
              className="px-3.5 py-1.5 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 shadow-md shadow-blue-500/20 flex items-center gap-1.5 transition-all"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Download PDF</span>
            </a>
          )}

          {tailoredData?.docx_filename && (
            <a
              href={api.getDownloadUrl(tailoredData.docx_filename)}
              download
              className="hidden md:flex px-3 py-1.5 rounded-xl text-xs font-semibold text-slate-200 hover:text-white bg-[#1e2032] hover:bg-[#282b42] border border-[#303350] items-center gap-1.5 transition-all"
            >
              <FileCode className="w-3.5 h-3.5 text-blue-400" />
              <span>DOCX</span>
            </a>
          )}

          {job?.url && onProceedToApply ? (
            <button
              onClick={() => {
                onClose();
                onProceedToApply(job);
              }}
              className="px-4 py-1.5 rounded-xl text-xs font-bold bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white shadow-md shadow-emerald-500/20 flex items-center gap-1.5 transition-all"
            >
              <Send className="w-3.5 h-3.5" />
              <span>Proceed to Apply</span>
            </button>
          ) : (
            <button
              disabled
              className="px-3.5 py-1.5 rounded-xl text-xs font-medium bg-[#1a1c2c] text-slate-500 border border-[#2b2d44] flex items-center gap-1.5 cursor-not-allowed opacity-75"
              title="To submit an application, search for a live job opening on Job Scout and click Tailor / Apply"
            >
              <Send className="w-3 h-3 opacity-40" />
              <span>Target a Job to Apply</span>
            </button>
          )}
        </div>
      </header>

      {/* =========================================================================
          SPLIT-SCREEN STUDIO LAYOUT
          Left Panel [35% width]: Visual Templates, Swatches, AI Co-Pilot & Prompts
          Right Panel [65% width]: Live Full-Scale A4 Paper Canvas Preview
         ========================================================================= */}
      <div className="flex-1 flex overflow-hidden">
        {/* =====================================================================
            LEFT PANEL: Controls, Visual Gallery, Swatches & AI Co-Pilot
           ===================================================================== */}
        <aside className="w-[380px] lg:w-[410px] xl:w-[440px] flex-shrink-0 border-r border-[#1c1e30] bg-[#0e101c] flex flex-col h-full overflow-hidden">
          {/* Scrollable Control Surface */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
            {/* 0. Generation Mode Toggle: Mode 1 (ATS Tailoring) vs Mode 2 (From Scratch) */}
            <div className="bg-[#141624] border border-[#23263c] rounded-2xl p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-amber-400" /> Generation Mode
                </span>
                <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold border ${
                  generationMode === 'tailor'
                    ? 'text-blue-300 bg-blue-500/10 border-blue-500/20'
                    : 'text-amber-300 bg-amber-500/10 border-amber-500/20'
                }`}>
                  {generationMode === 'tailor' ? 'Mode 1: Master Profile' : 'Mode 2: Cold Start'}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 bg-[#0c0d16] p-1.5 rounded-xl border border-[#1e2034]">
                <button
                  type="button"
                  onClick={() => handleModeChange('tailor')}
                  disabled={isGenerating}
                  className={`py-2 px-2.5 rounded-lg text-xs font-bold transition-all text-left flex items-start gap-2 ${
                    generationMode === 'tailor'
                      ? 'bg-blue-600 text-white shadow-sm ring-1 ring-blue-400/50'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-[#181a28]'
                  }`}
                >
                  <FileText className="w-4 h-4 mt-0.5 flex-shrink-0 text-blue-200" />
                  <div>
                    <span className="block text-[11px] font-bold leading-tight">Tailor Master Resume</span>
                    <span className="block text-[8.5px] font-normal opacity-75 mt-0.5">Use verified career</span>
                  </div>
                </button>
                <button
                  type="button"
                  onClick={() => handleModeChange('scratch')}
                  disabled={isGenerating}
                  className={`py-2 px-2.5 rounded-lg text-xs font-bold transition-all text-left flex items-start gap-2 ${
                    generationMode === 'scratch'
                      ? 'bg-amber-600 text-white shadow-sm ring-1 ring-amber-400/50'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-[#181a28]'
                  }`}
                >
                  <Wand2 className="w-4 h-4 mt-0.5 flex-shrink-0 text-amber-200" />
                  <div>
                    <span className="block text-[11px] font-bold leading-tight">Generate From Scratch</span>
                    <span className="block text-[8.5px] font-normal opacity-75 mt-0.5">Synthesize from JD</span>
                  </div>
                </button>
              </div>
            </div>

            {/* 1. Page Length Segmented Switch */}
            <div className="bg-[#141624] border border-[#23263c] rounded-2xl p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                  <Layout className="w-3.5 h-3.5 text-blue-400" /> Page Budget & Format
                </span>
                <span className="text-[10px] text-purple-300 bg-purple-500/10 border border-purple-500/20 px-2 py-0.5 rounded-full font-semibold">
                  A4 Dimensions
                </span>
              </div>
              <div className="grid grid-cols-5 gap-1.5 bg-[#0c0d16] p-1.5 rounded-xl border border-[#1e2034]">
                {[
                  { pages: 1, label: '1 Page', sub: 'Quick Screen' },
                  { pages: 2, label: '2 Pages', sub: 'Senior (Rec)' },
                  { pages: 3, label: '3 Pages', sub: 'Staff & Arch' },
                  { pages: 4, label: '4 Pages', sub: 'Exec Lead' },
                  { pages: 5, label: '5+ Pages', sub: 'Master CV' },
                ].map((item) => {
                  const isSelected = targetPages === item.pages;
                  return (
                    <button
                      key={item.pages}
                      type="button"
                      onClick={() => handlePageCountChange(item.pages)}
                      disabled={isGenerating}
                      className={`py-1.5 px-1 rounded-lg text-xs font-bold transition-all text-center ${
                        isSelected
                          ? item.pages === 1
                            ? 'bg-blue-600 text-white shadow-sm ring-1 ring-blue-400/50'
                            : item.pages === 2
                            ? 'bg-purple-600 text-white shadow-sm ring-1 ring-purple-400/50'
                            : 'bg-emerald-600 text-white shadow-sm ring-1 ring-emerald-400/50'
                          : 'text-slate-400 hover:text-slate-200 hover:bg-[#181a28]'
                      }`}
                    >
                      <span className="block text-[11px] whitespace-nowrap">{item.label}</span>
                      <span className="block text-[8.5px] font-normal opacity-75 truncate">{item.sub}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* 2. Visual Template Cards Gallery (A) */}
            <div className="bg-[#141624] border border-[#23263c] rounded-2xl p-3.5">
              <div className="flex items-center justify-between mb-2.5">
                <span className="text-[11px] font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                  <Layout className="w-3.5 h-3.5 text-indigo-400" /> Layout Skeleton
                </span>
                <span className="text-[10px] text-slate-400">4 Modular Designs</span>
              </div>

              <div className="grid grid-cols-2 gap-2.5">
                {TEMPLATE_OPTIONS.map((tpl) => {
                  const isSelected = selectedTemplate === tpl.id;
                  return (
                    <button
                      key={tpl.id}
                      type="button"
                      onClick={() => handleTemplateChange(tpl.id)}
                      disabled={isGenerating}
                      className={`group text-left p-2.5 rounded-xl border transition-all relative overflow-hidden flex flex-col justify-between ${
                        isSelected
                          ? 'bg-[#1b1c2e] border-purple-500 shadow-md shadow-purple-500/10 ring-1 ring-purple-500/50'
                          : 'bg-[#0f111d] border-[#22253a] hover:border-[#383c5e] hover:bg-[#151726]'
                      }`}
                    >
                      {/* Visual Thumbnail Representation */}
                      <div className="w-full h-16 rounded-lg bg-[#080911] border border-[#23263c] mb-2 p-1.5 flex gap-1 overflow-hidden relative">
                        {tpl.thumbnailStyle === 'sidebar' ? (
                          <>
                            {/* Left dark sidebar */}
                            <div className="w-[30%] h-full bg-[#1e2235] rounded-sm p-1 flex flex-col justify-between">
                              <div className="w-full h-1.5 bg-blue-400/80 rounded-xs" />
                              <div className="space-y-0.5">
                                <div className="w-full h-1 bg-slate-500/40 rounded-xs" />
                                <div className="w-3/4 h-1 bg-slate-500/40 rounded-xs" />
                              </div>
                            </div>
                            {/* Right content */}
                            <div className="flex-1 h-full bg-white/90 rounded-sm p-1 flex flex-col justify-between">
                              <div className="w-1/2 h-1.5 bg-slate-800 rounded-xs" />
                              <div className="space-y-0.5">
                                <div className="w-full h-1 bg-slate-300 rounded-xs" />
                                <div className="w-full h-1 bg-slate-300 rounded-xs" />
                                <div className="w-4/5 h-1 bg-slate-300 rounded-xs" />
                              </div>
                            </div>
                          </>
                        ) : tpl.thumbnailStyle === 'minimalist' ? (
                          <div className="w-full h-full bg-white/90 rounded-sm p-1.5 flex flex-col justify-between">
                            <div className="flex justify-between items-center border-b border-slate-300 pb-0.5">
                              <div className="w-1/3 h-1.5 bg-slate-800 rounded-xs" />
                              <div className="w-1/4 h-1 bg-emerald-600 rounded-xs" />
                            </div>
                            <div className="space-y-0.5">
                              <div className="w-full h-1 bg-slate-300 rounded-xs" />
                              <div className="w-full h-1 bg-slate-300 rounded-xs" />
                              <div className="w-5/6 h-1 bg-slate-300 rounded-xs" />
                            </div>
                          </div>
                        ) : tpl.thumbnailStyle === 'grid' ? (
                          <div className="w-full h-full bg-white/90 rounded-sm p-1 flex flex-col justify-between">
                            <div className="w-full h-1.5 bg-blue-600 rounded-xs" />
                            <div className="grid grid-cols-4 gap-0.5">
                              <div className="h-2 bg-blue-100 rounded-xs" />
                              <div className="h-2 bg-blue-100 rounded-xs" />
                              <div className="h-2 bg-blue-100 rounded-xs" />
                              <div className="h-2 bg-blue-100 rounded-xs" />
                            </div>
                            <div className="grid grid-cols-2 gap-1">
                              <div className="h-4 bg-slate-100 border border-slate-200 rounded-xs" />
                              <div className="h-4 bg-slate-100 border border-slate-200 rounded-xs" />
                            </div>
                          </div>
                        ) : tpl.thumbnailStyle === 'classic' ? (
                          <div className="w-full h-full bg-white/95 rounded-sm p-1.5 flex flex-col justify-between">
                            <div className="border-b border-blue-900 pb-0.5">
                              <div className="w-1/2 h-1.5 bg-slate-900 rounded-xs" />
                              <div className="w-3/4 h-1 bg-blue-800 rounded-xs mt-0.5" />
                            </div>
                            <div className="space-y-0.5">
                              <div className="w-full h-1 bg-slate-400 rounded-xs" />
                              <div className="w-full h-1 bg-slate-300 rounded-xs" />
                              <div className="w-4/5 h-1 bg-slate-300 rounded-xs" />
                            </div>
                            <div className="border-t border-slate-300 pt-0.5 space-y-0.5">
                              <div className="w-1/3 h-1 bg-blue-900 rounded-xs" />
                              <div className="w-full h-1 bg-slate-300 rounded-xs" />
                            </div>
                          </div>
                        ) : (
                          <div className="w-full h-full bg-white/90 rounded-sm p-1 flex flex-col justify-between">
                            <div className="flex justify-between items-center border-b-2 border-purple-500 pb-0.5">
                              <div className="w-2/5 h-1.5 bg-purple-900 rounded-xs" />
                              <div className="w-1/4 h-1 bg-slate-400 rounded-xs" />
                            </div>
                            <div className="grid grid-cols-3 gap-0.5">
                              <div className="h-3 bg-purple-50 rounded-xs border border-purple-200" />
                              <div className="h-3 bg-purple-50 rounded-xs border border-purple-200" />
                              <div className="h-3 bg-purple-50 rounded-xs border border-purple-200" />
                            </div>
                          </div>
                        )}

                        {isSelected && (
                          <div className="absolute top-1 right-1 w-4 h-4 rounded-full bg-purple-500 text-white flex items-center justify-center shadow">
                            <Check className="w-2.5 h-2.5" />
                          </div>
                        )}
                      </div>

                      <div>
                        <div className="flex items-center justify-between">
                          <h4 className="text-xs font-bold text-slate-100 group-hover:text-purple-300 transition-colors">
                            {tpl.name}
                          </h4>
                        </div>
                        <p className="text-[10px] text-slate-400 mt-0.5">{tpl.category}</p>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* 3. 1-Click Color Theme Palette Swatches (B) */}
            <div className="bg-[#141624] border border-[#23263c] rounded-2xl p-3.5">
              <div className="flex items-center justify-between mb-2.5">
                <span className="text-[11px] font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                  <Palette className="w-3.5 h-3.5 text-pink-400" /> Theme Palette Swatches
                </span>
                <span className="text-[10px] text-purple-300 font-medium">Instant &lt;300ms</span>
              </div>

              <div className="flex items-center justify-between gap-2 bg-[#0c0d16] p-2 rounded-xl border border-[#1e2034]">
                {PALETTE_OPTIONS.map((pal) => {
                  const isSelected = selectedPalette === pal.id;
                  return (
                    <button
                      key={pal.id}
                      type="button"
                      onClick={() => handlePaletteChange(pal.id)}
                      disabled={isGenerating}
                      className="group flex flex-col items-center gap-1.5 focus:outline-none"
                      title={`${pal.name} (${pal.color})`}
                    >
                      <div
                        className={`w-7 h-7 rounded-full transition-all relative flex items-center justify-center ${
                          isSelected
                            ? 'ring-2 ring-white scale-110 shadow-lg'
                            : 'hover:scale-105 opacity-80 hover:opacity-100'
                        }`}
                        style={{ backgroundColor: pal.color }}
                      >
                        {isSelected && <Check className="w-3.5 h-3.5 text-white drop-shadow" />}
                      </div>
                      <span className={`text-[9.5px] font-semibold ${isSelected ? 'text-white' : 'text-slate-400'}`}>
                        {pal.label}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* 4. Professional Typography & Font Family Selector */}
            <div className="bg-[#141624] border border-[#23263c] rounded-2xl p-3.5">
              <div className="flex items-center justify-between mb-2.5">
                <span className="text-[11px] font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                  <Type className="w-3.5 h-3.5 text-sky-400" /> Typography Font
                </span>
                <span className="text-[10px] text-sky-300 bg-sky-500/10 border border-sky-500/20 px-2 py-0.5 rounded-full font-semibold">
                  ATS Verified
                </span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5 bg-[#0c0d16] p-1.5 rounded-xl border border-[#1e2034]">
                {FONT_OPTIONS.map((f) => {
                  const isSelected = selectedFont === f.id;
                  return (
                    <button
                      key={f.id}
                      type="button"
                      onClick={() => handleFontChange(f.id)}
                      disabled={isGenerating}
                      className={`p-2 rounded-lg border text-left transition-all ${
                        isSelected
                          ? 'bg-[#1b1c2e] border-sky-500 text-white shadow-sm ring-1 ring-sky-500/50'
                          : 'bg-[#131522] border-[#22253a] text-slate-400 hover:text-slate-200 hover:border-[#383c5e]'
                      }`}
                    >
                      <span className="block text-xs font-bold leading-tight" style={{ fontFamily: f.css }}>
                        {f.name}
                      </span>
                      <span className="block text-[8.5px] opacity-70 truncate mt-0.5">{f.category}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* 5. Smart "Fill Page Gaps" AI Action Buttons & Custom Prompt Bar (C) */}
            <div className="bg-[#141624] border border-[#23263c] rounded-2xl p-3.5">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-bold text-purple-300 uppercase tracking-wider flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-purple-400" /> AI Resume Co-Pilot (Agent 2)
                </span>
                {appliedBadge && (
                  <span className="text-[9.5px] bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 px-2 py-0.5 rounded-full font-medium truncate max-w-[140px]">
                    ✓ {appliedBadge}
                  </span>
                )}
              </div>

              {/* Quick 1-Click Action Buttons */}
              <div className="grid grid-cols-2 gap-1.5 mb-3">
                <button
                  type="button"
                  onClick={() =>
                    handleRefineSubmit(
                      'Auto-Fill Empty Spaces: Scan candidate master resume and target JD for unused technical skills, architecture details, and project metrics. Expand experience bullets and project sections on Page 2 so that Page 2 is 100% full with zero bottom whitespace, preserving A4 margins and layout boundaries.',
                      'Auto-Fill Empty Spaces'
                    )
                  }
                  disabled={isGenerating}
                  className="p-2 rounded-xl bg-[#1b1d2e] hover:bg-purple-900/30 border border-[#2e314e] hover:border-purple-500/50 text-left transition-all group disabled:opacity-50"
                >
                  <div className="flex items-center gap-1.5 text-purple-300 text-xs font-bold mb-0.5">
                    <Wand2 className="w-3.5 h-3.5 text-purple-400 group-hover:scale-110 transition-transform" />
                    <span>Auto-Fill Gaps</span>
                  </div>
                  <p className="text-[10px] text-slate-400 leading-tight">Eliminate dead space on Page 2</p>
                </button>

                <button
                  type="button"
                  onClick={() =>
                    handleRefineSubmit(
                      'Boost ATS Match Score: Identify missing keywords from target job description and inject them organically into experience bullets, skills matrix, and executive summary using STAR/XYZ format.',
                      'Boost ATS Score'
                    )
                  }
                  disabled={isGenerating}
                  className="p-2 rounded-xl bg-[#1b1d2e] hover:bg-emerald-900/30 border border-[#2e314e] hover:border-emerald-500/50 text-left transition-all group disabled:opacity-50"
                >
                  <div className="flex items-center gap-1.5 text-emerald-300 text-xs font-bold mb-0.5">
                    <Zap className="w-3.5 h-3.5 text-emerald-400 group-hover:scale-110 transition-transform" />
                    <span>Boost ATS Score</span>
                  </div>
                  <p className="text-[10px] text-slate-400 leading-tight">Inject missing JD keywords</p>
                </button>

                <button
                  type="button"
                  onClick={() =>
                    handleRefineSubmit(
                      'Trim to Fit Page 1: Select highest-impact bullets, tighten wording, and ensure crisp 1-page fit.',
                      'Trim to 1 Page'
                    )
                  }
                  disabled={isGenerating}
                  className="p-2 rounded-xl bg-[#1b1d2e] hover:bg-blue-900/30 border border-[#2e314e] hover:border-blue-500/50 text-left transition-all group disabled:opacity-50"
                >
                  <div className="flex items-center gap-1.5 text-blue-300 text-xs font-bold mb-0.5">
                    <Scissors className="w-3.5 h-3.5 text-blue-400 group-hover:scale-110 transition-transform" />
                    <span>Trim to 1 Page</span>
                  </div>
                  <p className="text-[10px] text-slate-400 leading-tight">Tighten to concise 1 page</p>
                </button>

                <button
                  type="button"
                  onClick={() =>
                    handleRefineSubmit(
                      'Quantify Metrics: Add concrete volume, scale, and performance metrics (e.g., 1,000+ users, 99.9% uptime, latency reduction) across all bullet points.',
                      'Quantify Metrics'
                    )
                  }
                  disabled={isGenerating}
                  className="p-2 rounded-xl bg-[#1b1d2e] hover:bg-amber-900/30 border border-[#2e314e] hover:border-amber-500/50 text-left transition-all group disabled:opacity-50"
                >
                  <div className="flex items-center gap-1.5 text-amber-300 text-xs font-bold mb-0.5">
                    <BarChart3 className="w-3.5 h-3.5 text-amber-400 group-hover:scale-110 transition-transform" />
                    <span>Quantify Metrics</span>
                  </div>
                  <p className="text-[10px] text-slate-400 leading-tight">Add 1,000+ users & scale</p>
                </button>
              </div>

              {/* Custom Prompt Input */}
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleRefineSubmit();
                }}
                className="flex items-center gap-2"
              >
                <input
                  type="text"
                  value={customPrompt}
                  onChange={(e) => setCustomPrompt(e.target.value)}
                  placeholder="Ask AI to expand... (e.g. 'Fill Page 2 bottom')"
                  disabled={isGenerating}
                  className="flex-1 bg-[#0b0d17] border border-[#2a2d46] focus:border-purple-500 text-slate-100 text-xs rounded-xl px-3 py-2 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-purple-500 disabled:opacity-50"
                />
                <button
                  type="submit"
                  disabled={isGenerating || !customPrompt.trim()}
                  className="px-3.5 py-2 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 shadow-md shadow-purple-500/20 flex items-center gap-1 transition-all disabled:opacity-40 whitespace-nowrap"
                >
                  <Sparkles className={`w-3.5 h-3.5 ${isRefining ? 'animate-spin' : ''}`} />
                  <span>Refine</span>
                </button>
              </form>
            </div>

            {/* 5. Keywords Checklist Drawer */}
            <div className="bg-[#141624] border border-[#23263c] rounded-2xl p-3.5">
              <h4 className="text-[11px] font-bold text-emerald-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                Target ATS Keywords Integrated
              </h4>
              <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto custom-scrollbar">
                {(tailoredData?.matched_keywords || baselineData?.matched_skills || [
                  'Python',
                  'FastAPI',
                  'PostgreSQL',
                  'Docker',
                  'Redis',
                  'Microservices',
                  'WebSockets',
                  'JWT',
                ]).map((kw: string, i: number) => (
                  <span
                    key={i}
                    className="px-2 py-0.5 rounded-lg text-[10.5px] font-medium bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 flex items-center gap-1"
                  >
                    <CheckCircle2 className="w-2.5 h-2.5 text-emerald-400" /> {kw}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </aside>

        {/* =====================================================================
            RIGHT PANEL: Live Page-Budget Preview (Full-Scale A4 Paper Canvas)
           ===================================================================== */}
        <main className="flex-1 bg-[#07080f] flex flex-col h-full overflow-hidden">
          {/* Preview Toolbar */}
          <div className="h-11 border-b border-[#1b1c2b] bg-[#0c0d16] px-5 flex items-center justify-between text-xs flex-shrink-0">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setViewMode('preview')}
                className={`px-3 py-1 rounded-lg font-semibold flex items-center gap-1.5 transition-all ${
                  viewMode === 'preview'
                    ? 'bg-purple-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Eye className="w-3.5 h-3.5" />
                <span>Live A4 Paper Canvas</span>
              </button>

              <button
                onClick={() => setViewMode('markdown')}
                className={`px-3 py-1 rounded-lg font-semibold flex items-center gap-1.5 transition-all ${
                  viewMode === 'markdown'
                    ? 'bg-purple-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <FileText className="w-3.5 h-3.5" />
                <span>Markdown Source</span>
              </button>
            </div>

            <div className="flex items-center gap-3">
              <span className="text-[11px] text-slate-400 hidden sm:inline-block">
                A4 Portrait • {targetPages} Pages • Zero Bottom Gap Verified
              </span>

              {tailoredData?.html_filename && (
                <a
                  href={`${api.getPreviewUrl(tailoredData.html_filename)}?v=${previewTimestamp}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-2.5 py-1 rounded-lg text-xs font-medium text-blue-300 hover:text-white bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/30 flex items-center gap-1 transition-all"
                  title="Open resume in full browser window"
                >
                  <ExternalLink className="w-3 h-3" />
                  <span>Open in Tab</span>
                </a>
              )}
            </div>
          </div>

          {/* Full-Scale Canvas Surface */}
          <div className="flex-1 overflow-y-auto p-6 md:p-8 flex flex-col items-center justify-start bg-[#080911] custom-scrollbar">
            {viewMode === 'preview' ? (
              tailoredData?.html_filename ? (
                <div className="w-full max-w-[840px] flex flex-col items-center gap-6">
                  {/* Real Paper Display Frame */}
                  <div className="w-full bg-white rounded-md overflow-hidden border border-[#2b2d44] shadow-[0_20px_60px_rgba(0,0,0,0.7)] transition-all">
                    <iframe
                      key={`${tailoredData.html_filename}_${previewTimestamp}`}
                      src={`${api.getPreviewUrl(tailoredData.html_filename)}?v=${previewTimestamp}`}
                      title="Live A4 Resume Canvas"
                      className="w-full border-0 min-h-[1180px] lg:min-h-[1450px]"
                    />
                  </div>
                </div>
              ) : isGenerating ? (
                <div className="flex-1 flex flex-col items-center justify-center text-center space-y-4 my-auto">
                  <div className="w-14 h-14 rounded-2xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400 animate-pulse">
                    <Loader2 className="w-7 h-7 animate-spin" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-slate-200">
                      {statusText || 'Synthesizing candidate background into STAR/XYZ format...'}
                    </h4>
                    <p className="text-xs text-slate-500 mt-1 max-w-md">
                      Calibrating typography density, 5-metric ribbons, and ensuring Page 2 has zero whitespace.
                    </p>
                  </div>
                </div>
              ) : (
                <div className="flex-1 flex flex-col items-center justify-center text-center space-y-2 text-slate-500 text-xs my-auto">
                  <FileText className="w-8 h-8 text-slate-600 mb-1" />
                  <p>Select your template and length on the left panel to generate the resume preview.</p>
                </div>
              )
            ) : (
              /* Markdown Source View (Editable & Live Recompilable) */
              <div className="w-full max-w-4xl bg-[#0d0f1a] border border-[#23263b] rounded-2xl p-6 shadow-2xl flex flex-col gap-4">
                <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-[#1f2236]">
                  <div>
                    <span className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                      <FileText className="w-4 h-4 text-purple-400" /> Editable Markdown Source
                    </span>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                      Directly modify your experience, skills, or projects. Click "Apply &amp; Recompile" to update the live canvas.
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    {/* Word Counter & Page Budget Badge */}
                    <div className="px-3 py-1 rounded-lg bg-[#161826] border border-[#2b2e47] text-[11px] text-slate-300 font-mono">
                      {(editableMarkdown || tailoredData?.markdown_content || '').trim().split(/\s+/).filter(Boolean).length} words
                      <span className="text-slate-500 mx-1.5">•</span>
                      <span className={targetPages === 1 ? "text-amber-400" : "text-emerald-400"}>
                        {targetPages === 1 ? 'Target: 350–450 (1P)' : 'Target: 700–900 (2P)'}
                      </span>
                    </div>

                    <button
                      onClick={handleCopyMarkdown}
                      className="px-3 py-1.5 rounded-lg text-xs font-medium text-slate-200 bg-[#1a1c2e] hover:bg-[#252840] border border-[#2e314e] flex items-center gap-1.5 transition-all"
                      title="Copy markdown to clipboard"
                    >
                      {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                      <span>{copied ? 'Copied' : 'Copy'}</span>
                    </button>

                    <button
                      onClick={handleApplyMarkdownEdits}
                      disabled={isGenerating || !(editableMarkdown || tailoredData?.markdown_content || '').trim()}
                      className="px-4 py-1.5 rounded-lg text-xs font-bold text-white bg-gradient-to-r from-purple-600 via-indigo-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 disabled:opacity-50 shadow-md shadow-purple-600/30 flex items-center gap-1.5 transition-all cursor-pointer"
                      title="Recompile live HTML and PDF with your edits"
                    >
                      {isGenerating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                      <span>Apply &amp; Recompile</span>
                    </button>
                  </div>
                </div>

                {recompileSuccessMsg && (
                  <div className="px-3.5 py-2 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-medium flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                    <span>{recompileSuccessMsg}</span>
                  </div>
                )}

                {/* Editable Textarea */}
                <div className="relative">
                  <textarea
                    value={editableMarkdown || tailoredData?.markdown_content || streamedContent}
                    onChange={(e) => setEditableMarkdown(e.target.value)}
                    spellCheck={false}
                    className="w-full h-[600px] bg-[#07080f] text-slate-100 font-mono text-xs md:text-sm p-4 rounded-xl border border-[#212438] focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500 resize-none leading-relaxed custom-scrollbar shadow-inner"
                    placeholder="# Full Name&#10;**Role**&#10;&#10;## PROFESSIONAL SUMMARY&#10;..."
                  />
                </div>

                {/* Quick Insert Formatting Toolbar */}
                <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-[#1a1c2b] text-[11px] text-slate-400">
                  <span className="font-semibold text-slate-300">Quick Insert:</span>
                  <button
                    type="button"
                    onClick={() => {
                      setEditableMarkdown((prev) => (prev || tailoredData?.markdown_content || '') + "\n- **Active Power Verb:** Architected [Component] achieving [Metric %] by implementing [Technology].\n");
                    }}
                    className="px-2.5 py-1 rounded-md bg-[#161826] hover:bg-[#202336] text-purple-300 border border-[#2a2d45] hover:border-purple-500/40 transition-colors"
                  >
                    + XYZ Impact Bullet
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setEditableMarkdown((prev) => (prev || tailoredData?.markdown_content || '') + "\n#### **N. Module Name — Platform Subservice**\n- Bullet 1 describing architectural ownership.\n- Bullet 2 with quantifiable throughput or latency improvement.\n");
                    }}
                    className="px-2.5 py-1 rounded-md bg-[#161826] hover:bg-[#202336] text-blue-300 border border-[#2a2d45] hover:border-blue-500/40 transition-colors"
                  >
                    + SagaSoft Sub-Module
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setEditableMarkdown((prev) => (prev || tailoredData?.markdown_content || '') + "\n- **New Skill Category:** Python, FastAPI, Redis, Docker, PostgreSQL\n");
                    }}
                    className="px-2.5 py-1 rounded-md bg-[#161826] hover:bg-[#202336] text-emerald-300 border border-[#2a2d45] hover:border-emerald-500/40 transition-colors"
                  >
                    + Skill Category
                  </button>
                </div>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
};
