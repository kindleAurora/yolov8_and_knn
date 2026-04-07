# Infrastructure

本目录提供阶段 1 所需的基础设施脚手架，当前重点是本地开发环境而不是生产环境部署闭环。

## 当前内容

- `docker/docker-compose.yml`：本地开发编排
- `nginx/default.conf`：后续网关层预留
- `postgres/`：数据库初始化预留目录
- `redis/`：缓存层预留目录
- `observability/`：后续监控体系预留目录

## 使用方式

在项目根目录准备 `.env` 后执行：

```powershell
docker compose -f code/infra/docker/docker-compose.yml up --build
```
