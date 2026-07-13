# Flutter-to-RN — AI Agent

<p align="center">
  <b>AI 驱动的 Flutter → React Native 代码转换工具</b><br>
  <i>LangGraph StateGraph 编排多阶段 Pipeline · RAG 语义上下文检索 · 混合文件分类 · 类别感知差异化转换 · 质量审查与自动修复 · 结构化构建错误修复</i>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/framework-LangGraph-blue" alt="LangGraph">
  <img src="https://img.shields.io/badge/LLM-OpenAI%20Compatible-brightgreen" alt="OpenAI Compatible">
  <img src="https://img.shields.io/badge/RAG-Chroma%2BHuggingFace-orange" alt="Chroma + HuggingFace">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
</p>

---

## 快速开始

> **前置要求：** Python 3.12+、Node.js 18+（构建验证阶段需要 `npm` 和 `npx`）

```bash
# 1. 创建并激活虚拟环境
python3 -m venv venv
source venv/bin/activate

# 2. 安装依赖
pip3 install -r requirements.txt

# 3. 配置 API Key（支持 OpenAI / DeepSeek 等兼容 API）
export OPENAI_API_KEY="your-api-key"
export OPENAI_BASE_URL="https://api.deepseek.com"   # 可选，默认 OpenAI

# 4. 一键转换（默认读取 sample/，输出到 output/）
python3 main.py

# 也可指定自定义路径
python3 main.py --source ./flutter_project --target ./output
```

---

## 简介

Flutter-to-RN 是一个 **AI 驱动的自动化代码转换工具**，将 Flutter (Dart) 项目转换为 React Native (TypeScript)，覆盖从项目初始化到构建验证的全流程。

**核心能力：**
- 一键转换完整 Flutter 项目为 React Native 项目
- 智能文件分类（规则 + LLM 混合），支持 Flutter 包目录关键词识别
- 类别感知的差异化代码转换（每类别仅发送相关映射规则）
- **RAG 语义上下文检索**：基于 Chroma 向量库的代码语义检索，自动查找跨文件相关代码
- 跨文件上下文感知：同前缀名匹配 + import 导入链解析 + **RAG 语义检索**三重机制
- 文件注册表全局追踪 Dart → TS 映射，避免重复定义
- 资产文件（图片/字体等）自动复制至 `src/assets/`
- 质量审查（全量 screens/widgets，8 维度评分）与智能重转（含分数回退保护）
- **结构化 tsc 错误解析**：按文件分组、按类别归类（import/declaration/type/syntax/unused），按优先级排序修复
- **跨文件导出上下文修复**：import 扫描 + **RAG 类型定义检索**
- TypeScript 构建验证 + ReAct Agent 自动修复（可配置重试次数）
- 断点续传：JSON 文件状态持久化，中断后可继续
- 并发安全：写入暂存文件 + 原子替换
- 并行转换（ThreadPoolExecutor，最多 6 线程）
- 支持任意 OpenAI 兼容 API（DeepSeek / Ollama / vLLM 等）

---

## CLI 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--source` | Flutter 源码目录 | `./sample` |
| `--target` | React Native 输出目录 | `./output` |
| `--model` | LLM 模型名称 | `deepseek-v4-pro` |
| `--api-key` | API Key（默认读取 `OPENAI_API_KEY` 环境变量） | — |
| `--base-url` | API Base URL（默认读取 `OPENAI_BASE_URL` 环境变量） | — |
| `--timeout` | LLM 请求超时（秒） | `120` |
| `--max-retries` | 构建验证最大重试次数 | `3` |
| `--scan-mode` | 扫描模式: `fast` / `smart` / `deep` | `fast` |
| `--skip-setup` | 跳过项目初始化 | `false` |
| `--skip-conversion` | 跳过代码转换 | `false` |
| `--skip-verification` | 跳过构建验证 | `false` |

---

## 系统架构

采用**分层架构**，自顶向下共七层，层间通过 `Config`、`LLMClient`、`StateManager` 全局共享：

```
 ┌───────────────────────────────────────────────────┐
 │                    CLI 入口                         │
 │                   main.py                          │
 └───────────────────────┬───────────────────────────┘
                         │
 ┌───────────────────────▼───────────────────────────┐
 │                    编排层                           │
 │               orchestration/                       │
 │        LangGraph StateGraph · 5 阶段 Pipeline      │
 │     Setup → Scan → Copy Assets → Convert → Verify  │
 └───────────────────────┬───────────────────────────┘
                         │
 ┌───────────────────────▼───────────────────────────┐
 │                   Agent 层                         │
 │                   agents/                          │
 │   ScanAgent       ConvertAgent    ReflectAgent      │
 │   VerifyAgent     BaseAgent                         │
 │   (各阶段核心逻辑 + RAG 检索 (Convert/Verify))         │
 └───────────────────────┬───────────────────────────┘
                         │
 ┌───────────────────────▼───────────────────────────┐
 │                   Tools 层                          │
 │                   tools/                            │
 │    8 个 @tool 函数 · 全局注册表 TOOLS               │
 └───────────────────────┬───────────────────────────┘
                         │
 ┌───────────────────────▼───────────────────────────┐
 │                  Prompts 层                         │
 │                  prompts/                           │
 │    按文件类别组合差异化 LLM 提示词                    │
 └───────────────────────┬───────────────────────────┘
                         │
 ┌───────────────────────▼───────────────────────────┐
 │                  Framework 层                       │
 │                  framework/                        │
 │   config / llm / state / state_machine / rag       │
 │   (Chroma 向量库 · 双嵌入策略 · 两类索引)            │
 └───────────────────────┬───────────────────────────┘
                         │
 ┌───────────────────────▼───────────────────────────┐
 │                 Templates 层                        │
 │                 templates/                         │
 │   package.json / App.tsx / AppNavigator.tsx / ...   │
 └───────────────────────────────────────────────────┘
```

### RAG 引擎

RAG 引擎（`framework/rag.py`）为 ConvertAgent 和 VerifyAgent 提供语义检索能力：

```
                    RAGEngine
                       │
          ┌────────────┼────────────┐
          │            │            │
    ConvertAgent  ReflectAgent  VerifyAgent
     Dart 源码 →    Issue 模式    TS 类型定义 →
     语义上下文     跨文件警告     上下文修复参考
          │            │            │
          └────────────┼────────────┘
                       │
              Chroma Vector Store
                       │
          ┌────────────┴────────────┐
  OpenAI Embeddings          HuggingFace 本地嵌入
  (text-embedding-3-small)   (all-MiniLM-L6-v2, CPU)
```

**嵌入策略：** OpenAI API 用户 → 远程 `text-embedding-3-small`；非 OpenAI 用户 → 自动回退本地 `all-MiniLM-L6-v2`（~80MB）；均不可用 → RAG 静默禁用，降级为文件名匹配。

### 技术栈

| 技术 | 用途 |
|------|------|
| **LangChain** | `ChatOpenAI` 统一 LLM 调用，`@tool` 函数注册与 schema 生成 |
| **LangGraph** | `StateGraph` 编排 Pipeline 节点与条件路由 |
| **LangGraph ReAct Agent** | VerifyAgent 的推理-行动循环 |
| **Chroma + HuggingFace Embeddings** | 向量存储与语义嵌入（RAG 引擎） |
| **JSON 文件** | 转换进度持久化（断点续传，原子写入） |
| **OpenAI Compatible API** | 兼容 DeepSeek / Ollama / vLLM 等 |
| **rich** | 终端彩色日志输出 |
| **ThreadPoolExecutor** | 文件级并行转换（最多 6 线程） |

---

## 转换 Pipeline

LangGraph `StateGraph` 编排 **5 个节点**（setup → scan → copy_assets → convert → verify），通过 `PipelineState` 在节点间传递数据：

```
setup ──→ scan ──→ copy_assets ──→ convert ──→ verify ──→ END
                                              │
                                        build_fail ──→ verify (重试)
```

### Phase 1 · Setup — 项目初始化

生成 RN 项目骨架：`package.json`、`tsconfig.json`、`babel.config.js`、`metro.config.js`、`App.tsx`、`AppNavigator.tsx`、`Home.tsx`，以及 `src/` 目录结构。

### Phase 2 · Scan — 文件扫描与分类

`ScanAgent` 将 Flutter 源码分类为 screens / widgets / services / models / providers / utils / assets。采用**目录名规则初筛 → 必要时 LLM 批量补充**的两阶段策略（每批 50 文件，仅发前 20 行预览）。

| 扫描模式 | 原理 | 适用场景 |
|------|------|----------|
| `fast` | 纯规则匹配 | **目录标准的项目（默认）** |
| `smart` | 规则 + 仅兜底文件走 LLM | 需更高准确率 |
| `deep` | 全部走 LLM | 目录不标准 |

### Phase 3 · Copy Assets — 资产复制

将图片/字体等资源自动复制到 `output/src/assets/`。

### Phase 4 · Convert — 代码转换 + 质量审查

**（A）RAG 索引构建**：转换前将 Dart 源码分块索引至 Chroma（按 class/mixin/enum 等结构边界分割，chunk_size=600）；转换完成后对 TS 输出建索引（chunk_size=800），供 VerifyAgent 检索。

**（B）ConvertAgent**（单次 LLM 调用）：按文件类别组合差异化提示词，每类别仅发送相关映射规则：

| 类别 | 输出目录 | 提示词组成 |
|------|---------|-----------|
| screens | `src/screens/` | 核心 + 组件映射 + 状态管理 + 导航 + 样式 + 布局 |
| widgets | `src/components/` | 核心 + 组件映射 + 样式 + 布局 |
| services | `src/services/` | 核心 + API/平台适配 |
| models | `src/models/` | 仅核心 |
| providers | `src/providers/` | 核心 + 状态管理 |
| utils | `src/utils/` | 核心 + API/平台适配 |

**（C）ReflectAgent**（Convert 子阶段）：对**所有** screens/widgets 文件执行质量审查（8 维度），起始 100 分：

| 维度 | 扣分 |
|------|------|
| 缺失/错误的 widget 映射 | -3/个 |
| 缺失属性 | -3/个 |
| 布局/样式映射错误 | -2/个 |
| 状态管理缺口 | -5/个 |
| import/lint 问题 | -2/个 |
| `any` 类型（应具体化时） | -2/个 |
| 无法编译的代码 | -10 |

**≥ 90 分通过**，否则触发重转（最多 1 次重试 + 重审），重转后分数回退时自动恢复原始版本。

### Phase 5 · Verify — 构建验证

`VerifyAgent`（LangGraph ReAct Agent）：`npm install` → `tsc --noEmit` → 失败自动修复并重试。tsc 错误自动解析为结构化对象，按 import → declaration → type → syntax → unused 优先级排序修复。修复时优先通过 RAG 检索类型定义，回退策略为扫描 import 语句提取导出签名。

---

## 配置方式

支持三种方式，优先级从高到低：

**1. CLI 参数**
```bash
python3 main.py --model gpt-4o --api-key sk-xxx
```
**2. 环境变量**
```bash
export OPENAI_API_KEY="sk-xxx"
export OPENAI_BASE_URL="https://api.deepseek.com"
```
**3. `.env` 文件**（项目根目录，`python-dotenv` 自动加载）
```env
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.deepseek.com
```

---

## 输出产物

```
output/
├── package.json                     # RN 项目依赖
├── tsconfig.json                    # TypeScript 编译配置
├── babel.config.js                  # Babel 配置
├── metro.config.js                  # Metro Bundler 配置
├── App.tsx                          # 应用入口（NavigationContainer）
├── .flutter_to_rn_state.json        # 转换状态 Checkpoint
├── .rag_cache/                      # RAG 向量缓存目录
└── src/
    ├── navigation/AppNavigator.tsx
    ├── screens/                     # .tsx
    ├── components/                  # .tsx
    ├── services/                    # .ts
    ├── models/                      # .ts
    ├── providers/                   # .tsx
    ├── utils/                       # .ts
    └── assets/
```

---

## 项目结构

```
Flutter-to-RN/
├── main.py                           # CLI 入口
├── requirements.txt
├── .env                              # API 配置（可选）
├── orchestration/                    # 编排层
│   ├── pipeline.py                   #   LangGraph StateGraph 主编排
│   └── setup.py                      #   RN 项目骨架生成
├── agents/                           # Agent 层
│   ├── base.py                       #   Agent 基类 + Agent 工厂
│   ├── scan_agent.py                 #   文件扫描分类
│   ├── convert_agent.py              #   代码转换
│   ├── reflect_agent.py              #   质量审查+重转
│   └── verify_agent.py               #   构建验证+修复
├── tools/                            # @tool 函数 + 注册表
├── prompts/                          # LLM 提示词模板
├── framework/                        # 基础设施
│   ├── config.py                     #   配置
│   ├── llm.py                        #   LLM 客户端
│   ├── state.py                      #   状态持久化
│   ├── state_machine.py              #   状态机
│   └── rag.py                        #   RAG 引擎
├── templates/                        # RN 项目模板
├── tests/                            # pytest 测试（50+ 用例）
└── sample/                           # 示例 Flutter 项目
```

---

## 运行测试

```bash
python3 -m pytest tests/ -v
python3 -m pytest tests/test_tools.py -v          # 指定模块
```

---

## License

MIT
