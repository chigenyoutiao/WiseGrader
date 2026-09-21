import { useState } from 'react';
import { Bot, User, FileText, FileSpreadsheet, Download, Loader2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown'; // 🟢 引入 Markdown 组件
import remarkGfm from 'remark-gfm';         // 🟢 引入高级语法插件
import type { Message, MessageOption } from '../../store';
import { useStore } from '../../store';
import ProgressPanel from './ProgressPanel';
import GradingResults from './GradingResults';
import FillScoreProgress from './FillScoreProgress'; // 🟢 新增：回填进度组件
import AnimatedLogo from '../AnimatedLogo';

interface ChatMessageProps {
  message: Message;
  onOptionSelect: (option: MessageOption) => void;
  isAgentLoading?: boolean;
}

export default function ChatMessage({ message, onOptionSelect, isAgentLoading = false }: ChatMessageProps) {
  const isUser = message.type === 'user';
  const isSystem = message.type === 'system';
  
  const exportResults = useStore(state => state.exportResults);
  const jobId = useStore(state => state.jobId);
  const batchJobs = useStore(state => state.batchJobs);
  const storeResults = useStore(state => state.jobResults);
  const xxtState = useStore(state => state.xxtState); // 🟢 新增：获取回填状态
  const currentFillScoreMessageId = useStore(state => state.currentFillScoreMessageId); // 🟢 新增：获取当前回填消息ID
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const step4Completed = (message.executionSteps || []).some(
    step => step.id === '4' && step.status === 'completed'
  );
  const hasMessageResults = !!(message.gradingResults && message.gradingResults.length > 0);
  const hasStoreResults = storeResults.length > 0;
  // 🟢 修复：确保任务完成后能显示结果（即使消息中没有结果）
  // 如果消息中有结果，或者步骤4完成且store中有结果，或者消息内容包含"批改完成"且store中有结果
  const shouldShowResults = hasMessageResults || (step4Completed && hasStoreResults) || (message.content?.includes('批改完成') && hasStoreResults);

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  const handleDownload = async (jobId: string, _fileName: string) => {
    if (downloadingId) return;
    setDownloadingId(jobId);
    try {
      await exportResults(jobId);
    } catch (e) {
      console.error(e);
      alert("下载失败，请重试");
    } finally {
      setDownloadingId(null);
    }
  };

  return (
    <div 
      data-message-id={message.id}
      className={`flex items-start gap-3 ${isUser ? 'flex-row-reverse' : ''} animate-in fade-in slide-in-from-bottom-2 duration-300`}
    >
      
      {/* 1. 头像区域 */}
      {!isUser && (
        <div className={`flex-shrink-0 flex items-center justify-center ${
          isSystem 
            ? 'w-8 h-8 rounded-lg bg-slate-200 dark:bg-gray-600 shadow-sm' 
            : '' 
        }`}>
          {isSystem ? (
            <Bot className="w-4 h-4 text-gray-500 dark:text-gray-300" />
          ) : (
            <AnimatedLogo size={38} />
          )}
        </div>
      )}

      {isUser && (
        <div className="w-8 h-8 rounded-lg bg-slate-200 dark:bg-gray-600 flex items-center justify-center flex-shrink-0">
          <User className="w-4 h-4 text-slate-500 dark:text-gray-300" />
        </div>
      )}

      {/* 2. 消息气泡区域 */}
      <div className={`flex-1 max-w-[90%] ${isUser ? 'flex flex-col items-end' : ''}`}>
        <div
          className={`px-4 py-3 shadow-md ${
            isUser
              ? 'bg-cyan-600 text-white rounded-2xl rounded-tr-sm shadow-cyan-600/10'
              : isSystem && message.content?.includes('回填')
              ? 'bg-white dark:bg-gray-800 border border-slate-100 dark:border-gray-700 text-slate-600 dark:text-gray-300 rounded-2xl'
              : isSystem
              ? 'bg-yellow-50 dark:bg-yellow-900/20 text-yellow-900 dark:text-yellow-100 border border-yellow-200 dark:border-yellow-800 rounded-2xl'
              : 'bg-white dark:bg-gray-800 border border-slate-100 dark:border-gray-700 text-slate-600 dark:text-gray-300 rounded-2xl rounded-tl-sm'
          }`}
        >
          {/* 2.1 文件卡片 (用户发送) */}
          {message.files && message.files.length > 0 && (
            <div className="mb-3 space-y-2">
              {message.files.map((file, index) => (
                <div 
                  key={index} 
                  className={`group relative flex items-center gap-3 p-2.5 rounded-lg border ${
                    isUser 
                      ? 'bg-white/10 border-white/20' 
                      : 'bg-gray-50 dark:bg-gray-900/50 border-gray-200 dark:border-gray-700'
                  }`}
                >
                  <div className={`p-2 rounded-lg ${
                    isUser ? 'bg-white/20' : 'bg-white dark:bg-gray-800 shadow-sm'
                  }`}>
                    <FileText className={`w-4 h-4 ${isUser ? 'text-white' : 'text-cyan-600'}`} />
                  </div>
                  <div className="flex-1 min-w-0 text-left">
                    <div className={`text-sm font-medium truncate ${
                      isUser ? 'text-white' : 'text-gray-700 dark:text-gray-200'
                    }`}>
                      {file.name}
                    </div>
                    <div className={`text-xs ${
                      isUser ? 'text-white/70' : 'text-gray-400'
                    }`}>
                      {formatFileSize(file.size)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* 🟢 2.2 文本内容 (Markdown 渲染核心修复) */}
          {/* 🟢 修改：如果消息包含"回填"，且有回填进度组件，则不显示文本内容 */}
          {message.content && 
           !(message.content?.includes('回填') && 
             message.id === currentFillScoreMessageId && 
             xxtState && 
             xxtState.stage?.startsWith('fill_score')) && (
            <div className={`text-sm leading-relaxed overflow-hidden ${
              isUser ? 'text-white' : 'text-slate-700 dark:text-gray-200'
            }`}>
              <ReactMarkdown 
                remarkPlugins={[remarkGfm]}
                components={{
                  // 自定义样式，让 Markdown 渲染得更漂亮
                  h1: ({node, ...props}) => <h1 className="text-lg font-bold mt-4 mb-2 first:mt-0" {...props} />,
                  h2: ({node, ...props}) => <h2 className="text-base font-bold mt-3 mb-2" {...props} />,
                  h3: ({node, ...props}) => <h3 className="text-sm font-bold mt-3 mb-1" {...props} />,
                  p: ({node, ...props}) => <p className="mb-2 last:mb-0" {...props} />,
                  ul: ({node, ...props}) => <ul className="list-disc pl-5 mb-2 space-y-1" {...props} />,
                  ol: ({node, ...props}) => <ol className="list-decimal pl-5 mb-2 space-y-1" {...props} />,
                  li: ({node, ...props}) => <li className="pl-1" {...props} />,
                  strong: ({node, ...props}) => <strong className="font-bold opacity-90" {...props} />,
                  blockquote: ({node, ...props}) => <blockquote className="border-l-4 border-gray-300 pl-4 italic text-gray-500 my-2" {...props} />,
                  code: ({node, ...props}) => <code className="bg-gray-100 dark:bg-gray-700 px-1 py-0.5 rounded text-xs font-mono" {...props} />,
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          )}

          {/* 2.3 Excel 下载卡片 */}
          {message.downloadFiles && message.downloadFiles.length > 0 && (
            <div className="mt-4 pt-3 border-t border-gray-100 dark:border-gray-700">
              <div className="space-y-2">
                {message.downloadFiles.map((file: any, index: number) => (
                  <div
                    key={index}
                    onClick={() => handleDownload(file.jobId, file.name)}
                    className="group flex items-center justify-between p-3 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl cursor-pointer hover:border-emerald-500 hover:shadow-md transition-all duration-200 w-full"
                  >
                    <div className="flex items-center gap-3 overflow-hidden">
                      <div className="w-10 h-10 rounded-lg bg-emerald-50 dark:bg-emerald-900/20 flex items-center justify-center flex-shrink-0 text-emerald-600 dark:text-emerald-400 group-hover:scale-110 transition-transform">
                        <FileSpreadsheet className="w-5 h-5" />
                      </div>
                      <div className="flex flex-col min-w-0 text-left">
                        <span className="text-sm font-bold text-gray-900 dark:text-gray-100 truncate group-hover:text-emerald-600 transition-colors">
                          {file.name}
                        </span>
                        <span className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
                          点击立即下载
                        </span>
                      </div>
                    </div>
                    <div className="text-gray-400 group-hover:text-emerald-600 transition-colors pl-2">
                      {downloadingId === file.jobId ? (
                        <Loader2 className="w-5 h-5 animate-spin text-emerald-500" />
                      ) : (
                        <Download className="w-5 h-5" />
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 2.4 进度面板 */}
          {message.executionSteps && message.executionSteps.length > 0 && (
            <ProgressPanel
              steps={message.executionSteps}
              isRunning={message.isExecuting || false}
            />
          )}

          {/* 🟢 2.4.5 新增：回填进度面板 - 只在当前回填消息中显示 */}
          {message.content?.includes('回填') && 
           message.id === currentFillScoreMessageId && 
           xxtState && 
           xxtState.stage?.startsWith('fill_score') && (
            <FillScoreProgress state={xxtState} />
          )}

          {/* 2.5 批改结果 / 批量任务结果 */}
          {shouldShowResults && (
            <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
              <GradingResults
                results={hasMessageResults ? message.gradingResults! : storeResults}
                jobId={message.metadata?.jobId || jobId}
              />
            </div>
          )}
        </div>

        {/* 3. 选项按钮 */}
        {message.options && message.options.length > 0 && (
          <div className="mt-3 space-y-2 w-full">
            {message.options.map((option, index) => (
              <button
                key={index}
                onClick={() => onOptionSelect(option)}
                disabled={isAgentLoading}
                className={`block w-full text-left px-4 py-2 border rounded-lg transition-colors ${
                  isAgentLoading
                    ? 'bg-gray-100 dark:bg-gray-800 border-gray-300 dark:border-gray-600 text-gray-400 dark:text-gray-500 cursor-not-allowed'
                    : 'bg-white dark:bg-gray-700 border-gray-200 dark:border-gray-600 hover:border-cyan-500 dark:hover:border-cyan-400 hover:bg-cyan-50 dark:hover:bg-cyan-900/20 text-gray-900 dark:text-white'
                }`}
              >
                <span className={`text-sm font-medium ${
                  isAgentLoading
                    ? 'text-gray-400 dark:text-gray-500'
                    : 'text-gray-900 dark:text-white'
                }`}>
                  {option.label}
                </span>
                {(() => {
                  const description = option.metadata?.description;
                  return description && typeof description === 'string' ? (
                    <span className="block text-xs text-gray-500 dark:text-gray-400 mt-1">
                      {description}
                    </span>
                  ) : null;
                })()}
              </button>
            ))}
          </div>
        )}

        {/* 4. 时间戳 */}
        <p
          className={`text-xs text-gray-400 dark:text-gray-500 mt-1 ${
            isUser ? 'text-right' : ''
          }`}
        >
          {message.timestamp.toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </p>
      </div>
    </div>
  );
}
