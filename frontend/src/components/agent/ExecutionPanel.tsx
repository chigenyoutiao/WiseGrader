import { CheckCircle2, Circle, Loader2, XCircle, QrCode, Download, FileText, Sparkles } from 'lucide-react';
import { useStore, type StepStatus, type ExecutionStep } from '../../store';

export default function ExecutionPanel() {
  const { executionSteps, xxtState } = useStore();
  const steps = executionSteps;
  const classNames = (xxtState?.classes || [])
    .map((c: any) => {
      if (typeof c === 'string') return c;
      return c?.name || c?.id || '';
    })
    .filter((n: string) => n && !n.includes('全部班级') && !n.includes('默认班级'));

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

    // Default icons based on step type
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

  const getStepColor = (status: StepStatus) => {
    switch (status) {
      case 'running':
        return 'border-cyan-500 bg-cyan-50 dark:bg-cyan-900/20 text-cyan-700 dark:text-cyan-300';
      case 'completed':
        return 'border-green-500 bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300';
      case 'failed':
        return 'border-red-500 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300';
      default:
        return 'border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-500 dark:text-gray-400';
    }
  };

  const getConnectorColor = (currentStatus: StepStatus, nextStatus: StepStatus) => {
    if (currentStatus === 'completed' && (nextStatus === 'completed' || nextStatus === 'running')) {
      return 'bg-green-500';
    }
    if (currentStatus === 'completed' || currentStatus === 'running') {
      return 'bg-cyan-500';
    }
    return 'bg-gray-300 dark:bg-gray-600';
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
          执行流程
        </h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          实时追踪任务进度
        </p>
      </div>

      {classNames.length > 0 && (
        <div className="px-6 pt-4">
          <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">已发现班级</div>
          <div className="flex flex-wrap gap-2">
            {classNames.map((name) => (
              <span
                key={name}
                className="px-3 py-1 rounded-full bg-cyan-50 text-cyan-700 border border-cyan-200 text-xs dark:bg-cyan-900/20 dark:text-cyan-200 dark:border-cyan-700"
              >
                {name}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Steps Timeline */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="space-y-0">
          {steps.map((step, index) => (
            <div key={step.id} className="relative">
              {/* Step Item */}
              <div className="flex items-start gap-3 pb-8">
                {/* Icon Container */}
                <div
                  className={`w-10 h-10 rounded-lg border-2 flex items-center justify-center flex-shrink-0 transition-all ${getStepColor(
                    step.status
                  )}`}
                >
                  {getStepIcon(step)}
                </div>

                {/* Content */}
                <div className="flex-1 pt-1">
                  <h3
                    className={`text-sm font-medium ${
                      step.status === 'pending'
                        ? 'text-gray-500 dark:text-gray-400'
                        : 'text-gray-900 dark:text-white'
                    }`}
                  >
                    {step.title}
                  </h3>
                  {step.description && (
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      {step.description}
                    </p>
                  )}
                  {step.status === 'running' && (
                    <div className="mt-2">
                      <div className="h-1 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                        <div className="h-full bg-cyan-500 animate-pulse w-2/3"></div>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Connector Line */}
              {index < steps.length - 1 && (
                <div
                  className={`absolute left-5 top-10 w-0.5 h-8 -translate-x-1/2 transition-colors ${getConnectorColor(
                    step.status,
                    steps[index + 1].status
                  )}`}
                ></div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Footer Info */}
      <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
        <div className="text-xs text-gray-500 dark:text-gray-400 space-y-1">
          <div className="flex items-center justify-between">
            <span>当前阶段</span>
            <span className="font-medium text-gray-700 dark:text-gray-300">
              {xxtState?.stage || '等待指令'}
            </span>
          </div>
          {xxtState?.error && (
            <div className="text-red-600 dark:text-red-400 text-xs mt-2">
              错误: {xxtState.error}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
