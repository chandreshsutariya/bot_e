import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { MessageCircle, X, Send, Mic, ChevronDown, Minimize2 } from 'lucide-react';

interface Message {
  id: string;
  text: string;
  sender: 'user' | 'bot';
  timestamp: Date;
  imageUrl?: string;
}



export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [inputValue, setInputValue] = useState("");
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      text: "Hi! How can I help you with your shopping today?",
      sender: 'bot',
      timestamp: new Date()
    }
  ]);
  const [isTyping, setIsTyping] = useState(false);
  const [fullscreenImage, setFullscreenImage] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (SpeechRecognition) {
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = false;
      recognitionRef.current.interimResults = false;
      recognitionRef.current.lang = 'en-US';

      recognitionRef.current.onstart = () => {
        setIsListening(true);
      };

      recognitionRef.current.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript;
        setInputValue(prev => prev ? `${prev} ${transcript}` : transcript);
      };

      recognitionRef.current.onerror = (event: any) => {
        console.error("Speech recognition error", event.error);
        setIsListening(false);
      };

      recognitionRef.current.onend = () => {
        setIsListening(false);
      };
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

  const handleSendMessage = async (text: string) => {
    if (!text.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      text: text,
      sender: 'user',
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue("");
    setIsTyping(true);

    try {
      const apiResponse = await fetch("http://127.0.0.1:8000/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          Username: "Guest",
          User_preffered_language: "en",
          question: text,
          top_k: 5
        }),
      });

      if (!apiResponse.ok) {
        throw new Error(`HTTP error! status: ${apiResponse.status}`);
      }

      const data = await apiResponse.json();
      
      let responseText = data.Definition;
      
      if (data.Steps && data.Steps.length > 0) {
        responseText += "\n\nSteps:\n" + data.Steps.map((step: string, i: number) => `${i + 1}. ${step}`).join("\n");
      }
      if (data.Tips && data.Tips.length > 0) {
        responseText += "\n\nTips:\n" + data.Tips.map((tip: string) => `• ${tip}`).join("\n");
      }

      // Extract URL from Image_References safely
      const rawImageRef = data.Image_References || "";
      const extractedUrl = rawImageRef.match(/https?:\/\/[^\s]+/) ? rawImageRef.match(/https?:\/\/[^\s]+/)[0] : undefined;

      const botMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: responseText || (data.Image_References && data.Image_References.trim() !== "" ? "" : "I'm sorry, I couldn't understand that."),
        sender: 'bot',
        timestamp: new Date(),
        imageUrl: extractedUrl
      };

      setMessages(prev => [...prev, botMessage]);
    } catch (error) {
      console.error("Error generating response:", error);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: "Sorry, I'm having trouble connecting right now. Please try again later.",
        sender: 'bot',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage(inputValue);
    }
  };

  return (
    <div className="fixed bottom-4 right-4 sm:bottom-6 sm:right-6 z-50 flex flex-col items-end pointer-events-none">
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 sm:static z-50 sm:z-auto w-full h-[100dvh] sm:w-[380px] sm:h-[min(600px,calc(100vh-8rem))] sm:mb-4 bg-white rounded-none sm:rounded-2xl shadow-2xl overflow-hidden flex flex-col pointer-events-auto border border-gray-100 font-sans"
          >
            {/* Header */}
            <div className="bg-[#1E88E5] p-4 flex items-center justify-between text-white shrink-0">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 overflow-hidden shadow-sm">
                  <img src="https://userguide.playagegaming.tech/apple-touch-icon.png" alt="Playage Bot" className="w-full h-full object-cover" />
                </div>
                <div>
                  <h2 className="font-semibold text-lg leading-tight">Playage AI</h2>
                  <p className="text-xs text-blue-100 opacity-90">Always here to help</p>
                </div>
              </div>
              <button 
                onClick={() => setIsOpen(false)}
                className="p-1.5 hover:bg-white/10 rounded-full transition-colors"
              >
                <ChevronDown className="w-5 h-5" />
              </button>
            </div>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-4 bg-white space-y-6">
              {messages.map((msg) => (
                <div key={msg.id} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`flex gap-3 max-w-[85%] ${msg.sender === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                    {msg.sender === 'bot' && (
                      <div className="w-8 h-8 rounded-[12px] bg-gradient-to-tr from-[#34d399] via-[#3b82f6] to-[#8b5cf6] p-[2px] shrink-0 mt-1">
                        <div className="w-full h-full bg-white rounded-[10px] flex items-center justify-center relative overflow-hidden">
                           <img src="https://userguide.playagegaming.tech/apple-touch-icon.png" alt="Playage Bot" className="w-full h-full object-cover" />
                        </div>
                      </div>
                    )}
                    
                    <div className="flex flex-col gap-1">
                      <div 
                        className={`p-3.5 rounded-2xl text-[15px] leading-relaxed shadow-sm whitespace-pre-wrap ${
                          msg.sender === 'user' 
                            ? 'bg-[#1E88E5] text-white rounded-tr-none' 
                            : 'bg-gray-50 text-gray-800 border border-gray-100 rounded-tl-none'
                        }`}
                      >
                        {msg.text}
                        {msg.imageUrl && (
                          <div className={`${msg.text ? 'mt-3' : ''} relative rounded-lg overflow-hidden border border-gray-200 cursor-pointer group`} onClick={() => setFullscreenImage(msg.imageUrl!)}>
                            <img src={msg.imageUrl} alt="Reference" className="w-full h-auto max-h-48 object-cover transition-transform duration-300 group-hover:scale-105" />
                            <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center">
                              <Minimize2 className="w-6 h-6 text-white opacity-0 group-hover:opacity-100 transition-opacity" />
                            </div>
                          </div>
                        )}
                      </div>
                      <span className="text-[11px] text-gray-400 px-1">
                        {msg.sender === 'bot' ? 'AI Assistant · ' : 'You · '}
                        just now
                      </span>
                    </div>
                  </div>
                </div>
              ))}
              
              {isTyping && (
                <div className="flex justify-start">
                  <div className="flex gap-3 max-w-[85%]">
                    <div className="w-8 h-8 rounded-[12px] bg-gradient-to-tr from-[#34d399] via-[#3b82f6] to-[#8b5cf6] p-[2px] shrink-0 mt-1">
                        <div className="w-full h-full bg-white rounded-[10px] flex items-center justify-center relative overflow-hidden">
                           <img src="https://userguide.playagegaming.tech/apple-touch-icon.png" alt="Playage Bot" className="w-full h-full object-cover" />
                        </div>
                    </div>
                    <div className="bg-gray-50 border border-gray-100 p-4 rounded-2xl rounded-tl-none shadow-sm flex items-center gap-1.5">
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>



            {/* Input Area */}
            <div className="p-4 bg-white border-t border-gray-100 shrink-0">
              <div className="relative flex items-center gap-2">
                <div className="flex-1 bg-gray-50 rounded-full border border-gray-200 flex items-center px-4 py-2.5 focus-within:ring-2 focus-within:ring-blue-100 focus-within:border-blue-300 transition-all">
                  <input
                    type="text"
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Send message"
                    className="flex-1 bg-transparent outline-none text-gray-700 placeholder:text-gray-400 text-sm"
                  />
                  <div className="flex items-center gap-2 text-gray-400">
                    <button 
                      onClick={toggleListening}
                      title={isListening ? "Stop recording" : "Start recording"}
                      className={`transition-colors flex items-center justify-center w-8 h-8 rounded-full ${isListening ? 'text-red-500 bg-red-50 hover:bg-red-100' : 'hover:text-gray-600 hover:bg-gray-100'}`}
                    >
                        <Mic className="w-5 h-5" />
                    </button>
                  </div>
                </div>
                <button 
                  onClick={() => handleSendMessage(inputValue)}
                  disabled={!inputValue.trim()}
                  className="p-2.5 rounded-full bg-transparent text-gray-400 hover:text-[#1E88E5] disabled:opacity-50 disabled:hover:text-gray-400 transition-colors"
                >
                  <Send className="w-5 h-5" />
                </button>
              </div>
              <div className="text-center mt-3">
                <p className="text-[10px] text-gray-400 font-medium">Powered by Playage AI</p>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Launcher Button */}
      <motion.button
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        onClick={() => setIsOpen(!isOpen)}
        className="pointer-events-auto w-[68px] h-[68px] rounded-[24px] shadow-xl flex items-center justify-center relative group"
      >
        {/* Gradient Background - Fixed Professional Colors */}
        <div className="absolute inset-0 rounded-[24px] bg-gradient-to-br from-[#3bd9a5] via-[#548cf5] to-[#8e52f5] transition-all duration-300 opacity-90 group-hover:opacity-100" />
        
        {isTyping ? (
            <div className="relative z-10 w-[40px] h-[40px] bg-white rounded-[12px] flex items-center justify-center shadow-lg animate-bounce">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  className="w-7 h-7 text-[#ef4444] animate-[spin_0.8s_linear_infinite]"
                >
                  <rect width="18" height="18" x="3" y="3" rx="4" ry="4" fill="currentColor" />
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
                <img src="https://userguide.playagegaming.tech/apple-touch-icon.png" alt="Playage Bot" className="w-full h-full object-cover" />
            </div>
        )}
      </motion.button>

      {/* Fullscreen Image Modal */}
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

