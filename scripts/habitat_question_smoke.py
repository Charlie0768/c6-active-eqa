"""将单道 OpenEQA 原题与同住宅的 Habitat 起始 RGB 交给本地 Qwen。"""
import argparse
import json
from pathlib import Path

from mlx_vlm import generate, load
from mlx_vlm.prompt_utils import apply_chat_template
from mlx_vlm.utils import load_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--question-id", required=True)
    parser.add_argument("--data", type=Path, default=Path("data/raw/route-a/open-eqa-v0.json"))
    parser.add_argument("--model", type=Path, default=Path("models/qwen3-vl-2b-instruct-4bit"))
    args = parser.parse_args()
    # 先核对场景 ID，再从原始行中单独取出问题文字。参考答案不会进入提示词。
    rows = json.loads(args.data.read_text())
    matches = [row for row in rows if row["question_id"] == args.question_id]
    if len(matches) != 1:
        parser.error("Expected a unique official question ID")
    row = matches[0]
    run = json.loads((args.run / "trace.json").read_text())
    scene_id = run["scene"].split(".")[0]
    if not row["episode_history"].startswith("hm3d-v0/") or row["episode_history"].rsplit("-", 1)[-1] != scene_id:
        parser.error("Question does not belong to the rendered scene")
    image = str(args.run / run["trace"][0]["image"])
    prompt = ("Answer briefly using only the image. If the evidence is insufficient, answer 'unknown'. "
              + row["question"])
    model, processor = load(str(args.model))
    formatted = apply_chat_template(processor, load_config(str(args.model)), prompt, num_images=1)
    result = generate(model, processor, formatted, image=[image], temperature=0, seed=0,
                      max_tokens=64, verbose=False)
    record = dict(question_id=args.question_id, prompt=prompt, image=image, answer=result.text.strip(),
                  actions_used=0, condition="start_view", model=str(args.model))
    print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
