from __future__ import annotations

import os
from typing import Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .database import init_db
from .face_auth import enroll_face, profile_info, verify_face
from .knowledge import build_knowledge, clear_documents, delete_document, list_documents, save_upload
from .providers import cloud_ollama_models, test_provider
from .workflow import (
    generate_chapter,
    generate_quiz,
    list_chapters,
    list_quizzes,
    run_outline,
    submit_quiz,
    wrong_answers,
)


MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_BATCH_FILES = 10

Provider = Literal["local_ollama", "cloud_ollama", "openai_compatible", "mock"]


class ProviderConfig(BaseModel):
    provider: Provider = "mock"
    model: str = ""
    base_url: str = ""
    api_key: str = ""
    api_key_env: str = ""
    langsmith_enabled: bool = False


class SubmitPayload(BaseModel):
    answers: dict[str, str]


class FacePayload(BaseModel):
    username: str = "杨翰飞"
    descriptor: list[float]
    allow_replace: bool = False
    replace_token: str = ""


app = FastAPI(title="AI 学习助手", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "langsmith_ready": bool(os.getenv("LANGSMITH_API_KEY")),
        "ollama_key_ready": bool(os.getenv("OLLAMA_API_KEY")),
        "deepseek_key_ready": bool(os.getenv("DEEPSEEK_API_KEY")),
    }


@app.get("/api/documents")
def documents() -> dict:
    return {"documents": list_documents()}


@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)) -> dict:
    try:
        content = await _read_upload(file)
        path = save_upload(file.filename or "material.txt", content)
        document = build_knowledge(path)
        return {"document": document}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/documents/upload-batch")
async def upload_documents(files: list[UploadFile] = File(...)) -> dict:
    if len(files) > MAX_BATCH_FILES:
        raise HTTPException(status_code=400, detail=f"一次最多上传 {MAX_BATCH_FILES} 个文件。")
    documents = []
    errors = []
    for file in files:
        try:
            content = await _read_upload(file)
            path = save_upload(file.filename or "material.txt", content)
            documents.append(build_knowledge(path))
        except Exception as exc:
            errors.append({"filename": file.filename or "未命名文件", "message": str(exc)})
    if not documents and errors:
        raise HTTPException(status_code=400, detail="；".join(f"{item['filename']}：{item['message']}" for item in errors))
    return {"documents": documents, "errors": errors}


@app.delete("/api/documents/{document_id}")
def remove_document(document_id: int) -> dict:
    try:
        document = delete_document(document_id)
        return {"ok": True, "document": document, "message": "资料已删除，学习大纲与测验记录已同步清理。"}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/documents")
def remove_documents() -> dict:
    count = clear_documents()
    return {"ok": True, "count": count, "message": "资料库已清空，学习大纲与测验记录已同步清理。"}


async def _read_upload(file: UploadFile) -> bytes:
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        limit_mb = MAX_UPLOAD_BYTES // 1024 // 1024
        raise ValueError(f"单个文件不能超过 {limit_mb}MB，请压缩或拆分后再上传。")
    if not content:
        raise ValueError("上传文件为空，请选择有效资料。")
    return content


@app.post("/api/outline")
def outline(config: ProviderConfig) -> dict:
    _configure_langsmith(config)
    try:
        return run_outline(config.provider, config.model, config.base_url, config.api_key, config.api_key_env)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/chapters")
def chapters() -> dict:
    return {"chapters": list_chapters()}


@app.post("/api/chapters/{chapter_id}/content")
def chapter_content(chapter_id: int, config: ProviderConfig) -> dict:
    _configure_langsmith(config)
    try:
        return generate_chapter(chapter_id, config.provider, config.model, config.base_url, config.api_key, config.api_key_env)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/chapters/{chapter_id}/quiz")
def chapter_quiz(chapter_id: int, config: ProviderConfig) -> dict:
    _configure_langsmith(config)
    try:
        return generate_quiz(chapter_id, config.provider, config.model, config.base_url, config.api_key, config.api_key_env)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/provider/test")
def provider_test(config: ProviderConfig) -> dict:
    try:
        return test_provider(config.provider, config.model, config.base_url, config.api_key, config.api_key_env)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/provider/cloud-ollama/models")
def provider_cloud_ollama_models(config: ProviderConfig) -> dict:
    try:
        return {"models": cloud_ollama_models(config.base_url, config.api_key, config.api_key_env)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/chapters/{chapter_id}/quiz")
def get_quiz(chapter_id: int) -> dict:
    return {"quizzes": list_quizzes(chapter_id)}


@app.post("/api/chapters/{chapter_id}/submit")
def submit(chapter_id: int, payload: SubmitPayload) -> dict:
    try:
        return submit_quiz(chapter_id, payload.answers)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/wrong-answers")
def wrong_answer_list() -> dict:
    return {"wrong_answers": wrong_answers()}


@app.get("/api/face/profile")
def face_profile(username: str = "杨翰飞") -> dict:
    return profile_info(username)


@app.post("/api/face/enroll")
def face_enroll(payload: FacePayload) -> dict:
    try:
        return enroll_face(payload.username, payload.descriptor, payload.allow_replace, payload.replace_token)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/face-login")
def face_login(payload: FacePayload) -> dict:
    try:
        result = verify_face(payload.username, payload.descriptor)
        if not result["ok"]:
            raise HTTPException(status_code=401, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _configure_langsmith(config: ProviderConfig) -> None:
    if config.langsmith_enabled and os.getenv("LANGSMITH_API_KEY"):
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ.setdefault("LANGCHAIN_PROJECT", "AI学习助手大作业")
    else:
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
