import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import apiClient, * as api from './api';
import { AxiosError } from 'axios';

interface TokenUsage {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
}

interface FormattingCheck {
  rule: string;
  passed: boolean;
  weight?: number;
  message: string;
  value?: unknown;
}

export interface GradingResult {
  studentId: string;
  studentName: string;
  score: number | null;
  contentScore?: number | null;
  formattingScore?: number | null;
  formattingChecks?: FormattingCheck[];
  formattingPreview?: string | null;
  formattingPreviewFormat?: string | null;
  formattingConfidence?: number | null;
  formattingMetrics?: Record<string, unknown> | null;
  feedback: string;
  model?: string;
  status: 'processing' | 'completed' | 'failed';
  tokenUsage?: TokenUsage | null;
  // 🟢 新增：用于批量任务模式下区分不同班级的结果
  jobId?: string;
  className?: string;
}

// 🟢 历史记录项的定义
export interface HistoryItem {
  id: string;
  title: string;
  timestamp: number;
  messages: Message[];
  executionSteps: ExecutionStep[];
  agentContext: Record<string, unknown>;
  jobId: string | null;
  jobIds: string[];
  batchJobs: { name: string; jobId: string; status?: 'pending' | 'running' | 'completed' | 'failed' }[];
  lastJobId: string | null;
}

interface JobProgress {
  completed: number;
  total: number;
}

type JobStatus = 'uploaded' | 'processing' | 'completed' | 'failed' | null;

const createEmptyTokenUsage = (): TokenUsage => ({
  promptTokens: 0,
  completionTokens: 0,
  totalTokens: 0,
});

const safeNumber = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string') {
    const parsed = Number(value);
    return Number.isNaN(parsed) ? null : parsed;
  }
  return null;
};

const normalizeTokenUsage = (usage: unknown): TokenUsage | null => {
  if (!usage || typeof usage !== 'object') return null;
  const source = usage as Record<string, unknown>;
  const prompt = safeNumber(source.promptTokens ?? source.prompt_tokens ?? source.input_tokens) ?? null;
  const completion = safeNumber(source.completionTokens ?? source.completion_tokens ?? source.output_tokens) ?? null;
  const total = safeNumber(source.totalTokens ?? source.total_tokens) ?? null;
  if (prompt === null && completion === null && total === null) return null;
  const resolvedTotal = total !== null ? total : (prompt ?? 0) + (completion ?? 0);
  const resolvedPrompt = prompt !== null ? prompt : Math.max(resolvedTotal - (completion ?? 0), 0);
  const resolvedCompletion = completion !== null ? completion : Math.max(resolvedTotal - resolvedPrompt, 0);
  return {
    promptTokens: Math.max(resolvedPrompt, 0),
    completionTokens: Math.max(resolvedCompletion, 0),
    totalTokens: Math.max(resolvedTotal, 0),
  };
};

const normalizeFormattingChecks = (value: unknown): FormattingCheck[] => {
  if (!Array.isArray(value)) return [];
  return value.map((entry): FormattingCheck | null => {
    if (!entry || typeof entry !== 'object') return null;
    const source = entry as Record<string, unknown>;
    return {
      rule: typeof source.rule === 'string' ? source.rule : 'unknown',
      passed: Boolean(source.passed),
      weight: typeof source.weight === 'number' ? source.weight : undefined,
      message: typeof source.message === 'string' ? source.message : '',
      value: source.value,
    };
  }).filter((item): item is FormattingCheck => item !== null);
};

const mapResultFromApi = (raw: any): GradingResult => {
  const normalizedStatus: GradingResult['status'] = (raw?.status) ?? (typeof raw?.score === 'number' || raw?.score === null ? 'completed' : 'processing');
  let score: number | null = null;
  if (typeof raw?.score === 'number' && Number.isFinite(raw.score)) score = raw.score;
  else if (typeof raw?.score === 'string') { const parsed = Number(raw.score); score = Number.isNaN(parsed) ? null : parsed; }
  return {
    studentId: raw?.studentId || raw?.student_id || '',
    studentName: raw?.studentName || raw?.student_name || '',
    score,
    contentScore: safeNumber(raw?.contentScore ?? raw?.content_score),
    formattingScore: safeNumber(raw?.formattingScore ?? raw?.formatting_score),
    formattingChecks: normalizeFormattingChecks(raw?.formattingChecks ?? raw?.formatting_checks),
    formattingPreview: raw?.formattingPreview || raw?.formatting_preview || null,
    formattingPreviewFormat: raw?.formattingPreviewFormat || raw?.formatting_preview_format || null,
    formattingConfidence: safeNumber(raw?.formattingConfidence ?? raw?.formatting_confidence),
    formattingMetrics: raw?.formattingMetrics || raw?.formatting_metrics || null,
    feedback: raw?.feedback || '',
    model: raw?.model || '',
    status: normalizedStatus,
    tokenUsage: normalizeTokenUsage(raw?.tokenUsage ?? raw?.token_usage),
  };
};

const deriveProgress = (incoming: JobProgress | null | undefined, results: GradingResult[], fallbackTotal: number): JobProgress | null => {
  const total = (incoming?.total ?? 0) > 0 ? (incoming?.total ?? 0) : Math.max(fallbackTotal, results.length);
  if (!total) return null;
  const completed = (typeof incoming?.completed === 'number' ? incoming?.completed : undefined) ?? results.filter(item => item.status !== 'processing').length;
  return { completed: Math.min(completed, total), total };
};

const sumTokenUsage = (results: GradingResult[]): TokenUsage => {
  return results.reduce<TokenUsage>((acc, result) => {
    if (!result.tokenUsage) return acc;
    return {
      promptTokens: acc.promptTokens + result.tokenUsage.promptTokens,
      completionTokens: acc.completionTokens + result.tokenUsage.completionTokens,
      totalTokens: acc.totalTokens + result.tokenUsage.totalTokens,
    };
  }, createEmptyTokenUsage());
};

interface GradingTargets {
  passRate: number | '';
  excellentRate: number | '';
  minScore: number | '';
}

export interface Message {
  id: string;
  type: 'user' | 'agent' | 'system';
  content: string;
  timestamp: Date;
  options?: MessageOption[];
  metadata?: Record<string, unknown>;
  executionSteps?: ExecutionStep[];
  isExecuting?: boolean;
  gradingResults?: GradingResult[];
  // 消息附带的文件列表
  files?: Array<{ name: string; size: number }>;
  // 🟢 新增：用于存放待下载的文件信息
  downloadFiles?: Array<{ name: string; jobId: string }>;
}

export interface MessageOption {
  type: 'course' | 'exam' | 'action';
  label: string;
  value: string;
  metadata?: Record<string, unknown>;
}

export type StepStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface ExecutionStep {
  id: string;
  title: string;
  description?: string;
  status: StepStatus;
  icon?: 'qr' | 'download' | 'file' | 'sparkles';
}

export interface XxtState {
  stage: string;
  message?: string;     // 新增
  qrImage?: string;     // 新增：二维码图片文件名
  courses?: Array<{ id: string; name: string }>;
  exams?: Array<{ id: string; name: string }>;
  logs?: string[];
  error?: string;
  jobId?: string;
  jobIds?: string[];
  batchJobs?: Array<{ name?: string; className?: string; jobId: string }>;
  // 🟢 新增：回填进度相关字段
  currentStudent?: string;  // 当前正在处理的学生学号
  currentIndex?: number;    // 当前进度（已完成的个数）
  total?: number;           // 总数
  progress?: number;        // 进度百分比
  successCount?: number;    // 🟢 新增：成功数量
  failedCount?: number;     // 🟢 新增：失败数量
  missingStudents?: string[]; // 未找到的学生列表
}

interface AppState {
  currentPage: 'landing' | 'agent' | 'legacy';
  token: string | null;
  isLoggedIn: boolean;
  loginError: string | null;
  jobId: string | null;
  jobIds: string[];
  batchJobs: { name: string; jobId: string; status?: 'pending' | 'running' | 'completed' | 'failed' }[];
  jobStatus: JobStatus;
  jobProgress: JobProgress | null;
  jobResults: GradingResult[];
  studentCount: number;
  tokenUsageTotals: TokenUsage;
  retryingStudentIds: string[];
  isLoading: boolean;
  currentStep: number;
  pollingTimer: number | null;
  messages: Message[];
  isAgentLoading: boolean;
  agentContext: Record<string, unknown>;
  isLoginModalOpen: boolean;
  executionSteps: ExecutionStep[];
  xxtState: XxtState | null;
  xxtPollingTimer: number | null;
  fillScorePollingTimer: number | null;  // 🟢 新增：回填进度轮询定时器
  currentFillScoreMessageId: string | null;  // 🟢 新增：当前回填消息ID
  fillingClassMap: Record<string, string | null>;  // 🟢 新增：跟踪每个班级的回填状态（key: `${jobId}-${className}`, value: messageId）
  selectedModel: string;
  apiKey: string;
  criteria: string;
  feedbackStyle: string;
  gradingTargets: GradingTargets;
  isDarkMode: boolean;
  pendingFillScore: boolean;

  // 🟢 历史记录相关
  history: HistoryItem[];
  activeHistoryId: string | null;

  language: 'zh' | 'en';

  // 🟢 记录刚刚上传的文件 ID
  uploadedJobId: string | null;

  setLanguage: (lang: 'zh' | 'en') => void;

  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  uploadJob: (file: File) => Promise<void>;
  importFromXxt: () => Promise<void>;
  uploadCriteriaFile: (file: File) => Promise<string>;
  extractCriteria: (text: string) => Promise<{ success: boolean; extractedPoints?: string }>;
  startJob: (jobId: string, model: string, apiKey: string, criteria: string, feedbackStyle: string, gradingTargets?: GradingTargets) => Promise<void>;
  startJobs: (jobIds: string[], model: string, apiKey: string, criteria: string, feedbackStyle: string, gradingTargets?: GradingTargets) => Promise<void>;
  startBatchJobs: (batch: { name: string; jobId: string }[], model: string, apiKey: string, criteria: string, feedbackStyle: string, gradingTargets?: GradingTargets) => Promise<void>;
  startJobs: (jobIds: string[], model: string, apiKey: string, criteria: string, feedbackStyle: string, gradingTargets?: GradingTargets) => Promise<void>;
  pollJobStatus: (jobId?: string) => Promise<void>;
  exportResults: (jobId: string) => Promise<void>;
  retryFailedStudents: (studentIds: string[]) => Promise<void>;
  setCurrentStep: (step: number) => void;
  setSelectedModel: (model: string) => void;
  setApiKey: (key: string) => void;
  setCriteria: (criteria: string) => void;
  setFeedbackStyle: (style: string) => void;
  setGradingTargets: (targets: GradingTargets) => void;
  toggleTheme: () => void;
  setLoginModalOpen: (open: boolean) => void;
  resetJob: () => void;
  resetXxtSession: () => void;

  startNewConversation: () => void;
  loadConversation: (id: string) => void;
  deleteConversation: (id: string) => void;

  setCurrentPage: (page: 'landing' | 'agent' | 'legacy') => void;
  addMessage: (message: Message) => void;
  sendMessage: (content: string, files?: File[]) => Promise<void>;
  handleOptionSelect: (option: MessageOption) => Promise<void>;
  startXxtRunner: (mode: 'list_courses' | 'list_exams' | 'download', options?: Record<string, string | string[]>) => Promise<void>;
  pollXxtState: () => Promise<void>;
  stopXxtPolling: () => void;
  updateExecutionStep: (stepId: string, status: StepStatus) => void;
  authError: (message?: string) => void;
  
  // 🟢 新增：回填分数的方法，返回 messageId
  triggerScoreFill: (jobId: string, course: string, exam: string, className?: string) => Promise<string>;
}

export const useStore = create<AppState>()(
  persist(
    (set, get) => ({
      currentPage: 'landing',
      token: null,
      isLoggedIn: false,
      loginError: null,
        jobId: null,
        jobIds: [],
        batchJobs: [],
        lastJobId: null,
      jobStatus: null,
      jobProgress: null,
      jobResults: [],
      studentCount: 0,
      tokenUsageTotals: createEmptyTokenUsage(),
      retryingStudentIds: [],
      isLoading: false,
      currentStep: 0,
      pollingTimer: null,

      history: [],
      activeHistoryId: null,
      // 上传初始化为空
      uploadedJobId: null,

      messages: [
        {
          id: '1',
          type: 'agent',
          content: '你好！我是 WiseGrader。请告诉我你想批改哪门课程的作业，例如："帮我批改区块链课的期末考试"',
          timestamp: new Date(),
        },
      ],
      isAgentLoading: false,
      agentContext: {},
      isLoginModalOpen: false,
      executionSteps: [],
      xxtState: null,
      xxtPollingTimer: null,
      fillScorePollingTimer: null,  // 🟢 新增：回填进度轮询定时器
      currentFillScoreMessageId: null,  // 🟢 新增：当前回填消息ID
      fillingClassMap: {},  // 🟢 新增：跟踪每个班级的回填状态
      selectedModel: '',
      apiKey: '',
      criteria: '',
      feedbackStyle: 'detailed',
      gradingTargets: { passRate: '', excellentRate: '', minScore: '' },
      isDarkMode: false,
      pendingFillScore: false,
      language: navigator.language.startsWith('zh') ? 'zh' : 'en',

      setLanguage: (lang) => set({ language: lang }),

      login: async (username, password) => {
        set({ isLoading: true, loginError: null });
        try {
          const response = await api.login(username, password);
          set({ token: response.token, isLoggedIn: true, loginError: null, isLoading: false, xxtState: null, xxtPollingTimer: null });
        } catch (error: any) {
          const payload = error.response?.data;
          set({ loginError: payload?.error || payload?.message || '登录失败', isLoading: false });
          throw error;
        }
      },
      logout: () => {
        const timer = get().pollingTimer;
        if (timer) window.clearTimeout(timer);
          set({ token: null, isLoggedIn: false, loginError: null, jobId: null, lastJobId: null, jobStatus: null, jobProgress: null, jobResults: [], studentCount: 0, currentStep: 0, pollingTimer: null, tokenUsageTotals: createEmptyTokenUsage(), retryingStudentIds: [], pendingFillScore: false });
      },

      // 🟢 上传作业功能 
      uploadJob: async (file: File) => {
        set({ isLoading: true });
        try {
          const response = await api.uploadJob(file);
          set({
            jobId: response.jobId,
            uploadedJobId: response.jobId, // 🟢 关键：记下这个ID，后续对话要用
            studentCount: response.studentCount,
            jobStatus: 'uploaded',
            jobProgress: null,
            jobResults: [],
            tokenUsageTotals: createEmptyTokenUsage(),
            retryingStudentIds: [],
            isLoading: false,
            currentStep: 1,
          });

          // 🟢 移除系统提示消息（用户不需要看到）

        } catch (error) {
          set({ isLoading: false });
          throw error;
        }
      },

      // 🟢 恢复从学习通导入功能 (之前被缩略掉了)
      importFromXxt: async () => {
        set({ isLoading: true });
        try {
          const response = await api.importFromXxt();
          set({
            jobId: response.jobId,
            studentCount: response.studentCount,
            jobStatus: 'uploaded',
            jobProgress: null,
            jobResults: [],
            tokenUsageTotals: createEmptyTokenUsage(),
            retryingStudentIds: [],
            isLoading: false,
            currentStep: 1,
          });
        } catch (error) {
          set({ isLoading: false });
          throw error;
        }
      },

      // 🟢 恢复上传评分标准功能 (核心问题所在！)
      uploadCriteriaFile: async (file: File) => {
        set({ isLoading: true });
        try {
          const response = await api.uploadCriteriaFile(file);
          const extracted = response.criteriaText || response.extracted_text || '';
          set({
            criteria: extracted,
            isLoading: false,
          });
          // 必须返回字符串，ConfigSidebar 才能拿到
          return extracted;
        } catch (error) {
          set({ isLoading: false });
          throw error;
        }
      },

      // 🟢 恢复提取评分标准功能 (之前被缩略掉了)
      extractCriteria: async (text: string) => {
        set({ isLoading: true });
        try {
          const response = await api.extractCriteria(text);
          set({ isLoading: false });
          return {
            success: response.success,
            extractedPoints: response.extractedPoints,
          };
        } catch (error) {
          set({ isLoading: false });
          throw error;
        }
      },

      startJob: async (jobId: string, model: string, apiKey: string, criteria: string, feedbackStyle: string, gradingTargets?: GradingTargets) => {
        const totalStudents = get().studentCount;
        const targets = gradingTargets || get().gradingTargets;
        set({ isLoading: true, jobStatus: 'processing', jobProgress: totalStudents ? { completed: 0, total: totalStudents } : null });
        try {
          get().updateExecutionStep('4', 'running');
          await api.startJob(jobId, model, apiKey, criteria, feedbackStyle, targets);
          set({ jobStatus: 'processing', currentStep: 2, jobProgress: totalStudents ? { completed: 0, total: totalStudents } : null });
          await get().pollJobStatus(jobId);
        } catch (error) {
          set({ isLoading: false, jobStatus: 'uploaded', jobProgress: null });
          throw error;
        }
      },

      // 串行启动多个 jobId
      startJobs: async (jobIds: string[], model: string, apiKey: string, criteria: string, feedbackStyle: string, gradingTargets?: GradingTargets) => {
        for (const jid of jobIds) {
          await get().startJob(jid, model, apiKey, criteria, feedbackStyle, gradingTargets);
        }
      },

      // 串行启动 batchJobs，并更新状态
      startBatchJobs: async (batch, model, apiKey, criteria, feedbackStyle, gradingTargets) => {
        // 🟢 修复：批量任务应该并行启动所有任务，然后统一轮询状态
        // 而不是串行执行，避免状态混乱
        try {
          // 1. 标记所有任务为运行中
          set((state) => ({
            batchJobs: state.batchJobs.map((b) => {
              const found = batch.find(item => item.jobId === b.jobId);
              return found ? { ...b, status: 'running' as const } : b;
            }),
            isLoading: true,
            jobStatus: 'processing' as const,
          }));
          
          // 2. 并行启动所有任务（不等待完成）
          const startPromises = batch.map(async (item) => {
            try {
              get().updateExecutionStep('4', 'running');
              await api.startJob(item.jobId, model, apiKey, criteria, feedbackStyle, gradingTargets || {});
              return { jobId: item.jobId, success: true };
            } catch (e) {
              console.error(`Failed to start job ${item.jobId}:`, e);
              return { jobId: item.jobId, success: false };
            }
          });
          
          await Promise.all(startPromises);
          
          // 3. 开始统一轮询所有任务的状态（使用批量聚合模式）
          await get().pollJobStatus();
        } catch (e) {
          console.error('Batch job start failed:', e);
          set((state) => ({
            batchJobs: state.batchJobs.map((b) => {
              const found = batch.find(item => item.jobId === b.jobId);
              return found ? { ...b, status: 'failed' as const } : b;
            }),
            isLoading: false,
          }));
        }
      },

      // 串行启动多个 jobId
      startJobs: async (jobIds: string[], model: string, apiKey: string, criteria: string, feedbackStyle: string, gradingTargets?: GradingTargets) => {
        for (const jid of jobIds) {
          await get().startJob(jid, model, apiKey, criteria, feedbackStyle, gradingTargets);
        }
      },

      pollJobStatus: async (jobId?: string) => {
        const state = get();
        const existingTimer = state.pollingTimer;
        if (existingTimer) { window.clearTimeout(existingTimer); set({ pollingTimer: null }); }

        // 批量聚合模式
        if (state.batchJobs && state.batchJobs.length > 0) {
          try {
            const responses = await Promise.all(state.batchJobs.map((b) => api.getJobStatus(b.jobId)));

            let allResults: GradingResult[] = [];
            let totalCompleted = 0;
            let totalCount = 0;
            let anyProcessing = false;
            let anyFailed = false;

            responses.forEach((res, idx) => {
              const batchJob = state.batchJobs[idx];
              const jobId = batchJob?.jobId;
              const className = batchJob?.name || batchJob?.jobId || '';
              
              // 🟢 修复：为每个结果添加来源班级信息
              const normalized = (res.results || []).map((r: any) => {
                const result = mapResultFromApi(r);
                return {
                  ...result,
                  jobId: jobId,
                  className: className,
                };
              });
              allResults = allResults.concat(normalized);
              totalCompleted += res.progress?.completed || 0;
              totalCount += res.progress?.total || normalized.length;
              if (res.status === 'processing') anyProcessing = true;
              if (res.status === 'failed') anyFailed = true;
            });

            let finalStatus: JobStatus = 'completed';
            if (anyProcessing) finalStatus = 'processing';
            else if (anyFailed && totalCompleted === 0) finalStatus = 'failed';

            const usageTotals = sumTokenUsage(allResults);

            set({
              jobResults: allResults,
              jobProgress: { completed: totalCompleted, total: totalCount },
              jobStatus: finalStatus,
              studentCount: totalCount,
              tokenUsageTotals: usageTotals,
            });

            if (finalStatus === 'completed') {
              // 🟢 修复：确保轮询完全停止，并更新所有批量任务状态为完成
              set((state) => ({
                isLoading: false,
                currentStep: 3,
                pollingTimer: null,
                lastJobId: state.batchJobs[0]?.jobId || state.jobId,
                batchJobs: state.batchJobs.map((b, idx) => {
                  const response = responses[idx];
                  // 根据响应状态更新批量任务状态
                  if (response && response.status === 'completed') {
                    return { ...b, status: 'completed' as const };
                  } else if (response && response.status === 'failed') {
                    return { ...b, status: 'failed' as const };
                  }
                  return b;
                }),
              }));
              get().updateExecutionStep('4', 'completed');
              
              // 🟢 修复：批量任务完成时也添加完成消息
              const completedMessage: Message = {
                id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
                type: 'system',
                content: `✅ 批改完成！共批改 ${allResults.length} 份作业。`,
                timestamp: new Date(),
                gradingResults: allResults,
              };
              set((state) => {
                const lastMessage = state.messages[state.messages.length - 1];
                if (lastMessage?.content?.includes('批改完成')) return state;
                return { messages: [...state.messages, completedMessage] };
              });
              
              // 🟢 关键修复：确保不再继续轮询
              return;
            } else if (finalStatus === 'failed') {
              set({ isLoading: false, jobStatus: 'uploaded', jobProgress: null, pollingTimer: null });
              get().updateExecutionStep('4', 'failed');
              return; // 失败时也停止轮询
            } else if (finalStatus === 'processing') {
              // 🟢 修复：确保在设置新定时器前清除旧的定时器
              const currentTimer = get().pollingTimer;
              if (currentTimer) window.clearTimeout(currentTimer);
              const timerId = window.setTimeout(() => get().pollJobStatus(), 2000);
              set({ pollingTimer: timerId });
            } else {
              set({ pollingTimer: null });
              return; // 未知状态时停止轮询
            }
          } catch (error) {
            console.error('Polling error:', error);
            set({ isLoading: false, pollingTimer: null });
          }
          return;
        }

        // 单任务逻辑
        const activeJobId = jobId ?? state.jobId;
        if (!activeJobId) return;

        const poll = async () => {
          try {
            const response = await api.getJobStatus(activeJobId);
            const normalizedResults = (response.results || []).map(mapResultFromApi);
            const currentStudents = state.studentCount;
            const progress = deriveProgress(response.progress, normalizedResults, currentStudents);
            const nextStudentTotal = progress?.total ?? currentStudents;
            const usageTotals = sumTokenUsage(normalizedResults);

            set({ jobStatus: response.status, jobProgress: progress, jobResults: normalizedResults, studentCount: nextStudentTotal, tokenUsageTotals: usageTotals });

            if (response.status === 'completed') {
              // 🟢 修复：确保轮询完全停止，不要清空 uploadedJobId（需要保留用于结果显示）
              set({ isLoading: false, currentStep: 3, pollingTimer: null, lastJobId: activeJobId });
              get().updateExecutionStep('4', 'completed');
              
              // 🟢 修复：确保完成消息被正确添加，且结果能被显示
              const completedMessage: Message = {
                id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
                type: 'system',
                content: `✅ 批改完成！共批改 ${normalizedResults.length} 份作业。`,
                timestamp: new Date(),
                gradingResults: normalizedResults,
              };
              set((state) => {
                const lastMessage = state.messages[state.messages.length - 1];
                if (lastMessage?.content?.includes('批改完成')) return state;
                return { messages: [...state.messages, completedMessage] };
              });
              
              // 🟢 关键修复：确保不再继续轮询
              return; // 直接返回，不再继续执行
            } else if (response.status === 'failed') {
              set({ isLoading: false, jobStatus: 'uploaded', jobProgress: null, pollingTimer: null });
              get().updateExecutionStep('4', 'failed');
              return; // 失败时也停止轮询
            } else if (response.status === 'processing') {
              // 🟢 修复：确保在设置新定时器前清除旧的定时器
              const currentTimer = get().pollingTimer;
              if (currentTimer) window.clearTimeout(currentTimer);
              const timerId = window.setTimeout(poll, 2000);
              set({ pollingTimer: timerId });
            } else {
              set({ pollingTimer: null });
              return; // 未知状态时停止轮询
            }
          } catch (error) {
            console.error('Polling error:', error);
            set({ isLoading: false, pollingTimer: null });
          }
        };
        await poll();
      },

      exportResults: async (jobId) => {
        set({ isLoading: true });
        try {
          await api.exportJob(jobId);
          set({ isLoading: false });
        } catch (error) {
          set({ isLoading: false });
          throw error;
        }
      },

      // 🟢 新增：回填分数到学习通，返回 messageId
      triggerScoreFill: async (jobId: string, course: string, exam: string, className?: string): Promise<string> => {
        set({ isAgentLoading: true });
        
        try {
          // 🟢 1. 停止之前的轮询（如果存在）
          const stateSnapshot = get();
          if (stateSnapshot.fillScorePollingTimer) {
            clearTimeout(stateSnapshot.fillScorePollingTimer);
            set({ fillScorePollingTimer: null });
          }
          
          // 2. 调用 API（传入 className）
          await api.fillScoresToXxt(jobId, course, exam, className);
          
          // 3. 在聊天界面添加一条系统消息，告诉用户开始了
          const classNameText = className ? `（${className}）` : '';
          const messageId = `fill_${Date.now()}_${jobId}`;  // 🟢 生成唯一的消息ID
          const systemMessage: Message = {
            id: messageId,
            type: 'system',
            content: `🚀 自动回填指令已发送！\n正在将任务 [${jobId}]${classNameText} 的成绩同步至学习通课程《${course}》的《${exam}》...\n\n请查看浏览器窗口，完成登录和回填操作。`,
            timestamp: new Date(),
          };
          
          // 🟢 记录该班级正在回填
          const classKey = className ? `${jobId}-${className}` : jobId;
          set((state) => ({ 
            messages: [...state.messages, systemMessage],
            isAgentLoading: false,
            currentFillScoreMessageId: messageId,  // 🟢 记录当前回填消息ID
            fillingClassMap: { ...state.fillingClassMap, [classKey]: messageId },  // 🟢 记录该班级正在回填
          }));
          
          // 🟢 4. 新增：开始轮询回填进度状态（仅针对当前消息）
          // 启动轮询，检查回填进度
          const startPollingFillProgress = () => {
            let pollTimer: number | null = null;
            const poll = async () => {
              try {
                // 🟢 检查是否还是当前的回填任务
                const currentState = get();
                if (currentState.currentFillScoreMessageId !== messageId) {
                  console.log('[回填进度] 已切换到新的回填任务，停止轮询');
                  return; // 已切换任务，停止轮询
                }
                
                const response = await api.getXxtState();
                if (response?.success && response?.state) {
                  const fillState = response.state;
                  
                  // 🟢 再次检查是否还是当前的回填任务
                  const checkState = get();
                  if (checkState.currentFillScoreMessageId !== messageId) {
                    console.log('[回填进度] 已切换到新的回填任务，停止轮询');
                    return;
                  }
                  
                  set({ xxtState: fillState });
                  
                  // 如果回填完成或失败，停止轮询（但不清空 currentFillScoreMessageId，以便进度条继续显示）
                  if (fillState.stage === 'fill_score_completed' || 
                      fillState.stage === 'fill_score_partial' ||
                      fillState.stage?.includes('error')) {
                    console.log('[回填进度] 回填完成或失败，停止轮询');
                    // 🟢 清除该班级的回填状态（从 fillingClassMap 中移除）
                    const currentState = get();
                    const updatedMap = { ...currentState.fillingClassMap };
                    Object.keys(updatedMap).forEach(key => {
                      if (updatedMap[key] === messageId) {
                        updatedMap[key] = null;
                      }
                    });
                    set({ fillScorePollingTimer: null, fillingClassMap: updatedMap }); // 🟢 清除回填状态
                    return; // 停止轮询
                  }
                  
                  // 继续轮询
                  pollTimer = window.setTimeout(poll, 2000); // 每2秒轮询一次
                  set({ fillScorePollingTimer: pollTimer });
                } else {
                  // 如果获取状态失败，也继续轮询
                  pollTimer = window.setTimeout(poll, 3000);
                  set({ fillScorePollingTimer: pollTimer });
                }
              } catch (error) {
                console.error('轮询回填进度失败:', error);
                // 🟢 检查是否还是当前的回填任务
                const errorState = get();
                if (errorState.currentFillScoreMessageId !== messageId) {
                  console.log('[回填进度] 已切换到新的回填任务，停止轮询');
                  return;
                }
                // 出错时也继续轮询（可能只是暂时性错误）
                pollTimer = window.setTimeout(poll, 3000);
                set({ fillScorePollingTimer: pollTimer });
              }
            };
            // 延迟一下再开始轮询，给后端一点时间启动
            pollTimer = window.setTimeout(poll, 1000);
            set({ fillScorePollingTimer: pollTimer });
          };
          
          startPollingFillProgress();
          
          // 🟢 返回 messageId 以便滚动到消息
          return messageId;

        } catch (error: any) {
          // 处理错误
          const errorMessage: Message = {
            id: Date.now().toString(),
            type: 'system',
            content: `❌ 回填启动失败: ${error.response?.data?.error || error.message || '未知错误'}`,
            timestamp: new Date(),
          };
          set((state) => ({ 
            messages: [...state.messages, errorMessage],
            isAgentLoading: false 
          }));
          throw error; // 🟢 重新抛出错误
        }
      },

      retryFailedStudents: async (studentIds) => {
        // 简化起见，保留核心逻辑
        const uniqueIds = Array.from(new Set(studentIds.map((id) => id?.toString().trim()).filter((id): id is string => Boolean(id))));
        const { jobId, selectedModel, apiKey, criteria, feedbackStyle, gradingTargets } = get();
        if (!jobId || uniqueIds.length === 0) return;

        set((state) => {
          // ... retry state update logic ...
          return { ...state, jobStatus: 'processing' };
        });

        try {
          await api.retryStudents(jobId, uniqueIds, selectedModel, apiKey, criteria, feedbackStyle, gradingTargets);
          await get().pollJobStatus(jobId);
        } finally {
          // ... cleanup ...
        }
      },

      setCurrentStep: (step) => set({ currentStep: step }),
      setSelectedModel: (model) => set({ selectedModel: model }),
      setApiKey: (key) => set({ apiKey: key }),
      setCriteria: (criteria) => set({ criteria }),
      setFeedbackStyle: (style) => set({ feedbackStyle: style }),
      setGradingTargets: (targets) => set({ gradingTargets: targets }),
      toggleTheme: () => set((state) => ({ isDarkMode: !state.isDarkMode })),
      setLoginModalOpen: (open) => set({ isLoginModalOpen: open }),

      resetJob: () => {
        const timer = get().pollingTimer;
        if (timer !== null) window.clearTimeout(timer);
        set({
          jobId: null, jobStatus: null, jobProgress: null, jobResults: [], studentCount: 0, currentStep: 0,
          pollingTimer: null, retryingStudentIds: [],uploadedJobId: null,
        });
      },

      resetXxtSession: () => {
        const timer = get().xxtPollingTimer;
        if (timer) window.clearTimeout(timer);
        // 🟢 新增：清理回填进度轮询定时器
        const fillScoreTimer = get().fillScorePollingTimer;
        if (fillScoreTimer) window.clearTimeout(fillScoreTimer);
        set({
          xxtState: null, jobId: null, xxtPollingTimer: null,
          fillScorePollingTimer: null,  // 🟢 清理回填进度轮询定时器
          currentFillScoreMessageId: null,  // 🟢 清理当前回填消息ID
          executionSteps: [
            { id: '1', title: '登录学习通', description: '扫描二维码登录', status: 'pending', icon: 'qr' },
            { id: '2', title: '选择课程与考试', description: '获取可用课程列表', status: 'pending', icon: 'file' },
            { id: '3', title: '下载作业', description: '从学习通下载学生作业', status: 'pending', icon: 'download' },
            { id: '4', title: 'AI 批改', description: '智能批改并生成评语', status: 'pending', icon: 'sparkles' },
          ],
        });
      },

      startNewConversation: () => {
        const state = get();
        if (state.messages.length > 1) {
          const firstUserMsg = state.messages.find(m => m.type === 'user');
          const title = firstUserMsg
            ? (firstUserMsg.content.length > 20 ? firstUserMsg.content.substring(0, 20) + '...' : firstUserMsg.content)
            : '未命名对话';

          const currentConversationData = {
            title: title,
            timestamp: Date.now(),
            messages: state.messages,
            executionSteps: state.executionSteps,
            agentContext: state.agentContext,
            jobId: state.jobId
          };

          if (state.activeHistoryId) {
            const updatedHistory = state.history.filter(item => item.id !== state.activeHistoryId);
            const updatedItem = { ...currentConversationData, id: state.activeHistoryId };
            set({ history: [updatedItem, ...updatedHistory] });
          } else {
            const newItem: HistoryItem = { id: Date.now().toString(), ...currentConversationData };
            set({ history: [newItem, ...state.history] });
          }
        }

        if (state.pollingTimer) clearTimeout(state.pollingTimer);
        if (state.xxtPollingTimer) clearTimeout(state.xxtPollingTimer);
        // 🟢 新增：清理回填进度轮询定时器
        if (state.fillScorePollingTimer) clearTimeout(state.fillScorePollingTimer);

        set({
          messages: [{ id: '1', type: 'agent', content: '你好！我是 WiseGrader。请告诉我你想批改哪门课程的作业，例如："帮我批改区块链课的期末考试"', timestamp: new Date() }],
          isAgentLoading: false, agentContext: {}, jobId: null, jobStatus: null, jobProgress: null, jobResults: [], studentCount: 0,
           executionSteps: [], xxtState: null, currentStep: 0, pollingTimer: null, xxtPollingTimer: null, 
           fillScorePollingTimer: null, currentFillScoreMessageId: null, fillingClassMap: {},  // 🟢 新增：清理回填进度相关状态
           activeHistoryId: null,uploadedJobId: null,
        });
      },

      loadConversation: (id: string) => {
        const state = get();
        const targetItem = state.history.find(item => item.id === id);
        if (targetItem) {
          if (state.pollingTimer) clearTimeout(state.pollingTimer);
          if (state.xxtPollingTimer) clearTimeout(state.xxtPollingTimer);
          // 🟢 新增：清理回填进度轮询定时器
          if (state.fillScorePollingTimer) clearTimeout(state.fillScorePollingTimer);
          const hydratedMessages = targetItem.messages.map((msg) => ({
            ...msg,
            // 无论它是字符串还是Date，new Date() 都能把它变成真正的 Date 对象
            timestamp: new Date(msg.timestamp),
          }));

          set({
            messages: hydratedMessages,
            executionSteps: targetItem.executionSteps,
            agentContext: targetItem.agentContext,
            jobId: targetItem.jobId,
            isAgentLoading: false,
            xxtState: null,
            fillScorePollingTimer: null,  // 🟢 清理回填进度轮询定时器
            currentFillScoreMessageId: null,  // 🟢 清理当前回填消息ID
            fillingClassMap: {},  // 🟢 清理回填状态映射
            activeHistoryId: targetItem.id
          });
        }
      },

      deleteConversation: (id: string) => {
        set((state) => ({
          history: state.history.filter(item => item.id !== id),
          activeHistoryId: state.activeHistoryId === id ? null : state.activeHistoryId
        }));
      },

      setCurrentPage: (page: 'landing' | 'agent' | 'legacy') => set({ currentPage: page }),
      addMessage: (message: Message) => set((state) => ({ messages: [...state.messages, message] })),


      //传到后端！
      // 🟢 修改：增加 files 参数，默认为空数组
      // 🟢 修复版 sendMessage：支持文件参数 + 历史记录 + 跳过下载
      sendMessage: async (content: string, files: File[] = []) => {
        // 1. 创建用户消息（包含文件信息）
        const userMessage: Message = {
          id: Date.now().toString(),
          type: 'user',
          content,
          timestamp: new Date(),
          // 🟢 关键：保存文件列表，这样界面上才能显示文件卡片
          files: files.map(f => ({ name: f.name, size: f.size }))
        };

        set((state) => ({ messages: [...state.messages, userMessage], isAgentLoading: true }));

        try {
          const stateSnapshot = get();

          // 🟢 1. 获取当前的评分标准
          const currentCriteria = stateSnapshot.criteria;

          // 🟢 1. 预处理：如果有非 ZIP 文件，先提取内容
          let documentContext = "";

          if (files.length > 0) {
            for (const file of files) {
              if (file.name.toLowerCase().endsWith('.zip')) continue;
              try {
                // 🟢 修改：传入 currentCriteria
                const res = await api.uploadChatFile(file, currentCriteria);
                
                if (res.success && res.text) {
                  documentContext += `\n\n【文件内容：${file.name}】\n${res.text.slice(0, 15000)}\n----------------\n`;
                }
              } catch (err) {
                console.error(err);
              }
            }
          }

          // 🟢 2. 构造 context，把提取到的 documentContext 放进去
          const fillKeywords = ['回填', '填分', '同步成绩', '同步分数', '上传成绩', '把分数填回去', '回填分数'];
          const hasFillKeyword = fillKeywords.some((k) => content.includes(k));
          const pendingFillScore = hasFillKeyword || stateSnapshot.pendingFillScore;
          if (pendingFillScore !== stateSnapshot.pendingFillScore) {
            set({ pendingFillScore });
          }

          const context = {
            ...stateSnapshot.agentContext,
            uploadedJobId: stateSnapshot.uploadedJobId,
            lastJobId: stateSnapshot.lastJobId,
            currentJobId: stateSnapshot.jobId,
            pendingFillScore,
            currentChatFiles: files.map(f => f.name),

            // 👇 把提取出的“文件内容”塞给 AI
            fileContent: documentContext
          };

          const response = await api.sendAgentMessage(content, context);

          const agentMessage: Message = {
            id: (Date.now() + 1).toString(),
            type: 'agent',
            content: typeof response?.message === 'string' ? response.message : 'AI 暂时无法回应',
            timestamp: new Date(),
            options: (response?.options as MessageOption[]) ?? undefined,
            metadata: { stage: response?.stage, session: response?.session },
          };
          const shouldClearFill = typeof response?.message === 'string' && (
            response.message.includes('回填任务已启动') ||
            response.message.includes('无法回填') ||
            response.message.includes('请先进行批改') ||
            response.message.includes('找不到当前批改任务')
          );
          set((state) => ({
            messages: [...state.messages, agentMessage],
            agentContext: { ...state.agentContext, ...(response?.session ?? {}) },
            isAgentLoading: false,
            pendingFillScore: shouldClearFill ? false : state.pendingFillScore,
          }));

          const nextAction = response?.nextAction;

          // 🟢 核心修改：导出逻辑 (变自动下载为更新消息卡片)
          if (nextAction?.type === 'trigger_export' && nextAction.jobId) {
            set((state) => {
              const newMessages = [...state.messages];
              // 找到最后一条 AI 消息（即那条“好的，正在生成...”）
              const lastMsgIndex = newMessages.length - 1;

              if (lastMsgIndex >= 0 && newMessages[lastMsgIndex].type === 'agent') {
                // 1. 动态修改文字
                newMessages[lastMsgIndex].content = "✅ 成绩单生成成功！请点击下方文件下载。";

                // 2. 挂载文件附件数据
                newMessages[lastMsgIndex].downloadFiles = [{
                  name: `成绩单_${nextAction.jobId}.xlsx`, // 文件名
                  jobId: nextAction.jobId
                }];
              }
              return { messages: newMessages };
            });
            return; // 结束，不再自动调用下载函数
          }
          if (nextAction?.type === 'start_runner') {

            // 3. 处理“跳过下载”逻辑 (本地文件批改)
            if (nextAction.skipDownload && nextAction.jobId) {
              set({
                executionSteps: [
                  { id: '1', title: '文件上传', status: 'completed', icon: 'file' },
                  { id: '2', title: '解析作业包', status: 'completed', icon: 'download' },
                  { id: '3', title: '准备批改', status: 'completed', icon: 'sparkles' },
                  { id: '4', title: 'AI 批改', status: 'running', icon: 'sparkles' },
                ],
                jobId: nextAction.jobId,
                isAgentLoading: false
              });

              const s = get();
              try {
                await get().startJob(
                  nextAction.jobId,
                  s.selectedModel,
                  s.apiKey,
                  s.criteria,
                  s.feedbackStyle,
                  s.gradingTargets
                );
              } catch (e) {
                console.error(e);
              }
              return;
            }

            // 4. 原有学习通下载逻辑
            get().resetXxtSession();
            set({ isAgentLoading: true });
            try {
              await get().startXxtRunner('download', { course: nextAction.course, exam: nextAction.exam, sidebar: nextAction.sidebar, autoMatch: 'true' });
            } catch (runnerError) {
              const runnerMessage: Message = { id: (Date.now() + 2).toString(), type: 'system', content: `❌ 自动下载失败：${runnerError instanceof Error ? runnerError.message : '未知错误'}`, timestamp: new Date() };
              set((state) => ({ messages: [...state.messages, runnerMessage] }));
            } finally { set({ isAgentLoading: false }); }
          }
        } catch (error) {
          const errorMessage: Message = { id: (Date.now() + 1).toString(), type: 'system', content: `AI 对话失败：${error instanceof Error ? error.message : '未知错误'}`, timestamp: new Date() };
          set((state) => ({ messages: [...state.messages, errorMessage], isAgentLoading: false }));
        }
      },

      handleOptionSelect: async (_option: MessageOption) => { /* ... */ },

      startXxtRunner: async (mode: 'list_courses' | 'list_exams' | 'download', options: Record<string, string | string[]> = {}) => {
        set({ isLoading: true });
        try {
          await api.startXxtRunner({ mode, ...options });
          if (mode === 'list_courses' || mode === 'download') get().updateExecutionStep('1', 'running');
          get().pollXxtState();
          set({ isLoading: false });
        } catch (error: any) {
          const status = error.response?.status;
          if (status === 409) {
            if (mode === 'list_courses' || mode === 'download') get().updateExecutionStep('1', 'running');
            get().pollXxtState();
            set({ isLoading: false });
            return;
          }
          set({ isLoading: false });
          throw error;
        }
      },

      authError: (_message?: string) => { /* ... */ },
      pollXxtState: async () => {
        try {
          const response = await api.getXxtState();
          if (!response || !response.success) {
            setTimeout(() => get().pollXxtState(), 3000);
            return;
          }
          const xxtState = response.state || {};
          set((state) => ({ xxtState: { ...state.xxtState, ...xxtState } }));

          // 批次任务模式：batchJobs 优先
          if (Array.isArray(xxtState.batchJobs) && xxtState.batchJobs.length > 0) {
            const normalized = xxtState.batchJobs
              .map((b: any) => ({ name: b.name || b.className || '', jobId: b.jobId || '', status: 'pending' as const }))
              .filter((b: any) => b.jobId);
            if (normalized.length > 0) {
              set({
                batchJobs: normalized,
                jobIds: normalized.map((b) => b.jobId),
                jobId: normalized[0].jobId,
                jobStatus: 'uploaded',
              });
            }
          } else if (Array.isArray(xxtState.jobIds) && xxtState.jobIds.length > 0) {
            set({ jobIds: xxtState.jobIds, jobId: xxtState.jobIds[0], jobStatus: 'uploaded' });
          }

          const stage = xxtState.stage || '';
          
          // 🟢 调试：打印状态信息
          if (stage === 'waiting_login') {
            console.log('[XXT] waiting_login 状态，qrImage:', xxtState.qrImage);
            get().updateExecutionStep('1', 'running');
          }
          
          if (!stage) { setTimeout(() => get().pollXxtState(), 3000); return; }

          if (stage.startsWith('fill_score')) {
            if (stage.includes('login')) {
              get().updateExecutionStep('1', 'completed');
              get().updateExecutionStep('2', 'running');
            } else if (stage.includes('course') || stage.includes('exam')) {
              get().updateExecutionStep('1', 'completed');
              get().updateExecutionStep('2', 'completed');
              get().updateExecutionStep('3', 'running');
            } else if (stage.includes('running')) {
              get().updateExecutionStep('1', 'completed');
              get().updateExecutionStep('2', 'completed');
              get().updateExecutionStep('3', 'running');
            } else if (stage.includes('completed')) {
              get().updateExecutionStep('1', 'completed');
              get().updateExecutionStep('2', 'completed');
              get().updateExecutionStep('3', 'completed');
              get().updateExecutionStep('4', 'completed');
            } else if (stage.includes('partial') || stage.includes('error')) {
              get().updateExecutionStep('1', 'completed');
              get().updateExecutionStep('2', 'completed');
              get().updateExecutionStep('3', 'completed');
              get().updateExecutionStep('4', 'failed');
            }

            if (!stage.includes('completed') && !stage.includes('partial') && !stage.includes('error')) {
              setTimeout(() => get().pollXxtState(), 3000);
            } else {
              set({ isAgentLoading: false });
            }
            return;
          }

          if (stage.includes('login') || stage.includes('qr')) {
            get().updateExecutionStep('1', 'running');
          } else if (stage.includes('course') || stage.includes('exam')) {
            get().updateExecutionStep('1', 'completed');
            get().updateExecutionStep('2', 'running');
          } else if (stage.includes('download') && !stage.includes('complete')) {
            get().updateExecutionStep('1', 'completed');
            get().updateExecutionStep('2', 'completed');
            get().updateExecutionStep('3', 'running');
          } else if (stage.includes('download_complete')) {
            get().updateExecutionStep('2', 'completed');
            get().updateExecutionStep('3', 'completed');
          } else if (stage.includes('completed') || xxtState.jobId) {
            // 确保前端步骤 1-3 全部收尾，防止“选择课程/考试”卡住
            get().updateExecutionStep('1', 'completed');
            get().updateExecutionStep('2', 'completed');
            get().updateExecutionStep('3', 'completed');

            // 核心修改：批量优先，且防重复触发
            const state = get();
            const step4Status = state.executionSteps.find(s => s.id === '4')?.status;

            if (step4Status === 'pending') {
              // 1) 批量任务优先
              if (state.batchJobs.length > 0) {
                console.log('[自动批改] 检测到批量任务，准备启动...', state.batchJobs);
                get().updateExecutionStep('4', 'running');
                set({ isAgentLoading: true });

                setTimeout(async () => {
                  try {
                    const s = get();
                    await s.startBatchJobs(
                      s.batchJobs,
                      s.selectedModel,
                      s.apiKey,
                      s.criteria,
                      s.feedbackStyle,
                      s.gradingTargets
                    );
                    set({ isAgentLoading: false });
                  } catch (e) {
                    console.error('[自动批改] 批量启动失败', e);
                    get().updateExecutionStep('4', 'failed');
                    set({ isAgentLoading: false });
                  }
                }, 500);
              }
              // 2) 兜底：无批量则跑单任务
              else if (xxtState.jobId && xxtState.jobId !== state.jobId) {
                console.log('[自动批改] 启动单任务...', xxtState.jobId);
                set({ jobId: xxtState.jobId, isAgentLoading: true });
                get().updateExecutionStep('4', 'running');

                setTimeout(async () => {
                  try {
                    const s = get();
                    await s.startJob(
                      xxtState.jobId!,
                      s.selectedModel,
                      s.apiKey,
                      s.criteria,
                      s.feedbackStyle,
                      s.gradingTargets
                    );
                    set({ isAgentLoading: false });
                  } catch (e) {
                    set({ isAgentLoading: false });
                  }
                }, 500);
              }
            }
          }

          // 🟢 关键修复：waiting_login 状态也需要继续轮询，以便获取更新的 qrImage
          if (!stage.includes('completed') && !stage.includes('error')) {
            setTimeout(() => get().pollXxtState(), 3000);
          } else {
            set({ isAgentLoading: false });
          }
        } catch (e) { set({ isAgentLoading: false }); }
      },
      stopXxtPolling: () => { /* ... */ },
      updateExecutionStep: (stepId: string, status: StepStatus) => {
        set((state) => {
          const updatedSteps = state.executionSteps.map((step) => step.id === stepId ? { ...step, status } : step);
          const messages = [...state.messages];
          for (let i = messages.length - 1; i >= 0; i--) {
            if (messages[i].executionSteps?.length) {
              messages[i] = { ...messages[i], executionSteps: updatedSteps, isExecuting: updatedSteps.some(s => s.status === 'running') };
              break;
            }
          }
          return { executionSteps: updatedSteps, messages };
        });
      },
    }),
    {
      name: 'ai-grading-storage',
      partialize: (state) => ({
        isDarkMode: state.isDarkMode,
        selectedModel: state.selectedModel,
        apiKey: state.apiKey,
        criteria: state.criteria,
        feedbackStyle: state.feedbackStyle,
        gradingTargets: state.gradingTargets,
        history: state.history,
        language: state.language,
        uploadedJobId: state.uploadedJobId,
        lastJobId: state.lastJobId,
        batchJobs: state.batchJobs,
        jobIds: state.jobIds,
      }),
    }
  )
);

apiClient.interceptors.request.use((config) => {
  const token = useStore.getState().token;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
}, e => Promise.reject(e));

apiClient.interceptors.response.use(r => r, (error: AxiosError) => {
  if (error.response?.status === 401) console.warn('401 Ignored in guest mode');
  return Promise.reject(error);
});
