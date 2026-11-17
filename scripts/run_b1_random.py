"""B1 随机探索 pilot：固定种子执行动作，最多取四帧给本地模型答题。

每道题从同一场景起点重置；随机策略只依赖预先声明的种子和预算，
不读取题目文字、私有答案、参考路径或物体 metadata 来选动作。
所有尝试过的动作（包括失败）都计入预算。当前只用于两题开发 pilot，
帧选择和提示词尚未冻结为正式 B1/B2/B3 共同协议。
"""

import argparse
import json
import platform
import random
import re
import time
from importlib.metadata import version
from pathlib import Path

from PIL import Image

from one_step_episode import action_success, consume_action
from run_b0 import pose_matches, sha256_file


# 顺序和等概率抽样方式都属于实验配置；不能根据题目或动作结果改写候选集。
RANDOM_ACTIONS = ("RotateRight", "RotateLeft", "MoveAhead", "LookUp", "LookDown")
MAX_MODEL_IMAGES = 4


def sample_actions(seed, budget):
    """每个 episode 从同一种子产生相同动作序列，与问题内容无关。"""
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("seed must be an integer")
    if not isinstance(budget, int) or isinstance(budget, bool) or not 1 <= budget <= 20:
        raise ValueError("budget must be between 1 and 20")
    rng = random.Random(seed)
    return [rng.choice(RANDOM_ACTIONS) for _ in range(budget)]


def select_frame_steps(actions_used, max_images=MAX_MODEL_IMAGES):
    """固定选起点、终点及均匀间隔的中间帧；不看图像内容或正确答案。"""
    if (not isinstance(actions_used, int) or isinstance(actions_used, bool) or actions_used < 0
            or not isinstance(max_images, int) or isinstance(max_images, bool) or max_images < 1
            or (actions_used > 0 and max_images < 2)):
        raise ValueError("invalid frame selection parameters")
    frame_count = actions_used + 1
    if frame_count <= max_images:
        return list(range(frame_count))
    return sorted({round(i * actions_used / (max_images - 1)) for i in range(max_images)})


def make_prompt(question, frame_count):
    """只把问题和所选帧数写进模型提示词，不插入真值或仿真 metadata。"""
    if not isinstance(question, str) or not question.strip() or frame_count < 1:
        raise ValueError("question and frame_count must be valid")
    return (
        f"你将按时间顺序看到随机探索中采样的 {frame_count} 张第一人称画面。"
        "第一张是起点，最后一张是本次探索的终点。"
        "请只根据这些画面回答；看不清或证据不足时回答不确定，不要猜测画面外内容。"
        f"问题：{question.strip()}"
        '只输出 JSON：{"answer":"是/否/不确定"}。'
    )


def save_frame(event, path, step):
    """保存每一步的 RGB；所有画面都用于回放，只有选中帧进入模型。"""
    if event.frame is None:
        raise RuntimeError(f"simulator returned no RGB frame at step {step}")
    Image.fromarray(event.frame).save(path)
    return {"step": step, "file": path.name, "sha256": sha256_file(path),
            "shape": list(event.frame.shape)}


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
        raise ValueError("this B1 pilot only supports FloorPlan1 dev questions")
    actions = sample_actions(args.seed, args.budget)
    if sha256_file(args.model / "model.safetensors") != MODEL_WEIGHTS_SHA256:
        raise ValueError("model weights differ from the pinned S03 checkpoint")

    args.output.mkdir(parents=True, exist_ok=True)
    result_path = args.output / "predictions.json"
    result = {
        "schema_version": public_data["schema_version"],
        "baseline": "B1_uniform_random_pilot",
        "questions_sha256": sha256_file(args.questions),
        "model_repo": MODEL_REPO,
        "model_revision": MODEL_REVISION,
        "model_weights_sha256": MODEL_WEIGHTS_SHA256,
        "ai2thor_version": version("ai2thor"),
        "mlx_vlm_version": version("mlx-vlm"),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "image_size": [300, 300],
        "action_seed": args.seed,
        "action_budget": args.budget,
        "random_action_set": RANDOM_ACTIONS,
        "sampled_action_sequence": actions,
        "frame_selection": {"method": "uniform_time_indices_including_first_last",
                            "max_images": MAX_MODEL_IMAGES},
        "generation": {"max_tokens": 64, "temperature": 0, "seed": 0},
        "predictions": [],
    }
    controller = None
    try:
        controller = Controller(scene="FloorPlan1", width=300, height=300)
        model, processor = load(str(args.model.resolve()))
        config = load_config(str(args.model.resolve()))
        for row in questions:
            started = time.perf_counter()
            event = controller.reset(scene=row["scene"])
            if not pose_matches(event.metadata, row["initial_pose"]):
                raise RuntimeError(f"initial pose differs from dataset: {row['id']}")
            frames = [save_frame(event, args.output / f"{row['id']}_step00.png", 0)]
            action_trace = []
            used = 0
            for action in actions:
                # 扣预算发生在仿真调用之前；失败动作也保留在轨迹与计数中。
                used = consume_action(action, used, args.budget)
                event = controller.step(action=action)
                success = action_success(event.metadata)
                action_trace.append({"step": used, "action": action, "success": success})
                frames.append(save_frame(event, args.output / f"{row['id']}_step{used:02d}.png", used))

            selected_steps = select_frame_steps(used)
            selected_frames = [frames[step] for step in selected_steps]
            prompt = make_prompt(row["question"], len(selected_frames))
            formatted = apply_chat_template(processor, config, prompt, num_images=len(selected_frames))
            if formatted.count("<|image_pad|>") != len(selected_frames):
                raise RuntimeError("image placeholder count does not match selected frames")
            response = generate(
                model, processor, formatted,
                image=[str((args.output / frame["file"]).resolve()) for frame in selected_frames],
                max_tokens=64, temperature=0, seed=0, verbose=False,
            )
            raw = response.text.strip()
            parsed, fence_removed = parse_answer(raw)
            valid = (isinstance(parsed, dict) and set(parsed) == {"answer"}
                     and parsed["answer"] in ("是", "否", "不确定"))
            result["predictions"].append({
                "id": row["id"],
                "answer": parsed["answer"] if valid else None,
                "valid_answer_json": valid,
                "actions_used": used,
                "model_visible": {"question": row["question"],
                                  "selected_frames": [frame["file"] for frame in selected_frames]},
                "selected_frame_steps": selected_steps,
                "frames": frames,
                "action_trace": action_trace,
                "raw_output": raw,
                "json_code_fence_removed": fence_removed,
                "model_prompt": prompt,
                "prompt_tokens": response.prompt_tokens,
                "generation_tokens": response.generation_tokens,
                "mlx_peak_memory_gb": round(response.peak_memory, 3),
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "paid_api_cost": 0,
            })
            # 每题完成即保存；若下一题失败，评分器会因缺少 ID 拒绝部分结果。
            result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    finally:
        if controller is not None:
            controller.stop()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=Path("data/dev_questions.json"))
    parser.add_argument("--model", type=Path, default=Path("models/qwen3-vl-2b-instruct-4bit"))
    parser.add_argument("--output", type=Path, default=Path("runs/s05-b1-random"))
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--budget", type=int, default=20)
    args = parser.parse_args()
    if not args.questions.is_file():
        parser.error(f"question file does not exist: {args.questions}")
    if not (args.model / "model.safetensors").is_file():
        parser.error("pinned local model weights are missing")
    if args.output.exists() and any(args.output.iterdir()):
        parser.error(f"output directory is not empty: {args.output}")
    result = run(args)
    print(json.dumps({"baseline": result["baseline"], "action_seed": result["action_seed"],
                      "selected_frame_steps": [row["selected_frame_steps"] for row in result["predictions"]],
                      "predictions": [{key: row[key] for key in (
                          "id", "answer", "valid_answer_json", "actions_used", "elapsed_seconds")}
                          for row in result["predictions"]]}, ensure_ascii=False, indent=2))
    print(f"Full run: {(args.output / 'predictions.json').resolve()}")


if __name__ == "__main__":
    main()
