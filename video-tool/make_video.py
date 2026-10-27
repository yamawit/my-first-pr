"""台本データ（episodes/*.json）から縦型ショート動画を作る。

使い方:
    python make_video.py episodes/01-tokyo.json

必要なもの: VOICEVOX（起動しておく）、ffmpeg、Pillow
背景: bg/<id>/ に Earth Studio の連番画像か mp4 を置くと、それを使う。無ければ仮の背景。
"""
import json
import random
import re
import subprocess
import sys
import wave
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
GAP = 0.25  # セリフ間の無音（秒）
VOICEVOX = "http://127.0.0.1:50021"
FONT = "C:/Windows/Fonts/YuGothB.ttc"
ROOT = Path(__file__).parent


def font(size):
    return ImageFont.truetype(FONT, size)


# ---------- 音声 ----------

def synthesize(text, speaker, speed, path):
    q = requests.post(f"{VOICEVOX}/audio_query", params={"text": text, "speaker": speaker}, timeout=30)
    q.raise_for_status()
    query = q.json()
    query["speedScale"] = speed
    query["prePhonemeLength"] = 0.05
    query["postPhonemeLength"] = 0.1
    r = requests.post(f"{VOICEVOX}/synthesis", params={"speaker": speaker}, json=query, timeout=60)
    r.raise_for_status()
    path.write_bytes(r.content)
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def join_wavs(paths, out):
    with wave.open(str(paths[0])) as first:
        params = first.getparams()
    silence = b"\x00" * int(params.framerate * GAP) * params.sampwidth * params.nchannels
    with wave.open(str(out), "wb") as dst:
        dst.setparams(params)
        for p in paths:
            with wave.open(str(p)) as src:
                dst.writeframes(src.readframes(src.getnframes()))
            dst.writeframes(silence)


# ---------- 画像 ----------

def fit_size(lines, max_w, start):
    size = start
    while size > 40:
        f = font(size)
        if all(f.getlength(line) <= max_w for line in lines):
            return size
        size -= 4
    return size


def draw_centered(draw, lines, size, center_y, fill, stroke, stroke_w):
    f = font(size)
    line_h = int(size * 1.25)
    top = center_y - line_h * len(lines) // 2
    for i, line in enumerate(lines):
        draw.text((W // 2, top + i * line_h + line_h // 2), line, font=f, fill=fill,
                  anchor="mm", stroke_width=stroke_w, stroke_fill=stroke)


def telop_image(seg, path):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    lines = seg["telop"].split("\n")
    price = seg.get("style") == "price"
    size = fit_size(lines, W - 100, 190 if price else 130)
    box_h = int(size * 1.25) * len(lines) + 80
    cy = H // 2
    d.rounded_rectangle((30, cy - box_h // 2, W - 30, cy + box_h // 2), radius=40, fill=(0, 0, 0, 150))
    if price:
        draw_centered(d, lines, size, cy, (255, 225, 40), (200, 20, 30), 12)
    else:
        draw_centered(d, lines, size, cy, (255, 255, 255), (0, 0, 0), 10)
    if seg.get("note"):
        nf = font(fit_size([seg["note"]], W - 120, 52))
        d.text((W // 2, cy + box_h // 2 + 60), seg["note"], font=nf, fill=(255, 255, 255),
               anchor="mm", stroke_width=6, stroke_fill=(0, 0, 0))
    img.save(path)


def frame_image(ep, path, placeholder):
    """ずっと表示する枠：上のタイトルと下のクレジット。"""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, 250), fill=(200, 20, 30, 230))
    d.text((W // 2, 85), "47都道府県 一番高いタワマン", font=font(64), fill="white", anchor="mm")
    d.text((W // 2, 180), f"#{ep['number']:02d} {ep['prefecture']}", font=font(80), fill=(255, 225, 40),
           anchor="mm", stroke_width=6, stroke_fill=(120, 0, 10))
    if placeholder:
        d.text((W // 2, 300), "（仮の背景：ここに Google Earth Studio の空撮映像が入ります）", font=font(30),
               fill=(220, 220, 235), anchor="mm", stroke_width=3, stroke_fill="black")
    # 下端 140px は Earth Studio のクレジット表示用に空けておく
    credit = "VOICEVOX:ずんだもん　価格：掲載価格（2026年10月確認）"
    d.text((W // 2, H - 190), credit, font=font(34), fill="white", anchor="mm",
           stroke_width=4, stroke_fill="black")
    img.save(path)


def placeholder_bg(path):
    """空撮映像が無いときの仮背景：夜空のグラデーションとビル群のシルエット。"""
    bw, bh = W, int(H * 1.25)
    img = Image.new("RGB", (bw, bh))
    d = ImageDraw.Draw(img)
    for y in range(bh):
        t = y / bh
        d.line((0, y, bw, y), fill=(int(20 + 60 * t), int(25 + 30 * t), int(70 + 60 * t)))
    rnd = random.Random(1)
    x = 0
    while x < bw:
        w = rnd.randint(60, 150)
        h = rnd.randint(300, 900)
        d.rectangle((x, bh - h, x + w, bh), fill=(15, 18, 35))
        for wy in range(bh - h + 30, bh, 45):
            for wx in range(x + 12, x + w - 12, 28):
                if rnd.random() < 0.35:
                    d.rectangle((wx, wy, wx + 10, wy + 16), fill=(255, 210, 120))
        x += w + rnd.randint(5, 25)
    tower_x = bw // 2 - 70
    d.rectangle((tower_x, bh - 1500, tower_x + 140, bh), fill=(25, 30, 55))
    img.save(path)


# ---------- 背景の入力 ----------

def background_args(ep, work, duration):
    bg_dir = ROOT / "bg" / ep["id"]
    if bg_dir.is_dir():
        videos = sorted(bg_dir.glob("*.mp4"))
        if videos:
            return ["-stream_loop", "-1", "-i", str(videos[0])], \
                f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1"
        frames = sorted(p for p in bg_dir.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
        if frames:
            m = re.match(r"(.*?)(\d+)(\.\w+)$", frames[0].name)
            pattern = f"{m.group(1)}%0{len(m.group(2))}d{m.group(3)}"
            return ["-framerate", str(FPS), "-start_number", str(int(m.group(2))),
                    "-stream_loop", "-1", "-i", str(bg_dir / pattern)], \
                f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1"
    bg = work / "placeholder.png"
    placeholder_bg(bg)
    pan = int(H * 0.25)
    return ["-loop", "1", "-framerate", str(FPS), "-i", str(bg)], \
        f"crop={W}:{H}:0:'{pan}-{pan}*t/{duration:.2f}',setsar=1"


# ---------- 本体 ----------

def main(episode_path):
    ep = json.loads(Path(episode_path).read_text(encoding="utf-8"))
    work = ROOT / "out" / ep["id"]
    work.mkdir(parents=True, exist_ok=True)

    wavs, times, t = [], [], 0.0
    for i, seg in enumerate(ep["segments"]):
        wav = work / f"say{i:02d}.wav"
        dur = synthesize(seg["say"], ep.get("speaker", 3), ep.get("speed", 1.0), wav)
        wavs.append(wav)
        times.append((t, t + dur + GAP))
        telop_image(seg, work / f"telop{i:02d}.png")
        t += dur + GAP
    total = t + 0.5
    join_wavs(wavs, work / "voice.wav")

    bg_in, bg_filter = background_args(ep, work, total)
    frame_image(ep, work / "frame.png", placeholder=(work / "placeholder.png") in map(Path, bg_in))
    inputs = bg_in + ["-i", str(work / "frame.png")]
    for i in range(len(ep["segments"])):
        inputs += ["-i", str(work / f"telop{i:02d}.png")]
    inputs += ["-i", str(work / "voice.wav")]

    chain = [f"[0:v]{bg_filter}[bg]", "[bg][1:v]overlay=0:0[v0]"]
    last = "v0"
    for i, (s, e) in enumerate(times):
        chain.append(f"[{last}][{i + 2}:v]overlay=0:0:enable='between(t,{s:.2f},{e:.2f})'[v{i + 1}]")
        last = f"v{i + 1}"
    audio_idx = len(ep["segments"]) + 2

    out = ROOT / "out" / f"{ep['id']}.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", *inputs,
           "-filter_complex", ";".join(chain),
           "-map", f"[{last}]", "-map", f"{audio_idx}:a",
           "-t", f"{total:.2f}", "-r", str(FPS),
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "20",
           "-c:a", "aac", "-b:a", "192k", str(out)]
    subprocess.run(cmd, check=True)
    print(f"{out}  ({total:.1f}秒)")
    for i, (s, e) in enumerate(times):
        print(f"  {s:5.1f}-{e:5.1f}s  {ep['segments'][i]['telop'].replace(chr(10), ' ')}")


if __name__ == "__main__":
    main(sys.argv[1])
