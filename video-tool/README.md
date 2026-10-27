# 動画の自動生成ツール

台本データ（`episodes/*.json`）から、読み上げ音声とテロップ入りの縦型ショート動画（1080×1920・30fps）を作ります。

## 使い方

1. VOICEVOX を起動しておく
2. このフォルダで次を実行する

```bash
python make_video.py episodes/01-tokyo.json
```

3. `out/01-tokyo.mp4` ができる

## 空撮映像を入れる

`bg/<エピソードID>/` に、Google Earth Studio で書き出したファイルを置いてから実行し直すだけです。

- 連番画像（ZIP を解凍した中身の `.jpeg` など）でも、`.mp4` でもOK
- 例：`bg/01-tokyo/tokyo_000.jpeg, tokyo_001.jpeg, ...`
- 何も無いときは、仮の背景（夜景のイラスト）になります
- 画面の下端 140px は Earth Studio のクレジット表示のために空けてあります

## 台本データの書き方

```json
{
  "id": "01-tokyo",          // 出力ファイル名と bg フォルダ名
  "number": 1,               // 画面上部の「#01」
  "prefecture": "東京都",
  "speaker": 3,              // VOICEVOX の話者ID（3 = ずんだもん ノーマル）
  "speed": 1.15,             // 話す速さ
  "segments": [
    {
      "say": "読み上げる文",     // 読み間違えそうな語はひらがなで書く
      "telop": "画面の文字\n改行もOK",
      "style": "price",        // 省略可。価格用の黄色い大きな文字
      "note": "※補足"          // 省略可。テロップの下に小さく出す
    }
  ]
}
```

## 必要なもの

- VOICEVOX（起動しておく）
- ffmpeg
- Python 3 と `requests`、`Pillow`（`pip install requests Pillow`）
