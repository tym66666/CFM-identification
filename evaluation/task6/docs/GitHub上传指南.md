# 任务6 GitHub上传指南

当前仓库目录：`C:\Users\16209\Documents\GitHub\CFM-identification`。当前本地分支是`task6-llm-evaluation`，remote `fork`指向`yuehan19777/CFM-identification`，`origin`指向`zzyyLOGIC/CFM-identification`。执行前用下面命令复核，若输出不同先停下检查。

## 1. 需要提交哪些文件

只提交整个 `evaluation/task6/`：

- `__init__.py`、`README_ZH.md`：包入口和当前状态；
- `materials/`：24份测试输入；`references/`：24份待审参考草稿；
- `scripts/`：评测、评分、事实台账、N01链路、离线收尾和快照恢复脚本；
- `tests/`：离线测试；
- `docs/`：评分口径、审查待办、参考审读空表、PR说明和本指南；
- `results/20261105/`：已有脱敏统计、失败清单、配置与Skill快照、证据哈希及历史报告。

下面这些**不提交**：整个`outputs/`（含私有请求、模型输出、AI预审、恢复候选、N01审核数据）；根目录的`task6_holdout_32_results.zip`、`fix_n01_fact_candidate.py`、`task6_n01_fullchain.py`；任何API密钥、`.env`或含密钥的日志。必要的N01链路脚本已放在`evaluation/task6/scripts/n01_fullchain.py`。单题候选可以在受控环境供审读，公开前需确认脱敏。

## 2. 检查、暂存、提交

在PowerShell逐行运行：

```powershell
cd C:\Users\16209\Documents\GitHub\CFM-identification
git status --short --branch
git remote -v
python -m unittest discover -s evaluation/task6/tests -v
git add --dry-run -- evaluation/task6/
git add -- evaluation/task6/
git diff --cached --stat
git diff --cached --name-only
git diff --cached --check
```

确认暂存列表只包含上述`evaluation/task6/`文件，并检查暂存内容里没有密钥或私有回答。若出现其他已暂存文件，**不要运行下一条提交命令**；先通过Git界面或`git restore --staged -- <具体文件>`移除那些暂存项，保留工作区文件。确认无误后：

```powershell
git commit -m "Add Task 6 reading evaluation and audit"
git push -u fork task6-llm-evaluation
```

若提示身份未设置，用你自己的GitHub身份配置`git config user.name`和`git config user.email`；若身份验证失败，用GitHub Desktop或Git Credential Manager登录。若网络不可达，恢复网络后重试push；不要把密钥写进命令行、README或远程地址。

## 3. 创建PR

打开 https://github.com/yuehan19777/CFM-identification 的`task6-llm-evaluation`分支，点击“Contribute / Open pull request”，选择目标仓库`zzyyLOGIC/CFM-identification`的`main`为base，选择你的fork的`task6-llm-evaluation`为compare。复制`docs/PR说明.md`中的标题和内容；建议以Draft PR提交，因为独立审读和全链路验收仍未完成。核对Files changed只有任务6目录后再创建。

## 4. 当前边界

如果原项目主分支已更新，先在GitHub比较差异并与维护者确认合并方式；本地上次网络检查无法连接GitHub，未核实远端实时状态。本指南仅说明操作，本次没有代你commit、push或创建PR。
