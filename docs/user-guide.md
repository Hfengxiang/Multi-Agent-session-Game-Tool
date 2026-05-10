# Game Master 操作指南

## 概述

Game Master 是一个双 AI Agent 博弈框架。它启动两个 Claude Code 会话 — 一个**执行者**（修改文件）和一个**评价者**（评分反馈）— 通过迭代博弈使文件质量达到目标分数（默认 95 分）。

```
┌──────────┐     ┌───────────┐     ┌──────────┐
│ 执行者    │ ──→ │ 消息邮箱   │ ──→ │ 评价者    │
│ 修改文件   │     │           │     │ 评分反馈   │
└──────────┘     └───────────┘     └──────────┘
       ↑                                  │
       └──────── 分数 < 95 继续 ──────────┘
                分数 ≥ 95 完成 ✓
```

---

## 环境要求

- Python 3.10+
- Claude Code CLI（`claude` 命令在 PATH 中可用）
- 仅使用 Python 标准库，无需额外安装依赖

验证环境：
```bash
python --version          # 3.10+
claude --version          # 应输出版本信息
```

---

## 快速开始

### 1. 准备角色文件

创建两个 markdown 文件，定义执行者和评价者的角色：

**执行者角色**（`my-executor.md`）：
```markdown
你是一个资深 Python 工程师，擅长代码重构和性能优化。
对评价者的每一条反馈都要认真对待并做出具体改进。
```

**评价者角色**（`my-evaluator.md`）：
```markdown
你是一个严格的代码审查者，从以下维度评分（0-100）：
1. 代码清晰度
2. 错误处理
3. 性能
4. 可维护性
严格要求自己，95 分以上才表示代码达到生产级别。
```

### 2. 启动博弈

```bash
python game_master.py run \
    --task "优化 main.py 的代码质量和可读性" \
    --target /path/to/your/main.py \
    --executor-role my-executor.md \
    --evaluator-role my-evaluator.md
```

### 3. 观察输出

```
[GameMaster] Starting game for task: 优化 main.py 的代码质量和可读性
[GameMaster] Target: /path/to/your/main.py
[GameMaster] Max rounds: 10, Score threshold: 95

[Round 1] Executor: 重构了变量命名和提取了辅助函数 → Evaluator: 72分 | 结构改善但缺少类型注解
[Round 2] Executor: 添加了类型注解和文档字符串 → Evaluator: 88分 | 注解清晰但错误处理不足
[Round 3] Executor: 增加了异常处理和边界检查 → Evaluator: 96分 ✓ 达标！

=== Game Over ===
Status: completed
Rounds: 3
Best Score: 96
Work Dir: /path/to/your/.game-master/a1b2c3d4
```

---

## 命令参考

### run —— 启动博弈会话

```bash
python game_master.py run \
    --task <任务描述> \
    --target <目标文件或目录> \
    --executor-role <执行者角色文件> \
    --evaluator-role <评价者角色文件> \
    [--max-rounds <最大轮数>] \
    [--timeout <超时秒数>] \
    [--score-threshold <达标分数>] \
    [--task-id <自定义任务ID>]
```

| 参数 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `--task` | 是 | — | 任务描述，告诉执行者和评价者要做什么 |
| `--target` | 是 | — | 目标文件或目录的路径 |
| `--executor-role` | 是 | — | 执行者角色定义文件（.md） |
| `--evaluator-role` | 是 | — | 评价者角色定义文件（.md） |
| `--max-rounds` | 否 | 10 | 最大博弈轮数，超过后取最高分退出 |
| `--timeout` | 否 | 300 | 每轮 `claude -p` 调用超时（秒） |
| `--score-threshold` | 否 | 95 | 达标分数线，达到即停止 |
| `--task-id` | 否 | 自动生成 | 自定义任务 ID，用于后续控制命令 |

### control —— 发送控制指令

```bash
python game_master.py control \
    --control quit \
    --task-id latest \
    [--target <目标路径>]
```

| 参数 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `--control` | 是 | — | 指令类型，当前仅支持 `quit` |
| `--task-id` | 否 | `latest` | 任务 ID，`latest` 表示最近一次会话 |
| `--target` | 否 | 当前目录 | 博弈启动时使用的目标路径 |

---

## 中断机制

### 方式一：Ctrl+C

在运行 `python game_master.py run ...` 的终端中直接按 `Ctrl+C`，程序会完成当前轮后优雅退出：

```
^C
[GameMaster] Interrupted by user. Finishing current round...
=== Game Over ===
Status: aborted
```

### 方式二：控制消息队列

在另一个终端中发送 quit 指令：

```bash
python game_master.py control --control quit --task-id latest
```

程序在下一轮开始前检测到 quit 消息后退出。适用场景：远程控制、MCP 服务封装、脚本化编排。

---

## 配置参数建议

| 场景 | --max-rounds | --timeout | --score-threshold |
|------|-------------|-----------|-------------------|
| 快速试验 | 3 | 180 | 80 |
| 日常优化 | 5 | 300 | 90 |
| 高质量要求 | 10 | 600 | 95 |
| 严苛审查 | 15 | 600 | 98 |

**注意：** timeout 值需要根据任务复杂度调整。简单任务（如修改变量名）2-3 分钟足够，复杂任务（如重构整个模块）可能需要 5-10 分钟。

---

## 工作目录结构

每次博弈会话在目标路径旁创建 `.game-master/{task-id}/` 目录：

```
.game-master/a1b2c3d4/
├── mailbox/
│   ├── executor-inbox.json      # 评价者 → 执行者的消息（评分+反馈）
│   └── evaluator-inbox.json     # 执行者 → 评价者的消息（改动摘要）
├── control-queue.json           # 外部控制指令队列
└── history.jsonl                # 完整博弈记录（每行一条 JSON）
```

- **审计：** `history.jsonl` 包含所有轮次的完整记录
- **调试：** `mailbox/` 中的 JSON 文件可查看任意时刻的会话状态
- **清理：** 删除 `.game-master/` 即可清除所有运行时数据

---

## 角色文件编写指南

### 执行者角色要点

- 明确专业领域和技能
- 说明如何处理反馈（认真对待 / 逐条回应 / 有异议时说明理由）
- 可以补充输出风格偏好

### 评价者角色要点

- 列出评分维度（2-5 个）
- 说明各维度权重或评分逻辑
- 设定"生产就绪"标准（什么情况下给 95+）
- **重要：** 必须声明自己是只读角色，不可修改文件

### 示例：代码审查场景

**executor-cr.md:**
```markdown
你是高级后端工程师，擅长 Go 和 Python。
每次收到评价者反馈后：
1. 逐条回应每个问题
2. 对同意的建议立即修改
3. 对不同意的建议给出技术理由
修改完成后确保所有测试通过。
```

**evaluator-cr.md:**
```markdown
你是 SRE 团队的代码审查者，评分维度：
- 正确性（35%）：逻辑是否无误，边界是否覆盖
- 可读性（25%）：命名、结构、注释
- 性能（20%）：是否有多余分配、不必要复杂度
- 安全性（20%）：输入校验、错误处理、资源释放
95分以上 = 无明显缺陷，可安全上线。
你是只读角色，不得修改任何文件。
```

---

## 故障排查

### 问题：提示 "claude CLI not found in PATH"

```bash
# 检查 claude 是否安装
which claude        # Linux/Mac
where claude        # Windows

# 如未安装，参考 Claude Code 文档安装
npm install -g @anthropic-ai/claude-code
```

### 问题：Agent 反复超时

```
[GameMaster] Agent timed out (attempt 1/2), retrying...
[GameMaster] Agent timed out (attempt 2/2), retrying...
[GameMaster] Agent failed after 2 attempts. Stopping.
```

**原因：** timeout 设置太短或任务太复杂
**解决：** 增加 `--timeout` 参数，如 `--timeout 600`

### 问题：分数不收敛

如果评价者分数始终在低分徘徊且不上升：
- 检查评价者角色是否过于严格或不合理
- 检查执行者角色是否与任务不匹配
- 增加 `--max-rounds` 尝试更多迭代
- 检查 `mailbox/` 中的具体消息，确认沟通是否有效

### 问题：Windows 终端中文乱码

程序本身使用 UTF-8 编码。如果终端显示乱码：
- PowerShell：`chcp 65001` 切换到 UTF-8
- CMD：`chcp 65001`
- 或在 PowerShell 7+ 中运行
