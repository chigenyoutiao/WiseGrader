import { useState } from 'react';
import { Dialog } from '@headlessui/react';
import { LogIn, AlertCircle, X, UserPlus, ArrowRight, Shield, Sparkles } from 'lucide-react';
import { useStore } from '../store';

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function LoginModal({ isOpen, onClose }: LoginModalProps) {
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [email, setEmail] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [registerInfo, setRegisterInfo] = useState<string | null>(null);
  const { login, loginError, isLoading } = useStore();

  const resetForm = () => {
    setUsername('');
    setPassword('');
    setEmail('');
    setConfirmPassword('');
    setRegisterInfo(null);
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await login(username, password);
      onClose();
      resetForm();
      setAuthMode('login');
    } catch (error) {
      console.error('Login failed:', error);
    }
  };

  const handleRegister = (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || !email || !password || !confirmPassword) {
      setRegisterInfo('请完整填写注册信息');
      return;
    }
    if (password !== confirmPassword) {
      setRegisterInfo('两次输入的密码不一致');
      return;
    }
    setRegisterInfo('注册功能即将上线，当前仅支持先登录体验。');
  };

  const openFullRegisterPage = () => {
    onClose();
    resetForm();
    setAuthMode('login');
    // Note: Register page navigation removed as 'register' is not a valid page type
  };

  const renderLoginForm = () => (
    <form onSubmit={handleLogin} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          用户名
        </label>
        <input
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="w-full px-4 py-2.5 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl text-gray-900 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
          placeholder="teacher"
          required
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          密码
        </label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full px-4 py-2.5 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl text-gray-900 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
          placeholder="******"
          required
        />
      </div>
      {loginError && (
        <div className="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl">
          <AlertCircle className="w-4 h-4 text-red-600 dark:text-red-400 flex-shrink-0" />
          <p className="text-sm text-red-600 dark:text-red-400">{loginError}</p>
        </div>
      )}
      <button
        type="submit"
        disabled={isLoading}
        className="w-full py-3 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-semibold rounded-xl shadow-lg hover:shadow-xl transform hover:scale-[1.01] active:scale-[0.99] transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
      >
        {isLoading ? (
          <>
            <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
            <span>登录中...</span>
          </>
        ) : (
          <>
            <LogIn className="w-5 h-5" />
            <span>登录</span>
          </>
        )}
      </button>
    </form>
  );

  const renderRegisterForm = () => (
    <form onSubmit={handleRegister} className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            用户名
          </label>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="w-full px-4 py-2.5 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl text-gray-900 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all"
            placeholder="输入昵称或工号"
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            邮箱
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full px-4 py-2.5 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl text-gray-900 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all"
            placeholder="name@example.com"
            required
          />
        </div>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            密码
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full px-4 py-2.5 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl text-gray-900 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all"
            placeholder="至少 8 位，包含字母和数字"
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            确认密码
          </label>
          <input
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="w-full px-4 py-2.5 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl text-gray-900 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all"
            placeholder="请再次输入密码"
            required
          />
        </div>
      </div>
      {registerInfo && (
        <div className="text-sm text-emerald-600 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-100 dark:border-emerald-800 rounded-xl px-3 py-2">
          {registerInfo}
        </div>
      )}
      <button
        type="submit"
        className="w-full py-3 bg-gradient-to-r from-emerald-500 to-cyan-500 hover:from-emerald-600 hover:to-cyan-600 text-white font-semibold rounded-xl shadow-lg hover:shadow-xl transform hover:scale-[1.01] active:scale-[0.99] transition-all duration-300 flex items-center justify-center gap-2"
      >
        <UserPlus className="w-5 h-5" />
        <span>提交注册</span>
      </button>
    </form>
  );

  return (
    <Dialog open={isOpen} onClose={onClose} className="relative z-50">
      <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" aria-hidden="true" />
      <div className="fixed inset-0 flex items-center justify-center p-4">
        <Dialog.Panel className="relative w-full max-w-4xl bg-white dark:bg-gray-900 rounded-3xl shadow-2xl overflow-hidden">
          <button
            onClick={() => {
              onClose();
              resetForm();
              setAuthMode('login');
            }}
            className="absolute top-4 right-4 z-10 p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-full transition-colors"
          >
            <X className="w-5 h-5" />
          </button>

          <div className="grid grid-cols-1 md:grid-cols-5">
            <div className="relative col-span-2 bg-slate-900 text-white p-8 flex flex-col justify-between overflow-hidden">
              <div>
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 text-xs tracking-[0.3em] uppercase">
                  <Sparkles className="w-3 h-3" />
                  AI
                </div>
                <h2 className="mt-6 text-3xl font-bold leading-tight">
                  WiseGrader
                  <br />
                  智能批改工作台
                </h2>
                <p className="mt-4 text-sm text-white/80">
                  登录后同步作业配置与批改历史，注册账号即可保存评分标准与模型偏好。
                </p>
              </div>
              <div className="space-y-3 text-sm text-white/70">
                <div className="flex items-center gap-3">
                  <Shield className="w-4 h-4" />
                  企业级数据加密
                </div>
                <div className="flex items-center gap-3">
                  <UserPlus className="w-4 h-4" />
                  多角色协作与共享
                </div>
                <div className="flex items-center gap-3">
                  <Sparkles className="w-4 h-4" />
                  AI 智能反馈模板
                </div>
              </div>
              <div className="absolute inset-0 pointer-events-none opacity-40">
                <div className="absolute -top-10 -right-16 w-48 h-48 bg-indigo-500 rounded-full blur-3xl" />
                <div className="absolute bottom-0 -left-10 w-36 h-36 bg-purple-500 rounded-full blur-3xl" />
              </div>
            </div>

            <div className="col-span-3 p-8 md:p-10">
              <div className="flex items-center gap-4 mb-6">
                <button
                  onClick={() => {
                    setAuthMode('login');
                    setRegisterInfo(null);
                  }}
                  className={`flex-1 py-2 rounded-xl font-semibold transition-all ${
                    authMode === 'login'
                      ? 'bg-indigo-50 text-indigo-600 border border-indigo-100 dark:bg-indigo-900/30 dark:text-indigo-200 dark:border-indigo-800'
                      : 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-300'
                  }`}
                >
                  登录
                </button>
                <button
                  onClick={() => {
                    setAuthMode('register');
                    setRegisterInfo(null);
                  }}
                  className={`flex-1 py-2 rounded-xl font-semibold transition-all ${
                    authMode === 'register'
                      ? 'bg-emerald-50 text-emerald-600 border border-emerald-100 dark:bg-emerald-900/30 dark:text-emerald-200 dark:border-emerald-800'
                      : 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-300'
                  }`}
                >
                  注册
                </button>
              </div>

              <div className="space-y-2 mb-6">
                <h3 className="text-2xl font-semibold text-gray-900 dark:text-white">
                  {authMode === 'login' ? '欢迎回来' : '创建新账户'}
                </h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  {authMode === 'login'
                    ? '输入账号密码即可继续批改工作。'
                    : '注册后可保存模型配置、批改模板与历史记录。'}
                </p>
              </div>

              {authMode === 'login' ? renderLoginForm() : renderRegisterForm()}

              <div className="mt-6 flex flex-col gap-3 text-xs text-gray-400 dark:text-gray-500">
                <p className="text-center">
                  登录或注册即表示同意我们的《服务协议》与《隐私政策》
                </p>
                <button
                  onClick={openFullRegisterPage}
                  className="inline-flex items-center justify-center gap-2 text-indigo-500 hover:text-indigo-600 dark:text-indigo-300 dark:hover:text-indigo-200 transition-colors"
                >
                  前往完整注册页面
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </Dialog.Panel>
      </div>
    </Dialog>
  );
}




