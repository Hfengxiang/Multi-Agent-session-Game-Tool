# Game Master — 双智能体博弈框架设计

## 概述

独立 Python CLI 程序，让两个 AI Agent 会话通过消息队列进行对抗/协作博弈。执行者修改文件，评价者评分反馈，循环迭代直到评分达标。Adapter 模式支持多种 Agent 后端（Claude Code / Codex / Gemini），当前只实现 Claude Code。

## 架构流程图

```
                            ┌──────────────────────────────┐
                            │        用户终端 (Ctrl+C)       │
                            └──────────────┬───────────────┘
                                           │ SIGINT
                                           ▼
┌──────────────┐    启动      ┌──────────────────────────┐
│   CLI 入口    │ ──────────→ │      GameMaster           │
│              │             │                          │
│ --task       │             │  ┌────────────────────┐  │
│ --exec-role  │             │  │  ControlQueue      │  │
│ --eval-role  │             │  │  (control-queue    │  │
│ --max-rounds │             │  │   .json)           │  │
│ --timeout    │             │  └─────────┬──────────┘  │
└──────────────┘             │            │ 每轮前检查    │
                             │            ▼              │
                             │  ┌────────────────────┐  │
                             │  │   主循环            │  │
                             │  │   round = 1..N     │  │
                             │  └─────────┬──────────┘  │
                             │            │              │
                             │     ┌──────┴──────┐      │
                             │     ▼              ▼      │
                             │ ┌────────┐  ┌─────────┐  │
                             │ │Executor│  │Evaluator│  │
                             │ │ Turn   │  │ Turn    │  │
                             │ └───┬────┘  └────┬────┘  │
                             │     │            │        │
                             │     │  ┌─────────┘        │
                             │     ▼  ▼                  │
                             │ ┌──────────────────────┐  │
                             │ │   AgentAdapter       │  │
                             │ │                      │  │
                             │ │  ┌────────────────┐  │  │
                             │ │  │ ClaudeCode     │  │  │
                             │ │  │ Adapter        │  │  │
                             │ │  │ (claude -p)    │  │  │
                             │ │  └────────────────┘  │  │
                             │ │                      │  │
                             │ │  ┌────────────────┐  │  │
                             │ │  │ Codex Adapter  │  │  │
                             │ │  │ (codex exec)   │  │  │
                             │ │  └────────────────┘  │  │
                             │ │                      │  │
                             │ │  ┌────────────────┐  │  │
                             │ │  │ Gemini Adapter │  │  │
                             │ │  │ (gemini CLI)   │  │  │
                             │ │  └────────────────┘  │  │
                             │ └──────────┬───────────┘  │
                             │            │              │
                             │            ▼              │
                             │  ┌────────────────────┐  │
                             │  │   Mailbox (JSON)   │  │
                             │  │   history.jsonl    │  │
                             │  └────────────────────┘  │
                             └──────────────────────────┘
                                           │
                                           ▼
                                    终端输出摘要
                              (每轮一行，不污染上下文)
```

## 核心类图

```
                    ┌──────────────┐
                    │  GameMaster  │
                    ├──────────────┤
                    │ + run()      │
                    │ + stop()     │
                    └──────┬───────┘
                           │ 持有
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
    ┌──────────────┐ ┌──────────┐ ┌──────────────┐
    │ ControlQueue │ │ Agent    │ │   Mailbox    │
    │              │ │ Adapter  │ │              │
    │ + push()     │ │          │ │ + put()      │
    │ + pop_all()  │ │ + build  │ │ + get()      │
    │ + has_quit() │ │   _prompt│ │ + append_    │
    └──────────────┘ │ + execute│ │   history()  │
                     │ + parse  │ └──────────────┘
                     │   _output│
                     └────┬─────┘
                          │ 实现
              ┌───────────┼───────────┐
              ▼           ▼           ▼
    ┌──────────────┐ ┌──────────┐ ┌─────────────┐
    │ ClaudeCode   │ │ Codex    │ │ Gemini      │
    │ Adapter      │ │ Adapter  │ │ Adapter     │
    │ (当前实现)    │ │ (后续)   │ │ (后续)      │
    │              │ │          │ │             │
    │ claude -p    │ │ codex    │ │ gemini      │
    │ subprocess   │ │ exec     │ │ CLI         │
    └──────────────┘ └──────────┘ └─────────────┘
```

## Adapter 接口设计

```python
class AgentAdapter(ABC):
    """AI Agent 适配器抽象基类"""

    @abstractmethod
    def build_prompt(self, role: str, task: str, feedback: dict,
                     history: list) -> str:
        """构建发送给 Agent 的完整 prompt"""

    @abstractmethod
    def execute(self, prompt: str, allowed_tools: list,
                timeout: int) -> AgentResult:
        """调用 Agent CLI，返回执行结果"""

    @abstractmethod
    def parse_output(self, output: str) -> dict:
        """解析 Agent 输出，提取结构化信息"""

class ClaudeCodeAdapter(AgentAdapter):
    """Claude Code 适配器 — 通过 claude -p 子进程调用"""

    def build_prompt(self, ...):
        # 合并 base prompt + role + task + feedback + history

    def execute(self, ...):
        # subprocess.run(["claude", "-p", prompt], timeout=...)

    def parse_output(self, ...):
        # 正则提取分数 /score:\s*(\d+)/i
        # 提取改动摘要、反馈要点
```

后续扩展只需实现新 Adapter 子类，GameMaster 核心逻辑不变。

## 目录结构

```
E:\WorkSpace\Projects\GameTool\
├── game_master.py                # CLI 入口 + GameMaster 类
├── adapters/
│   ├── __init__.py
│   ├── base.py                   # AgentAdapter 抽象类
│   └── claude_code.py            # ClaudeCodeAdapter（当前实现）
├── core/
│   ├── __init__.py
│   ├── game_master.py            # 主循环 + 状态机
│   ├── control_queue.py          # 控制消息队列
│   └── mailbox.py                # 消息邮箱
├── prompts/
│   ├── executor-base.md          # 执行者预置系统提示词
│   └── evaluator-base.md         # 评价者预置系统提示词
├── templates/
│   ├── executor-role.md          # 用户角色模板（示例）
│   └── evaluator-role.md
└── .game-master/                 # 运行时自动创建
    ├── mailbox/
    │   ├── executor-inbox.json
    │   └── evaluator-inbox.json
    ├── control-queue.json
    └── history.jsonl
```

## 状态机

```
INIT
  │ 加载角色文件、校验参数
  ▼
CHECK_CONTROL_QUEUE ←──────────────────────┐
  │ 有 quit 消息 → ABORT                    │
  │ 无 → 继续                               │
  ▼                                         │
EXECUTOR_TURN                               │
  │ Adapter.build_prompt(executor)          │
  │ Adapter.execute(prompt, rw_tools)       │
  │ Adapter.parse_output()                  │
  │ Mailbox → evaluator-inbox.json          │
  ▼                                         │
EVALUATOR_TURN                              │
  │ Adapter.build_prompt(evaluator)         │
  │ Adapter.execute(prompt, ro_tools)       │
  │ Adapter.parse_output()                  │
  │ Mailbox → executor-inbox.json           │
  ▼                                         │
  ├── score ≥ threshold → DONE ─────────────┘
  ├── round ≥ max_rounds → DONE (取最高分)
  └── 否则 → CHECK_CONTROL_QUEUE (下一轮)
```

## 控制消息队列

`control-queue.json` 格式（消息数组）：

```json
[
  {"command": "quit", "timestamp": "2026-05-09T15:30:00"}
]
```

- 每轮开始前 `pop_all()` 消费全部消息
- 遇到 `quit` → 通知 Agent 停止（如子进程 kill）→ 输出摘要 → 退出
- 支持外部写入，为 MCP 封装预留

外部发送中断：
```bash
python game_master.py --control quit --task-id <id>
```

## 消息协议

### executor-inbox.json（评价者 → 执行者）
```json
{
  "round": 3,
  "from": "evaluator",
  "score": 72,
  "feedback": "变量命名不够清晰...",
  "strengths": ["结构合理"],
  "weaknesses": ["命名不规范"],
  "timestamp": "2026-05-09T15:30:00"
}
```

### evaluator-inbox.json（执行者 → 评价者）
```json
{
  "round": 3,
  "from": "executor",
  "changes": "修改了 resume.md 第12-45行...",
  "files_modified": ["resume.md"],
  "summary": "重新组织了技能描述段落",
  "timestamp": "2026-05-09T15:28:00"
}
```

## 错误处理

- 子进程超时：重试1次，仍失败则终止
- 子进程崩溃：输出已完成轮次摘要
- 评分提取失败：重试解析，仍失败则要求重试本轮
- 启动校验：目标路径/角色文件/Agent CLI 可用性/工作目录可写性

## 配置项

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--max-rounds` | 10 | 最大轮数 |
| `--timeout` | 300 | 子进程超时（秒） |
| `--score-threshold` | 95 | 达标分数线 |
| `--adapter` | claude_code | Agent 后端选择 |

## 终端输出

```
[Round 1] Executor: 修改了 resume.md（调整排版）→ Evaluator: 65分 | 排版改善但内容平淡
[Round 2] Executor: 修改了 resume.md（增加量化成果）→ Evaluator: 78分 | 量化数据有力
[Round 3] Executor: 修改了 resume.md（补充关键词）→ Evaluator: 96分 ✓ 达标！

博弈完成，共 3 轮，最终评分 96。
```
