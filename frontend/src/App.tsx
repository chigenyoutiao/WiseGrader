import { useEffect } from 'react';
import { useStore } from './store';
import AgentPage from './pages/AgentPage';

function App() {
  const { isDarkMode, pollJobStatus, jobStatus } = useStore();

  // 初始化主题
  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDarkMode]);

  // 🟢 移除自动轮询 - pollJobStatus 内部已经有递归轮询机制
  // 避免重复轮询导致状态混乱

  // 默认显示聊天界面，登录与注册通过侧边栏入口触发
  return <AgentPage />;
}

export default App;
