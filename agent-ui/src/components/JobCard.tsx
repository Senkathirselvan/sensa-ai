import React, { useState } from 'react';
import { ExternalLink, Bookmark, Send, CheckCircle, AlertCircle, Building2, MapPin, Briefcase, IndianRupee, Clock, Sparkles } from 'lucide-react';
import { JobCard as JobCardType } from '../types';
import { api } from '../services/api';

interface JobCardProps {
  job: JobCardType;
  onApplyClick?: (job: JobCardType) => void;
  onSaveSuccess?: () => void;
  onTailorClick?: (job: JobCardType) => void;
}

export const JobCard: React.FC<JobCardProps> = ({ job, onApplyClick, onSaveSuccess, onTailorClick }) => {
  const [saved, setSaved] = useState(job.status === 'SAVED');
  const [saving, setSaving] = useState(false);

  const score = job.score || 0;
  const scoreColor =
    score >= 80
      ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10'
      : score >= 60
      ? 'text-amber-400 border-amber-500/30 bg-amber-500/10'
      : 'text-slate-400 border-slate-500/30 bg-slate-500/10';

  const getPlatform = () => {
    const raw = (job.platform || '').trim();
    if (raw && raw.toLowerCase() !== 'web') {
      if (raw.toLowerCase() === 'linkedin') return 'LinkedIn';
      if (raw.toLowerCase() === 'naukri') return 'Naukri';
      if (raw.toLowerCase() === 'indeed') return 'Indeed';
      return raw;
    }
    const url = (job.url || '').toLowerCase();
    if (url.includes('naukri.com')) return 'Naukri';
    if (url.includes('linkedin.com')) return 'LinkedIn';
    if (url.includes('indeed.com')) return 'Indeed';
    if (url.includes('glassdoor')) return 'Glassdoor';
    return raw || 'Web';
  };
  const platformName = getPlatform();

  const platformBadgeStyle = () => {
    const p = platformName.toLowerCase();
    if (p === 'naukri') {
      return 'bg-amber-500/15 text-amber-300 border-amber-500/30 font-bold';
    }
    if (p === 'linkedin') {
      return 'bg-blue-500/15 text-blue-400 border-blue-500/25';
    }
    if (p === 'indeed') {
      return 'bg-indigo-500/15 text-indigo-300 border-indigo-500/25';
    }
    return 'bg-slate-500/15 text-slate-300 border-slate-500/25';
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      await api.saveJob({ ...job, status: 'SAVED' });
      setSaved(true);
      if (onSaveSuccess) onSaveSuccess();
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-[#1b1b22] hover:bg-[#1f1f28] border border-[#2d2d3a] hover:border-[#3e3e50] transition-all duration-200 rounded-xl p-4 my-3 text-sm shadow-md">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
            <span className={`text-xs px-2.5 py-0.5 rounded-full border shadow-sm ${platformBadgeStyle()}`}>
              {platformName}
            </span>
            {job.location && (
              <span className="flex items-center gap-1 text-xs text-slate-400">
                <MapPin className="w-3 h-3 text-slate-500" /> {job.location}
              </span>
            )}
            {job.experience && (
              <span className="flex items-center gap-1 text-xs text-slate-400">
                <Briefcase className="w-3 h-3 text-slate-500" /> {job.experience}
              </span>
            )}
            {job.salary && (
              <span className="flex items-center gap-1 text-xs text-emerald-400 font-medium">
                <IndianRupee className="w-3 h-3 text-emerald-500" /> {job.salary}
              </span>
            )}
            {job.posted_date && (
              <span className="flex items-center gap-1 text-xs text-sky-300 bg-sky-950/40 border border-sky-800/40 px-2 py-0.5 rounded-full font-medium">
                <Clock className="w-3 h-3 text-sky-400" /> {job.posted_date}
              </span>
            )}
          </div>
          <h4 className="text-base font-semibold text-slate-100 hover:text-blue-400 transition-colors truncate">
            {job.title}
          </h4>
          <p className="flex items-center gap-1.5 text-xs text-slate-400 mt-0.5">
            <Building2 className="w-3.5 h-3.5 text-slate-500" />
            <span className="font-medium text-slate-300">{job.company}</span>
          </p>
        </div>

        {score > 0 && (
          <div className={`px-2.5 py-1 rounded-lg border text-xs font-bold flex flex-col items-center justify-center shrink-0 ${scoreColor}`}>
            <span className="text-sm font-extrabold">{score}%</span>
            <span className="text-[10px] tracking-tight opacity-80 uppercase font-semibold">Match</span>
          </div>
        )}
      </div>

      {job.snippet && (
        <p className="text-xs text-slate-400 mt-2.5 line-clamp-2 leading-relaxed">
          {job.snippet}
        </p>
      )}

      {/* Match Reasons */}
      {job.match_reasons && job.match_reasons.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {job.match_reasons.slice(0, 3).map((r, i) => (
            <span key={i} className="inline-flex items-center gap-1 text-[11px] bg-emerald-950/40 text-emerald-300 border border-emerald-800/40 px-2 py-0.5 rounded-md">
              <CheckCircle className="w-2.5 h-2.5" /> {r}
            </span>
          ))}
        </div>
      )}

      {/* Missing Skills */}
      {job.missing_skills && job.missing_skills.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {job.missing_skills.slice(0, 2).map((s, i) => (
            <span key={i} className="inline-flex items-center gap-1 text-[11px] bg-rose-950/30 text-rose-300 border border-rose-800/30 px-2 py-0.5 rounded-md">
              <AlertCircle className="w-2.5 h-2.5" /> Missing: {s}
            </span>
          ))}
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex items-center justify-between mt-3.5 pt-3 border-t border-[#2d2d3a] gap-2">
        {job.url ? (
          <a
            href={job.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 font-medium transition-colors"
          >
            <span>View on {platformName}</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        ) : (
          <span className="text-xs text-slate-500">Platform Link Saved</span>
        )}

        <div className="flex items-center gap-2">
          {job.screenshot_url && (
            <a
              href={job.screenshot_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-emerald-950/40 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-900/50 transition-colors shadow-sm"
              title="View live browser verification snapshot"
            >
              <CheckCircle className="w-3 h-3 text-emerald-400" />
              <span>Proof Snapshot</span>
            </a>
          )}

          {job.status === 'APPLIED' ? (
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/25">
              <CheckCircle className="w-3 h-3" />
              <span>{job.submission_status || 'Applied'}</span>
            </span>
          ) : (
            <>
              {onTailorClick && (
                <button
                  onClick={() => onTailorClick(job)}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-gradient-to-r from-purple-600/30 to-indigo-600/30 hover:from-purple-600/50 hover:to-indigo-600/50 text-purple-200 border border-purple-500/30 hover:border-purple-400 transition-all shadow-sm"
                  title="Tailor candidate resume for this job description"
                >
                  <Sparkles className="w-3 h-3 text-purple-300" />
                  <span>Tailor Resume</span>
                </button>
              )}

              <button
                onClick={handleSave}
                disabled={saved || saving}
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${
                  saved
                    ? 'bg-slate-800 text-slate-400 cursor-default'
                    : 'bg-[#282834] hover:bg-[#343444] text-slate-200 border border-[#3e3e50]'
                }`}
              >
                <Bookmark className={`w-3 h-3 ${saved ? 'fill-current text-blue-400' : ''}`} />
                {saved ? 'Saved' : saving ? 'Saving...' : 'Save'}
              </button>

              {onApplyClick && (
                <button
                  onClick={() => onApplyClick(job)}
                  className="inline-flex items-center gap-1 px-3 py-1 rounded-lg text-xs font-medium bg-blue-600 hover:bg-blue-500 text-white transition-colors shadow-sm"
                >
                  <Send className="w-3 h-3" /> Apply
                </button>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};
