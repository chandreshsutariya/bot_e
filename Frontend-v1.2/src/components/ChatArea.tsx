import React, { useState, useRef, useEffect } from 'react';
import { ArrowUp, ChevronDown, ExternalLink, Copy, ThumbsUp, ThumbsDown, X, ChevronLeft, ChevronRight, Dices, PanelLeft } from 'lucide-react';
import { isVideoUrl } from '../services/api';
import type { Message } from '../services/api';

interface ChatAreaProps {
  messages: Message[];
  isTyping: boolean;
  onSendMessage: (msg: string) => void;
  language: string;
  setLanguage: (val: string) => void;
  isViewingHistory?: boolean;
  isSidebarOpen: boolean;
  setIsSidebarOpen: (open: boolean) => void;
}

const MediaCarousel = ({ mediaUrls, setSelectedImage }: { mediaUrls: string[], setSelectedImage: (url: string) => void }) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  const scroll = (direction: 'left' | 'right') => {
    if (scrollRef.current) {
      const scrollAmount = 300;
      scrollRef.current.scrollBy({ left: direction === 'left' ? -scrollAmount : scrollAmount, behavior: 'smooth' });
    }
  };

  return (
    <div className="relative group mt-4 w-full">
      {mediaUrls.length > 1 && (
        <>
          <button onClick={() => scroll('left')} className="absolute left-2 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-black/60 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity z-10 hover:bg-black/80 shadow-lg backdrop-blur-sm">
            <ChevronLeft className="w-5 h-5" />
          </button>
          <button onClick={() => scroll('right')} className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-black/60 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity z-10 hover:bg-black/80 shadow-lg backdrop-blur-sm">
            <ChevronRight className="w-5 h-5" />
          </button>
        </>
      )}
      <div ref={scrollRef} className="flex gap-3 overflow-x-auto w-full snap-x snap-mandatory pb-2 scroll-smooth [&::-webkit-scrollbar]:hidden [-ms-overflow-style:'none'] [scrollbar-width:'none']">
        {mediaUrls.map((url, i) => (
          isVideoUrl(url) ? (
            <video key={i} src={url} controls className="h-[200px] md:h-[240px] w-auto shrink-0 rounded-xl border border-gray-200 dark:border-white/10 shadow-sm bg-black snap-center object-cover" />
          ) : (
            <img key={i} src={url} alt="Reference" className="h-[200px] md:h-[240px] w-auto shrink-0 rounded-xl border border-gray-200 dark:border-white/10 shadow-sm cursor-pointer hover:opacity-90 transition-opacity snap-center object-cover" onClick={() => setSelectedImage(url)} />
          )
        ))}
      </div>
    </div>
  );
};

const SourceGallery = ({ references, language }: { references: any[], language: string }) => {
  const [isOpen, setIsOpen] = useState(false);
  const isTurkish = language === 'Turkish';

  const getHostname = (url: string) => {
    try {
      const host = new URL(url).hostname;
      return host.replace('www.', '');
    } catch {
      return 'source';
    }
  };

  return (
    <div className="mt-6 w-full">
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-3 bg-gray-50 dark:bg-white/[0.03] hover:bg-gray-100 dark:hover:bg-white/[0.06] border border-gray-200 dark:border-white/5 rounded-full px-4 py-2 transition-all group"
      >
        <div className="flex -space-x-1.5 overflow-hidden">
          {references.slice(0, 3).map((ref, i) => (
            <img 
              key={i}
              src={`https://www.google.com/s2/favicons?domain=${new URL(ref.url).hostname}&sz=32`}
              alt="icon"
              className="w-4 h-4 rounded-full border border-white dark:border-[#111111] bg-white object-contain"
              onError={(e) => { (e.target as HTMLImageElement).src = import.meta.env.VITE_FAVICON_URL || 'https://userguide.playagegaming.tech/favicon.ico'; }}
            />
          ))}
        </div>
        <span className="text-[13px] font-semibold text-gray-700 dark:text-white/70 group-hover:text-gray-900 dark:group-hover:text-white transition-colors">
          {references.length} {isTurkish ? 'kaynak' : 'sources'}
        </span>
        <ChevronDown className={`w-4 h-4 text-gray-400 group-hover:text-gray-600 dark:group-hover:text-white/80 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 mt-4 animate-in fade-in slide-in-from-top-2 duration-300">
          {references.map((ref, i) => (
            <a 
              key={i} 
              href={ref.url} 
              target="_blank" 
              rel="noopener noreferrer" 
              className="flex flex-col gap-2 p-4 bg-white dark:bg-white/[0.02] hover:bg-gray-50 dark:hover:bg-white/[0.05] border border-gray-200 dark:border-white/5 rounded-2xl transition-all group/card shadow-sm hover:shadow-md"
            >
              <div className="flex items-center gap-2">
                <img 
                  src={`https://www.google.com/s2/favicons?domain=${new URL(ref.url).hostname}&sz=64`}
                  alt="site icon"
                  className="w-4 h-4 rounded-sm object-contain opacity-80 group-hover/card:opacity-100 transition-opacity"
                  onError={(e) => { (e.target as HTMLImageElement).src = import.meta.env.VITE_FAVICON_URL || 'https://userguide.playagegaming.tech/favicon.ico'; }}
                />
                <span className="text-[11px] font-bold text-gray-400 dark:text-white/30 uppercase tracking-widest truncate">
                  {getHostname(ref.url)}
                </span>
              </div>
              <p className="text-[13px] font-medium text-gray-700 dark:text-white/80 leading-snug group-hover/card:text-blue-600 dark:group-hover/card:text-blue-400 transition-colors line-clamp-2">
                {ref.title}
              </p>
            </a>
          ))}
        </div>
      )}
    </div>
  );
};

export default function ChatArea({ messages, isTyping, onSendMessage, language, setLanguage, isViewingHistory = false, isSidebarOpen, setIsSidebarOpen }: ChatAreaProps) {
  const [inputValue, setInputValue] = useState("");
  const [langOpen, setLangOpen] = useState(false);
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const hasMessages = messages.length > 0;
  const isTurkish = language === 'Turkish';

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (inputValue.trim() && !isTyping) {
        onSendMessage(inputValue);
        setInputValue('');
      }
    }
  };

  const renderFormattedText = (text: string) => {
    if (!text) return null;
    const parts = text.split(/(\*\*.*?\*\*|https?:\/\/[^\s]+)/g);
    return parts.map((part, index) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={index} className="font-bold">{part.slice(2, -2)}</strong>;
      }
      if (part.startsWith('http')) {
        return (
          <a key={index} href={part} target="_blank" rel="noopener noreferrer" className="text-blue-600 dark:text-[#3b82f6] hover:underline inline-flex items-center gap-1">
            {part}
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        );
      }
      return <React.Fragment key={index}>{part}</React.Fragment>;
    });
  };

  const getProcessedText = (msg: Message) => {
    const noInfoBackend = "This information is not available in the documentation.";
    if (msg.sender === 'bot' && msg.text.trim() === noInfoBackend) {
      const userguideUrl = import.meta.env.VITE_USERGUIDE_URL || "https://userguide.playagegaming.tech/";
      return isTurkish 
        ? `Üzgünüz, bu konuda bilgim yok.\nBilgi tabanımda bu sorunun cevabı bulunmamaktadır.\nBuradan kontrol edebilirsiniz:\n${userguideUrl}`
        : `Sorry For Inconvenience\nI don't have answer of this question in My knowlegefe base\nSo u can check it here\n${userguideUrl}`;
    }
    return msg.text;
  };

  return (
    <div className="flex-1 h-full flex flex-col relative bg-[#f9fafb] dark:bg-black overflow-hidden w-full min-w-0 transition-colors duration-200">
       {/* Top Header */}
      <div className="h-[72px] w-full flex items-center justify-between px-6 shrink-0 pointer-events-none z-30">
        
        {/* Left: Sidebar Toggle */}
        <div className="flex items-center pointer-events-auto">
          <button 
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className="p-2.5 bg-white dark:bg-[#1e1e1e] border border-gray-200 dark:border-white/10 rounded-2xl shadow-sm hover:shadow-md transition-all active:scale-95 group/toggle"
          >
            <PanelLeft className={`w-5 h-5 ${isSidebarOpen ? 'text-blue-500' : 'text-gray-400 dark:text-white/40 group-hover/toggle:text-blue-500'}`} />
          </button>
        </div>

        {/* Center: Branding (Absolute Center) */}
        <div className="absolute left-1/2 -translate-x-1/2 pointer-events-none">
          <div className="font-bold text-[20px] bg-gradient-to-r from-gray-900 to-gray-600 dark:from-white dark:to-white/60 bg-clip-text text-transparent tracking-tight whitespace-nowrap">Playage AI</div>
        </div>

        {/* Right: Language Selector (Perfect Floating Pill) */}
        <div className="flex items-center pointer-events-auto">
          <div className="relative group/lang">
            <button 
              onClick={() => setLangOpen(!langOpen)}
              className={`p-1 bg-white dark:bg-[#1a1a1a] border ${langOpen ? 'border-blue-500 ring-2 ring-blue-500/10' : 'border-gray-200 dark:border-white/10'} rounded-full shadow-sm hover:shadow-md transition-all duration-300 active:scale-95 overflow-hidden w-10 h-10 flex items-center justify-center relative z-50`}
            >
              <img 
                src={language === 'English' ? 'https://flagcdn.com/gb.svg' : 'https://flagcdn.com/tr.svg'} 
                className="w-8 h-8 aspect-square rounded-full object-cover shadow-sm" 
                alt={language} 
              />
            </button>
            
            {langOpen && (
              <div className="absolute right-0 top-[calc(100%+12px)] flex flex-col items-center bg-white/90 dark:bg-[#1e1e1e]/90 backdrop-blur-xl border border-gray-200 dark:border-white/10 rounded-full shadow-2xl p-1.5 z-40 animate-in fade-in zoom-in-95 duration-200 origin-top">
                <div className="flex flex-col gap-3 py-1">
                  <button 
                    onClick={() => { setLanguage('English'); setLangOpen(false); }}
                    className={`w-8 h-8 rounded-full transition-all duration-300 hover:scale-110 relative group/btn ${language === 'English' ? 'ring-2 ring-blue-500 ring-offset-2 dark:ring-offset-[#1e1e1e] scale-105 shadow-md' : 'opacity-40 hover:opacity-100 grayscale-[0.3] hover:grayscale-0'}`}
                  >
                    <img src="https://flagcdn.com/gb.svg" className="w-full h-full aspect-square rounded-full object-cover" alt="English" title="English" />
                    {language === 'English' && <div className="absolute -right-0.5 -top-0.5 w-2.5 h-2.5 bg-blue-500 rounded-full border-2 border-white dark:border-[#1e1e1e] shadow-sm" />}
                  </button>
                  <button 
                    onClick={() => { setLanguage('Turkish'); setLangOpen(false); }}
                    className={`w-8 h-8 rounded-full transition-all duration-300 hover:scale-110 relative group/btn ${language === 'Turkish' ? 'ring-2 ring-blue-500 ring-offset-2 dark:ring-offset-[#1e1e1e] scale-105 shadow-md' : 'opacity-40 hover:opacity-100 grayscale-[0.3] hover:grayscale-0'}`}
                  >
                    <img src="https://flagcdn.com/tr.svg" className="w-full h-full aspect-square rounded-full object-cover" alt="Turkish" title="Türkçe" />
                    {language === 'Turkish' && <div className="absolute -right-0.5 -top-0.5 w-2.5 h-2.5 bg-blue-500 rounded-full border-2 border-white dark:border-[#1e1e1e] shadow-sm" />}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden flex flex-col items-center px-4 md:px-8 pb-48 w-full">
        {!hasMessages && !isViewingHistory ? (
          <div className="flex flex-col items-center justify-start min-h-[60vh] w-full text-center px-4 animate-in fade-in slide-in-from-bottom-4 duration-1000 pt-[15vh]">
            <div className="flex flex-col items-center gap-2 mb-4">
               <h2 className="text-xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent tracking-tight">
                  Hello User
               </h2>
               <h1 className="text-3xl md:text-[52px] font-medium text-gray-900 dark:text-white tracking-[-0.02em] mb-6 leading-[1.15] max-w-[900px]">
                 {isTurkish 
                   ? "Playage Backoffice AI'ya Hoş Geldiniz" 
                   : "Welcome to Playage Backoffice AI"}
               </h1>
            </div>
            
            {/* Centered Large Input Box */}
            <div className="w-full max-w-[800px] mt-8">
              <div className="bg-white dark:bg-[#202020] rounded-[32px] border border-gray-200 dark:border-white/10 focus-within:border-blue-500 dark:focus-within:border-blue-500 shadow-[0_8px_30px_rgb(0,0,0,0.04)] dark:shadow-xl transition-all duration-300 min-h-[160px] flex flex-col relative group/input">
                <textarea 
                  value={inputValue} 
                  onChange={(e) => setInputValue(e.target.value)} 
                  onKeyDown={handleKeyDown} 
                  placeholder={isTurkish ? "Sorularınızı buraya sorun....." : 'Ask Your Doubts here.....'} 
                  className="flex-1 w-full bg-transparent border-none outline-none text-gray-900 dark:text-white placeholder:text-gray-400 dark:placeholder:text-[#6e6e6e] resize-none px-7 py-6 text-lg" 
                />
                <div className="flex items-center justify-between px-6 py-4 mt-auto">
                  <div className="flex items-center gap-4 relative">
                    {/* Media support button removed */}
                  </div>
                  <div className="flex items-center gap-6">
                    <button 
                      onClick={() => { if(inputValue.trim() && !isTyping) { onSendMessage(inputValue); setInputValue(''); } }}
                      className={`w-[40px] h-[40px] rounded-full flex items-center justify-center transition-all shadow-md
                        ${(inputValue.trim() && !isTyping) ? "bg-blue-600 dark:bg-[#3b82f6] text-white hover:bg-blue-700 scale-110" : "bg-gray-100 dark:bg-white/5 text-gray-400 dark:text-[#333] opacity-50"}
                      `}
                      disabled={!inputValue.trim() || isTyping}
                    >
                      <ArrowUp className="w-[20px] h-[20px]" strokeWidth={3} />
                    </button>
                  </div>
                </div>
              </div>
            </div>
            <div className="text-center mt-3.5 mb-1 text-[10px] text-gray-400 dark:text-[#525252] font-[600] tracking-wider uppercase px-4 truncate">
              {isTurkish ? 'Playage AI Studio tarafından geliştirilen sohbet arayüzü.' : 'chat Interface by Playage AI Studio.'}
            </div>
          </div>
        ) : (
          <div className="w-full max-w-[48rem] flex flex-col gap-6 pt-4 min-w-0 pb-12">
            <div className="flex flex-col gap-8 pb-8 pt-4 w-full min-w-0">
              {messages.map((msg) => (
                <div key={msg.id} className={`flex w-full ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                  {msg.sender === 'bot' && (
                    <div className="w-10 h-10 mr-4 mt-0.5 shrink-0 rounded-full overflow-hidden bg-white dark:bg-white/5 border border-gray-200 dark:border-white/10 flex items-center justify-center shadow-sm">
                         <img src="https://userguide.playagegaming.tech/favicon.ico" alt="Logo" className="w-full h-full object-contain p-1" />
                    </div>
                  )}
                  <div className={`flex flex-col max-w-[85%] md:max-w-[80%] ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}>
                    <div className={`leading-relaxed break-words min-w-0 whitespace-pre-wrap transition-colors
                        ${msg.sender === 'user' 
                          ? 'bg-gray-100 dark:bg-[#2a2a2a] text-gray-900 dark:text-white rounded-[24px] rounded-br-[8px] px-5 py-3.5 shadow-sm border border-gray-200 dark:border-transparent' 
                          : 'bg-transparent text-gray-800 dark:text-[#e5e5e5] rounded-2xl p-0 py-1'
                        }`}
                    >
                      {renderFormattedText(getProcessedText(msg))}

                      {msg.mediaUrls && msg.mediaUrls.length > 0 && (
                        <MediaCarousel mediaUrls={msg.mediaUrls} setSelectedImage={setSelectedImage} />
                      )}

                      {msg.references && msg.references.length > 0 && (
                        <SourceGallery references={msg.references} language={language} />
                      )}

                      {msg.sender === "bot" && msg.followUpQuestions && msg.followUpQuestions.length > 0 && (
                        <div className="mt-8">
                          <p className="font-medium text-gray-900 dark:text-[#e5e5e5] mb-3 select-none">{isTurkish ? 'Daha ileri gitmek isterseniz:' : 'If you want to go further:'}</p>
                          <ul className="list-disc pl-6 space-y-2.5 marker:text-gray-400 dark:marker:text-[#737373]">
                            {msg.followUpQuestions.map((q, i) => (
                              <li key={i} className="text-gray-700 dark:text-[#e5e5e5] pl-1">
                                <button onClick={() => onSendMessage(q)} disabled={isTyping} className="text-left hover:text-blue-600 dark:hover:text-[#3b82f6] transition-colors disabled:opacity-50">
                                  {q}
                                </button>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      
                      {msg.sender === "bot" && (
                        <div className="flex items-center gap-1 mt-6 pt-1 text-gray-500 dark:text-[#737373]">
                          <button onClick={() => navigator.clipboard.writeText(getProcessedText(msg))} className="p-2 hover:bg-gray-100 dark:hover:bg-white/5 rounded-md transition-colors" title={isTurkish ? 'Kopyala' : 'Copy'}>
                            <Copy className="w-[18px] h-[18px]" strokeWidth={1.5} />
                          </button>
                          <button className="p-2 hover:bg-gray-100 dark:hover:bg-white/5 rounded-md transition-colors" title={isTurkish ? 'Beğen' : 'Like'}>
                            <ThumbsUp className="w-[18px] h-[18px]" strokeWidth={1.5} />
                          </button>
                          <button className="p-2 hover:bg-gray-100 dark:hover:bg-white/5 rounded-md transition-colors" title={isTurkish ? 'Beğenme' : 'Dislike'}>
                            <ThumbsDown className="w-[18px] h-[18px]" strokeWidth={1.5} />
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
              
              {isTyping && (
                <div className="flex justify-start w-full gap-4 animate-in fade-in duration-300">
                  <div className="w-9 h-9 shrink-0 rounded-xl flex items-center justify-center bg-red-500/10 border border-red-500/20 shadow-[0_0_15px_rgba(239,68,68,0.1)]">
                    <Dices className="w-5 h-5 text-red-500 animate-dice-shuffle" />
                  </div>
                  <div className="text-gray-500 dark:text-[#a3a3a3] text-sm mt-2.5 font-medium flex gap-1 items-center italic tracking-wide">
                    {isTurkish ? 'Zeka düşünüyor...' : 'Intelligence is thinking...'}
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>
        )}
      </div>

      {(hasMessages || isViewingHistory) && !isViewingHistory && (
        <div className="absolute bottom-0 left-0 right-0 flex flex-col items-center bg-gradient-to-t from-[#f9fafb] via-[#f9fafb] dark:from-black dark:via-black to-transparent pt-12 pb-5 px-4 z-20 pointer-events-none transition-all duration-300 animate-in slide-in-from-bottom-2 fade-in">
          <div className="w-full max-w-[48rem] relative pointer-events-auto px-1 md:px-2">
            <div className="bg-white dark:bg-[#202020] rounded-[24px] border border-gray-200 dark:border-white/10 focus-within:border-gray-300 dark:focus-within:border-white/20 shadow-[0_0_40px_rgba(0,0,0,0.05)] dark:shadow-xl flex flex-col transition-all overflow-hidden w-full relative min-h-[140px]">
              <textarea value={inputValue} onChange={(e) => setInputValue(e.target.value)} onKeyDown={handleKeyDown} placeholder={isTurkish ? "Sorularınızı buraya sorun....." : 'Ask Your Doubts here.....'} className="flex-1 w-full bg-transparent border-none outline-none text-gray-900 dark:text-white placeholder:text-gray-400 dark:placeholder:text-[#6e6e6e] resize-none px-5 py-5 pb-16 h-full min-h-[135px] focus:ring-0 bg-inherit text-inherit" />
              <div className="flex items-center justify-end px-4 py-3 gap-4 w-full absolute bottom-1 right-1">
                {inputValue.trim() && (
                  <button className="text-xs font-medium text-gray-500 dark:text-[#737373] hover:text-gray-700 dark:hover:text-[#a3a3a3] transition-colors hidden sm:block">
                    {isTurkish ? 'İstemi optimize et' : 'Optimize prompt'}
                  </button>
                )}
                
                <button 
                  onClick={() => { if(inputValue.trim() && !isTyping) { onSendMessage(inputValue); setInputValue(''); } }}
                  className={`w-[32px] h-[32px] rounded-full flex items-center justify-center transition-all shrink-0 shadow-sm
                    ${(inputValue.trim() && !isTyping) ? "bg-blue-600 dark:bg-[#3b82f6] text-white hover:bg-blue-700 dark:hover:bg-blue-600 scale-110" : "bg-gray-100 dark:bg-white/5 text-gray-400 dark:text-[#525252] cursor-not-allowed scale-100 opacity-50"}
                  `}
                  disabled={!inputValue.trim() || isTyping}
                >
                  <ArrowUp className="w-[18px] h-[18px]" strokeWidth={2.5} />
                </button>
              </div>
            </div>
            <div className="text-center mt-3.5 mb-1 text-[10px] text-gray-400 dark:text-[#525252] font-[600] tracking-wider uppercase px-4 truncate">
              {isTurkish ? 'Playage AI Studio tarafından geliştirilen sohbet arayüzü.' : 'chat Interface by Playage AI Studio.'}
            </div>
          </div>
        </div>
      )}

      {selectedImage && (
        <div className="fixed inset-0 z-[9999] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-200" onClick={() => setSelectedImage(null)}>
          <button onClick={(e) => { e.stopPropagation(); setSelectedImage(null); }} className="absolute top-6 right-6 p-2 rounded-full bg-white/10 hover:bg-white/20 text-white transition-colors">
            <X className="w-6 h-6" />
          </button>
          <img src={selectedImage} alt="Expanded view" className="max-w-full max-h-[90vh] object-contain rounded-lg shadow-2xl" onClick={(e) => e.stopPropagation()} />
        </div>
      )}

    </div>
  );
}
