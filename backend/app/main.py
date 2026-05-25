from __future__ import annotations

import os
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .database import init_db
from .face_auth import enroll_face, has_profile, verify_face
from .knowledge import build_knowledge, list_documents, save_upload
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
        content = await file.read()
        path = save_upload(file.filename or "material.txt", content)
        document = build_knowledge(path)
        return {"document": document}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
    return {"username": username, "enrolled": has_profile(username)}


@app.post("/api/face/enroll")
def face_enroll(payload: FacePayload) -> dict:
    try:
        return enroll_face(payload.username, payload.descriptor)
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
