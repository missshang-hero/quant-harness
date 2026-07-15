# 极投雷达

AI 赛道与短线共振研究台。

这个项目用于 A 股题材、赛道和短线共振的盘后研究，核心目标是把行情输入、策略信号、组合建议、验证回放和日报归档串成一个可复盘的闭环。它不是全自动实盘交易机器人，页面中的信号只用于研究、观察和模拟验证。

## 功能

- 市场情绪和题材热度分析
- 龙头/游资/共振候选筛选
- 推理赛道增长模型和当前热门赛道页签
- 组合建议与模拟持仓跟踪
- 盘后任务一键执行
- 历史日报归档和策略验证看板

## 技术栈

- 后端：Python、FastAPI、Pydantic、pandas、httpx、AkShare
- 前端：Next.js、React、TypeScript、Ant Design、Recharts
- 部署：Vercel 前端 + Vercel/Render 后端

## 本地启动

后端：

```bash
cd /Users/hero/Documents/quant-harness
source apps/api/.venv/bin/activate
uvicorn apps.api.main:app --host 127.0.0.1 --port 8010
```

前端：

```bash
cd /Users/hero/Documents/quant-harness/apps/web
npm install
npm run dev
```

打开：

- 前端：http://localhost:3010
- 后端健康检查：http://127.0.0.1:8010/health

## macOS 桌面端

桌面端使用 Electron 承载现有 Next.js 页面，并在本机自动启动 FastAPI 后端。

首次安装桌面端依赖：

```bash
cd /Users/hero/Documents/quant-harness/apps/desktop
npm install
```

开发模式启动：

```bash
cd /Users/hero/Documents/quant-harness/apps/desktop
npm run dev
```

打包 macOS `.app`：

```bash
cd /Users/hero/Documents/quant-harness/apps/desktop
npm run pack:mac
```

打包前脚本会准备 Python venv、导出静态前端，并把 `apps/api`、`packages`、样本数据和前端静态产物一起放进应用资源。桌面端运行时数据库和日报会写到 macOS 用户数据目录，而不是写进 `.app` 包内部。

## 线上部署

前端项目环境变量：

```bash
NEXT_PUBLIC_API_BASE_URL=https://api.herojiatou.com
```

如果没有配置这个变量，前端在 `herojiatou.com` 上会默认请求 `https://api.herojiatou.com`；本地开发仍默认请求 `http://127.0.0.1:8010`。

后端健康检查：

```bash
curl https://api.herojiatou.com/health
```

## 盘后任务

手动执行完整盘后任务：

```bash
cd /Users/hero/Documents/quant-harness
source apps/api/.venv/bin/activate
python scripts/run_daily_job.py
```

任务会执行：

- 拉取行情数据
- 生成策略信号
- 生成组合建议
- 保存运行记录
- 验证历史信号
- 归档 JSON 和 Markdown 日报

日报路径：

- `reports/daily/YYYY-MM-DD.json`
- `reports/daily/YYYY-MM-DD.md`

## 数据源说明

系统优先使用真实行情输入：

1. AkShare
2. 东方财富公开接口
3. 内置真实 A 股样本兜底

兜底样本只用于保证服务可运行，不代表推荐买入。后端会过滤无效 A 股代码，避免生成不可搜索的假股票。
