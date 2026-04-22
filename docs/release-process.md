# 发布流程

每个 release tag 当前会产出以下发布物：

- 1 个 Python 源码包 `sdist`
- 1 个 Python wheel

本仓库当前只维护 GitHub Release / Tag 发布面，不接入 PyPI。

稳定安装入口默认固定为：

- `git+https://github.com/zsa233/api-blueprint@stable`

## 分支约定

发布工作在冻结分支上完成，不要求必须从 `main` 直接发布。

推荐约定：

1. 日常开发继续在 `main` 或其他开发分支推进。
2. 准备某个具体版本发布时，从当前冻结代码线切出或继续使用 `release/vX.Y.Z`。
3. RC 与 stable 的版本切换、文档收束、校验、commit 与 tag 都在 `release/vX.Y.Z` 上完成。
4. 远端 `stable` 分支固定指向“最新 stable GitHub Release 对应代码”，不承载日常开发提交。
5. stable 发布完成后，必须确认远端 `stable` 已同步到对应 stable tag 的提交。
6. stable 发布完成后，把 `release/vX.Y.Z` 合并回 `main`。

## 发版请求前置条件

只有在用户明确给出目标发布版本号之后，才进入正式发版流程。

执行前应先确认：

1. 用户已经明确说明这次要发布的目标版本号。
2. 目标版本号与当前 release 分支、当前版本真源、当前已发布 stable 之间不存在明显冲突。
3. 如果用户给出的版本号不符合正常递增关系，应先确认版本号是否有误，而不是直接继续。

这里的“先确认”优先于后续所有版本切换、preflight、dry-run、RC 或 stable 步骤。

## 发版前文档收束

正式进入 release-version、preflight、RC 或 stable 之前，必须先基于 `PRE_README.MD` 收束对外文档。

固定顺序：

1. 更新 `PRE_README.MD`
2. 收束 `README.md`
3. 收束 `README_EN.md`
4. 对 `README.md` / `README_EN.md` 做一次双语镜像二次校对

双语镜像二次校对至少要检查：

- 章节顺序是否一致
- 标题数量与层级是否一致
- 表格数量和顺序是否一致
- 代码块数量、顺序和参数是否一致
- 提示项、限制说明、示例数量是否一致

如果中英 README 任一边存在漏段、漏表示例、漏限制说明，视为文档收束未完成，不允许进入 release-version / preflight / RC / stable。

## 版本切换与本地校验

版本切换统一通过 `scripts/release_version.py` 和 `Makefile` 完成，不手改版本文件。

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

这些命令当前只会同步：

- `release-version.toml`
- `src/api_blueprint/_version.py`

需要特别明确：

- `CHECK=1` 当前只会执行版本同步校验，不会自动代替完整的 `make release-preflight`。
- `make release-version-rc` / `make release-version-stable` 不会自动创建 git commit 或 tag。
- release commit 与 tag 必须由发布操作者按顺序显式执行，不要并行。
- 不要把 `git commit` 和 `git tag` 放进并行任务，否则 tag 很容易落到错误提交上。

完整的本地发布检查固定是三步：

```sh
make release-preflight RELEASE_TAG=vX.Y.Z[-rc.N]
make release-local RELEASE_TAG=vX.Y.Z[-rc.N]
make release-install-check RELEASE_TAG=vX.Y.Z[-rc.N]
```

它们分别负责：

- `release-preflight`：版本同步、release contract、README 镜像与测试校验
- `release-local`：构建 sdist / wheel
- `release-install-check`：验证 wheel 资源、安装 smoke 与 CLI `--help`

## 远端 CI 校验

在进入 release dry-run、push release tag 或继续 RC/stable 后续步骤之前，必须先确认当前 release ref 的 GitHub Actions `CI` 已经通过。

当前仓库的 `CI` workflow 具备两种入口：

- push 到 `main` 或 `release/*` 时自动触发
- 手动 `workflow_dispatch` 触发

推荐规则：

1. 先把当前 release 分支 push 到远端，例如 `release/vX.Y.Z`。
2. 优先复用这次 push 自动触发的 `CI` 结果。
3. 如果需要补跑，可以再手动触发一次 `CI` workflow。

发版继续之前，至少要确认这些作业全部通过：

- `release-contract`
- `python-tests (ubuntu-latest, 3.11)`
- `python-tests (macos-latest, 3.11)`
- `python-tests (windows-latest, 3.11)`

其中 `python-tests (windows-latest, 3.11)` 最容易暴露路径、shell 和平台差异回归；如果它失败，不要继续发版。

CI 未通过时的固定处理原则：

- 立即停止当前 release 流程
- 优先定位并修复 CI 红项
- 修复后重新 push release 分支，或重新触发 `CI`
- 只有 CI 全绿后，才允许继续 dry-run、打 tag 或 publish

推荐在每次准备 push tag 之前做一次显式确认：

```sh
git rev-parse HEAD
git rev-parse vX.Y.Z[-rc.N]
```

这两个值必须完全一致；如果不一致，说明 tag 没有打在当前 release commit 上，应先修正 tag，再继续后续发布流程。

## GitHub Release Dry-Run

`release.yml` 与 `release-rc.yml` 都支持 `workflow_dispatch` dry-run。

对于 `workflow_dispatch`：

- 只会执行 `build` job
- 会上传 `release-bundle-<tag>` artifact
- 不会创建 GitHub Release / prerelease
- 不会推进 `stable` 分支
- 不会触发 `production` environment 审批

推荐在公开 push tag 前，先做一次远端 dry-run。

示例：

```sh
gh workflow run release.yml --repo ZSA233/api-blueprint --ref release/vX.Y.Z -f tag=vX.Y.Z
gh workflow run release-rc.yml --repo ZSA233/api-blueprint --ref release/vX.Y.Z -f tag=vX.Y.Z-rc.N
```

## Production 环境审批

stable `Release` workflow 的正式发布 job 绑定到 GitHub `production` environment。

如果仓库给 `production` 配置了 `required reviewers`，stable tag 推上去后，workflow 会在正式发布前停下来等待人工审核。

是否真正形成审批停顿，取决于仓库 `production` environment 的一次性配置；这属于仓库初始化事实，不纳入每次发版的重复检查清单。

stable 正式发布的远端顺序固定为：

1. push stable tag
2. `Release` workflow 启动正式发布；如果仓库已配置 reviewer，会在 `production` environment 停下来等待审批
3. 如果进入审批，先在 GitHub 上完成 `production` environment 审核
4. workflow 创建 GitHub Release
5. workflow 同步远端 `stable` 分支

## RC 流程

RC 用于公开验证。RC 只创建 GitHub prerelease，不推进 `stable` 分支，也不进入 `production` environment 审批。

只有在用户明确要求“先 RC，再 stable”时，才进入这条流程。

步骤如下：

1. 在发布分支上切到目标 RC：

```sh
make release-version-rc BASE_VERSION=X.Y.Z RC=N CHECK=1
make release-preflight RELEASE_TAG=vX.Y.Z-rc.N
make release-local RELEASE_TAG=vX.Y.Z-rc.N
make release-install-check RELEASE_TAG=vX.Y.Z-rc.N
```

2. 把 RC 版本切换结果提交到发布分支：

```sh
git add PRE_README.MD README.md README_EN.md \
  docs/release-process.md AGENTS.MD \
  release-version.toml src/api_blueprint/_version.py
git commit -m "release: cut vX.Y.Z-rc.N"
git tag vX.Y.Z-rc.N
test "$(git rev-parse HEAD)" = "$(git rev-parse vX.Y.Z-rc.N)"
```

3. push `release/vX.Y.Z`，确认远端 `CI` 全绿。
4. 如需在不提前公开 RC tag 的前提下做远端 dry-run，先用 `workflow_dispatch` 触发 `release-rc.yml`。
5. 如果 dry-run 正常，再 push RC tag：

```sh
git push origin release/vX.Y.Z
git push origin vX.Y.Z-rc.N
```

6. 确认 GitHub Actions `Release RC` workflow 通过，并检查 GitHub prerelease 是否可见。
7. RC 发布完成后，停下来等待用户确认是否继续 stable。

## Stable 流程

默认推荐 direct stable。

步骤如下：

1. 在发布分支上切到目标 stable：

```sh
make release-version-stable BASE_VERSION=X.Y.Z CHECK=1
make release-preflight RELEASE_TAG=vX.Y.Z
make release-local RELEASE_TAG=vX.Y.Z
make release-install-check RELEASE_TAG=vX.Y.Z
```

2. 把 stable 版本切换结果提交到发布分支：

```sh
git add PRE_README.MD README.md README_EN.md \
  docs/release-process.md AGENTS.MD \
  release-version.toml src/api_blueprint/_version.py \
  .github/workflows/ci.yml .github/workflows/release.yml \
  .github/workflows/release-rc.yml .github/actions/release-bundle/action.yml
git commit -m "release: prepare vX.Y.Z"
git tag vX.Y.Z
test "$(git rev-parse HEAD)" = "$(git rev-parse vX.Y.Z)"
```

3. 先 push `release/vX.Y.Z`，确认远端 `CI` 全绿。
4. 如需额外稳妥，先用 `workflow_dispatch` 触发 `release.yml` 做远端 dry-run。
5. 确认 dry-run 正常后，再 push stable tag：

```sh
git push origin release/vX.Y.Z
git push origin vX.Y.Z
```

6. 如果仓库已配置 reviewer，确认 GitHub Actions `Release` workflow 停在 `production` environment 审批，并等待人工批准。
7. 审批完成后，确认 workflow 继续执行正式发布。
8. 确认 workflow 后续通过，并检查：
   - GitHub Release 已创建
   - 远端 `stable` 已同步到 `vX.Y.Z`
9. stable 发布完成后，把 `release/vX.Y.Z` 合并回 `main`。

stable 分支同步和 `main` 回灌都属于发布完成条件的一部分，不是可选收尾项。
