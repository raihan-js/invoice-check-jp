"""Shared prompt and image-budget settings for the Qwen2.5-VL systems (zero-shot and QLoRA fine-tuned use the same prompt)."""
from .extraction import SCHEMA_TEXT

MODEL_ID = "Qwen/Qwen2.5-VL-3B-Instruct"
MAX_PIXELS = 1003520      # about 1,280 visual tokens (28x28 px per token); capped so QLoRA fits 12 GB, and reported
MIN_PIXELS = 256 * 28 * 28

PROMPT_V1 = f"""この画像は日本の適格請求書です。次のJSONスキーマに従って、書かれている内容だけを正確に抽出してください。
- 日付は西暦のISO形式 (YYYY-MM-DD) にする。和暦（令和・R）は西暦に直す。
- 金額と数量は整数（カンマや円記号は除く）。※が付いた品目の税率は8、それ以外は10。
- 登録番号は「T」と13桁の数字。見えない値を推測で補わない。
- JSONのみを出力する。

{SCHEMA_TEXT}"""

PROMPT_V2 = f"""この画像は日本の適格請求書です。次のJSONスキーマに従って、書かれている内容だけを正確に抽出してください。
- issuer_name: 請求書を発行した会社（登録番号・住所・印鑑がある側）。宛名や振込先の口座名義ではなく発行者の名前。
- recipient_name: 宛先（「御中」「様」の前に書かれた会社名）。
- 日付は西暦のISO形式 (YYYY-MM-DD)。和暦（令和・R）は西暦に直す（令和1年=2019年）。各桁を丁寧に読む。
- 金額・数量・単価は整数（カンマ・円記号は除く）。
- 品目の rate: 品名の先頭に「※」が付いている品目は 8、付いていない品目は 10。
- tax_included: 税率ごとの集計欄が「（税込）」ならtrue、「（税抜）」ならfalse。
- totals: 「10%対象」「8%対象」の各行の対象金額(subtotal)と消費税額(tax)。
- 登録番号は「T」と13桁の数字。見えない値を推測で補わない。
- JSONのみを出力する。

{SCHEMA_TEXT}"""
PROMPTS = {"v1": PROMPT_V1, "v2": PROMPT_V2}
PROMPT = PROMPT_V2          # current default; v1 is kept so the iteration is on the record


def messages(image_path, prompt_version="v2"):
    return [{"role": "user", "content": [{"type": "image", "image": f"file://{image_path}", "max_pixels": MAX_PIXELS},
                                         {"type": "text", "text": PROMPTS[prompt_version]}]}]
