# Azure Functions Doctor

[![PyPI](https://img.shields.io/pypi/v/azure-functions-doctor.svg)](https://pypi.org/project/azure-functions-doctor/)
[![Downloads](https://static.pepy.tech/badge/azure-functions-doctor/month)](https://pepy.tech/project/azure-functions-doctor)
[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)](https://pypi.org/project/azure-functions-doctor/)
[![CI](https://github.com/yeongseon/azure-functions-doctor-python/actions/workflows/ci-test.yml/badge.svg)](https://github.com/yeongseon/azure-functions-doctor-python/actions/workflows/ci-test.yml)
[![Release](https://github.com/yeongseon/azure-functions-doctor-python/actions/workflows/publish-pypi.yml/badge.svg)](https://github.com/yeongseon/azure-functions-doctor-python/actions/workflows/publish-pypi.yml)
[![Security Scans](https://github.com/yeongseon/azure-functions-doctor-python/actions/workflows/security.yml/badge.svg)](https://github.com/yeongseon/azure-functions-doctor-python/actions/workflows/security.yml)
[![codecov](https://codecov.io/gh/yeongseon/azure-functions-doctor-python/branch/main/graph/badge.svg)](https://codecov.io/gh/yeongseon/azure-functions-doctor-python)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://pre-commit.com/)
[![Docs](https://img.shields.io/badge/docs-yeongseon.dev-blue)](https://yeongseon.dev/azure-functions-python/doctor/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

其他语言: [English](README.md) | [한국어](README.ko.md) | [日本語](README.ja.md)

> ℹ️ 本翻译由社区维护，仅供参考，可能落后于最新的 [English README](README.md)。请以英文版为准。

Azure Functions Doctor 是一个用于诊断基于 **Azure Functions Python v2 编程模型** 构建的项目的 CLI 工具。

它会检查本地项目中存在的常见问题，例如：

- 不支持的 Python 版本
- 缺失 `host.json` 或 `requirements.txt`
- 缺失 `azure-functions` 依赖项
- 缺失虚拟环境 (virtual environments)
- 缺失 Azure Functions Core Tools
- 本地开发环境配置不完整

## Why Use It

设置 Azure Functions Python 项目需要多个配置文件、依赖项和工具。缺少任何一个都会导致令人困惑的运行时错误。`azure-functions-doctor` 会根据精选的规则集检查项目，并在问题到达生产环境之前报告。

## Scope

本项目仅针对基于装饰器的 Azure Functions Python v2 编程模型。

- 支持的模型：使用 `@app.route()` 等装饰器的 `func.FunctionApp()`
- 不支持的模型：传统的基于 `function.json` 的 Python v1 项目

## Installation

从 PyPI 安装：

```bash
pip install azure-functions-doctor
```

从源码安装：

```bash
git clone https://github.com/yeongseon/azure-functions-doctor.git
cd azure-functions-doctor
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Quick Start

在当前项目中运行 doctor：

```bash
azure-functions-doctor doctor
```

针对特定项目路径运行：

```bash
azure-functions-doctor doctor --path ./examples/v2/http-trigger
```

使用仅包含必要检查项的配置：

```bash
azure-functions-doctor doctor --profile minimal
```

为 CI 输出 JSON 格式：

```bash
azure-functions-doctor doctor --format json
```

### 命令名称与已弃用的别名

`azure-functions-doctor` 是**正式（canonical）**命令。两个旧的控制台
脚本别名仍可使用，但已**弃用（deprecated）**，调用时会打印警告：

| 命令 | 状态 |
| --- | --- |
| `azure-functions-doctor` | 正式 — 请使用此命令。 |
| `azure-functions` | 已弃用 — 计划在 **v1.0.0** 移除。 |
| `fdoctor` | 已弃用 — 计划在 **v1.0.0** 移除。 |

请在 v1.0.0 发布移除别名之前，将脚本或 CI 流水线迁移到
`azure-functions-doctor`。

有关涵盖 shell 脚本、GitHub Actions、Makefile 和 pre-commit 钩子的逐步示例，
请参阅[已弃用别名迁移指南](docs/deprecated-aliases.md)。

## Demo

以下演示是使用 VHS 从 [`demo/doctor-demo.tape`](demo/doctor-demo.tape) 生成的。
它通过对代表性示例项目以及一个故意损坏的副本运行真实的 `azure-functions-doctor doctor` CLI，来展示成功与失败的对比。

![Doctor demo](docs/assets/doctor-demo.gif)

最终的终端状态也被捕获为静态图像，以便快速查看。

![Doctor final output](docs/assets/doctor-demo-final.png)

## Features

默认规则集会验证以下内容：

- Azure Functions Python v2 装饰器的使用情况
- Python 版本
- 虚拟环境激活状态
- Python 可执行文件的可用性
- `requirements.txt`
- `azure-functions` 依赖声明
- `host.json`
- `local.settings.json` (可选)
- Azure Functions Core Tools 的存在及其版本 (可选)
- Durable Functions 主机配置 (可选)
- Application Insights 配置 (可选)
- `extensionBundle` 配置 (可选)
- ASGI/WSGI callable 的公开情况 (可选)
- 项目树中常见的冗余文件 (可选)

## Examples

- [examples/v2/http-trigger/README.md](examples/v2/http-trigger/README.md)
- [examples/v2/multi-trigger/README.md](examples/v2/multi-trigger/README.md)

## Requirements

- Python 3.10+
- 开发工作流所需的 Hatch
- 建议安装 Azure Functions Core Tools v4+ 以进行本地运行

## Documentation

- [docs/index.md](docs/index.md)
- [docs/usage.md](docs/usage.md)
- [docs/rules.md](docs/rules.md)
- [docs/diagnostics.md](docs/diagnostics.md)
- [docs/development.md](docs/development.md)

## Ecosystem

本包是 **Azure Functions Python DX Toolkit** 的一部分。

**设计原则：** `azure-functions-doctor` 负责部署前诊断。它不修复问题或生成代码 —— 而是呈现可操作的发现，供开发者自行修复。运行时行为归属于 [`azure-functions-openapi`](https://github.com/yeongseon/azure-functions-openapi-python)（API 文档与规范生成）、[`azure-functions-validation`](https://github.com/yeongseon/azure-functions-validation-python)（请求/响应校验）和 [`azure-functions-langgraph`](https://github.com/yeongseon/azure-functions-langgraph-python)（LangGraph 运行时暴露）。

| 包 | 职责 |
|---------|------|
| [azure-functions-openapi-python](https://github.com/yeongseon/azure-functions-openapi-python) | OpenAPI 规范生成与 Swagger UI |
| [azure-functions-validation-python](https://github.com/yeongseon/azure-functions-validation-python) | 请求/响应校验与序列化 |
| [azure-functions-db-python](https://github.com/yeongseon/azure-functions-db-python) | 基于 SQLAlchemy 的数据库集成助手（基于轮询的伪触发器，输入/输出/客户端注入） |
| [azure-functions-langgraph-python](https://github.com/yeongseon/azure-functions-langgraph-python) | 面向 Azure Functions 的 LangGraph 部署适配器 |
| [azure-functions-scaffold-python](https://github.com/yeongseon/azure-functions-scaffold-python) | 项目脚手架 CLI |
| [azure-functions-logging-python](https://github.com/yeongseon/azure-functions-logging-python) | 结构化日志与可观测性 |
| **azure-functions-doctor-python** | 部署前诊断 CLI |
| [azure-functions-durable-graph-python](https://github.com/yeongseon/azure-functions-durable-graph-python) | 基于 Durable Functions 的清单优先图运行时 *(实验性)* |
| [azure-functions-knowledge-python](https://github.com/yeongseon/azure-functions-knowledge-python) | 知识检索（RAG）装饰器 |
| [azure-functions-cookbook-python](https://github.com/yeongseon/azure-functions-cookbook-python) | 内部实践示例 — 可运行的完整工具链演示 |

## Disclaimer

本项目是独立的社区项目，与 Microsoft 没有关联，也未获得 Microsoft 的认可或维护。

Azure 和 Azure Functions 是 Microsoft Corporation 的商标。

## License

MIT
