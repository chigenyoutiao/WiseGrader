import { Fragment, useState, useEffect } from 'react';
import { Dialog, Listbox, Transition } from '@headlessui/react';
import { X, Settings, FileText, Key, Check, ChevronRight, Eye, EyeOff, AlertCircle } from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import { useStore } from '../store';

interface ConfigSidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AI_MODELS = [
  { id: 'deepseek-chat', name: 'DeepSeek Chat' },
  { id: 'deepseek-reasoner', name: 'DeepSeek Reasoner (思考模式)' },
  { id: 'Doubao-Seed-1.6', name: 'Doubao Seed 1.6 (豆包)' },
  { id: 'kimi-k2-thinking', name: 'Kimi K2 Thinking' },
  { id: 'qwen-plus', name: 'Qwen Plus' },
  { id: 'gpt-4o', name: 'GPT-4o' },
  { id: 'o3', name: 'o3 (OpenAI)' },
  { id: 'gemini-1.5-pro', name: 'Gemini 1.5 Pro' },
  { id: 'glm-4', name: 'GLM-4' },
];

const CONFIG_TRANSLATIONS = {
  zh: {
    title: "批改配置",
    model: "AI 模型",
    selectModel: "请选择模型",
    apiKey: "API Key",
    apiKeyPlaceholder: "输入 API Key",
    criteria: "评分标准",
    uploadProcessing: "上传识别中...",
    uploadSuccess: "识别成功！",
    uploadEmpty: "未识别到文字",
    uploadError: "上传失败",
    uploadTip: "拖拽文件到此处或点击上传",
    uploadFormat: "支持 PDF、DOCX、DOC 格式",
    criteriaPlaceholder: "识别的评分标准将显示在这里...",
    feedbackStyle: "反馈风格",
    styleDetailed: "详细",
    styleConcise: "简洁",
    styleEncouraging: "鼓励性",
    styleProfessional: "专业性",
    close: "关闭",
    closeAndSave: "关闭并保存"
  },
  en: {
    title: "AI Configuration",
    model: "AI Model",
    selectModel: "Select Model",
    apiKey: "API Key",
    apiKeyPlaceholder: "Enter API Key",
    criteria: "Grading Criteria",
    uploadProcessing: "Processing...",
    uploadSuccess: "Success!",
    uploadEmpty: "No text found",
    uploadError: "Upload Failed",
    uploadTip: "Drag & drop file or click to upload",
    uploadFormat: "Supports PDF, DOCX, DOC",
    criteriaPlaceholder: "Extracted criteria will appear here...",
    feedbackStyle: "Feedback Style",
    styleDetailed: "Detailed",
    styleConcise: "Concise",
    styleEncouraging: "Encouraging",
    styleProfessional: "Professional",
    close: "Close",
    closeAndSave: "Close and Save"
  }
};

export default function ConfigSidebar({ isOpen, onClose }: ConfigSidebarProps) {
  const [showApiKey, setShowApiKey] = useState(false);
  const {
    selectedModel,
    setSelectedModel,
    apiKey,
    setApiKey,
    criteria,
    setCriteria,
    feedbackStyle,
    setFeedbackStyle,
    uploadCriteriaFile,
    extractCriteria,
    language 
  } = useStore();

  const [uploadStatus, setUploadStatus] = useState<'idle' | 'uploading' | 'success' | 'error' | 'empty'>('idle');
  
  const t = CONFIG_TRANSLATIONS[language];

  // 监听 criteria 变化，确保输入框同步更新
  const [localCriteria, setLocalCriteria] = useState(criteria);
  useEffect(() => {
    setLocalCriteria(criteria);
  }, [criteria]);

  const onDrop = async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;
    const file = acceptedFiles[0];
    
    setUploadStatus('uploading');
    
    try {
      console.log("开始上传文件:", file.name);
      // 1. 上传并等待文本返回
      const extractedText = await uploadCriteriaFile(file);
      console.log("后端返回文字长度:", extractedText?.length);

      if (!extractedText || extractedText.trim().length === 0) {
        setUploadStatus('empty');
        setCriteria(""); // 清空
        setTimeout(() => setUploadStatus('idle'), 3000);
        return;
      }

      // 2. 强制更新本地和全局状态
      setCriteria(extractedText);
      setLocalCriteria(extractedText);
      setUploadStatus('success');
      
      // 3. AI 提炼 (不阻塞 UI)
      extractCriteria(extractedText).catch(e => console.warn("提炼失败:", e));
      
      setTimeout(() => setUploadStatus('idle'), 2000);

    } catch (error) {
      console.error('Failed to upload criteria file:', error);
      setUploadStatus('error');
      setTimeout(() => setUploadStatus('idle'), 3000);
    }
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'application/msword': ['.doc'],
    },
    multiple: false,
  });

  const currentModel = AI_MODELS.find((m) => m.id === selectedModel);

  // 获取上传状态显示的文字和颜色
  const getUploadStatusUI = () => {
    switch (uploadStatus) {
      case 'uploading': return { text: t.uploadProcessing, color: 'text-cyan-600' };
      case 'success': return { text: t.uploadSuccess, color: 'text-emerald-600' };
      case 'empty': return { text: t.uploadEmpty, color: 'text-amber-500' };
      case 'error': return { text: t.uploadError, color: 'text-red-500' };
      default: return { text: t.uploadTip, color: 'text-gray-600 dark:text-gray-400' };
    }
  };

  const statusUI = getUploadStatusUI();

  return (
    <Transition.Root show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-in-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in-out duration-300"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/20 backdrop-blur-sm transition-opacity" />
        </Transition.Child>

        <div className="fixed inset-0 overflow-hidden">
          <div className="absolute inset-0 overflow-hidden">
            <div className="pointer-events-none fixed inset-y-0 right-0 flex max-w-full pl-10">
              <Transition.Child
                as={Fragment}
                enter="transform transition ease-in-out duration-300 sm:duration-500"
                enterFrom="translate-x-full"
                enterTo="translate-x-0"
                leave="transform transition ease-in-out duration-300 sm:duration-500"
                leaveFrom="translate-x-0"
                leaveTo="translate-x-full"
              >
                <Dialog.Panel className="pointer-events-auto w-screen max-w-md">
                  <div className="flex h-full flex-col overflow-y-scroll bg-white dark:bg-gray-900 shadow-xl">
                    
                    {/* Header */}
                    <div className="px-6 py-6 border-b border-gray-100 dark:border-gray-800">
                      <div className="flex items-center justify-between">
                        <Dialog.Title className="text-xl font-bold text-gray-900 dark:text-white flex items-center gap-3">
                          <div className="w-10 h-10 rounded-xl bg-cyan-50 dark:bg-cyan-900/30 flex items-center justify-center text-cyan-600 dark:text-cyan-400">
                            <Settings className="w-6 h-6" />
                          </div>
                          {t.title}
                        </Dialog.Title>
                        <button
                          type="button"
                          className="rounded-md text-gray-400 hover:text-gray-500 focus:outline-none transition-colors"
                          onClick={onClose}
                          title={t.closeAndSave}
                        >
                          <X className="w-6 h-6" />
                        </button>
                      </div>
                    </div>

                    {/* Content */}
                    <div className="flex-1 px-6 py-6 space-y-8">
                      
                      {/* Model Selection */}
                      <div className="space-y-3">
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                          {t.model}
                        </label>
                        <Listbox value={selectedModel} onChange={setSelectedModel}>
                          <div className="relative">
                            <Listbox.Button className="relative w-full cursor-pointer rounded-xl bg-gray-50 dark:bg-gray-800 py-3 pl-4 pr-10 text-left border border-gray-200 dark:border-gray-700 focus:outline-none focus:ring-2 focus:ring-cyan-500 sm:text-sm">
                              <span className="block truncate text-gray-900 dark:text-white font-medium">
                                {currentModel ? currentModel.name : t.selectModel}
                              </span>
                              <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2">
                                <ChevronRight className="h-4 w-4 text-gray-400" />
                              </span>
                            </Listbox.Button>
                            <Transition
                              as={Fragment}
                              leave="transition ease-in duration-100"
                              leaveFrom="opacity-100"
                              leaveTo="opacity-0"
                            >
                              <Listbox.Options className="absolute z-10 mt-2 max-h-60 w-full overflow-auto rounded-xl bg-white dark:bg-gray-800 py-1 text-base shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none sm:text-sm">
                                {AI_MODELS.map((model) => (
                                  <Listbox.Option
                                    key={model.id}
                                    className={({ active }) =>
                                      `relative cursor-pointer select-none py-3 pl-10 pr-4 ${
                                        active ? 'bg-cyan-50 dark:bg-cyan-900/20 text-cyan-900 dark:text-cyan-100' : 'text-gray-900 dark:text-white'
                                      }`
                                    }
                                    value={model.id}
                                  >
                                    {({ selected }) => (
                                      <>
                                        <span className={`block truncate ${selected ? 'font-medium' : 'font-normal'}`}>
                                          {model.name}
                                        </span>
                                        {selected ? (
                                          <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-cyan-600 dark:text-cyan-400">
                                            <Check className="h-4 w-4" aria-hidden="true" />
                                          </span>
                                        ) : null}
                                      </>
                                    )}
                                  </Listbox.Option>
                                ))}
                              </Listbox.Options>
                            </Transition>
                          </div>
                        </Listbox>
                      </div>

                      {/* API Key */}
                      <div className="space-y-3">
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                          {t.apiKey}
                        </label>
                        <div className="relative rounded-md shadow-sm">
                          <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                            <Key className="h-4 w-4 text-gray-400" />
                          </div>
                          <input
                            type={showApiKey ? 'text' : 'password'}
                            value={apiKey}
                            onChange={(e) => setApiKey(e.target.value)}
                            className="block w-full rounded-xl border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 pl-10 pr-10 py-3 text-gray-900 dark:text-white focus:border-cyan-500 focus:ring-cyan-500 sm:text-sm"
                            placeholder={t.apiKeyPlaceholder}
                          />
                          <button
                            type="button"
                            onClick={() => setShowApiKey(!showApiKey)}
                            className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                          >
                            {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                          </button>
                        </div>
                      </div>

                      {/* Criteria */}
                      <div className="space-y-3">
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                          {t.criteria}
                        </label>
                        <div
                          {...getRootProps()}
                          className={`mt-1 flex justify-center rounded-xl border-2 border-dashed px-6 pt-5 pb-6 transition-colors cursor-pointer ${
                            isDragActive
                              ? 'border-cyan-500 bg-cyan-50 dark:bg-cyan-900/10'
                              : 'border-gray-300 dark:border-gray-700 hover:border-cyan-400 hover:bg-gray-50 dark:hover:bg-gray-800'
                          }`}
                        >
                          {/* 🟢 修复 1: 唯一的 input 放在这里 */}
                          <input {...getInputProps()} />
                          
                          <div className="space-y-1 text-center">
                            {uploadStatus === 'error' ? (
                               <AlertCircle className="mx-auto h-12 w-12 text-red-500" />
                            ) : uploadStatus === 'success' ? (
                               <Check className="mx-auto h-12 w-12 text-emerald-500" />
                            ) : (
                               <FileText className="mx-auto h-12 w-12 text-gray-400" />
                            )}
                            
                            <div className="flex text-sm justify-center">
                              {/* 🟢 修复 2: label 改为 span，移除内部多余的 input */}
                              <span className={`relative rounded-md font-medium focus-within:outline-none ${statusUI.color}`}>
                                <span>{statusUI.text}</span>
                              </span>
                            </div>
                            <p className="text-xs text-gray-500 dark:text-gray-500">
                              {t.uploadFormat}
                            </p>
                          </div>
                        </div>
                        
                        <div className="mt-2">
                          <textarea
                            rows={6}
                            value={localCriteria}
                            onChange={(e) => {
                                setLocalCriteria(e.target.value);
                                setCriteria(e.target.value);
                            }}
                            className="block w-full rounded-xl border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 py-3 px-4 text-gray-900 dark:text-white shadow-sm focus:border-cyan-500 focus:ring-cyan-500 sm:text-sm resize-none transition-all"
                            placeholder={t.criteriaPlaceholder}
                          />
                        </div>
                      </div>

                      {/* Feedback Style */}
                      <div className="space-y-3">
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                          {t.feedbackStyle}
                        </label>
                        <select
                          value={feedbackStyle}
                          onChange={(e) => setFeedbackStyle(e.target.value)}
                          className="block w-full rounded-xl border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 py-3 px-4 text-gray-900 dark:text-white shadow-sm focus:border-cyan-500 focus:ring-cyan-500 sm:text-sm"
                        >
                          <option value="detailed">{t.styleDetailed}</option>
                          <option value="concise">{t.styleConcise}</option>
                          <option value="encouraging">{t.styleEncouraging}</option>
                          <option value="professional">{t.styleProfessional}</option>
                        </select>
                      </div>

                    </div>
                  </div>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </div>
      </Dialog>
    </Transition.Root>
  );
}