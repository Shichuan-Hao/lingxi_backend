# 故障排查记录

---

## 1. Pydantic Settings 验证错误

### 日期

2026-07-26

### 错误现象

启动服务时报 `pydantic_core._pydantic_core.ValidationError`，服务无法启动：

```text
pydantic_core._pydantic_core.ValidationError: 4 validation errors for Settings
REDIS_HOST
  Field required [type=missing, ...]
REDIS_PORT
  Field required [type=missing, ...]
HF_ENDPOINT
  Extra inputs are not permitted [type=extra_forbidden, ...]
REDIS_URL
  Extra inputs are not permitted [type=extra_forbidden, ...]
```

### 完整堆栈

```text
File "main.py", line 6, in <module>
    from app.services.llm_factory import LLMFactory
  File "app/services/llm_factory.py", line 2, in <module>
    from app.core.config import settings, ServiceType
  File "app/core/config.py", line 73, in <module>
    settings = Settings()
  File "pydantic_settings/main.py", line 247, in __init__
    ...
pydantic_core._pydantic_core.ValidationError: 4 validation errors for Settings
```

### 根因分析

问题出在 `app/core/config.py` 中的 `Settings` 类定义与 `.env` 文件内容不匹配，有两类错误：

**① `REDIS_HOST` / `REDIS_PORT` — Field required（必填字段缺失）**
- `Settings` 类定义：`REDIS_HOST: str` 和 `REDIS_PORT: int` 都是无默认值的必填字段。
- `.env` 实际：只写了 `REDIS_URL=redis://localhost:6379/0`，没有这两个字段。
- 原因：`REDIS_URL` 是 `Settings` 类的 `@property`（计算属性），不是 pydantic 字段，pydantic 不会用它推导 `REDIS_HOST` / `REDIS_PORT`。

**② `HF_ENDPOINT` / `REDIS_URL` — Extra inputs are not permitted（不允许额外字段）**
- Pydantic v2 的 `BaseSettings` 默认 `extra='forbid'`，`.env` 中未在模型定义的变量会被拒绝。
- `HF_ENDPOINT` 未在 `Settings` 中定义；`REDIS_URL` 是 `@property` 不是字段。

### 解决方案

**修改 1（`HF_ENDPOINT` Extra forbidden）：`app/core/config.py`** — 在 `Settings` 中定义 `HF_ENDPOINT` 字段：

```python
# Embedding settings 区域新增
HF_ENDPOINT: str = "https://huggingface.co"
```

> 注意：优先使用「定义字段」而非 `extra = "ignore"`，这样可以显式管理所有配置项，避免遗漏。

**修改 2（`REDIS_HOST` / `REDIS_PORT` Field required）：`.env`** — 将 `REDIS_URL` 拆分为独立字段：

```env
# 旧写法（错误）
REDIS_URL=redis://localhost:6379/0

# 新写法（正确）
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
```

**修改 3：`.env.example`** — 同步更新示例文件。

### 经验总结

| 问题类型 | 原因 | 预防措施 |
|---------|------|---------|
| Field required | `.env` 变量名与 `Settings` 字段名不一致 | 添加新配置时确保两边命名完全一致 |
| Extra forbidden | `.env` 中有 Settings 未定义的变量 | 优先在 Settings 中显式定义该字段（带默认值），而非用 `extra = "ignore"` 静默忽略 |
| `@property` vs 字段 | 把计算属性误当成可配置字段 | `@property` 不能从 `.env` 注入，需要用独立原始字段 |

**核心原则：`.env` 中的每个变量名必须与 `Settings` 类中的字段名一一对应（区分大小写）。新增环境变量时，同步在 `Settings` 中定义对应字段。**

---

## 2. OllamaService.generate_stream() 参数不匹配

### 日期

2026-07-26

### 错误现象

聊天接口返回 500，日志报错：

```text
ERROR    | main:chat_endpoint:96 - Chat error: OllamaService.generate_stream() got an unexpected keyword argument 'conversation_id'
```

### 完整堆栈

```text
File "main.py", line 87, in chat_endpoint
    chat_service.generate_stream(
        messages=request.messages,
        user_id=request.user_id,
        conversation_id=request.conversation_id,
        on_complete=ConversationService.save_message
    )
TypeError: OllamaService.generate_stream() got an unexpected keyword argument 'conversation_id'
```

### 根因分析

`main.py` 的 `chat_endpoint` 调用 `generate_stream()` 时传了 4 个参数：`messages`、`user_id`、`conversation_id`、`on_complete`。

但 `OllamaService.generate_stream()` 的签名只有 `messages` 和 `user_id`，缺少 `conversation_id` 和 `on_complete`。而 `DeepseekService.generate_stream()` 已经适配了这 4 个参数。

当 `.env` 中 `CHAT_SERVICE=ollama` 时，`LLMFactory` 返回 `OllamaService` 实例，调用就报错了。

### 解决方案

在 `app/services/ollama_service.py` 中：

**① 导入 `Callable`：**

```python
from typing import List, Dict, AsyncGenerator, Callable, Optional
```

**② 给 `generate_stream()` 增加参数和保存逻辑：**

```python
async def generate_stream(
    self, 
    messages: List[Dict],
    user_id: Optional[int] = None,
    conversation_id: Optional[int] = None,
    on_complete: Optional[Callable[[int, int, List[Dict], str], None]] = None,
    model: str = "deepseek-r1:32b"
) -> AsyncGenerator[str, None]:
```

在缓存命中和缓存未命中两个分支末尾，增加保存消息的回调：

```python
# 缓存命中后
if on_complete and user_id is not None and conversation_id is not None:
    await on_complete(user_id, conversation_id, messages, cached_response)

# 缓存未命中后（在完整响应拼接完成后）
if on_complete and user_id is not None and conversation_id is not None:
    await on_complete(user_id, conversation_id, messages, complete_response)
```

### 经验总结

| 问题类型 | 原因 | 预防措施 |
|---------|------|---------|
| 接口不一致 | 多个实现类（OllamaService / DeepseekService）的方法签名不同步 | 抽取公共接口/基类，新增参数时同步所有实现 |

**核心原则：当多个类实现同一接口时，方法签名必须保持一致。新增参数要同步修改所有实现类。**

---

## 3. UTF-8 编码错误：surrogates not allowed

### 日期

2026-07-26

### 错误现象

调用 DeepSeek API 后，打印模型回复时报错：

```text
发生错误: 'utf-8' codec can't encode characters in position 93-94: surrogates not allowed
```

### 完整堆栈

```text
  File "app/test/deepseek_disk_cache.py", line 64, in main
    print(f"AI助手: {assistant_message.content}")
UnicodeEncodeError: 'utf-8' codec can't encode characters in position 93-94: surrogates not allowed
```

### 根因分析

DeepSeek API 返回的文本内容中有时会包含 `\ud800`-`\udfff` 范围内的孤立代理字符（surrogates）。这些字符：

- 是 Unicode 保留给 UTF-16 编码内部使用的，**不是合法的 Unicode 码点**
- 在 UTF-8 编码中无法表示，因为 UTF-8 编码规范不允许对代理码点进行编码
- 当 `print()` 或文件写入操作试图将这些字符串编码为 UTF-8 时会直接抛出 `UnicodeEncodeError`

这是 LLM 模型输出的已知偶发问题，模型可能生成不在标准字符集中的异常字节序列。

### 解决方案

对 API 返回的内容做一层安全过滤，用 `errors='replace'` 将非法字符替换为 `�`：

```python
def safe_str(s: str) -> str:
    """移除字符串中的非法 Unicode 代理字符，防止 UTF-8 编码报错"""
    return s.encode('utf-8', errors='replace').decode('utf-8')
```

在使用 `assistant_message.content` 之前调用：

```python
content = safe_str(assistant_message.content)
print(f"AI助手: {content}")
```

### 经验总结

| 问题类型 | 原因 | 预防措施 |
|---------|------|---------|
| 编码错误 | LLM 输出中混入非法 Unicode 代理字符 | 对外部 API 返回的文本始终做编码清洗 |

**核心原则：任何来自 LLM API 的文本内容，在打印、存储、序列化之前，都应做一次 `encode('utf-8', errors='replace').decode('utf-8')` 安全过滤。**

---

## 3. 创建会话报错 `Multiple rows were found when one or none was required`

### 问题现象

POST `/api/conversations` 接口返回 500，日志显示：

```
Error creating conversation: Multiple rows were found when one or none was required
```

### 原因分析

`create_conversation` 中查询已有空会话时使用了 `scalar_one_or_none()`：

```python
stmt = select(Conversation).where(
    Conversation.user_id == user_id,
    Conversation.title == "新会话"
).order_by(Conversation.created_at.desc())

result = await db.execute(stmt)
existing_conversation = result.scalar_one_or_none()  # 多行时抛异常
```

当用户多次刷新页面，每次都触发创建 title 为"新会话"的空会话，但又没发过消息（导致未改名），表中会积累多条同名空会话。`scalar_one_or_none()` 要求最多返回 1 行，遇到多行直接抛异常。

### 解决方案

**文件：`app/services/conversation_service.py`** — 将 `scalar_one_or_none()` 改为 `scalars().first()`：

修复前：
```python
async def create_conversation(
    self, user_id: int, title: Optional[str] = None
):
    from app.models.conversation import Conversation
    async with AsyncSessionLocal() as db:
        stmt = select(Conversation).where(
            Conversation.user_id == user_id,
            Conversation.title == "新会话"
        ).order_by(Conversation.created_at.desc())

        result = await db.execute(stmt)
        existing_conversation = result.scalar_one_or_none()  # 多行时抛异常

        if existing_conversation:
            return existing_conversation

        conversation = Conversation(user_id=user_id, title="新会话")
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        return conversation
```

修复后：
```python
async def create_conversation(
    self, user_id: int, title: Optional[str] = None
):
    from app.models.conversation import Conversation
    async with AsyncSessionLocal() as db:
        stmt = select(Conversation).where(
            Conversation.user_id == user_id,
            Conversation.title == "新会话"
        ).order_by(Conversation.created_at.desc())

        result = await db.execute(stmt)
        existing_conversation = result.scalars().first()  # 可能有多条，取最新一条

        if existing_conversation:
            return existing_conversation

        conversation = Conversation(user_id=user_id, title="新会话")
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        return conversation
```

### 经验总结

| 方法 | 行为 | 适用场景 |
|------|------|---------|
| `scalar_one_or_none()` | 最多 1 行，多行抛异常 | 确定唯一值（如 id 精确查询） |
| `scalars().first()` | 取第一行，多行不报错 | 带排序条件、可能有多条结果 |

**核心原则：条件中不含唯一约束时，禁止使用 `scalar_one` / `scalar_one_or_none`，用 `scalars().first()` 或 `scalars().all()` 代替。**
