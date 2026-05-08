# Game Master — 双智能体博弈框架 开发进度

## 当前状态

**阶段：** 实现阶段 — Subagent-Driven Development  
**当前步骤：** Task 5 完成，准备 Task 6  
**最后更新：** 2026-05-09

---

## 进度总览

| Task | 内容 | 状态 |
|------|------|------|
| 1 | Mailbox（消息邮箱） | ✅ 已完成 |
| 2 | ControlQueue（控制队列） | ✅ 已完成 |
| 3 | AgentAdapter ABC + AgentResult | ✅ 已完成 |
| 4 | Prompt 模板 | ✅ 已完成 |
| 5 | ClaudeCodeAdapter + 单元测试 | ✅ 已完成（6/6 tests pass） |
| 6 | GameMaster 状态机 | ✅ 已完成 |
| 7 | CLI 入口 | ✅ 已完成 |
| 8 | 角色模板示例 | ✅ 已完成 |
| 9 | 集成测试 | ⏳ 进行中 |

- ⬜ 待开始 ⏳ 进行中 ✅ 已完成

---

## 设计决策记录

### 1. 架构形态
- **决策：** 独立 Python CLI 程序，不封装为 Skill，后续可封装为 MCP 服务
- **原因：** 用户担心 Skill 在对话中被意外修改；纯 Python CLI 更可靠

### 2. Agent 后端
- **决策：** Adapter 模式，只实现 ClaudeCodeAdapter（`claude -p` 子进程），Codex / Gemini 预留
- **原因：** 当前只需 Claude Code，但框架应支持扩展

### 3. 通信方式
- **决策：** 文件邮箱（JSON inbox）+ 控制消息队列（`control-queue.json`）
- **原因：** 简单可靠，天然持久化和审计，避免管道通信的复杂度和死锁风险

### 4. 子会话启动
- **决策：** Python 脚本通过 `subprocess.run(["claude", "-p", prompt])` 全自动启动，每轮独立会话
- **原因：** 用户要求尽量自动化，减少手动操作

### 5. 中断机制
- **决策：** 两种方式 — Ctrl+C (SIGINT) 和外部写 `control-queue.json` {"command":"quit"}
- **原因：** Ctrl+C 用于手动中断；消息队列方式为 MCP 远程控制预留

### 6. 评分机制
- **决策：** 评分标准由用户在角色文件中自由定义，程序只做正则提取
- **原因：** 通用框架不应绑定特定评分维度

### 7. 角色设定
- **决策：** 角色文件 (.md)，程序预置通用博弈规则（`prompts/*-base.md`）
- **原因：** 复杂角色适合文件形式，base prompt 提供通用规则骨架

### 8. 工作目录
- **决策：** `{target}/.game-master/{task-id}/` 运行时自动创建
- **原因：** 随目标位置自然放置，多个博弈任务互不干扰

### 9. 执行方式
- **决策：** Subagent-Driven Development（每 Task 一个子 agent + spec review + code quality review）
- **原因：** 用户选择的高质量实现方式

---

## 关键设计约束

- Python 3.11+，仅用标准库
- 每轮 `claude -p` 超时默认 300s，失败重试 1 次
- 最大轮数默认 10，评分阈值默认 95
- 执行者工具：Read/Write/Edit/Glob/Grep/Bash
- 评价者工具：Read/Glob/Grep/Bash（只读）
- 终端每轮只输出一行摘要，不污染主会话上下文

## 文件结构（规划）

```
E:\WorkSpace\Projects\GameTool\
├── game_master.py                # CLI 入口
├── adapters/
│   ├── __init__.py
│   ├── base.py                   # AgentAdapter ABC
│   └── claude_code.py            # ClaudeCodeAdapter
├── core/
│   ├── __init__.py
│   ├── game_master.py            # 主循环 + 状态机
│   ├── control_queue.py          # 控制消息队列
│   └── mailbox.py                # 消息邮箱
├── prompts/
│   ├── executor-base.md
│   └── evaluator-base.md
├── templates/
│   ├── executor-role.md
│   └── evaluator-role.md
└── .game-master/                 # 运行时
    ├── mailbox/
    ├── control-queue.json
    └── history.jsonl
```

---

## 对话摘要

1. 用户提出需求：双 Claude 会话博弈系统，Python 消息中心协调
2. 使用 brainstorming 技能进行需求澄清和设计
3. 确认方案：独立 Python CLI + Adapter 模式 + 文件邮箱 + 消息队列中断
4. 生成架构 HTML 图表（含中断路径）
5. 使用 writing-plans 生成 9-task 实现计划
6. 使用 subagent-driven-development 开始执行
7. 关联远程仓库 https://github.com/Hfengxiang/Multi-Agent-session-Game-Tool.git
8. Task 1-4 手动快速实现（Mailbox / ControlQueue / Adapter ABC / Prompts）
9. Task 5 子 agent 实现（ClaudeCodeAdapter + 6 单元测试 all pass）
