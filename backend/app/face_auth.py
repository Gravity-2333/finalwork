from __future__ import annotations

import json
import math
import secrets

from .database import connect


DEFAULT_COSINE_THRESHOLD = 0.86
DEFAULT_FACEAPI_DISTANCE_THRESHOLD = 0.38
DEFAULT_HASH_DISTANCE_THRESHOLD = 0.34
FACE_DESCRIPTOR_LENGTH = 128
HASH_DESCRIPTOR_LENGTH = 256
COMPOSITE_DESCRIPTOR_LENGTH = FACE_DESCRIPTOR_LENGTH + HASH_DESCRIPTOR_LENGTH
SUPPORTED_DESCRIPTOR_LENGTHS = {FACE_DESCRIPTOR_LENGTH, COMPOSITE_DESCRIPTOR_LENGTH, 1024}
FACE_SESSIONS: dict[str, str] = {}


def profile_info(username: str) -> dict:
    with connect() as conn:
        row = conn.execute("SELECT descriptor, updated_at FROM face_profiles WHERE username=?", (username,)).fetchone()
    if not row:
        return {"username": username, "enrolled": False, "descriptor_length": 0, "needs_upgrade": False}
    descriptor = json.loads(row["descriptor"])
    return {
        "username": username,
        "enrolled": True,
        "descriptor_length": len(descriptor),
        "needs_upgrade": len(descriptor) != COMPOSITE_DESCRIPTOR_LENGTH,
        "updated_at": row["updated_at"],
    }


def enroll_face(username: str, descriptor: list[float], allow_replace: bool = False, replace_token: str = "") -> dict:
    clean = _validate_descriptor(descriptor)
    with connect() as conn:
        existing = conn.execute("SELECT descriptor FROM face_profiles WHERE username=?", (username,)).fetchone()
        existing_length = len(json.loads(existing["descriptor"])) if existing else 0
        upgrading_template = existing_length and existing_length != COMPOSITE_DESCRIPTOR_LENGTH and len(clean) == COMPOSITE_DESCRIPTOR_LENGTH
        if existing and not upgrading_template and existing_length in {FACE_DESCRIPTOR_LENGTH, COMPOSITE_DESCRIPTOR_LENGTH} and not _can_replace(username, allow_replace, replace_token):
            raise ValueError("该账号已录入授权人脸，未登录状态下不能覆盖人脸模板。")
        conn.execute(
            """
            INSERT INTO face_profiles(username, descriptor, threshold, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(username) DO UPDATE SET
                descriptor=excluded.descriptor,
                threshold=excluded.threshold,
                updated_at=CURRENT_TIMESTAMP
            """,
            (username, json.dumps(clean), _default_threshold(clean)),
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
    threshold = _effective_threshold(probe, float(row["threshold"]))
    if len(probe) in {FACE_DESCRIPTOR_LENGTH, COMPOSITE_DESCRIPTOR_LENGTH}:
        face_distance = _euclidean_distance(_face_part(enrolled), _face_part(probe))
        hash_distance = _hash_distance(enrolled, probe) if len(probe) == COMPOSITE_DESCRIPTOR_LENGTH else None
        if face_distance > threshold or (hash_distance is not None and hash_distance > DEFAULT_HASH_DISTANCE_THRESHOLD):
            return {
                "ok": False,
                "username": username,
                "distance": round(face_distance, 4),
                "threshold": threshold,
                "hash_distance": round(hash_distance, 4) if hash_distance is not None else None,
                "hash_threshold": DEFAULT_HASH_DISTANCE_THRESHOLD if hash_distance is not None else None,
                "metric": "face_distance+hash_distance" if hash_distance is not None else "euclidean_distance",
                "message": _failure_message(face_distance, threshold, hash_distance),
            }
        return {
            "ok": True,
            "username": username,
            "distance": round(face_distance, 4),
            "threshold": threshold,
            "hash_distance": round(hash_distance, 4) if hash_distance is not None else None,
            "hash_threshold": DEFAULT_HASH_DISTANCE_THRESHOLD if hash_distance is not None else None,
            "metric": "face_distance+hash_distance" if hash_distance is not None else "euclidean_distance",
            "replace_token": _create_face_session(username),
            "message": "人脸识别通过，已进入 AI 学习助手。",
        }
    similarity = _cosine_similarity(enrolled, probe)
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
        "replace_token": _create_face_session(username),
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


def _euclidean_distance(left: list[float], right: list[float]) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right)))


def _default_threshold(descriptor: list[float]) -> float:
    if len(descriptor) in {FACE_DESCRIPTOR_LENGTH, COMPOSITE_DESCRIPTOR_LENGTH}:
        return DEFAULT_FACEAPI_DISTANCE_THRESHOLD
    return DEFAULT_COSINE_THRESHOLD


def _effective_threshold(descriptor: list[float], stored_threshold: float) -> float:
    if len(descriptor) in {FACE_DESCRIPTOR_LENGTH, COMPOSITE_DESCRIPTOR_LENGTH}:
        return DEFAULT_FACEAPI_DISTANCE_THRESHOLD
    return stored_threshold


def _face_part(descriptor: list[float]) -> list[float]:
    return descriptor[:FACE_DESCRIPTOR_LENGTH]


def _hash_distance(left: list[float], right: list[float]) -> float | None:
    if len(left) != COMPOSITE_DESCRIPTOR_LENGTH or len(right) != COMPOSITE_DESCRIPTOR_LENGTH:
        return None
    left_hash = left[FACE_DESCRIPTOR_LENGTH:]
    right_hash = right[FACE_DESCRIPTOR_LENGTH:]
    return sum(1 for left_bit, right_bit in zip(left_hash, right_hash) if round(left_bit) != round(right_bit)) / HASH_DESCRIPTOR_LENGTH


def _failure_message(face_distance: float, face_threshold: float, hash_distance: float | None) -> str:
    message = f"人脸比对未通过，模型距离 {round(face_distance, 4)} / 阈值 {face_threshold}"
    if hash_distance is not None:
        message += f"，灰度模板差异 {round(hash_distance, 4)} / 阈值 {DEFAULT_HASH_DISTANCE_THRESHOLD}"
    return message + "。"


def _create_face_session(username: str) -> str:
    token = secrets.token_urlsafe(24)
    FACE_SESSIONS[token] = username
    return token


def _can_replace(username: str, allow_replace: bool, replace_token: str) -> bool:
    return allow_replace and bool(replace_token) and FACE_SESSIONS.get(replace_token) == username
