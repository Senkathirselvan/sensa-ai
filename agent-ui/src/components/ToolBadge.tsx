import React from 'react';
import { Loader2, CheckCircle2 } from 'lucide-react';

interface ToolBadgeProps {
  statusText?: string;
  isThinking?: boolean;
}

export const ToolBadge: React.FC<ToolBadgeProps> = ({ statusText, isThinking }) => {
  if (!statusText && !isThinking) return null;

  return (
    <div className="inline-flex items-center gap-2 bg-[#1b1b24] border border-[#2d2d3c] px-3 py-1.5 rounded-xl text-xs text-slate-300 my-2 shadow-sm animate-fade-in">
      {isThinking ? (
        <Loader2 className="w-3.5 h-3.5 text-blue-400 animate-spin" />
      ) : (
        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
      )}
      <span className="font-medium text-slate-200">
        {statusText || 'Processing request...'}
      </span>
    </div>
  );
};
