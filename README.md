# TMS Research Collaboration System

基于 Transactive Memory System（TMS，交互记忆系统）理论的研究团队交互式协作原型。系统把项目事实、成员能力、专家网络、计划生成、任务交接、验收回流和共享记忆问答放进同一条闭环，用来模拟“谁知道什么、谁负责什么、谁验收什么、团队共同记住什么”。

## 核心功能

- 用户登录与项目广场：预置王博士、李同学、张老师三类演示成员，支持创建项目、申请加入、组长审批加入。
- 项目资料入库：支持粘贴文本、上传 PDF、上传 Markdown，经过审核后进入团队共享记忆层。
- 项目内能力画像：成员提交项目相关能力文本，系统结构化生成能力画像、置信度和专家网络。
- 智能规划闭环：分析 Agent、计划 Agent、任务发放 Agent 基于共享记忆生成计划草稿，组长审批后写入共享层并生成任务链。
- 任务交接与状态机：任务执行者提交成果，下游验收人确认，组长最终确认后推进下一步。
- 项目内 AI 助手：每位成员都可以向项目助手提问，助手只应基于共享层正式记忆回答。
- 风险与降级：LLM 输出不足时提供风险提示、补充材料建议和强制生成入口，规则模板作为降级模式保留。

## 技术栈

- 后端：Python、FastAPI、Pydantic、httpx、pypdf
- 前端：React、TypeScript、Vite、CSS
- 存储：当前演示版使用内存仓库，适合原型验证，不适合作为生产数据库
- LLM：默认配置 DeepSeek V4 Pro 的接口地址和模型名；公开仓库不包含 API Key

## 目录结构

```text
backend/
  app/                  # FastAPI 应用、TMS 内核、Agent、记忆与流程服务
  requirements.txt      # 后端运行依赖
  pyproject.toml        # Python 工具配置
frontend/
  src/                  # React 前端源码
  index.html
  package.json
  vite.config.ts
docs/
  2026-06-10-仓库技术实现文档.md
```

## 本地启动

后端：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8011
```

前端：

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5174
```

浏览器访问：

```text
http://127.0.0.1:5174
```

## LLM 配置说明

仓库版本不会提交真实 API Key。后端默认保留 DeepSeek V4 Pro 的服务地址、模型名和最大输出长度，但 `api_key` 为空。

运行时可以在前端的 LLM 配置区域填写：

```text
Base URL: https://api.deepseek.com/v1
Chat Model: deepseek-v4-pro
Embedding Model: deepseek-embedding
API Key: 你的本地密钥
```

如果要把系统改成“本地默认硬编码密钥”，请只在个人本地副本中修改 `backend/app/services/llm_provider.py`。默认配置位置如下：

```python
@dataclass(slots=True)
class LLMProviderConfig:
    provider_name: str = "DeepSeek V4 Pro"
    base_url: str = "https://api.deepseek.com/v1"
    chat_model: str = "deepseek-v4-pro"
    embedding_model: str = "deepseek-embedding"
    api_key: str = ""
```

把最后一行改成你自己的本地密钥即可：

```python
api_key: str = "sk-你的本地密钥"
```

改完后重启后端：

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8011
```

注意：真实密钥只建议保留在你自己的本地副本里，不要提交到 GitHub。

## 演示流程建议

1. 使用张老师创建项目，填写项目名称和基础说明。
2. 使用王博士、李同学在项目广场申请加入，张老师审批通过。
3. 所有成员上传项目资料或粘贴文本，张老师审核进入共享记忆。
4. 成员提交项目内能力画像，张老师审核后形成专家网络。
5. 张老师运行智能规划，检查风险提示和补料建议，必要时强制生成草稿。
6. 张老师批准计划，计划进入共享层并生成线性任务链。
7. 执行者提交任务成果，下游验收人验收，张老师最终确认后推进流程。
8. 任意成员使用项目助手查询当前共享层事实、任务状态和责任人。

## 注意事项

- 这是研究协作系统原型，不是生产级权限系统。
- 当前存储是进程内内存，后端重启后演示数据会恢复到种子状态。
- 公开仓库已排除测试目录、验证脚本、依赖缓存、构建产物、日志、临时模拟材料和本地参考仓库。
- 如果需要生产化，应补充持久化数据库、正式认证授权、审计日志落盘、文件存储、密钥管理和更严格的 LLM 输出校验。
