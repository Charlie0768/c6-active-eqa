"""S02 仿真烟测：在同一场景中执行两轮固定动作，并保存可检查的 RGB 证据。

本脚本只检查环境能否启动、行动、重置和导出图片；它不是正式 EQA 策略。
轨迹记录行动反馈和 agent 自身位姿，不把场景内未观察物体清单交给模型。
"""

import argparse
import hashlib
import json
import platform
from importlib.metadata import version
from pathlib import Path

import numpy as np
from ai2thor.controller import Controller
from PIL import Image


# 固定动作序列用于比较两次从同一场景起点出发的运行结果。
ACTIONS = ("RotateRight", "MoveAhead", "RotateLeft", "LookDown", "LookUp")


def inspect_event(event, run_number, step_number, action, output_dir):
    """从一次仿真 event 中保存画面，并提取用于检查重放的少量字段。"""
    frame = event.frame
    if frame is None:
        raise RuntimeError("AI2-THOR returned no RGB frame")

    # 每轮的 step00 是初始画面；后续编号对应 ACTIONS 的第几个动作。
    frame_name = f"run{run_number}_step{step_number:02d}.png"
    frame_path = output_dir / frame_name
    Image.fromarray(frame).save(frame_path)
    # metadata 只在这个诊断脚本中用来检查自身位姿和动作反馈；不读物体真值。
    agent = event.metadata.get("agent", {})
    pose = {
        "position": agent.get("position"),
        "rotation": agent.get("rotation"),
        "cameraHorizon": agent.get("cameraHorizon"),
        "isStanding": agent.get("isStanding"),
    }
    # 哈希用于确认保存的文件与轨迹对应，不要求两次重置的像素哈希相同。
    return {
        "run": run_number,
        "step": step_number,
        "action": action,
        "success": None if action == "INITIAL" else event.metadata.get("lastActionSuccess"),
        "error": None if action == "INITIAL" else event.metadata.get("errorMessage") or None,
        "pose": pose,
        "frame": frame_name,
        "frame_sha256": hashlib.sha256(frame_path.read_bytes()).hexdigest(),
        "frame_shape": list(frame.shape),
    }


def comparable_state(record):
    """剔除轮次、文件名和像素哈希，只比较重置后应稳定的状态。"""
    return {key: record[key] for key in ("step", "action", "success", "error", "pose", "frame_shape")}


def frame_difference(first, second, output_dir):
    """计算两次对应画面的像素差；该差值是诊断信息而非通过门槛。"""
    # int16 防止 uint8 相减时发生溢出，例如 0-255 变成 1。
    first_frame = np.asarray(Image.open(output_dir / first["frame"]), dtype=np.int16)
    second_frame = np.asarray(Image.open(output_dir / second["frame"]), dtype=np.int16)
    difference = np.abs(first_frame - second_frame)
    return {
        "exact_png_match": first["frame_sha256"] == second["frame_sha256"],
        "mean_absolute_pixel_difference": round(float(difference.mean()), 6),
        "max_absolute_pixel_difference": int(difference.max()),
    }


def main():
    """读取命令行参数，运行两轮场景，再落盘轨迹和重置比较摘要。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", default="FloorPlan1")
    parser.add_argument("--output", type=Path, default=Path("runs/smoke"))
    parser.add_argument("--width", type=int, default=300)
    parser.add_argument("--height", type=int, default=300)
    args = parser.parse_args()
    # 禁止覆盖既有实验结果；每次重跑使用新目录或空目录。
    if args.output.exists() and any(args.output.iterdir()):
        parser.error(f"output directory is not empty: {args.output}")
    args.output.mkdir(parents=True, exist_ok=True)

    # Controller 在本机启动 Unity；try/finally 保证异常时也关闭进程。
    controller = None
    runs = []
    try:
        controller = Controller(scene=args.scene, width=args.width, height=args.height)
        for run_number in (1, 2):
            # 第一轮读取创建场景后的首帧；第二轮 reset 回到同一场景起点。
            event = controller.last_event if run_number == 1 else controller.reset(scene=args.scene)
            records = [inspect_event(event, run_number, 0, "INITIAL", args.output)]
            for step_number, action in enumerate(ACTIONS, start=1):
                event = controller.step(action=action)
                records.append(inspect_event(event, run_number, step_number, action, args.output))
            runs.append(records)
    finally:
        if controller is not None:
            controller.stop()

    # JSONL 一行对应一个观察时刻，便于逐步回放和检查。
    with (args.output / "trace.jsonl").open("w", encoding="utf-8") as trace:
        for records in runs:
            for record in records:
                trace.write(json.dumps(record, ensure_ascii=False) + "\n")

    # zip 对齐两轮同一 step；状态比较与像素比较分别记录。
    comparisons = []
    for first, second in zip(*runs):
        comparisons.append({
            "step": first["step"],
            "state_match": comparable_state(first) == comparable_state(second),
            **frame_difference(first, second, args.output),
        })
    # summary.json 汇总通过门槛；像素完全一致仅作为附加统计。
    summary = {
        "scene": args.scene,
        "actions": ACTIONS,
        "image_size": [args.width, args.height],
        "ai2thor_version": version("ai2thor"),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "frames": sum(map(len, runs)),
        "action_successes": [sum(r["success"] is True for r in records) for records in runs],
        "reset_comparisons": comparisons,
        "all_states_match_across_reset": all(row["state_match"] for row in comparisons),
        "all_pngs_match_exactly": all(row["exact_png_match"] for row in comparisons),
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Trace and PNG frames: {args.output.resolve()}")
    if not summary["all_states_match_across_reset"]:
        raise SystemExit("State/action replay differs after reset; inspect summary.json")


if __name__ == "__main__":
    main()
