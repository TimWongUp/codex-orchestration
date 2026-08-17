[English](README.md) | [简体中文](README.zh-CN.md)

# Codex Orchestration

一套跨平台的 Codex 自定义子代理编排工具：由主代理统一编排，同一时刻只有一个 Writer，任务包显式传递，模型路由可自定义，Review 按风险选择。

它的目标是让多代理开发可预测，同时避免把每个任务都变成“代理委员会”。简单工作仍由主代理完成，只有收益明确时才委派。

## 适合谁

当前版本以 macOS 和原生 Windows 上的 Codex 为目标，提供可复用的代码探索、资料研究、正式实现、原型、疑难 Bug 和专项 Review 子代理。候选版本只有在两个平台的 CI 都通过后才声明受支持。

安装由用户的 Agent 根据仓库内经过审查的安装契约执行。Agent 会检测当前 Codex 路径，并按平台处理文件与 Hook 配置，不依赖平台专用安装器。

## 让 Agent 安装

要求：macOS 或原生 Windows、已启用自定义子代理的 Codex，以及用于验证的 Python 3.9 或更高版本。

在 Codex 中打开本仓库，然后输入：

```text
为我的本地 Codex 环境安装这个仓库。完整阅读 INSTALL.md，先展示全部计划，并保留无关或未经我批准的配置。
```

Agent 会验证仓库、检测当前平台和 Codex 路径、分类每个目标，并在写入前展示全部变更。必需的 Skill 和 Agent 配置使用复制安装以保证可移植性；Hooks 与模型路由分别作为可选决定。无关配置和未经批准的漂移会被保留。

完整且唯一权威的步骤位于 [INSTALL.md](INSTALL.md)，可以先审查再让 Agent 执行。

## 第一次成功使用

安装后新建 Codex 任务，再输入：

```text
使用 explorer 子代理梳理这个功能的真实执行路径，先汇总证据，再提出修改方案。
```

讨论功能时，可以让 Codex 使用 `web-researcher` 调查公开实现模式，或使用 `reference-researcher` 核对官方文档。

## 包含什么

- 支持 `coverage`、`panel`、`hybrid` 三种只读协作模式的主代理编排 Skill。
- `diagnosing-bugs-worker` 与 `prototype-worker` 使用的完整方法 Skill。
- 只读探索、研究、设计和专项 Review Agent。
- 受全局单 Writer 租约约束的实现、Bug 诊断和原型 Worker。
- 可选的 `UserPromptSubmit` 与 `SubagentStart` Hooks。
- 可选的本地模型路由文件；仓库不固定任何模型 ID。
- 面向 macOS 与原生 Windows、保留无关 Codex 配置的 Agent 安装契约。

写入租约是编排合同，不是操作系统 ACL。主代理始终负责 Git、验收、Reviewer 选择和最终交付。

## 继续阅读

- [架构](docs/architecture.md)
- [配置](docs/configuration.md)
- [Hooks 与长期规则提示词](docs/hooks-and-prompts.md)
- [Agent 安装契约](INSTALL.md)
- [贡献指南](CONTRIBUTING.md)

随包方法 Skill 的原作者为 Matt Pocock，以 MIT License 分发，详见[第三方声明](THIRD_PARTY_NOTICES.md)。

## 许可证

Codex Orchestration 使用 [MIT License](LICENSE)；随包第三方材料保留其原始声明和许可证。
