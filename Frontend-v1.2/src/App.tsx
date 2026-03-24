import { useState, useEffect, useRef } from 'react';
import Sidebar from './components/Sidebar';
import ChatArea from './components/ChatArea';
import ConfirmationModal from './components/ConfirmationModal';
import { BACKEND_API_KEY, API_BASE_URL, computeFingerprint, parseReferences } from './services/api';
import type { Message } from './services/api';
import { X } from 'lucide-react';
import SettingsModal from './components/SettingsModal';

export interface ChatSession {
  id: string;
  messages: Message[];
  title?: string;
}

function App() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const sessionIdRef = useRef<string>("fp-loading");
  
  // Security
  const [isDevToolsOpen, setIsDevToolsOpen] = useState(false);

  // Settings & Session State
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'dark');
  const [fontFamily, setFontFamily] = useState(() => localStorage.getItem('fontFamily') || 'sans');
  const [fontSize, setFontSize] = useState(() => localStorage.getItem('fontSize') || 'text-[15px]');
  const [language, setLanguage] = useState(() => localStorage.getItem('language') || 'English');
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isConfirmingNewChat, setIsConfirmingNewChat] = useState(false);
  const [isViewingHistory, setIsViewingHistory] = useState(false);
  
  const [chatHistory, setChatHistory] = useState<ChatSession[]>(() => {
    const saved = localStorage.getItem('chatHistory');
    if (!saved) return [];
    try {
      const parsed = JSON.parse(saved);
      // Migration: Convert old Message[][] to ChatSession[]
      if (Array.isArray(parsed) && parsed.length > 0 && Array.isArray(parsed[0])) {
        return (parsed as Message[][]).map(msgs => ({
          id: Math.random().toString(36).substring(7),
          messages: msgs
        }));
      }
      return parsed;
    } catch {
      return [];
    }
  });

  // Persist Settings & History
  useEffect(() => {
    localStorage.setItem('theme', theme);
    localStorage.setItem('fontFamily', fontFamily);
    localStorage.setItem('fontSize', fontSize);
    localStorage.setItem('language', language);
    localStorage.setItem('chatHistory', JSON.stringify(chatHistory));
  }, [theme, fontFamily, fontSize, language, chatHistory]);

  // Initialization
  useEffect(() => {
    computeFingerprint().then((fp) => {
      sessionIdRef.current = fp;
      localStorage.setItem("playage_gemini_session", fp);
    });

    const checkDevTools = () => {
      const THRESHOLD = 160;
      const widthDelta = window.outerWidth - window.innerWidth;
      const heightDelta = window.outerHeight - window.innerHeight;
      const detected = widthDelta > THRESHOLD || heightDelta > THRESHOLD;
      setIsDevToolsOpen((prev) => (prev !== detected ? detected : prev));
    };

    checkDevTools();
    const id = setInterval(checkDevTools, 500);
    window.addEventListener("resize", checkDevTools);
    return () => {
      clearInterval(id);
      window.removeEventListener("resize", checkDevTools);
    };
  }, []);

  // Backend session cleanup helper
  const clearBackendSession = () => {
    const sid = sessionIdRef.current;
    if (!sid || sid === "fp-loading") return;
    const payload = JSON.stringify({
      session_id: sid,
      api_key: BACKEND_API_KEY,
    });
    fetch(`${API_BASE_URL}/session/delete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: payload
    }).catch(e => console.error("Session cleanup failed:", e));
  };

  const handleNewChatClick = () => {
    if (isViewingHistory || messages.length === 0) {
      confirmNewChat();
    } else {
      setIsConfirmingNewChat(true);
    }
  };

  const confirmNewChat = () => {
    clearBackendSession();

    if (messages.length > 0 && !isViewingHistory) {
      const newSession: ChatSession = {
        id: Date.now().toString(),
        messages: messages
      };
      setChatHistory(prev => [newSession, ...prev].slice(0, 5));
    }

    setMessages([]);
    setIsViewingHistory(false);

    computeFingerprint().then((fp) => {
      sessionIdRef.current = `${fp}-${Date.now()}`;
    });

    setIsConfirmingNewChat(false);
  };

  const handleDeleteHistory = (id: string) => {
    setChatHistory(prev => prev.filter(session => session.id !== id));
  };

  const handleRenameHistory = (id: string, newTitle: string) => {
    setChatHistory(prev => prev.map(session => 
      session.id === id ? { ...session, title: newTitle } : session
    ));
  };

  const handleSendMessage = async (text: string) => {
    if (!text.trim() || isDevToolsOpen) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      text,
      sender: "user",
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsTyping(true);

    try {
      const apiResponse = await fetch(`${API_BASE_URL}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          Username: "User",
          User_preffered_language: language === 'Turkish' ? "tr" : "en",
          question: text,
          top_k: 5,
          session_id: sessionIdRef.current,
          api_key: BACKEND_API_KEY,
        }),
      });

      if (!apiResponse.ok) throw new Error(`HTTP error! status: ${apiResponse.status}`);
      const data = await apiResponse.json();

      let responseText = data.Definition || "";
      if (data.Steps && data.Steps.length > 0) {
        responseText += "\n\n" + data.Steps.map((s: string, i: number) => `${i + 1}. ${s.replace(/^\d+[\.\)]\s*/, '')}`).join("\n");
      }

      const imageRefs = Array.isArray(data.Image_References) ? data.Image_References : [];
      const videoRefs = Array.isArray(data.Video_References) ? data.Video_References : [];
      const followUpQuestions = Array.isArray(data.Follow_Up_Questions) ? data.Follow_Up_Questions.slice(0, 3) : [];
      const parsedRefs = parseReferences(data.References || "");

      const botMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: responseText || ((imageRefs.length || videoRefs.length) ? "" : "I couldn't find information on that."),
        sender: "bot",
        timestamp: new Date(),
        mediaUrls: [...videoRefs, ...imageRefs],
        references: parsedRefs,
        followUpQuestions,
      };

      setMessages((prev) => [...prev, botMessage]);
    } catch (error) {
      console.error(error);
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          text: "Sorry, I'm having trouble connecting to the backend right now.",
          sender: "bot",
          timestamp: new Date(),
        },
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className={`flex w-full h-[100dvh] transition-colors duration-200 bg-white dark:bg-[#111111] ${fontFamily === 'serif' ? 'font-serif' : fontFamily === 'mono' ? 'font-mono' : 'font-sans'} ${fontSize === 'text-sm' ? 'text-sm' : fontSize === 'text-lg' ? 'text-lg' : 'text-[15px]'} text-gray-900 dark:text-white selection:bg-blue-500/30 overflow-hidden relative ${theme === 'dark' ? 'dark' : ''}`}>
      
      {isDevToolsOpen && (
        <div className="absolute inset-0 z-[9999] bg-white dark:bg-[#131314] flex flex-col items-center justify-center p-8 text-center text-gray-900 dark:text-[#e3e3e3] font-sans">
           <div className="w-16 h-16 rounded-full bg-red-500/10 flex items-center justify-center mb-6 border border-red-500/20">
             <X className="w-8 h-8 text-red-500" />
           </div>
           <h1 className="text-2xl font-bold mb-3 tracking-wide">Developer Tools Detected</h1>
           <p className="text-gray-600 dark:text-[#a3a3a3] max-w-sm">
             Playage Security requires you to close DevTools before continuing this session.
           </p>
        </div>
      )}

      <Sidebar 
        isOpen={isSidebarOpen} 
        setIsOpen={setIsSidebarOpen} 
        onNewChat={handleNewChatClick}
        onSettingsClick={() => setIsSettingsOpen(true)}
        language={language}
        history={chatHistory}
        viewHistory={(msgs) => {
          setMessages(msgs);
          setIsViewingHistory(true);
        }}
        onDeleteHistory={handleDeleteHistory}
        onRenameHistory={handleRenameHistory}
      />
      
      <main className="flex-1 w-0 flex flex-col relative h-full overflow-hidden">
         <ChatArea 
           messages={messages}
           isTyping={isTyping}
           onSendMessage={handleSendMessage}
           language={language}
           setLanguage={setLanguage}
           isViewingHistory={isViewingHistory}
           isSidebarOpen={isSidebarOpen}
           setIsSidebarOpen={setIsSidebarOpen}
         />
      </main>
      
      <SettingsModal 
         isOpen={isSettingsOpen}
         onClose={() => setIsSettingsOpen(false)}
         theme={theme}
         setTheme={setTheme}
         fontFamily={fontFamily}
         setFontFamily={setFontFamily}
         fontSize={fontSize}
         setFontSize={setFontSize}
         language={language}
      />

      <ConfirmationModal 
        isOpen={isConfirmingNewChat}
        onClose={() => setIsConfirmingNewChat(false)}
        onConfirm={confirmNewChat}
        language={language}
      />
    </div>
  );
}

export default App;
