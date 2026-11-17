"""同一组 300×300 厨房图，比较模型回答、拒答与证据定位。运行时无需 Unity。"""
from contextlib import ExitStack
import argparse
import hashlib
import json
import platform
import re
import time
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# (视图顺序，问题，答案，能提供证据的图号，从 1 起算；无证据时用 0)
CASES = [
    ([0], "画面中央的大型家电是冰箱吗？", "是", [1]),
    ([4], "厨房房门是白色的吗？", "否", [1]),
    ([4], "厨房房门是深棕色的吗？", "是", [1]),
    ([5], "冰箱旁地板上的小桶是白色的吗？", "否", [1]),
    ([5], "冰箱旁地板上的小桶在冰箱的右侧吗？", "是", [1]),
    ([1], "微波炉位于炉灶的下方吗？", "否", [1]),
    ([0], "厨房房门是白色的吗？", "不确定", [0]),
    ([4], "冰箱里有鸡蛋吗？", "不确定", [0]),
    ([5], "厨房房门是深棕色的吗？", "不确定", [0]),
    ([0, 1, 2, 3], "厨房房门是白色的吗？", "不确定", [0]),
    ([0, 1, 4, 3], "厨房房门是白色的吗？", "否", [3]),
    ([1, 5, 2, 3], "冰箱旁地板上的小桶在冰箱的右侧吗？", "是", [2]),
]
INSTRUCTION = ('只根据实际提供的图片回答。图片从1开始编号。'
               '如果图中无法判断，答“不确定”且图号填0。'
               '只输出JSON，格式为{"answer":"是/否/不确定","frame":整数}。问题：')


def mlx_engine(size):
    from mlx_vlm import load, generate
    from mlx_vlm.prompt_utils import apply_chat_template
    from mlx_vlm.utils import load_config
    path = ROOT / f"models/qwen3-vl-{size}b-instruct-4bit"
    model, processor = load(str(path))
    config = load_config(str(path))

    def predict(text, images):
        prompt = apply_chat_template(processor, config, text, num_images=len(images))
        response = generate(model, processor, prompt, image=list(map(str, images)),
                            max_tokens=48, temperature=0, seed=0, verbose=False)
        return response.text, round(response.peak_memory, 3)

    # 逐个记录实际加载目录中的权重文件哈希。
    digest = {}
    for weights in sorted(path.glob("*.safetensors")):
        with weights.open("rb") as f:
            digest[weights.name] = hashlib.file_digest(f, "sha256").hexdigest()
    return predict, {"backend": "mlx", "mlx_vlm": version("mlx-vlm"), "weights_sha256": digest,
                     "memory_metric": "MLX reported peak GB"}


def cuda_engine(size):
    import torch
    from transformers import AutoProcessor, BitsAndBytesConfig, Qwen3VLForConditionalGeneration
    if not torch.cuda.is_available():
        raise RuntimeError("需要 CUDA 版 PyTorch 与可用 NVIDIA GPU")
    name = f"Qwen/Qwen3-VL-{size}B-Instruct"
    revision = {"2": "89644892e4d85e24eaac8bacfd4f463576704203",
                "4": "ebb281ec70b05090aa6165b016eac8ec08e71b17"}[size]
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                               bnb_4bit_compute_dtype=torch.float16)
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        name, revision=revision, quantization_config=quant, device_map={"": 0}, dtype=torch.float16,
        attn_implementation="sdpa").eval()
    processor = AutoProcessor.from_pretrained(name, revision=revision)

    @torch.inference_mode()
    def predict(text, images):
        content = [{"type": "image", "image": str(p)} for p in images]
        content.append({"type": "text", "text": text})
        inputs = processor.apply_chat_template([{"role": "user", "content": content}],
                        tokenize=True, add_generation_prompt=True, return_dict=True,
                        return_tensors="pt").to("cuda:0")
        out = model.generate(**inputs, max_new_tokens=48, do_sample=False)
        answer = processor.batch_decode(out[:, inputs.input_ids.shape[1]:], skip_special_tokens=True)[0]
        return answer, round(torch.cuda.max_memory_reserved() / 1e9, 3)

    return predict, {"backend": "cuda_nf4", "gpu": torch.cuda.get_device_name(),
                     "vram_gb": torch.cuda.get_device_properties(0).total_memory / 1e9,
                     "memory_metric": "PyTorch peak reserved GB", "torch": torch.__version__,
                     "transformers": version("transformers"), "revision": revision}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=["mlx", "cuda"], required=True)
    parser.add_argument("--size", choices=["2", "4"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--with-unity", action="store_true",
                        help="同时启动一个 300×300 场景，检查仿真和推理共存")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("请用新输出路径，保留原始结果")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with ExitStack() as stack:
        controller = None
        if args.with_unity:
            from ai2thor.controller import Controller
            controller = Controller(scene="FloorPlan1", width=300, height=300)
            stack.callback(controller.stop)
        run_cases(args, controller)


def run_cases(args, controller):
    predict, meta = (mlx_engine if args.backend == "mlx" else cuda_engine)(args.size)
    rows = []
    for images, question, gold, refs in CASES:
        if controller is not None:
            # 真实执行动作以验证 Unity 仍能渲染。模型输入使用固定图，以便逐题配对。
            event = controller.step(action="RotateRight")
            if event.metadata["lastActionSuccess"] is not True or event.frame is None:
                raise RuntimeError("Unity 动作或渲染失败")
        files = [ROOT / "data/vision_probe" / f"view{i}.png" for i in images]
        start = time.perf_counter()
        raw, peak = predict(INSTRUCTION + question, files)
        elapsed = round(time.perf_counter() - start, 3)
        match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", raw.strip(), re.S | re.I)
        try:
            obj = json.loads(match.group(1) if match else raw)
        except ValueError:
            obj = None
        obj = obj if isinstance(obj, dict) else {}
        correct = obj.get("answer") == gold
        rows.append(dict(images=images, question=question, gold=gold, expected_frames=refs,
                         raw=raw, correct=correct, supported=correct and type(obj.get("frame")) is int
                         and obj["frame"] in refs, elapsed_s=elapsed, peak_gb=peak))
        args.output.write_text(json.dumps(dict(size=args.size, platform=platform.platform(),
             **meta, unity_active=controller is not None, rows=rows), indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(args.output, "answer", sum(r["correct"] for r in rows),
          "answer+frame", sum(r["supported"] for r in rows), "/", len(rows))


if __name__ == "__main__":
    main()
