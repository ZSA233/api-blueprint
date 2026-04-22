# 发布流程

## 范围

本仓库当前只维护 GitHub Release / Tag 发布面，不接入 PyPI。

稳定安装入口默认固定为：

- `git+https://github.com/zsa233/api-blueprint@stable`

## 进入发布流程前

只有在用户明确给出目标版本号之后，才进入正式发布准备。

进入发布前必须先确认：

1. 用户已经明确说明这次要发布的版本号。
2. 目标版本号与当前仓库状态不存在明显冲突。
3. 如果版本号看起来不合理，必须先向用户确认，而不是直接继续。

## 文档收束顺序

正式进入版本切换、preflight、tag 或 release 之前，必须先完成文档收束。

固定顺序：

1. 更新 `PRE_README.MD`
2. 收束 `README.md`
3. 收束 `README_EN.md`

`README.md` 与 `README_EN.md` 必须保持严格镜像：

- 标题层级一致
- 表格数量和顺序一致
- 代码块数量和顺序一致
- 提示项和限制说明一致

## 版本真源

发布关键版本信息只允许由以下文件驱动：

- `release-version.toml`
- `src/api_blueprint/_version.py`

不要手改散落版本号。

查看当前版本派生结果：

```sh
make release-version-show
```

切到 RC：

```sh
make release-version-rc BASE_VERSION=X.Y.Z RC=N CHECK=1
```

切到 stable：

```sh
make release-version-stable BASE_VERSION=X.Y.Z CHECK=1
```

## 分支与 tag 约定

- release 分支：`release/vX.Y.Z`
- stable tag：`vX.Y.Z`
- RC tag：`vX.Y.Z-rc.N`

默认推荐 direct stable。

只有当用户明确要求先走 RC 时，才执行 RC 流程。

## 本地发布检查

正式打 tag 之前，至少要依次执行：

```sh
make release-preflight RELEASE_TAG=vX.Y.Z[-rc.N]
make release-local RELEASE_TAG=vX.Y.Z[-rc.N]
make release-install-check RELEASE_TAG=vX.Y.Z[-rc.N]
```

这些命令分别负责：

- release contract 与版本同步校验
- 构建 sdist / wheel
- 检查 wheel 资源、安装 smoke 与 CLI `--help`

## 远端 CI 门槛

push tag 之前，必须确认当前 release ref 的 GitHub Actions `CI` 已经全绿。

如果 `CI` 仍有红项：

- 立即停止发布
- 先定位并修复问题
- 重新验证 `CI`
- 只有 CI 全绿后，才允许继续打 tag 或发 Release

## 正式发布

### RC

RC workflow 会：

1. 校验输入 tag
2. 运行 release bundle
3. 构建并上传产物
4. 创建 GitHub prerelease

RC 发布完成后，应停下来等待用户确认是否继续 stable。

### Stable

stable workflow 会：

1. 校验输入 tag
2. 运行 release bundle
3. 构建并上传产物
4. 创建 GitHub Release
5. 将远端 `stable` 分支同步到该 stable tag 对应提交

stable 分支同步是发布完成条件的一部分，不是可选收尾项。
