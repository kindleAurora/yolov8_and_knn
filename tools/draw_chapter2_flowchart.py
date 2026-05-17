from __future__ import annotations

from html import escape
from math import atan2, cos, sin, pi
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "output" / "figures"
PNG_PATH = OUT_DIR / "chapter2_theory_flowchart.png"
SVG_PATH = OUT_DIR / "chapter2_theory_flowchart.svg"

FONT_REGULAR = Path(r"C:\Windows\Fonts\msyh.ttc")
FONT_BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")

SCALE = 2
W, H = 3600, 1800


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size * SCALE)


def c(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


COLORS = {
    "bg": "#F7F9FC",
    "ink": "#1F2937",
    "muted": "#64748B",
    "line": "#CBD5E1",
    "blue": "#2563EB",
    "blue_light": "#EAF1FF",
    "green": "#0F8A5F",
    "green_light": "#E7F6EF",
    "amber": "#D97706",
    "amber_light": "#FFF2D9",
    "violet": "#5B5FC7",
    "violet_light": "#EEF0FF",
    "white": "#FFFFFF",
}


def scaled_box(box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    return tuple(v * SCALE for v in box)


def text_width(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=fnt)
    return bbox[2] - bbox[0]


def wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    fnt: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    lines: list[str] = []
    current = ""
    for ch in text:
        trial = current + ch
        if current and text_width(draw, trial, fnt) > max_width:
            lines.append(current)
            current = ch
        else:
            current = trial
    if current:
        lines.append(current)
    return lines


def center_text(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    fnt: ImageFont.FreeTypeFont,
    fill: str,
    line_gap: int = 10,
) -> None:
    x1, y1, x2, y2 = scaled_box(box)
    max_width = x2 - x1 - 44 * SCALE
    lines = wrap_text(draw, text, fnt, max_width)
    heights = [draw.textbbox((0, 0), line, font=fnt)[3] for line in lines]
    total_h = sum(heights) + (len(lines) - 1) * line_gap * SCALE
    y = y1 + (y2 - y1 - total_h) // 2
    for line, h in zip(lines, heights):
        w = text_width(draw, line, fnt)
        draw.text((x1 + (x2 - x1 - w) // 2, y), line, font=fnt, fill=c(fill))
        y += h + line_gap * SCALE


def left_text(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    fnt: ImageFont.FreeTypeFont,
    fill: str,
    max_width: int,
    line_gap: int = 9,
) -> int:
    sx, sy = x * SCALE, y * SCALE
    lines = wrap_text(draw, text, fnt, max_width * SCALE)
    for line in lines:
        draw.text((sx, sy), line, font=fnt, fill=c(fill))
        bbox = draw.textbbox((0, 0), line, font=fnt)
        sy += (bbox[3] - bbox[1]) + line_gap * SCALE
    return sy // SCALE


def rounded_rect(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    fill: str,
    outline: str | None = None,
    radius: int = 26,
    width: int = 2,
) -> None:
    draw.rounded_rectangle(
        scaled_box(box),
        radius=radius * SCALE,
        fill=c(fill),
        outline=c(outline) if outline else None,
        width=width * SCALE,
    )


def arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    color: str,
    width: int = 8,
    head: int = 24,
) -> None:
    x1, y1 = start[0] * SCALE, start[1] * SCALE
    x2, y2 = end[0] * SCALE, end[1] * SCALE
    draw.line((x1, y1, x2, y2), fill=c(color), width=width * SCALE)
    angle = atan2(y2 - y1, x2 - x1)
    h = head * SCALE
    p1 = (x2, y2)
    p2 = (x2 - h * cos(angle - pi / 6), y2 - h * sin(angle - pi / 6))
    p3 = (x2 - h * cos(angle + pi / 6), y2 - h * sin(angle + pi / 6))
    draw.polygon([p1, p2, p3], fill=c(color))


def draw_column(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    w: int,
    h: int,
    title: str,
    summary: str,
    steps: list[tuple[str, str]],
    accent: str,
    light: str,
) -> None:
    rounded_rect(draw, (x, y, x + w, y + h), COLORS["white"], COLORS["line"], 30, 3)
    rounded_rect(draw, (x, y, x + w, y + 118), light, None, 30, 0)
    draw.rounded_rectangle(
        scaled_box((x, y + 74, x + w, y + 136)),
        radius=0,
        fill=c(light),
    )
    draw.text((x * SCALE + 40 * SCALE, y * SCALE + 30 * SCALE), title, font=font(33, True), fill=c(accent))
    left_text(draw, x + 40, y + 85, summary, font(20), COLORS["muted"], w - 80, 7)

    step_y = y + 180
    step_h = 132
    gap = 22
    for idx, (head, body) in enumerate(steps, start=1):
        rounded_rect(
            draw,
            (x + 42, step_y, x + w - 42, step_y + step_h),
            "#FFFFFF",
            "#D6DEE9",
            18,
            2,
        )
        badge = (x + 66, step_y + 32, x + 118, step_y + 84)
        rounded_rect(draw, badge, accent, None, 16, 0)
        center_text(draw, badge, str(idx), font(21, True), "#FFFFFF", 0)
        draw.text(
            ((x + 142) * SCALE, (step_y + 22) * SCALE),
            head,
            font=font(24, True),
            fill=c(COLORS["ink"]),
        )
        left_text(draw, x + 142, step_y + 63, body, font(19), COLORS["muted"], w - 205, 7)
        if idx < len(steps):
            arrow(
                draw,
                (x + w // 2, step_y + step_h + 4),
                (x + w // 2, step_y + step_h + gap - 2),
                "#94A3B8",
                width=5,
                head=14,
            )
        step_y += step_h + gap


def build_png() -> None:
    image = Image.new("RGB", (W * SCALE, H * SCALE), c(COLORS["bg"]))
    draw = ImageDraw.Draw(image)

    # Subtle grid background.
    for x in range(0, W * SCALE, 80 * SCALE):
        draw.line((x, 0, x, H * SCALE), fill=c("#EEF2F7"), width=1)
    for y in range(0, H * SCALE, 80 * SCALE):
        draw.line((0, y, W * SCALE, y), fill=c("#EEF2F7"), width=1)

    title = "第二章理论基础流程图"
    subtitle = "YOLOv8 目标检测、DeepSORT 多目标跟踪与 KNN 行为分类的处理链"
    tw = text_width(draw, title, font(58, True))
    draw.text(((W * SCALE - tw) // 2, 70 * SCALE), title, font=font(58, True), fill=c(COLORS["ink"]))
    sw = text_width(draw, subtitle, font(27))
    draw.text(((W * SCALE - sw) // 2, 150 * SCALE), subtitle, font=font(27), fill=c(COLORS["muted"]))

    input_box = (105, 480, 475, 690)
    rounded_rect(draw, input_box, COLORS["violet_light"], COLORS["violet"], 30, 3)
    center_text(draw, input_box, "牧场视频 / 图像输入", font(30, True), COLORS["violet"])
    center_text(draw, (125, 620, 455, 675), "连续帧或单帧图像", font(20), COLORS["muted"])

    x1, x2, x3 = 555, 1385, 2215
    y, cw, ch = 315, 730, 1080
    draw_column(
        draw,
        x1,
        y,
        cw,
        ch,
        "YOLOv8 目标检测",
        "解决单帧图像中的牛只定位与识别问题。",
        [
            ("图像预处理", "尺寸调整、归一化后送入神经网络。"),
            ("Backbone 特征提取", "提取颜色、纹理、边缘、形状和语义特征。"),
            ("Neck 多尺度融合", "融合浅层细节与深层语义，增强大小目标检测能力。"),
            ("Head 解耦预测", "分类分支预测类别，回归分支定位边界框。"),
            ("Anchor-Free + NMS", "直接预测目标中心与边界框，删除重复检测框。"),
        ],
        COLORS["blue"],
        COLORS["blue_light"],
    )
    draw_column(
        draw,
        x2,
        y,
        cw,
        ch,
        "DeepSORT 目标跟踪",
        "在连续帧间建立身份关联，保持牛只 ID 一致。",
        [
            ("检测结果输入", "接收每帧牛只检测框、类别和置信度。"),
            ("卡尔曼滤波预测", "根据已有轨迹状态预测当前帧目标位置。"),
            ("外观特征提取", "对检测框区域提取特征向量，描述目标外观。"),
            ("数据关联计算", "综合运动距离与外观距离构建匹配代价。"),
            ("匈牙利匹配与轨迹管理", "完成最优分配，更新、新建或删除轨迹。"),
        ],
        COLORS["green"],
        COLORS["green_light"],
    )
    draw_column(
        draw,
        x3,
        y,
        cw,
        ch,
        "KNN 行为分类",
        "依据样本特征相似性完成牛只基础行为判别。",
        [
            ("样本特征表示", "使用 HOG 梯度方向特征与检测框长宽比特征。"),
            ("距离度量", "计算待分类样本与训练样本的欧氏距离。"),
            ("K 近邻选择", "选取距离最近的 K 个训练样本。"),
            ("普通多数投票", "根据邻近样本类别票数确定预测类别。"),
            ("K 值实验确定", "在偏差与方差之间平衡分类稳定性和局部能力。"),
        ],
        COLORS["amber"],
        COLORS["amber_light"],
    )

    arrow(draw, (475, 585), (540, 585), COLORS["violet"], 9, 28)
    arrow(draw, (1285, 585), (1368, 585), COLORS["blue"], 9, 28)
    arrow(draw, (2115, 585), (2198, 585), COLORS["green"], 9, 28)

    out_box = (3045, 480, 3495, 755)
    rounded_rect(draw, out_box, "#FFFFFF", COLORS["line"], 30, 3)
    draw.text((3085 * SCALE, 525 * SCALE), "理论输出", font=font(32, True), fill=c(COLORS["ink"]))
    y_text = left_text(draw, 3085, 590, "牛只检测框、类别、置信度", font(20), COLORS["muted"], 360, 7)
    y_text = left_text(draw, 3085, y_text + 8, "牛只身份 ID 与运动轨迹", font(20), COLORS["muted"], 360, 7)
    left_text(draw, 3085, y_text + 8, "基础行为分类结果", font(20), COLORS["muted"], 360, 7)
    arrow(draw, (2945, 585), (3030, 585), COLORS["amber"], 9, 28)

    bottom = (410, 1470, 3190, 1660)
    rounded_rect(draw, bottom, "#FFFFFF", COLORS["line"], 28, 3)
    draw.text((460 * SCALE, 1510 * SCALE), "章节逻辑关系", font=font(28, True), fill=c(COLORS["ink"]))
    left_text(
        draw,
        460,
        1560,
        "目标检测提供单帧位置与类别；目标跟踪在时间维度维护同一牛只的轨迹；KNN 利用特征空间近邻投票完成行为判别。三者共同构成第三章融合检测与行为监测方法的理论基础。",
        font(23),
        COLORS["muted"],
        2680,
        10,
    )

    image = image.resize((W, H), Image.Resampling.LANCZOS)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    image.save(PNG_PATH, dpi=(300, 300))


def svg_text_lines(text: str, x: int, y: int, max_chars: int, size: int, color: str) -> str:
    lines: list[str] = []
    current = ""
    for ch in text:
        if len(current) >= max_chars:
            lines.append(current)
            current = ch
        else:
            current += ch
    if current:
        lines.append(current)
    parts = []
    for i, line in enumerate(lines):
        dy = 0 if i == 0 else size + 7
        parts.append(
            f'<text x="{x}" y="{y + i * (size + 7)}" font-size="{size}" fill="{color}">{escape(line)}</text>'
        )
    return "\n".join(parts)


def build_svg() -> None:
    columns = [
        (
            555,
            COLORS["blue"],
            COLORS["blue_light"],
            "YOLOv8 目标检测",
            [
                ("图像预处理", "尺寸调整、归一化后送入神经网络。"),
                ("Backbone 特征提取", "提取颜色、纹理、边缘、形状和语义特征。"),
                ("Neck 多尺度融合", "融合浅层细节与深层语义，增强大小目标检测能力。"),
                ("Head 解耦预测", "分类分支预测类别，回归分支定位边界框。"),
                ("Anchor-Free + NMS", "直接预测目标中心与边界框，删除重复检测框。"),
            ],
        ),
        (
            1385,
            COLORS["green"],
            COLORS["green_light"],
            "DeepSORT 目标跟踪",
            [
                ("检测结果输入", "接收每帧牛只检测框、类别和置信度。"),
                ("卡尔曼滤波预测", "根据已有轨迹状态预测当前帧目标位置。"),
                ("外观特征提取", "对检测框区域提取特征向量，描述目标外观。"),
                ("数据关联计算", "综合运动距离与外观距离构建匹配代价。"),
                ("匈牙利匹配与轨迹管理", "完成最优分配，更新、新建或删除轨迹。"),
            ],
        ),
        (
            2215,
            COLORS["amber"],
            COLORS["amber_light"],
            "KNN 行为分类",
            [
                ("样本特征表示", "使用 HOG 梯度方向特征与检测框长宽比特征。"),
                ("距离度量", "计算待分类样本与训练样本的欧氏距离。"),
                ("K 近邻选择", "选取距离最近的 K 个训练样本。"),
                ("普通多数投票", "根据邻近样本类别票数确定预测类别。"),
                ("K 值实验确定", "平衡分类稳定性和局部分类能力。"),
            ],
        ),
    ]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        f'<rect width="{W}" height="{H}" fill="{COLORS["bg"]}"/>',
        '<defs><marker id="arrow" markerWidth="14" markerHeight="14" refX="12" refY="7" orient="auto"><path d="M0,0 L14,7 L0,14 z" fill="#64748B"/></marker></defs>',
        f'<text x="{W//2}" y="125" text-anchor="middle" font-family="Microsoft YaHei, SimSun, sans-serif" font-size="58" font-weight="700" fill="{COLORS["ink"]}">第二章理论基础流程图</text>',
        f'<text x="{W//2}" y="185" text-anchor="middle" font-family="Microsoft YaHei, SimSun, sans-serif" font-size="27" fill="{COLORS["muted"]}">YOLOv8 目标检测、DeepSORT 多目标跟踪与 KNN 行为分类的处理链</text>',
        f'<rect x="105" y="480" width="370" height="210" rx="30" fill="{COLORS["violet_light"]}" stroke="{COLORS["violet"]}" stroke-width="3"/>',
        f'<text x="290" y="575" text-anchor="middle" font-family="Microsoft YaHei, SimSun, sans-serif" font-size="30" font-weight="700" fill="{COLORS["violet"]}">牧场视频 / 图像输入</text>',
        f'<text x="290" y="640" text-anchor="middle" font-family="Microsoft YaHei, SimSun, sans-serif" font-size="20" fill="{COLORS["muted"]}">连续帧或单帧图像</text>',
        '<line x1="475" y1="585" x2="540" y2="585" stroke="#64748B" stroke-width="8" marker-end="url(#arrow)"/>',
    ]
    for x, accent, light, title, steps in columns:
        parts.append(f'<rect x="{x}" y="315" width="730" height="1080" rx="30" fill="#fff" stroke="{COLORS["line"]}" stroke-width="3"/>')
        parts.append(f'<rect x="{x}" y="315" width="730" height="136" rx="30" fill="{light}"/>')
        parts.append(f'<text x="{x+40}" y="370" font-family="Microsoft YaHei, SimSun, sans-serif" font-size="33" font-weight="700" fill="{accent}">{escape(title)}</text>')
        step_y = 495
        for idx, (head, body) in enumerate(steps, start=1):
            parts.append(f'<rect x="{x+42}" y="{step_y}" width="646" height="132" rx="18" fill="#fff" stroke="#D6DEE9" stroke-width="2"/>')
            parts.append(f'<rect x="{x+66}" y="{step_y+32}" width="52" height="52" rx="16" fill="{accent}"/>')
            parts.append(f'<text x="{x+92}" y="{step_y+67}" text-anchor="middle" font-family="Microsoft YaHei, SimSun, sans-serif" font-size="21" font-weight="700" fill="#fff">{idx}</text>')
            parts.append(f'<text x="{x+142}" y="{step_y+55}" font-family="Microsoft YaHei, SimSun, sans-serif" font-size="24" font-weight="700" fill="{COLORS["ink"]}">{escape(head)}</text>')
            parts.append(svg_text_lines(body, x + 142, step_y + 93, 24, 19, COLORS["muted"]))
            if idx < len(steps):
                parts.append(f'<line x1="{x+365}" y1="{step_y+136}" x2="{x+365}" y2="{step_y+150}" stroke="#94A3B8" stroke-width="5" marker-end="url(#arrow)"/>')
            step_y += 154
    parts.extend(
        [
            '<line x1="1285" y1="585" x2="1368" y2="585" stroke="#64748B" stroke-width="8" marker-end="url(#arrow)"/>',
            '<line x1="2115" y1="585" x2="2198" y2="585" stroke="#64748B" stroke-width="8" marker-end="url(#arrow)"/>',
            '<line x1="2945" y1="585" x2="3030" y2="585" stroke="#64748B" stroke-width="8" marker-end="url(#arrow)"/>',
            f'<rect x="3045" y="480" width="450" height="275" rx="30" fill="#fff" stroke="{COLORS["line"]}" stroke-width="3"/>',
            f'<text x="3085" y="560" font-family="Microsoft YaHei, SimSun, sans-serif" font-size="32" font-weight="700" fill="{COLORS["ink"]}">理论输出</text>',
            f'<text x="3085" y="625" font-family="Microsoft YaHei, SimSun, sans-serif" font-size="20" fill="{COLORS["muted"]}">牛只检测框、类别、置信度</text>',
            f'<text x="3085" y="675" font-family="Microsoft YaHei, SimSun, sans-serif" font-size="20" fill="{COLORS["muted"]}">牛只身份 ID 与运动轨迹</text>',
            f'<text x="3085" y="725" font-family="Microsoft YaHei, SimSun, sans-serif" font-size="20" fill="{COLORS["muted"]}">基础行为分类结果</text>',
            f'<rect x="410" y="1470" width="2780" height="190" rx="28" fill="#fff" stroke="{COLORS["line"]}" stroke-width="3"/>',
            f'<text x="460" y="1535" font-family="Microsoft YaHei, SimSun, sans-serif" font-size="28" font-weight="700" fill="{COLORS["ink"]}">章节逻辑关系</text>',
            svg_text_lines(
                "目标检测提供单帧位置与类别；目标跟踪在时间维度维护同一牛只的轨迹；KNN 利用特征空间近邻投票完成行为判别。三者共同构成第三章融合检测与行为监测方法的理论基础。",
                460,
                1590,
                72,
                23,
                COLORS["muted"],
            ),
            "</svg>",
        ]
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SVG_PATH.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    build_png()
    build_svg()
    print(PNG_PATH)
    print(SVG_PATH)


if __name__ == "__main__":
    main()
