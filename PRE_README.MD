# API Blueprint README Fact Base

## 项目定位

`api-blueprint` 是一个面向 API 契约定义与多语言代码生成的 Python 项目。

主线能力是：

1. 用 Python DSL 定义 `Blueprint`、路由、请求模型、响应模型与错误结构。
2. 在运行时构建 FastAPI/OpenAPI 文档服务。
3. 基于同一份蓝图输出 Go 与 TypeScript 的代码快照。

## 仓库事实

- 包名：`api-blueprint`
- 当前对外 CLI：
  - `api-doc-server`
  - `api-gen-golang`
  - `api-gen-typescript`
- GitHub-only 稳定安装入口固定为：
  - `git+https://github.com/zsa233/api-blueprint@stable`
- 版本真源：
  - `release-version.toml`
  - `src/api_blueprint/_version.py`

## 结构事实

- `src/api_blueprint/engine/`：DSL、模型、Blueprint、路由与 FastAPI/OpenAPI 语义。
- `src/api_blueprint/writer/`：Go / TypeScript 代码生成。
- `src/api_blueprint/hub/` 与 `src/api_blueprint/static/`：文档服务 UI 资源。
- `examples/blueprints/`：示例蓝图真源。
- `examples/golang/` 与 `examples/typescript/`：生成产物快照。

## 运行时事实

- `Blueprint(app=None)` 默认共享一个全局 `FastAPI` app。
- 如果多个 `Blueprint` 没有显式传入 `app`，它们会被注册到同一个文档应用里。
- `api-doc-server` 默认通过配置文件加载 entrypoints 并启动文档服务。

## 文档与生成约束

- `PRE_README.MD` 是 README 收束基线。
- `README.md` 与 `README_EN.md` 需要严格镜像。
- 只要用户可见能力、CLI、配置、生成结果目录、安装方式或发布方式发生变化，就必须先更新本文件。
- `main.py` 与 `debug.py` 属于本地辅助脚本，不是公共发布接口。

## 推荐 README 结构

1. 项目概述
2. 支持的输出
3. 安装
4. 核心工作流
5. 配置文件
6. 蓝图 DSL 示例
7. CLI 命令
8. 生成产物与仓库约束
9. 开发
10. 发布

## 推荐发布口径

- 默认发布路线是 direct stable。
- 只有在用户明确要求时才走 RC。
- 发版前文档收束顺序固定为：
  - `PRE_README.MD`
  - `README.md`
  - `README_EN.md`
- 发布前检查主线命令：
  - `make release-version-show`
  - `make release-preflight RELEASE_TAG=vX.Y.Z[-rc.N]`
  - `make release-local RELEASE_TAG=vX.Y.Z[-rc.N]`
  - `make release-install-check RELEASE_TAG=vX.Y.Z[-rc.N]`

## README 必须覆盖的事实

- 项目是“Python DSL -> FastAPI/OpenAPI -> Go/TypeScript 代码生成器”。
- `examples/blueprints/` 是真源，`examples/golang/` / `examples/typescript/` 是生成快照。
- 共享全局 app 是默认行为。
- GitHub-only 稳定安装入口是 `@stable`，不是固定 tag。
- 发布流程和详细规范在 `docs/release-process.md`。
