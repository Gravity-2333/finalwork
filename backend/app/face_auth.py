from __future__ import annotations

import json
import math

from .database import connect


DEFAULT_THRESHOLD = 0.86
SUPPORTED_DESCRIPTOR_LENGTHS = {128, 1024}


def has_profile(username: str) -> bool:
    with connect() as conn:
        row = conn.execute("SELECT username FROM face_profiles WHERE username=?", (username,)).fetchone()
    return row is not None


def enroll_face(username: str, descriptor: list[float]) -> dict:
    clean = _validate_descriptor(descriptor)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO face_profiles(username, descriptor, threshold, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(username) DO UPDATE SET
                descriptor=excluded.descriptor,
                threshold=excluded.threshold,
                updated_at=CURRENT_TIMESTAMP
            """,
            (username, json.dumps(clean), DEFAULT_THRESHOLD),
        )
    return {"ok": True, "username": username, "message": "授权人脸模板已录入。"}


def verify_face(username: str, descriptor: list[float]) -> dict:
    probe = _validate_descriptor(descriptor)
    with connect() as conn:
        row = conn.execute("SELECT descriptor, threshold FROM face_profiles WHERE username=?", (username,)).fetchone()
    if not row:
        raise ValueError("当前账号尚未录入授权人脸，请先完成人脸录入。")
    enrolled = json.loads(row["descriptor"])
    if len(enrolled) != len(probe):
        raise ValueError("人脸模板版本已更新，请重新录入账号本人脸部模板后再登录。")
    similarity = _cosine_similarity(enrolled, probe)
    threshold = float(row["threshold"])
    if similarity < threshold:
        return {
            "ok": False,
            "username": username,
            "similarity": round(similarity, 4),
            "threshold": threshold,
            "message": "人脸比对未通过，请使用已录入账号本人登录。",
        }
    return {
        "ok": True,
        "username": username,
        "similarity": round(similarity, 4),
        "threshold": threshold,
        "message": "人脸识别通过，已进入 AI 学习助手。",
    }


def _validate_descriptor(descriptor: list[float]) -> list[float]:
    if len(descriptor) not in SUPPORTED_DESCRIPTOR_LENGTHS:
        raise ValueError("人脸特征长度异常，请重新采集。")
    clean = [float(item) for item in descriptor]
    if not all(math.isfinite(item) for item in clean):
        raise ValueError("人脸特征包含无效值，请重新采集。")
    return clean


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)
