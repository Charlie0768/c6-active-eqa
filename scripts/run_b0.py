"""S05 起始视角基线 B0：每题只看初始 RGB，行动数恒为 0。

本脚本只读取 data/dev_questions.json，不读取私有 dev_labels.json。
仿真 metadata 仅用于检查起点姿态；模型实际输入只有问题文字和一张 RGB 图。
"""

import argparse
import hashlib
import json
import platform
import re
import time
from importlib.metadata import version
from pathlib import Path

from PIL import Image


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_prompt(question):
    """只接收题目字符串；不可能从标签记录拼入标准答案或参考路径。"""
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be a nonempty string")
    return (
        "请只根据当前这一张第一人称画面回答问题。"
        "如果画面没有足够证据，请回答不确定；不要猜测画面外内容。"
        f"问题：{question.strip()}"
        '只输出 JSON：{"answer":"是/否/不确定"}。'
    )


def pose_matches(metadata, expected, tolerance=0.02):
    """检查重置是否回到题目声明的起点；此信息不进入模型提示词。"""
    agent = metadata["agent"]
    position = agent["position"]
    for axis in ("x", "y", "z"):
        if abs(position[axis] - expected["position"][axis]) > tolerance:
            return False
    yaw_difference = (agent["rotation"]["y"] - expected["yaw_degrees"] + 180) % 360 - 180
    return (abs(yaw_difference) <= tolerance
            and abs(agent["cameraHorizon"] - expected["camera_horizon_degrees"]) <= tolerance)


def run(args):
    from ai2thor.controller import Controller
    from mlx_vlm import generate, load
    from mlx_vlm.prompt_utils import apply_chat_template
    from mlx_vlm.utils import load_config
    from smoke_vl import MODEL_REPO, MODEL_REVISION, MODEL_WEIGHTS_SHA256, parse_answer

    public_data = json.loads(args.questions.read_text(encoding="utf-8"))
    questions = public_data["questions"]
    if not questions or len({row["id"] for row in questions}) != len(questions):
        raise ValueError("question set must be nonempty and IDs unique")
    for row in questions:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", row["id"]):
            raise ValueError(f"unsafe question ID: {row['id']}")
        if set(row) & {"answer", "gold_answer", "truth", "evidence", "reference_actions", "reference_image"}:
            raise ValueError(f"private label fields found in public question: {row['id']}")
    if any(row["split"] != "dev" or row["scene"] != "FloorPlan1" for row in questions):
        raise ValueError("this small B0 pilot only supports FloorPlan1 dev questions")
    if sha256_file(args.model / "model.safetensors") != MODEL_WEIGHTS_SHA256:
        raise ValueError("model weights differ from the pinned S03 checkpoint")

    args.output.mkdir(parents=True, exist_ok=True)
    result_path = args.output / "predictions.json"
    result = {
        "schema_version": public_data["schema_version"],
        "baseline": "B0_initial_rgb_only",
        "questions_sha256": sha256_file(args.questions),
        "model_repo": MODEL_REPO,
        "model_revision": MODEL_REVISION,
        "model_weights_sha256": MODEL_WEIGHTS_SHA256,
        "image_size": [300, 300],
        "generation": {"max_tokens": 64, "temperature": 0, "seed": 0},
        "ai2thor_version": version("ai2thor"),
        "mlx_vlm_version": version("mlx-vlm"),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "predictions": [],
    }
    controller = None
    try:
        # 与 S04 一样让 Unity 在本机运行；模型只在本进程加载一次。
        controller = Controller(scene="FloorPlan1", width=300, height=300)
        model, processor = load(str(args.model.resolve()))
        config = load_config(str(args.model.resolve()))
        for row in questions:
            started = time.perf_counter()
            event = controller.reset(scene=row["scene"])
            if not pose_matches(event.metadata, row["initial_pose"]):
                raise RuntimeError(f"initial pose differs from dataset: {row['id']}")
            if event.frame is None:
                raise RuntimeError(f"simulator returned no RGB frame: {row['id']}")
            # 文件名来自受控题目 ID；每道题仅保存起点，不执行环境动作。
            frame_path = args.output / f"{row['id']}_frame0.png"
            Image.fromarray(event.frame).save(frame_path)

            prompt = make_prompt(row["question"])
            formatted = apply_chat_template(processor, config, prompt, num_images=1)
            if formatted.count("<|image_pad|>") != 1:
                raise RuntimeError("expected exactly one image placeholder")
            response = generate(model, processor, formatted, image=[str(frame_path.resolve())],
                                max_tokens=64, temperature=0, seed=0, verbose=False)
            raw = response.text.strip()
            parsed, fence_removed = parse_answer(raw)
            valid = (isinstance(parsed, dict) and set(parsed) == {"answer"}
                     and parsed["answer"] in ("是", "否", "不确定"))
            result["predictions"].append({
                "id": row["id"],
                "answer": parsed["answer"] if valid else None,
                "valid_answer_json": valid,
                "actions_used": 0,
                "model_visible": {"question": row["question"], "image_file": frame_path.name},
                "image_sha256": sha256_file(frame_path),
                "raw_output": raw,
                "json_code_fence_removed": fence_removed,
                "model_prompt": prompt,
                "prompt_tokens": response.prompt_tokens,
                "generation_tokens": response.generation_tokens,
                "mlx_peak_memory_gb": round(response.peak_memory, 3),
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "paid_api_cost": 0,
            })
            # 每题立即落盘；中途失败时已完成的预测仍可检查，但评分器会拒绝缺题。
            result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    finally:
        if controller is not None:
            controller.stop()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=Path("data/dev_questions.json"))
    parser.add_argument("--model", type=Path, default=Path("models/qwen3-vl-2b-instruct-4bit"))
    parser.add_argument("--output", type=Path, default=Path("runs/s05-b0"))
    args = parser.parse_args()
    if not args.questions.is_file():
        parser.error(f"question file does not exist: {args.questions}")
    if not (args.model / "model.safetensors").is_file():
        parser.error("pinned local model weights are missing")
    if args.output.exists() and any(args.output.iterdir()):
        parser.error(f"output directory is not empty: {args.output}")
    result = run(args)
    print(json.dumps({"baseline": result["baseline"], "predictions": [
        {key: row[key] for key in ("id", "answer", "valid_answer_json", "actions_used", "elapsed_seconds")}
        for row in result["predictions"]]}, ensure_ascii=False, indent=2))
    print(f"Full run: {(args.output / 'predictions.json').resolve()}")


if __name__ == "__main__":
    main()
