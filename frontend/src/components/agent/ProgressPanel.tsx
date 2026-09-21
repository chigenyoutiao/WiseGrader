import { useState } from 'react';
import { ChevronDown, ChevronUp, CheckCircle2, Circle, Loader2, XCircle } from 'lucide-react';
import type { ExecutionStep, StepStatus } from '../../store';

interface ProgressPanelProps {
  steps: ExecutionStep[];
  isRunning?: boolean;
}

export default function ProgressPanel({ steps, isRunning = false }: ProgressPanelProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  const getStepIcon = (step: ExecutionStep) => {
    const iconClass = 'w-3.5 h-3.5';

    if (step.status === 'running') {
      return <Loader2 className={`${iconClass} animate-spin text-cyan-600`} />;
    }
    if (step.status === 'completed') {
      return <CheckCircle2 className={`${iconClass} text-green-600`} />;
    }
    if (step.status === 'failed') {
      return <XCircle className={`${iconClass} text-red-600`} />;
    }
    return <Circle className={`${iconClass} text-gray-400`} />;
  };

  const getStepTextColor = (status: StepStatus) => {
    switch (status) {
      case 'running':
        return 'text-cyan-700 dark:text-cyan-300';
      case 'completed':
        return 'text-green-700 dark:text-green-300';
      case 'failed':
        return 'text-red-700 dark:text-red-300';
      default:
        return 'text-gray-600 dark:text-gray-400';
    }
  };

  const completedCount = steps.filter(s => s.status === 'completed').length;
  const totalCount = steps.length;
  const currentStep = steps.find(s => s.status === 'running');
  const isFailed = steps.some(s => s.status === 'failed');

  return (
    <div className="mt-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800/50 overflow-hidden">
      {/* Header - 可折叠 */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-3 py-2 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          {isRunning ? (
            <Loader2 className="w-4 h-4 text-cyan-600 animate-spin" />
          ) : isFailed ? (
            <XCircle className="w-4 h-4 text-red-600" />
          ) : (
            <CheckCircle2 className="w-4 h-4 text-green-600" />
          )}
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
            {isRunning ? '正在执行' : isFailed ? '执行失败' : '执行完成'}
          </span>
          <span className="text-xs text-gray-500 dark:text-gray-400">
            {completedCount}/{totalCount}
          </span>
        </div>
        {isExpanded ? (
          <ChevronUp className="w-4 h-4 text-gray-500" />
        ) : (
          <ChevronDown className="w-4 h-4 text-gray-500" />
        )}
      </button>

      {/* Content - 展开时显示 */}
      {isExpanded && (
        <div className="px-3 py-2 border-t border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-900/30">
          <div className="space-y-2">
            {steps.map((step) => (
              <div key={step.id} className="flex items-start gap-2">
                <div className="mt-0.5">{getStepIcon(step)}</div>
                <div className="flex-1 min-w-0">
                  <p className={`text-xs font-medium ${getStepTextColor(step.status)}`}>
                    {step.title}
                  </p>
                  {step.description && (
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                      {step.description}
                    </p>
                  )}
                  {step.status === 'running' && (
                    <div className="mt-1.5">
                      <div className="h-0.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                        <div className="h-full bg-cyan-500 animate-pulse w-2/3"></div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* 当前步骤提示 */}
          {currentStep && (
            <div className="mt-3 pt-2 border-t border-gray-200 dark:border-gray-700">
              <p className="text-xs text-gray-600 dark:text-gray-400">
                当前: {currentStep.title}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
