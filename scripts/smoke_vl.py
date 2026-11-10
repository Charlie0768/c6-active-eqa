"""S03 单图烟测：用本地 Qwen3-VL MLX 权重回答一张 RGB 图片的问题。

模型只收到图片和固定提示词；脚本不读取仿真 metadata 或标准答案。
输出是接口与资源记录，不是 EQA 正式评测分数。
"""

import argparse
import hashlib
import json
import platform
import re
import resource
import sys
import time
from importlib.metadata import version
from pathlib import Path

from PIL import Image
from mlx_vlm import generate, load
from mlx_vlm.prompt_utils import apply_chat_template
from mlx_vlm.utils import load_config


# 固定下载来源、修订版与权重哈希，避免同名模型悄悄变化。
MODEL_REPO = "mlx-community/Qwen3-VL-2B-Instruct-4bit"
MODEL_REVISION = "9c4f5209e57b31f4b9dfba735de3fb983739c9cc"
MODEL_WEIGHTS_SHA256 = "4750d95a2162829e127a94e83ac350d498d02070aab216c4687da48804a06ffb"
# 先只问可见冰箱，并要求简短 JSON；不允许猜测画面以外的信息。
PROMPT = (
    "请只根据这张图片回答：能否看到冰箱？"
    '只输出严格 JSON，格式为 {"answer":"是/否/不确定","evidence":"不超过20字的可见证据"}。'
    "不要猜测画面外的信息。"
)


def sha256_file(path):
    """分块读取大文件并计算 SHA-256，避免一次把权重读进内存。"""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_answer(raw):
    """解析纯 JSON 或一层 Markdown JSON 围栏；调用方仍保存原始文本。"""
    # 部分模型即使被要求严格 JSON，仍会包一层 ```json；这里只去掉完整围栏。
    match = re.fullmatch(r"```(?:json)?\s*\n(.*?)\n```", raw, flags=re.DOTALL | re.IGNORECASE)
    candidate = match.group(1).strip() if match else raw
    try:
        return json.loads(candidate), bool(match)
    except json.JSONDecodeError:
        return None, bool(match)


def main():
    """验证输入与权重，运行一次离线推理，保存完整审计记录。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, default=Path("runs/smoke-final/run1_step00.png"))
    parser.add_argument("--model", type=Path, default=Path("models/qwen3-vl-2b-instruct-4bit"))
    parser.add_argument("--output", type=Path, default=Path("runs/s03-one-image"))
    parser.add_argument("--max-tokens", type=int, default=96)
    args = parser.parse_args()
    # 先检查图片、模型目录、输出目录和生成长度，避免昂贵加载后才发现错误。
    if not args.image.is_file():
        parser.error(f"image does not exist: {args.image}")
    if not (args.model / "config.json").is_file():
        parser.error(f"model snapshot is missing config.json: {args.model}")
    if args.output.exists() and any(args.output.iterdir()):
        parser.error(f"output directory is not empty: {args.output}")
    if args.max_tokens < 1 or args.max_tokens > 128:
        parser.error("max-tokens must be between 1 and 128 for this smoke test")

    # verify() 检查文件可解码；图片哈希用于与 S02 的轨迹核对。
    with Image.open(args.image) as source_image:
        image_size = list(source_image.size)
        source_image.verify()
    image_hash = sha256_file(args.image)
    # 本地模型权重与 S03 已验收 checkpoint 必须完全一致。
    model_file = args.model / "model.safetensors"
    if not model_file.is_file():
        parser.error(f"model weights are missing: {model_file}")
    model_weights_hash = sha256_file(model_file)
    if model_weights_hash != MODEL_WEIGHTS_SHA256:
        parser.error("model weights SHA-256 differs from the S03 pinned checkpoint")

    # load 从本地路径读取模型和处理器；这里不调用在线推理 API。
    started = time.perf_counter()
    model, processor = load(str(args.model.resolve()))
    config = load_config(str(args.model.resolve()))
    loaded = time.perf_counter()
    # 模型的聊天模板必须包含恰好一个图像占位符，对应下面的唯一图片路径。
    formatted_prompt = apply_chat_template(processor, config, PROMPT, num_images=1)
    image_placeholder_count = formatted_prompt.count("<|image_pad|>")
    if image_placeholder_count != 1:
        sys.exit(f"Expected one image placeholder, found {image_placeholder_count}")
    # temperature=0、seed=0 固定采样设置；重复输出仍应以实际记录为准。
    response = generate(
        model,
        processor,
        formatted_prompt,
        image=[str(args.image.resolve())],
        max_tokens=args.max_tokens,
        temperature=0,
        seed=0,
        verbose=False,
    )
    finished = time.perf_counter()

    # 原文、解析结果、JSON 格式是否符合约定分别保存，便于诊断格式失败。
    raw = response.text.strip()
    parsed, json_code_fence_removed = parse_answer(raw)
    valid_answer = (
        isinstance(parsed, dict)
        and set(parsed) == {"answer", "evidence"}
        and parsed.get("answer") in ("是", "否", "不确定")
        and isinstance(parsed.get("evidence"), str)
        and 1 <= len(parsed["evidence"]) <= 20
    )
    # 资源指标与耗时只是本次烟测，不代表长批量实验的峰值或吞吐。
    record = {
        "model_repo": MODEL_REPO,
        "model_revision": MODEL_REVISION,
        "model_quantization": "MLX 4-bit community conversion",
        "model_path": str(args.model.resolve()),
        "model_weights_sha256": model_weights_hash,
        "mlx_vlm_version": version("mlx-vlm"),
        "mlx_version": version("mlx"),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "image": str(args.image.resolve()),
        "image_sha256": image_hash,
        "image_size": image_size,
        "question_prompt": PROMPT,
        "formatted_prompt_sha256": hashlib.sha256(formatted_prompt.encode("utf-8")).hexdigest(),
        "formatted_prompt_image_placeholder_count": image_placeholder_count,
        "generation": {"max_tokens": args.max_tokens, "temperature": 0, "seed": 0},
        "raw_output": raw,
        "parsed_output": parsed,
        "json_code_fence_removed": json_code_fence_removed,
        "valid_answer_json": valid_answer,
        "finish_reason": response.finish_reason,
        "prompt_tokens": response.prompt_tokens,
        "generation_tokens": response.generation_tokens,
        "load_seconds": round(loaded - started, 3),
        "generate_seconds": round(finished - loaded, 3),
        "total_seconds": round(finished - started, 3),
        "mlx_peak_memory_gb": round(response.peak_memory, 3),
        "process_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "paid_api_cost": 0,
    }
    # 只在生成结束后写 result.json；格式不合格时仍保留记录供排查。
    args.output.mkdir(parents=True, exist_ok=True)
    result_path = args.output / "result.json"
    result_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: record[key] for key in (
        "raw_output", "parsed_output", "valid_answer_json", "load_seconds",
        "generate_seconds", "mlx_peak_memory_gb", "process_peak_rss_bytes"
    )}, ensure_ascii=False, indent=2))
    print(f"Full record: {result_path.resolve()}")
    if not valid_answer:
        sys.exit("Model output did not match the requested JSON schema; inspect result.json")


if __name__ == "__main__":
    main()
