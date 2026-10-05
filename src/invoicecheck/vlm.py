"""Shared prompt and image-budget settings for the Qwen2.5-VL systems (zero-shot and QLoRA fine-tuned use the same prompt)."""
from .extraction import SCHEMA_TEXT

MODEL_ID = "Qwen/Qwen2.5-VL-3B-Instruct"
MAX_PIXELS = 1003520      # about 1,280 visual tokens (28x28 px per token); capped so QLoRA fits 12 GB, and reported
MIN_PIXELS = 256 * 28 * 28

PROMPT = f"""この画像は日本の適格請求書です。次のJSONスキーマに従って、書かれている内容だけを正確に抽出してください。
- 日付は西暦のISO形式 (YYYY-MM-DD) にする。和暦（令和・R）は西暦に直す。
- 金額と数量は整数（カンマや円記号は除く）。※が付いた品目の税率は8、それ以外は10。
- 登録番号は「T」と13桁の数字。見えない値を推測で補わない。
- JSONのみを出力する。

{SCHEMA_TEXT}"""


def messages(image_path):
    return [{"role": "user", "content": [{"type": "image", "image": f"file://{image_path}", "max_pixels": MAX_PIXELS},
                                         {"type": "text", "text": PROMPT}]}]
