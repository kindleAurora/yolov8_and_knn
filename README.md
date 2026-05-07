# 牛只智能监控平台

本仓库用于实现 `docs/` 中定义的牛只智能监控平台毕业设计项目。

当前已完成：

- 阶段 1：工程骨架、Docker 开发环境、前后端基础服务、推理服务占位
- 阶段 2：登录鉴权、JWT 会话保持、角色权限、设备管理、区域管理、审计日志
- 阶段 3：推理服务统一契约、行为事件写库、事件工作台与最近事件展示
- 阶段 4：告警规则、告警中心、历史查询与基础可视化分析

## 语言规范

项目统一要求前后端对外展示内容使用中文：

- 前端页面标题、导航、按钮、表单、状态文案、提示信息统一使用中文
- 后端接口文档标题、标签、默认响应消息、错误提示统一使用中文
- 新增功能若无特殊原因，默认继续沿用中文界面与中文文案

该要求也已写入 [docs/ui-language-guideline.md](docs/ui-language-guideline.md)。

## 默认账号

执行阶段 3 迁移后，可直接使用以下演示账号：

- 管理员：`admin` / `admin123`
- 普通用户：`viewer` / `viewer123`

权限说明：

- 管理员可新增、编辑、停用、删除设备
- 普通用户可查看设备，并在当前农场范围内管理区域

## Docker 启动

在项目根目录执行：

```powershell
docker compose -f code/infra/docker/docker-compose.yml up -d --build
docker compose -f code/infra/docker/docker-compose.yml exec -T api alembic upgrade head
```

启动后访问：

- 前端：`http://localhost:5173`
- API 文档：`http://localhost:8000/docs`
- API 健康检查：`http://localhost:8000/health`
- 推理服务健康检查：`http://localhost:8001/health`

## 局域网 IP 部署

如果下一步要把整套系统部署到本机并通过局域网 IP 直接访问，优先使用生产部署编排：

```powershell
docker compose -f code/infra/docker/docker-compose.prod.yml up -d --build
docker compose -f code/infra/docker/docker-compose.prod.yml exec -T api alembic upgrade head
```

部署完成后：

- Web 入口：`http://<你的电脑IP>/`
- API 文档：`http://<你的电脑IP>/docs`
- API 接口：`http://<你的电脑IP>/api/v1/...`
- HLS 直播流：`http://<你的电脑IP>/hls/<stream-path>/index.m3u8`

当前生产部署做了这些调整：

- 前端由 `nginx` 提供静态文件，不再依赖 `vite dev server`
- Web、API、HLS 统一走同一个 IP，避免浏览器访问远程设备时命中 `localhost`
- API 与推理服务以非 `--reload` 模式运行，更适合常驻部署

上线前还需要确认两件事：

- Docker Desktop 已启动，并允许容器正常运行
- Windows 防火墙放通 Web 端口（默认 `80`）以及 RTSP 端口（默认 `8554`，如果外部设备需要推流/拉流）

## 本地开发

先复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

启动基础依赖：

```powershell
docker compose -f code/infra/docker/docker-compose.yml up -d postgres redis
```

启动 API：

```powershell
cd code/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

启动推理服务：

```powershell
cd code/inference-service
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

启动前端：

```powershell
cd code/web
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

## 阶段 2 验收点

- 未登录用户访问核心页面时会被重定向到登录页
- 登录后刷新页面仍可保持登录状态
- 退出登录后本地会话状态会被清除
- 管理员可维护设备
- 普通用户不能新增或编辑设备
- 已登录用户可管理区域
- 设备和区域查询默认按农场边界隔离

## 阶段 3 验收点

- 推理服务可接收图片、视频、视频流与边缘上报四类标准输入
- 推理服务统一返回设备编号、事件时间、行为类型、牛只数量、置信度、模型名称、模型版本和推理来源
- 业务后端可调用推理服务并将结果写入 `behavior_event`
- 平台可在“行为事件”页面手动导入推理结果并查看最新事件
- 首页可展示今日行为事件数与最近行为事件摘要

## 阶段 4 验收点

- 平台支持预设规则与最小自定义规则配置
- 行为事件导入后可自动执行规则判断并生成告警
- 可查看告警列表、告警详情并更新处理状态
- 历史行为与历史告警支持按条件分页查询
- 历史分析页可展示趋势图与占比图

## 常用命令

```powershell
docker compose -f code/infra/docker/docker-compose.yml ps
docker compose -f code/infra/docker/docker-compose.yml logs -f api
docker compose -f code/infra/docker/docker-compose.yml logs -f web
docker compose -f code/infra/docker/docker-compose.yml down
```

## 质量检查

前端：

- `npm run lint`
- `npm run test`
- `npm run build`

后端：

- `python -m pytest`
- `python -m ruff check .`

## Zone-Assisted Behavior Logic

The inference service now uses manually drawn zones as a second-stage behavior refiner.

- Anchor point: each cow uses the bottom-center of its detection box as the location anchor.
- Zone match order:
  1. The anchor is inside the polygon.
  2. If not inside, it is still treated as matched when the distance to the polygon edge is within `ZONE_PROXIMITY_THRESHOLD` (default `0.04`, which is about 4% of the frame size).
- Time accumulation:
  - For videos, the service accumulates dwell time per tracked cow in each zone.
  - For images and realtime snapshots, the service only records the matched zone and does not force a time-based override.
- Refinement rules:
  - Feeding: if a cow stays in a `feeding` zone for at least `8s` and that zone accounts for at least `60%` of the observed track duration, the final behavior becomes `feeding`.
  - Drinking: if a cow stays in a `water` zone for at least `6s` and that zone accounts for at least `60%` of the observed track duration, the final behavior becomes `drinking`.
  - Resting: if a cow stays in a `rest` zone for at least `12s` and that zone accounts for at least `60%` of the observed track duration, the final behavior becomes `resting`.
  - Lying priority: if the model already decides the cow is lying, the result keeps `lying` even when the cow is in the rest zone.
- Output behavior:
  - Events now keep the matched `zone_name`.
  - When a zone rule changes the final behavior, the event notes include a `zone-rule:...` explanation with base behavior, zone, dwell time, and share.

推理服务：

- `python -m pytest`
- `python -m ruff check .`
