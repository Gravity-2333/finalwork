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


# 检查讯飞语音听写凭证是否齐全。
# 功能：供健康检查和前端状态提示使用，不暴露具体密钥内容。
def xfyun_ready() -> bool:
    return all(os.getenv(name) for name in ("XFYUN_APPID", "XFYUN_API_KEY", "XFYUN_API_SECRET"))


# 调用讯飞语音听写 WebAPI 识别 PCM 音频。
# 功能：接收前端 16k PCM 数据，生成鉴权 WebSocket URL，分片发送音频并拼接返回文字。
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
        async with websockets.connect(url, close_timeout=5) as websocket:
            chunks = list(_chunks(audio, 1280))
            for index, chunk in enumerate(chunks):
                if index == 0:
                    status = 0
                elif index == len(chunks) - 1:
                    status = 2
                else:
                    status = 1
                await websocket.send(json.dumps(_frame(app_id, chunk, status), ensure_ascii=False))
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


# 生成讯飞 WebSocket 鉴权 URL。
# 功能：按讯飞规范用 APISecret 对 host/date/request-line 做 HMAC-SHA256 签名。
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


# 构造讯飞音频帧。
# 功能：首帧携带 common/business 参数，中间帧和尾帧只发送音频状态与 PCM 数据。
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
