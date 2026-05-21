## 用法

仓库内已包含相关文件和目录，拉到本地后修改 docker-compose.yml 文件里的环境变量后运行`docker-compose up -d`即可。

## 模型名说明

兼容原有通过模型名指定语言的方式：

- `deeplx-EN-ZH`: 英文转中文
- `deeplx-ZH-EN`: 中文转英文
- `deeplx-EN`: 自动识别语言转英文
- `deeplx-ZH`: 自动识别语言转中文

也可以使用 `model: "deeplx"`，在用户消息中用 JSON 指定翻译参数。

## 调用示例

### 通过模型名指定语言

```json
{
    "messages": [
        {
            "role": "user",
            "content": [
                "Hi"
            ]
        }
    ],
    "stream": true,
    "model": "deeplx-ZH"
}
```

预期响应：

```plaintext
data: {"id": "a0e35ab6-b859-441b-93e6-6391dcb468ed", "object": "chat.completion.chunk", "created": 1709348239, "model": "deeplx-ZH", "choices": [{"index": 0, "delta": {"content": "你好"}, "finish_reason": null}]}

data: [DONE]
```

### 通过 JSON 指定语言

`stream` 可省略，默认返回非流式 OpenAI Chat Completions 格式响应。

```json
{
    "messages": [
        {
            "role": "user",
            "content": "{\"source_lang\": \"EN\", \"target_lang\": \"ZH\", \"text\": \"Hi\"}"
        }
    ],
    "model": "deeplx"
}
```

也支持 `source`、`target`、`content` 等字段别名，以及 `english`、`zh-cn`、`traditional chinese` 等常见语言名或 locale 写法。

常见客户端提示词配置示例：

陪读蛙：

```json
{
    "target_lang": "{{targetLanguage}}",
    "content": "{{input}}"
}
```

Zotero：

```json
{
    "source_lang": "${langFrom}",
    "target_lang": "${langTo}",
    "content": "${sourceText}"
}
```

预期响应：

```json
{
    "id": "a0e35ab6-b859-441b-93e6-6391dcb468ed",
    "object": "chat.completion",
    "created": 1709348239,
    "model": "deeplx",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "你好"
            },
            "finish_reason": "stop"
        }
    ],
    "usage": {
        "prompt_tokens": 2,
        "completion_tokens": 2,
        "total_tokens": 4
    }
}
```

## 效果展示

![image](https://github.com/Ink-Osier/DeepLXToV1Api/assets/133617214/12c60ed1-538b-4a24-8b4d-999e54f8dabd)
