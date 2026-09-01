# Flutter-to-RN — AI Agent

<p align="center">
  <b>AI 驱动的 Flutter → React Native 代码转换工具</b><br>
  <i>LangGraph StateGraph 多阶段 Pipeline · Harness 统一 LLM 编排 · 按任务模型路由（含失败降级） · 跨运行记忆 · RAG 语义检索 · 质量审查与自动修复 · 结构化构建错误修复</i>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/framework-LangGraph-blue" alt="LangGraph">
  <img src="https://img.shields.io/badge/LLM-OpenAI%20Compatible-brightgreen" alt="OpenAI Compatible">
  <img src="https://img.shields.io/badge/RAG-Chroma%2BHuggingFace-orange" alt="Chroma + HuggingFace">
  <img src="https://img.shields.io/badge/Harness-路由%20%2F%20账本%20%2F%20缓存-blueviolet" alt="Harness">
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

**核心特性：**
- 一键转换完整 Flutter 项目为 React Native 项目（5 阶段 Pipeline）
- 智能文件分类（规则 + LLM 混合）+ 类别感知的差异化转换（每类别仅发相关映射规则）
- **Harness 统一 LLM 编排**（`framework/harness.py`）：按任务模型路由（含失败降级）/ Token 账本 / 响应缓存 / 跨运行记忆 / 预算守护 / 重试封顶
- **RAG 语义上下文检索**（Chroma 向量库）+ 跨文件上下文感知（前缀匹配 + import 链）
- 质量审查与自动重转（分数回退保护）+ 结构化 tsc 错误解析与自动修复
- 断点续传（原子写入）+ 并行转换（最多 6 线程）+ 支持任意 OpenAI 兼容 API

---

## CLI 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--source` | Flutter 源码目录 | `./sample` |
| `--target` | React Native 输出目录 | `./output` |
| `--model` | 全局 LLM 模型名称 | `deepseek-v4-pro` |
| `--route` | 按任务路由模型（可重复，如 `--route convert=claude-sonnet-5`，见[模型路由](#模型路由)） | 全局 `--model` |
| `--api-key` | API Key（默认读取 `OPENAI_API_KEY` 环境变量） | — |
| `--base-url` | API Base URL（默认读取 `OPENAI_BASE_URL` 环境变量） | — |
| `--timeout` | LLM 请求超时（秒） | `120` |
| `--max-retries` | 构建验证最大重试次数 | `3` |
| `--scan-mode` | 扫描模式: `fast` / `smart` / `deep` | `fast` |
| `--skip-setup` | 跳过项目初始化 | `false` |
| `--skip-conversion` | 跳过代码转换 | `false` |
| `--skip-verification` | 跳过构建验证 | `false` |
| `--no-memory` | 禁用跨运行记忆（few-shots / fix-memos / 摘要） | `false` |
| `--cache-ttl` | 响应缓存 TTL（小时） | `24` |
| `--budget` | 硬性 token 预算上限（`0` = 不限，超限中止调用） | `0` |

---

## 模型路由

默认所有任务共用全局模型（`--model` + `OPENAI_API_KEY` + `OPENAI_BASE_URL`）。
如需按任务分派到不同模型（含不同 provider），通过环境变量 `MODEL_ROUTES`（JSON）配置：

```bash
export MODEL_ROUTES='{
  "scan_classify": {"model": "deepseek-chat"},
  "convert":       {"model": "claude-sonnet-5", "base_url": "https://api.anthropic.com", "api_key": "sk-..."},
  "reflect":       {"model": "deepseek-v4-pro", "fallback_model": "deepseek-chat"}
}'
```

- **任务类型**：`scan_classify` / `convert` / `reflect` / `convert_fix` / `verify_fix`。
- 每个条目可指定 `model` / `base_url` / `api_key`，缺省字段回退全局配置。
- **失败降级**：可选 `fallback_model`（含 `fallback_base_url` / `fallback_api_key`，缺省继承该任务主连接）。
  主模型重试封顶（默认 3 次）失败后，自动切换 fallback 模型再试 1 次。
- **缓存隔离**：缓存键包含实际调用的模型与 base_url，不同模型不会互相命中缓存。
- **命令行快速覆盖**（只改主模型，保留该任务 env 连接与 fallback）：

```bash
python3 main.py --route convert=claude-sonnet-5 --route scan_classify=deepseek-chat
```

> 未配置 `MODEL_ROUTES` 或 `--route` 时，行为与单模型完全一致。

---

## 系统架构

采用**分层架构**，自顶向下共七层，层间通过 `Config`、`Harness`、`StateManager` 全局共享（`Harness` 为所有 LLM 调用的唯一入口）：

```
 ┌───────────────────────────────────────────────────┐
 │                    CLI 入口                         │
 │                   main.py                          │
 └───────────────────────┬───────────────────────────┘
                         │
 ┌───────────────────────▼───────────────────────────┐
 │                    编排层                           │
 │               orchestration/                       │
 │        LangGraph StateGraph · 5 阶段 Pipeline       │
 │     Setup → Scan → Copy Assets → Convert → Verify  │
 └───────────────────────┬───────────────────────────┘
                         │
 ┌───────────────────────▼───────────────────────────┐
 │                   Agent 层                         │
 │                   agents/                          │
 │   ScanAgent       ConvertAgent    ReflectAgent     │
 │   VerifyAgent     BaseAgent                        │
 │   (各阶段核心逻辑 + RAG 检索 (Convert/Verify))        │
 └───────────────────────┬───────────────────────────┘
                         │
 ┌───────────────────────▼───────────────────────────┐
 │                   Tools 层                         │
 │                   tools/                           │
 │ 8 个 @tool · TOOLS(通用) + VERIFY_FIX_TOOLS(ReAct) │
 └───────────────────────┬───────────────────────────┘
                         │
 ┌───────────────────────▼───────────────────────────┐
 │                  Prompts 层                        │
 │                  prompts/                          │
 │    按文件类别组合差异化 LLM 提示词                     │
 └───────────────────────┬───────────────────────────┘
                         │
 ┌───────────────────────▼───────────────────────────┐
 │                  Framework 层                      │
 │                  framework/                        │
 │   harness / memory / llm / config / state /        │
 │   state_machine / rag                              │
 │   (Harness 编排 · 多模型路由 · 跨运行记忆 ·        │
 │    Chroma 向量库 · 双嵌入策略 · 两类索引)            │
 └───────────────────────┬───────────────────────────┘
                         │
 ┌───────────────────────▼───────────────────────────┐
 │                 Templates 层                       │
 │                 templates/                         │
 │   package.json / App.tsx / AppNavigator.tsx / ...  │
 └───────────────────────────────────────────────────┘
```

### RAG 引擎

RAG 引擎（`framework/rag.py`）为 ConvertAgent（Dart 源码 → 语义上下文）和 VerifyAgent（TS 类型定义 → 修复参考）提供语义检索，基于 Chroma 向量库。

- **双嵌入策略**：OpenAI API 用户 → 远程 `text-embedding-3-small`；非 OpenAI 用户 → 自动回退本地 `all-MiniLM-L6-v2`（~80MB）；均不可用 → RAG 静默禁用，降级为文件名匹配。
- **索引**：转换前 Dart 源码按结构边界分块（chunk_size=600）；转换后 TS 输出重建索引（chunk_size=800）供 VerifyAgent 检索。
- **优化**：检索结果缓存（键 = 截断查询 + 文件名 + k，超 500 条淘汰最早 100）、查询截断（`query_code` 仅取前 N 字符嵌入）、类别门控（仅 screens/widgets/providers 走 RAG，简单类别用 companion 上下文）。

### Harness 统一编排层

`Harness`（`framework/harness.py`）是**所有 LLM 调用的唯一入口**——薄编排层而非多步工具循环。每次 `harness.call()` 依序完成：**路由 → 自适应参数 → 缓存查询 → 记忆注入 → 调用 → 账本记账**。

```
harness.call(task_type, system_prompt, user_message, ...)
  ├─ 路由:     按任务类型解析模型连接（MODEL_ROUTES / --route），未配置时
  │             回退全局模型；主模型重试封顶（3 次）后自动切换 fallback 再试 1 次
  ├─ 自适应:   按任务类型分配调用参数（convert/verify_fix → max_tokens 8192，
  │             scan_classify → 2048，reflect → 4096）
  ├─ 缓存:     (装配输入 + 实际模型 + 温度 + 版本盐) 命中则直接返回
  ├─ 记忆注入: 转换经验 / 项目摘要追加到 user message（绝不进 system，保前缀磁盘缓存）
  ├─ 调用:     ChatOpenAI 多模型实例池（按 base_url + model + api_key 隔离）
  └─ 账本:     input/output token + 缓存命中 token + 推理 token 落盘审计
```

> Agentic 路径（Verify 的 ReAct 修复循环）绕过 `call()` 直接经 LLM 实例池调模型，但通过 `record_usage()` / `over_budget()` 与 `call()` 共享同一 Token 账本与预算守护，审计与预算不遗漏。

**按任务自适应 + 模型路由：** 未配置路由时，所有调用共用全局模型（`--model`，默认 `deepseek-v4-pro`）。"智能"体现在 Harness 对每次调用按其任务类型自动调整调用参数——代码生成类任务（convert / convert_fix / verify_fix）分配大输出预算（`max_tokens=8192`），分类类任务（scan_classify）只需小预算（`2048`），评审类（reflect）居中（`4096`）；调用方也可传 `max_tokens` 临时覆盖。配置 `MODEL_ROUTES`（或 `--route`）后，同一套 `task_type` 同时决定调用参数与目标模型，主模型失败自动降级到 `fallback_model`，详见[模型路由](#模型路由)。

**跨运行持久记忆**（`framework/memory.py` → `target_dir/.memory.json`，可 `--no-memory` 关闭）：

| 类型 | 内容 | 写入时机 | 读取时机 |
|------|------|---------|---------|
| ① 转换经验 few-shot | 高分(≥90) dart→ts 转换对 | reflect 通过后 | convert / convert_fix 注入 top-k |
| ② 修复模式 fix-memo | error_code → 修复片段 | verify 修复后 tsc 通过 | 下次同 error_code 时注入 |
| ③ 评分记忆 | source_hash + 分数/通过状态 + 依赖集哈希 | reflect 后 | 源未变**且依赖未变**则跳过重审/重转 |
| ④ 项目摘要 | 已转换模块清单 + 关键类型签名 | 每 run 刷新 | convert 注入，替代冗长 RAG 块 |

**Token 优化机制**：响应缓存（确定性调用 `temperature==0` 自动命中，TTL 24h）、Token 账本、预算守护（`--budget` 硬上限，超限中止调用）、reflect 批量化 + 8K 截断、记忆注入保持 system 前缀稳定以命中磁盘前缀缓存。

### 技术栈

| 技术 | 用途 |
|------|------|
| **langchain-openai** | `ChatOpenAI` 多模型路由实例池，统一兼容 OpenAI / DeepSeek 等 |
| **LangGraph** | `StateGraph` 编排 Pipeline 节点与条件路由 |
| **Chroma + HuggingFace Embeddings** | 向量存储与语义嵌入（RAG 引擎） |
| **JSON 文件** | 状态断点续传（原子写入）+ 响应缓存 `.llm_cache.json` + 记忆 `.memory.json` |
| **JSONL 账本** | Token 计量 `.token_ledger.jsonl`（每阶段审计） |
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

**（A）RAG 索引构建**：转换前索引 Dart 源码，转换完成后对 TS 输出重建索引，供 VerifyAgent 检索（分块参数见上文 RAG 引擎）。

**（B）ConvertAgent**（单次 LLM 调用）：按文件类别组合差异化提示词，每类别仅发送相关映射规则：

| 类别 | 输出目录 | 提示词组成 |
|------|---------|-----------|
| screens | `src/screens/` | 核心 + 组件映射 + 状态管理 + 导航 + 样式 + 布局 |
| widgets | `src/components/` | 核心 + 组件映射 + 样式 + 布局 |
| services | `src/services/` | 核心 + API/平台适配 |
| models | `src/models/` | 仅核心 |
| providers | `src/providers/` | 核心 + 状态管理 |
| utils | `src/utils/` | 核心 + API/平台适配 |

输出解析失败时自动重试一次（关闭缓存、温度升到 0.4）；若产物含 JSX 但扩展名是 `.ts`，自动升级保存为 `.tsx`。

**（C）ReflectAgent**（Convert 子阶段）：对 screens/widgets 文件执行质量审查（**批量 LLM 调用**：每批 10 文件、单侧 8K 自适应截断，批解析失败的文件自动回退为单独审查），起始 100 分：

| 维度 | 扣分 |
|------|------|
| 缺失/错误的 widget 映射 | -3/个 |
| 缺失属性 | -3/个 |
| 布局/样式映射错误 | -2/个 |
| 状态管理缺口 | -5/个 |
| import/lint 问题 | -2/个 |
| `any` 类型（应具体化时） | -2/个 |
| 无法编译的代码 | -10 |

**≥ 90 分通过**，否则触发重转（最多 1 次重试 + 重审），重转后分数回退时自动恢复原始版本。通过结果写入评分记忆（③），后续运行同一文件源哈希 + 依赖集哈希未变时直接**跳过重审/重转**。

### Phase 5 · Verify — 构建验证

`VerifyAgent`：`npm install`（`node_modules` 已存在则跳过，节省每次重试约 30s）→ `tsc --noEmit` → 失败自动修复并重试。修复循环由 LangGraph `StateMachine` 驱动（install → build → check → fix → build…）。tsc 错误自动解析为结构化对象（`TscErrorGroup`），按 import → declaration → type → syntax → unused 优先级排序修复；**无进展检测**——连续两轮错误签名完全一致时判定修复无进展，直接 `gave_up` 停止而非重复调用 LLM。修复所需的跨文件上下文优先通过 RAG 检索类型定义，回退策略为扫描 import 语句提取导出签名。

**修复方式为「ReAct 优先 + 单次兜底」两路径混合**：
- **ReAct 自验证循环（首选）**：LangGraph ReAct agent 绑定 `VERIFY_FIX_TOOLS`（`read_source_file` / `write_output_file` / `run_tsc_check` / `run_build_check`），按「读 → 写 → 本地 tsc 自验证 → 迭代直到 BUILD_OK」工作（`recursion_limit=20`）。内部调用绕过 `harness.call()`，但经 `record_usage()` / `over_budget()` 与主账本共享 Token 计量与预算守护。
- **单次调用兜底**：当模型不支持 function calling，或 ReAct 未产生有效写入时，回退为单次 `harness.call(task_type="verify_fix")` —— 内联文件 + 结构化错误 + 跨文件导出签名 + 修复记忆，直接返回完整修正文件，由外层 StateMachine 以 `tsc` 验证。
- 修复成功（tsc 通过）即写入 fix-memo（②），下次同 `error_code` 时自动注入提示。

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
export MODEL_ROUTES='{"convert":{"model":"<强模型>","fallback_model":"<备用模型>"}}'   # 可选，按任务路由，见「模型路由」
```
**3. `.env` 文件**（项目根目录，`python-dotenv` 自动加载）
```env
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.deepseek.com

# ── 模型路由（可选，见「模型路由」章节）──
# MODEL_ROUTES={"convert":{"model":"claude-sonnet-5","fallback_model":"deepseek-chat"}}

# ── Harness 特性 ──
# TOKEN_BUDGET=0                                    # 0=不限；硬上限，超限中止调用
# CACHE_ENABLED=true                                # 响应缓存开关
# CACHE_TTL_HOURS=24
# MEMORY_ENABLED=true                               # 跨运行记忆开关
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
├── .token_ledger.jsonl              # Token 账本（每阶段输入/输出/缓存命中/推理 token）
├── .llm_cache.json                  # 响应缓存（装配输入哈希 → 输出，TTL 过期）
├── .memory.json                     # 跨运行记忆（few-shots / fix-memos / 评分记忆 / 项目摘要）
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
├── .env.example                      # 环境变量示例（含模型路由 / Harness 开关）
├── orchestration/                    # 编排层
│   ├── pipeline.py                   #   LangGraph StateGraph 主编排
│   └── setup.py                      #   RN 项目骨架生成
├── agents/                           # Agent 层
│   ├── base.py                       #   Agent 基类 + Agent 工厂
│   ├── scan_agent.py                 #   文件扫描分类
│   ├── convert_agent.py              #   代码转换
│   ├── reflect_agent.py              #   质量审查+重转
│   └── verify_agent.py               #   构建验证+修复
├── tools/                            # @tool 函数（TOOLS + VERIFY_FIX_TOOLS 双注册表）
├── prompts/                          # LLM 提示词模板
├── framework/                        # 基础设施
│   ├── config.py                     #   配置（预算/缓存/记忆字段 + .env 解析）
│   ├── harness.py                    #   LLM 统一编排（自适应/账本/缓存/记忆/预算/重试封顶）
│   ├── memory.py                     #   跨运行记忆（few-shots / fix-memos / 评分记忆 / 摘要）
│   ├── llm.py                        #   多模型路由实例池
│   ├── state.py                      #   状态持久化
│   ├── state_machine.py              #   状态机
│   └── rag.py                        #   RAG 引擎
├── templates/                        # RN 项目模板
├── tests/                            # pytest 测试（93 用例）
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
