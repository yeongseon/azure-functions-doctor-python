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

他の言語: [English](README.md) | [한국어](README.ko.md) | [简体中文](README.zh-CN.md)

> ℹ️ この翻訳はコミュニティによる参考用であり、最新の [English README](README.md) より古い場合があります。正確な最新情報は英語版を参照してください。

Azure Functions Doctor は、**Azure Functions Python v2 プログラミングモデル**で構築されたプロジェクトのための診断 CLI ツールです。

このツールは、ローカルプロジェクトにおける以下のような一般的な問題をチェックします：

- サポートされていない Python バージョン
- `host.json` または `requirements.txt` の欠如
- `azure-functions` 依存関係の欠如
- 仮想環境（virtual environments）の欠如
- Azure Functions Core Tools の欠如
- 不完全なローカル開発環境のセットアップ

## Why Use It

Azure Functions Python プロジェクトのセットアップには、複数の設定ファイル、依存関係、ツールが必要です。いずれか一つでも欠けると、分かりにくいランタイムエラーが発生します。`azure-functions-doctor` は厳選されたルールセットに基づいてプロジェクトをチェックし、問題が本番環境に到達する前に報告します。

## Scope

このリポジトリは、デコレータベースの Azure Functions Python v2 プログラミングモデルのみを対象としています。

- サポートされているモデル: `@app.route()` などのデコレータを使用した `func.FunctionApp()`
- サポートされていないモデル: 従来の `function.json` ベースの Python v1 プロジェクト

## Installation

PyPI からインストール：

```bash
pip install azure-functions-doctor
```

ソースからインストール：

```bash
git clone https://github.com/yeongseon/azure-functions-doctor-python.git
cd azure-functions-doctor
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Quick Start

現在のプロジェクトで doctor を実行：

```bash
azure-functions-doctor doctor
```

特定のプロジェクトパスを指定して実行：

```bash
azure-functions-doctor doctor --path ./examples/v2/http-trigger
```

必須項目のみをチェックするプロファイルを使用：

```bash
azure-functions-doctor doctor --profile minimal
```

CI 用に JSON 形式で出力：

```bash
azure-functions-doctor doctor --format json
```

### コマンド名と非推奨のエイリアス

`azure-functions-doctor` が**正式（canonical）**コマンドです。既存の 2 つの
コンソールスクリプトエイリアスは引き続き動作しますが、**非推奨（deprecated）**であり、
実行時に警告を出力します：

| コマンド | 状態 |
| --- | --- |
| `azure-functions-doctor` | 正式 — これを使用してください。 |
| `azure-functions` | 非推奨 — **v1.0.0** で削除予定。 |
| `fdoctor` | 非推奨 — **v1.0.0** で削除予定。 |

v1.0.0 リリースでエイリアスが削除される前に、スクリプトや CI パイプラインを
`azure-functions-doctor` に移行してください。

シェルスクリプト、GitHub Actions、Makefile、pre-commit フックをカバーする
ステップバイステップの例は、[非推奨エイリアス移行ガイド](docs/deprecated-aliases.md)を参照してください。

## Demo

以下のデモは、VHS を使用して [`demo/doctor-demo.tape`](demo/doctor-demo.tape) から生成されました。
代表的なサンプルプロジェクトと、意図的にエラーを発生させたコピーに対して実際の `azure-functions-doctor doctor` CLI を実行し、成功と失敗の対比を示しています。

![Doctor demo](docs/assets/doctor-demo.gif)

最終的なターミナルの状態は、素早く確認できるように静止画像としてもキャプチャされています。

![Doctor final output](docs/assets/doctor-demo-final.png)

## Features

デフォルトのルールセットは以下を検証します：

- Azure Functions Python v2 デコレータの使用
- Python バージョン
- 仮想環境の有効化
- Python 実行ファイルの利用可能性
- `requirements.txt`
- `azure-functions` 依存関係の宣言
- `host.json`
- `local.settings.json`（オプション）
- Azure Functions Core Tools の存在とバージョン（オプション）
- Durable Functions ホスト設定（オプション）
- Application Insights 設定（オプション）
- `extensionBundle` 設定（オプション）
- ASGI/WSGI callable の公開（オプション）
- プロジェクトツリー内の一般的な不要ファイル（オプション）

## Examples

- [examples/v2/http-trigger/README.md](examples/v2/http-trigger/README.md)
- [examples/v2/multi-trigger/README.md](examples/v2/multi-trigger/README.md)

## Requirements

- Python 3.10+
- 開発ワークフローのための Hatch
- ローカル実行のために Azure Functions Core Tools v4+ を推奨

## Documentation

- [docs/index.md](docs/index.md)
- [docs/usage.md](docs/usage.md)
- [docs/rules.md](docs/rules.md)
- [docs/diagnostics.md](docs/diagnostics.md)
- [docs/development.md](docs/development.md)

## Ecosystem

このパッケージは **Azure Functions Python DX Toolkit** の一部です。

**設計原則:** `azure-functions-doctor` はデプロイ前診断を担当します。問題を直接修正したりコードを生成したりはせず — 開発者が修正できるよう、実行可能な発見事項を提示します。ランタイムの動作は [`azure-functions-openapi`](https://github.com/yeongseon/azure-functions-openapi-python)（API ドキュメントとスペック生成）、[`azure-functions-validation`](https://github.com/yeongseon/azure-functions-validation-python)（リクエスト/レスポンスのバリデーション）、[`azure-functions-langgraph`](https://github.com/yeongseon/azure-functions-langgraph-python)（LangGraph ランタイムの公開）に属します。

| パッケージ | 役割 |
|---------|------|
| [azure-functions-openapi-python](https://github.com/yeongseon/azure-functions-openapi-python) | OpenAPI スペック生成と Swagger UI |
| [azure-functions-validation-python](https://github.com/yeongseon/azure-functions-validation-python) | リクエスト/レスポンスのバリデーションとシリアライズ |
| [azure-functions-db-python](https://github.com/yeongseon/azure-functions-db-python) | SQLAlchemy ベースの DB 統合ヘルパー（ポーリングベースの擬似トリガー、入力/出力/クライアント注入） |
| [azure-functions-langgraph-python](https://github.com/yeongseon/azure-functions-langgraph-python) | Azure Functions 向け LangGraph デプロイアダプター |
| [azure-functions-scaffold-python](https://github.com/yeongseon/azure-functions-scaffold-python) | プロジェクトスキャフォールディング CLI |
| [azure-functions-logging-python](https://github.com/yeongseon/azure-functions-logging-python) | 構造化ロギングと可観測性 |
| **azure-functions-doctor-python** | デプロイ前診断 CLI |
| [azure-functions-durable-graph-python](https://github.com/yeongseon/azure-functions-durable-graph-python) | Durable Functions によるマニフェストファーストのグラフランタイム *(実験的)* |
| [azure-functions-knowledge-python](https://github.com/yeongseon/azure-functions-knowledge-python) | 知識検索（RAG）デコレーター |
| [azure-functions-cookbook-python](https://github.com/yeongseon/azure-functions-cookbook-python) | ドッグフード例 — ツールキット全体を活用する実行可能なレシピ |

## Disclaimer

このプロジェクトは独立したコミュニティプロジェクトであり、Microsoft と提携・承認・保守関係にはありません。

Azure および Azure Functions は Microsoft Corporation の商標です。

## License

MIT
