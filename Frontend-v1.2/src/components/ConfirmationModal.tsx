import { TriangleAlert } from 'lucide-react';

interface ConfirmationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  language: string;
}

export default function ConfirmationModal({ isOpen, onClose, onConfirm, language }: ConfirmationModalProps) {
  if (!isOpen) return null;

  const isTurkish = language === 'Turkish';

  return (
    <div className="fixed inset-0 bg-black/70 z-[200] flex items-center justify-center backdrop-blur-sm p-4 animate-in fade-in duration-300">
      <div className="bg-white dark:bg-[#171717] w-full max-w-[380px] rounded-[24px] shadow-2xl border border-gray-100 dark:border-white/5 overflow-hidden flex flex-col animate-in zoom-in duration-300">
        
        <div className="p-6 pt-8 flex flex-col items-center text-center">
          <div className="mb-5 animate-bounce">
            <TriangleAlert className="w-16 h-16 text-red-500" strokeWidth={2.5} />
          </div>
          
          <h3 className="text-[19px] font-bold text-gray-900 dark:text-white mb-2 leading-tight">
            {isTurkish ? 'Emin misiniz?' : 'Are you sure?'}
          </h3>
          
          <p className="text-[14px] text-gray-500 dark:text-white/50 leading-relaxed px-2">
            {isTurkish 
              ? 'Yeni bir sohbet başlatmak mevcut sohbetinizi geçmişe taşıyacak ve zekanın hafızasını sıfırlayacaktır.' 
              : 'Starting a new chat will move your current conversation to history and reset the Intelligence memory.'}
          </p>
        </div>

        <div className="p-6 pt-2 flex gap-3">
          <button 
            onClick={onConfirm}
            className="flex-1 bg-red-600 hover:bg-red-700 text-white font-bold py-3 px-4 rounded-2xl transition-all shadow-lg shadow-red-600/20 active:scale-[0.98]"
          >
            {isTurkish ? 'EVET' : 'YES'}
          </button>
          <button 
            onClick={onClose}
            className="flex-1 bg-gray-100 dark:bg-white/5 hover:bg-gray-200 dark:hover:bg-white/10 text-gray-700 dark:text-white font-bold py-3 px-4 rounded-2xl border border-gray-200 dark:border-white/5 transition-all active:scale-[0.98]"
          >
            {isTurkish ? 'HAYIR' : 'NO'}
          </button>
        </div>

      </div>
    </div>
  );
}
