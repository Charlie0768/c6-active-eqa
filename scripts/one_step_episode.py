"""S04 最小闭环：AI2-THOR 行动一次，再用本地 VL 模型回答两帧问题。

动作由脚本预设，不是模型自主选择；搜索策略和正式评分属于后续工作单。
模型输入由白名单构造，不会直接收到完整仿真 metadata 或隐藏真值。
"""

import argparse
import hashlib
import json
import platform
import resource
import subprocess
import sys
import time
from importlib.metadata import version
from pathlib import Path

from PIL import Image


# 本阶段只做一次固定右转，确认仿真和推理能在同一进程顺序接通。
ACTION = "RotateRight"
# 预算函数允许的动作集合；明确拒绝 Teleport 等越界动作。
ALLOWED_ACTIONS = frozenset({"RotateRight", "RotateLeft", "MoveAhead", "LookUp", "LookDown"})
QUESTION = "这两张画面中是否看到了冰箱？"


def consume_action(action, used, budget):
    """在执行前扣行动预算；即使后续仿真动作失败也已经计数。"""
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"action is not allowed: {action}")
    if used >= budget:
        raise RuntimeError("action budget exhausted")
    return used + 1


def action_success(metadata):
    """仅从仿真 metadata 中取出上次动作成功与否这一个布尔值。"""
    value = metadata.get("lastActionSuccess")
    if not isinstance(value, bool):
        raise ValueError("missing boolean lastActionSuccess")
    return value


def sha256_file(path):
    """分块计算文件哈希，用于记录图片和权重的确切版本。"""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_frame(event, path):
    """把 event 的 RGB 数组写成 PNG，并返回供审计的帧清单。"""
    if event.frame is None:
        raise RuntimeError("AI2-THOR returned no RGB frame")
    Image.fromarray(event.frame).save(path)
    # 此脚本只用固定文件名 frame1/frame2；哈希和 shape 是日志字段，不是视觉真值。
    return {"frame_number": 1 if path.stem == "frame1" else 2,
            "file": path.name, "sha256": sha256_file(path),
            "shape": list(event.frame.shape)}


def make_observation(question, frames, action, success, used, budget):
    """构造本次可见信息清单；不加入对象列表、位置真值或标准答案。"""
    # frames 中的文件名供模型加载图片；哈希和 shape 仅用于记录审计。
    return {
        "question": question,
        "frames": frames,
        "previous_action": {"name": action, "success": success},
        "actions_used": used,
        "action_budget": budget,
    }


def make_prompt(observation):
    """把清单中的问题、动作反馈和预算转为文字提示词。"""
    # 实际图片由 generate(image=...) 传入，不把 PNG 或哈希嵌入这段文字。
    status = "成功" if observation["previous_action"]["success"] else "失败"
    return (
        "你会按顺序看到两张第一人称图像：图1是行动前，图2是行动后。"
        f"执行的动作是 {observation['previous_action']['name']}，动作{status}。"
        f"已用 {observation['actions_used']}/{observation['action_budget']} 次行动。"
        f"问题：{observation['question']}"
        '请只根据这两张图输出 JSON：{"answer":"是/否/不确定",'
        '"evidence_frame":1或2或null}。'
        "图1或图2只填实际提供证据的那一帧；不要猜测画面外内容。"
    )


def rss_bytes(pid):
    """用 ps 读取某一时刻进程 RSS；它不是进程生命周期峰值。"""
    if not pid:
        return None
    result = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)],
                            capture_output=True, text=True, check=False)
    return int(result.stdout.strip()) * 1024 if result.returncode == 0 and result.stdout.strip() else None


def run_episode(args):
    """执行一条完整链路：启动场景→两帧→本地推理→落盘→关闭 Unity。"""
    # 重依赖放在函数内，便于单元测试只导入预算/白名单函数。
    from ai2thor.controller import Controller
    from mlx_vlm import generate, load
    from mlx_vlm.prompt_utils import apply_chat_template
    from mlx_vlm.utils import load_config
    from smoke_vl import MODEL_REPO, MODEL_REVISION, MODEL_WEIGHTS_SHA256, parse_answer

    # 先核对本地权重。这里的量化 checkpoint 固定，不从网络拉取模型。
    model_file = args.model / "model.safetensors"
    if sha256_file(model_file) != MODEL_WEIGHTS_SHA256:
        raise ValueError("model weights differ from the S03 pinned checkpoint")

    # 用单调时钟分别记录启动、动作、加载和生成耗时。
    started = time.perf_counter()
    controller = None
    try:
        # Controller 启动本机 Unity 的 FloorPlan1；last_event 是初始第一人称画面。
        controller = Controller(scene="FloorPlan1", width=300, height=300)
        controller_started = time.perf_counter()
        frame1 = save_frame(controller.last_event, args.output / "frame1.png")

        # 先扣 1/1 次预算，再执行 RotateRight；失败的动作也应占一次预算。
        used = consume_action(ACTION, 0, 1)
        event = controller.step(action=ACTION)
        # 只投影 lastActionSuccess，绝不把 event.metadata 整体送入提示词。
        success = action_success(event.metadata)
        frame2 = save_frame(event, args.output / "frame2.png")
        acted = time.perf_counter()

        # 把可见问题、两张已保存画面、动作反馈与预算组装成清单。
        observation = make_observation(QUESTION, [frame1, frame2], ACTION, success, used, 1)
        prompt = make_prompt(observation)
        # 模型加载前后各取一次 Unity 存活状态和 RSS，检查是否真在同机共存。
        unity_pid = controller.unity_pid
        unity_rss_before = rss_bytes(unity_pid)
        unity_alive_before = controller.server.unity_proc.poll() is None

        # 本地 MLX 权重与处理器加载到当前 Python 进程；无云端推理调用。
        model, processor = load(str(args.model.resolve()))
        config = load_config(str(args.model.resolve()))
        model_loaded = time.perf_counter()
        # 图像占位符数量必须与实际传入的两张图片一一对应。
        formatted_prompt = apply_chat_template(processor, config, prompt, num_images=2)
        image_placeholder_count = formatted_prompt.count("<|image_pad|>")
        if image_placeholder_count != 2:
            raise RuntimeError(f"expected two image placeholders, found {image_placeholder_count}")
        # 图片路径按 observation.frames 的顺序传入，保证证据帧 1/2 有明确含义。
        response = generate(model, processor, formatted_prompt,
                            image=[str((args.output / frame["file"]).resolve()) for frame in observation["frames"]],
                            max_tokens=128, temperature=0, seed=0, verbose=False)
        answered = time.perf_counter()
        unity_rss_after = rss_bytes(unity_pid)
        unity_alive_after = controller.server.unity_proc.poll() is None

        # 保存原始回答；解析时允许单层 Markdown 围栏，但仍严格校验 JSON 字段。
        raw = response.text.strip()
        parsed, code_fence_removed = parse_answer(raw)
        # 只有两个字段、允许的答案集合及有效证据帧号才算格式通过。
        valid = (isinstance(parsed, dict)
                 and set(parsed) == {"answer", "evidence_frame"}
                 and parsed["answer"] in ("是", "否", "不确定")
                 and parsed["evidence_frame"] in (1, 2, None)
                 and (parsed["answer"] != "是" or parsed["evidence_frame"] in (1, 2)))
        # episode.json 同时存输入清单、输出、版本、计时和资源样本，供复核。
        # MLX 峰值和进程 RSS 口径不同，不能简单相加为“机器总内存”。
        record = {
            "status": "completed" if valid else "invalid_answer_format",
            "scene": "FloorPlan1",
            "policy": "scripted_one_step",
            "model_repo": MODEL_REPO,
            "model_revision": MODEL_REVISION,
            "model_weights_sha256": MODEL_WEIGHTS_SHA256,
            "model_quantization": "MLX 4-bit community conversion",
            "ai2thor_version": version("ai2thor"),
            "mlx_vlm_version": version("mlx-vlm"),
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "model_input_allowlist": observation,
            "model_prompt": prompt,
            "formatted_prompt_sha256": hashlib.sha256(formatted_prompt.encode("utf-8")).hexdigest(),
            "image_placeholder_count": image_placeholder_count,
            "raw_answer": raw,
            "parsed_answer": parsed,
            "json_code_fence_removed": code_fence_removed,
            "valid_answer_json": valid,
            "prompt_tokens": response.prompt_tokens,
            "generation_tokens": response.generation_tokens,
            "timing_seconds": {
                "simulator_start": round(controller_started - started, 3),
                "capture_and_action": round(acted - controller_started, 3),
                "model_load": round(model_loaded - acted, 3),
                "model_generate": round(answered - model_loaded, 3),
                "total_before_cleanup": round(answered - started, 3),
            },
            "resource": {
                "mlx_peak_memory_gb": round(response.peak_memory, 3),
                "python_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                "unity_pid": unity_pid,
                "unity_rss_bytes_before_model": unity_rss_before,
                "unity_rss_bytes_after_model": unity_rss_after,
                "unity_alive_before_model": unity_alive_before,
                "unity_alive_after_model": unity_alive_after,
            },
            "paid_api_cost": 0,
        }
        # 即使答案格式不合格，也写下完整记录；main 再以非零状态报错。
        (args.output / "episode.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return record
    finally:
        # 成功、格式失败或抛异常时，都停止 Unity，避免留下后台进程。
        if controller is not None:
            controller.stop()


def main():
    """解析路径、保护已有输出目录，并展示本次闭环的简要结果。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=Path("models/qwen3-vl-2b-instruct-4bit"))
    parser.add_argument("--output", type=Path, default=Path("runs/s04-one-step"))
    args = parser.parse_args()
    # 输出目录必须为空：新实验不会覆盖旧的 episode.json 或图片。
    if not (args.model / "model.safetensors").is_file():
        parser.error("pinned local model weights are missing")
    if args.output.exists() and any(args.output.iterdir()):
        parser.error(f"output directory is not empty: {args.output}")
    args.output.mkdir(parents=True, exist_ok=True)
    record = run_episode(args)
    print(json.dumps({
        "status": record["status"],
        "observation": record["model_input_allowlist"],
        "answer": record["parsed_answer"],
        "timing_seconds": record["timing_seconds"],
        "resource": record["resource"],
    }, ensure_ascii=False, indent=2))
    print(f"Full record: {(args.output / 'episode.json').resolve()}")
    if record["status"] != "completed":
        sys.exit("Model output failed JSON schema; inspect episode.json")


if __name__ == "__main__":
    main()
