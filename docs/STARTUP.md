# 灵犀 (Lingxi) v1.1 启动文档

---

## 环境要求

| 依赖 | 版本要求 | 说明 |
|---|---|---|
| Python | 3.11+ | 解释器 |
| MySQL | 5.7+ / 8.0+ | 用户、对话、消息数据存储 |
| Ollama | 最新版 | 可选，本地模型推理 |
| pip | 最新版 | 包管理 |

---

## 一、安装 MySQL 并创建数据库

```sql
-- 登录 MySQL（替换为你的用户名和密码）
mysql -u root -p

-- 创建数据库
CREATE DATABASE ling_xi CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 确认创建成功
SHOW DATABASES LIKE 'ling_xi';

EXIT;
```

---

## 二、修改 .env 数据库配置

打开项目根目录的 `.env` 文件，确认数据库配置与你的实际环境一致：

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=你的真实密码
DB_NAME=ling_xi
```

---

## 三、安装 Python 依赖

```powershell
# 创建虚拟环境（推荐）
python -m venv venv
venv\Scripts\activate

# 安装依赖（sentence-transformers 首次会下载 ~2GB 模型文件，耗时较长）
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
```

---

## 四、配置 Ollama（可选，仅使用本地模型时需要）

```powershell
# 确认 Ollama 服务已启动
ollama list

# 拉取需要的模型
# 普通对话模型（轻量快速）
ollama pull qwen2.5:1.5b

# 深度推理模型（逻辑分析能力强）
ollama pull deepseek-r1:7b
```

---

## 五、启动服务

```powershell
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

启动成功后会输出：

```
==================================================
灵犀服务启动 - 当前路由配置：
  普通对话 /chat   -> ollama   | 模型: qwen2.5:1.5b
  深度推理 /reason -> ollama   | 模型: deepseek-r1:7b
  联网搜索 /search -> deepseek | 模型: deepseek-ai/DeepSeek-V3
==================================================
```

---

## 六、验证服务

### 健康检查（含 Ollama 模型状态）

```powershell
curl http://localhost:8000/health
```

正常返回示例：

```json
{
  "status": "ok",
  "routing": {
    "chat": {
      "service": "ollama",
      "model": "qwen2.5:1.5b",
      "ollama_status": { "reachable": true, "model_available": true, "error": null }
    },
    "reason": {
      "service": "ollama",
      "model": "deepseek-r1:7b",
      "ollama_status": { "reachable": true, "model_available": true, "error": null }
    },
    "search": { "service": "deepseek", "model": "deepseek-ai/DeepSeek-V3" }
  }
}
```

### 普通对话测试

```powershell
curl -X POST http://localhost:8000/chat `
  -H "Content-Type: application/json" `
  -d '{"message":"你好，请介绍一下你自己"}'
```

---

## 附录 A：JWT 密钥详解

JWT（JSON Web Token）的 `SECRET_KEY` 是用于签名和验证 Token 的密钥，本质是一个**随机字符串**。

### 密钥的作用

```
用户登录 → 服务器用 SECRET_KEY 签发 Token（签名）
用户请求 → 服务器用 SECRET_KEY 验证 Token（验签）
```

- Token 本身不加密（Payload 可被任何人解码查看）
- SECRET_KEY 保证 Token **无法被伪造**（签名校验）
- 只有持有正确 SECRET_KEY 的服务器才能签发有效 Token

### 如何生成安全的密钥

**方式一（推荐）：Python 一行命令**

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
# 输出示例：51ae1a4ab84b4a1dd733f7f0130bb03656d5034c393f0abae446d4f29a2b2635
```

**方式二：OpenSSL**

```powershell
openssl rand -hex 32
```

**方式三：Linux / macOS**

```bash
head -c 32 /dev/urandom | xxd -p -c 64
```

### 安全注意事项

| 场景 | 做法 |
|---|---|
| 开发环境 | 可以使用固定值，不影响功能 |
| 生产环境 | 必须使用随机生成的长密钥（≥32字节） |
| 密钥泄露 | 立即更换，旧 Token 将全部失效 |
| 密钥存储 | 放在 `.env` 中，**不要提交到 Git** |
| 密钥轮换 | 定期更换，通常 3-6 个月一次 |

### 当前项目配置

```env
SECRET_KEY=51ae1a4ab84b4a1dd733f7f0130bb03656d5034c393f0abae446d4f29a2b2635
ALGORITHM=HS256                    # HMAC-SHA256 对称签名算法
ACCESS_TOKEN_EXPIRE_MINUTES=1440   # Token 有效期 24 小时
```

- `HS256` 是单体应用最常用的算法，性能好、实现简单
- 如果需要多服务共享验证，可以切换到 `RS256`（非对称算法，支持公钥分发）

---

## 附录 B：常见问题排查

| 问题 | 原因 | 解决 |
|---|---|---|
| `Can't connect to MySQL server` | MySQL 未启动 | `net start MySQL80`（Windows） |
| `Unknown database 'ling_xi'` | 数据库未创建 | 执行步骤一中的 `CREATE DATABASE` |
| `ModuleNotFoundError: xxx` | 依赖未安装 | `pip install -r requirements.txt` |
| Ollama 状态显示 `reachable: false` | Ollama 未启动 | 打开 Ollama 桌面程序或执行 `ollama serve` |
| `model_available: false` | 模型未拉取 | `ollama pull 模型名` |
| `Access denied for user` | 数据库密码错误 | 检查 `.env` 中 `DB_PASSWORD` |
| `sentence-transformers` 安装失败 | 缺少 C++ 编译工具 | 安装 Visual C++ Build Tools |
