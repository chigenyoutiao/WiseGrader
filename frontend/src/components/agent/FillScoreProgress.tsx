import { useEffect, useState } from 'react';
import { Loader2, CheckCircle2, User } from 'lucide-react';
import type { XxtState } from '../../store';

interface FillScoreProgressProps {
  state: XxtState | null;
}

export default function FillScoreProgress({ state }: FillScoreProgressProps) {
  // 🟢 闪动效果：当前学生名字
  const [isPulsing, setIsPulsing] = useState(true);
  useEffect(() => {
    if (!state?.currentStudent) return;
    const interval = setInterval(() => {
      setIsPulsing(prev => !prev);
    }, 800);
    return () => clearInterval(interval);
  }, [state?.currentStudent]);

  if (!state || !state.stage?.startsWith('fill_score')) {
    return null;
  }

  const currentIndex = state.currentIndex || 0;
  const total = state.total || 1;
  const progress = state.progress || ((currentIndex / total) * 100);
  const currentStudent = state.currentStudent || '';
  const isCompleted = state.stage === 'fill_score_completed';
  const isPartial = state.stage === 'fill_score_partial';
  const isRunning = state.stage === 'fill_score_running';
  const successCount = state.successCount ?? (isCompleted ? total : currentIndex);
  const failedCount = state.failedCount ?? (isPartial ? (total - currentIndex) : 0);

  return (
    <div className="mt-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800/50 overflow-hidden">
      <div className="px-3 py-2">
        {/* 标题 */}
        <div className="flex items-center gap-2 mb-2">
          {isRunning ? (
            <Loader2 className="w-4 h-4 text-cyan-600 animate-spin" />
          ) : (
            <CheckCircle2 className="w-4 h-4 text-green-600" />
          )}
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
            {isRunning ? '正在导入...' : '导入完成'}
          </span>
          {/* 完成时显示成功/失败统计 */}
          {(isCompleted || isPartial) && (
            <span className="text-xs text-gray-600 dark:text-gray-400">
              成功 {successCount} 个，失败 {failedCount} 个
            </span>
          )}
        </div>

        {/* 进度条 */}
        <div className="mb-2">
          <div className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-cyan-500 to-cyan-600 dark:from-cyan-400 dark:to-cyan-500 transition-all duration-500 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        {/* 当前处理的学生名字（只在运行中显示） */}
        {currentStudent && isRunning && (
          <div className="flex items-center gap-2">
            <User className={`w-3.5 h-3.5 text-cyan-600 ${isPulsing ? 'opacity-100' : 'opacity-60'} transition-opacity duration-300`} />
            <span className={`text-xs text-cyan-700 dark:text-cyan-300 ${isPulsing ? 'opacity-100 animate-pulse' : 'opacity-70'} transition-opacity duration-300`}>
              {currentStudent}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
