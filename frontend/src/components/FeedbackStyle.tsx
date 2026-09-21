import { useStore } from '../store';

export default function FeedbackStyle() {
  const { feedbackStyle, setFeedbackStyle } = useStore();

  return (
    <div>
      <label
        htmlFor="feedback-style"
        className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
      >
        自定义风格要求
      </label>
      <textarea
        id="feedback-style"
        value={feedbackStyle}
        onChange={(e) => setFeedbackStyle(e.target.value)}
        className="w-full px-4 py-3 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded-xl text-gray-900 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-pink-500 focus:border-transparent transition-all resize-none"
        rows={8}
        placeholder="输入评语风格要求，例如：&#10;- 语气友好、鼓励性&#10;- 指出具体问题和改进建议&#10;- 精确到个位数、拒绝惰性评分"
      />
      <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
        提示：建议包含"精确到个位数、拒绝惰性评分"以确保精确评分
      </p>
    </div>
  );
}
