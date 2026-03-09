import React, { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  MessageCircle,
  X,
  Send,
  Mic,
  ChevronDown,
  Minimize2,
  ExternalLink,
  MoreVertical,
  Moon,
  Sun,
  Star,
  LogOut,
  MessageSquarePlus,
  Globe,
} from "lucide-react";

// ─── Types ───────────────────────────────────────────────────────────────────

interface ParsedReference {
  index: number;
  title: string;
  url: string;
}

interface Message {
  id: string;
  text: string;
  sender: "user" | "bot";
  timestamp: Date;
  mediaUrls?: string[];
  videoUrls?: string[];
  references?: ParsedReference[];
  followUpQuestions?: string[]; // clickable suggestion chips
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

// Mandatory API key — must match BACKEND_API_KEY on the server
const BACKEND_API_KEY = "tmkoc2026#trewas2326uvkplS@45wm_tfwsnoname_host";

/**
 * Derive a stable browser fingerprint using Web Crypto SHA-256.
 * Combines stable signals so the same browser always produces the same ID
 * — even after localStorage is cleared.
 */
async function computeFingerprint(): Promise<string> {
  const signals = [
    navigator.userAgent,
    navigator.language,
    `${screen.width}x${screen.height}x${screen.colorDepth}`,
    Intl.DateTimeFormat().resolvedOptions().timeZone,
    String(navigator.hardwareConcurrency ?? 0),
    navigator.platform,
    navigator.vendor ?? "",
  ].join("||");

  const encoded = new TextEncoder().encode(signals);
  const hashBuf = await crypto.subtle.digest("SHA-256", encoded);
  const hashArr = Array.from(new Uint8Array(hashBuf));
  // Use first 12 bytes → 24 hex chars, prefix with 'fp-'
  return (
    "fp-" +
    hashArr
      .slice(0, 12)
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("")
  );
}

/**
 * Detect whether a URL points to a video resource.
 */
function isVideoUrl(url: string): boolean {
  return /\.(mp4|webm|ogg|mov|avi)(\?.*)?$/i.test(url);
}

/**
 * Parse the plain-text References block that comes from the API:
 *
 *   ---
 *   References:
 *   1. Title
 *      https://...
 *   2. Title
 *      https://...
 */
function parseReferences(raw: string): ParsedReference[] {
  if (!raw || !raw.trim()) return [];

  const refs: ParsedReference[] = [];
  // Match numbered items: "N. Title\n   URL"
  const pattern = /(\d+)\.\s+(.+?)\n\s+(https?:\/\/[^\s]+)/g;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(raw)) !== null) {
    refs.push({
      index: parseInt(match[1], 10),
      title: match[2].trim(),
      url: match[3].trim(),
    });
  }
  return refs;
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function BotAvatar() {
  return (
    <div className="w-8 h-8 rounded-[12px] bg-gradient-to-tr from-[#34d399] via-[#3b82f6] to-[#8b5cf6] p-[2px] shrink-0 mt-1">
      <div className="w-full h-full bg-white rounded-[10px] flex items-center justify-center relative overflow-hidden">
        <img
          src="https://userguide.playagegaming.tech/apple-touch-icon.png"
          alt="Playage Bot"
          className="w-full h-full object-cover"
        />
      </div>
    </div>
  );
}

interface MediaPreviewProps {
  urls: string[];
  onImageClick: (url: string) => void;
}

function MediaPreview({ urls, onImageClick }: MediaPreviewProps) {
  const images = urls.filter((u) => !isVideoUrl(u));
  const videos = urls.filter((u) => isVideoUrl(u));

  return (
    <div className="flex flex-col gap-2 mt-3">
      {videos.map((url, i) => (
        <div
          key={i}
          className="rounded-xl overflow-hidden border border-gray-200 shadow-sm"
        >
          <video
            src={url}
            controls
            className="w-full max-h-56 object-cover rounded-xl"
            preload="metadata"
          >
            Your browser does not support the video tag.
          </video>
        </div>
      ))}
      {images.map((url, i) => (
        <div
          key={i}
          className="relative rounded-xl overflow-hidden border border-gray-200 cursor-pointer group shadow-sm"
          onClick={() => onImageClick(url)}
        >
          <img
            src={url}
            alt={`Reference ${i + 1}`}
            className="w-full h-auto max-h-48 object-cover transition-transform duration-300 group-hover:scale-105"
          />
          <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center">
            <Minimize2 className="w-6 h-6 text-white opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
        </div>
      ))}
    </div>
  );
}

interface ReferencesBlockProps {
  refs: ParsedReference[];
}

function ReferencesBlock({ refs }: ReferencesBlockProps) {
  if (!refs.length) return null;

  return (
    <div className="mt-3 pt-3 border-t border-gray-200">
      <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-wide mb-1.5">
        References
      </p>
      <ul className="flex flex-col gap-1">
        {refs.map((ref) => (
          <li key={ref.index} className="flex items-start gap-1.5">
            <span className="text-[12px] text-gray-400 shrink-0 mt-0.5">
              {ref.index}.
            </span>
            <a
              href={ref.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[12px] text-[#1E88E5] hover:text-[#1565C0] hover:underline leading-snug flex items-center gap-1 group"
            >
              <span>{ref.title}</span>
              <ExternalLink className="w-3 h-3 shrink-0 opacity-50 group-hover:opacity-100 transition-opacity" />
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);

  // ── Setup / Onboarding ───────────────────────────────────────────────────────
  const [setupDone, setSetupDone] = useState(
    () => !!localStorage.getItem('playage_username')
  );
  const [userName, setUserName] = useState(
    () => localStorage.getItem('playage_username') || ''
  );
  const [language, setLanguage] = useState<'en' | 'tr'>(
    () => (localStorage.getItem('playage_language') as 'en' | 'tr') || 'en'
  );
  const [setupNameInput, setSetupNameInput] = useState('');

  const handleSetupComplete = (lang: 'en' | 'tr') => {
    const name = setupNameInput.trim() || 'Guest';
    setUserName(name);
    setLanguage(lang);
    localStorage.setItem('playage_username', name);
    localStorage.setItem('playage_language', lang);
    setSetupDone(true);
    // Personalise initial message
    setMessages([
      {
        id: '1',
        text: lang === 'tr'
          ? `Merhaba ${name}! Playage Backoffice Asistanıyım. Size nasıl yardımcı olabilirim?`
          : `Hi ${name}! I'm the Playage Backoffice Assistant. How can I help you today?`,
        sender: 'bot',
        timestamp: new Date(),
      },
    ]);
  };

  const [inputValue, setInputValue] = useState('');
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      text: "Hi! I'm the Playage Backoffice Assistant. How can I help you today?",
      sender: 'bot',
      timestamp: new Date(),
    },
  ]);
  const [isTyping, setIsTyping] = useState(false);
  const [fullscreenImage, setFullscreenImage] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // ── Theme (dark / light) ─────────────────────────────────────────────────
  const [isDark, setIsDark] = useState(
    () => localStorage.getItem("playage_theme") === "dark",
  );
  const toggleTheme = () => {
    setIsDark((prev) => {
      localStorage.setItem("playage_theme", prev ? "light" : "dark");
      return !prev;
    });
  };

  // ── Three-dots menu ───────────────────────────────────────────────────────
  const [menuOpen, setMenuOpen] = useState(false);
  const [showEndConfirm, setShowEndConfirm] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
        setShowEndConfirm(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // ── Feedback modal ───────────────────────────────────────────────────────
  const [showFeedback, setShowFeedback] = useState(false);
  const [feedbackRating, setFeedbackRating] = useState(0);
  const [feedbackHover, setFeedbackHover] = useState(0);
  const [feedbackText, setFeedbackText] = useState("");
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);
  const handleFeedbackSubmit = () => {
    // UI only — no backend
    setFeedbackSubmitted(true);
    setTimeout(() => {
      setShowFeedback(false);
      setFeedbackSubmitted(false);
      setFeedbackRating(0);
      setFeedbackText("");
    }, 1800);
  };

  // ── Session ID: browser-fingerprint based, persistent across storage clears ─
  // 1. Synchronously seed from localStorage cache (instant, avoids flicker)
  // 2. useEffect re-derives fingerprint asynchronously and updates the ref + cache
  //    so even if localStorage was cleared, the same browser gets the same session.
  const sessionIdRef = useRef<string>(
    localStorage.getItem("playage_fp_session") || "fp-loading",
  );

  useEffect(() => {
    computeFingerprint().then((fp) => {
      sessionIdRef.current = fp;
      localStorage.setItem("playage_fp_session", fp);
    });
  }, []);

  // ── End Session ───────────────────────────────────────────────────────────
  const endSession = () => {
    setMenuOpen(false);
    // Delete backend memory
    const sid = sessionIdRef.current;
    if (sid && sid !== "fp-loading") {
      const payload = JSON.stringify({
        session_id: sid,
        api_key: BACKEND_API_KEY,
      });
      navigator.sendBeacon(
        "http://127.0.0.1:8000/session/delete",
        new Blob([payload], { type: "application/json" }),
      );
    }
    // Reset frontend: regenerate session ID + clear messages
    computeFingerprint().then((fp) => {
      // force a new unique session ID by appending timestamp
      const newId = `${fp}-${Date.now()}`;
      sessionIdRef.current = newId;
      localStorage.setItem("playage_fp_session", newId);
    });
    setMessages([
      {
        id: Date.now().toString(),
        text: "Hi! I'm the Playage Backoffice Assistant. How can I help you today?",
        sender: "bot",
        timestamp: new Date(),
      },
    ]);
    setInputValue("");
  };

  // ── Tab/window close → delete session memory from backend ────────────────
  // navigator.sendBeacon works even during page unload (unlike fetch)
  useEffect(() => {
    const handleUnload = () => {
      const sid = sessionIdRef.current;
      if (!sid || sid === "fp-loading") return;
      const payload = JSON.stringify({
        session_id: sid,
        api_key: BACKEND_API_KEY,
      });
      navigator.sendBeacon(
        "http://127.0.0.1:8000/session/delete",
        new Blob([payload], { type: "application/json" }),
      );
    };
    window.addEventListener("beforeunload", handleUnload);
    return () => window.removeEventListener("beforeunload", handleUnload);
  }, []);

  // ── DevTools / Inspect Element Detection ─────────────────────────────────
  // Compares outer window size vs inner viewport. When DevTools is docked
  // (right, bottom, or undocked/floating), the delta exceeds the threshold.
  const [isDevToolsOpen, setIsDevToolsOpen] = useState(false);

  useEffect(() => {
    const THRESHOLD = 160; // px — smaller than any realistic toolbar/sidebar

    const check = () => {
      const widthDelta = window.outerWidth - window.innerWidth;
      const heightDelta = window.outerHeight - window.innerHeight;
      const detected = widthDelta > THRESHOLD || heightDelta > THRESHOLD;
      setIsDevToolsOpen((prev) => (prev !== detected ? detected : prev));
    };

    check(); // run once immediately
    const id = setInterval(check, 500);
    window.addEventListener("resize", check);
    return () => {
      clearInterval(id);
      window.removeEventListener("resize", check);
    };
  }, []);
  // ─────────────────────────────────────────────────────────────────────────

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  // ── Speech Recognition ───────────────────────────────────────────────────
  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    const SpeechRecognition =
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition;
    if (SpeechRecognition) {
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = false;
      recognitionRef.current.interimResults = false;
      recognitionRef.current.lang = "en-US";

      recognitionRef.current.onstart = () => setIsListening(true);
      recognitionRef.current.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript;
        setInputValue((prev) => (prev ? `${prev} ${transcript}` : transcript));
      };
      recognitionRef.current.onerror = () => setIsListening(false);
      recognitionRef.current.onend = () => setIsListening(false);
    }
  }, []);

  const toggleListening = () => {
    if (isListening) {
      recognitionRef.current?.stop();
    } else {
      try {
        recognitionRef.current?.start();
      } catch (e) {
        console.error("Could not start speech recognition:", e);
      }
    }
  };

  // ── Send + API ────────────────────────────────────────────────────────────
  const handleSendMessage = async (text: string) => {
    if (!text.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      text,
      sender: "user",
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue("");
    setIsTyping(true);

    try {
      const apiResponse = await fetch("http://127.0.0.1:8000/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          Username: userName || 'Guest',
          User_preffered_language: language,
          question: text,
          top_k: 5,
          session_id: sessionIdRef.current,
          api_key: BACKEND_API_KEY,
        }),
      });

      if (!apiResponse.ok)
        throw new Error(`HTTP error! status: ${apiResponse.status}`);

      const data = await apiResponse.json();

      // ── Build display text (Definition + Steps only, no Tips inline) ──────
      let responseText = data.Definition || "";

      if (data.Steps && data.Steps.length > 0) {
        responseText +=
          "\n\n" +
          data.Steps.map((step: string, i: number) => `${i + 1}. ${step}`).join(
            "\n",
          );
      }

      // ── Media arrays ──────────────────────────────────────────────────────
      const imageRefs: string[] = Array.isArray(data.Image_References)
        ? data.Image_References
        : [];
      const videoRefs: string[] = Array.isArray(data.Video_References)
        ? data.Video_References
        : [];
      const allMedia = [...videoRefs, ...imageRefs];

      // ── Follow-up question chips ──────────────────────────────────────────
      const followUpQuestions: string[] = Array.isArray(
        data.Follow_Up_Questions,
      )
        ? data.Follow_Up_Questions.slice(0, 3)
        : [];

      // ── References ────────────────────────────────────────────────────────
      const parsedRefs = parseReferences(data.References || "");

      const botMessage: Message = {
        id: (Date.now() + 1).toString(),
        text:
          responseText ||
          (allMedia.length > 0
            ? ""
            : "I'm sorry, I couldn't find information on that."),
        sender: "bot",
        timestamp: new Date(),
        mediaUrls: allMedia,
        references: parsedRefs,
        followUpQuestions,
      };

      setMessages((prev) => [...prev, botMessage]);
    } catch (error) {
      console.error("Error generating response:", error);
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          text: "Sorry, I'm having trouble connecting right now. Please try again later.",
          sender: "bot",
          timestamp: new Date(),
        },
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage(inputValue);
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="fixed bottom-4 right-4 sm:bottom-6 sm:right-6 z-50 flex flex-col items-end pointer-events-none">
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            transition={{ duration: 0.2 }}
            className={`fixed inset-0 sm:static z-50 sm:z-auto w-full h-[100dvh] sm:w-[390px] sm:h-[min(640px,calc(100vh-8rem))] sm:mb-4 rounded-none sm:rounded-2xl shadow-2xl overflow-hidden flex flex-col pointer-events-auto font-sans ${ isDark ? 'bg-[#111827] border border-white/10' : 'bg-white border border-gray-100' }`}
          >
            {/* ── Welcome / Onboarding Screen ───────────────────────────────── */}
            {!setupDone && (
              <div className={`flex flex-col h-full ${ isDark ? 'bg-[#111827]' : 'bg-white' }`}>
                {/* Top brand bar */}
                <div className={`p-4 flex items-center justify-between shrink-0 ${ isDark ? 'bg-[#1a1f2e]' : 'bg-[#1E88E5]' }`}>
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full overflow-hidden shadow-sm shrink-0">
                      <img src="https://userguide.playagegaming.tech/apple-touch-icon.png" alt="Playage" className="w-full h-full object-cover" />
                    </div>
                    <div>
                      <h2 className="font-semibold text-lg text-white leading-tight">Playage AI</h2>
                      <p className="text-xs text-blue-100 opacity-80">Always here to help</p>
                    </div>
                  </div>
                  <button onClick={() => setIsOpen(false)} className="p-1.5 hover:bg-white/10 rounded-full transition-colors text-white">
                    <ChevronDown className="w-5 h-5" />
                  </button>
                </div>

                {/* Welcome content */}
                <div className="flex-1 flex flex-col items-center justify-center px-6 py-8 gap-6">
                  {/* Avatar + greeting */}
                  <div className="flex flex-col items-center gap-3 text-center">
                    <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-[#34d399] via-[#3b82f6] to-[#8b5cf6] p-[2.5px] shadow-lg">
                      <div className="w-full h-full bg-white rounded-[14px] overflow-hidden flex items-center justify-center">
                        <img src="https://userguide.playagegaming.tech/apple-touch-icon.png" alt="Playage" className="w-full h-full object-cover" />
                      </div>
                    </div>
                    <div>
                      <h3 className={`text-[20px] font-bold leading-tight ${ isDark ? 'text-slate-100' : 'text-gray-800' }`}>Welcome!</h3>
                      <p className={`text-[13px] mt-1 ${ isDark ? 'text-slate-400' : 'text-gray-500' }`}>Let's personalise your chat experience.</p>
                    </div>
                  </div>

                  {/* Username input */}
                  <div className="w-full flex flex-col gap-1.5">
                    <label className={`text-[12px] font-semibold ${ isDark ? 'text-slate-300' : 'text-gray-600' }`}>Your Name</label>
                    <input
                      type="text"
                      value={setupNameInput}
                      onChange={(e) => setSetupNameInput(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && setupNameInput.trim() && handleSetupComplete(language)}
                      placeholder="Enter your name…"
                      maxLength={32}
                      className={`w-full rounded-xl px-4 py-3 text-[14px] outline-none border transition-colors ${ isDark
                        ? 'bg-[#1e2535] border-white/10 text-slate-200 placeholder:text-slate-500 focus:border-blue-500/50'
                        : 'bg-gray-50 border-gray-200 text-gray-800 placeholder:text-gray-400 focus:border-[#1E88E5]/50'
                      }`}
                    />
                  </div>

                  {/* Language selection */}
                  <div className="w-full flex flex-col gap-2">
                    <label className={`text-[12px] font-semibold ${ isDark ? 'text-slate-300' : 'text-gray-600' }`}>Choose Your Language</label>
                    <div className="grid grid-cols-2 gap-3">
                      {(['en', 'tr'] as const).map((lang) => (
                        <button
                          key={lang}
                          onClick={() => handleSetupComplete(lang)}
                          disabled={!setupNameInput.trim()}
                          className={`py-3.5 rounded-xl text-[14px] font-semibold border-2 transition-all disabled:opacity-40 disabled:cursor-not-allowed ${ isDark
                            ? 'bg-[#1e2535] border-white/10 text-slate-200 hover:border-blue-500/60 hover:bg-blue-500/10'
                            : 'bg-white border-gray-200 text-gray-700 hover:border-[#1E88E5] hover:bg-blue-50'
                          }`}
                        >
                          <span className="text-lg mr-2">{ lang === 'en' ? '🇬🇧' : '🇹🇷' }</span>
                          { lang === 'en' ? 'English' : 'Türkçe' }
                        </button>
                      ))}
                    </div>
                    <p className={`text-[11px] text-center mt-1 ${ isDark ? 'text-slate-500' : 'text-gray-400' }`}>
                      { !setupNameInput.trim() ? 'Enter your name above to continue' : 'Click a language to start chatting' }
                    </p>
                  </div>
                </div>

                {/* Bottom branding */}
                <div className={`py-3 text-center text-[10px] font-medium ${ isDark ? 'text-slate-600' : 'text-gray-400' }`}>
                  Powered by Playage AI
                </div>
              </div>
            )}

            {/* ── Rest of chat UI (only when setup is done) ─────────────── */}
            {setupDone && (
              <>
            {/* ── DevTools Warning Overlay — Premium Dark Security Screen ─── */}
            {isDevToolsOpen && (
              <div
                className="absolute inset-0 z-[99] flex flex-col items-center justify-center rounded-none sm:rounded-2xl overflow-hidden"
                style={{
                  background:
                    "linear-gradient(160deg, #0f1117 0%, #13151f 100%)",
                }}
              >
                {/* Crimson top-edge accent */}
                <div
                  className="absolute top-0 left-0 right-0 h-[3px]"
                  style={{
                    background:
                      "linear-gradient(90deg, transparent, #dc2626 40%, #ef4444 60%, transparent)",
                  }}
                />

                {/* Ambient glow behind icon */}
                <div
                  className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-48 h-48 rounded-full opacity-10 blur-3xl"
                  style={{ background: "#dc2626" }}
                />

                {/* Content */}
                <div className="relative z-10 flex flex-col items-center px-8 text-center">
                  {/* Shield icon with ring */}
                  <div className="relative mb-6">
                    {/* Outer ping ring */}
                    <div className="absolute inset-0 rounded-full border border-red-500/30 animate-ping" />
                    {/* Icon container */}
                    <div
                      className="relative w-[72px] h-[72px] rounded-2xl flex items-center justify-center"
                      style={{
                        background: "rgba(220,38,38,0.12)",
                        border: "1px solid rgba(220,38,38,0.25)",
                        boxShadow: "0 0 32px rgba(220,38,38,0.2)",
                      }}
                    >
                      {/* Shield-lock SVG */}
                      <svg
                        className="w-9 h-9"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="#ef4444"
                        strokeWidth="1.6"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <path d="M12 2L3 7v5c0 5.25 3.75 10.15 9 11.25C17.25 22.15 21 17.25 21 12V7L12 2z" />
                        <rect x="9" y="11" width="6" height="5" rx="1" />
                        <path d="M10 11V9a2 2 0 1 1 4 0v2" />
                      </svg>
                    </div>
                  </div>

                  {/* Title */}
                  <p
                    className="text-[11px] font-semibold tracking-[0.18em] uppercase mb-2"
                    style={{ color: "#ef4444", letterSpacing: "0.15em" }}
                  >
                    Security Alert
                  </p>
                  <h3
                    className="text-[20px] font-bold mb-3 leading-tight"
                    style={{ color: "#f9fafb" }}
                  >
                    Developer Tools Detected
                  </h3>
                  <p
                    className="text-[13px] leading-relaxed mb-7 max-w-[240px]"
                    style={{ color: "#6b7280" }}
                  >
                    This session is protected.&nbsp;
                    <span style={{ color: "#9ca3af" }}>
                      Close DevTools to resume the assistant.
                    </span>
                  </p>

                  {/* Divider */}
                  <div
                    className="w-full max-w-[240px] mb-5"
                    style={{
                      height: "1px",
                      background: "rgba(255,255,255,0.06)",
                    }}
                  />

                  {/* Keyboard shortcuts */}
                  <p
                    className="text-[10px] font-semibold tracking-[0.12em] uppercase mb-3"
                    style={{ color: "#4b5563" }}
                  >
                    Press to close
                  </p>
                  <div className="flex flex-col items-center gap-2 w-full max-w-[240px]">
                    {/* F12 row */}
                    <div
                      className="flex items-center justify-between w-full px-4 py-2 rounded-lg"
                      style={{
                        background: "rgba(255,255,255,0.04)",
                        border: "1px solid rgba(255,255,255,0.07)",
                      }}
                    >
                      <span
                        className="text-[12px]"
                        style={{ color: "#6b7280" }}
                      >
                        Toggle DevTools
                      </span>
                      <kbd
                        className="px-2 py-0.5 rounded text-[11px] font-mono font-semibold"
                        style={{
                          background: "rgba(255,255,255,0.08)",
                          color: "#e5e7eb",
                          border: "1px solid rgba(255,255,255,0.12)",
                        }}
                      >
                        F12
                      </kbd>
                    </div>
                    {/* Ctrl+Shift+I row */}
                    <div
                      className="flex items-center justify-between w-full px-4 py-2 rounded-lg"
                      style={{
                        background: "rgba(255,255,255,0.04)",
                        border: "1px solid rgba(255,255,255,0.07)",
                      }}
                    >
                      <span
                        className="text-[12px]"
                        style={{ color: "#6b7280" }}
                      >
                        Inspect Element
                      </span>
                      <div className="flex items-center gap-1">
                        {["Ctrl", "Shift", "I"].map((k, i) => (
                          <span key={k} className="flex items-center gap-1">
                            <kbd
                              className="px-1.5 py-0.5 rounded text-[11px] font-mono font-semibold"
                              style={{
                                background: "rgba(255,255,255,0.08)",
                                color: "#e5e7eb",
                                border: "1px solid rgba(255,255,255,0.12)",
                              }}
                            >
                              {k}
                            </kbd>
                            {i < 2 && (
                              <span
                                style={{ color: "#374151", fontSize: "10px" }}
                              >
                                +
                              </span>
                            )}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Bottom brand watermark */}
                <div className="absolute bottom-4 flex items-center gap-1.5">
                  <div
                    className="w-1 h-1 rounded-full"
                    style={{ background: "#374151" }}
                  />
                  <p
                    className="text-[10px] font-medium"
                    style={{ color: "#374151" }}
                  >
                    Playage Security
                  </p>
                  <div
                    className="w-1 h-1 rounded-full"
                    style={{ background: "#374151" }}
                  />
                </div>
              </div>
            )}

            {/* ── Header ─────────────────────────────────────────────────── */}
            <div
              className={`p-4 flex items-center justify-between shrink-0 ${
                isDark ? "bg-[#1a1f2e] text-white" : "bg-[#1E88E5] text-white"
              }`}
            >
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 overflow-hidden shadow-sm">
                  <img
                    src="https://userguide.playagegaming.tech/apple-touch-icon.png"
                    alt="Playage Bot"
                    className="w-full h-full object-cover"
                  />
                </div>
                <div>
                  <h2 className="font-semibold text-lg leading-tight">
                    Playage AI
                  </h2>
                  <p
                    className={`text-xs opacity-80 ${isDark ? "text-slate-400" : "text-blue-100"}`}
                  >
                    Always here to help
                  </p>
                </div>
              </div>

              {/* Right side: lang switcher + three-dots + collapse */}
              <div className="flex items-center gap-1">

                {/* Language switcher — shows only the ALTERNATE language */}
                <button
                  onClick={() => {
                    const next = language === 'en' ? 'tr' : 'en';
                    setLanguage(next);
                    localStorage.setItem('playage_language', next);
                  }}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold tracking-wide hover:bg-white/15 transition-colors border border-white/20"
                  title={language === 'en' ? 'Switch to Turkish' : 'Switch to English'}
                >
                  <Globe className="w-3.5 h-3.5 opacity-80" />
                  {language === 'en' ? 'TR' : 'EN'}
                </button>

                {/* Three-dots menu */}
                <div className="relative" ref={menuRef}>
                  <button
                    onClick={() => setMenuOpen((v) => !v)}
                    className="p-1.5 hover:bg-white/10 rounded-full transition-colors"
                    title="Options"
                  >
                    <MoreVertical className="w-5 h-5" />
                  </button>

                  <AnimatePresence>
                    {menuOpen && (
                      <motion.div
                        initial={{ opacity: 0, scale: 0.92, y: -6 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.92, y: -6 }}
                        transition={{ duration: 0.15 }}
                        className={`absolute right-0 top-9 w-48 rounded-xl shadow-2xl overflow-hidden z-50 border ${
                          isDark
                            ? "bg-[#1e2535] border-white/10"
                            : "bg-white border-gray-100"
                        }`}
                      >
                        {/* ── Normal menu items ── */}
                        {!showEndConfirm ? (
                          <>
                            {/* End Session */}
                            <button
                              onClick={() => setShowEndConfirm(true)}
                              className={`w-full flex items-center gap-3 px-4 py-3 text-[13px] font-medium transition-colors ${
                                isDark
                                  ? "text-red-400 hover:bg-red-500/10"
                                  : "text-red-500 hover:bg-red-50"
                              }`}
                            >
                              <LogOut className="w-4 h-4" />
                              End Session
                            </button>

                            <div className={`mx-3 border-t ${ isDark ? "border-white/8" : "border-gray-100" }`} />

                            {/* Theme toggle — icon badge style, no pill */}
                            <button
                              onClick={() => { toggleTheme(); setMenuOpen(false); }}
                              className={`w-full flex items-center gap-3 px-4 py-3 text-[13px] font-medium transition-colors ${
                                isDark
                                  ? "text-slate-300 hover:bg-white/5"
                                  : "text-gray-700 hover:bg-gray-50"
                              }`}
                            >
                              {/* Icon in a tinted badge */}
                              <span className={`w-6 h-6 rounded-lg flex items-center justify-center ${
                                isDark ? "bg-amber-400/15" : "bg-indigo-50"
                              }`}>
                                {isDark
                                  ? <Sun className="w-3.5 h-3.5 text-amber-400" />
                                  : <Moon className="w-3.5 h-3.5 text-indigo-500" />}
                              </span>
                              {isDark ? "Switch to Light" : "Switch to Dark"}
                            </button>

                            <div className={`mx-3 border-t ${ isDark ? "border-white/8" : "border-gray-100" }`} />

                            {/* Feedback */}
                            <button
                              onClick={() => { setShowFeedback(true); setMenuOpen(false); }}
                              className={`w-full flex items-center gap-3 px-4 py-3 text-[13px] font-medium transition-colors ${
                                isDark
                                  ? "text-slate-300 hover:bg-white/5"
                                  : "text-gray-700 hover:bg-gray-50"
                              }`}
                            >
                              <span className="w-6 h-6 rounded-lg bg-blue-50 flex items-center justify-center">
                                <MessageSquarePlus className="w-3.5 h-3.5 text-[#1E88E5]" />
                              </span>
                              Feedback
                            </button>
                          </>
                        ) : (
                          /* ── End Session confirmation ── */
                          <div className="px-4 py-4 flex flex-col gap-3">
                            <div className="flex items-center gap-2.5 mb-0.5">
                              <span className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${
                                isDark ? "bg-red-500/15" : "bg-red-50"
                              }`}>
                                <LogOut className="w-3.5 h-3.5 text-red-500" />
                              </span>
                              <div>
                                <p className={`text-[13px] font-semibold leading-tight ${ isDark ? "text-slate-100" : "text-gray-800" }`}>End this session?</p>
                                <p className={`text-[11px] leading-tight mt-0.5 ${ isDark ? "text-slate-400" : "text-gray-400" }`}>Your chat history will be cleared.</p>
                              </div>
                            </div>
                            <div className="flex gap-2">
                              <button
                                onClick={() => setShowEndConfirm(false)}
                                className={`flex-1 py-2 rounded-lg text-[12px] font-medium transition-colors ${
                                  isDark
                                    ? "bg-white/8 text-slate-300 hover:bg-white/12"
                                    : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                                }`}
                              >
                                Cancel
                              </button>
                              <button
                                onClick={() => { setShowEndConfirm(false); endSession(); }}
                                className="flex-1 py-2 rounded-lg text-[12px] font-semibold bg-red-500 text-white hover:bg-red-600 transition-colors"
                              >
                                Yes, End It
                              </button>
                            </div>
                          </div>
                        )}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>

                {/* Collapse */}
                <button
                  onClick={() => setIsOpen(false)}
                  className="p-1.5 hover:bg-white/10 rounded-full transition-colors"
                >
                  <ChevronDown className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* ── Messages Area ───────────────────────────────────────────── */}
            <div className={`flex-1 overflow-y-auto p-4 space-y-6 chat-scrollbar ${ isDark ? 'bg-[#111827] dark-scrollbar' : 'bg-white' }`}>
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`flex gap-3 max-w-[88%] ${
                      msg.sender === "user" ? "flex-row-reverse" : "flex-row"
                    }`}
                  >
                    {msg.sender === "bot" && <BotAvatar />}

                    <div className="flex flex-col gap-1">
                      <div
                        className={`p-3.5 rounded-2xl text-[15px] leading-relaxed shadow-sm whitespace-pre-wrap ${
                          msg.sender === "user"
                            ? 'bg-[#1E88E5] text-white rounded-tr-none'
                            : isDark
                              ? 'bg-[#1e2535] text-slate-200 border border-white/8 rounded-tl-none'
                              : 'bg-gray-50 text-gray-800 border border-gray-100 rounded-tl-none'
                        }`}
                      >
                        {/* Text */}
                        {msg.text}

                        {/* Media (images + videos as arrays) */}
                        {msg.mediaUrls && msg.mediaUrls.length > 0 && (
                          <MediaPreview
                            urls={msg.mediaUrls}
                            onImageClick={setFullscreenImage}
                          />
                        )}

                        {/* References */}
                        {msg.references && msg.references.length > 0 && (
                          <ReferencesBlock refs={msg.references} />
                        )}
                      </div>

                      <span className="text-[11px] text-gray-400 px-1">
                        {msg.sender === "bot" ? "AI Assistant · " : "You · "}
                        just now
                      </span>

                      {/* ── Follow-Up Question Chips ───────────────────── */}
                      {msg.sender === "bot" &&
                        msg.followUpQuestions &&
                        msg.followUpQuestions.length > 0 && (
                          <div className="flex flex-col gap-1.5 mt-1">
                            {msg.followUpQuestions.map((q, i) => (
                              <button
                                key={i}
                                onClick={() => handleSendMessage(q)}
                                disabled={isTyping}
                                className={`text-left text-[12px] px-3.5 py-2 rounded-xl transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed leading-snug box-border ${
                                  isDark 
                                    ? 'bg-[#1e253c]/80 border border-blue-500/20 text-blue-300 hover:bg-[#25304d] hover:border-blue-400/40' 
                                    : 'bg-blue-50/60 border border-[#1E88E5]/30 text-[#1E88E5] hover:bg-blue-100/80 hover:border-[#1E88E5]/60'
                                }`}
                              >
                                <span className={`mr-1.5 ${ isDark ? 'text-blue-400/70' : 'opacity-50' }`}>↩</span>
                                {q}
                              </button>
                            ))}
                          </div>
                        )}
                    </div>
                  </div>
                </div>
              ))}

              {/* Typing indicator */}
              {isTyping && (
                <div className="flex justify-start">
                  <div className="flex gap-3 max-w-[85%]">
                    <BotAvatar />
                    <div className={`p-4 rounded-2xl rounded-tl-none shadow-sm flex items-center gap-1.5 ${ isDark ? 'bg-[#1e2535] border border-white/8' : 'bg-gray-50 border border-gray-100' }`}>
                        {[0, 1, 2].map((i) => (
                          <div
                            key={i}
                            className={`w-1.5 h-1.5 rounded-full animate-bounce ${ isDark ? 'bg-slate-500' : 'bg-gray-400' }`}
                            style={{ animationDelay: `${i * 0.15}s` }}
                          />
                        ))}
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* ── Input Area ──────────────────────────────────────────────── */}
            <div className={`p-4 border-t shrink-0 ${ isDark ? 'bg-[#1a1f2e] border-white/8' : 'bg-white border-gray-100' }`}>
              <div className="relative flex items-center gap-2">
                <div className={`flex-1 rounded-full border flex items-center px-4 py-2.5 focus-within:ring-2 transition-all ${
                  isDark
                    ? 'bg-[#111827] border-white/10 focus-within:ring-indigo-500/30 focus-within:border-indigo-500/50'
                    : 'bg-gray-50 border-gray-200 focus-within:ring-blue-100 focus-within:border-blue-300'
                }`}>
                  <input
                    type="text"
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder={
                      isDevToolsOpen
                        ? "Close DevTools to continue…"
                        : "Send message"
                    }
                    disabled={isDevToolsOpen}
                    className={`flex-1 bg-transparent outline-none text-sm placeholder:text-gray-400 ${ isDark ? 'text-slate-200' : 'text-gray-700' }`}
                  />
                  <div className="flex items-center gap-2 text-gray-400">
                    <button
                      onClick={toggleListening}
                      title={isListening ? "Stop recording" : "Start recording"}
                      className={`transition-colors flex items-center justify-center w-8 h-8 rounded-full ${
                        isListening
                          ? "text-red-500 bg-red-50 hover:bg-red-100"
                          : "hover:text-gray-600 hover:bg-gray-100"
                      }`}
                    >
                      <Mic className="w-5 h-5" />
                    </button>
                  </div>
                </div>
                <button
                  onClick={() => handleSendMessage(inputValue)}
                  disabled={!inputValue.trim() || isTyping || isDevToolsOpen}
                  className="p-2.5 rounded-full bg-transparent text-gray-400 hover:text-[#1E88E5] disabled:opacity-50 disabled:hover:text-gray-400 transition-colors"
                >
                  <Send className="w-5 h-5" />
                </button>
              </div>
              <div className="text-center mt-3">
                <p className="text-[10px] text-gray-400 font-medium">
                  Powered by Playage AI
                </p>
              </div>
            </div>

            {/* \u2500\u2500 Feedback Modal Overlay \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500 */}
            <AnimatePresence>
              {showFeedback && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="absolute inset-0 z-[60] flex items-center justify-center p-5"
                  style={{ background: 'rgba(0,0,0,0.45)', backdropFilter: 'blur(4px)' }}
                >
                  <motion.div
                    initial={{ scale: 0.9, y: 16 }}
                    animate={{ scale: 1, y: 0 }}
                    exit={{ scale: 0.9, y: 16 }}
                    transition={{ type: 'spring', stiffness: 320, damping: 24 }}
                    className={`w-full max-w-[300px] rounded-2xl shadow-2xl overflow-hidden ${ isDark ? 'bg-[#1e2535]' : 'bg-white' }`}
                  >
                    {feedbackSubmitted ? (
                      /* Success state */
                      <div className="flex flex-col items-center justify-center py-10 px-6 gap-3">
                        <div className="w-14 h-14 rounded-full bg-green-100 flex items-center justify-center mb-1">
                          <svg className="w-7 h-7 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                          </svg>
                        </div>
                        <p className={`text-[15px] font-semibold ${ isDark ? 'text-slate-100' : 'text-gray-800' }`}>Thanks for your feedback!</p>
                        <p className={`text-[12px] text-center ${ isDark ? 'text-slate-400' : 'text-gray-400' }`}>Your response helps us improve.</p>
                      </div>
                    ) : (
                      /* Feedback form */
                      <div className="flex flex-col">
                        {/* Modal header */}
                        <div className={`flex items-center justify-between px-5 py-4 border-b ${ isDark ? 'border-white/8' : 'border-gray-100' }`}>
                          <div className="flex items-center gap-2">
                            <MessageSquarePlus className="w-4 h-4 text-[#1E88E5]" />
                            <span className={`text-[14px] font-semibold ${ isDark ? 'text-slate-100' : 'text-gray-800' }`}>Share Feedback</span>
                          </div>
                          <button
                            onClick={() => setShowFeedback(false)}
                            className={`p-1 rounded-full transition-colors ${ isDark ? 'hover:bg-white/10 text-slate-400' : 'hover:bg-gray-100 text-gray-400' }`}
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>

                        <div className="px-5 py-4 flex flex-col gap-4">
                          {/* Rate your experience */}
                          <div>
                            <p className={`text-[12px] font-medium mb-2.5 ${ isDark ? 'text-slate-300' : 'text-gray-500' }`}>How was your experience?</p>
                            <div className="flex gap-2 justify-center">
                              {[1, 2, 3, 4, 5].map((star) => (
                                <button
                                  key={star}
                                  onMouseEnter={() => setFeedbackHover(star)}
                                  onMouseLeave={() => setFeedbackHover(0)}
                                  onClick={() => setFeedbackRating(star)}
                                  className="transition-transform hover:scale-110 active:scale-95"
                                >
                                  <Star
                                    className="w-7 h-7 transition-colors"
                                    fill={(feedbackHover || feedbackRating) >= star ? '#f59e0b' : 'none'}
                                    stroke={(feedbackHover || feedbackRating) >= star ? '#f59e0b' : isDark ? '#4b5563' : '#d1d5db'}
                                    strokeWidth={1.8}
                                  />
                                </button>
                              ))}
                            </div>
                          </div>

                          {/* Comment */}
                          <div>
                            <p className={`text-[12px] font-medium mb-1.5 ${ isDark ? 'text-slate-300' : 'text-gray-500' }`}>Comments <span className="opacity-50 font-normal">(optional)</span></p>
                            <textarea
                              value={feedbackText}
                              onChange={(e) => setFeedbackText(e.target.value)}
                              placeholder="Tell us what you think…"
                              rows={3}
                              className={`w-full rounded-xl text-[13px] px-3.5 py-2.5 resize-none outline-none border transition-colors ${ isDark
                                ? 'bg-[#111827] border-white/10 text-slate-200 placeholder:text-slate-500 focus:border-indigo-500/50'
                                : 'bg-gray-50 border-gray-200 text-gray-700 placeholder:text-gray-400 focus:border-blue-300'
                              }`}
                            />
                          </div>

                          {/* Submit */}
                          <button
                            onClick={handleFeedbackSubmit}
                            disabled={feedbackRating === 0}
                            className="w-full py-2.5 rounded-xl text-[13px] font-semibold bg-[#1E88E5] text-white hover:bg-[#1565C0] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                          >
                            Submit Feedback
                          </button>
                        </div>
                      </div>
                    )}
                  </motion.div>
                </motion.div>
              )}
            </AnimatePresence>
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Launcher Button ────────────────────────────────────────────────── */}
      <motion.button
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        onClick={() => setIsOpen(!isOpen)}
        className="pointer-events-auto w-[68px] h-[68px] rounded-[24px] shadow-xl flex items-center justify-center relative group"
      >
        <div className="absolute inset-0 rounded-[24px] bg-gradient-to-br from-[#3bd9a5] via-[#548cf5] to-[#8e52f5] transition-all duration-300 opacity-90 group-hover:opacity-100" />

        {isTyping ? (
          <div className="relative z-10 w-[40px] h-[40px] bg-white rounded-[12px] flex items-center justify-center shadow-lg animate-bounce">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              className="w-7 h-7 text-[#ef4444] animate-[spin_0.8s_linear_infinite]"
            >
              <rect
                width="18"
                height="18"
                x="3"
                y="3"
                rx="4"
                ry="4"
                fill="currentColor"
              />
              <circle cx="8" cy="8" r="1.5" fill="white" />
              <circle cx="16" cy="8" r="1.5" fill="white" />
              <circle cx="12" cy="12" r="1.5" fill="white" />
              <circle cx="8" cy="16" r="1.5" fill="white" />
              <circle cx="16" cy="16" r="1.5" fill="white" />
            </svg>
          </div>
        ) : isOpen ? (
          <div className="relative z-10 w-[36px] h-[36px] bg-white rounded-full flex items-center justify-center shadow-sm">
            <ChevronDown className="w-5 h-5 text-[#548cf5]" strokeWidth={3} />
          </div>
        ) : (
          <div className="absolute inset-[3px] bg-white rounded-[21px] flex items-center justify-center overflow-hidden">
            <img
              src="https://userguide.playagegaming.tech/apple-touch-icon.png"
              alt="Playage Bot"
              className="w-full h-full object-cover"
            />
          </div>
        )}
      </motion.button>

      {/* ── Fullscreen Image Modal ──────────────────────────────────────────── */}
      <AnimatePresence>
        {fullscreenImage && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[60] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 pointer-events-auto"
            onClick={() => setFullscreenImage(null)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              transition={{ type: "spring", damping: 25, stiffness: 300 }}
              className="relative max-w-5xl w-full max-h-[90vh] flex flex-col items-center justify-center"
              onClick={(e) => e.stopPropagation()}
            >
              <button
                onClick={() => setFullscreenImage(null)}
                className="absolute -top-12 right-0 p-2 text-white/70 hover:text-white bg-black/50 hover:bg-black/80 rounded-full transition-all"
              >
                <X className="w-6 h-6" />
              </button>
              <img
                src={fullscreenImage}
                alt="Fullscreen View"
                className="w-full h-full object-contain rounded-lg shadow-2xl"
              />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
