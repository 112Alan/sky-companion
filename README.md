# Sky Companion

光遇 PC 端桌面 AI 伴侣。程序会截图识别游戏里的聊天气泡，用聊天模型生成短回复，然后把回复打进游戏。

## 安全说明

仓库不内置任何 API Key。

首次运行时，程序会在本机生成：

```text
user_data/settings.json
user_data/memory.json
user_data/style_knowledge.json
user_data/search_knowledge.json
user_data/小懒快速配置.txt
```

`user_data/` 已加入 `.gitignore`，不要上传这个目录。

## 默认模型

默认识别和回复方式：

- 视觉识别：Windows 本地 OCR，不需要 API Key
- 聊天回复：DeepSeek，默认模型 `deepseek-v4-pro`

首次运行只需要填写 DeepSeek 聊天模型配置：

- 接口网址 `base_url`
- 模型名
- API Key

## 首次运行会询问

1. DeepSeek 聊天模型的网址、模型名和 Key
2. 给你的光遇伴侣命名
3. 你在光遇里的称呼/备注名
4. 性格提示词
5. 是否需要识别使用者

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
截图 -> 本地 Windows OCR 快速识别 -> 聊天模型回复 -> 输入到光遇
```

可选视觉模型兜底默认关闭。正常使用只走本地 OCR 和 DeepSeek。

## 使用者识别

如果开启“需要识别使用者”，程序会按光遇聊天记录里的后缀判断是谁说的话：

```text
哈喽-大号
走了拜拜-其他人
```

只有后缀匹配“使用者称呼”的消息才会回复。比如使用者称呼是 `大号`，程序会回复 `哈喽-大号`，跳过 `走了拜拜-其他人`。

开启后，程序会尽量保持聊天记录栏打开：

- 没看到聊天栏时，会按 `C` 拉出聊天记录。
- 底部是“聊天”时，会先按一次 `Enter` 再输入。
- 底部是“发送”时，会直接输入并发送。

## 快速配置

运行后会生成：

```text
user_data/小懒快速配置.txt
```

可以用记事本打开修改：

```text
当前称呼：小懒

使用者称呼：大号

是否需要识别使用者：是

当前性格：
像真实朋友一样聊天……
```

保存后，正在运行的小懒会自动同步这些配置。

## 长期记忆

程序不会把所有聊天原句都塞进提示词。它会先保留少量近期对话作为整理素材，再定期让 DeepSeek 把聊天整合成一段长期理解提示词，例如使用者偏好、相处方式、讨厌点、最近状态。

长期记忆保存在：

```text
user_data/memory.json
```

下次运行时会读取这段整理后的理解，让伴侣越来越了解使用者。

## 联网搜索

程序内置无 Key 的轻量网页搜索，默认开启：

- 玩家明确说“搜/查一下/上网查/什么意思/什么梗”，或问“今天任务是什么”“复刻是谁”“季节蜡烛在哪”等资料型问题时，会临时搜索。
- 遇到不懂的词、梗、活动名或玩法名时，会尽量先搜再回答。
- 搜索到的公开摘要会整理成本地知识，保存到：

```text
user_data/search_knowledge.json
```

- 如果性格提示词里写了“病恋/病娇/抖音/参考风格”等，程序也会联网搜索公开摘要，整理成一段本地风格参考，保存到：

```text
user_data/style_knowledge.json
```

这份风格参考只提炼语气和氛围，不会模仿具体博主，也不会引导现实威胁或控制行为。

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

通常是本地 OCR 没有读到画面文字，优先检查：

- 光遇窗口没有最小化，聊天文字在截图里清楚可见
- PowerShell/OBS/别的窗口没有挡住光遇聊天区域
- 光遇文字太小或太暗时，可以把游戏窗口放大一点

## License

MIT
