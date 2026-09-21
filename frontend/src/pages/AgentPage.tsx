import { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { Send, Settings, X, FileText, Paperclip, FileArchive, Loader2, QrCode, Smartphone } from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import { Dialog } from '@headlessui/react';
import { motion, AnimatePresence } from 'framer-motion';
import AutoResizingTextarea from 'react-textarea-autosize';

import WorkflowStep from '../components/agent/WorkflowStep';
import ChatMessage from '../components/agent/ChatMessage';
import MouseFollower from '../components/MouseFollower';
import Sidebar from '../components/Sidebar';
import ConfigSidebar, { AI_MODELS } from '../components/ConfigSidebar';
import { useStore, type MessageOption } from '../store';
import AnimatedLogo from '../components/AnimatedLogo';
import { API_BASE_URL } from '../api';

const TRANSLATIONS = {
  zh: {
    startChat: "WiseGrader",
    startChatDesc: "智能作业批改助手，支持从学习通自动下载与AI批改。",
    inputPlaceholder: "请输入消息....",
    pressEnter: "按 Enter 发送 · Shift + Enter 换行",
    configTip: "请先配置 AI 模型和 API Key",
    aiConfig: "AI 配置",
    configured: "已配置",
    model: "AI 模型",
    selectModel: "请选择模型",
    apiKey: "API Key",
    apiKeyPlaceholder: "输入 API Key",
    criteria: "评分标准",
    uploadProcessing: "上传中...",
    uploadSuccess: "上传成功！",
    uploadTip: "拖拽文件到此处或点击上传",
    uploadFormat: "支持 PDF、DOCX、DOC 格式",
    criteriaPlaceholder: "或直接在此输入评分标准...",
    feedbackStyle: "反馈风格",
    styleDetailed: "详细",
    styleConcise: "简洁",
    styleEncouraging: "鼓励性",
    styleProfessional: "专业性",
    close: "关闭",
    authTitle: "需要身份验证",
    authDesc: "请登录后继续操作。",
    username: "账号",
    usernamePlaceholder: "请输入账号",
    password: "密码",
    passwordPlaceholder: "请输入密码",
    login: "登录",
    loggingIn: "登录中...",
    thinking: "Thinking...",
    defaultWorkflowTitle: "智能批改任务"
  },
  en: {
    startChat: "WiseGrader",
    startChatDesc: "Your AI grading assistant. Auto-download & Grade assignments.",
    inputPlaceholder: "Input....",
    pressEnter: "Press Enter to send · Shift + Enter for new line",
    configTip: "Please configure AI Model and API Key first",
    aiConfig: "AI Config",
    configured: "Configured",
    model: "AI Model",
    selectModel: "Select Model",
    apiKey: "API Key",
    apiKeyPlaceholder: "Enter API Key",
    criteria: "Grading Criteria",
    uploadProcessing: "Uploading...",
    uploadSuccess: "Success!",
    uploadTip: "Drag & drop or click to upload",
    uploadFormat: "Supports PDF, DOCX, DOC",
    criteriaPlaceholder: "Or paste criteria text here...",
    feedbackStyle: "Feedback Style",
    styleDetailed: "Detailed",
    styleConcise: "Concise",
    styleEncouraging: "Encouraging",
    styleProfessional: "Professional",
    close: "Close",
    authTitle: "Authentication Required",
    authDesc: "Please login to continue.",
    username: "Username",
    usernamePlaceholder: "Enter username",
    password: "Password",
    passwordPlaceholder: "Enter password",
    login: "Login",
    loggingIn: "Logging in...",
    thinking: "Thinking...",
    defaultWorkflowTitle: "AI Grading Task"
  }
};

export default function AgentPage() {
  const [inputMessage, setInputMessage] = useState('');
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isConfigSidebarOpen, setIsConfigSidebarOpen] = useState(false);
  const [showConfigTip, setShowConfigTip] = useState(false);
  const [isFocused, setIsFocused] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  const {
    xxtState,
    messages,
    isAgentLoading,
    sendMessage,
    handleOptionSelect,
    selectedModel,
    apiKey,
    executionSteps,
    login,
    isLoginModalOpen,
    setLoginModalOpen,
    language,
    uploadJob,
  } = useStore();

  const t = TRANSLATIONS[language];

  // 🟢 调试：打印 xxtState 的变化
  useEffect(() => {
    if (xxtState?.stage === 'waiting_login') {
      console.log('[AgentPage] waiting_login 状态:', {
        stage: xxtState.stage,
        qrImage: xxtState.qrImage,
        message: xxtState.message,
        fullState: xxtState
      });
    }
  }, [xxtState]);

  const [loginUsername, setLoginUsername] = useState('teacher');
  const [loginPassword, setLoginPassword] = useState('');
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [loginErrorMsg, setLoginErrorMsg] = useState<string | null>(null);
  const [chatFiles, setChatFiles] = useState<Array<{ id: string; file: File; name: string; size: number }>>([]);

  // 🟢 控制“是否需要自动滚动到底部”，避免和用户主动滚动冲突
  const [shouldAutoScroll, setShouldAutoScroll] = useState(true);

  const scrollToBottom = (behavior: ScrollBehavior = 'smooth') => {
    if (!messagesEndRef.current) return;
    messagesEndRef.current.scrollIntoView({ behavior, block: 'nearest' });
  };

  // 当消息变更时，仅在用户本来就在底部（shouldAutoScroll=true）时才自动滚动
  useEffect(() => {
    if (shouldAutoScroll) {
      scrollToBottom('smooth');
    }
  }, [messages, executionSteps, shouldAutoScroll]);

  const isConfigured = Boolean(selectedModel && apiKey);

  const handleSendMessage = async () => {
    if ((!inputMessage.trim() && chatFiles.length === 0) || isAgentLoading) return;

    if (!isConfigured) {
      setShowConfigTip(true);
      setIsConfigSidebarOpen(true);
      setTimeout(() => setShowConfigTip(false), 3000);
      return;
    }

    const content = inputMessage.trim() || '';
    const filesToSend = chatFiles.map(f => f.file);

    setInputMessage('');
    setChatFiles([]);

    try {
      await sendMessage(content, filesToSend);
    } catch (error) {
      console.error('Failed to send message:', error);
    }
  };

  const onOptionSelect = async (option: MessageOption) => {
    try {
      await handleOptionSelect(option);
    } catch (error) {
      console.error('Failed to handle option:', error);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // 文件上传处理 (聊天框)
  const handleChatFileUpload = useCallback(async (acceptedFiles: File[]) => {
    if (!acceptedFiles || acceptedFiles.length === 0) return;

    setChatFiles(prev => {
      const currentHasZip = prev.some(f => f.name.toLowerCase().endsWith('.zip'));
      const incomingHasZip = acceptedFiles.some(f => f.name.toLowerCase().endsWith('.zip'));

      if (currentHasZip) {
        alert("一次只能上传一个 ZIP 作业包，且不能与其他文档混传。");
        return prev;
      }

      if (incomingHasZip) {
        if (acceptedFiles.length > 1 || prev.length > 0) {
          alert("ZIP 作业包必须单独上传，请先清空其他文件。");
          return prev;
        }
      }

      const remainingSlots = 2 - prev.length;
      if (remainingSlots <= 0) {
        alert("最多只能上传 2 个文档");
        return prev;
      }

      const filesToAdd = acceptedFiles.slice(0, remainingSlots);
      const newFileItems = filesToAdd.map((file, index) => ({
        id: `file-${Date.now()}-${index}`,
        file: file,
        name: file.name,
        size: file.size,
      }));

      if (acceptedFiles.length > remainingSlots) {
        alert(`最多只能上传 2 个文件，已添加 ${remainingSlots} 个`);
      }

      return [...prev, ...newFileItems];
    });

    const zipFile = acceptedFiles.find(f => f.name.toLowerCase().endsWith('.zip'));
    if (zipFile && acceptedFiles.length === 1) {
      try {
        await uploadJob(zipFile);
      } catch (error) {
        console.error("上传失败:", error);
        setChatFiles(prev => prev.filter(f => f.file !== zipFile));
        alert("ZIP 上传失败，请检查网络。");
      }
    }
  }, [uploadJob]);

  // Dropzone Hook - 🟢 关键修复：解构出 open 方法
  const { getRootProps, getInputProps, open } = useDropzone({
    onDrop: handleChatFileUpload,
    noClick: true, // 禁用默认点击
    noKeyboard: true,
    multiple: true
  });

  const handleRemoveFile = useCallback((fileId: string) => {
    setChatFiles(prev => prev.filter(f => f.id !== fileId));
  }, []);

  const handleLoginSubmit = async (event?: React.FormEvent) => {
    event?.preventDefault();
    if (isLoggingIn) return;
    setIsLoggingIn(true);
    setLoginErrorMsg(null);
    try {
      await login(loginUsername.trim(), loginPassword);
      setLoginModalOpen(false);
      setLoginPassword('');
    } catch (error) {
      const message = (error as any)?.response?.data?.error || (error as Error)?.message || '登录失败';
      setLoginErrorMsg(message);
    } finally {
      setIsLoggingIn(false);
    }
  };

  const uniqueMessages = useMemo(
    () => messages.filter((message, index, self) => index === self.findIndex((m) => m.id === message.id)),
    [messages]
  );

  const hasExecutionSteps = Array.isArray(executionSteps) && executionSteps.length > 0;

  const isInitialState = !hasExecutionSteps && (
    uniqueMessages.length === 0 ||
    (uniqueMessages.length === 1 && uniqueMessages[0].type === 'agent' && uniqueMessages[0].id === '1')
  );

  const workflowAnchorId = useMemo(() => {
    if (!hasExecutionSteps) return null;
    for (let i = uniqueMessages.length - 1; i >= 0; i--) {
      const msg = uniqueMessages[i];
      if (msg.content.includes('Excel') || msg.content.includes('表格')) continue;
      if ((msg.type === 'system' || msg.type === 'agent') && (
        msg.content.includes('已识别') ||
        msg.content.includes('正在启动') ||
        msg.content.includes('开始下载') ||
        msg.content.includes('Identified') ||
        msg.content.includes('Starting')
      )) {
        return msg.id;
      }
    }
    return null;
  }, [uniqueMessages, hasExecutionSteps]);

  const derivedWorkflowSteps = useMemo(() => {
    if (!hasExecutionSteps) return [];
    let workflowTitle = t.defaultWorkflowTitle;
    let triggerSystemMsgIndex = -1;

    for (let i = uniqueMessages.length - 1; i >= 0; i--) {
      if (uniqueMessages[i].id === workflowAnchorId) {
        triggerSystemMsgIndex = i;
        break;
      }
    }

    if (triggerSystemMsgIndex > 0) {
      for (let i = triggerSystemMsgIndex - 1; i >= 0; i--) {
        if (uniqueMessages[i].type === 'user') {
          workflowTitle = uniqueMessages[i].content;
          break;
        }
      }
    }

    const displayTitle = workflowTitle.length > 20
      ? workflowTitle.substring(0, 20) + '...'
      : workflowTitle;

    const gradingMessages = uniqueMessages.filter(m => m.gradingResults && m.gradingResults.length > 0);
    const isAllCompleted = executionSteps.every(s => s.status === 'completed');

    return [
      {
        id: 'step-main-workflow',
        title: displayTitle,
        messages: gradingMessages,
        isCompleted: isAllCompleted,
      },
    ];
  }, [uniqueMessages, hasExecutionSteps, executionSteps, workflowAnchorId, t]);

  const renderInputArea = useCallback((centered: boolean = false) => (
    <div className={`relative ${centered ? 'w-full max-w-2xl' : 'w-full max-w-4xl mx-auto'}`}>
      {showConfigTip && (
        <div className={`absolute left-0 right-0 flex justify-center z-30 ${centered ? '-top-12' : 'bottom-full mb-2'}`}>
          <div className="bg-amber-500 text-white px-4 py-2 rounded-lg text-sm shadow-lg animate-fade-in-down">
            {t.configTip}
          </div>
        </div>
      )}

      {/* 🟢 主输入容器 */}
      <div
        className={`relative flex flex-col border rounded-2xl bg-white dark:bg-gray-800 shadow-sm transition-all ${isFocused
            ? 'border-cyan-500 dark:border-cyan-400 ring-1 ring-cyan-500/20 shadow-md'
            : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
          } ${centered ? 'shadow-xl border-gray-300 dark:border-gray-600' : ''}`}
      >

        {/* 文件列表 (内嵌) */}
        {chatFiles.length > 0 && (
          <div className="flex gap-2 p-3 border-b border-gray-100 dark:border-gray-700 overflow-x-auto scrollbar-none">
            <AnimatePresence>
              {chatFiles.map((fileItem) => (
                <motion.div
                  key={fileItem.id}
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  className="relative group flex-shrink-0"
                >
                  <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-50 dark:bg-gray-700/50 rounded-lg border border-gray-200 dark:border-gray-600 pr-8">
                    <div className={`p-1 rounded ${fileItem.name.toLowerCase().endsWith('.zip')
                        ? 'bg-yellow-100 text-yellow-600 dark:bg-yellow-900/30 dark:text-yellow-400'
                        : 'bg-cyan-100 text-cyan-600 dark:bg-cyan-900/30 dark:text-cyan-400'
                      }`}>
                      {fileItem.name.toLowerCase().endsWith('.zip') ? <FileArchive className="w-3.5 h-3.5" /> : <FileText className="w-3.5 h-3.5" />}
                    </div>
                    <span className="text-xs font-medium text-gray-700 dark:text-gray-200 truncate max-w-[120px]">
                      {fileItem.name}
                    </span>
                  </div>
                  <button
                    onClick={() => handleRemoveFile(fileItem.id)}
                    className="absolute -top-1 -right-1 w-5 h-5 bg-gray-400 hover:bg-red-500 text-white rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity shadow-sm"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}

        {/* 2. 输入框和按钮区域 */}
        <div className="flex items-end pl-2 pr-2 py-2">
          {/* 🟢 修复：添加 !border-0 !ring-0 !outline-none 强制去掉白框 */}
          <AutoResizingTextarea
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            placeholder={chatFiles.length > 0 ? "输入消息..." : t.inputPlaceholder}
            disabled={isAgentLoading}
            className="flex-1 max-h-[200px] py-2.5 px-3 text-base text-gray-900 dark:text-white bg-transparent !border-0 !ring-0 !outline-none !shadow-none placeholder:text-gray-400 resize-none leading-6 focus:ring-0 focus:outline-none"
            autoFocus={!centered}
          />

          <div className="flex items-center gap-1 pb-1.5 pl-2">
            {/* 上传按钮 */}
            <div {...getRootProps()}>
              <input {...getInputProps()} />
              <button
                type="button"
                onClick={open} // 🟢 关键修复：绑定 open 方法！
                disabled={isAgentLoading || chatFiles.length >= 2}
                className={`p-2 rounded-xl transition-all ${chatFiles.length > 0
                    ? 'bg-cyan-50 text-cyan-600 dark:bg-cyan-900/20 dark:text-cyan-400'
                    : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 dark:hover:text-gray-300'
                  } ${chatFiles.length >= 2 ? 'opacity-50 cursor-not-allowed' : ''}`}
                title="上传文件"
              >
                <Paperclip className="w-5 h-5" />
              </button>
            </div>

            {/* 设置按钮 */}
            <button
              onClick={() => setIsConfigSidebarOpen(true)}
              className={`rounded-xl transition-all flex items-center gap-1.5 ${isConfigured
                  ? 'px-3 py-2 text-cyan-600 dark:text-cyan-400 hover:bg-cyan-50 dark:hover:bg-cyan-900/20 bg-cyan-50/50 dark:bg-cyan-900/10'
                  : 'p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                }`}
              title={isConfigured ? (AI_MODELS.find(m => m.id === selectedModel)?.name || "AI 配置") : "AI 配置"}
            >
              {isConfigured ? (
                <span className="text-xs font-medium whitespace-nowrap max-w-[100px] truncate">
                  {AI_MODELS.find(m => m.id === selectedModel)?.name || selectedModel}
                </span>
              ) : (
                <Settings className="w-5 h-5 flex-shrink-0" />
              )}
            </button>

            {/* 发送按钮 */}
            <button
              onClick={handleSendMessage}
              disabled={(!inputMessage.trim() && chatFiles.length === 0) || isAgentLoading}
              className={`p-2 rounded-xl flex items-center justify-center transition-all ml-1 ${(inputMessage.trim() || chatFiles.length > 0) && !isAgentLoading
                  ? 'bg-cyan-600 text-white shadow-md hover:bg-cyan-500 hover:scale-105 active:scale-95'
                  : 'bg-gray-100 text-gray-400 dark:bg-gray-800 dark:text-gray-600 cursor-not-allowed'
                }`}
            >
              {isAgentLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* 底部提示 */}
      <p className="text-center text-xs text-gray-400 dark:text-gray-500 mt-3">
        {t.pressEnter}
      </p>
    </div>
  ), [inputMessage, isConfigured, chatFiles, isFocused, isAgentLoading, t, handleSendMessage, handleRemoveFile, getRootProps, getInputProps, setIsConfigSidebarOpen, open]);

  return (
    <div className="h-screen flex bg-gradient-to-b from-gray-50 to-white dark:from-gray-900 dark:to-gray-800 text-gray-800 dark:text-gray-100 overflow-hidden relative">
      <MouseFollower />

      {/* 固定在左侧的侧边栏，与中间聊天区解耦 */}
      <div className="fixed inset-y-0 left-0 z-30">
        <Sidebar />
      </div>

      {/* 右侧主内容区整体右移，避免被侧边栏遮挡 */}
      <div className="flex-1 flex flex-col h-full relative ml-64">
        {isInitialState ? (
          <div className="flex-1 flex flex-col items-center justify-center px-4 pb-20">
            <div className="text-center mb-10 animate-in fade-in zoom-in duration-500">
              <div className="mb-8 mx-auto flex justify-center items-center">
                <AnimatedLogo size={100} className="filter drop-shadow-xl" />
              </div>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-3 tracking-tight">
                {t.startChat}
              </h1>
              <p className="text-gray-500 dark:text-gray-400 text-lg max-w-md mx-auto leading-relaxed">
                {t.startChatDesc}
              </p>
            </div>
            {renderInputArea(true)}
          </div>
        ) : (
          <>
            <main
              ref={messagesContainerRef}
              className="flex-1 overflow-y-auto px-4 py-8 relative z-10 scrollbar-thin"
              onScroll={() => {
                const container = messagesContainerRef.current;
                if (!container) return;
                const threshold = 80; // 离底部 80px 以内认为在底部
                const distanceToBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
                setShouldAutoScroll(distanceToBottom < threshold);
              }}
            >
              {/* 预留足够空间，防止底部固定输入框遮挡最后几条消息 */}
              <div className="max-w-3xl mx-auto space-y-6 pb-40">
                <div className="space-y-6">
                  {uniqueMessages.map((message) => {
                    if (message.id === '1' && message.type === 'agent') return null;
                    if (hasExecutionSteps && message.gradingResults && message.gradingResults.length > 0) {
                      const isInWorkflowStep = derivedWorkflowSteps.some(step =>
                        step.messages.some(m => m.id === message.id)
                      );
                      if (isInWorkflowStep) return null;
                    }
                    const isAnchor = message.id === workflowAnchorId;

                    return (
                      <div key={message.id}>
                        <ChatMessage
                          message={message}
                          onOptionSelect={onOptionSelect}
                          isAgentLoading={false}
                        />
                        {isAnchor && hasExecutionSteps && derivedWorkflowSteps.length > 0 && (
                          <div className="mt-4 mb-6">
                            {derivedWorkflowSteps.map((step) => (
                              <WorkflowStep
                                key={step.id}
                                stepId={step.id}
                                title={step.title}
                                messages={step.messages}
                                onOptionSelect={onOptionSelect}
                                isAgentLoading={isAgentLoading}
                                isCompleted={step.isCompleted}
                                defaultExpanded={true}
                                isActive={true}
                              />
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}

                  {isAgentLoading && (
                    <div className="flex items-start gap-3 p-4 bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 shadow-sm w-fit">
                      <div className="flex-shrink-0">
                        <AnimatedLogo size={32} />
                      </div>
                      <div className="flex-1 pt-1.5">
                        <div className="flex items-center gap-1.5">
                          <div className="w-2 h-2 bg-cyan-500 rounded-full animate-bounce"></div>
                          <div className="w-2 h-2 bg-cyan-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                          <div className="w-2 h-2 bg-cyan-500 rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></div>
                          <span className="text-sm text-gray-500 dark:text-gray-400 ml-2 font-medium">{t.thinking}</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
                <div ref={messagesEndRef} />
              </div>
            </main>

            <div className="fixed bottom-0 left-0 right-0 bg-gradient-to-t from-white via-white to-transparent dark:from-gray-900 dark:via-gray-900 pb-6 pt-10 px-4 md:px-8 z-20 pointer-events-none">
              <div className="pointer-events-auto">
                {renderInputArea(false)}
              </div>
            </div>
          </>
        )}

        <ConfigSidebar isOpen={isConfigSidebarOpen} onClose={() => setIsConfigSidebarOpen(false)} />
        <Dialog open={isLoginModalOpen} onClose={() => setLoginModalOpen(false)} className="relative z-[9999]">
          <div className="fixed inset-0 bg-black/40 backdrop-blur-sm" aria-hidden="true" />
          <div className="fixed inset-0 flex items-center justify-center px-4">
            <Dialog.Panel className="w-full max-w-md bg-white dark:bg-gray-900 rounded-2xl shadow-2xl border border-slate-100 dark:border-gray-800 p-6 space-y-6">
              <div>
                <Dialog.Title className="text-xl font-semibold text-gray-900 dark:text-white">
                  {t.authTitle}
                </Dialog.Title>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  {t.authDesc}
                </p>
              </div>
              <form className="space-y-4" onSubmit={handleLoginSubmit}>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t.username}</label>
                  <input
                    type="text"
                    value={loginUsername}
                    onChange={(e) => setLoginUsername(e.target.value)}
                    className="w-full px-4 py-2.5 rounded-xl bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700"
                    placeholder={t.usernamePlaceholder}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t.password}</label>
                  <input
                    type="password"
                    value={loginPassword}
                    onChange={(e) => setLoginPassword(e.target.value)}
                    className="w-full px-4 py-2.5 rounded-xl bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700"
                    placeholder={t.passwordPlaceholder}
                  />
                </div>
                {loginErrorMsg && <p className="text-sm text-red-600">{loginErrorMsg}</p>}
                <button
                  type="submit"
                  disabled={isLoggingIn}
                  className="w-full py-2.5 rounded-xl bg-cyan-600 hover:bg-cyan-700 text-white font-semibold"
                >
                  {isLoggingIn ? t.loggingIn : t.login}
                </button>
              </form>
            </Dialog.Panel>
          </div>
        </Dialog>

        <Dialog open={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} className="relative z-50">
        </Dialog>
     
        {/* --- 学习通二维码扫码对话框 (XXT QR Code Dialog) --- */}
        <AnimatePresence>
          {/* 🟢 修改：即使 qrImage 暂时为空也显示对话框，显示加载状态 */}
          {xxtState?.stage === 'waiting_login' && (
            <Dialog
              open={true}
              onClose={() => { }} // 禁用关闭，直到登录成功
              className="relative z-50"
            >
              {/* 背景遮罩 */}
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="fixed inset-0 bg-black/50"
                aria-hidden="true"
              />

              {/* 对话框主体 */}
              <div className="fixed inset-0 flex items-center justify-center p-4 z-50">
                <motion.div
                  initial={{ opacity: 0, scale: 0.95, y: 20 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95, y: 20 }}
                  transition={{ duration: 0.2, ease: "easeOut" }}
                >
                  <Dialog.Panel className="w-full max-w-md rounded-3xl bg-gradient-to-br from-white to-gray-50 dark:from-gray-800 dark:to-gray-900 p-8 shadow-2xl border border-gray-200/50 dark:border-gray-700/50 backdrop-blur-sm">
                    {/* 顶部图标和标题区域 */}
                    <div className="flex flex-col items-center mb-6">
                      <div className="relative mb-4">
                        {/* 背景装饰圆圈 */}
                        <div className="absolute inset-0 bg-gradient-to-br from-blue-500/20 to-purple-500/20 rounded-full blur-xl"></div>
                        <div className="relative bg-gradient-to-br from-blue-500 to-purple-600 p-4 rounded-2xl shadow-lg">
                          <QrCode className="w-8 h-8 text-white" />
                        </div>
                      </div>
                      <h3 className="text-2xl font-bold bg-gradient-to-r from-gray-900 to-gray-700 dark:from-white dark:to-gray-300 bg-clip-text text-transparent mb-2">
                        扫描登录学习通
                      </h3>
                      <p className="text-sm text-gray-500 dark:text-gray-400 flex items-center gap-1.5">
                        <Smartphone className="w-4 h-4" />
                        请使用学习通 APP 扫描二维码
                      </p>
                    </div>

                    {/* 二维码容器 - 更精美的设计 */}
                    <div className="relative mx-auto mb-6">
                      {/* 外层装饰边框 */}
                      <div className="absolute -inset-1 bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 rounded-2xl opacity-20 blur-sm"></div>
                      <div className="relative bg-white dark:bg-gray-800 p-4 rounded-2xl shadow-inner border-2 border-gray-100 dark:border-gray-700">
                        {/* 四个角的装饰 */}
                        <div className="absolute top-0 left-0 w-6 h-6 border-t-2 border-l-2 border-blue-500 rounded-tl-lg"></div>
                        <div className="absolute top-0 right-0 w-6 h-6 border-t-2 border-r-2 border-blue-500 rounded-tr-lg"></div>
                        <div className="absolute bottom-0 left-0 w-6 h-6 border-b-2 border-l-2 border-blue-500 rounded-bl-lg"></div>
                        <div className="absolute bottom-0 right-0 w-6 h-6 border-b-2 border-r-2 border-blue-500 rounded-br-lg"></div>
                        
                        {/* 二维码图片 */}
                        <div className="relative w-56 h-56 mx-auto flex items-center justify-center">
                          {xxtState.qrImage ? (
                            <img
                              src={`${API_BASE_URL}/api/xxt/image/${xxtState.qrImage}?t=${Date.now()}`}
                              alt="Login QR Code"
                              className="w-full h-full object-contain rounded-lg"
                              onError={(e) => {
                                console.error('[AgentPage] 二维码图片加载失败:', xxtState.qrImage);
                                console.error('[AgentPage] 请求 URL:', (e.target as HTMLImageElement).src);
                                setTimeout(() => {
                                  const target = e.target as HTMLImageElement;
                                  if (xxtState.qrImage) {
                                    target.src = `${API_BASE_URL}/api/xxt/image/${xxtState.qrImage}?retry=${Date.now()}`;
                                  }
                                }, 1000);
                              }}
                              onLoad={() => {
                                console.log('[AgentPage] 二维码图片加载成功:', xxtState.qrImage);
                              }}
                            />
                          ) : (
                            <div className="flex flex-col items-center justify-center space-y-3">
                              <Loader2 className="w-10 h-10 animate-spin text-blue-500" />
                              <p className="text-sm text-gray-500 dark:text-gray-400 font-medium">正在生成二维码...</p>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* 状态提示 - 更精美的样式 */}
                    <div className="flex items-center justify-center gap-2 px-4 py-3 bg-blue-50 dark:bg-blue-900/20 rounded-xl border border-blue-100 dark:border-blue-800/50">
                      <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
                      <p className="text-sm font-semibold text-blue-600 dark:text-blue-400">
                        {xxtState.message || "等待您扫码中..."}
                      </p>
                    </div>

                    {/* 底部提示文字 */}
                    <p className="mt-4 text-xs text-gray-400 dark:text-gray-500 text-center">
                      二维码每 2 秒自动刷新，确保最新有效
                    </p>
                  </Dialog.Panel>
                </motion.div>
              </div>
            </Dialog>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}