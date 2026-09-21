import axios from 'axios';
import type { AxiosInstance } from 'axios';
import { useStore } from './store';

// 🟢 统一的 API 基础 URL 配置
// 支持环境变量，如果没有设置则使用默认值
// 开发环境：http://127.0.0.1:5000
// 生产环境：通过环境变量 VITE_API_BASE_URL 配置（如：https://api.example.com）
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || (import.meta.env.PROD ? '' : 'http://127.0.0.1:5000');

// Create axios instance with base configuration
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000, // 5 minutes for long-running grading operations
  withCredentials: true, // 加上这一行！关键！
  headers: {
    'Content-Type': 'application/json',
  },
});



// API Functions

/**
 * Login to get authentication token
 */
export const login = async (username: string, password: string) => {
  const response = await apiClient.post('/api/login', {
    username,
    password,
  });
  return response.data;
};

/**
 * Upload outer ZIP file containing student submissions
 */
export const uploadJob = async (file: File) => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await apiClient.post('/api/upload/jobs', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

/**
 * Upload grading criteria file (PDF or DOCX)
 */
export const uploadCriteriaFile = async (file: File) => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await apiClient.post('/api/upload/criteria-file', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

/**
 * Upload a file specifically for chat context (returns extracted text)
 */
export const uploadChatFile = async (file: File, criteria?: string) => {
  const formData = new FormData();
  formData.append('file', file);
  if (criteria) {
    formData.append('criteria', criteria); // 把标准放进表单数据
  }

  const response = await apiClient.post('/api/upload/chat-file', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data; 
};




/**
 * Extract grading criteria from text (Mock in Phase 1)
 */
export const extractCriteria = async (text: string) => {
  const response = await apiClient.post('/api/criteria/extract', {
    criteriaText: text,  // 修复：使用驼峰命名
  });
  return response.data;
};

/**
 * Start grading job (Synchronous in Phase 1)
 */
export const startJob = async (
  jobId: string,
  model: string,
  apiKey: string,
  criteria: string,
  feedbackStyle: string,
  gradingTargets?: {
    passRate: number | '';
    excellentRate: number | '';
    minScore: number | '';
  }
) => {
  const response = await apiClient.post('/api/jobs/start', {
    jobId: jobId,  // 修复：使用驼峰命名
    model,
    apiKey: apiKey,  // 修复：使用驼峰命名
    gradingCriteria: criteria,  // 修复：使用后端期望的参数名
    feedbackStyle: feedbackStyle,  // 修复：使用驼峰命名
    gradingTargets: gradingTargets,  // 添加教学指标
  });
  return response.data;
};

/**
 * Retry grading for a subset of students
 */
export const retryStudents = async (
  jobId: string,
  studentIds: string[],
  model: string,
  apiKey: string,
  criteria: string,
  feedbackStyle: string,
  gradingTargets?: {
    passRate: number | '';
    excellentRate: number | '';
    minScore: number | '';
  }
) => {
  const response = await apiClient.post('/api/jobs/retry', {
    jobId,
    studentIds,
    model,
    apiKey,
    gradingCriteria: criteria,
    feedbackStyle,
    gradingTargets,
  });
  return response.data;
};

/**
 * Get job status and results
 */
export const getJobStatus = async (jobId: string) => {
  const response = await apiClient.get(`/api/jobs/status/${jobId}`);
  return response.data;
};

/**
 * Export job results to Excel file
 */
export const exportJob = async (jobId: string) => {
  const response = await apiClient.get(`/api/jobs/export/${jobId}`, {
    responseType: 'blob',
  });

  // Extract filename from Content-Disposition header or use default
  const contentDisposition = response.headers['content-disposition'];
  let filename = 'grading_results.xlsx';

  if (contentDisposition) {
    const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
    if (filenameMatch && filenameMatch[1]) {
      filename = filenameMatch[1].replace(/['"]/g, '');
      // Decode URI-encoded filename
      try {
        filename = decodeURIComponent(filename);
      } catch (e) {
        console.warn('Failed to decode filename:', e);
      }
    }
  }

  // Create download link and trigger download
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);

  return response.data;
};

/**
 * Import job from Xuexitong (Learning Pass) download directory
 */
export const importFromXxt = async (options?: {
  directory?: string;
  pattern?: string;
  recursive?: boolean;
}) => {
  const response = await apiClient.post('/api/xxt/import', options || {});
  return response.data;
};

/**
 * Get Xuexitong runner state
 */
export const getXxtState = async () => {
  const response = await apiClient.get('/api/xxt/state');
  return response.data;
};

/**
 * Start Xuexitong runner with specific mode
 */
export const startXxtRunner = async (options: {
  mode: 'list_courses' | 'list_exams' | 'download';
  course?: string;
  exam?: string;
  sidebar?: string;
  classes?: string[] | string;
}) => {
  const response = await apiClient.post('/api/xxt/start', options);
  return response.data;
};

/**
 * Get list of courses from Xuexitong
 */
export const getXxtCourses = async (options?: { sidebar?: string }) => {
  const response = await apiClient.post('/api/xxt/courses', options ?? {});
  return response.data;
};

/**
 * Get list of exams for a course from Xuexitong
 */
export const getXxtExams = async (course: string, sidebar?: string) => {
  const payload = sidebar ? { course, sidebar } : { course };
  const response = await apiClient.post('/api/xxt/exams', payload);
  return response.data;
};

/**
 * Agent conversation API
 */
export const sendAgentMessage = async (message: string, context?: Record<string, unknown>) => {
  // 1. 从 Store 中获取当前的配置信息
  // 🟢 修改：多获取一个 criteria
  const { apiKey, selectedModel, language, criteria } = useStore.getState();

  const response = await apiClient.post('/api/agent', {
    message,
    context,
    apiKey: apiKey,
    model: selectedModel,
    language: language,
    criteria: criteria // 🟢 传给后端，确保 Session 同步
  });
  return response.data;
};

/**
 * Fill scores back to Xuexitong (Learning Pass)
 */
export const fillScoresToXxt = async (jobId: string, course: string, exam: string, className?: string) => {
  const response = await apiClient.post('/api/xxt/fill_scores', {
    jobId,
    course,
    exam,
    className, // 🟢 新增：传递班级名称
  });
  return response.data;
};

export default apiClient;
