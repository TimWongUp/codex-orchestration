[English](README.md) | [简体中文](README.zh-CN.md)

# Codex Orchestration

一套面向 macOS 的 Codex 自定义子代理编排工具：由主代理统一编排，同一时刻只有一个 Writer，任务包显式传递，模型路由可自定义，Review 按风险选择。

它的目标是让多代理开发可预测，同时避免把每个任务都变成“代理委员会”。简单工作仍由主代理完成，只有收益明确时才委派。

## 适合谁

如果你在 macOS 上使用 Codex，并希望复用代码探索、资料研究、正式实现、原型、疑难 Bug 和专项 Review 子代理，可以使用本项目。

当前版本有意只支持 macOS。Windows 的打包和运行行为尚未声明支持。

## 从本地仓库安装

要求：macOS、已启用自定义子代理的 Codex，以及 Python 3.9 或更高版本。

```bash
python3 scripts/validate.py
python3 scripts/install.py
python3 scripts/install.py --apply --with-hooks
```

安装器第一次运行只输出计划，并在任何写入前检查三个 Skill 名称以及全部受管 Agent、Hook 和路由目标。主机上已有合法同名 Skill 时直接复用且不修改；发生冲突或未批准的漂移时，不执行计划并停止安装。无关 Agent 和 Hook 会被保留；如受管文件已漂移，必须显式传入 `--replace` 才会覆盖。

### 让 Agent 安装

在本仓库中打开 Codex 任务，然后使用完整的 [Agent 安装提示词](docs/agent-install.md)。它会要求 Agent 先检查仓库、dry-run 全部变更，分别确认 Hooks 和模型路由，并验证最终运行时。

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
- 保留无关 Codex 配置的 macOS 安装器。

写入租约是编排合同，不是操作系统 ACL。主代理始终负责 Git、验收、Reviewer 选择和最终交付。

## 继续阅读

- [架构](docs/architecture.md)
- [配置](docs/configuration.md)
- [Hooks 与长期规则提示词](docs/hooks-and-prompts.md)
- [Agent 安装提示词](docs/agent-install.md)
- [贡献指南](CONTRIBUTING.md)

随包方法 Skill 的原作者为 Matt Pocock，以 MIT License 分发，详见[第三方声明](THIRD_PARTY_NOTICES.md)。

## 许可证

Codex Orchestration 使用 [MIT License](LICENSE)；随包第三方材料保留其原始声明和许可证。
