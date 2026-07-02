# Flutter-to-RN — AI

<p align="center">
  <b>AI 驱动的 Flutter → React Native 代码转换工具</b><br>
  <i>LangGraph StateGraph 编排多阶段 Pipeline · 混合文件分类 · 类别感知差异化转换 · 质量审查 · 构建自动修复</i>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/framework-LangGraph-blue" alt="LangGraph">
  <img src="https://img.shields.io/badge/LLM-OpenAI%20Compatible-brightgreen" alt="OpenAI Compatible">
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
#    方式一：编辑项目根目录的 .env 文件（推荐）
#    方式二：通过环境变量传入
export OPENAI_API_KEY="your-api-key"
export OPENAI_BASE_URL="https://api.deepseek.com"   # 可选，默认 OpenAI

# 4. 一键转换（默认读取 sample/，输出到 output/）
python3 main.py

# 也可指定自定义路径
python3 main.py --source ./flutter_project --target ./output
```

---

## 简介

Flutter-to-RN 是一个 **AI 驱动的自动化代码转换工具**，将 Flutter (Dart) 项目转换为 React Native (TypeScript)。它利用 **LangChain + LangGraph** 构建多 Agent 协作流水线，覆盖从项目初始化到构建验证的全流程。

**核心能力：**
- 一键转换完整 Flutter 项目为 React Native 项目
- 智能文件分类（规则 + LLM 混合），支持 Flutter 包目录关键词识别
- 类别感知的差异化代码转换（每类别仅发送相关映射规则）
- 跨文件上下文感知：同前缀名匹配 + import 导入链解析双重机制
- 文件注册表全局追踪 Dart → TS 映射，避免重复定义
- 资产文件（图片/字体等）自动复制至 `src/assets/`
- 质量审查（全量 screens/widgets，8 维度评分）与自动重转
- TypeScript 构建验证 + 自动修复（最多 3 轮重试）
- 断点续传：JSON 文件状态持久化，中断后可继续
- 并发安全：写入暂存文件 + 原子替换，防止数据损坏
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

项目采用**分层架构**，自顶向下共七层，层间通过 `Config`、`LLMClient`、`StateManager` 全局共享：

```
 ┌───────────────────────────────────────────────────┐
 │                    CLI 入口                         │
 │                   main.py                          │
 │           参数解析 → venv 激活 → 启动               │
 └───────────────────────┬───────────────────────────┘
                         │
 ┌───────────────────────▼───────────────────────────┐
 │                    编排层                           │
 │               orchestration/                       │
 │                                                   │
 │        LangGraph StateGraph · 5 阶段 Pipeline      │
 │                                                   │
 │     Setup → Scan → Copy Assets → Convert → Verify │
 │                                                   │
 │       ├─ Reflect: Convert 子阶段, 全量 screens/widgets 审查         │
 │       └─ 构建失败自动重试 (≤3 轮)                   │
 └───────────────────────┬───────────────────────────┘
                         │
 ┌───────────────────────▼───────────────────────────┐
 │                   Agent 层                         │
 │                   agents/                          │
 │                                                   │
 │   ┌────────────┐  ┌────────────┐  ┌────────────┐  │
 │   │ ScanAgent  │  │ConvertAgent│  │ReflectAgent │  │
 │   │  文件扫描   │  │  代码转换   │  │ 质量审查+重转│  │
 │   └────────────┘  └────────────┘  └────────────┘  │
 │   ┌────────────┐  ┌────────────────────────────┐  │
 │   │VerifyAgent │  │         BaseAgent          │  │
 │   │ 构建验证+修复│  │   LLM 访问 + Agent 工厂    │  │
 │   └────────────┘  └────────────────────────────┘  │
 └───────────────────────┬───────────────────────────┘
                         │
 ┌───────────────────────▼───────────────────────────┐
 │                   Tools 层                          │
 │                   tools/                            │
 │                                                   │
 │    8 个 @tool 函数 · 全局注册表 TOOLS               │
 │                                                   │
 │   classify_file           scan_source_directory       │
 │   read_source_file        write_output_file             │
 │   extract_code_from_response   run_build_check         │
 │   run_tsc_check           reflect_on_conversion        │
 └───────────────────────┬───────────────────────────┘
                         │
 ┌───────────────────────▼───────────────────────────┐
 │                  Prompts 层                         │
 │                  prompts/                           │
 │                                                   │
 │    按文件类别拼装差异化 LLM 提示词                    │
 │                                                   │
 │   convert.py     → 6 种类别 × N 片段               │
 │   verify.py      → 构建错误修复                     │
 │   scanner.py     → 批量分类 (50 文件/批)             │
 │   generic.py     → truncate_content 工具           │
 └───────────────────────┬───────────────────────────┘
                         │
 ┌───────────────────────▼───────────────────────────┐
 │                  Framework 层                       │
 │                  framework/                        │
 │                                                   │
 │   config.py   → Config 数据类 · .env · 三优先级     │
 │   llm.py      → ChatOpenAI · Agent 工厂            │
 │   state.py    → JSON 文件状态持久化                  │
 │   state_machine.py → StateGraph 状态机封装          │
 └───────────────────────┬───────────────────────────┘
                         │
 ┌───────────────────────▼───────────────────────────┐
 │                 Templates 层                        │
 │                 templates/                         │
 │                                                   │
 │   package.json → React 18 + RN 0.76 + 导航/存储    │
 │   rn_app.py    → App.tsx (NavigationContainer)     │
 │   rn_navigation.py → AppNavigator.tsx              │
 │   rn_screens.py → Home.tsx (默认首页)               │
 └───────────────────────────────────────────────────┘
```

### 技术栈

| 技术 | 用途 |
|------|------|
| **LangChain** | `ChatOpenAI` 统一 LLM 调用，`@tool` 函数注册与 schema 生成 |
| **LangGraph** | `StateGraph` 编排 Pipeline 节点与条件路由 |
| **LangGraph ReAct Agent** | VerifyAgent 的推理-行动循环 |
| **JSON 文件** | 转换进度持久化（断点续传，原子写入） |
| **OpenAI Compatible API** | 兼容 DeepSeek / Ollama / vLLM 等 |
| **rich** | 终端彩色日志输出 |
| **ThreadPoolExecutor** | 文件级并行转换（最多 6 线程） |

---

## 转换 Pipeline

LangGraph `StateGraph` 编排 **5 个阶段**（setup → scan → copy_assets → convert → verify），通过 `PipelineState`（TypedDict）在节点间传递数据：

```
setup ──→ scan ──→ copy_assets ──→ convert ──→ verify ──→ END
                    (reflect 嵌入 convert 节点)         │
                                                  build_fail ──→ verify (重试，最多 3 轮)
```

### Phase 1 · Setup — 项目初始化

生成 RN 项目骨架：`package.json`、`tsconfig.json`、`babel.config.js`、`metro.config.js`、`App.tsx`、`AppNavigator.tsx`、`Home.tsx`，以及 `src/` 目录结构。

### Phase 2 · Scan — 文件扫描与分类

`ScanAgent` 将 Flutter 源码分类为 screens / widgets / services / models / providers / utils / assets。

**两阶段分类：** 目录名规则初筛 → 必要时 LLM 批量补充（每批 50 文件，仅发前 20 行预览）。跳过 `*.g.dart` / 平台目录（ios/android 等）。支持 `packages/`、`modules/` 等 Flutter 包目录关键词识别。

| 扫描模式 | 原理 | 适用场景 |
|------|------|----------|
| `fast` | 纯规则匹配，无 LLM | **目录标准的项目（默认）** |
| `smart` | 规则 + 仅兜底文件走 LLM | 需更高准确率 |
| `deep` | 所有 Dart 文件走 LLM | 目录不标准 |

### Phase 3 · Copy Assets — 资产复制

将图片/字体等资源自动复制到 `output/src/assets/`。

### Phase 4 · Convert — 代码转换（含质量审查）

`ConvertAgent` — 单次 LLM 调用（非 ReAct），按文件类别拼装差异化提示词：

| 类别 | 输出目录 | 提示词组成 |
|------|---------|-----------|
| screens | `src/screens/` | 核心 + 组件映射 + 状态管理 + 导航 + 样式 + 布局 |
| widgets | `src/components/` | 核心 + 组件映射 + 样式 + 布局 |
| services | `src/services/` | 核心 + API/平台适配 |
| models | `src/models/` | 仅核心 |
| providers | `src/providers/` | 核心 + 状态管理 |
| utils | `src/utils/` | 核心 + API/平台适配 |

- **文件注册表**：全局 Dart → TS 映射，避免重复定义
- **同行上下文**：同前缀匹配（`LoginMainView` ↔ `LoginMainModel`）+ import 解析自动查找已转换依赖
- **JSX 自动检测**：LLM 输出 `.ts` 但代码包含 JSX 语法时，自动升级保存为 `.tsx`，避免类型检查误判
- 并行转换（6 线程）+ 断点续传（JSON 文件标记）

### Phase 5 · Verify — 构建验证

`VerifyAgent`（LangGraph ReAct）：`npm install` → `tsc --noEmit` → 失败时自动修复并重试，**最多 3 轮**。

**结构化 tsc 错误解析：** 自动将 `tsc --noEmit` 输出解析为结构化错误（`TscError` 数据类），按文件分组并按类别归类（import、declaration、type、syntax、unused）。修复时按**优先级排序**：import 错误优先修复，其次 declaration → type → syntax → unused，从根源消除连锁报错。

**跨文件上下文修复：** 自动扫描错误文件中的 import 语句，提取被引用文件的导出签名（export type、interface、class、const 等），作为上下文注入 LLM 修复提示，大幅提升 import 路径修正和类型补全的准确率。

安全机制包含 `gave_up` 防死循环、代码提取失败返回空字符串、`node_modules` 缓存。

---

#### Reflect — 质量审查（Convert 子阶段）

Convert 完成后对**所有** screens/widgets 文件执行全量质量审查。`ReflectAgent` 从 8 维度（widget 映射、属性传递、状态管理、布局、样式、导入、导航、生命周期）评分，起始 100 分，**≥ 85 通过**，否则触发重转（最多 1 次重试 + 重审）。

---

## 配置方式

支持三种配置方式，优先级从高到低：

### 1. CLI 参数

```bash
python3 main.py --source ./app --target ./out --model gpt-4o --api-key sk-xxx --base-url https://api.openai.com
```

### 2. 环境变量

```bash
export OPENAI_API_KEY="sk-xxx"
export OPENAI_BASE_URL="https://api.deepseek.com"   # 可选
```

### 3. `.env` 文件

在项目根目录创建 `.env`（使用 `python-dotenv` 自动加载）：

```env
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.deepseek.com
```

---

## 输出产物

```
output/
├── package.json                     # RN 项目依赖（React 18 + RN 0.76）
├── tsconfig.json                    # TypeScript 编译配置（ESNext）
├── babel.config.js                  # Babel 配置（@react-native/babel-preset）
├── metro.config.js                  # Metro Bundler 配置
├── App.tsx                          # 应用入口（NavigationContainer）
├── .flutter_to_rn_state.json        # 转换状态（JSON Checkpoint）
└── src/
    ├── navigation/
    │   └── AppNavigator.tsx         # NativeStackNavigator 导航配置
    ├── screens/                     # 页面（.tsx）
    ├── components/                  # 共享组件（.tsx）
    ├── services/                    # 服务层（.ts）
    ├── models/                      # 数据模型（.ts）
    ├── providers/                   # 状态管理（.tsx / Context）
    ├── utils/                       # 工具函数（.ts）
    └── assets/                      # 资源文件（自动复制自源项目）
```

---

## 项目结构

```
Flutter-to-RN/
│
├── main.py                           # CLI 入口：参数解析 + venv 自激活 + Pipeline 启动
├── requirements.txt                  # Python 依赖声明
├── .env                              # API Key / Base URL 配置（可选）
│
├── orchestration/                    # 流程编排层
│   ├── __init__.py                   # 导出 Pipeline + ProjectSetup
│   ├── pipeline.py                   # LangGraph StateGraph 主编排（6 阶段）
│   └── setup.py                      # RN 项目骨架生成器（模板写入）
│
├── agents/                           # Agent 层：各阶段核心逻辑
│   ├── __init__.py                   # 导出 4 个 Agent
│   ├── base.py                       # Agent 基类（LLM 访问 + LangGraph Agent 工厂）
│   ├── scan_agent.py                 # 文件扫描：规则 + LLM 批量分类（3 模式）
│   ├── convert_agent.py              # 代码转换：单次 LLM 调用 + 文件注册表
│   ├── reflect_agent.py              # 质量审查：8 维度评分 + 重转
│   └── verify_agent.py               # 构建验证：npm install + tsc + 自动修复（LangGraph Agent）
│
├── tools/                            # Tool 层：@tool 装饰的无状态函数
│   ├── __init__.py                   # 8 个 @tool + 注册表 TOOLS + FileWriter 类
│   └── file_writer.py                # 向后兼容的 FileWriter 导出
│
├── prompts/                          # Prompts 层：LLM 提示词模板
│   ├── __init__.py                   # 统一导出所有提示词
│   ├── convert.py                    # 转换提示词（核心 + 6 个分类片段）
│   ├── verify.py                     # 构建修复提示词（按序修复 + 常见模式）
│   ├── scanner.py                    # 批量分类提示词（每条目含文件名 + 当前分类 + 代码预览）
│   └── generic.py                    # 通用工具函数（truncate_content）
│
├── framework/                        # Framework 层：基础设施
│   ├── __init__.py                   # 统一导出所有基础设施
│   ├── config.py                     # Config 数据类 + .env 加载 + 配置验证
│   ├── llm.py                        # LangChain ChatOpenAI 封装 + Agent 工厂
│   ├── state.py                      # JSON 文件状态持久化（原子写入）
│   └── state_machine.py              # LangGraph StateGraph 状态机封装
│
├── templates/                        # RN 项目模板
│   ├── package_json.py               # package.json（React 18 + RN 0.76 依赖）
│   ├── rn_app.py                     # App.tsx 模板
│   ├── rn_navigation.py              # AppNavigator.tsx 模板
│   └── rn_screens.py                 # Home.tsx 首页模板
│
├── tests/                            # 单元测试（pytest）
│   ├── conftest.py                   # 共享 fixtures（temp_dir, sample_config）
│   ├── test_classifier.py            # 文件分类规则测试（14 用例）
│   ├── test_convert_agent.py         # 转换 Agent 分发表测试（6 用例）
│   ├── test_tools.py                 # @tool 函数 + FileWriter 测试（20+ 用例）
│   └── test_prompts.py               # 提示词完整性测试（8 用例）
│
├── sample/                           # 示例 Flutter 项目
│   └── flutter_base/                 # Flutter 基础示例
│
└── venv/                             # Python 虚拟环境
```

---

## 运行测试

```bash
# 全部测试（50+ 用例）
python3 -m pytest tests/ -v

# 指定模块
python3 -m pytest tests/test_tools.py -v
python3 -m pytest tests/test_convert_agent.py -v
python3 -m pytest tests/test_prompts.py -v
```

---

## License

MIT
