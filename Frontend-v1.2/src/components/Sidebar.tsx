import { useState, useRef, useEffect } from 'react';
import { PanelLeft, Plus, Settings, History, MessageSquare, MoreVertical, Pencil, Trash2, Check, X } from 'lucide-react';
import type { Message } from '../services/api';
import type { ChatSession } from '../App';

interface SidebarProps {
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
  onNewChat: () => void;
  onSettingsClick: () => void;
  language: string;
  history?: ChatSession[];
  viewHistory?: (msgs: Message[]) => void;
  onDeleteHistory?: (id: string) => void;
  onRenameHistory?: (id: string, newTitle: string) => void;
}

export default function Sidebar({ 
  isOpen, setIsOpen, onNewChat, onSettingsClick, language, history = [], viewHistory, onDeleteHistory, onRenameHistory 
}: SidebarProps) {
  const isTurkish = language === 'Turkish';
  const [activeMenu, setActiveMenu] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setActiveMenu(null);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const getChatLabel = (session: ChatSession) => {
    if (session.title) return session.title;
    const firstUserMsg = session.messages.find(m => m.sender === 'user');
    if (firstUserMsg) {
      return firstUserMsg.text.length > 25 ? firstUserMsg.text.substring(0, 25) + '...' : firstUserMsg.text;
    }
    return isTurkish ? 'Önceki Sohbet' : 'Previous Chat';
  };

  const handleStartRename = (session: ChatSession) => {
    setEditingId(session.id);
    setEditValue(session.title || getChatLabel(session));
    setActiveMenu(null);
  };

  const handleSaveRename = (id: string) => {
    if (editValue.trim() && onRenameHistory) {
      onRenameHistory(id, editValue.trim());
    }
    setEditingId(null);
  };

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[45] lg:hidden transition-opacity duration-300"
          onClick={() => setIsOpen(false)}
        />
      )}

      <div className={`fixed lg:relative inset-y-0 left-0 h-full dark:bg-[#171717] bg-white border-r dark:border-white/5 border-gray-100 transition-all duration-300 flex flex-col z-[50] ${isOpen ? 'w-[280px] translate-x-0' : 'w-0 -translate-x-full lg:translate-x-0 overflow-hidden'}`}>
        
        <div className={`flex flex-col h-full w-[280px] ${!isOpen ? 'lg:opacity-0 lg:invisible' : 'opacity-100 visible'} transition-all duration-200 shadow-2xl lg:shadow-none`}>
        
        {/* Header */}
        <div className="p-6 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
             <div className="w-9 h-9 rounded-lg overflow-hidden dark:bg-white/5 bg-gray-100 border dark:border-white/10 border-gray-200 flex items-center justify-center p-1">
               <img src="https://userguide.playagegaming.tech/favicon.ico" alt="Logo" className="w-full h-full object-contain p-1" />
             </div>
             <span className="font-bold text-[17px] dark:text-white/90 text-gray-900 tracking-tight">PlayAge Intelligence</span>
          </div>
          <button onClick={() => setIsOpen(false)} className="p-2 dark:text-white/40 text-gray-400 hover:text-blue-500 dark:hover:text-white transition-colors rounded-lg dark:hover:bg-white/5 hover:bg-gray-100 lg:hidden">
            <PanelLeft className="w-5 h-5" />
          </button>
        </div>

        {/* New Chat Button */}
        <div className="px-4 py-2 shrink-0">
          <button 
            onClick={onNewChat}
            className="w-full flex items-center gap-3 dark:bg-white/[0.03] bg-gray-100/50 hover:bg-gray-100 dark:hover:bg-white/[0.07] dark:text-white/90 text-gray-900 font-semibold py-3 px-4 rounded-xl border dark:border-white/5 border-gray-100 transition-all group active:scale-[0.98]"
          >
            <div className="w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center group-hover:bg-blue-500 group-hover:text-white transition-all">
               <Plus className="w-4 h-4" />
            </div>
            <span className="text-sm font-bold tracking-wide">
              {isTurkish ? 'Yeni Sohbet' : 'New Chat'}
            </span>
          </button>
        </div>

        {/* History Section */}
        <div className="flex-1 overflow-y-auto px-4 py-6 scrollbar-hide flex flex-col gap-8">
          
          <div className="flex flex-col gap-3">
            <div className="px-2 flex items-center gap-2 dark:text-white/20 text-gray-400">
               <History className="w-3.5 h-3.5" />
               <span className="text-[11px] font-bold uppercase tracking-[0.15em]">
                 {isTurkish ? 'GEÇMİŞ' : 'HISTORY'}
               </span>
            </div>
            
            <div className="flex flex-col gap-1">
              {history.length === 0 ? (
                <div className="px-3 py-8 text-center border border-dashed dark:border-white/5 border-gray-200 rounded-2xl flex flex-col items-center gap-2">
                   <MessageSquare className="w-8 h-8 dark:text-white/5 text-gray-100" />
                   <p className="text-[12px] dark:text-white/20 text-gray-400 font-medium">
                     {isTurkish ? 'Henüz geçmiş yok' : 'No history yet'}
                   </p>
                </div>
              ) : (
                history.map((session) => (
                  <div key={session.id} className="relative group/item">
                    {editingId === session.id ? (
                      <div className="flex items-center gap-2 px-3 py-2 dark:bg-white/5 bg-gray-50 rounded-xl border border-blue-500/30">
                        <input 
                          autoFocus
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          onKeyDown={(e) => { if(e.key === 'Enter') handleSaveRename(session.id); if(e.key === 'Escape') setEditingId(null); }}
                          className="flex-1 bg-transparent border-none outline-none text-[13px] dark:text-white text-gray-900 py-1"
                        />
                        <button onClick={() => handleSaveRename(session.id)} className="p-1 hover:text-blue-500">
                          <Check className="w-3.5 h-3.5" />
                        </button>
                        <button onClick={() => setEditingId(null)} className="p-1 hover:text-red-500">
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center">
                        <button
                          onClick={() => viewHistory?.(session.messages)}
                          className="flex-1 text-left px-3 py-3 rounded-xl dark:hover:bg-white/5 hover:bg-gray-100 dark:text-white/50 text-gray-600 dark:hover:text-white/90 hover:text-gray-900 transition-all group flex items-center gap-3 min-w-0"
                        >
                          <MessageSquare className="w-4 h-4 dark:text-white/20 text-gray-300 group-hover:text-blue-500 transition-colors shrink-0" />
                          <span className="text-[13px] font-medium truncate">
                            {getChatLabel(session)}
                          </span>
                        </button>
                        
                        <button 
                          onClick={(e) => { e.stopPropagation(); setActiveMenu(activeMenu === session.id ? null : session.id); }}
                          className={`p-2 transition-all opacity-100 rounded-lg dark:hover:bg-white/10 hover:bg-gray-100 ${activeMenu === session.id ? 'dark:text-white text-gray-900 bg-gray-100 dark:bg-white/10' : 'dark:text-white/40 text-gray-400 hover:text-blue-500'}`}
                        >
                          <MoreVertical className="w-4 h-4" />
                        </button>
                      </div>
                    )}

                    {/* Context Menu */}
                    {activeMenu === session.id && (
                      <div ref={menuRef} className="absolute right-0 top-[80%] w-48 dark:bg-[#212121] bg-white border dark:border-white/5 border-gray-100 rounded-xl shadow-2xl z-50 py-1.5 animate-in fade-in zoom-in duration-200">
                        <button 
                          onClick={() => handleStartRename(session)}
                          className="w-full flex items-center gap-3 px-3.5 py-2.5 dark:hover:bg-white/5 hover:bg-gray-50 dark:text-white/80 text-gray-700 transition-colors text-left group"
                        >
                          <Pencil className="w-4 h-4 dark:text-white/40 text-gray-400 group-hover:text-blue-500 dark:group-hover:text-white" />
                          <span className="text-[13px] font-semibold">{isTurkish ? 'Yeniden adlandır' : 'Rename project'}</span>
                        </button>
                        <div className="h-[1px] dark:bg-white/5 bg-gray-100 my-1 mx-2" />
                        <button 
                          onClick={() => { onDeleteHistory?.(session.id); setActiveMenu(null); }}
                          className="w-full flex items-center gap-3 px-3.5 py-2.5 dark:hover:bg-white/5 hover:bg-red-50 dark:text-red-500/80 text-red-600 hover:text-red-700 transition-colors text-left group"
                        >
                          <Trash2 className="w-4 h-4 opacity-70 group-hover:opacity-100" />
                          <span className="text-[13px] font-semibold">{isTurkish ? 'Projeyi sil' : 'Delete project'}</span>
                        </button>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>

        </div>

        {/* Bottom Actions */}
        <div className="p-4 mt-auto border-t dark:border-white/5 border-gray-100 dark:bg-black/20 bg-gray-50/50">
          <button 
            onClick={onSettingsClick}
            className="w-full flex items-center gap-3.5 dark:text-white/40 text-gray-500 hover:text-blue-600 dark:hover:text-white dark:hover:bg-white/5 hover:bg-white p-3 rounded-xl transition-all group hover:shadow-sm border border-transparent hover:border-gray-100 dark:hover:border-transparent"
          >
            <Settings className="w-5 h-5 group-hover:rotate-90 transition-transform duration-500" />
            <span className="text-sm font-semibold tracking-wide">
              {isTurkish ? 'Ayarlar' : 'Settings'}
            </span>
          </button>
        </div>

      </div>

      </div>
    </>
  );
}
