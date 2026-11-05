import React, { useState, useEffect } from 'react';
import {
  Briefcase,
  X,
  ExternalLink,
  Trash2,
  AlertTriangle,
  RotateCcw,
  CheckCircle2,
  BookmarkCheck,
  Send,
  CalendarCheck,
  Loader2,
  Building2,
  MapPin,
  Sparkles
} from 'lucide-react';
import { JobCard, JobCounts } from '../types';
import { api } from '../services/api';

interface TrackerModalProps {
  isOpen: boolean;
  initialTab?: 'ALL' | 'SAVED' | 'APPLIED' | 'INTERVIEW';
  jobCounts: JobCounts;
  onClose: () => void;
  onCountsUpdated: () => void;
}

export const TrackerModal: React.FC<TrackerModalProps> = ({
  isOpen,
  initialTab = 'ALL',
  jobCounts,
  onClose,
  onCountsUpdated,
}) => {
  const [activeTab, setActiveTab] = useState<'ALL' | 'SAVED' | 'APPLIED' | 'INTERVIEW'>(initialTab);
  const [jobs, setJobs] = useState<JobCard[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [confirmClearStatus, setConfirmClearStatus] = useState<string | null>(null);
  const [feedbackMsg, setFeedbackMsg] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setActiveTab(initialTab);
      loadJobs(initialTab);
    }
  }, [isOpen, initialTab]);

  const loadJobs = async (tab: 'ALL' | 'SAVED' | 'APPLIED' | 'INTERVIEW') => {
    setIsLoading(true);
    setFeedbackMsg(null);
    try {
      const statusParam = tab === 'ALL' ? undefined : tab;
      const data = await api.getTrackedJobs(statusParam);
      setJobs(data);
    } catch (e: any) {
      console.error('Failed to load tracked jobs:', e);
      setJobs([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleTabChange = (tab: 'ALL' | 'SAVED' | 'APPLIED' | 'INTERVIEW') => {
    setActiveTab(tab);
    loadJobs(tab);
  };

  const handleDeleteSingle = async (jobId?: string) => {
    if (!jobId) return;
    setIsDeleting(true);
    try {
      await api.deleteTrackedJob(jobId);
      setJobs((prev) => prev.filter((j) => j.id !== jobId));
      onCountsUpdated();
      setFeedbackMsg('Job removed from tracker.');
      setTimeout(() => setFeedbackMsg(null), 3000);
    } catch (e: any) {
      console.error('Failed to delete tracked job:', e);
      setFeedbackMsg('Failed to delete job.');
    } finally {
      setIsDeleting(false);
    }
  };

  const handleExecuteClear = async (status: string) => {
    setIsDeleting(true);
    try {
      const res = await api.clearTrackedJobs(status);
      setConfirmClearStatus(null);
      await loadJobs(activeTab);
      onCountsUpdated();
      setFeedbackMsg(res.message || 'Records cleared successfully.');
      setTimeout(() => setFeedbackMsg(null), 3500);
    } catch (e: any) {
      console.error('Failed to clear tracked jobs:', e);
      setFeedbackMsg('Error clearing records.');
    } finally {
      setIsDeleting(false);
    }
  };

  if (!isOpen) return null;

  const totalAll = (jobCounts.SAVED || 0) + (jobCounts.APPLIED || 0) + (jobCounts.INTERVIEW || 0);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-fade-in">
      <div className="relative w-full max-w-3xl bg-[#0f1017] border border-[#232537] rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[88vh]">
        
        {/* Header */}
        <div className="p-4 sm:p-5 border-b border-[#1f2130] flex items-center justify-between bg-[#151622]/60">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400">
              <Briefcase className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base sm:text-lg font-bold text-slate-100 flex items-center gap-2">
                Job Applications Tracker
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
                  {totalAll} Total
                </span>
              </h2>
              <p className="text-xs text-slate-400">
                Review verified applications, saved targets, or reset counts to start fresh.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-[#1f2130] transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Feedback Alert Bar */}
        {feedbackMsg && (
          <div className="px-5 py-2.5 bg-blue-500/10 border-b border-blue-500/20 text-xs text-blue-300 flex items-center justify-between animate-fade-in">
            <span className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              {feedbackMsg}
            </span>
            <button onClick={() => setFeedbackMsg(null)} className="text-slate-400 hover:text-white">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Filter Tabs & Batch Clear Bar */}
        <div className="px-5 py-3 border-b border-[#1c1d2b] flex flex-wrap items-center justify-between gap-3 bg-[#11121c]">
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => handleTabChange('ALL')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeTab === 'ALL'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-[#1a1b2a]'
              }`}
            >
              All ({totalAll})
            </button>
            <button
              onClick={() => handleTabChange('APPLIED')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
                activeTab === 'APPLIED'
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-[#1a1b2a]'
              }`}
            >
              <Send className="w-3 h-3 text-emerald-400" />
              Applied ({jobCounts.APPLIED || 0})
            </button>
            <button
              onClick={() => handleTabChange('SAVED')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
                activeTab === 'SAVED'
                  ? 'bg-blue-600/80 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-[#1a1b2a]'
              }`}
            >
              <BookmarkCheck className="w-3 h-3 text-blue-400" />
              Saved ({jobCounts.SAVED || 0})
            </button>
            <button
              onClick={() => handleTabChange('INTERVIEW')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
                activeTab === 'INTERVIEW'
                  ? 'bg-purple-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-[#1a1b2a]'
              }`}
            >
              <CalendarCheck className="w-3 h-3 text-purple-400" />
              Interview ({jobCounts.INTERVIEW || 0})
            </button>
          </div>

          {/* Quick Clear Buttons */}
          <div className="flex items-center gap-2">
            {activeTab !== 'ALL' && (
              <button
                onClick={() => setConfirmClearStatus(activeTab)}
                disabled={isDeleting || (activeTab === 'APPLIED' ? jobCounts.APPLIED === 0 : activeTab === 'SAVED' ? jobCounts.SAVED === 0 : jobCounts.INTERVIEW === 0)}
                className="px-2.5 py-1.5 rounded-lg text-xs font-medium text-rose-400 hover:text-rose-300 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 transition-all flex items-center gap-1.5 disabled:opacity-40 disabled:cursor-not-allowed"
                title={`Clear all ${activeTab.toLowerCase()} jobs`}
              >
                <Trash2 className="w-3.5 h-3.5" />
                Clear {activeTab === 'APPLIED' ? 'Applied' : activeTab === 'SAVED' ? 'Saved' : 'Interviews'}
              </button>
            )}

            <button
              onClick={() => setConfirmClearStatus('ALL')}
              disabled={isDeleting || totalAll === 0}
              className="px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-300 hover:text-white bg-[#1d1f30] hover:bg-rose-600/80 border border-[#2b2d42] hover:border-rose-500/50 transition-all flex items-center gap-1.5 disabled:opacity-40 disabled:cursor-not-allowed"
              title="Reset all counts to 0"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Reset All
            </button>
          </div>
        </div>

        {/* Modal Confirmation Alert Box */}
        {confirmClearStatus && (
          <div className="p-4 bg-rose-950/40 border-b border-rose-500/30 flex items-center justify-between gap-4 animate-fade-in">
            <div className="flex items-center gap-2.5 text-xs text-rose-200">
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>
                {confirmClearStatus === 'ALL'
                  ? `Are you sure you want to delete ALL ${totalAll} tracked jobs? This will reset all counters to 0.`
                  : `Are you sure you want to delete all ${confirmClearStatus} jobs (${confirmClearStatus === 'APPLIED' ? jobCounts.APPLIED : confirmClearStatus === 'SAVED' ? jobCounts.SAVED : jobCounts.INTERVIEW})?`}
              </span>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={() => setConfirmClearStatus(null)}
                className="px-3 py-1 rounded-md text-xs font-medium text-slate-300 bg-slate-800 hover:bg-slate-700 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handleExecuteClear(confirmClearStatus)}
                disabled={isDeleting}
                className="px-3 py-1 rounded-md text-xs font-semibold text-white bg-rose-600 hover:bg-rose-500 transition-colors flex items-center gap-1.5 shadow-sm"
              >
                {isDeleting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                Confirm Delete
              </button>
            </div>
          </div>
        )}

        {/* Jobs List Body */}
        <div className="p-4 sm:p-5 overflow-y-auto space-y-2.5 flex-1 custom-scrollbar">
          {isLoading ? (
            <div className="py-12 flex flex-col items-center justify-center text-slate-400 gap-2.5">
              <Loader2 className="w-6 h-6 animate-spin text-blue-400" />
              <span className="text-xs">Loading tracked applications...</span>
            </div>
          ) : jobs.length === 0 ? (
            <div className="py-12 flex flex-col items-center justify-center text-slate-500 gap-2">
              <Briefcase className="w-8 h-8 text-slate-600 mb-1" />
              <span className="text-sm font-semibold text-slate-300">No {activeTab === 'ALL' ? '' : activeTab.toLowerCase()} jobs found</span>
              <span className="text-xs text-slate-500 max-w-sm text-center">
                Jobs applied or saved by the Sensa AI autonomous agent will appear here with live tracking status.
              </span>
            </div>
          ) : (
            jobs.map((job) => {
              const isApplied = job.status === 'APPLIED';
              const isSaved = job.status === 'SAVED';
              const isInterview = job.status === 'INTERVIEW';

              return (
                <div
                  key={job.id || job.url}
                  className="p-3.5 rounded-xl bg-[#141522] border border-[#212338] hover:border-slate-700/60 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-3 group"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className="text-sm font-semibold text-slate-100 truncate group-hover:text-blue-400 transition-colors">
                        {job.title}
                      </span>

                      {/* Status Badge */}
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded-md border ${
                          isApplied
                            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                            : isSaved
                            ? 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                            : 'bg-purple-500/10 text-purple-400 border-purple-500/20'
                        }`}
                      >
                        {job.status}
                      </span>

                      {/* Match Score Badge */}
                      {job.score ? (
                        <span className="text-[10px] font-semibold text-slate-300 bg-slate-800/80 px-1.5 py-0.5 rounded border border-slate-700/50 flex items-center gap-1">
                          <Sparkles className="w-2.5 h-2.5 text-amber-400" />
                          {job.score}% Match
                        </span>
                      ) : null}
                    </div>

                    <div className="flex items-center gap-3 text-xs text-slate-400 flex-wrap">
                      <span className="flex items-center gap-1 text-slate-300 font-medium">
                        <Building2 className="w-3.5 h-3.5 text-slate-400" />
                        {job.company}
                      </span>
                      {job.location && (
                        <span className="flex items-center gap-1 text-slate-400">
                          <MapPin className="w-3 h-3 text-slate-500" />
                          {job.location}
                        </span>
                      )}
                      {job.applied_at && (
                        <span className="text-[11px] text-slate-400">
                          Applied: {new Date(job.applied_at).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 self-end sm:self-center shrink-0">
                    {job.url && (
                      <a
                        href={job.url}
                        target="_blank"
                        rel="noreferrer"
                        className="p-1.5 rounded-lg text-slate-400 hover:text-slate-100 bg-[#1c1d2e] hover:bg-[#25273d] border border-[#2b2d42] transition-colors"
                        title="Open posting on job portal"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    )}
                    <button
                      onClick={() => handleDeleteSingle(job.id)}
                      disabled={isDeleting}
                      className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 bg-[#1c1d2e] hover:bg-rose-500/10 border border-[#2b2d42] hover:border-rose-500/30 transition-colors"
                      title="Delete from tracker"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Modal Footer */}
        <div className="p-3.5 px-5 border-t border-[#1f2130] bg-[#12131e] flex items-center justify-between text-xs text-slate-400">
          <span>
            {jobs.length} item{jobs.length === 1 ? '' : 's'} displayed
          </span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-xl font-medium text-slate-200 bg-[#1a1b2a] hover:bg-[#232537] border border-[#2c2e44] transition-colors"
          >
            Close
          </button>
        </div>

      </div>
    </div>
  );
};

