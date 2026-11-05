import React, { useState, useEffect, useRef } from 'react';
import {
  AlertTriangle,
  ExternalLink,
  Check,
  X,
  Building2,
  MapPin,
  Bot,
  Loader2,
  FileText,
  ShieldCheck,
  Eye,
  ArrowRight,
  Sparkles,
  CheckCircle2
} from 'lucide-react';
import { JobCard, PlatformAuthStatus } from '../types';
import { api } from '../services/api';
import { PlatformLoginModal, SupportedPlatform } from './PlatformLoginModal';

interface ApplyConfirmModalProps {
  job: JobCard | null;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const ApplyConfirmModal: React.FC<ApplyConfirmModalProps> = ({
  job,
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [isRunning, setIsRunning] = useState(false);
  const [statusText, setStatusText] = useState<string>('');
  const [telemetry, setTelemetry] = useState<{ stage: string; progress: number }>({ stage: 'IDLE', progress: 0 });
  const [reviewData, setReviewData] = useState<any>(null);
  const [isSubmittingFinal, setIsSubmittingFinal] = useState(false);
  const [doneData, setDoneData] = useState<any>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [platformAuth, setPlatformAuth] = useState<PlatformAuthStatus | null>(null);
  const [isPlatformModalOpen, setIsPlatformModalOpen] = useState(false);

  const abortControllerRef = useRef<AbortController | null>(null);

  const targetPlatform: SupportedPlatform | null = (() => {
    const url = (job?.url || '').toLowerCase();
    if (url.includes('linkedin.com')) return 'linkedin';
    if (url.includes('indeed.com')) return 'indeed';
    if (url.includes('naukri.com')) return 'naukri';
    return null;
  })();

  const platformDisplayName =
    targetPlatform === 'linkedin' ? 'LinkedIn' : targetPlatform === 'indeed' ? 'Indeed' : 'Naukri';

  useEffect(() => {
    if (!isOpen) {
      resetState();
    } else if (job && targetPlatform) {
      api.getPlatformAuthStatus(targetPlatform).then(setPlatformAuth).catch(() => {});
    }
  }, [isOpen, job?.url]);

  const resetState = () => {
    setIsRunning(false);
    setStatusText('');
    setTelemetry({ stage: 'IDLE', progress: 0 });
    setReviewData(null);
    setIsSubmittingFinal(false);
    setDoneData(null);
    setErrorMsg(null);
    setIsPlatformModalOpen(false);
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  if (!isOpen || !job) return null;

  const handleStartApply = () => {
    if (targetPlatform && !platformAuth?.connected) {
      setIsPlatformModalOpen(true);
      return;
    }

    setIsRunning(true);
    setErrorMsg(null);
    setDoneData(null);
    setReviewData(null);
    setStatusText(`Initializing autonomous browser for ${job.company}...`);
    setTelemetry({ stage: 'INIT', progress: 15 });

    abortControllerRef.current = new AbortController();

    api.streamApplyJob(
      {
        job_id: job.id,
        job_title: job.title,
        company: job.company,
        job_url: job.url || 'https://naukri.com',
        headless: true,
      },
      {
        onStatus: (st) => setStatusText(st),
        onTelemetry: (t) => setTelemetry(t),
        onReviewReady: (rev) => {
          setReviewData(rev);
          setStatusText('Human-in-the-Loop Gate: Please review the filled application below.');
        },
        onDone: (data) => {
          setIsRunning(false);
          setDoneData(data);
          if (data.status === 'submitted' && data.is_verified) {
            setStatusText(`✓ Successfully submitted application to ${job.company}!`);
            api.confirmApply(job).catch(() => {});
            setTimeout(() => {
              onSuccess();
            }, 3500);
          } else if (data.status === 'auth_required') {
            setStatusText(`⚠️ Authentication required: Please connect your ${platformDisplayName} account.`);
          } else {
            setStatusText(data.message || `Application status: ${data.status}`);
          }
        },
        onError: (err) => {
          setIsRunning(false);
          setErrorMsg(err.message || 'Application process failed.');
        },
      },
      abortControllerRef.current.signal
    );
  };

  const handleConfirmFinal = async () => {
    if (!reviewData?.session_id) return;
    setIsSubmittingFinal(true);
    setStatusText('Releasing security gate: Submitting application on portal...');
    try {
      await api.confirmApplyStep(reviewData.session_id);
    } catch (e: any) {
      setErrorMsg(`Submission release error: ${e.message}`);
      setIsSubmittingFinal(false);
    }
  };

  const handleAbort = async () => {
    if (reviewData?.session_id) {
      try {
        await api.abortApply(reviewData.session_id);
      } catch {}
    }
    resetState();
    onClose();
  };

  const platformBadge = (() => {
    const url = (job.url || '').toLowerCase();
    if (url.includes('naukri.com')) return { name: 'Naukri 1-Click Apply', color: 'bg-blue-500/10 text-blue-300 border-blue-500/20' };
    if (url.includes('linkedin.com')) return { name: 'LinkedIn Easy Apply', color: 'bg-sky-500/10 text-sky-300 border-sky-500/20' };
    if (url.includes('indeed.com')) return { name: 'Indeed Apply', color: 'bg-indigo-500/10 text-indigo-300 border-indigo-500/20' };
    return { name: 'Company ATS Portal', color: 'bg-purple-500/10 text-purple-300 border-purple-500/20' };
  })();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-fade-in">
      <div className="bg-[#121420] border border-[#26283c] w-full max-w-2xl rounded-2xl shadow-2xl p-6 text-slate-200 flex flex-col max-h-[90vh] overflow-hidden">
        {/* Modal Header */}
        <div className="flex items-center justify-between pb-4 border-b border-[#202236] flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-gradient-to-br from-indigo-500/20 to-purple-600/20 border border-indigo-500/30 text-indigo-400">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-slate-100">Autonomous Job Apply Agent</h3>
                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${platformBadge.color}`}>
                  {platformBadge.name}
                </span>
              </div>
              <p className="text-xs text-slate-400">Agent 3 • Playwright Stealth & Human-in-the-Loop Gateway</p>
            </div>
          </div>
          <button
            onClick={handleAbort}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-[#1a1c2e] transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable Content Body */}
        <div className="flex-1 overflow-y-auto py-4 space-y-4 custom-scrollbar">
          {/* Target Job Info Card */}
          <div className="bg-[#181a29] border border-[#282a40] rounded-xl p-4">
            <div className="flex items-start justify-between">
              <div>
                <h4 className="text-sm font-bold text-slate-100">{job.title}</h4>
                <div className="flex items-center gap-3 text-xs text-slate-400 mt-1">
                  <span className="flex items-center gap-1">
                    <Building2 className="w-3.5 h-3.5 text-slate-500" /> {job.company}
                  </span>
                  {job.location && (
                    <span className="flex items-center gap-1">
                      <MapPin className="w-3.5 h-3.5 text-slate-500" /> {job.location}
                    </span>
                  )}
                </div>
              </div>
              {job.url && (
                <a
                  href={job.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-2 rounded-lg bg-[#202238] border border-[#2d304e] hover:border-blue-500/50 text-blue-400 hover:text-blue-300 transition-colors"
                  title="Open live URL"
                >
                  <ExternalLink className="w-4 h-4" />
                </a>
              )}
            </div>
          </div>

          {/* Target Platform Session Status Banner */}
          {!isRunning && !doneData && targetPlatform && (
            <div
              className={`p-3 rounded-xl border flex items-center justify-between gap-3 text-xs ${
                platformAuth?.connected
                  ? 'bg-emerald-950/20 border-emerald-500/30 text-emerald-300'
                  : 'bg-amber-950/25 border-amber-500/40 text-amber-200'
              }`}
            >
              <div className="flex items-center gap-2.5 min-w-0">
                {platformAuth?.connected ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                ) : (
                  <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                )}
                <div className="min-w-0">
                  <div className="font-semibold text-slate-100">
                    {platformAuth?.connected
                      ? `✓ ${platformDisplayName} Session Authenticated`
                      : `⚠️ ${platformDisplayName} Session Required`}
                  </div>
                  <div className="text-[11px] opacity-80 truncate">
                    {platformAuth?.connected
                      ? `Ready for automated ${platformDisplayName} Easy Apply submission.`
                      : `Connect your account so the agent can apply directly without login walls.`}
                  </div>
                </div>
              </div>

              {!platformAuth?.connected && (
                <button
                  type="button"
                  onClick={() => setIsPlatformModalOpen(true)}
                  className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs shrink-0 transition shadow-sm"
                >
                  Connect {platformDisplayName}
                </button>
              )}
            </div>
          )}

          {/* Real-Time Progress Bar & Telemetry Status */}
          {isRunning && (
            <div className="bg-[#151726] border border-[#24263c] rounded-xl p-3.5 space-y-2.5">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-slate-300 flex items-center gap-2">
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-purple-400" />
                  {statusText || 'Executing application steps...'}
                </span>
                <span className="text-[11px] font-mono text-purple-400 font-bold">{telemetry.progress}%</span>
              </div>
              <div className="w-full bg-[#0c0d16] rounded-full h-1.5 overflow-hidden">
                <div
                  className="bg-gradient-to-r from-blue-500 via-purple-500 to-emerald-500 h-full transition-all duration-300"
                  style={{ width: `${telemetry.progress}%` }}
                />
              </div>
            </div>
          )}

          {/* Review Ready: Human-in-the-Loop Review Screen */}
          {reviewData && !doneData && (
            <div className="bg-[#171a2e] border border-amber-500/30 rounded-2xl p-4 space-y-3.5">
              <div className="flex items-center gap-2 text-amber-300 text-xs font-bold uppercase tracking-wider">
                <ShieldCheck className="w-4 h-4 text-amber-400" />
                Human-in-the-Loop Verification Required
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                The agent has navigated to the portal, mapped your candidate data, and attached your tailored resume.
                Please review before authorizing final submission:
              </p>

              {/* Verified Details */}
              <div className="grid grid-cols-2 gap-2 text-xs bg-[#10121e] p-3 rounded-xl border border-[#222438]">
                <div>
                  <span className="text-slate-500 block text-[10px]">Attached Resume:</span>
                  <span className="font-semibold text-slate-200 flex items-center gap-1 mt-0.5 truncate">
                    <FileText className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                    {reviewData.resume_filename || 'Tailored Resume.pdf'}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">Portal Route:</span>
                  <span className="font-semibold text-slate-200 capitalize mt-0.5 block truncate">
                    {reviewData.platform.replace('_', ' ')}
                  </span>
                </div>
                {reviewData.fields_filled && Object.keys(reviewData.fields_filled).length > 0 && (
                  <div className="col-span-2 pt-1 border-t border-[#1c1e30]">
                    <span className="text-slate-500 block text-[10px] mb-1">Populated Fields:</span>
                    <div className="flex flex-wrap gap-1.5">
                      {Object.entries(reviewData.fields_filled).map(([k, v]: any) => (
                        <span key={k} className="text-[10.5px] px-2 py-0.5 rounded-md bg-[#191b2c] border border-[#282a42] text-slate-300">
                          <strong className="text-slate-400">{k}:</strong> {String(v)}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Live Form Screenshot View */}
              {reviewData.screenshot_filename && (
                <div className="rounded-xl border border-[#2b2e48] overflow-hidden bg-black/40">
                  <div className="flex items-center justify-between px-3 py-1.5 bg-[#121422] text-[11px] text-slate-400 border-b border-[#2b2e48]">
                    <span className="flex items-center gap-1.5">
                      <Eye className="w-3.5 h-3.5 text-purple-400" /> Live Browser Snapshot
                    </span>
                    <span className="text-[10px] text-slate-500">Captured in stealth context</span>
                  </div>
                  <img
                    src={api.getApplyScreenshotUrl(reviewData.screenshot_filename)}
                    alt="Application preview"
                    className="w-full max-h-[180px] object-cover object-top hover:opacity-95 transition-opacity"
                  />
                </div>
              )}
            </div>
          )}

          {/* Success / Status Done State */}
          {doneData && (
            <div className={`p-4 rounded-xl border space-y-2.5 ${
              doneData.status === 'submitted' && doneData.is_verified !== false
                ? 'bg-emerald-950/30 border-emerald-500/30 text-emerald-300'
                : doneData.status === 'auth_required'
                ? 'bg-amber-950/30 border-amber-500/40 text-amber-300'
                : 'bg-indigo-950/30 border-indigo-500/30 text-slate-300'
            }`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm font-bold">
                  {doneData.status === 'submitted' && doneData.is_verified !== false ? (
                    <>
                      <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                      Application Submitted & Receipt Verified!
                    </>
                  ) : doneData.status === 'auth_required' ? (
                    <>
                      <AlertTriangle className="w-5 h-5 text-amber-400" />
                      Sign In Required on {doneData.platform === 'linkedin' ? 'LinkedIn' : doneData.platform === 'naukri' ? 'Naukri' : doneData.platform === 'indeed' ? 'Indeed' : 'Portal'}
                    </>
                  ) : (
                    <>
                      <AlertTriangle className="w-5 h-5 text-indigo-400" />
                      Application Status Update
                    </>
                  )}
                </div>
                {doneData.status === 'auth_required' && (
                  <div className="flex items-center gap-2">
                    {targetPlatform && (
                      <button
                        type="button"
                        onClick={() => setIsPlatformModalOpen(true)}
                        className="px-3 py-1 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-sm"
                      >
                        Connect {platformDisplayName}
                      </button>
                    )}
                    {job.url && (
                      <a
                        href={job.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="px-3 py-1 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-200 border border-amber-500/40 text-xs font-semibold flex items-center gap-1.5 transition-colors"
                      >
                        Open Portal <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    )}
                  </div>
                )}
              </div>

              <p className="text-xs opacity-90 leading-relaxed">
                {doneData.message || (doneData.status === 'auth_required'
                  ? 'The portal requires an active account session. Please log in to complete your application.'
                  : 'Your job application has been processed.')}
              </p>

              {doneData.proof_screenshot && (
                <div className="pt-2">
                  <span className="text-[10px] opacity-75 block mb-1">Live Portal View / Proof Snapshot:</span>
                  <img
                    src={api.getApplyScreenshotUrl(doneData.proof_screenshot)}
                    alt="Submission proof"
                    className="rounded-lg border border-slate-700/50 max-h-[160px] object-cover w-full"
                  />
                </div>
              )}
            </div>
          )}

          {/* Error Message */}
          {errorMsg && (
            <div className="p-3 rounded-xl bg-rose-950/40 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}
        </div>

        {/* Modal Action Buttons Footer */}
        <div className="flex items-center justify-between pt-4 border-t border-[#202236] flex-shrink-0">
          <button
            onClick={handleAbort}
            disabled={isSubmittingFinal}
            className="px-4 py-2 rounded-xl border border-[#30334a] hover:bg-[#1a1c2c] text-xs font-semibold text-slate-300 transition-colors"
          >
            {doneData ? 'Close' : 'Cancel'}
          </button>

          {!isRunning && !reviewData && !doneData && (
            <button
              onClick={handleStartApply}
              className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-xs font-bold text-white transition-all flex items-center gap-2 shadow-lg shadow-blue-600/25"
            >
              <Sparkles className="w-4 h-4 text-amber-300" /> Launch Autonomous Apply Agent
            </button>
          )}

          {reviewData && !doneData && (
            <button
              onClick={handleConfirmFinal}
              disabled={isSubmittingFinal}
              className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-xs font-bold text-white transition-all flex items-center gap-2 shadow-lg shadow-emerald-600/25"
            >
              {isSubmittingFinal ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" /> Submitting...
                </>
              ) : (
                <>
                  <Check className="w-4 h-4" /> Approve & Submit Application
                </>
              )}
            </button>
          )}
        </div>
      </div>

      {/* Platform Login Modal for connecting LinkedIn / Indeed / Naukri */}
      {targetPlatform && (
        <PlatformLoginModal
          isOpen={isPlatformModalOpen}
          platform={targetPlatform}
          onClose={() => setIsPlatformModalOpen(false)}
          onSuccess={() => {
            setIsPlatformModalOpen(false);
            api.getPlatformAuthStatus(targetPlatform).then(setPlatformAuth);
          }}
        />
      )}
    </div>
  );
};
