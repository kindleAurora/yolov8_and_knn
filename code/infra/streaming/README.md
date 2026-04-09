# MP4 Loop Streaming

这个目录提供了一条完整的本地演示链路：

- `all_datasets/videos/*.mp4` 按文件名数字顺序拼接
- `FFmpeg` 持续循环推送到 `MediaMTX`
- `MediaMTX` 同时暴露 `RTSP` 和浏览器可播放的 `HLS`
- `code/web` 里的监控主画面优先播放 `HLS`，后端和推理仍可继续使用 `RTSP`

## 默认地址

- RTSP 发布/读取地址：`rtsp://localhost:8554/cow-monitor/demo`
- HLS 播放地址：`http://localhost:8888/cow-monitor/demo/index.m3u8`

## 启动流媒体服务

在项目根目录执行：

```powershell
docker compose -f code/infra/docker/docker-compose.yml up -d mediamtx video-loop-publisher
```

如果要连同整套平台一起启动：

```powershell
docker compose -f code/infra/docker/docker-compose.yml up -d --build
```

## Web 端接入方式

1. 在“设备管理”里新增或编辑一个设备。
2. 将 `stream_url` 填成 `rtsp://localhost:8554/cow-monitor/demo`。
3. 将设备状态设为“在线”，并保持启用。
4. 打开监控页面，主画面会自动尝试播放对应的 HLS 地址。

如果某个设备的浏览器播放地址不是按 RTSP 路径自动映射的，可以在设备扩展配置 JSON 中显式写：

```json
{
  "browser_stream_url": "http://localhost:8888/cow-monitor/demo/index.m3u8"
}
```

## 当前数据目录说明

脚本会扫描 `C:\Users\Admin\Desktop\毕设\all_datasets\videos` 下所有 `*.mp4` 文件并按数字顺序排序。

当前目录里实际识别到 `687` 个 MP4 文件，编号范围是 `1.mp4` 到 `689.mp4`，其中缺少：

- `236.mp4`
- `309.mp4`

如果你后续补齐这两个文件，重启 `video-loop-publisher` 即可自动纳入循环播放。
