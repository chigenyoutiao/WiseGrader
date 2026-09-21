import { Target } from 'lucide-react';
import { useStore } from '../store';

export default function GradingTargets() {
  const { gradingTargets, setGradingTargets } = useStore();

  const handleChange = (field: keyof typeof gradingTargets, value: string) => {
    const numValue = value === '' ? '' : Number(value);
    setGradingTargets({
      ...gradingTargets,
      [field]: numValue,
    });
  };

  return (
    <div className="space-y-4">
      <div className="p-4 bg-gradient-to-r from-amber-50 to-orange-50 dark:from-amber-900/20 dark:to-orange-900/20 border border-amber-200 dark:border-amber-800 rounded-xl">
        <div className="flex items-start gap-3 mb-3">
          <Target className="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="text-sm font-semibold text-amber-900 dark:text-amber-100">
              教学指标设置（可选）
            </h4>
            <p className="text-xs text-amber-700 dark:text-amber-300 mt-1">
              设置批改目标，AI会参考这些指标进行评分，以满足教学要求
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* 及格率目标 */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
            及格率目标 (%)
          </label>
          <div className="relative">
            <input
              type="number"
              min="0"
              max="100"
              step="1"
              value={gradingTargets.passRate}
              onChange={(e) => handleChange('passRate', e.target.value)}
              className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-amber-500 focus:border-transparent transition-all"
              placeholder="例如: 85"
            />
            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-gray-500 dark:text-gray-400">
              %
            </span>
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            要求≥60分的学生占比
          </p>
        </div>

        {/* 优秀率目标 */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
            优秀率目标 (%)
          </label>
          <div className="relative">
            <input
              type="number"
              min="0"
              max="100"
              step="1"
              value={gradingTargets.excellentRate}
              onChange={(e) => handleChange('excellentRate', e.target.value)}
              className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-amber-500 focus:border-transparent transition-all"
              placeholder="例如: 30"
            />
            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-gray-500 dark:text-gray-400">
              %
            </span>
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            要求≥90分的学生占比
          </p>
        </div>

        {/* 最低分要求 */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
            最低分要求
          </label>
          <div className="relative">
            <input
              type="number"
              min="0"
              max="100"
              step="1"
              value={gradingTargets.minScore}
              onChange={(e) => handleChange('minScore', e.target.value)}
              className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-amber-500 focus:border-transparent transition-all"
              placeholder="例如: 40"
            />
            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-gray-500 dark:text-gray-400">
              分
            </span>
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            班级最低分不得低于此值
          </p>
        </div>
      </div>

      <div className="p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
        <p className="text-xs text-blue-800 dark:text-blue-200">
          💡 提示：设置教学指标后，AI会在批改时参考这些目标，确保整体成绩分布符合教学要求。留空则AI完全依据评分标准客观评分。
        </p>
      </div>
    </div>
  );
}
