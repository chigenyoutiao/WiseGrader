import { useState } from 'react';
import { ChevronDown, CheckCircle2, Circle, Loader2, XCircle, QrCode, Download, FileText, Sparkles } from 'lucide-react';
import { useStore, type Message, type MessageOption, type ExecutionStep } from '../../store';
import ChatMessage from './ChatMessage';

interface WorkflowStepProps {
  stepId: string;
  title: string;
  messages: Message[];
  onOptionSelect: (option: MessageOption) => void;
  isAgentLoading: boolean;
  isCompleted?: boolean;
  defaultExpanded?: boolean;
  isActive?: boolean;
}

export default function WorkflowStep({
  title,
  messages,
  onOptionSelect,
  isAgentLoading,
  isCompleted = false,
  defaultExpanded = false,
  isActive = false,
}: WorkflowStepProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  
  const globalExecutionSteps = useStore((state) => state.executionSteps);
  const jobProgress = useStore((state) => state.jobProgress);

  const hasGradingResults = messages.some(m => m.gradingResults && m.gradingResults.length > 0);
  const isExecuting = messages.some(m => m.isExecuting);
  
  const messageExecutionSteps: ExecutionStep[] = messages
    .map(m => m.executionSteps || [])
    .flat()
    .filter((step, index, self) =>
      index === self.findIndex(s => s.id === step.id)
    );

  const ownsExecutionState = messageExecutionSteps.length > 0 || messages.some(m => m.isExecuting);

  const executionSteps: ExecutionStep[] = ownsExecutionState
    ? messageExecutionSteps
    : isActive
      ? globalExecutionSteps
      : [];

  const completedCount = executionSteps.filter(s => s.status === 'completed').length;
  const totalCount = executionSteps.length || 0;
  const isRunning = executionSteps.some(s => s.status === 'running');

  const hasExecutionSteps = executionSteps.length > 0;
  const effectiveAgentLoading = isAgentLoading && isActive;
  
  const getStepIcon = (step: ExecutionStep) => {
    const iconClass = 'w-4 h-4';
    if (step.status === 'running') {
      return <Loader2 className={`${iconClass} animate-spin`} />;
    }
    if (step.status === 'completed') {
      return <CheckCircle2 className={iconClass} />;
    }
    if (step.status === 'failed') {
      return <XCircle className={iconClass} />;
    }
    switch (step.icon) {
      case 'qr':
        return <QrCode className={iconClass} />;
      case 'download':
        return <Download className={iconClass} />;
      case 'file':
        return <FileText className={iconClass} />;
      case 'sparkles':
        return <Sparkles className={iconClass} />;
      default:
        return <Circle className={iconClass} />;
    }
  };

  return (
    <div className="group cursor-pointer">
      {/* Header */}
      <div
        onClick={() => setIsExpanded(!isExpanded)}
        className={`flex items-center justify-between p-3 rounded-2xl transition-all duration-200 ${
          isExpanded
            ? 'bg-white dark:bg-gray-800 shadow-sm'
            : 'hover:bg-white dark:hover:bg-gray-800 hover:shadow-sm'
        }`}
      >
        <div className="flex items-center gap-4">
          {/* 状态图标 */}
          {isExecuting || isRunning ? (
            <div className="relative w-8 h-8 rounded-full bg-cyan-50 dark:bg-cyan-900/30 text-cyan-600 dark:text-cyan-400 ring-4 ring-cyan-500/20 dark:ring-cyan-500/10 flex items-center justify-center flex-shrink-0">
              <Loader2 className="w-4 h-4 animate-spin" />
            </div>
          ) : isCompleted || hasGradingResults ? (
            <div className="w-8 h-8 rounded-full bg-emerald-50 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400 ring-4 ring-emerald-500/10 dark:ring-emerald-500/10 flex items-center justify-center flex-shrink-0">
              <CheckCircle2 className="w-4 h-4" strokeWidth={3} />
            </div>
          ) : (
            <div className="w-8 h-8 rounded-full bg-slate-100 dark:bg-gray-700 text-slate-400 dark:text-gray-500 ring-4 ring-slate-200/50 dark:ring-gray-600/50 flex items-center justify-center flex-shrink-0">
              <Circle className="w-4 h-4" />
            </div>
          )}

          {/* 标题和描述 */}
          <div>
            <h3 className="text-sm font-bold text-slate-700 dark:text-white">
              {title}
            </h3>
            <p className="text-[10px] text-slate-400 dark:text-gray-400 font-medium mt-0.5">
              {hasExecutionSteps
                ? `${isRunning ? '正在执行' : isCompleted ? '已完成' : '待执行'} ${completedCount}/${totalCount}`
                : `${messages.length} 条消息${hasGradingResults ? ' · 已完成' : ''}`}
            </p>
          </div>
        </div>

        <div
          className={`text-slate-300 dark:text-gray-500 transform transition-transform duration-300 ${
            isExpanded ? 'rotate-180' : 'rotate-0'
          }`}
        >
          <ChevronDown className="w-5 h-5" />
        </div>
      </div>

      {/* Content */}
      <div
        className={`overflow-hidden transition-all duration-500 ${
          isExpanded ? 'h-auto opacity-100' : 'h-0 opacity-0'
        }`}
      >
        <div className="pl-7 ml-4 border-l-2 border-slate-100 dark:border-gray-700 space-y-6 py-6">
          {/* 用户消息 */}
          <div className="space-y-4">
            {messages
              .filter((message) => message.type === 'user')
              .map((message) => (
                <ChatMessage
                  key={message.id}
                  message={message}
                  onOptionSelect={onOptionSelect}
                  isAgentLoading={effectiveAgentLoading}
                />
              ))}
          </div>

          {/* 🟢 核心修复：删除了 && hasSystemMessages */}
          {hasExecutionSteps && !hasGradingResults && (
            <div className="ml-2 space-y-4">
              <div className="space-y-4">
                {executionSteps.map((step) => {
                  const isStep4Running = step.id === '4' && step.status === 'running';
                  const showProgress = isStep4Running && jobProgress && jobProgress.total > 0;
                  
                  return (
                    <div key={step.id} className="relative flex items-center gap-4 group/item">
                      <div
                        className={`absolute -left-[35px] w-2.5 h-2.5 rounded-full border-2 border-white dark:border-gray-800 shadow-sm z-10 ${
                          step.status === 'completed'
                            ? 'bg-emerald-500'
                            : step.status === 'running'
                            ? 'bg-cyan-500 animate-pulse'
                            : 'bg-slate-200 dark:bg-gray-600'
                        }`}
                      ></div>
                      
                      <div
                        className={`flex-shrink-0 p-1.5 rounded-md transition-all ${
                          step.status === 'completed'
                            ? 'text-emerald-500 bg-emerald-50 dark:bg-emerald-900/20'
                            : step.status === 'running'
                            ? 'text-cyan-600 dark:text-cyan-400 bg-cyan-50 dark:bg-cyan-900/20'
                            : 'text-slate-400 dark:text-gray-500 bg-slate-50 dark:bg-gray-800'
                        }`}
                      >
                        {getStepIcon(step)}
                      </div>

                      <div className="flex flex-col flex-1">
                        <span
                          className={`text-sm ${
                            step.status === 'pending'
                              ? 'text-slate-400 dark:text-gray-400 line-through decoration-slate-300 dark:decoration-gray-600'
                              : step.status === 'running'
                              ? 'font-bold text-cyan-700 dark:text-cyan-400'
                              : 'text-slate-400 dark:text-gray-400 line-through decoration-slate-300 dark:decoration-gray-600'
                          }`}
                        >
                          {step.title}
                        </span>
                        {step.status === 'running' && step.description && (
                          <span className="text-[10px] text-cyan-500/70 dark:text-cyan-400/70 mt-0.5">
                            {step.description}
                          </span>
                        )}
                        
                        {/* 进度条 */}
                        {showProgress && (
                          <div className="mt-2">
                            <div className="h-1.5 bg-slate-200 dark:bg-gray-700 rounded-full overflow-hidden">
                              <div
                                className="h-full bg-cyan-500 transition-all duration-300"
                                style={{
                                  width: `${(jobProgress.completed / jobProgress.total) * 100}%`,
                                }}
                              ></div>
                            </div>
                            <p className="text-[10px] text-cyan-600 dark:text-cyan-400 mt-1">
                              批改进度: {jobProgress.completed}/{jobProgress.total}
                            </p>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* 其他消息（批改结果） */}
          <div className="space-y-4">
            {messages
              .filter((message) => {
                if (message.type === 'user') return false;
                if (hasExecutionSteps) {
                    return message.gradingResults && message.gradingResults.length > 0;
                }
                return true;
              })
              .map((message) => (
                <ChatMessage
                  key={message.id}
                  message={message}
                  onOptionSelect={onOptionSelect}
                  isAgentLoading={effectiveAgentLoading}
                />
              ))}
          </div>
        </div>
      </div>
    </div>
  );
}