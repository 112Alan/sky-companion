# Sky Companion

光遇 PC 端桌面 AI 伴侣。程序会截图识别游戏里的聊天气泡，用聊天模型生成短回复，然后把回复打进游戏。

## 安全说明

仓库不内置任何 API Key。

首次运行时，程序会在本机生成：

```text
user_data/settings.json
user_data/memory.json
```

`user_data/` 已加入 `.gitignore`，不要上传这个目录。

## 默认模型

首次运行会询问你是否有默认模型的 API Key：

- 视觉识别：Gemini，默认模型 `gemini-2.5-flash`
- 聊天回复：DeepSeek，默认模型 `deepseek-chat`

如果你没有对应 Key，可以选择自定义 OpenAI Chat Completions 兼容模型，然后输入：

- 接口网址 `base_url`
- 模型名
- API Key

## 首次运行会询问

1. 视觉模型的网址、模型名和 Key
2. 聊天模型的网址、模型名和 Key
3. 给你的光遇伴侣命名
4. 你在光遇里的称呼/备注名
5. 性格提示词

如果没有给伴侣命名，程序会提示：

```text
请给你的光遇伴侣命名！
```

## 安装

```bash
pip install -r requirements.txt
```

建议用管理员权限打开终端，否则游戏窗口激活和输入可能失败。

## 运行

启动光遇后运行：

```bash
python main.py
```

或双击：

```text
start_sky.bat
```

菜单：

```text
1) 自动聊天
2) 网页聊天
3) 退出
```

自动聊天会执行：

```text
截图 -> 视觉模型识别聊天气泡 -> 聊天模型回复 -> 输入到光遇
```

## 长期记忆

程序会把对话摘要保存到：

```text
user_data/memory.json
```

下次运行时会读取这些记忆，让伴侣记得使用者和之前聊过的内容。

## 项目结构

```text
sky_companion/
├── main.py
├── config.py
├── requirements.txt
├── start_sky.bat
├── core/
│   ├── ocr_agent.py
│   ├── user_settings.py
│   ├── game_controller.py
│   └── screen_capture.py
├── knowledge/
│   └── dialogue.py
├── companion/
│   └── chat_interface.py
└── web_server.py
```

## 重新配置

删除本地配置后重新运行：

```text
user_data/settings.json
```

程序会再次进入首次配置流程。

## OCR 一直 empty 怎么办

如果日志反复出现：

```text
OCR: empty
```

通常是视觉模型没有读到画面文字，优先检查：

- 光遇窗口没有最小化，聊天文字在截图里清楚可见
- PowerShell/OBS/别的窗口没有挡住光遇聊天区域
- 视觉模型的 `base_url`、模型名、API Key 填对
- 视觉接口必须兼容 OpenAI Chat Completions 图片输入格式
- 光遇文字太小或太暗时，可以把游戏窗口放大一点

如果出现：

```text
VHTTP: 401
VHTTP: 403
VHTTP: 404
```

一般分别是 Key 错、接口不允许、网址或模型不对。

## License

MIT
