from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "output" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def set_font() -> None:
    for font_path in [
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path(r"C:\Windows\Fonts\simsun.ttc"),
    ]:
        if font_path.exists():
            fm.fontManager.addfont(str(font_path))
            plt.rcParams["font.family"] = fm.FontProperties(fname=str(font_path)).get_name()
            break
    plt.rcParams["axes.unicode_minus"] = False


def add_box(ax, x, y, w, h, title, lines, face, edge):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.012,rounding_size=0.018",
        linewidth=1.7,
        edgecolor=edge,
        facecolor=face,
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h - 0.045, title, ha="center", va="top", fontsize=12.5, weight="bold", color="#0f172a")
    for i, line in enumerate(lines):
        ax.text(x + w / 2, y + h - 0.092 - i * 0.038, line, ha="center", va="top", fontsize=9.8, color="#334155")


def add_arrow(ax, start, end, rad=0):
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=13,
            linewidth=1.5,
            color="#475569",
            connectionstyle=f"arc3,rad={rad}",
        )
    )


def main() -> None:
    set_font()
    fig, ax = plt.subplots(figsize=(14.5, 8.0), dpi=260)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    ax.text(0.5, 0.955, "智慧牧场监控系统总体架构", ha="center", va="top", fontsize=22, weight="bold", color="#0f172a")

    add_box(ax, 0.05, 0.68, 0.17, 0.16, "用户浏览器", ["登录访问", "查看监控结果"], "#eef6ff", "#2563eb")
    add_box(ax, 0.31, 0.65, 0.24, 0.20, "Web 前端", ["Vue / Vite", "设备、区域、监控", "告警、事件、历史分析"], "#eff6ff", "#1d4ed8")
    add_box(ax, 0.31, 0.38, 0.24, 0.20, "后端 API 服务", ["FastAPI", "认证、设备、区域、规则", "事件、告警、历史数据"], "#f0fdf4", "#16a34a")
    add_box(ax, 0.66, 0.37, 0.28, 0.23, "推理服务", ["YOLOv8 检测与计数", "DeepSORT 目标跟踪", "KNN 行为分类", "动量修正、区域语义细分"], "#fff7ed", "#ea580c")
    add_box(ax, 0.66, 0.70, 0.28, 0.15, "视频流服务", ["MediaMTX", "RTSP / HLS 视频流"], "#fdf2f8", "#db2777")

    add_box(ax, 0.66, 0.16, 0.28, 0.14, "牧场视频源", ["监控视频 / 数据集视频", "FFmpeg 循环推流"], "#faf5ff", "#9333ea")
    add_box(ax, 0.29, 0.14, 0.20, 0.16, "PostgreSQL", ["用户、设备、区域", "事件、告警、历史统计"], "#f8fafc", "#475569")
    add_box(ax, 0.52, 0.14, 0.17, 0.16, "Redis", ["缓存", "任务与运行状态"], "#fef2f2", "#dc2626")
    add_box(ax, 0.05, 0.16, 0.17, 0.14, "模型与配置", ["YOLO 权重", "KNN 模型、阈值"], "#fefce8", "#ca8a04")

    # Main data flow
    add_arrow(ax, (0.22, 0.755), (0.31, 0.755))
    add_arrow(ax, (0.43, 0.65), (0.43, 0.58))
    add_arrow(ax, (0.55, 0.49), (0.66, 0.49))
    add_arrow(ax, (0.66, 0.45), (0.55, 0.45))
    add_arrow(ax, (0.40, 0.38), (0.40, 0.30))
    add_arrow(ax, (0.53, 0.38), (0.59, 0.30))
    add_arrow(ax, (0.74, 0.37), (0.74, 0.30))
    add_arrow(ax, (0.15, 0.30), (0.66, 0.48), rad=-0.08)
    add_arrow(ax, (0.80, 0.30), (0.80, 0.70))
    add_arrow(ax, (0.80, 0.70), (0.80, 0.60))
    add_arrow(ax, (0.66, 0.76), (0.55, 0.76))

    # Short arrow notes, placed away from arrows.
    notes = [
        (0.265, 0.775, "访问"),
        (0.455, 0.615, "REST API"),
        (0.605, 0.515, "推理请求"),
        (0.605, 0.425, "识别结果"),
        (0.37, 0.345, "业务数据"),
        (0.69, 0.655, "视频帧"),
        (0.60, 0.77, "HLS 预览"),
        (0.55, 0.34, "缓存状态"),
        (0.31, 0.53, "页面数据"),
        (0.35, 0.42, "加载模型"),
        (0.835, 0.50, "推流"),
    ]
    for x, y, text in notes:
        ax.text(x, y, text, ha="center", va="center", fontsize=9.2, color="#475569", bbox=dict(facecolor="white", edgecolor="none", alpha=0.9, pad=1.2))

    ax.text(
        0.5,
        0.055,
        "前端负责页面展示与交互；后端负责业务接口和数据管理；推理服务完成检测、跟踪与行为识别；视频流、数据库和缓存为系统运行提供支撑。",
        ha="center",
        va="center",
        fontsize=10.5,
        color="#475569",
    )

    png_path = OUT_DIR / "system_overall_architecture.png"
    svg_path = OUT_DIR / "system_overall_architecture.svg"
    fig.savefig(png_path, bbox_inches="tight", pad_inches=0.14)
    fig.savefig(svg_path, bbox_inches="tight", pad_inches=0.14)
    print(png_path)
    print(svg_path)


if __name__ == "__main__":
    main()
