"""Replace English text with Chinese on figure images using PIL."""
from PIL import Image, ImageDraw, ImageFont
import os

# Find the Droid Sans Fallback font file
import matplotlib.font_manager as fm
font_path = None
for f in fm.fontManager.ttflist:
    if f.name == 'Droid Sans Fallback':
        font_path = f.fname
        break

if not font_path:
    raise RuntimeError("Droid Sans Fallback font not found")

print(f"Using font: {font_path}")

def replace_text_on_image(input_path, output_path, replacements):
    """
    replacements: list of dicts with keys:
        'region': (x1, y1, x2, y2) - region to white out
        'text': str - new text to draw
        'position': (x, y) - position to draw text
        'font_size': int
        'color': str or tuple
        'anchor': str (optional, PIL anchor)
    """
    img = Image.open(input_path)
    draw = ImageDraw.Draw(img)

    for r in replacements:
        # White out old text region
        draw.rectangle(r['region'], fill='white')

        # Draw new text
        font = ImageFont.truetype(font_path, r['font_size'])
        kwargs = {
            'xy': r['position'],
            'text': r['text'],
            'fill': r.get('color', 'black'),
            'font': font,
        }
        if 'anchor' in r:
            kwargs['anchor'] = r['anchor']
        draw.text(**kwargs)

    img.save(output_path, quality=95)
    print(f"Saved: {output_path}")


# ---- Figure 4-5: case_sax_better.jpg ----
img1 = Image.open("files/Img/case_sax_better.jpg")
w1, h1 = img1.size
print(f"case_sax_better.jpg size: {w1}x{h1}")
img1.close()

replace_text_on_image(
    "files/Img/case_sax_better.jpg",
    "files/Img/case_sax_better_cn.jpg",
    [
        # Title: "Metric Comparison: cpu_usage\nTarget Node: red line"
        {
            'region': (0, 0, w1, 62),
            'text': '指标对比：cpu_usage\n目标节点：红色曲线',
            'position': (w1 // 2, 8),
            'font_size': 18,
            'color': 'black',
            'anchor': 'ma',
        },
        # Y-axis label: "Value"
        {
            'region': (0, h1 // 2 - 30, 28, h1 // 2 + 30),
            'text': '数\n值',
            'position': (14, h1 // 2),
            'font_size': 16,
            'color': 'black',
            'anchor': 'mm',
        },
        # X-axis label: "Timestamp"
        {
            'region': (w1 // 2 - 60, h1 - 28, w1 // 2 + 60, h1),
            'text': '时间戳',
            'position': (w1 // 2, h1 - 14),
            'font_size': 16,
            'color': 'black',
            'anchor': 'mm',
        },
        # Legend: "Target Node" -> "目标节点", "other nodes" -> "其他节点"
        {
            'region': (690, 45, 808, 62),
            'text': '目标节点',
            'position': (692, 47),
            'font_size': 12,
            'color': 'red',
        },
        {
            'region': (838, 45, 940, 62),
            'text': '      ',
            'position': (838, 47),
            'font_size': 12,
            'color': 'black',
        },
        {
            'region': (920, 87, 1020, 104),
            'text': '其他494节点',
            'position': (922, 89),
            'font_size': 12,
            'color': 'gray',
        },
    ]
)


# ---- Figure 4-6: case_euc_better.jpg ----
img2 = Image.open("files/Img/case_euc_better.jpg")
w2, h2 = img2.size
print(f"case_euc_better.jpg size: {w2}x{h2}")
img2.close()

replace_text_on_image(
    "files/Img/case_euc_better.jpg",
    "files/Img/case_euc_better_cn.jpg",
    [
        # Title
        {
            'region': (0, 0, w2, 62),
            'text': '指标对比：nvlink_tx_bytes\n目标节点：红色曲线',
            'position': (w2 // 2, 8),
            'font_size': 18,
            'color': 'black',
            'anchor': 'ma',
        },
        # Y-axis label
        {
            'region': (0, h2 // 2 - 30, 28, h2 // 2 + 30),
            'text': '数\n值',
            'position': (14, h2 // 2),
            'font_size': 16,
            'color': 'black',
            'anchor': 'mm',
        },
        # X-axis label
        {
            'region': (w2 // 2 - 60, h2 - 28, w2 // 2 + 60, h2),
            'text': '时间戳',
            'position': (w2 // 2, h2 - 14),
            'font_size': 16,
            'color': 'black',
            'anchor': 'mm',
        },
        # Legend
        {
            'region': (690, 45, 808, 62),
            'text': '目标节点',
            'position': (692, 47),
            'font_size': 12,
            'color': 'red',
        },
        {
            'region': (838, 45, 940, 62),
            'text': '      ',
            'position': (838, 47),
            'font_size': 12,
            'color': 'black',
        },
        {
            'region': (920, 87, 1020, 104),
            'text': '其他543节点',
            'position': (922, 89),
            'font_size': 12,
            'color': 'gray',
        },
    ]
)

print("Done!")
