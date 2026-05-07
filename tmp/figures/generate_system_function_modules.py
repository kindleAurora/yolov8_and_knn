from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch


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
    ax.text(x + w / 2, y + h - 0.04, title, ha="center", va="top", fontsize=12.5, weight="bold", color="#0f172a")
    for i, line in enumerate(lines):
        ax.text(x + w / 2, y + h - 0.087 - i * 0.038, line, ha="center", va="top", fontsize=9.6, color="#334155")
    return (x + w / 2, y + h / 2)


def main() -> None:
    set_font()
    fig, ax = plt.subplots(figsize=(13.2, 7.2), dpi=260)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    ax.text(0.5, 0.95, "系统功能模块图", ha="center", va="top", fontsize=22, weight="bold", color="#0f172a")

    root_x, root_y, root_w, root_h = 0.33, 0.75, 0.34, 0.12
    root = FancyBboxPatch(
        (root_x, root_y),
        root_w,
        root_h,
        boxstyle="round,pad=0.014,rounding_size=0.02",
        linewidth=1.9,
        edgecolor="#1d4ed8",
        facecolor="#eff6ff",
    )
    ax.add_patch(root)
    ax.text(root_x + root_w / 2, root_y + root_h / 2, "牧场牲畜行为检测系统", ha="center", va="center", fontsize=15, weight="bold", color="#0f172a")

    modules = [
        (0.06, 0.49, "用户登录模块", ["身份验证", "登录状态管理"], "#eef6ff", "#2563eb"),
        (0.31, 0.49, "设备管理模块", ["设备列表维护", "视频流地址与状态"], "#f0fdf4", "#16a34a"),
        (0.56, 0.49, "实时监控模块", ["视频画面展示", "检测框、ID 与行为结果"], "#fff7ed", "#ea580c"),
        (0.06, 0.23, "区域管理模块", ["采食区、饮水区、休息区", "区域规则配置"], "#fdf2f8", "#db2777"),
        (0.31, 0.23, "行为事件与告警模块", ["行为事件记录", "规则告警与状态查看"], "#fef2f2", "#dc2626"),
        (0.56, 0.23, "历史数据分析模块", ["按时间与设备查询", "行为统计与趋势分析"], "#f8fafc", "#475569"),
    ]

    root_center = (root_x + root_w / 2, root_y)
    module_centers = []
    for x, y, title, lines, face, edge in modules:
        center = add_box(ax, x, y, 0.20, 0.15, title, lines, face, edge)
        module_centers.append((center, x, y))

    # Split connector to reduce crossing.
    hub = (0.5, 0.68)
    ax.plot([root_center[0], hub[0]], [root_center[1], hub[1]], color="#475569", linewidth=1.5)
    ax.plot([0.16, 0.66], [hub[1], hub[1]], color="#475569", linewidth=1.5)

    for center, x, y in module_centers:
        top = (center[0], y + 0.15)
        mid_x = center[0]
        ax.plot([mid_x, mid_x], [hub[1], top[1]], color="#475569", linewidth=1.5)

    ax.text(
        0.5,
        0.08,
        "各功能模块围绕用户操作、设备接入、实时检测、区域配置、事件告警和历史分析展开，共同支撑牧场牲畜行为检测与管理。",
        ha="center",
        va="center",
        fontsize=10.5,
        color="#475569",
    )

    png_path = OUT_DIR / "system_function_modules.png"
    svg_path = OUT_DIR / "system_function_modules.svg"
    fig.savefig(png_path, bbox_inches="tight", pad_inches=0.14)
    fig.savefig(svg_path, bbox_inches="tight", pad_inches=0.14)
    print(png_path)
    print(svg_path)


if __name__ == "__main__":
    main()
