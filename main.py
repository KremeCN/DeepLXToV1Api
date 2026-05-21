import os
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import aiohttp
import asyncio
import logging
from typing import List
import datetime
import json
import uuid
import time 
import re

logging.basicConfig(level=logging.INFO)

from starlette.middleware.base import BaseHTTPMiddleware

class LogRequestsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 读取请求体内容
        body = await request.body()
        
        # 记录请求路径和请求体
        logging.debug(f"Request path: {request.url.path}")
        logging.debug(f"Request body: {body}")
        
        # 继续处理请求
        response = await call_next(request)
        return response

app = FastAPI()

# 添加中间件到应用
app.add_middleware(LogRequestsMiddleware)

class ChatRequest(BaseModel):
    messages: List[dict]
    stream: bool = False
    model: str


def extract_text_content(content):
    if isinstance(content, list):
        if not content:
            return ""
        first = content[0]
        if isinstance(first, dict):
            return first.get("text", "")
        return first
    return content or ""


LANG_ALIASES = {
    # English
    "en": "EN",
    "en-us": "EN",
    "en_us": "EN",
    "en-gb": "EN",
    "en_gb": "EN",
    "english": "EN",
    # Chinese simplified
    "zh": "ZH",
    "zh-cn": "ZH",
    "zh_cn": "ZH",
    "zh-hans": "ZH",
    "zh_hans": "ZH",
    "simplified chinese": "ZH",
    "mandarin chinese": "ZH",
    "simplified mandarin chinese": "ZH",
    # Chinese traditional
    "zh-tw": "ZH-HANT",
    "zh_tw": "ZH-HANT",
    "zh-hant": "ZH-HANT",
    "zh_hant": "ZH-HANT",
    "traditional chinese": "ZH-HANT",
    "traditional mandarin chinese": "ZH-HANT",
    # Japanese
    "ja": "JA",
    "ja-jp": "JA",
    "ja_jp": "JA",
    "japanese": "JA",
    # Korean
    "ko": "KO",
    "ko-kr": "KO",
    "ko_kr": "KO",
    "korean": "KO",
    # French
    "fr": "FR",
    "fr-fr": "FR",
    "fr_fr": "FR",
    "french": "FR",
    # German
    "de": "DE",
    "de-de": "DE",
    "de_de": "DE",
    "german": "DE",
    # Spanish
    "es": "ES",
    "es-es": "ES",
    "es_es": "ES",
    "spanish": "ES",
    # Russian
    "ru": "RU",
    "ru-ru": "RU",
    "ru_ru": "RU",
    "russian": "RU",
}


def normalize_lang(value: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    raw = value.strip()
    if raw == "":
        return ""
    key = raw.lower().replace("_", "-")
    if key in LANG_ALIASES:
        return LANG_ALIASES[key]
    # Fallback: normalize obvious locale forms like pt-BR -> PT-BR, en-US -> EN-US
    parts = [p for p in key.split("-") if p]
    if len(parts) == 1:
        return parts[0].upper()
    if len(parts) >= 2:
        return parts[0].upper() + "-" + parts[1].upper()
    return raw.upper()


def parse_translation_payload_from_user_json(messages: List[dict]):
    if not messages:
        return None, None, None, "No messages found."

    user_raw = None
    for message in messages:
        if message.get("role") == "user":
            user_raw = extract_text_content(message.get("content", ""))

    if not isinstance(user_raw, str) or user_raw == "":
        return None, None, None, "For model `deeplx`, the user message must be a JSON string."

    payload = None
    try:
        payload = json.loads(user_raw)
    except Exception:
        # Fallback: tolerate pseudo-JSON with literal newlines inside the content string.
        def extract_value(field_names):
            for name in field_names:
                pattern = rf'"{re.escape(name)}"\s*:\s*"'
                m = re.search(pattern, user_raw)
                if not m:
                    continue
                start = m.end()
                if name in ('content', 'text', 'input', 'message'):
                    # Take everything until the closing quote that is followed by optional whitespace then } or ,
                    m2 = re.search(r'"\s*(?:,\s*"|\}|$)', user_raw[start:], re.S)
                    if m2:
                        return user_raw[start:start + m2.start()]
                else:
                    m2 = re.search(r'([^"\\]*(?:\\.[^"\\]*)*)"', user_raw[start:], re.S)
                    if m2:
                        return m2.group(1)
            return None

        payload = {
            'source_lang': extract_value(['source_lang', 'sourceLang', 'source']) or '',
            'target_lang': extract_value(['target_lang', 'targetLang', 'target']) or '',
            'content': extract_value(['text', 'content', 'input', 'message']) or '',
        }

    source_lang = normalize_lang(payload.get("source_lang") or payload.get("sourceLang") or payload.get("source") or "")
    target_lang = normalize_lang(payload.get("target_lang") or payload.get("targetLang") or payload.get("target") or "")
    text = payload.get("text") or payload.get("content") or payload.get("input") or payload.get("message") or ""

    if not target_lang:
        return None, None, None, "For model `deeplx`, `target_lang` is required in the user JSON message."
    if not isinstance(text, str) or text == "":
        return None, None, None, "For model `deeplx`, `text` is required in the user JSON message."

    return source_lang, target_lang, text, None


async def translate_single(text: str, source_lang: str, target_lang: str, session: aiohttp.ClientSession):
    if source_lang == target_lang:
        return {target_lang: text}

    # url = "https://api.deeplx.org/translate"
    # url 从环境变量获取
    url = os.environ.get("TRANSLATION_API_URL", "https://api.deeplx.org/translate")
    payload = {}
    if source_lang == "":
        payload = {
            "text": text,
            "target_lang": target_lang
        }
    else:
        payload = {
            "text": text,
            "source_lang": source_lang,
            "target_lang": target_lang
        }

    start_time = time.time()
    async with session.post(url, json=payload) as response:
        logging.info(f"Translation from {source_lang} to {target_lang} took: {time.time() - start_time}")
        if response.status != 200:
            logging.error(f"Translation failed: {response.status}, {await response.text()}")
            raise HTTPException(status_code=response.status, detail="Translation failed")

        result = await response.json()
        if result['code'] != 200:
            logging.error(f"Translation failed: {result}")
            raise HTTPException(status_code=400, detail="Translation failed")

        return {target_lang: result['data']}
    
from fastapi.encoders import jsonable_encoder

@app.post("/v1/chat/completions")
async def translate_request(chat_request: ChatRequest):
    request_data = jsonable_encoder(chat_request)
    logging.info(f"Received request: {request_data}")

    text = ""
    if chat_request.model == "deeplx":
        source_lang, target_lang, text, err = parse_translation_payload_from_user_json(chat_request.messages)
        if err:
            logging.error(err)
            return Response(content=err, status_code=400)
    else:
        model_split = chat_request.model.split('-')
        # 检查 model_split 的长度，以适应不同情况
        if len(model_split) == 3:
            source_lang = model_split[1]
            target_lang = model_split[2]
        elif len(model_split) == 2:
            source_lang = ""  # 将 source_lang 置为空
            target_lang = model_split[1]
        else:
            # 如果 model_split 长度既不是 2 也不是 3，记录错误并返回
            logging.error(f"Invalid model format: {chat_request.model}")
            return Response(content="Invalid model format.", status_code=400)

        for message in chat_request.messages:
            if message['role'] == 'user':
                text = extract_text_content(message.get('content', ""))

        if text == "":
            logging.warning("No user message found.")
            return Response(content="No user message found.", status_code=400)

    logging.info(f"Translating from {source_lang} to {target_lang}, text: {text}")

    async with aiohttp.ClientSession() as session:
        translation_result = await translate_single(text, source_lang, target_lang, session)

    translated_text = translation_result.get(target_lang, "")
    chat_message_id = str(uuid.uuid4())
    timestamp = int(datetime.datetime.now().timestamp())

    if not chat_request.stream:
        data = {
            "id": chat_message_id,
            "object": "chat.completion",
            "created": timestamp,
            "model": chat_request.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": translated_text
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": len(text),
                "completion_tokens": len(translated_text),
                "total_tokens": len(text) + len(translated_text)
            }
        }
        logging.info(f"Translated text (json mode): {translated_text}")
        return data

    async def sse_translate():
        data = {
            "id": chat_message_id,
            "object": "chat.completion.chunk",
            "created": timestamp,
            "model": chat_request.model,
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "content": translated_text
                    },
                    "finish_reason": None
                }
            ]
        }
        logging.info(f"Translated text (stream mode): {translated_text}")
        yield f"data: {json.dumps(data)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(sse_translate(), media_type="text/event-stream")


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
