from __future__ import annotations

import json
import re
from pathlib import Path

from docx import Document as DocxDocument
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .database import UPLOAD_DIR, connect


ALLOWED_SUFFIXES = {".txt", ".md", ".docx", ".pdf"}


def save_upload(file_name: str, content: bytes) -> Path:
    suffix = Path(file_name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError("仅支持 txt、md、docx、pdf 格式资料。")
    safe_name = re.sub(r"[^\w.\-\u4e00-\u9fff]+", "_", Path(file_name).name)
    target = UPLOAD_DIR / safe_name
    if target.exists():
        if target.read_bytes() == content:
            return target
        target = _next_available_path(target)
    target.write_bytes(content)
    return target


def build_knowledge(file_path: Path) -> dict:
    existing = _existing_document(file_path.name)
    if existing:
        return existing
    docs = _load_documents(file_path)
    splitter = RecursiveCharacterTextSplitter(chunk_size=650, chunk_overlap=90)
    chunks = splitter.split_documents(docs)
    summary = _summarize_chunks(chunks)
    with connect() as conn:
        cursor = conn.execute(
            "INSERT INTO documents(filename, file_path, chunk_count, summary) VALUES (?, ?, ?, ?)",
            (file_path.name, str(file_path), len(chunks), summary),
        )
        document_id = cursor.lastrowid
        conn.executemany(
            "INSERT INTO chunks(document_id, content, metadata) VALUES (?, ?, ?)",
            [
                (
                    document_id,
                    chunk.page_content,
                    json.dumps(chunk.metadata, ensure_ascii=False),
                )
                for chunk in chunks
            ],
        )
    return {
        "id": document_id,
        "filename": file_path.name,
        "chunk_count": len(chunks),
        "summary": summary,
    }


def list_documents() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM documents ORDER BY id DESC").fetchall()
    return [dict(row) for row in rows]


def delete_document(document_id: int) -> dict:
    with connect() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
        if not row:
            raise ValueError("资料不存在或已被删除。")
        document = dict(row)
        conn.execute("DELETE FROM chunks WHERE document_id=?", (document_id,))
        conn.execute("DELETE FROM documents WHERE id=?", (document_id,))
        _clear_learning_state(conn)
    _unlink_if_unused(document["file_path"], document["filename"])
    return document


def clear_documents() -> int:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM documents").fetchall()
        documents = [dict(row) for row in rows]
        conn.execute("DELETE FROM chunks")
        conn.execute("DELETE FROM documents")
        _clear_learning_state(conn)
    for document in documents:
        _unlink_if_unused(document["file_path"], document["filename"], assume_database_cleared=True)
    return len(documents)


def has_documents() -> bool:
    with connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM chunks").fetchone()
    return bool(row and row["count"])


def search_chunks(query: str, limit: int = 8) -> list[dict]:
    terms = [item for item in re.split(r"\W+", query.lower()) if item]
    with connect() as conn:
        rows = conn.execute("SELECT id, document_id, content, metadata FROM chunks").fetchall()
    ranked = []
    for row in rows:
        content = row["content"]
        lowered = content.lower()
        score = sum(lowered.count(term) for term in terms) if terms else 0
        score += min(len(content), 650) / 10000
        ranked.append((score, dict(row)))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [item for score, item in ranked[:limit] if score > 0]


def all_context(limit: int = 12) -> str:
    with connect() as conn:
        rows = conn.execute("SELECT content FROM chunks ORDER BY id LIMIT ?", (limit,)).fetchall()
    return "\n\n".join(row["content"] for row in rows)


def _existing_document(filename: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM documents WHERE filename=? ORDER BY id DESC LIMIT 1", (filename,)).fetchone()
    return dict(row) if row else None


def _next_available_path(target: Path) -> Path:
    for index in range(1, 1000):
        candidate = target.with_name(f"{target.stem}_{index}{target.suffix}")
        if not candidate.exists():
            return candidate
    raise ValueError("同名资料过多，请重命名文件后再上传。")


def _load_documents(file_path: Path) -> list[Document]:
    suffix = file_path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return _clean_documents(TextLoader(str(file_path), encoding="utf-8").load())
    if suffix == ".pdf":
        return _clean_documents(PyPDFLoader(str(file_path)).load())
    if suffix == ".docx":
        doc = DocxDocument(file_path)
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        return _clean_documents([Document(page_content=text, metadata={"source": str(file_path)})])
    raise ValueError("不支持的资料格式。")


def _clean_documents(documents: list[Document]) -> list[Document]:
    cleaned = []
    for doc in documents:
        text = doc.page_content.encode("utf-8", "ignore").decode("utf-8")
        cleaned.append(Document(page_content=text, metadata=doc.metadata))
    return cleaned


def _summarize_chunks(chunks: list[Document]) -> str:
    text = "\n".join(chunk.page_content for chunk in chunks[:3])
    text = re.sub(r"\s+", " ", text).strip()
    return text[:220] or "资料已加载，等待生成课程大纲。"


def _clear_learning_state(conn) -> None:
    conn.execute("DELETE FROM wrong_answers")
    conn.execute("DELETE FROM quizzes")
    conn.execute("DELETE FROM chapters")


def _unlink_if_unused(file_path: str, filename: str, assume_database_cleared: bool = False) -> None:
    target = Path(file_path)
    if not target.exists() or target.parent != UPLOAD_DIR:
        return
    if not assume_database_cleared and _existing_document(filename):
        return
    target.unlink(missing_ok=True)
