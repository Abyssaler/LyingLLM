# LyingLLM 部署手册

## 1. 架构概览

```
┌─────────────┐     ┌─────────────┐
│   Nginx     │────▶│  Frontend   │
│  (反向代理)   │     │  (静态文件)   │
│             │     └─────────────┘
│             │
│             │     ┌─────────────┐
│             │────▶│  Backend     │
│             │     │  (uvicorn)   │
│             │     │  :8000       │
└─────────────┘     └─────────────┘
```

- **后端**：FastAPI + uvicorn，提供 REST API (端口 8000) 和 WebSocket
- **前端**：Vite 构建产出静态文件，由 Nginx 托管并反向代理 API 请求到后端
- **数据存储**：内存存储（无数据库依赖），游戏数据通过 `GameLogStorage` 管理事件溯源日志

---

## 2. 生产部署

### 2.1 后端部署

#### 方式 A：直接运行

```bash
# 在项目根目录执行

# 1. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate    # Windows

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 填入生产环境配置

# 4. 启动（生产环境不要使用 --reload）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

#### 方式 B：Systemd 服务

创建 `/etc/systemd/system/lyingllm.service`：

```ini
[Unit]
Description=LyingLLM API
After=network.target

[Service]
Type=simple
User=lyingllm
WorkingDirectory=/opt/lyingllm
EnvironmentFile=/opt/lyingllm/.env
ExecStart=/opt/lyingllm/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable lyingllm
sudo systemctl start lyingllm
```

#### 方式 C：Docker

创建 `Dockerfile.api`：

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY configs ./configs

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

构建并运行：

```bash
docker build -f Dockerfile.api -t lyingllm-api .
docker run -d --name lyingllm-api \
  -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/configs:/app/configs:ro \
  -v $(pwd)/logs:/app/logs \
  lyingllm-api
```

### 2.2 前端部署

#### 方式 A：Nginx 托管

```bash
cd frontend

# 1. 安装依赖
npm install

# 2. 构建生产版本
npm run build
# 产出在 dist/ 目录
```

Nginx 配置 `/etc/nginx/sites-available/lyingllm`：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态文件
    root /opt/lyingllm/frontend/dist;
    index index.html;

    # SPA 路由回退
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API 反向代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # REST API 无额外配置
    }

    # WebSocket 反向代理
    location /api/ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/lyingllm /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

#### 方式 B：Docker

创建 `Dockerfile.frontend`：

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### 2.3 Docker Compose（一键部署）

创建 `docker-compose.yml`：

```yaml
version: "3.8"

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./configs:/app/configs:ro
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    ports:
      - "80:80"
    depends_on:
      api:
        condition: service_healthy
    restart: unless-stopped
```

```bash
docker compose up -d --build
```

---

## 3. 环境变量配置

### 3.1 后端环境变量

创建 `.env`（从 `.env.example` 复制）：

```bash
# === 必填 ===
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx

# === 可选 ===
# 应用配置
APP_HOST=0.0.0.0
APP_PORT=8000
APP_DEBUG=false
APP_LOG_DIR=./logs

# OpenAI
OPENAI_BASE_URL=https://api.openai.com/v1

# Anthropic
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
ANTHROPIC_BASE_URL=https://api.anthropic.com

# DeepSeek
DEEPSEEK_API_KEY=xxxxxxxxxxxxxxxx

# 自定义提供商（支持 OpenAI 兼容接口）
# CUSTOM_PROVIDER_1_NAME=my_provider
# CUSTOM_PROVIDER_1_API_KEY=xxxxxxxxxxxxxxxx
# CUSTOM_PROVIDER_1_BASE_URL=https://my-llm-api.example.com/v1
# CUSTOM_PROVIDER_1_MODEL=my-model-name
```

### 3.2 安全注意事项

| 事项 | 建议 |
|------|------|
| API Key | **切勿提交到版本控制**，`.env` 已在 `.gitignore` 中 |
| CORS | 生产环境应修改 `app/main.py` 中 `allow_origins` 为具体域名 |
| HTTPS | 生产环境必须启用，Nginx 配置 SSL 证书 |
| 防火墙 | 后端端口 8000 仅对 Nginx 可见，不对外暴露 |

---

## 4. 前端构建配置

### 4.1 生产环境 API 代理

生产环境通过 Nginx 反向代理，**不需要** 修改前端代码。Vite 构建产出的静态文件中 API 请求路径为 `/api/*`，由 Nginx 转发到后端。

### 4.2 WebSocket 协议

前端自动根据当前页面协议选择 `ws://` 或 `wss://`，生产环境启用 HTTPS 后自动使用 `wss://`。

相关代码位于 `frontend/src/api/client.ts`：

```typescript
const WS_PROTOCOL = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const WS_BASE = `${WS_PROTOCOL}//${window.location.host}/api/ws/games`;
```

### 4.3 自定义后端地址

如果前端和后端部署在不同域名，需要修改 Vite 代理配置（开发环境）或 Nginx 代理规则（生产环境）。

开发环境 `frontend/vite.config.ts`：

```typescript
server: {
  port: 3000,
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
    },
    '/api/ws': {
      target: 'ws://localhost:8000',
      ws: true,
    },
  },
}
```

---

## 5. 配置定制

### 5.1 添加新角色配置

在 `configs/roles/` 下创建新的 YAML 文件，例如 `custom.yaml`：

```yaml
name: "自定义角色配置"
version: "1.0"
roles:
  werewolf:
    name: "狼人"
    faction: wolf
    # ... 参照 classic.yaml 格式
```

通过 API 获取：`GET /api/configs/roles/custom`

### 5.2 添加新规则配置

在 `configs/rules/` 下创建新的 YAML 文件，例如 `fast.yaml`：

```yaml
name: "快速模式"
version: "1.0"
phases:
  enable_sheriff: false
  enable_last_words: false
  enable_wolf_discuss: false
# ... 参照 classic.yaml 格式
```

创建游戏时指定：`POST /api/games { "rules_config": "fast" }`

### 5.3 添加新 LLM 提供商

**方式一**：修改 `configs/models/providers.yaml`，添加新提供商条目。

**方式二**：通过环境变量动态添加（适合部署时注入）：

```bash
CUSTOM_PROVIDER_1_NAME=my_provider
CUSTOM_PROVIDER_1_API_KEY=sk-xxx
CUSTOM_PROVIDER_1_BASE_URL=https://my-llm-api.example.com/v1
CUSTOM_PROVIDER_1_MODEL=my-model-name
```

### 5.4 修改 CORS

编辑 `app/main.py` 中的 CORS 配置：

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-domain.com"],  # 限制为具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 6. 监控与日志

### 6.1 应用日志

后端日志输出到 `logs/` 目录（可通过 `APP_LOG_DIR` 环境变量配置）。

### 6.2 健康检查

```bash
curl http://localhost:8000/health
# 返回: {"status": "healthy"}
```

Docker Comprove 已配置健康检查，每 30 秒探测一次。

### 6.3 进程监控

```bash
# systemd
sudo systemctl status lyingllm
sudo journalctl -u lyingllm -f

# Docker
docker compose logs -f api
docker compose ps
```

---

## 7. 数据管理

### 7.1 游戏数据持久化

当前版本游戏数据存储在内存中（`_games` 字典），服务重启后数据丢失。

如需持久化：
1. 游戏日志可通过 `GET /api/games/{id}/log` 导出为 JSON
2. 可在游戏结束后调用此接口保存数据

### 7.2 扩展建议

- 添加数据库存储（如 PostgreSQL + SQLAlchemy）
- 游戏日志写入文件（`GameLogStorage.save_to_file()` 已实现）
- 添加 Redis 用于 WebSocket 会话管理

---

## 8. 常见部署问题

| 问题 | 原因 | 解决方法 |
|------|------|---------|
| Nginx 502 Bad Gateway | 后端未启动或端口不匹配 | 检查后端进程和端口 |
| WebSocket 连接立即断开 | Nginx 未配置 WebSocket 代理头 | 确认 `proxy_set_header Upgrade/Connection` 配置 |
| API 请求 404 | Nginx 代理路径不匹配 | 确认 `/api/` location 块正确 |
| 前端页面刷新 404 | Nginx 未配置 SPA 回退 | 添加 `try_files $uri $uri/ /index.html` |
| CORS 报错 | 生产环境跨域配置 | 修改 `allow_origins` 为具体前端域名 |
| LLM 调用超时 | 网络/API Key/配额问题 | 检查后端日志确认错误类型 |
| `pip install` 失败 | Python 版本不兼容 | 确认 Python >= 3.11 |
| `npm install` 失败 | Node.js 版本不兼容 | 确认 Node.js >= 18 |

---

## 9. 快速部署清单

```bash
# 1. 克隆代码
git clone <repo-url> && cd LyingLLM

# 2. 配置后端
# 在项目根目录执行
cp .env.example .env
# 编辑 .env 填入 OPENAI_API_KEY

# 3. 配置前端
cd frontend
npm install

# 4. 启动后端（终端 1）
cd ..
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 5. 启动前端开发服务器（终端 2）
cd frontend
npm run dev

# 6. 访问 http://localhost:3000 开始游戏
```

生产部署：

```bash
# 后端
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# 前端
cd frontend && npm install && npm run build
# 将 dist/ 目录部署到 Nginx
```
