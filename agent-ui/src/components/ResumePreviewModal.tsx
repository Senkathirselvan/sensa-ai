import React, { useState } from 'react';
import {
  X,
  Download,
  ExternalLink,
  Sparkles,
  FileText,
  Eye,
  CheckCircle2,
  Maximize2
} from 'lucide-react';

interface ResumePreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  previewUrl: string | null;
  onOpenInStudio?: (previewUrl: string) => void;
}

export const ResumePreviewModal: React.FC<ResumePreviewModalProps> = ({
  isOpen,
  onClose,
  previewUrl,
  onOpenInStudio,
}) => {
  const [isLoading, setIsLoading] = useState(true);

  if (!isOpen || !previewUrl) return null;

  // Extract base filename to construct PDF and DOCX download links
  const cleanUrl = previewUrl.split('?')[0];
  const filename = cleanUrl.split('/').pop() || '';
  const pdfFilename = filename.replace(/\.html?$/i, '.pdf');
  const docxFilename = filename.replace(/\.html?$/i, '.docx');

  const pdfDownloadUrl = `http://localhost:8001/api/resume/download/${pdfFilename}`;
  const docxDownloadUrl = `http://localhost:8001/api/resume/download/${docxFilename}`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 md:p-6 bg-black/80 backdrop-blur-md animate-fade-in">
      <div className="relative w-full max-w-6xl h-[92vh] flex flex-col bg-[#0d0e14] border border-[#232738] rounded-2xl shadow-2xl overflow-hidden">
        {/* Header Toolbar */}
        <header className="h-16 px-6 border-b border-[#1b1c2b] bg-[#11121c] flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-purple-600 to-blue-500 flex items-center justify-center text-white shadow-md shadow-purple-500/20">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm md:text-base font-bold text-white tracking-tight">
                  Sensa AI ATS Resume Studio
                </h2>
                <span className="text-[10px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
                  Live Preview
                </span>
              </div>
              <p className="text-xs text-slate-400 truncate max-w-md">
                {filename || 'Interactive A4 Document'}
              </p>
            </div>
          </div>

          {/* Action Toolbar */}
          <div className="flex items-center gap-2 md:gap-3">
            {onOpenInStudio && (
              <button
                type="button"
                onClick={() => {
                  onClose();
                  onOpenInStudio(previewUrl);
                }}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold text-white bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 shadow-md shadow-purple-600/30 transition-all cursor-pointer"
                title="Open full interactive ATS Studio with layout templates, typography, and live markdown editing"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Customize in ATS Studio</span>
              </button>
            )}

            <a
              href={previewUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-300 hover:text-white bg-[#1a1b29] hover:bg-[#23253a] border border-[#2e3048] transition-colors"
              title="Open full preview in a separate browser tab"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span>Open in Tab</span>
            </a>

            <a
              href={docxDownloadUrl}
              download
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-300 hover:text-white bg-[#1a1b29] hover:bg-[#23253a] border border-[#2e3048] transition-colors"
            >
              <FileText className="w-3.5 h-3.5 text-blue-400" />
              <span className="hidden md:inline">Download</span> DOCX
            </a>

            <a
              href={pdfDownloadUrl}
              download
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold text-white bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 shadow-md shadow-blue-600/25 transition-all"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Download PDF</span>
            </a>

            <button
              onClick={onClose}
              className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-[#1f2133] transition-colors ml-1"
              aria-label="Close Preview"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </header>

        {/* Studio Canvas Area */}
        <main className="flex-1 overflow-y-auto p-4 md:p-8 bg-[#090a10] flex flex-col items-center custom-scrollbar">
          <div className="w-full max-w-4xl relative flex flex-col items-center">
            {isLoading && (
              <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-[#090a10]/80 backdrop-blur-sm min-h-[400px]">
                <div className="w-10 h-10 border-3 border-blue-500/20 border-t-blue-500 rounded-full animate-spin mb-3" />
                <span className="text-xs font-medium text-slate-400">Rendering high-fidelity A4 document...</span>
              </div>
            )}

            <div className="w-full bg-white rounded-lg shadow-2xl overflow-hidden border border-[#2b2d42]">
              <iframe
                src={previewUrl}
                title="Resume ATS Studio Live Canvas"
                onLoad={() => setIsLoading(false)}
                className="w-full border-0 min-h-[920px] md:min-h-[1250px]"
              />
            </div>
          </div>
        </main>

        {/* Footer Note */}
        <footer className="h-10 px-6 border-t border-[#1b1c2b] bg-[#0c0d16] flex items-center justify-between text-[11px] text-slate-400 flex-shrink-0">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            <span>Interactive ATS Studio Preview active. Review your structure here &mdash; download only if you need the physical file.</span>
          </div>
          <span className="hidden sm:inline text-slate-400">Press ESC or click ✕ to close</span>
        </footer>
      </div>
    </div>
  );
};

