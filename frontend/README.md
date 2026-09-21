# AI智能作业批改助手 · 前端控制台

基于 React + TypeScript + Vite 的管理面板，用于驱动 Phase 1/2 后端的批改流程、上传 ZIP、配置评分参数，并可视化任务进度。

## 技术栈
- React 19 + TypeScript 5 + Vite 7（快速开发与 HMR）
- Tailwind CSS 3 与 Headless UI 构建浅/深色自适应界面
- Zustand 全局状态（用户会话、任务进度、Toast）
- Axios 拦截器封装后台 Token/错误处理
- Lucide React 图标、React Dropzone 负责拖拽上传

## 快速开始
`ash
cd frontend
npm install
npm run dev       # 开发调试（默认 http://localhost:5173）
npm run lint      # ESLint + TypeScript 检查
npm run build     # 生成生产包至 dist/
npm run preview   # 本地预览生产包
`

> 首次接入后端时，请确认 src/api.ts 中的 aseURL 指向实际 Flask 服务；若需要多环境切换，可改为读取 import.meta.env.VITE_API_BASE_URL。

## 目录速览
- src/api.ts：统一的 Axios 客户端、鉴权和长耗时请求超时设置
- src/components/*：上传、评分配置、进度面板、结果表格等原子组件
- src/store.ts：Zustand store，集中管理 token、文件、任务状态
- src/pages/LoginPage.tsx 与 src/layouts/MainLayout.tsx：登录流与主界面骨架
- src/index.css、	ailwind.config.js：主题、暗色模式、苹果风格的 UI token

## 与后端的约定
- 所有接口均走 /api/*，鉴权 Token 自动注入至 Authorization: Bearer <token>
- 上传接口采用 multipart/form-data，其余请求保持 JSON camelCase，与 Flask 端的驼峰兼容层对应
- 长耗时的 /api/jobs/start、/api/jobs/status/<id> 采用 300s 超时，请在后端异步化后视情况下调

## 文档入口
- docs/frontend/frontend_prompt.zh.md：前端架构师 prompt 与交互基调
- docs/frontend/NAVBAR_OPTIMIZATION.md：导航/布局演化记录
- docs/README.md：跨前后端的文档索引与项目蓝图

如需添加新的交互设计或性能调优文档，请直接放入 docs/frontend/，保持与后端文档同级管理。
