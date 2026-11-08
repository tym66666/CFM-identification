# Identification 网页演示

这是个人 Identification 仓库的实时网页入口，沿用团队演示的页面、九个示例、业务读取与后台复核流程。输出识别公式、采用条件、POINT/PARTIAL 或实际停止原因，以及独立证书重放结果。它不包含估计器、Policy、模拟器或 Notebook，也不需要它们的模型权重。

## 启动

下载完整仓库，在仓库根目录执行：

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[documents]"
.venv\Scripts\python demo/serve.py
```

Linux/macOS 将 `.venv\Scripts\python` 换成 `.venv/bin/python`。默认打开 `http://127.0.0.1:8772/`。也可以使用 `python demo/serve.py --port 8773 --no-browser`。不能直接双击 HTML 代替 Python 服务。

在页面“模型连接”中配置自己的 LongCat 或 DeepSeek Key；支持从本地 TXT 导入。密钥仅存在服务进程内存，关闭服务即清除，不写进源码或结果。启动网页、查看示例和历史结果不调用模型；点击开始读取才发起请求。默认每个服务进程最多 20 次模型请求，可用 `--max-api-calls 50` 显式调整。

## 使用与结果

上传用途、对象／关系模板及维护位置见[文件输入说明](../docs/FILE_INPUT_ZH.md)。

- 自由输入业务，或从右侧载入示例并修改。可以附 TXT、MD、JSON、PDF、DOCX、CSV、TSV、XLSX 资料。普通表格默认提取字段和行数；选择“字段说明表”会保留说明行。扫描 PDF 暂无 OCR，空文件、未读取内容或截断会在模型请求前提示处理。
- 对象名单与关系表分别上传，可下载 CSV 模板。完整名单保留孤立对象；须说明关系含义、时期与完整性，不会自动假定未列出的对象对没有关系。当前支持固定、简单、无向、无权的单位网络，不把它当作变量 DAG。
- “导入 CSV／Excel 数据”按用户选择的编号、处理、结果和数值特征列，在本地按名单对齐。须配套对象表与关系表；单时期、二元处理，每个对象保留一行，未回访结果可留空。模型仅收到字段解释、编号和实际结果覆盖信息，不收到逐条测量值，也不会把有限记录升级为总体信息。个人页不生成估计或 Policy 输出。
- “检查文件读取”不需 Key、不调用模型；开始分析时重新校验文件。已有普通材料和示例入口仍可使用，不要求所有问题都上传数值表。
- 后台读取目标、事实并复核来源；只有需要澄清原意或确认必要科学条件时才询问用户。审核边界与数学证书要求不变，模型复核不是科学真实性证明。
- 结果页展示公式与符号、适用条件和证书。没有代入总体数值的 POINT 不是已算出业务效果；有限模型 PARTIAL 的 sharp 性只相对于明确审核的模型成立。
- 九个示例保留原文和材料。N60 仍展示直接、同伴和局部总效应的识别；不再提供估计数据入口或估计数值。文献改编边界见 [示例说明](EXAMPLE_SOURCES_ZH.md)。
- “看验收记录”显示原团队网页此前的记录，明确标注为历史结果；修改业务后的新调用不沿用旧结果。程序不会从示例参考答案直接产生新任务的识别结果。

运行记录保存在仓库根目录 `outputs/web_runs/`，包含输入、模型原答及审核证据，应留在本机。服务仅监听本机，尚未作为多人公网服务部署；不要直接开放端口代替正式认证和访问控制。

## 目录和维护

| 位置 | 职责 |
|---|---|
| `serve.py` | 启动入口 |
| `index.html`、`app.js`、`style.css` | 页面、交互、公式与结果呈现 |
| `input-files.js`、`templates/` | 文件预览、列映射、对象／关系 CSV 模板 |
| `examples.json`、`condition_terms.json` | 合成示例、历史结果与统计术语 |
| `backend/` | HTTP、会话、模型请求、后台复核及 ID 调用 |
| `tests/` | 正负例、HTTP、隐私、审核边界和页面交互检查 |

`backend/` 调用本仓库的 `cfm_id.project`、读取合同与证书接口；不包含新数学求解器。自动读取／复核沿用原演示，经抽离后不再导入全流程 `autocfm`。测试夹具仅在 `tests/` 中使用，正式服务器不能导入参考答案。日常修改在维护源码的同名 `demo/` 中完成，验收后同步个人发布副本。

共同文件工具位于 `cfm_id_llm/`：`record_files.py` 负责有限记录的映射与覆盖元数据，`network_files.py`／`network_file_binding.py` 负责网络文件与引用，`file_coordinates.py` 负责确定性的编号展开，`upload_receipt.py` 负责读取回执。团队网页复用这些工具，再由自己的适配器生成估计数据；个人页不依赖团队估计模块。

两种网页共用文件合同不表示全部工作流或示例版本相同。当前个人页保留原九个示例；所有新增方法仍须单独检查目标、条件、来源和证书，不能由文件导入成功推定识别成立。

## 离线检查

```powershell
python -m pip install pytest jsonschema
python -m pytest demo/tests -q
node --test demo/tests/test_review_ui.cjs
```

这些检查不调用模型，不代表新的 LLM 准确率。识别库全量回归仍按根目录 README 运行。
