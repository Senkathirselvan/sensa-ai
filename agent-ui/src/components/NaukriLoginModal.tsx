import React, { useState } from "react";
import { api } from "../services/api";

interface NaukriLoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (pendingQuery?: string) => void;
  pendingQuery?: string;
}

export const NaukriLoginModal: React.FC<NaukriLoginModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  pendingQuery,
}) => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [showPasteTab, setShowPasteTab] = useState(false);
  const [pastedJson, setPastedJson] = useState("");

  if (!isOpen) return null;

  const handleCredentialLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setErrorMessage("Please enter both email/username and password.");
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);
    setStatusMessage("Opening browser to authenticate with Naukri...");

    try {
      const res = await api.loginNaukri(username.trim(), password.trim());
      if (res.success) {
        setStatusMessage("✅ Successfully connected! Resuming job search...");
        setTimeout(() => {
          setIsLoading(false);
          onSuccess(pendingQuery);
        }, 1200);
      } else {
        setIsLoading(false);
        let msg = res.detail || res.message || "Login failed. Please check your credentials.";
        if (msg.includes("Invalid details") || msg.includes("Email ID - Password combination")) {
          msg = "❌ Invalid email or password. Please verify your credentials.";
        } else if (msg.includes("BrowserType.launch") || msg.includes("Target page")) {
          msg = "⚠️ Browser initialization error. Please try pasting cookies or run interactive login.";
        }
        setErrorMessage(msg);
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
    setStatusMessage("🖥️ Browser window opened on your desktop! Please log in to Naukri there...");

    try {
      const res = await api.loginNaukri();
      if (res.success) {
        setStatusMessage("✅ Login detected! Saving session and resuming search...");
        setTimeout(() => {
          setIsLoading(false);
          onSuccess(pendingQuery);
        }, 1200);
      } else {
        setIsLoading(false);
        setErrorMessage(res.message || "Login was not completed within the time limit.");
        setStatusMessage(null);
      }
    } catch (err: any) {
      setIsLoading(false);
      setErrorMessage(err.message || "Failed to launch browser window.");
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
      const res = await api.pasteNaukriCookies(cookies);
      if (res.success) {
        setStatusMessage("✅ Cookies saved successfully! Resuming search...");
        setTimeout(() => {
          setIsLoading(false);
          onSuccess(pendingQuery);
        }, 1000);
      } else {
        setIsLoading(false);
        setErrorMessage("Failed to save cookies.");
      }
    } catch (e: any) {
      setErrorMessage("Failed to parse JSON. Please check the format.");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="w-full max-w-lg rounded-2xl border border-[#2b2b36] bg-[#1a1a24] shadow-2xl overflow-hidden text-gray-200">
        
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-[#2b2b36] px-6 py-4 bg-[#14141c]">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20 text-xl font-bold">
              N
            </div>
            <div>
              <h3 className="font-semibold text-white text-base">Connect Naukri Account</h3>
              <p className="text-xs text-gray-400">Required to bypass bot protection & fetch live jobs</p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isLoading}
            className="text-gray-400 hover:text-white transition p-1 rounded-lg hover:bg-[#2b2b36]"
          >
            ✕
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-4">
          {pendingQuery && (
            <div className="rounded-lg bg-blue-500/10 border border-blue-500/20 p-3 text-xs text-blue-300">
              <span className="font-semibold">Paused Query: </span>"{pendingQuery}"
              <p className="text-gray-400 mt-0.5">Search will automatically resume once logged in.</p>
            </div>
          )}

          {errorMessage && (
            <div className="rounded-lg bg-red-500/10 border border-red-500/20 p-3 text-xs text-red-400">
              {errorMessage}
            </div>
          )}

          {statusMessage && (
            <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/20 p-3 text-xs text-emerald-300 flex items-center gap-2">
              {isLoading && <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-emerald-400 border-t-transparent" />}
              {statusMessage}
            </div>
          )}

          {!showPasteTab ? (
            <form onSubmit={handleCredentialLogin} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1">
                  Naukri Email or Mobile Number
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="name@example.com"
                  disabled={isLoading}
                  className="w-full rounded-xl border border-[#2b2b36] bg-[#121218] px-3.5 py-2.5 text-sm text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none transition"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1">
                  Password
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  disabled={isLoading}
                  className="w-full rounded-xl border border-[#2b2b36] bg-[#121218] px-3.5 py-2.5 text-sm text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none transition"
                />
              </div>

              <div className="pt-2 flex flex-col gap-2.5">
                <button
                  type="submit"
                  disabled={isLoading}
                  className="w-full flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-500 transition shadow-lg shadow-blue-500/20 disabled:opacity-50"
                >
                  {isLoading ? "Connecting..." : "Connect & Search Jobs"}
                </button>

                <div className="relative flex py-1 items-center">
                  <div className="flex-grow border-t border-[#2b2b36]"></div>
                  <span className="flex-shrink mx-3 text-gray-500 text-xs uppercase tracking-wider">or</span>
                  <div className="flex-grow border-t border-[#2b2b36]"></div>
                </div>

                <button
                  type="button"
                  onClick={handleLaunchBrowser}
                  disabled={isLoading}
                  className="w-full flex items-center justify-center gap-2 rounded-xl border border-[#3b3b4d] bg-[#161622] px-4 py-2 text-xs font-medium text-gray-300 hover:text-white hover:bg-[#20202e] transition"
                >
                  🖥️ Open Browser Window (Solve OTP / CAPTCHA manually)
                </button>
              </div>
            </form>
          ) : (
            <div className="space-y-3">
              <label className="block text-xs font-medium text-gray-400">
                Paste JSON Cookies from Browser Extension (Cookie-Editor):
              </label>
              <textarea
                rows={5}
                value={pastedJson}
                onChange={(e) => setPastedJson(e.target.value)}
                placeholder='[{"name":"...", "value":"...", "domain":".naukri.com"}]'
                disabled={isLoading}
                className="w-full rounded-xl border border-[#2b2b36] bg-[#121218] p-3 text-xs font-mono text-gray-300 focus:border-blue-500 focus:outline-none"
              />
              <button
                type="button"
                onClick={handlePasteSubmit}
                disabled={isLoading || !pastedJson.trim()}
                className="w-full rounded-xl bg-blue-600 px-4 py-2 text-xs font-medium text-white hover:bg-blue-500 transition disabled:opacity-50"
              >
                Save Cookies & Continue
              </button>
            </div>
          )}

          <div className="text-center pt-2">
            <button
              type="button"
              onClick={() => {
                setShowPasteTab(!showPasteTab);
                setErrorMessage(null);
              }}
              className="text-xs text-gray-400 hover:text-blue-400 transition underline underline-offset-4"
            >
              {showPasteTab ? "← Back to Username & Password" : "Or paste exported JSON cookies instead"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
