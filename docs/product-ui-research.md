# ProvSci 产品工作台界面调研

## 参考项目

- [Open Paper](https://github.com/khoj-ai/openpaper)：上传论文后进入阅读工作区，文档和助手并排，回答带可点击引用。
- [DocsGPT](https://github.com/arc53/DocsGPT)：以文档上传、处理状态、工作区和结果问答为主要入口，强调私有部署。
- [AnythingLLM](https://github.com/Mintplex-Labs/anything-llm)：用工作区组织文件和任务，上传后显示文档状态，再进入问答或代理操作。
- [RAGFlow](https://github.com/infiniflow/ragflow)：把解析阶段、分段/表格结构和失败状态显式放到界面里，方便排查文档处理问题。

## 共同的界面规律

1. **文件先进入工作区。** 用户先拖入文件或选择文件，再配置任务；不把复杂参数放在第一屏。
2. **处理过程可见。** 上传、解析、索引或抽取用阶段条展示，失败时给出明确状态。
3. **结果和原文保持相邻。** 结果列表负责扫描，右侧或旁边的详情区负责查看原文、引用和上下文。
4. **工作区持续保存运行记录。** 最近运行、文件名、时间和结果数量让用户能返回之前的任务。

## ProvSci 的取舍

ProvSci 没有照搬“聊天窗口优先”的布局，因为产品的主要交付物是结构化科研数据。当前工作台因此采用：

```text
左侧：分析工作台 / 运行记录 / 数据字典 / 质量规则
中间：拖拽上传 → 分析配置 → 结构化数据表
右侧：ResultCard → Evidence locator → Acquisition path → verifier
```

和通用文档问答产品相比，ProvSci 额外固定了四个字段：

- 结果值、单位和实验条件；
- 原文表格/段落的精确 locator；
- 从证据到答案的 acquisition path；
- Gold、人工复核和 verifier 状态。

## 当前原型边界

`web/product_workspace.html` 是一个无构建依赖的前端原型：

- 可以载入真实演示论文数据；
- 支持拖拽或选择本地 JSON、CSV、TXT 等文件；
- 浏览器端提供基础字段预览和均值±误差识别；
- 用阶段进度展示完整 pipeline 的产品形态；
- 支持筛选、搜索、查看单条证据链和导出 CSV。

完整的 JATS/PDF 解析、白名单路径执行和 verifier 仍由现有 Python pipeline 提供。当前已经补了一个本地产品服务，可以让上传文件真正进入 pipeline：

```bash
PYTHONPATH=src python3 scripts/run_product_app.py 127.0.0.1 4173
```

浏览器打开 `http://127.0.0.1:4173/product_workspace.html`，前端的“开始分析”会向 `POST /api/analyze` 上传文件，服务返回摘要和适合表格展示的结构化结果。任务目录使用临时文件，结果只保存在本机运行期间；生产版还需要异步任务队列、持久化数据库、权限控制和更完整的进度事件。
