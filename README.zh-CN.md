[English](README.md) | [简体中文](README.zh-CN.md)

# Codex Orchestration

一套有明确纪律、可跨平台使用的 Codex 自定义子代理与独立 Worktree Root 编排系统。它不只提供一组 Agent，而是给每个根任务一套完整的工作方式：什么时候值得委派、每个子代理必须拿到哪些上下文、谁可以写入、并行 Worktree 工作线如何整合、如何验收结果，以及不同风险的改动需要多强的独立 Review。

Codex Orchestration 刻意不追求“Agent 越多越好”。简单任务仍由主代理直接完成；只读 Agent 可以按证据范围或独立观点并行调查，每个根任务内部则遵循本地单 Writer 租约。当用户明确要求使用 Codex 官方 Worktree，且任务可以安全拆分时，一个 Integration Root 最多可协调三个独立 Worktree Root 并行实现。每个 Worktree Root 都在分配的工作线内按普通根任务运行；全部声明工作线通过交接验收前，Integration Root 及其本地 Worker 均不得写仓库，之后它才串行合并整批结果并负责最终 Review 与交付。

项目仓库：[github.com/TimWongUp/codex-orchestration](https://github.com/TimWongUp/codex-orchestration)

## 安装

要求：macOS 或原生 Windows、已启用自定义子代理的 Codex，以及 Python 3.9 或更高版本。

下载或克隆仓库后，在项目目录运行：

```text
python3 scripts/install.py
```

首次安装会根据系统语言建议 `zh-CN` 或 `en`，输出完整计划，再询问一次是否应用；以后更新直接复用已有语言。默认目标是 `~/.codex` 和 Codex 官方用户 Skill 目录 `~/.agents/skills`。原生 Windows 只需把 `python3` 换成 `py -3`。

非交互环境不会询问并默认只做 dry run；首次运行须传入 `--language zh-CN` 或 `--language en`，确认计划后追加 `--apply`。非标准运行时仍可通过 `--codex-home` 和 `--skills-root` 覆盖默认路径。

Setup 会复制必需的 Skills 和 Agent 配置，并在当前生效的全局 `AGENTS.md` 或 `AGENTS.override.md` 中注入一个带归属标记的编排与代码 Review 规则块。它只写入这份现行投影，保留所有未托管的 Agent 配置、Hook 注册与文件、规则块外的个人指令、本机模型路由和其他用户文件。托管目标上的符号链接、归属冲突或标记损坏会阻止整批写入；运行中的安装器捕获到应用或验证失败时会回滚已完成变更。清理旧版本资产属于另行由用户指定目标的维护动作。

使用 `--no-global-rules` 可保持全局指令不变；若已有本项目规则块，它必须已是当前版本，旧 Review 路由会阻止计划。

卸载全局 Runtime 时，先预览完整移除计划，再应用同一计划：

```text
python3 scripts/install.py --uninstall
python3 scripts/install.py --uninstall --apply
```

交互式终端会再次询问确认，不必手动追加 `--apply`。卸载只移除仍与当前 checkout 完全一致的
托管文件和带归属标记的全局规则块；本机模型路由、Hooks、个人指令、未托管 Agents 与 Skills、
项目规则和额外文件全部保留。任何托管文件已被修改或规则标记损坏，都会阻止整批操作；不提供
强制删除模式。

完整且唯一权威的安装流程位于 [INSTALL.md](INSTALL.md)，其中也定义了冲突处理与运行时验证标准。

本仓库是可移植 Skills、Agents、安装器与全局规则受控块的唯一源码。安装文件只是可替换的运行产物；模型路由和无关 Hook 注册保留在本机。共享 context、memory-routing 与 closeout Hook 继续由其 Runtime 仓库拥有。

## 鲜明特点

- **委派有门槛。** 只有并行证据、专业分工或边界清晰的 Worker 能实质改善结果时，才启动子代理；独立交付门只授权它选中的只读 Reviewer。
- **交接保留有效压缩。** 委派使用自然语言简报，任务、必要上下文、交接重点和参考资料都只是可选结构，不要求固定字段或临时文档；Agent 自行恢复普通仓库上下文并返回可追溯证据。
- **任务语言保留在本机。** 初始化可持久化选择英文或简体中文的委派措辞；角色名、路径和外部协议字面量保持稳定。
- **读取可并行，根任务内写入串行。** Explorer、研究和 Review Agent 可以并发；每个根任务内同一时刻只能由主代理或一个获得租约的 Worker 写入。
- **并行 Worktree 使用对等根任务。** 经用户明确授权并通过准入门后，Integration Root 最多
  协调三个独立 Worktree Root。它们在隔离 checkout 中正常使用子代理。
- **编排权只属于根任务。** 派生 Agent 不调用协作工具，也不编排后代、同级或其他 Agent；
  Panel 成员身份不会改变这一边界。
- **并发按会话设上限。** 每个根会话最多使用八个派生 Agent 线程，不计主代理；宿主上限
  更低时以宿主为准。
- **等待取决于结果依赖。** 待返回结果可能改变决定、写入或最终回答时，主代理先等待；只有独立且不重叠的工作可以继续。
- **v2 策略位于工具之上。** 模型可见的协作工具 schema 负责调用机制；Skill 只补充普通委派的新上下文默认值、依赖等待、旧状态失效、显式停止收敛和 Worker 轮次上限。
- **协作方式有明确语义。** `coverage` 拆分证据范围，`panel` 让不同模型独立回答同一问题，
  `hybrid` 则让同题 Panel 与彼此独立的专项工作流并行。`single` 只是普通单代理路径，不属于
  多代理评估模式；任何模式都不会把多数票当作真相。
- **Review 是独立交付门。** `codex-review-gate` 独立定义路由，根主代理执行分级和整改：R0 覆盖局部自包含、主代理已完整验证且不存在实质失败假设的改动，运行行为变化与自包含说明性产物也可归入 R0；R1 对一个局部、已验证、可恢复且独立判断可能改变交付的实质失败假设使用一名 Reviewer，局部公共合同或托管策略改动也可属于 R1；R1 默认使用 `correctness-reviewer`，唯一风险明确属于专项时由匹配的专项 Reviewer 替代而非叠加；R2 覆盖多个独立风险、广泛或难恢复的公共合同、敏感边界及实质性不确定；R3 对信任边界变化或高影响失败追加专项整改与对抗式复核。R1–R3 始终至少使用一名匹配 Reviewer，只有新增实质失败假设才增加席位，不设人数配额。
- **Review 结论保留证据类别。** Reviewer 留在指定变更边界和风险内；当结论依赖任务或 Spec 要求、仓库规范时，引用对应来源并标明证据类别，不因此启动通用 Standards/Spec 审查。判断性风险明确标注，当前通过的工具已能确定覆盖的检查不再重复报告，除非工具覆盖本身存在疑问。接受的 finding 修复后，由原 Reviewer 在同一线程做定向复核；这不等于为取得 clean 报告而重启整轮 Review。
- **测试必须值得其维护成本。** 可写 Agent 只在测试能通过正确的可观察 seam 提供独特信心时才补测试，并优先扩展成本最低的合适层级中的现有测试。测试可靠性 Reviewer 还会识别为覆盖率凑数、重复、绑定实现或文案、不稳定及只保留退役兼容性的测试，但只有在等价行为与故障保护仍然存在时才建议删除。
- **模型路由留在本机。** Agent 配置不绑定模型；角色顺位、任务级覆盖、按主代理家族区分的
  Panel 阵容和宿主强制的服务层级要求都按本机配置。只有 `panel` 与 `hybrid` 的 Panel 部分读取
  宿主最新模型绑定，普通委派直接使用本地角色路由。
- **不夸大安全边界。** Worker 角色表达编排租约，不是操作系统权限控制；最终仍由主代理检查完整 diff 与验证证据。

## 适合谁

当前版本以 macOS 和原生 Windows 上的 Codex 为目标，提供可复用的代码探索、资料研究、正式实现、原型、疑难 Bug 和专项 Review 子代理。候选版本只有在两个平台的 CI 都通过后才声明受支持。

安装在两个平台上共用一个确定性、默认 dry run 的 Python 实现。Agent 可以在完整阅读 `INSTALL.md` 后代为运行，但不再自行重建文件投影。

## 第一次成功使用

安装后新建 Codex 任务，再输入：

```text
使用 explorer 子代理梳理这个功能的真实执行路径，先汇总证据，再提出修改方案。
```

讨论功能时，可以让 Codex 使用 `web-researcher` 调查公开实现模式，或使用 `reference-researcher` 核对官方文档。

## 包含什么

- 负责委派简报、本地写入租约、Worktree Root 协调、验收和通用 Agent 执行的根任务编排 Skill。
- 独立定义 R0–R3 路由、且只授权所选只读 Reviewer 的 `codex-review-gate` Skill；分级、整改和交付由根主代理执行。
- `diagnosing-bugs-worker` 与 `prototype-worker` 使用的完整方法 Skill。
- 只读代码探索、官方资料研究、Web 研究、专家和专项 Review Agent。
- 受每个根任务单 Writer 租约约束的实现、Bug 诊断和原型 Worker。
- 不安装项目 Hook；工具 schema 负责调用机制，Skill 负责编排策略，Agent 配置负责派生代理职责边界。
- 一个精简的全局 `AGENTS.md` 受控块：分别路由子代理执行与代码变更 Review，同时不替换个人指令。
- 可选的本地模型路由文件；仓库不固定任何模型 ID。
- 面向 macOS 与原生 Windows、带计划、归属检查、回滚和运行时验证的确定性安装与卸载契约。

写入租约是编排合同，不是操作系统 ACL。每个根任务始终负责自己的本地 Git 与验证；Integration Root 始终负责跨 Worktree 合并、最终 Reviewer 选择和最终交付。

## 继续阅读

- [架构](docs/architecture.md)
- [配置](docs/configuration.md)
- [Hooks 与长期规则提示词](docs/hooks-and-prompts.md)
- [确定性安装契约](INSTALL.md)
- [贡献指南](CONTRIBUTING.md)
- [安全策略](SECURITY.md)

随包方法 Skill 的原作者为 Matt Pocock，以 MIT License 分发，详见[第三方声明](THIRD_PARTY_NOTICES.md)。

## 许可证

Codex Orchestration 使用 [MIT License](LICENSE)；随包第三方材料保留其原始声明和许可证。
