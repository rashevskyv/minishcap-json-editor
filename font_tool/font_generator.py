from PIL import Image
import tkinter as tk
import json
import os
import requests
import io
import base64
import numpy as np

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Load from project root (parent directory)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(project_root, '.env')
    load_dotenv(env_path)
except ImportError:
    print("python-dotenv not installed. Using environment variables only.")

# OpenAI API ключ - читається з .env файлу або змінної оточення
OPENAI_API_KEY = os.getenv('FONT_TOOL_OPENAI_API_KEY') or os.getenv('OPENAI_API_KEY', '')

OUTPUT_JSON = "font_map.json"
CHAR_HEIGHT = 16

script_dir = os.path.dirname(os.path.abspath(__file__))

def find_glyphs(img, file_name):
    glyphs = []
    glyph_width, glyph_height = 8, 16
    num_cols, num_rows = img.width // glyph_width, img.height // glyph_height
    for col in range(num_cols):
        for row in range(num_rows):
            start_x, end_x = col * glyph_width, (col + 1) * glyph_width
            start_y, end_y = row * glyph_height, (row + 1) * glyph_height
            glyphs.append({
                "start_x": start_x,
                "end_x": end_x,
                "start_y": start_y,
                "end_y": end_y,
                "width": glyph_width,
                "height": glyph_height,
                "file": file_name
            })
    return glyphs

def crop_black_vertical(img):
    arr = np.array(img.convert("L"))
    mask = arr < 32
    cols = np.where(mask.mean(axis=0) < 0.95)[0]
    if len(cols) == 0:
        return img, 0, img.width
    left, right = int(cols[0]), int(cols[-1]+1)
    cropped = img.crop((left, 0, right, img.height))
    return cropped, left, right

def load_all_glyphs():
    bmp_files = [f for f in os.listdir(script_dir) if f.lower().endswith('.bmp')]
    all_glyphs = []
    for bmp in bmp_files:
        img_path = os.path.join(script_dir, bmp)
        img = Image.open(img_path).convert("RGB")
        glyphs = find_glyphs(img, bmp)
        for glyph in glyphs:
            glyph["img"] = img.crop((glyph["start_x"], glyph["start_y"], glyph["end_x"], glyph["end_y"]))
        all_glyphs.extend(glyphs)
    return all_glyphs

def ocr_glyph(glyph):
    img = glyph["img"]
    cropped, left, right = crop_black_vertical(img)
    glyph["cropped_start_x"] = int(glyph["start_x"] + left)
    glyph["cropped_end_x"] = int(glyph["start_x"] + right)
    buf = io.BytesIO()
    cropped.save(buf, format="PNG")
    buf.seek(0)
    image_b64 = base64.b64encode(buf.getvalue()).decode()
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What is the character in this image? Respond with a single character. якщо символ занімає меньше ніж 60 відсотків зображення по висоті, верогідно символ в нижньому регістрі. А якщо займає весь розмір, то в верхньому"},
                        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + image_b64}}
                    ]
                }
            ],
            "max_tokens": 1
        }
    )
    result = response.json()
    if "choices" not in result:
        return ""
    symbol = result["choices"][0]["message"]["content"].strip()
    return symbol[0] if symbol else ""

def save_glyph_bmp(glyph, char):
    char = char.strip()
    if not char or len(char) != 1:
        return
    temp_dir = "glyphs"
    os.makedirs(temp_dir, exist_ok=True)
    fname = os.path.join(temp_dir, f"glyph_{ord(char):03X}.bmp")
    glyph["img"].save(fname)

def save_json(font_map):
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(font_map, f, ensure_ascii=False, indent=2)

def update_info():
    filled = sum(1 for v in user_inputs if v)
    status2.config(text=f"Заповнено: {filled}/{len(user_inputs)}")

def show_glyph(idx):
    canvas.delete("all")
    glyph = glyphs[idx]
    img_path = os.path.join(script_dir, glyph["file"])
    full_img = Image.open(img_path).convert("RGB")
    scale = 4
    width, height = full_img.width * scale, full_img.height * scale
    from PIL import ImageTk  # Додаємо імпорт тут, якщо не імпортовано на початку файлу
    img_tk = ImageTk.PhotoImage(full_img.resize((width, height), Image.NEAREST))
    canvas.img_tk = img_tk
    canvas.config(width=width, height=height)
    canvas.create_rectangle(0, 0, width, height, fill="#e0e0e0", outline="#a0a0a0")
    canvas.create_image(0, 0, anchor=tk.NW, image=img_tk)
    glyph_width, glyph_height = glyph["width"] * scale, glyph["height"] * scale
    num_cols = full_img.width // glyph["width"]
    num_rows = full_img.height // glyph["height"]
    for col in range(num_cols):
        for row in range(num_rows):
            gidx = col * num_rows + row
            x1, y1 = col * glyph_width, row * glyph_height
            x2, y2 = x1 + glyph_width, y1 + glyph_height
            if gidx >= len(user_inputs):
                continue
            if user_inputs[gidx]:
                canvas.create_rectangle(x1, y1, x2, y2, fill="green", stipple="gray25", outline="")
            elif gidx < current["index"]:
                canvas.create_rectangle(x1, y1, x2, y2, fill="red", stipple="gray25", outline="")
    x1, y1 = glyph["start_x"] * scale, glyph["start_y"] * scale
    x2, y2 = glyph["end_x"] * scale - 1, glyph["end_y"] * scale - 1
    canvas.create_rectangle(x1, y1, x2, y2, outline="red", width=3)
    status.config(text=f"Гліф {idx+1} з {len(glyphs)} ({glyph['file']})")
    entry.delete(0, tk.END)
    if user_inputs[idx]:
        entry.insert(0, user_inputs[idx])
    entry.focus_set()
    update_info()

def save_current_glyph_to_json(idx):
    val = user_inputs[idx]
    if val:
        glyph = glyphs[idx]
        cropped, left, right = crop_black_vertical(glyph["img"])
        glyph["cropped_start_x"] = glyph["start_x"] + left
        glyph["cropped_end_x"] = glyph["start_x"] + right
        font_map[val] = {
            "start_x": int(glyph["cropped_start_x"]),
            "end_x": int(glyph["cropped_end_x"]),
            "start_y": int(glyph["start_y"]),
            "end_y": int(glyph["end_y"]),
            "width": int(glyph["cropped_end_x"] - glyph["cropped_start_x"]),
            "height": int(glyph["height"]),
            "file": glyph["file"]
        }
        save_glyph_bmp(glyph, val)
        save_json(font_map)

def on_entry(event):
    idx = current["index"]
    user_inputs[idx] = entry.get()
    save_current_glyph_to_json(idx)
    update_info()

def on_canvas_click(event):
    scale = 4
    glyph = glyphs[current["index"]]
    glyph_width, glyph_height = glyph["width"] * scale, glyph["height"] * scale
    col, row = event.x // glyph_width, event.y // glyph_height
    img_path = os.path.join(script_dir, glyph["file"])
    full_img = Image.open(img_path).convert("RGB")
    num_cols = full_img.width // glyph["width"]
    num_rows = full_img.height // glyph["height"]
    gidx = col * num_rows + row
    if 0 <= gidx < len(glyphs):
        user_inputs[current["index"]] = entry.get()
        save_current_glyph_to_json(current["index"])
        current["index"] = gidx
        if event.state & 0x0001:
            start, end = min(current["index"], gidx), max(current["index"], gidx)
            for i in range(start, end + 1):
                if not user_inputs[i]:
                    guess = ocr_glyph(glyphs[i])
                    user_inputs[i] = guess
                    save_current_glyph_to_json(i)
            show_glyph(current["index"])
        else:
            show_glyph(current["index"])
    else:
        glyph = glyphs[gidx]
        val = user_inputs[gidx]
        if val in font_map:
            del font_map[val]
        for key in ["cropped_start_x", "cropped_end_x"]:
            if key in glyph:
                del glyph[key]
        user_inputs[gidx] = None
        current["index"] = gidx
        show_glyph(current["index"])

def go_prev(event=None):
    if current["index"] > 0:
        user_inputs[current["index"]] = entry.get()
        save_current_glyph_to_json(current["index"])
        current["index"] -= 1
        show_glyph(current["index"])

def go_next(event=None):
    if current["index"] < len(glyphs) - 1:
        user_inputs[current["index"]] = entry.get()
        save_current_glyph_to_json(current["index"])
        current["index"] += 1
        show_glyph(current["index"])

def go_left(event=None):
    idx = current["index"]
    glyph = glyphs[idx]
    img_path = os.path.join(script_dir, glyph["file"])
    full_img = Image.open(img_path).convert("RGB")
    num_cols = full_img.width // glyph["width"]
    num_rows = full_img.height // glyph["height"]
    col, row = idx // num_rows, idx % num_rows
    if col > 0:
        new_idx = (col - 1) * num_rows + row
        if 0 <= new_idx < len(glyphs):
            user_inputs[idx] = entry.get()
            save_current_glyph_to_json(idx)
            current["index"] = new_idx
            show_glyph(current["index"])

def go_right(event=None):
    idx = current["index"]
    glyph = glyphs[idx]
    img_path = os.path.join(script_dir, glyph["file"])
    full_img = Image.open(img_path).convert("RGB")
    num_cols = full_img.width // glyph["width"]
    num_rows = full_img.height // glyph["height"]
    col, row = idx // num_rows, idx % num_rows
    if col < num_cols - 1:
        new_idx = (col + 1) * num_rows + row
        if 0 <= new_idx < len(glyphs):
            user_inputs[idx] = entry.get()
            save_current_glyph_to_json(idx)
            current["index"] = new_idx
            show_glyph(current["index"])

def go_down(event=None):
    idx = current["index"]
    glyph = glyphs[idx]
    img_path = os.path.join(script_dir, glyph["file"])
    full_img = Image.open(img_path).convert("RGB")
    num_cols = full_img.width // glyph["width"]
    num_rows = full_img.height // glyph["height"]
    col, row = idx // num_rows, idx % num_rows
    if row < num_rows - 1:
        new_idx = col * num_rows + (row + 1)
    else:
        new_idx = idx + 1
    if 0 <= new_idx < len(glyphs):
        user_inputs[idx] = entry.get()
        save_current_glyph_to_json(idx)
        current["index"] = new_idx
        show_glyph(current["index"])

def go_up(event=None):
    idx = current["index"]
    glyph = glyphs[idx]
    img_path = os.path.join(script_dir, glyph["file"])
    full_img = Image.open(img_path).convert("RGB")
    num_cols = full_img.width // glyph["width"]
    num_rows = full_img.height // glyph["height"]
    col, row = idx // num_rows, idx % num_rows
    if row > 0:
        new_idx = col * num_rows + (row - 1)
    else:
        new_idx = idx - 1
    if 0 <= new_idx < len(glyphs):
        user_inputs[idx] = entry.get()
        save_current_glyph_to_json(idx)
        current["index"] = new_idx
        show_glyph(current["index"])

def main():
    global glyphs, font_map, user_inputs, current, canvas, entry, status, status2
    glyphs = load_all_glyphs()
    font_map = {}
    user_inputs = [None] * len(glyphs)
    current = {"index": 0}
    root = tk.Tk()
    root.title("Введіть символ для кожного гліфа")
    label = tk.Label(root, text="Введіть символ, який відповідає зображенню:")
    label.pack()
    canvas = tk.Canvas(root, width=400, height=100)
    canvas.pack()
    canvas.bind("<Button-1>", on_canvas_click)
    entry = tk.Entry(root, font=("Consolas", 24), width=4)
    entry.pack()
    entry.bind("<Return>", on_entry)
    nav_frame = tk.Frame(root)
    nav_frame.pack()
    btn_prev = tk.Button(nav_frame, text="\u25C0 Назад", font=("Arial", 12), command=go_prev, compound=tk.LEFT)
    btn_prev.pack(side=tk.LEFT, padx=5)
    btn_next = tk.Button(nav_frame, text="Вперед \u25B6", font=("Arial", 12), command=go_next, compound=tk.RIGHT)
    btn_next.pack(side=tk.LEFT, padx=5)
    root.bind("<Left>", go_left)
    root.bind("<Right>", go_right)
    root.bind("<Up>", go_up)
    root.bind("<Down>", go_down)
    status = tk.Label(root, text="")
    status.pack()
    status2 = tk.Label(root, text="")
    status2.pack()
    show_glyph(current["index"])
    root.mainloop()

if __name__ == "__main__":
    main()