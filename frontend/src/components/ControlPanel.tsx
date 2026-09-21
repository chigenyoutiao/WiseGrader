import { useStore } from '../store';
import { Sun, Moon } from 'lucide-react';
import Login from './Login';
// @ts-expect-error: Missing type declarations for Config
import Config from './Config';
// @ts-expect-error: Missing type declarations for Criteria
import Criteria from './Criteria';
import FeedbackStyle from './FeedbackStyle';
// @ts-expect-error: Missing type declarations for Upload
import Upload from './Upload';
import Actions from './Actions';

export default function ControlPanel() {
  const { isDarkMode, toggleTheme, isLoggedIn } = useStore();

  return (
    <div className="w-96 h-screen bg-gray-50 dark:bg-gray-900 border-r border-gray-200 dark:border-gray-700 flex flex-col">
      {/* Header with Theme Toggle */}
      <div className="flex-shrink-0 p-6 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900 dark:text-white">
              WiseGrader
            </h1>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              智能作业批改系统
            </p>
          </div>
          <button
            onClick={toggleTheme}
            className="p-2.5 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            aria-label="Toggle theme"
          >
            {isDarkMode ? (
              <Sun className="w-5 h-5 text-yellow-500" />
            ) : (
              <Moon className="w-5 h-5 text-gray-600" />
            )}
          </button>
        </div>
      </div>

      {/* Scrollable Content */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {!isLoggedIn ? (
          <Login />
        ) : (
          <>
            <Config />
            <Criteria />
            <FeedbackStyle />
            <Upload />
            <Actions />
          </>
        )}
      </div>
    </div>
  );
}
