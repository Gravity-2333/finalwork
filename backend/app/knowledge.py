from __future__ import annotations

import json
import re
import shutil
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
    counter = 1
    while target.exists():
        target = UPLOAD_DIR / f"{target.stem}_{counter}{suffix}"
        counter += 1
    target.write_bytes(content)
    return target


def build_knowledge(file_path: Path) -> dict:
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


def seed_sample_material() -> dict:
    sample = Path(__file__).resolve().parents[2] / "docs" / "sample_course.txt"
    if not sample.exists():
        sample.write_text(
            "人工智能课程学习资料\n"
            "第一章 人工智能概述：介绍人工智能的发展、典型应用与学习路径。\n"
            "第二章 机器学习基础：包括监督学习、无监督学习、训练集、测试集与评估指标。\n"
            "第三章 大语言模型应用：介绍提示词、知识库检索、智能体编排与安全使用。\n"
            "第四章 学习复盘方法：通过章节测验、错题归档和阶段总结提升学习效果。\n",
            encoding="utf-8",
        )
    target = UPLOAD_DIR / sample.name
    if not target.exists():
        shutil.copyfile(sample, target)
    return build_knowledge(target)


def _load_documents(file_path: Path) -> list[Document]:
    suffix = file_path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return TextLoader(str(file_path), encoding="utf-8").load()
    if suffix == ".pdf":
        return PyPDFLoader(str(file_path)).load()
    if suffix == ".docx":
        doc = DocxDocument(file_path)
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        return [Document(page_content=text, metadata={"source": str(file_path)})]
    raise ValueError("不支持的资料格式。")


def _summarize_chunks(chunks: list[Document]) -> str:
    text = "\n".join(chunk.page_content for chunk in chunks[:3])
    text = re.sub(r"\s+", " ", text).strip()
    return text[:220] or "资料已加载，等待生成课程大纲。"

