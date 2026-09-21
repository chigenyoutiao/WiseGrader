import { useState, useRef, useEffect } from 'react';
import { Plus, ChevronLeft, ChevronRight, User, MoreVertical, Trash2, MessageSquare, Moon, Sun, Check } from 'lucide-react';
import { useStore } from '../store';
import LoginModal from './LoginModal';
import AnimatedLogo from './AnimatedLogo'; // 🟢 确保引入了新 Logo

// 1. 定义侧边栏翻译
const SIDEBAR_TRANSLATIONS = {
  zh: {
    appName: "WiseGrader",
    newChat: "开启新对话",
    noHistory: "暂无历史记录",
    last7Days: "最近 7 天",
    last30Days: "最近 30 天",
    older: "更早之前",
    delete: "删除",
    confirmDelete: "确定删除这条记录吗？",
    teacher: "教师",
    loggedIn: "已登录",
    guest: "访客",
    clickLogin: "点击登录",
    appearance: "外观",
    darkMode: "深色模式",
    lightMode: "浅色模式",
    language: "语言",
    zh: "简体中文",
    en: "English"
  },
  en: {
    appName: "WiseGrader",
    newChat: "New Chat",
    noHistory: "No history",
    last7Days: "Previous 7 Days",
    last30Days: "Previous 30 Days",
    older: "Older",
    delete: "Delete",
    confirmDelete: "Delete this conversation?",
    teacher: "Teacher",
    loggedIn: "Logged In",
    guest: "Guest",
    clickLogin: "Login",
    appearance: "Appearance",
    darkMode: "Dark Mode",
    lightMode: "Light Mode",
    language: "Language",
    zh: "简体中文",
    en: "English"
  }
};

export default function Sidebar() {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const {
    startNewConversation,
    isLoggedIn,
    history,
    loadConversation,
    deleteConversation,
    isDarkMode,
    toggleTheme,
    language,
    setLanguage
  } = useStore();

  const t = SIDEBAR_TRANSLATIONS[language];

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setShowUserMenu(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleNewConversation = () => {
    startNewConversation();
  };

  const handleConversationClick = (id: string) => {
    loadConversation(id);
  };

  const handleDeleteConversation = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (confirm(t.confirmDelete)) {
      deleteConversation(id);
    }
  };

  const now = new Date();
  const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  const thirtyDaysAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);

  const conversations7Days = history.filter(
    (conv) => new Date(conv.timestamp) >= sevenDaysAgo
  );

  const conversations30Days = history.filter(
    (conv) => {
      const date = new Date(conv.timestamp);
      return date >= thirtyDaysAgo && date < sevenDaysAgo;
    }
  );

  const conversationsOlder = history.filter(
    (conv) => new Date(conv.timestamp) < thirtyDaysAgo
  );

  if (isCollapsed) {
    return (
      <>
        <div className="w-16 h-screen bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-700 flex flex-col items-center py-4">
          <button onClick={() => setIsCollapsed(false)} className="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors mb-4">
            <ChevronRight className="w-5 h-5 text-gray-600 dark:text-gray-400" />
          </button>
          <button onClick={handleNewConversation} className="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors mb-auto" title={t.newChat}>
            <Plus className="w-5 h-5 text-gray-600 dark:text-gray-400" />
          </button>
          <button onClick={() => setIsLoginModalOpen(true)} className="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors mb-4">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center">
              <User className="w-4 h-4 text-white" />
            </div>
          </button>
          
          {/* 🟢 修复点 1：收起状态下使用新 Logo */}
          <div className="py-2">
            <AnimatedLogo size={42} />
          </div>
        </div>
        <LoginModal isOpen={isLoginModalOpen} onClose={() => setIsLoginModalOpen(false)} />
      </>
    );
  }

  return (
  <div className="w-64 h-screen bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-700 flex flex-col">
      {/* Header */}
      <div className="flex-shrink-0 p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {/* 🟢 修复点 2：展开状态下使用新 Logo */}
          <AnimatedLogo size={32} />
          <span className="text-lg font-semibold text-gray-900 dark:text-white">{t.appName}</span>
        </div>
        <button onClick={() => setIsCollapsed(true)} className="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors">
          <ChevronLeft className="w-4 h-4 text-gray-600 dark:text-gray-400" />
        </button>
      </div>

      {/* New Conversation Button */}
      <div className="flex-shrink-0 p-4">
        <button onClick={handleNewConversation} className="w-full flex items-center justify-center gap-2 px-4 py-2.5 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors text-gray-700 dark:text-gray-300">
          <div className="w-5 h-5 rounded-full border-2 border-gray-400 dark:border-gray-500 flex items-center justify-center">
            <Plus className="w-3 h-3" />
          </div>
          <span className="text-sm font-medium">{t.newChat}</span>
        </button>
      </div>

      {/* Conversations List - 独立滚动区域，底部预留空间给固定的登录区 */}
      <div className="flex-1 overflow-y-auto px-2 pb-24 scrollbar-thin">
        {history.length === 0 && (
          <div className="text-center text-xs text-gray-400 mt-10">
            {t.noHistory}
          </div>
        )}

        {conversations7Days.length > 0 && (
          <div className="mb-4">
            <div className="px-2 py-1.5 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
              {t.last7Days}
            </div>
            <div className="space-y-1">
              {conversations7Days.map((conv) => (
                <div
                  key={conv.id}
                  onClick={() => handleConversationClick(conv.id)}
                  className="group relative w-full text-left px-3 py-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors cursor-pointer flex items-center gap-2"
                >
                  <MessageSquare className="w-4 h-4 text-gray-400" />
                  <div className="text-sm text-gray-700 dark:text-gray-300 line-clamp-1 flex-1 pr-6">
                    {conv.title}
                  </div>
                  <button
                    onClick={(e) => handleDeleteConversation(e, conv.id)}
                    className="absolute right-2 opacity-0 group-hover:opacity-100 p-1 hover:text-red-500 transition-opacity"
                    title={t.delete}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {conversations30Days.length > 0 && (
          <div className="mb-4">
            <div className="px-2 py-1.5 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
              {t.last30Days}
            </div>
            <div className="space-y-1">
              {conversations30Days.map((conv) => (
                <div key={conv.id} onClick={() => handleConversationClick(conv.id)} className="group relative w-full text-left px-3 py-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors cursor-pointer flex items-center gap-2">
                  <MessageSquare className="w-4 h-4 text-gray-400" />
                  <div className="text-sm text-gray-700 dark:text-gray-300 line-clamp-1 flex-1 pr-6">{conv.title}</div>
                  <button onClick={(e) => handleDeleteConversation(e, conv.id)} className="absolute right-2 opacity-0 group-hover:opacity-100 p-1 hover:text-red-500 transition-opacity" title={t.delete}><Trash2 className="w-3.5 h-3.5" /></button>
                </div>
              ))}
            </div>
          </div>
        )}

        {conversationsOlder.length > 0 && (
          <div className="mb-4">
            <div className="px-2 py-1.5 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
              {t.older}
            </div>
            <div className="space-y-1">
              {conversationsOlder.map((conv) => (
                <div key={conv.id} onClick={() => handleConversationClick(conv.id)} className="group relative w-full text-left px-3 py-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors cursor-pointer flex items-center gap-2">
                  <MessageSquare className="w-4 h-4 text-gray-400" />
                  <div className="text-sm text-gray-700 dark:text-gray-300 line-clamp-1 flex-1 pr-6">{conv.title}</div>
                  <button onClick={(e) => handleDeleteConversation(e, conv.id)} className="absolute right-2 opacity-0 group-hover:opacity-100 p-1 hover:text-red-500 transition-opacity" title={t.delete}><Trash2 className="w-3.5 h-3.5" /></button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* User Profile & Menu Area - 永远固定在侧边栏底部可见 */}
      <div className="sticky bottom-0 p-4 border-t border-gray-200 dark:border-gray-700 bg-white/95 dark:bg-gray-900/95 backdrop-blur-sm relative" ref={menuRef}>

        {showUserMenu && (
          <div className="absolute bottom-16 right-4 w-48 bg-white dark:bg-gray-800 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 py-2 z-50 animate-in fade-in slide-in-from-bottom-2 duration-200">
            <div className="px-2 py-1">
              <div className="text-xs font-semibold text-gray-400 dark:text-gray-500 px-2 mb-1">{t.appearance}</div>
              <button onClick={() => { toggleTheme(); setShowUserMenu(false); }} className="w-full flex items-center justify-between px-2 py-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">
                <div className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-200">
                  {isDarkMode ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
                  <span>{isDarkMode ? t.darkMode : t.lightMode}</span>
                </div>
              </button>
            </div>
            <div className="h-px bg-gray-100 dark:bg-gray-700 my-1"></div>
            <div className="px-2 py-1">
              <div className="text-xs font-semibold text-gray-400 dark:text-gray-500 px-2 mb-1">{t.language}</div>
              <button onClick={() => setLanguage('zh')} className={`w-full flex items-center justify-between px-2 py-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors ${language === 'zh' ? 'bg-cyan-50 dark:bg-cyan-900/20' : ''}`}>
                <div className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-200"><span className="w-4 h-4 flex items-center justify-center text-xs font-bold">CN</span><span>{t.zh}</span></div>
                {language === 'zh' && <Check className="w-3.5 h-3.5 text-cyan-600" />}
              </button>
              <button onClick={() => setLanguage('en')} className={`w-full flex items-center justify-between px-2 py-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors ${language === 'en' ? 'bg-cyan-50 dark:bg-cyan-900/20' : ''}`}>
                <div className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-200"><span className="w-4 h-4 flex items-center justify-center text-xs font-bold">EN</span><span>{t.en}</span></div>
                {language === 'en' && <Check className="w-3.5 h-3.5 text-cyan-600" />}
              </button>
            </div>
          </div>
        )}

        <button onClick={() => setIsLoginModalOpen(true)} className="w-full flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors cursor-pointer group">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center flex-shrink-0">
            <User className="w-4 h-4 text-white" />
          </div>
          <div className="flex-1 min-w-0 text-left">
            {isLoggedIn ? (
              <>
                <div className="text-sm font-medium text-gray-900 dark:text-white truncate">{t.teacher}</div>
                <div className="text-xs text-gray-500 dark:text-gray-400 truncate">{t.loggedIn}</div>
              </>
            ) : (
              <>
                <div className="text-sm font-medium text-gray-900 dark:text-white truncate">{t.guest}</div>
                <div className="text-xs text-gray-500 dark:text-gray-400 truncate">{t.clickLogin}</div>
              </>
            )}
          </div>
          <span
            className="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded transition-colors cursor-pointer"
            role="button"
            tabIndex={0}
            onClick={(event) => {
              event.stopPropagation();
              setShowUserMenu(!showUserMenu);
            }}
          >
            <MoreVertical className="w-4 h-4 text-gray-500 dark:text-gray-400" />
          </span>
        </button>
      </div>
      <LoginModal isOpen={isLoginModalOpen} onClose={() => setIsLoginModalOpen(false)} />
    </div>
  );
}