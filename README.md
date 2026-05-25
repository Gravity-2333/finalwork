# AI 学习助手大作业

本项目是课程大作业“AI 学习助手”的完整实现，位于 `finalwork` 目录内独立管理。

## 功能概览

- 课程资料上传与本地知识库构建
- LangChain 文档加载与切割
- LangGraph 编排大纲、章节、测验、错题流程
- 可切换 AI Provider：本地 Ollama、云端 Ollama、DeepSeek、Mock
- 学习进度记录、在线测验、错题复盘
- 人脸核验演示与语音交互入口
- 自动截图与 Word 报告生成

## 快速运行

后端：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r backend\requirements.txt
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

前端：

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

打开 `http://127.0.0.1:5173`。

生成截图与报告：

```bash
npm install
cd frontend
npm install
cd ..
npm run screenshots
npm run report
```

## 环境变量

- `OLLAMA_API_KEY`：云端 Ollama / OpenAI-compatible Ollama 可选密钥。
- `DEEPSEEK_API_KEY`：DeepSeek API 密钥。
- `LANGSMITH_API_KEY`：LangSmith 可选追踪密钥，默认不启用。

没有密钥时可使用 `mock` Provider 完成演示。
