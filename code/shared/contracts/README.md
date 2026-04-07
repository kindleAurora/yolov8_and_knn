# Shared Contracts

该目录用于沉淀前端、业务后端、推理服务与边缘设备之间的共享契约。

阶段 1 当前提供的是“接口草案”，目的是先稳定字段命名和数据边界，避免后续阶段边开发边改结构。

已提供契约：

- `inference-request.schema.json`：业务后端或任务调度方向推理服务发送的标准请求
- `inference-response.schema.json`：推理服务回传的结构化结果
- `edge-heartbeat.schema.json`：边缘设备心跳上报草案
- `edge-report.schema.json`：边缘设备识别结果上报草案

后续约定：

- 时间统一使用 ISO 8601
- 设备标识优先使用 `device_code`
- 结构化附加字段统一落到 `metadata` / `payload`
- 算法替换不应影响顶层契约
