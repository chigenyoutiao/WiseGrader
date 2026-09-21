import { Disclosure, Transition } from '@headlessui/react';
import { ChevronDown, CheckCircle, XCircle, Loader2, Upload, Download } from 'lucide-react';
import { useState } from 'react';
import { useStore } from '../../store';
import type { GradingResult } from '../../store';

interface GradingResultsProps {
  results: GradingResult[];
  jobId?: string;
}

export default function GradingResults({ results, jobId }: GradingResultsProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [activeJobId, setActiveJobId] = useState<string | null>(jobId || null);
  const {
    agentContext,
    jobId: storeJobId,
    batchJobs,
    triggerScoreFill,
    isAgentLoading,
    exportResults,
    pollJobStatus,
    fillingClassMap,
  } = useStore();
  const effectiveJobId = activeJobId || storeJobId;

  // 视图状态
  const hasBatch = batchJobs && batchJobs.length > 0;
  const isListView = hasBatch && !effectiveJobId;

  const completedCount = results.filter(r => r.status === 'completed').length;
  const failedCount = results.filter(r => r.status === 'failed').length;
  const processingCount = results.filter(r => r.status === 'processing').length;

  // 🟢 修复：从 agentContext 直接获取课程和考试信息（session 数据已直接合并到 agentContext）
  const course = (agentContext?.course || agentContext?.session?.course) as string | undefined;
  const exam = (agentContext?.exam || agentContext?.session?.exam) as string | undefined;
  const canFillScores = effectiveJobId && course && exam && completedCount > 0;

  const handleExportAll = async () => {
    if (!hasBatch) return;
    for (const item of batchJobs) {
      if (item.jobId) {
        try { await exportResults(item.jobId); } catch (e) { console.error(e); }
      }
    }
  };

  const handleExportOne = async (jid: string) => {
    if (!jid) return;
    try { await exportResults(jid); } catch (e) { console.error(e); }
  };

  const handleViewOne = async (jid: string) => {
    if (!jid) return;
    await pollJobStatus(jid); // 刷新全局结果
    setActiveJobId(jid);
  };

  // 批量模式任务清单
  const renderBatchList = () => (
    <div className="space-y-3 mb-4">
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium text-gray-900 dark:text-white">
          已就绪 {batchJobs.length} 个班级的任务
        </div>
        <button
          onClick={handleExportAll}
          className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-lg bg-blue-50 text-blue-700 border border-blue-200 hover:bg-blue-100 dark:bg-blue-900/30 dark:text-blue-200 dark:border-blue-700"
        >
          <Download className="w-4 h-4" /> 一键导出全部
        </button>
      </div>
      <div className="space-y-2">
        {batchJobs.map((b, idx) => (
          <div key={b.jobId} className="flex items-center justify-between p-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
            <div className="flex items-center gap-2 text-sm text-gray-800 dark:text-gray-100">
              <span className="px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-xs text-gray-600 dark:text-gray-300">任务{idx + 1}</span>
              <span className="font-medium">{b.name || b.jobId}</span>
              <span className="text-xs text-gray-500 dark:text-gray-400">
                {b.status === 'running' ? '进行中' : b.status === 'completed' ? '已完成' : b.status === 'failed' ? '失败' : '待批改'}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => handleViewOne(b.jobId)}
                className="px-2 py-1 rounded border border-gray-200 dark:border-gray-600 text-xs text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700"
              >
                查看详情
              </button>
              <button
                onClick={() => handleExportOne(b.jobId)}
                className="px-2 py-1 rounded border border-blue-200 dark:border-blue-600 bg-blue-50 text-blue-700 text-xs hover:bg-blue-100 dark:bg-blue-900/30 dark:text-blue-200"
              >
                下载 Excel
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  const handleFillScores = async () => {
    if (!canFillScores || !effectiveJobId) return;
    await triggerScoreFill(effectiveJobId, course!, exam!);
  };

  // 🟢 新增：为特定班级回填分数
  const handleFillScoresForClass = async (jobId: string, className: string) => {
    if (!course || !exam) {
      // 🟢 如果没有课程和考试信息，提示用户并尝试从对话中获取
      const userInput = prompt(
        `请提供课程和考试信息，用于回填 ${className} 的成绩。\n格式：课程名称-考试名称\n例如：智能合约-期末考试`
      );
      if (!userInput || !userInput.includes('-')) {
        alert('格式错误，请使用"课程名称-考试名称"的格式，例如："智能合约-期末考试"');
        return;
      }
      const [inputCourse, inputExam] = userInput.split('-').map(s => s.trim());
      if (!inputCourse || !inputExam) {
        alert('格式错误，请使用"课程名称-考试名称"的格式');
        return;
      }
      await triggerScoreFill(jobId, inputCourse, inputExam, className);
    } else {
      await triggerScoreFill(jobId, course, exam, className);
    }
  };

  return (
    <div className="space-y-2">
      {/* 批量任务列表视图 */}
      {isListView && renderBatchList()}

      {/* 详情视图（单任务或选中某班） */}
      {!isListView && (
        <>
          {/* 🟢 修复：移除返回班级列表按钮，如果有批量任务且结果已包含班级信息，在分组显示中已经包含导出按钮 */}
          {/* 如果只是单任务或没有按班级分组，则显示导出按钮 */}
          {hasBatch && results.length > 0 && (() => {
            const hasClassInfo = results.some(r => r.className || r.jobId);
            // 如果没有按班级分组显示，则显示导出所有按钮
            if (!hasClassInfo || effectiveJobId) {
              return (
                <div className="mb-2 flex items-center gap-2">
                  <button
                    onClick={() => {
                      if (hasBatch && batchJobs.length > 0) {
                        handleExportAll();
                      } else if (effectiveJobId) {
                        handleExportOne(effectiveJobId);
                      } else if (jobId) {
                        handleExportOne(jobId);
                      }
                    }}
                    className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-lg bg-blue-50 text-blue-700 border border-blue-200 hover:bg-blue-100 dark:bg-blue-900/30 dark:text-blue-200 dark:border-blue-700 transition-colors"
                  >
                    <Download className="w-4 h-4" /> 导出成绩
                  </button>
                </div>
              );
            }
            return null;
          })()}

          {/* 🟢 修复：按班级分组显示结果 */}
          {(() => {
            // 🟢 修复：检查结果中是否有 className 或 jobId 信息（说明是批量任务的结果）
            // 或者检查是否有批量任务列表，如果有多个批量任务，也应该分组显示
            const hasClassInfo = results.some(r => r.className || r.jobId);
            const shouldGroupByClass = hasClassInfo || (hasBatch && batchJobs.length > 1);
            
            // 🟢 修复：如果需要分组，总是按班级分组显示
            if (shouldGroupByClass) {
              // 按班级分组结果
              const groupedByClass = results.reduce((acc, result) => {
                // 优先使用 result.className，否则从 batchJobs 中查找，最后使用 jobId
                let className = result.className;
                if (!className && result.jobId) {
                  const foundBatch = batchJobs.find(b => b.jobId === result.jobId);
                  className = foundBatch?.name || foundBatch?.jobId || result.jobId;
                }
                // 如果还是没有，尝试从 jobId 推断（假设 jobId 包含了班级信息）
                if (!className && result.jobId) {
                  className = result.jobId;
                }
                if (!className) {
                  className = '未知班级';
                }
                
                if (!acc[className]) {
                  acc[className] = [];
                }
                acc[className].push(result);
                return acc;
              }, {} as Record<string, typeof results>);

              const classNames = Object.keys(groupedByClass);
              
              // 🟢 调试：如果只有一个班级，也应该显示分组（以保持一致性）
              // 如果分组后只有一个班级，但仍然显示分组，这样可以保持界面一致性

              // 🟢 修复：只要有班级信息，就按班级分组显示（即使只有一个班级）
              if (classNames.length > 0) {
                return (
                  <div className="space-y-4">
                    {classNames.map((className) => {
                      const classResults = groupedByClass[className];
                      const classCompleted = classResults.filter(r => r.status === 'completed').length;
                      const classProcessing = classResults.filter(r => r.status === 'processing').length;
                      const classFailed = classResults.filter(r => r.status === 'failed').length;
                      
                      // 找到对应的 jobId（用于导出）
                      const classJobId = classResults[0]?.jobId || batchJobs.find(b => b.name === className)?.jobId;
                      
                      return (
                        <div key={className} className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
                          {/* 班级标题和统计 */}
                          <div className="flex items-center justify-between gap-2 p-3 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
                            <div className="flex items-center gap-4 text-sm">
                              <span className="font-medium text-gray-900 dark:text-white">{className}</span>
                              <span className="text-gray-600 dark:text-gray-400">总计: {classResults.length} 份</span>
                              {classCompleted > 0 && (
                                <span className="text-green-600 dark:text-green-400">已完成: {classCompleted}</span>
                              )}
                              {classProcessing > 0 && (
                                <span className="text-blue-600 dark:text-blue-400">批改中: {classProcessing}</span>
                              )}
                              {classFailed > 0 && (
                                <span className="text-red-600 dark:text-red-400">失败: {classFailed}</span>
                              )}
                            </div>
                            {/* 导出和回填按钮 */}
                            {classJobId && (
                              <div className="flex items-center gap-2">
                                <button
                                  onClick={() => handleExportOne(classJobId)}
                                  className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-lg bg-blue-50 text-blue-700 border border-blue-200 hover:bg-blue-100 dark:bg-blue-900/30 dark:text-blue-200 dark:border-blue-700"
                                >
                                  <Download className="w-4 h-4" /> 导出成绩
                                </button>
                                {/* 🟢 修复：回填按钮总是显示，只要有已完成的结果就可以回填 */}
                                {classCompleted > 0 && (() => {
                                  const classKey = `${classJobId}-${className}`;
                                  const isFilling = !!fillingClassMap[classKey];
                                  return (
                                    <button
                                      onClick={() => handleFillScoresForClass(classJobId, className)}
                                      disabled={isAgentLoading || isFilling}
                                      className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-lg bg-purple-50 text-purple-700 border border-purple-200 hover:bg-purple-100 dark:bg-purple-900/30 dark:text-purple-200 dark:border-purple-700 disabled:opacity-50 disabled:cursor-not-allowed disabled:bg-gray-100 disabled:text-gray-400 disabled:border-gray-200"
                                      title={isFilling ? `${className} 正在回填中...` : (course && exam ? `回填到学习通: ${course} - ${exam} - ${className}` : `回填 ${className} 的成绩到学习通（需要指定课程和考试）`)}
                                    >
                                      {isAgentLoading || isFilling ? (
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                      ) : (
                                        <Upload className="w-4 h-4" />
                                      )}
                                      回填分数
                                    </button>
                                  );
                                })()}
                              </div>
                            )}
                          </div>
                          
                          {/* 该班级的结果列表 */}
                          <div className="p-3 space-y-2 max-h-96 overflow-y-auto">
                            {classResults.map((result, index) => (
                              <ResultItem key={`${className}-${index}`} result={result} />
                            ))}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                );
              }
            }

            // 单班级或选中特定班级时的显示
            return (
              <>
                {/* 折叠按钮和统计信息 */}
                <div className="flex items-center justify-between gap-2">
                  <button
                    onClick={() => setIsExpanded(!isExpanded)}
                    className="flex-1 flex items-center justify-between p-2 hover:bg-slate-50 dark:hover:bg-gray-800 rounded-lg transition-colors"
                  >
                    <div className="flex items-center gap-4 text-sm text-gray-600 dark:text-gray-400">
                      <span className="font-medium">
                        {hasBatch && effectiveJobId 
                          ? batchJobs.find(b => b.jobId === effectiveJobId)?.name || '批改结果'
                          : '批改结果'}
                      </span>
                      <span>总计: {results.length} 份</span>
                      {completedCount > 0 && (
                        <span className="text-green-600 dark:text-green-400">已完成: {completedCount}</span>
                      )}
                      {processingCount > 0 && (
                        <span className="text-blue-600 dark:text-blue-400">批改中: {processingCount}</span>
                      )}
                      {failedCount > 0 && (
                        <span className="text-red-600 dark:text-red-400">失败: {failedCount}</span>
                      )}
                    </div>
                    <ChevronDown
                      className={`w-4 h-4 text-gray-400 transition-transform duration-300 ${
                        isExpanded ? 'rotate-180' : 'rotate-0'
                      }`}
                    />
                  </button>
                  
                  {/* 回填分数按钮 */}
                  {canFillScores && (
                    <button
                      onClick={handleFillScores}
                      disabled={isAgentLoading}
                      className="flex items-center gap-2 px-3 py-2 bg-purple-500 hover:bg-purple-600 dark:bg-purple-600 dark:hover:bg-purple-700 text-white text-sm font-medium rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                      title={`回填到学习通: ${course} - ${exam}`}
                    >
                      {isAgentLoading ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Upload className="w-4 h-4" />
                      )}
                      <span className="hidden sm:inline">回填分数</span>
                    </button>
                  )}
                </div>

                {/* 结果列表 - 可折叠 */}
                <div
                  className={`overflow-hidden transition-all duration-300 ${
                    isExpanded ? 'max-h-[800px] opacity-100' : 'max-h-0 opacity-0'
                  }`}
                >
                  <div className="space-y-2 max-h-96 overflow-y-auto">
                    {results.length > 0 ? (
                      results.map((result, index) => (
                        <ResultItem key={index} result={result} />
                      ))
                    ) : (
                       <div className="text-center py-8 text-gray-500 dark:text-gray-400 text-sm">
                         该班级暂无数据，请尝试点击上方"返回"后重新点击"查看详情"
                       </div>
                    )}
                  </div>
                </div>
              </>
            );
          })()}
        </>
      )}
    </div>
  );
}

function ResultItem({ result }: { result: GradingResult }) {
  const statusConfig = {
    processing: {
      icon: <Loader2 className="w-4 h-4 animate-spin" />,
      text: '批改中',
      className: 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300',
    },
    completed: {
      icon: <CheckCircle className="w-4 h-4" />,
      text: '已完成',
      className: 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300',
    },
    failed: {
      icon: <XCircle className="w-4 h-4" />,
      text: '失败',
      className: 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300',
    },
  };

  const config = statusConfig[result.status];

  return (
    <Disclosure>
      {({ open }) => (
        <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
          <Disclosure.Button className="w-full flex items-center justify-between p-3 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors">
            <div className="flex items-center gap-3 flex-1 text-left">
              <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium ${config.className}`}>
                {config.icon}
                {config.text}
              </span>
              <span className="text-sm font-medium text-gray-900 dark:text-white">
                {result.studentName} ({result.studentId})
              </span>
              {result.score !== null && result.score !== undefined && (
                <span className="text-sm font-semibold text-gray-900 dark:text-white">
                  {result.score} 分
                </span>
              )}
            </div>
            <ChevronDown
              className={`w-4 h-4 text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`}
            />
          </Disclosure.Button>
          <Transition
            enter="transition duration-100 ease-out"
            enterFrom="transform scale-95 opacity-0"
            enterTo="transform scale-100 opacity-100"
            leave="transition duration-75 ease-out"
            leaveFrom="transform scale-100 opacity-100"
            leaveTo="transform scale-95 opacity-0"
          >
            <Disclosure.Panel className="p-3 bg-gray-50 dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700">
              <div className="space-y-2 text-sm">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">分数:</span>
                    <span className="ml-2 font-medium text-gray-900 dark:text-white">
                      {result.score !== null && result.score !== undefined ? `${result.score} 分` : '-'}
                    </span>
                  </div>
                  {result.formattingScore !== null && result.formattingScore !== undefined && (
                    <div>
                      <span className="text-gray-500 dark:text-gray-400">格式分:</span>
                      <span className="ml-2 font-medium text-gray-900 dark:text-white">
                        {result.formattingScore} 分
                      </span>
                    </div>
                  )}
                  {result.tokenUsage && (
                    <div>
                      <span className="text-gray-500 dark:text-gray-400">Token:</span>
                      <span className="ml-2 font-medium text-gray-900 dark:text-white">
                        {result.tokenUsage.totalTokens.toLocaleString()}
                      </span>
                    </div>
                  )}
                </div>
                {result.feedback && (
                  <div>
                    <span className="text-gray-500 dark:text-gray-400 block mb-1">AI评语:</span>
                    <div className="p-2 bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 whitespace-pre-wrap text-xs max-h-40 overflow-y-auto">
                      {result.feedback}
                    </div>
                  </div>
                )}
                {result.formattingChecks && result.formattingChecks.length > 0 && (
                  <div>
                    <span className="text-gray-500 dark:text-gray-400 block mb-1">格式检查:</span>
                    <div className="space-y-1">
                      {result.formattingChecks.map((check, idx) => (
                        <div
                          key={idx}
                          className={`text-xs px-2 py-1 rounded ${
                            check.passed
                              ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300'
                              : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300'
                          }`}
                        >
                          {check.passed ? '✓' : '✗'} {check.message || check.rule || '格式检查'}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </Disclosure.Panel>
          </Transition>
        </div>
      )}
    </Disclosure>
  );
}
