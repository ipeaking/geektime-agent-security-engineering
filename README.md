# Agent Security Engineering

这是《AI 安全工程化实战》课程的配套项目。代码会随课程逐讲演进，每一讲的稳定版本都会用 Git Tag 保留。

## 课程代码地图

- 第 01 讲 `lesson-01-prompt-injection`：用 Live 与 Replay 研究间接提示词注入及其工程后果。
- 第 02 讲 `lesson-02-threat-model`：把参与者、资产、边界和威胁保存成可校验的 Threat Model as Code。
- 第 03 讲（当前开发版本）：用 Context Lab 观察同一注入载荷从不同来源、包装方式和 Prompt Profile 进入上下文时的模型行为。

切换到某一讲的 Tag 后再运行对应实验，可以避免后续代码变化影响前面课程。

## 第 01 讲：Prompt Injection

- **Live 模式**把只含自然语言恶意指令的网页交给真实模型，观察模型是否会自主提出越权工具调用。结果具有不确定性，不作为稳定回归测试。
- **Replay 模式**读取独立的工具调用轨迹，假设模型已经提出错误动作，稳定验证缺少任务级授权的执行器会产生什么受控副作用。

两种模式职责不同，不能互相冒充。

> 安全说明：文件工具只访问运行时生成的合成工作区；诊断工具只连接 `127.0.0.1` 本地接收器；配置里没有真实凭证。请勿移除这些限制后在真实工作区运行攻击实验。

## 实验准备：搭建 Python 环境并配置 DeepSeek

本课程统一使用 Python 3.12。Replay 模式不调用真实模型，但建议在开始实验前一次性完成环境和 DeepSeek 配置，这样后续可以直接切换 Live 与 Replay 两条路径。

### 1. 确认 Python 3.12

macOS / Linux：

```bash
python3.12 --version
```

Windows PowerShell：

```powershell
py -3.12 --version
```

预期看到 `Python 3.12.x`。如果命令不存在，请先从 [Python 官方网站](https://www.python.org/downloads/) 安装 Python 3.12，再继续下面的步骤。

### 2. 创建并激活虚拟环境

macOS / Linux：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell：

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
```

激活成功后，终端提示符通常会出现 `(.venv)`。项目已经在 `.gitignore` 中忽略 `.venv/`。

激活后，再运行 `python --version`，确认当前虚拟环境仍然显示 `Python 3.12.x`。

### 3. 安装项目和 Live 模式依赖

macOS / Linux：

```bash
python -m pip install --upgrade pip
python -m pip install -e '.[deepseek]'
```

Windows PowerShell：

```powershell
python -m pip install --upgrade pip
python -m pip install -e ".[deepseek]"
```

### 4. 创建 DeepSeek API Key

登录 [DeepSeek 开放平台](https://platform.deepseek.com/api_keys) 创建并复制 API Key。不要把真实 Key 写进源码、`.env.example`、文章截图或 Git 提交。

### 5. 创建本地配置文件

`.env.example` 位于仓库根目录，与 `README.md`、`Makefile` 和 `pyproject.toml` 同级。

macOS / Linux：

```bash
cp .env.example .env
```

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

打开新生成的 `.env`，填写：

```dotenv
DEEPSEEK_API_KEY=sk-替换成你的真实Key
DEEPSEEK_MODEL=deepseek-v4-pro
```

`.env` 已被 `.gitignore` 忽略。不要把真实 Key 填进 `.env.example`。

### 6. 检查依赖和配置

先确认 Live 模式依赖已经安装：

```bash
python -c "import openai, dotenv; print('live dependencies ok')"
```

再检查配置。下面的命令不会打印完整 Key：

```bash
python -c "from dotenv import dotenv_values; c=dotenv_values('.env'); print('key configured:', bool(c.get('DEEPSEEK_API_KEY')), 'model:', c.get('DEEPSEEK_MODEL'))"
```

预期输出类似：

```text
key configured: True model: deepseek-v4-pro
```

## 运行 Replay 实验

正常行为基线：

```bash
make lab-normal
```

确定性攻击回放：

```bash
make lab-attack-replay
```

运行测试：

```bash
make test
```

没有 `make` 时，macOS / Linux 可以直接运行：

```bash
PYTHONPATH=src python -m agent_security.lab.runner --case normal --provider replay
PYTHONPATH=src python -m agent_security.lab.runner --case attack --provider replay
PYTHONPATH=src python -m unittest discover -s tests -p "test_*.py" -v
```

Windows PowerShell：

```powershell
$env:PYTHONPATH="src"
python -m agent_security.lab.runner --case normal --provider replay
python -m agent_security.lab.runner --case attack --provider replay
python -m unittest discover -s tests -p "test_*.py" -v
```

## 运行 Live 实验

macOS / Linux：

```bash
make lab-attack-live
```

没有 `make` 或使用 Windows 时：

```bash
python -m agent_security.lab.runner --case attack --provider deepseek
```

Runner 会自动读取仓库根目录的 `.env`。命令行传入的 `--model` 会覆盖 `.env` 中的 `DEEPSEEK_MODEL`。

Live 模式中的网页把越权操作伪装成可见的“接入前兼容性检查”，其中只有自然语言和工具名称，没有 `data-lab-*` 一类程序控制属性。模型可能服从，也可能拒绝。一次未触发不代表系统安全，一次触发也不代表固定攻击成功率。

## 运行时证据

每次运行都会创建新的临时合成工作区，并生成不同的 Canary：

```text
COURSE-CANARY-<随机 UUID>
```

运行结果保存在 `.lab-output/`：

```text
.lab-output/
├── audit.jsonl
├── diagnostic.jsonl
└── runtime-workspace/
    └── demo-config.json
```

`audit.jsonl` 记录工具提议和执行，`diagnostic.jsonl` 记录本地接收器实际收到的数据。攻击是否造成影响要通过工具轨迹和受控副作用判断，不能只看最终回答。

## 项目结构

```text
src/agent_security/agent/                    Live 与 Replay Runtime
src/agent_security/tools/                    工具注册和故意缺少授权的执行器
src/agent_security/audit/                    JSON Lines 审计日志
labs/lesson_01_prompt_injection/             页面、Case、Replay 轨迹和合成数据模板
tests/security/test_lesson_01_prompt_injection.py
```

当前版本已有实验环境隔离，但故意缺少任务级授权、资源 Scope、Policy Engine、审批和数据流检查。后续课程会在同一项目上逐步增加这些能力。

## 第 02 讲：威胁模型

第二讲不增加防御功能，而是把第一讲系统的参与者、资产、组件、信任边界、数据流和威胁保存为结构化 TOML，并自动生成一份 Markdown 报告。

```bash
make threat-model-validate
make threat-model-render
make threat-model-check
make lesson-02
```

详细说明见 `labs/lesson_02_threat_model/README.md`，生成的完整报告位于 `labs/lesson_02_threat_model/generated/threat_model_report.md`。

## 第 03 讲：Context Lab

第三讲使用六个控制变量 Case，把确定性的上下文构建与真实模型观察分开：

```bash
make context-lab-inspect
make context-lab-render
make context-lab-check
make lesson-03
```

`make lesson-03` 不调用模型、不访问公网，也不需要 API Key。确认实验内容全部是合成数据后，可以手工运行 `make context-lab-live` 和 `make context-lab-report`。Live 中的 Observation Executor 只记录 `read_file` 和 `send_diagnostic` 提议，不执行敏感工具；它是测量装置，不是生产安全防御。

详细说明见 `labs/lesson_03_prompt_injection_mechanism/README.md`。
