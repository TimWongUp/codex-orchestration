[English](README.md) | [简体中文](README.zh-CN.md)

# Codex Orchestration

一套有明确纪律、可跨平台使用的 Codex 自定义子代理编排系统。它不只提供一组 Agent，而是给主代理一套完整的工作方式：什么时候值得委派、每个子代理必须拿到哪些上下文、谁可以写入、如何验收结果，以及不同风险的改动需要多强的独立 Review。

Codex Orchestration 刻意不追求“Agent 越多越好”。简单任务仍由主代理直接完成；只读 Agent 可以按证据范围或独立观点并行调查，正式实现则遵循全局单 Writer 租约。目标、Git、验证、Reviewer 选择和最终交付始终由主代理负责，让并行协作真正增加覆盖面，而不是稀释责任。

项目仓库：[github.com/TimWongUp/codex-orchestration](https://github.com/TimWongUp/codex-orchestration)

## 用 Codex 安装

要求：macOS 或原生 Windows、已启用自定义子代理的 Codex，以及用于验证的 Python 3.9 或更高版本。

在 Codex 中打开本仓库，然后粘贴下面这段提示词：

```text
从 https://github.com/TimWongUp/codex-orchestration 为我的本地 Codex 环境安装 Codex Orchestration。完整阅读 INSTALL.md，修改前先展示全部计划，并保留无关或未经我批准的配置。
```

Agent 会先验证仓库，实际探测 Codex Home 和当前生效的 Skill 根目录，而不是猜测路径；随后分类每个安装目标，并在写入前展示全部变更。必需的 Skill 和 Agent 配置使用复制安装以保证可移植性；首次配置时选择任务包语言，Hooks 与模型路由分别作为可选决定。无关配置和未经批准的漂移会被保留。

完整且唯一权威的安装流程位于 [INSTALL.md](INSTALL.md)，其中也定义了冲突处理与运行时验证标准。

本仓库是可移植 Skill、Agent 与三个编排 Hook（`orchestration_route.py`、`subagent_scope.py`、`subagent_guard.py`）的唯一源码。安装文件只是可替换的运行产物；模型路由、可执行路径和 Hook 注册保留在本机。共享 context、memory-routing 与 closeout Hook 继续由其 Runtime 仓库拥有。

## 鲜明特点

- **委派有门槛。** 只有并行证据、专业分工或边界清晰的 Worker 能实质改善结果时，才启动子代理。
- **交接保留有效压缩。** 定义跨领域约束的项目架构、设计、ADR 和交接文档由主代理亲读；委派结果返回可追溯证据，否定结论说明检索边界，复核无需重做整轮搜索。
- **任务语言保留在本机。** 初始化可持久化选择英文或简体中文，任务包协议字段与控制字面量保持稳定。
- **读取可并行，写入必须串行。** Explorer、研究、设计和 Review Agent 可以并发；同一时刻只能由主代理或一个获得租约的 Worker 写入。
- **等待取决于结果依赖。** 待返回结果可能改变决定、写入或最终回答时，主代理先等待；只有独立且不重叠的工作可以继续。
- **协作方式有明确语义。** `coverage` 拆分证据范围，`panel` 比较不同模型的独立判断，`hybrid` 组合两者，但不会把多数票当作真相。
- **Review 强度随风险升级。** R0–R3 从主代理自行验收到专项 Reviewer、修复闭环和对抗式复核逐级增强。
- **模型路由留在本机。** Agent 配置不绑定模型；可选的角色顺位与任务级覆盖根据每台机器实际可用的模型独立配置。
- **不夸大安全边界。** Hooks 负责强化路由和身份提醒，最终仍由主代理检查真实 diff 与验证证据。

## 适合谁

当前版本以 macOS 和原生 Windows 上的 Codex 为目标，提供可复用的代码探索、资料研究、正式实现、原型、疑难 Bug 和专项 Review 子代理。候选版本只有在两个平台的 CI 都通过后才声明受支持。

安装由用户的 Agent 根据仓库内经过审查的安装契约执行。Agent 会检测当前 Codex 路径，并按平台处理文件与 Hook 配置，不依赖平台专用安装器。

## 第一次成功使用

安装后新建 Codex 任务，再输入：

```text
使用 explorer 子代理梳理这个功能的真实执行路径，先汇总证据，再提出修改方案。
```

讨论功能时，可以让 Codex 使用 `web-researcher` 调查公开实现模式，或使用 `reference-researcher` 核对官方文档。

## 包含什么

- 负责委派、任务包、写入租约、验收和 R0–R3 Review 门的主代理编排 Skill。
- `diagnosing-bugs-worker` 与 `prototype-worker` 使用的完整方法 Skill。
- 只读代码探索、官方资料研究、Web 研究、前端设计、专家和专项 Review Agent。
- 受全局单 Writer 租约约束的实现、Bug 诊断和原型 Worker。
- 可选 Hooks：强化主代理路由与等待全部结果的行为、派生代理职责边界，并阻止未标记的中断或过早关闭仍在运行的子代理。
- 可选的本地模型路由文件；仓库不固定任何模型 ID。
- 面向 macOS 与原生 Windows、保留无关 Codex 配置的 Agent 安装契约。

写入租约是编排合同，不是操作系统 ACL。主代理始终负责 Git、验收、Reviewer 选择和最终交付。

## 继续阅读

- [架构](docs/architecture.md)
- [配置](docs/configuration.md)
- [Hooks 与长期规则提示词](docs/hooks-and-prompts.md)
- [Agent 安装契约](INSTALL.md)
- [贡献指南](CONTRIBUTING.md)
- [安全策略](SECURITY.md)

随包方法 Skill 的原作者为 Matt Pocock，以 MIT License 分发，详见[第三方声明](THIRD_PARTY_NOTICES.md)。

## 许可证

Codex Orchestration 使用 [MIT License](LICENSE)；随包第三方材料保留其原始声明和许可证。
