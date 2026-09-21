import { useState } from 'react';
import { useStore } from '../store';
import { LogIn, Sparkles } from 'lucide-react';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const { login, loginError, isLoading } = useStore();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await login(username, password);
  };

  return (
    <div className="min-h-screen w-full relative overflow-hidden bg-gradient-to-br from-blue-50 via-cyan-50 to-cyan-50 dark:from-gray-900 dark:via-blue-900/20 dark:to-cyan-900/20">
      {/* 背景动态装饰 */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-1/2 -left-1/4 w-96 h-96 bg-blue-400/30 dark:bg-blue-600/20 rounded-full blur-3xl animate-blob"></div>
        <div className="absolute -bottom-1/2 -right-1/4 w-96 h-96 bg-cyan-400/30 dark:bg-cyan-600/20 rounded-full blur-3xl animate-blob animation-delay-2000"></div>
        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-pink-400/20 dark:bg-pink-600/10 rounded-full blur-3xl animate-blob animation-delay-4000"></div>
      </div>

      {/* 主内容 */}
      <div className="relative z-10 flex items-center justify-center min-h-screen px-4 py-12">
        <div className="w-full max-w-md">
          {/* Logo 区域 */}
          <div className="text-center mb-8 animate-fade-in-down">
            <div className="inline-flex items-center justify-center w-20 h-20 rounded-3xl bg-gradient-to-br from-blue-500 to-cyan-600 shadow-2xl shadow-blue-500/50 dark:shadow-blue-600/30 mb-6 animate-float">
              <Sparkles className="w-10 h-10 text-white" />
            </div>
            <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-cyan-600 dark:from-blue-400 dark:to-cyan-400 bg-clip-text text-transparent mb-2">
              AI 智能批改助手
            </h1>
            <p className="text-gray-600 dark:text-gray-400 text-sm">
              让 AI 成为您的教学伙伴
            </p>
          </div>

          {/* 登录卡片 */}
          <div className="backdrop-blur-xl bg-white/70 dark:bg-gray-800/70 rounded-3xl shadow-2xl border border-white/20 dark:border-gray-700/50 p-8 animate-fade-in-up">
            <form onSubmit={handleSubmit} className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  用户名
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full px-4 py-3 bg-white/50 dark:bg-gray-900/50 border border-gray-300 dark:border-gray-600 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-300 text-gray-900 dark:text-gray-100 placeholder-gray-400"
                  placeholder="请输入用户名"
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
                  className="w-full px-4 py-3 bg-white/50 dark:bg-gray-900/50 border border-gray-300 dark:border-gray-600 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-300 text-gray-900 dark:text-gray-100 placeholder-gray-400"
                  placeholder="请输入密码"
                  required
                />
              </div>

              {loginError && (
                <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 px-4 py-3 rounded-xl text-sm animate-shake">
                  {loginError}
                </div>
              )}

              <button
                type="submit"
                disabled={isLoading}
                className="w-full bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-700 hover:to-cyan-700 text-white font-semibold py-3 px-4 rounded-xl shadow-lg hover:shadow-xl transform hover:scale-[1.02] active:scale-[0.98] transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none flex items-center justify-center gap-2"
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

            {/* 提示信息 */}
            <div className="mt-6 pt-6 border-t border-gray-200 dark:border-gray-700">
              <p className="text-xs text-gray-500 dark:text-gray-400 text-center">
                默认账号: <span className="font-mono text-blue-600 dark:text-blue-400">teacher</span> /
                <span className="font-mono text-blue-600 dark:text-blue-400"> admin123</span>
              </p>
            </div>
          </div>

          {/* 底部装饰 */}
          <div className="mt-8 text-center text-xs text-gray-500 dark:text-gray-400 animate-fade-in">
            <p>Powered by AI · 让作业批改更智能</p>
          </div>
        </div>
      </div>
    </div>
  );
}
