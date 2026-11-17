"""对同一套 HM3D 住宅的 OpenEQA 原题做配对读图检查。每题对比有线索和无线索。"""
import argparse
import hashlib
import json
import time
from pathlib import Path

from vision_probe import cuda_engine, mlx_engine

SCENE = "GLAQ4DNUx5U"
# 三组开发题和视角在第一次推理前固定。相同干扰图来自这套住宅的衣帽间。
# 两张厨房图从不同方向展示厨房与用餐区，沙发和暖架各有一张专门的细节图。
DISTRACTORS = ["p18-1", "p18-2", "p18-3", "p23-1"]
CASES = [
    ("91a12c51-1ca0-4651-902a-c5aaeb62534f", ["p29-0", *DISTRACTORS[1:]]),
    ("206ca121-9185-484d-ab22-acfb082b1359", [DISTRACTORS[0], "p16-1", *DISTRACTORS[2:]]),
    ("35c42d77-9cdd-4072-b423-768350e0dbf2", [*DISTRACTORS[:2], "p24-1", "p24-3"]),
]
PREFIX = ("Use only the four first-person photographs, numbered 1 to 4. "
          "Answer the question briefly in English. If the photos provide insufficient evidence, "
          "answer unknown and give frame 0. Otherwise give the frame number that best supports "
          'your answer. Return JSON only: {"answer":"...","frame":0}. Question: ')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--views", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--backend", required=True, choices=["mlx", "cuda"])
    parser.add_argument("--size", default="2", choices=["2", "4"])
    args = parser.parse_args()
    if args.output.exists():
        parser.error("请为此次运行指定新文件")
    manifest = json.loads((args.views / "views.json").read_text())
    if manifest["scene"] != f"{SCENE}.basis.glb" or manifest["seed"] != 17:
        parser.error("开发图不属于预先选定的住宅和种子")
    # 仅投影英文问题；包含参考答案的原始记录不进入模型接口。
    bank = {q["question_id"]: q["question"] for q in json.loads(args.questions.read_text(encoding="utf-8"))
            if q["episode_history"].startswith("hm3d-v0/") and q["episode_history"].endswith("-" + SCENE)}
    if any(question_id not in bank for question_id, _ in CASES):
        parser.error("当前题库缺少预先选定的 HM3D 题目")
    predict, metadata = (mlx_engine if args.backend == "mlx" else cuda_engine)(args.size)
    rows = []
    for question_id, selected in CASES:
        for condition, images in [("clues", selected), ("closet_only", DISTRACTORS)]:
            paths = [args.views / (name + ".png") for name in images]
            start = time.perf_counter()
            raw, peak = predict(PREFIX + bank[question_id], paths)
            rows.append(dict(question_id=question_id, question=bank[question_id], condition=condition,
                             images=images, raw=raw, elapsed_s=round(time.perf_counter()-start, 3),
                             peak_gb=peak, images_sha256=[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dict(scene=SCENE, size=args.size, **metadata, rows=rows), indent=2)
                           + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
