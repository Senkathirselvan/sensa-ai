import React, { useState } from "react";
import { api } from "../services/api";
import { ShieldCheck, Monitor, Key, Code, AlertCircle, CheckCircle2, X } from "lucide-react";

export type SupportedPlatform = "linkedin" | "indeed" | "naukri";

interface PlatformLoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  platform: SupportedPlatform;
  onSuccess?: (platform: SupportedPlatform, pendingQuery?: string) => void;
  pendingQuery?: string;
}

const PLATFORM_DETAILS: Record<
  SupportedPlatform,
  {
    name: string;
    brandColor: string;
    iconText: string;
    emailLabel: string;
    emailPlaceholder: string;
    description: string;
    cookiePlaceholder: string;
  }
> = {
  linkedin: {
    name: "LinkedIn",
    brandColor: "from-[#0A66C2]/20 to-[#004182]/20 border-[#0A66C2]/40 text-[#70b5f9]",
    iconText: "in",
    emailLabel: "LinkedIn Email or Phone",
    emailPlaceholder: "name@example.com or +91...",
    description: "Required for LinkedIn Easy Apply automated submission & profile matching",
    cookiePlaceholder: '[{"name":"li_at", "value":"AQED...", "domain":".linkedin.com"}]',
  },
  indeed: {
    name: "Indeed",
    brandColor: "from-[#2164f3]/20 to-[#0039a6]/20 border-[#2164f3]/40 text-[#60a5fa]",
    iconText: "I",
    emailLabel: "Indeed Account Email",
    emailPlaceholder: "name@example.com",
    description: "Required for Indeed Instant Apply and direct profile submissions",
    cookiePlaceholder: '[{"name":"CTK", "value":"...", "domain":".indeed.com"}]',
  },
  naukri: {
    name: "Naukri",
    brandColor: "from-amber-500/20 to-blue-600/20 border-amber-500/30 text-amber-300",
    iconText: "N",
    emailLabel: "Naukri Email or Mobile",
    emailPlaceholder: "name@example.com or 9876543210",
    description: "Required to bypass bot protection & fetch verified applications",
    cookiePlaceholder: '[{"name":"...", "value":"...", "domain":".naukri.com"}]',
  },
};

export const PlatformLoginModal: React.FC<PlatformLoginModalProps> = ({
  isOpen,
  onClose,
  platform,
  onSuccess,
  pendingQuery,
}) => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"credentials" | "paste">("credentials");
  const [pastedJson, setPastedJson] = useState("");

  if (!isOpen) return null;

  const details = PLATFORM_DETAILS[platform] || PLATFORM_DETAILS.linkedin;

  const handleCredentialLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setErrorMessage(`Please enter both ${details.name} email/username and password.`);
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);
    setStatusMessage(`Opening stealth browser to authenticate with ${details.name}...`);

    try {
      const res = await api.loginPlatform(platform, username.trim(), password.trim(), true);
      if (res.success) {
        setStatusMessage(`✅ Successfully connected ${details.name}! Resuming session...`);
        setTimeout(() => {
          setIsLoading(false);
          if (onSuccess) onSuccess(platform, pendingQuery);
          onClose();
        }, 1200);
      } else {
        setIsLoading(false);
        if (res.requires_interactive) {
          setErrorMessage(`⚠️ ${details.name} 2FA / Security Check required. Click "Open Browser Window" below to log in directly on your desktop!`);
        } else {
          setErrorMessage(res.message || `Login to ${details.name} failed. Please verify your credentials or try Desktop Browser login.`);
        }
        setStatusMessage(null);
      }
    } catch (err: any) {
      setIsLoading(false);
      setErrorMessage(err.message || "Failed to connect to authentication service.");
      setStatusMessage(null);
    }
  };

  const handleLaunchBrowser = async () => {
    setIsLoading(true);
    setErrorMessage(null);
    setStatusMessage(`🖥️ Browser window opened on your desktop! Please complete ${details.name} login there...`);

    try {
      const res = await api.loginPlatformInteractive(platform, username.trim() || undefined);
      if (res.success) {
        setStatusMessage(`✅ ${details.name} login detected! Saving session and resuming...`);
        setTimeout(() => {
          setIsLoading(false);
          if (onSuccess) onSuccess(platform, pendingQuery);
          onClose();
        }, 1200);
      } else {
        setIsLoading(false);
        setErrorMessage(res.message || "Login was not completed within the time limit.");
        setStatusMessage(null);
      }
    } catch (err: any) {
      setIsLoading(false);
      setErrorMessage(err.message || "Failed to launch browser window on desktop.");
      setStatusMessage(null);
    }
  };

  const handlePasteSubmit = async () => {
    if (!pastedJson.trim()) return;
    try {
      const parsed = JSON.parse(pastedJson);
      const cookies = Array.isArray(parsed) ? parsed : (parsed.cookies || []);
      if (!cookies.length) {
        setErrorMessage("Invalid cookie JSON: array of cookies expected.");
        return;
      }
      setIsLoading(true);
      const res = await api.pastePlatformCookies(platform, cookies);
      if (res.success) {
        setStatusMessage(`✅ ${details.name} cookies saved successfully!`);
        setTimeout(() => {
          setIsLoading(false);
          if (onSuccess) onSuccess(platform, pendingQuery);
          onClose();
        }, 1000);
      } else {
        setIsLoading(false);
        setErrorMessage(res.message || "Failed to save cookies.");
      }
    } catch {
      setErrorMessage("Failed to parse JSON. Please check the format.");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-in fade-in duration-200">
      <div className="w-full max-w-lg rounded-2xl border border-[#2b2b3b] bg-[#141520] shadow-2xl overflow-hidden text-slate-200">
        
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-[#252738] px-6 py-4 bg-[#10111a]">
          <div className="flex items-center gap-3">
            <div className={`flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br border text-lg font-bold shadow-inner ${details.brandColor}`}>
              {details.iconText}
            </div>
            <div>
              <h3 className="font-semibold text-white text-base">Connect {details.name} Account</h3>
              <p className="text-xs text-slate-400">{details.description}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isLoading}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-[#202234] hover:text-white transition disabled:opacity-50"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Selector */}
        <div className="flex border-b border-[#252738] bg-[#0d0e17] px-6 pt-2">
          <button
            type="button"
            onClick={() => setActiveTab("credentials")}
            className={`flex items-center gap-2 border-b-2 px-3 py-2.5 text-xs font-medium transition-colors ${
              activeTab === "credentials"
                ? "border-blue-500 text-blue-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Key className="w-3.5 h-3.5" />
            Credentials Login
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("paste")}
            className={`flex items-center gap-2 border-b-2 px-3 py-2.5 text-xs font-medium transition-colors ${
              activeTab === "paste"
                ? "border-blue-500 text-blue-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Code className="w-3.5 h-3.5" />
            Paste Cookies JSON
          </button>
        </div>

        {/* Body Content */}
        <div className="p-6 space-y-4">
          {/* Security Banner */}
          <div className="flex items-start gap-2.5 rounded-xl bg-blue-500/10 border border-blue-500/20 p-3 text-xs text-blue-300">
            <ShieldCheck className="h-4 w-4 shrink-0 text-blue-400 mt-0.5" />
            <span>
              Your session is saved securely in your local environment. The agent uses it to seamlessly perform authenticated job operations on your behalf.
            </span>
          </div>

          {/* Feedback messages */}
          {errorMessage && (
            <div className="rounded-xl bg-rose-500/15 border border-rose-500/30 p-3 text-xs text-rose-300 flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <span className="leading-relaxed">{errorMessage}</span>
            </div>
          )}

          {statusMessage && (
            <div className="rounded-xl bg-emerald-500/15 border border-emerald-500/30 p-3 text-xs text-emerald-300 flex items-center gap-2">
              {isLoading ? (
                <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-emerald-400 border-t-transparent shrink-0" />
              ) : (
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              )}
              <span>{statusMessage}</span>
            </div>
          )}

          {activeTab === "credentials" ? (
            <form onSubmit={handleCredentialLogin} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  {details.emailLabel}
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder={details.emailPlaceholder}
                  disabled={isLoading}
                  className="w-full rounded-xl border border-[#2d2f44] bg-[#0d0e17] px-3.5 py-2.5 text-sm text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none transition"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  Password
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  disabled={isLoading}
                  className="w-full rounded-xl border border-[#2d2f44] bg-[#0d0e17] px-3.5 py-2.5 text-sm text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none transition"
                />
              </div>

              <div className="pt-2 flex flex-col gap-2.5">
                <button
                  type="submit"
                  disabled={isLoading}
                  className="w-full flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:from-blue-500 hover:to-indigo-500 transition shadow-lg shadow-blue-500/20 disabled:opacity-50"
                >
                  {isLoading ? "Authenticating..." : `Connect ${details.name} Account`}
                </button>

                <div className="relative flex py-1 items-center">
                  <div className="flex-grow border-t border-[#26283c]"></div>
                  <span className="flex-shrink mx-3 text-slate-500 text-[11px] uppercase tracking-wider">or 2fa / captcha bypass</span>
                  <div className="flex-grow border-t border-[#26283c]"></div>
                </div>

                <button
                  type="button"
                  onClick={handleLaunchBrowser}
                  disabled={isLoading}
                  className="w-full flex items-center justify-center gap-2 rounded-xl border border-[#373a54] bg-[#161826] hover:bg-[#1e2032] px-4 py-2.5 text-xs font-medium text-slate-200 hover:text-white transition shadow-sm"
                >
                  <Monitor className="w-4 h-4 text-sky-400" />
                  <span>Open Browser Window (Solve 2FA / Login manually on desktop)</span>
                </button>
              </div>
            </form>
          ) : (
            <div className="space-y-3">
              <label className="block text-xs font-medium text-slate-300">
                Paste JSON Cookies from Browser Extension (e.g. Cookie-Editor):
              </label>
              <textarea
                rows={5}
                value={pastedJson}
                onChange={(e) => setPastedJson(e.target.value)}
                placeholder={details.cookiePlaceholder}
                disabled={isLoading}
                className="w-full rounded-xl border border-[#2d2f44] bg-[#0d0e17] p-3 text-xs font-mono text-slate-300 focus:border-blue-500 focus:outline-none placeholder-slate-600"
              />
              <button
                type="button"
                onClick={handlePasteSubmit}
                disabled={isLoading || !pastedJson.trim()}
                className="w-full rounded-xl bg-blue-600 px-4 py-2.5 text-xs font-semibold text-white hover:bg-blue-500 transition disabled:opacity-50 shadow-md shadow-blue-500/20"
              >
                Save Cookies & Connect {details.name}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

