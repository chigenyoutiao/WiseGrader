import { useStore } from '../store';
import { Play, Download, Loader2 } from 'lucide-react';

export default function Actions() {
  const {
    jobId,
    jobIds,
    batchJobs,
    jobStatus,
    selectedModel,
    apiKey,
    criteria,
    feedbackStyle,
    startJob,
    startJobs,
    startBatchJobs,
    exportResults,
    isLoading,
  } = useStore();

  const hasBatch = batchJobs && batchJobs.length > 0;
  const hasJobs = hasBatch || (jobIds && jobIds.length > 0) || jobId;
  const canStartJob = jobStatus === 'uploaded' && hasJobs && selectedModel && apiKey && criteria;
  const canExport = jobStatus === 'completed' && hasJobs;

  const handleStartJob = async () => {
    if (!canStartJob) return;

    try {
      if (hasBatch && batchJobs.length > 0) {
        await startBatchJobs(batchJobs, selectedModel, apiKey, criteria, feedbackStyle);
      } else if (jobIds && jobIds.length > 0) {
        await startJobs(jobIds, selectedModel, apiKey, criteria, feedbackStyle);
      } else if (jobId) {
        await startJob(jobId, selectedModel, apiKey, criteria, feedbackStyle);
      }
    } catch (error) {
      console.error('Failed to start job:', error);
    }
  };

  const handleExport = async () => {
    if (!canExport) return;

    try {
      // 仅导出第一个 jobId（或当前 jobId），如需批量导出可拓展
      const targetId = (jobIds && jobIds[0]) || jobId;
      if (targetId) await exportResults(targetId);
    } catch (error) {
      console.error('Failed to export results:', error);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      {/* 操作按钮组 */}
      <div className="flex gap-3">
        {/* Start Grading Button */}
        <button
          onClick={handleStartJob}
          disabled={!canStartJob || isLoading}
          className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-500 hover:bg-blue-600 dark:bg-blue-600 dark:hover:bg-blue-700 text-white font-medium rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isLoading && jobStatus === 'processing' ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>批改中...</span>
            </>
          ) : (
            <>
              <Play className="w-4 h-4" />
              <span>开始批改</span>
            </>
          )}
        </button>

        {/* Export Excel Button */}
        <button
          onClick={handleExport}
          disabled={!canExport || isLoading}
          className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-green-500 hover:bg-green-600 dark:bg-green-600 dark:hover:bg-green-700 text-white font-medium rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Download className="w-4 h-4" />
          <span>导出 Excel</span>
        </button>
      </div>

      {/* Status Hints */}
      {!canStartJob && jobStatus === 'uploaded' && (
        <div className="p-2.5 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
          <p className="text-xs text-yellow-800 dark:text-yellow-200">
            请确保已配置 AI 模型、API Key 和批改标准
          </p>
        </div>
      )}

      {hasBatch && batchJobs.length > 0 && (
        <div className="p-2.5 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
          <p className="text-xs text-blue-800 dark:text-blue-200 mb-1">已就绪 {batchJobs.length} 个班级的任务：</p>
          <div className="flex flex-col gap-1">
            {batchJobs.map((item, idx) => (
              <div key={item.jobId} className="flex items-center justify-between text-xs px-2 py-1 rounded bg-white dark:bg-blue-800 border border-blue-200 dark:border-blue-700">
                <span className="text-blue-700 dark:text-blue-100">任务{idx + 1}: {item.name || item.jobId}</span>
                <span className="text-gray-500 dark:text-gray-300">{item.status === 'running' ? '进行中' : item.status === 'completed' ? '已完成' : item.status === 'failed' ? '失败' : '待批改'}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {!hasBatch && jobIds && jobIds.length > 1 && (
        <div className="p-2.5 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
          <p className="text-xs text-blue-800 dark:text-blue-200 mb-1">批量任务列表:</p>
          <div className="flex flex-wrap gap-2">
            {jobIds.map((id, idx) => (
              <span key={id} className="px-2 py-1 rounded bg-white dark:bg-blue-800 text-xs text-blue-700 dark:text-blue-100 border border-blue-200 dark:border-blue-700">
                任务{idx + 1}: {id}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
