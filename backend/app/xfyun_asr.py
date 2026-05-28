from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from email.utils import format_datetime
from urllib.parse import urlencode

import websockets


class AsrError(RuntimeError):
    pass


IAT_HOST = "iat-api.xfyun.cn"
IAT_PATH = "/v2/iat"
IAT_URL = f"wss://{IAT_HOST}{IAT_PATH}"


def xfyun_ready() -> bool:
    return all(os.getenv(name) for name in ("XFYUN_APPID", "XFYUN_API_KEY", "XFYUN_API_SECRET"))


async def recognize_pcm_with_xfyun(audio: bytes) -> dict:
    if not audio:
        raise AsrError("没有收到语音数据，请重新录音。")
    app_id = os.getenv("XFYUN_APPID", "").strip()
    api_key = os.getenv("XFYUN_API_KEY", "").strip()
    api_secret = os.getenv("XFYUN_API_SECRET", "").strip()
    if not app_id or not api_key or not api_secret:
        raise AsrError("未配置讯飞语音听写凭证，请在后端环境变量中设置 XFYUN_APPID、XFYUN_API_KEY、XFYUN_API_SECRET。")

    url = _signed_url(api_key, api_secret)
    text_parts: list[str] = []
    try:
        async with websockets.connect(url, ping_interval=None, close_timeout=3) as websocket:
            chunks = list(_chunks(audio, 1280))
            for index, chunk in enumerate(chunks):
                status = 0 if index == 0 else 2 if index == len(chunks) - 1 else 1
                if len(chunks) == 1:
                    status = 0
                await websocket.send(json.dumps(_frame(app_id, chunk, status), ensure_ascii=False))
                await asyncio.sleep(0.04)
            if len(chunks) == 1:
                await websocket.send(json.dumps(_frame(app_id, b"", 2), ensure_ascii=False))
            while True:
                message = await asyncio.wait_for(websocket.recv(), timeout=8)
                payload = json.loads(message)
                code = payload.get("code", 0)
                if code != 0:
                    raise AsrError(payload.get("message") or f"讯飞识别失败，错误码 {code}。")
                text_parts.append(_extract_text(payload))
                if payload.get("data", {}).get("status") == 2:
                    break
    except AsrError:
        raise
    except asyncio.TimeoutError as exc:
        raise AsrError("讯飞识别超时，请检查网络后重试。") from exc
    except Exception as exc:
        raise AsrError(f"讯飞识别服务不可用：{exc}") from exc

    text = "".join(text_parts).strip()
    return {"text": text, "provider": "xfyun"}


def _signed_url(api_key: str, api_secret: str) -> str:
    date = format_datetime(datetime.now(timezone.utc), usegmt=True)
    signature_origin = f"host: {IAT_HOST}\ndate: {date}\nGET {IAT_PATH} HTTP/1.1"
    signature = base64.b64encode(
        hmac.new(api_secret.encode("utf-8"), signature_origin.encode("utf-8"), digestmod=hashlib.sha256).digest()
    ).decode("utf-8")
    authorization_origin = (
        f'api_key="{api_key}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature}"'
    )
    query = urlencode(
        {
            "authorization": base64.b64encode(authorization_origin.encode("utf-8")).decode("utf-8"),
            "date": date,
            "host": IAT_HOST,
        }
    )
    return f"{IAT_URL}?{query}"


def _frame(app_id: str, chunk: bytes, status: int) -> dict:
    frame = {
        "data": {
            "status": status,
            "format": "audio/L16;rate=16000",
            "encoding": "raw",
            "audio": base64.b64encode(chunk).decode("utf-8"),
        }
    }
    if status == 0:
        frame["common"] = {"app_id": app_id}
        frame["business"] = {
            "language": "zh_cn",
            "domain": "iat",
            "accent": "mandarin",
            "vad_eos": 3000,
        }
    return frame


def _extract_text(payload: dict) -> str:
    result = payload.get("data", {}).get("result", {})
    words = result.get("ws", [])
    return "".join(item.get("cw", [{}])[0].get("w", "") for item in words)


def _chunks(data: bytes, size: int):
    for start in range(0, len(data), size):
        yield data[start : start + size]
