import React, { useState, useEffect } from 'react';
import { X, Moon, Sun, Settings, Type, RotateCcw } from 'lucide-react';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  theme: string;
  setTheme: (t: string) => void;
  fontFamily: string;
  setFontFamily: (f: string) => void;
  fontSize: string;
  setFontSize: (s: string) => void;
  language?: string;
}

export default function SettingsModal({
  isOpen, onClose, theme, setTheme, fontFamily, setFontFamily, fontSize, setFontSize, language
}: SettingsModalProps) {
  // Local state for "Pending" changes
  const [tempTheme, setTempTheme] = useState(theme);
  const [tempFontFamily, setTempFontFamily] = useState(fontFamily);
  const [tempFontSize, setTempFontSize] = useState(fontSize);

  // Sync local state when modal opens
  useEffect(() => {
    if (isOpen) {
      setTempTheme(theme);
      setTempFontFamily(fontFamily);
      setTempFontSize(fontSize);
    }
  }, [isOpen, theme, fontFamily, fontSize]);

  if (!isOpen) return null;

  const handleSave = () => {
    setTheme(tempTheme);
    setFontFamily(tempFontFamily);
    setFontSize(tempFontSize);
    onClose();
  };

  const handleReset = () => {
    setTempTheme('dark');
    setTempFontFamily('sans');
    setTempFontSize('text-[15px]');
  };

  const isTurkish = language === 'Turkish';

  return (
    <div className="fixed inset-0 bg-black/60 z-[100] flex items-center justify-center backdrop-blur-md p-2 sm:p-4 animate-in fade-in duration-300">
      <div className="bg-white dark:bg-[#171717] w-full max-w-[min(420px,96vw)] max-h-[min(700px,94vh)] rounded-[24px] shadow-2xl border border-gray-100 dark:border-white/5 overflow-hidden flex flex-col animate-in zoom-in duration-300 transition-colors">
        
        {/* Header */}
        <div className="flex items-center justify-between p-5 md:p-6 pb-2 shrink-0">
          <h2 className="text-[17px] font-semibold text-gray-900 dark:text-white/90 flex items-center gap-2.5">
            <Settings className="w-[18px] h-[18px] text-blue-500 dark:text-blue-400" /> 
            {isTurkish ? 'Arayüz Ayarları' : 'Interface Settings'}
          </h2>
          <button onClick={onClose} className="p-2 -mr-2 text-gray-400 dark:text-white/40 hover:text-gray-900 dark:hover:text-white rounded-full hover:bg-gray-100 dark:hover:bg-white/5 transition-all">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 pt-4 flex flex-col gap-8 overflow-y-auto max-h-[80vh] custom-scrollbar">
          
          {/* Appearance Section */}
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1">
              <label className="text-[11px] font-bold text-gray-400 dark:text-white/40 uppercase tracking-[0.1em]">
                {isTurkish ? 'GÖRÜNÜM' : 'APPEARANCE'}
              </label>
              <p className="text-[13px] text-gray-500 dark:text-white/50 transition-colors">
                {isTurkish ? 'Uygulamanın ekranınızda nasıl görüneceğini seçin.' : 'Choose how the application looks on your screen.'}
              </p>
            </div>
            
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Light Theme Card */}
              <button 
                onClick={() => setTempTheme('light')}
                className={`group flex flex-col gap-3 p-1 rounded-2xl border transition-all text-left outline-none
                  ${tempTheme === 'light' ? 'border-blue-500/50 bg-blue-500/5' : 'border-gray-100 bg-gray-50 dark:border-white/5 dark:bg-white/[0.02] hover:bg-gray-100 dark:hover:bg-white/[0.04]'}
                `}
              >
                <div className="bg-white rounded-xl h-24 flex items-center justify-center overflow-hidden border border-gray-200 dark:border-white/10 relative shadow-sm">
                  <div className="w-12 h-1 bg-gray-100 rounded-full" />
                </div>
                <div className="flex items-center justify-between px-2 pb-2">
                  <span className={`text-sm font-medium ${tempTheme === 'light' ? 'text-blue-500 dark:text-blue-400' : 'text-gray-500 dark:text-white/60'}`}>
                    {isTurkish ? 'Açık' : 'Light'}
                  </span>
                  <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center transition-all 
                    ${tempTheme === 'light' ? 'border-blue-500 bg-blue-500' : 'border-gray-200 dark:border-white/20'}
                  `}>
                    {tempTheme === 'light' && <div className="w-1.5 h-1.5 rounded-full bg-white animate-in zoom-in duration-300" />}
                  </div>
                </div>
              </button>

              {/* Dark Theme Card */}
              <button 
                onClick={() => setTempTheme('dark')}
                className={`group flex flex-col gap-3 p-1 rounded-2xl border transition-all text-left outline-none
                  ${tempTheme === 'dark' ? 'border-blue-500/50 bg-blue-500/5' : 'border-gray-100 bg-gray-50 dark:border-white/5 dark:bg-white/[0.02] hover:bg-gray-100 dark:hover:bg-white/[0.04]'}
                `}
              >
                <div className="bg-[#111111] rounded-xl h-24 flex flex-col gap-2 p-4 justify-start overflow-hidden border border-white/5 shadow-inner">
                   <div className="w-full h-1 bg-white/10 rounded-full" />
                   <div className="w-2/3 h-1 bg-white/5 rounded-full" />
                </div>
                <div className="flex items-center justify-between px-2 pb-2">
                  <span className={`text-sm font-medium ${tempTheme === 'dark' ? 'text-blue-500 dark:text-blue-400' : 'text-gray-500 dark:text-white/60'}`}>
                    {isTurkish ? 'Koyu' : 'Dark'}
                  </span>
                  <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center transition-all 
                    ${tempTheme === 'dark' ? 'border-blue-500 bg-blue-500' : 'border-gray-200 dark:border-white/20'}
                  `}>
                    {tempTheme === 'dark' && <div className="w-1.5 h-1.5 rounded-full bg-white animate-in zoom-in duration-300" />}
                  </div>
                </div>
              </button>
            </div>
          </div>

          <div className="h-px bg-gray-100 dark:bg-white/5 w-full" />

          {/* Typography Section */}
          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-1">
              <label className="text-[11px] font-bold text-gray-400 dark:text-white/40 uppercase tracking-[0.1em]">
                {isTurkish ? 'TİPOGRAFİ' : 'TYPOGRAPHY'}
              </label>
              <p className="text-[13px] text-gray-500 dark:text-white/50">
                {isTurkish ? 'Arayüz için yazı tipi sistemini ve ölçeğini seçin.' : 'Select the font system and scale for the interface.'}
              </p>
            </div>

            {/* Font Style Segmented */}
            <div className="flex flex-col gap-2.5">
              <label className="text-[10px] font-bold text-gray-400/60 dark:text-white/30 uppercase">
                {isTurkish ? 'YAZI TİPİ' : 'FONT STYLE'}
              </label>
              <div className="bg-gray-100 dark:bg-[#111111] p-1 rounded-xl flex border border-gray-200 dark:border-white/5 shadow-inner">
                {['sans', 'serif', 'mono'].map((font) => (
                  <button
                    key={font}
                    onClick={() => setTempFontFamily(font)}
                    className={`flex-1 py-2 text-[13px] font-medium rounded-lg transition-all capitalize
                      ${tempFontFamily === font ? 'bg-white dark:bg-white/10 text-blue-500 dark:text-blue-400 shadow-sm dark:shadow-none' : 'text-gray-500 dark:text-white/40 hover:text-gray-700 dark:hover:text-white/60'}
                    `}
                  >
                    {font}
                  </button>
                ))}
              </div>
            </div>

            {/* Font Size Segmented */}
            <div className="flex flex-col gap-2.5">
              <label className="text-[10px] font-bold text-gray-400/60 dark:text-white/30 uppercase">
                {isTurkish ? 'YAZI BOYUTU' : 'FONT SIZE'}
              </label>
              <div className="bg-gray-100 dark:bg-[#111111] p-1 rounded-xl flex border border-gray-200 dark:border-white/5 shadow-inner">
                {[
                  { id: 'text-sm', label: isTurkish ? 'Küçük' : 'Small' },
                  { id: 'text-[15px]', label: isTurkish ? 'Normal' : 'Normal' },
                  { id: 'text-lg', label: isTurkish ? 'Büyük' : 'Large' }
                ].map((size) => (
                  <button
                    key={size.id}
                    onClick={() => setTempFontSize(size.id)}
                    className={`flex-1 py-2.5 text-[13px] font-medium rounded-lg transition-all
                      ${tempFontSize === size.id ? 'bg-white dark:bg-white/10 text-blue-500 dark:text-blue-400 shadow-sm dark:shadow-none' : 'text-gray-500 dark:text-white/40 hover:text-gray-700 dark:hover:text-white/60'}
                    `}
                  >
                    {size.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

        </div>

        {/* Footer */}
        <div className="p-4 md:p-6 pt-4 flex gap-3 border-t border-gray-100 dark:border-white/5 bg-gray-50/50 dark:bg-white/[0.01] shrink-0">
          <button 
            onClick={handleSave}
            className="flex-1 bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white text-[14px] md:text-[15px] font-semibold py-3 px-4 rounded-2xl shadow-lg shadow-blue-500/20 transition-all flex items-center justify-center whitespace-nowrap"
          >
            {isTurkish ? 'Kaydet' : 'Save Changes'}
          </button>
          <button 
            onClick={handleReset}
            className="flex-1 bg-gray-100 dark:bg-white/5 hover:bg-gray-200 dark:hover:bg-white/10 text-gray-700 dark:text-white/80 hover:text-gray-900 font-semibold py-3 px-4 rounded-2xl border border-gray-200 dark:border-white/5 transition-all flex items-center justify-center gap-2 group whitespace-nowrap"
          >
            <RotateCcw className="w-4 h-4 text-gray-400 dark:text-white/40 group-hover:rotate-[-90deg] transition-transform duration-300" />
            {isTurkish ? 'Sıfırla' : 'Reset'}
          </button>
        </div>

      </div>
    </div>
  );
}
