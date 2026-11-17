# 多大的 Qwen3-VL 能读懂 OpenEQA 的线索？

项目的最低目标为 Windows RTX 3060 6 GB，另测 Windows RTX 4060 8 GB 和 Apple M4 16 GB 统一内存。每个模型单独加载，batch=1，贪心生成，最多 48 个新 token。模型同时读取四张 480×270 的 Habitat 第一人称 RGB 和一道英文原题。Mac 使用 MLX 4-bit，Windows 使用 CUDA NF4。两端的量化权重和算子不同，策略比较需固定设备及推理后端。

## 怎样把探索与读图能力拆开测

1. 在公开样例住宅 GLAQ4DNUx5U 的导航网格上，用固定种子取 32 个点，各朝四个方向拍照。这个离线步骤可瞬移。实际测主动探索时，agent 必须从固定起点一步步走。
2. 检查图像后、模型推理前，从该住宅的 11 道真题中选 3 道。每题先给四张有线索的组合，再用四张衣帽间的照片问同样的问题。记录内容、图号、延迟、内存峰值和每张图片的哈希。模型只收到照片、统一的指令及原问题。
3. 有线索时人工对照原题参考答案，无线索时检查是否回答 unknown，另查返回图号。这个小样本用来诊断失误，未调用 LLM-Match。三题及同一住宅应留在开发集，正式评测另选住宅和问题。
4. 另保留早期 AI2-THOR 厨房的 12 个固定输入作为单图/四图软件回归，六个原图位于 `data/vision_probe/`。其是非题、中文提示和评分方式与 OpenEQA 不同，分开报告。

## M4 Mac 实测结果

下表每行由三个英文原题配对得到，一种条件每题只跑一次。正确与否为对官方参考答案的人工核对，unknown 单独计。峰值为 MLX 进程报告值，延迟从传入图片到收到回答，包含首次推理，排除模型加载时间。

| MLX 4-bit | 给线索，答中参考答案 | 只给衣帽间图，回答 unknown | 四图单次推理中位耗时 | MLX 峰值 |
|---|---:|---:|---:|---:|
| 2B | 1/3 | 3/3 | 1.42 秒 | 2.58 GB |
| 4B | 0/3 | 3/3 | 2.57 秒 | 3.90 GB |

- 客厅沙发的官方答案是 C 形。两者都引用了含沙发的第 1 张图，答成 L 形。衣帽间条件下 2B 写成数组 `[0]`，回答语义正确，但证据编号格式错误。
- 对于怎样晾干毛巾，浴室图有墙装暖架，参考答案是挂到毛巾加热架上。两者都回答 unknown。
- 对于在餐厅能否和厨房里做饭的人交谈，参考答案为 Yes。2B 给出 yes 并引用厨房图，4B 答 unknown。开放式布局的判断还依赖两张互补视角；命中答案只表明与参考答案一致。
- 同一住宅、人工挑图、三道题只能指导下一轮资源配置。暂时以 2B 跑基线。取得多个开发住宅后，优先用有充分可见证据的问题复测，再决定是否升级。Windows 两张卡仍待实机运行，Mac 峰值不能用来推算 6 GB 卡一定能跑。

逐条原始输出与图片哈希见 [2B](results/openeqa-mac-2b.json) 和 [4B](results/openeqa-mac-4b.json)。历史厨房回归中，2B 答案对 7/12，答案与证据图号同时正确 5/12；详情见 [历史原始输出](results/vision-probe-mac-2b.json)。

## 在 Mac 复现

先按 [Habitat 环境说明](HABITAT_MAC.md) 取得公开样例和原题，并按 [MLX 环境记录](ENVIRONMENT.md) 配好 MLX 与 2B 权重。4B 社区量化权重固定修订后约 3.11 GB。使用新的输出目录或文件保留每次结果。

```bash
runs/habitat-env/bin/python scripts/hm3d_dev_views.py --scene data/raw/route-a/example/GLAQ4DNUx5U.basis.glb --output runs/hm3d-views
.venv-vl/bin/python -c "from huggingface_hub import snapshot_download; snapshot_download('mlx-community/Qwen3-VL-4B-Instruct-4bit',revision='2fd8dacbdb8f1e54b8c005f081ec5bf79c56376b',local_dir='models/qwen3-vl-4b-instruct-4bit')"
HF_HUB_OFFLINE=1 .venv-vl/bin/python scripts/openeqa_size_probe.py --backend mlx --size 2 --questions data/raw/route-a/open-eqa-v0.json --views runs/hm3d-views --output runs/check/hm3d-mac2.json
HF_HUB_OFFLINE=1 .venv-vl/bin/python scripts/openeqa_size_probe.py --backend mlx --size 4 --questions data/raw/route-a/open-eqa-v0.json --views runs/hm3d-views --output runs/check/hm3d-mac4.json
```

## 在 Windows 复测

在仓库根目录用 Python 3.11 的虚拟环境，按 PyTorch 官方选择器安装与驱动匹配的 CUDA 版 torch 和 torchvision，再安装下列依赖。把同一批开发图和 views.json 放在 runs/hm3d-views，官方题库放在 data/raw/route-a/open-eqa-v0.json。可在组内按数据使用条款传递相同输入，原始 HM3D 资源和渲染图保存在各自设备上。[PyTorch 安装](https://pytorch.org/get-started/locally/) · [Transformers Qwen3-VL](https://huggingface.co/docs/transformers/v4.57.3/model_doc/qwen3_vl) · [NF4 加载](https://huggingface.co/docs/transformers/v4.57.3/quantization/bitsandbytes)

```powershell
New-Item -ItemType Directory -Force data/raw/route-a | Out-Null
Invoke-WebRequest "https://raw.githubusercontent.com/facebookresearch/open-eqa/cfa3fce4595c1622bb2f8a38ae2ca9aae9eb685b/data/open-eqa-v0.json" -OutFile data/raw/route-a/open-eqa-v0.json
python -m pip install "transformers==4.57.3" "accelerate>=1,<2" "bitsandbytes>=0.46,<1" Pillow
powershell -ExecutionPolicy Bypass -File scripts/check_windows_gpu.ps1 -Size 2 -Views runs/hm3d-views
powershell -ExecutionPolicy Bypass -File scripts/check_windows_gpu.ps1 -Size 4 -Views runs/hm3d-views
```

先在 3060 6 GB 上运行，随后用 4060 8 GB 复测。如果还未准备好 Habitat 图，省略 -Views 可先用仓库自带的厨房图检查推理链路。CUDA 在加载时把官方模型量化到单卡，首次下载的原始权重分别约占 4.26 GB 和 8.88 GB 磁盘。日志记录 GPU 型号、运行前空闲显存、所有预测及 PyTorch 峰值预留显存。OOM 时保留错误和 gpu.csv。Mac 上的 MLX 峰值与显卡专用显存口径不同。

固定图片复测完成后，在最低配置上让 Habitat 与推理同时运行，核对一次真实的 20 步轨迹及连续 10 道题，记录 OOM、整卡显存（nvidia-smi）、延迟与失败次数。Windows 原生可做 CUDA 读图，若在 WSL2/Linux 运行 Habitat，先按 Habitat 文档实测 OpenGL/EGL 渲染与导航。仿真与推理分机是另一个部署条件，须单独标明。[Habitat-Sim 安装](https://github.com/facebookresearch/habitat-sim#installation) · [Windows 上的 WSL GPU 环境](https://learn.microsoft.com/en-us/windows/ai/directml/gpu-cuda-in-wsl)

## 同一机位提高相机分辨率

脚本用 `--height` 设定 16:9 相机输出，高度取 9 的正整数倍。比如 `--height 720` 对应 1280×720，也可用 640×360 或 2560×1440，能否用于四帧推理由设备资源决定。以下模型实验只比较三档。使用同一住宅、相机视野、种子和导航网格，把图像从 480×270 提高到 960×540、1920×1080。三份机位清单中的 128 个位置与朝向逐项一致。用于四图问答的 8 张原图、题目、提示词、解码和模型权重都按机位或原始配置逐一匹配。模型收到完整视野；展示给人的局部对比才使用裁剪。

```bash
runs/habitat-env/bin/python scripts/hm3d_dev_views.py --scene data/raw/route-a/example/GLAQ4DNUx5U.basis.glb --height 1080 --output runs/hm3d-views-1080p
HF_HUB_OFFLINE=1 .venv-vl/bin/python scripts/openeqa_size_probe.py --backend mlx --size 2 --questions data/raw/route-a/open-eqa-v0.json --views runs/hm3d-views-1080p --output runs/check/hm3d-2b-1080p.json
```

另下载了官方标准 GLB 样例包（SHA-256 `b3b6c82990f6ed18006192a06055d9d831f087e20ae83ac6fe310e6873ddcb2f`）。检查同一住宅 GLAQ4DNUx5U 的 GLB 嵌入资源，Habitat 优化版是 57 张 2048×2048 的 Basis 纹理，标准版是 57 张 2048×2048 的 JPEG 纹理。标准版包更大，两种格式保留的纹理像素尺寸相同。[Matterport 官方下载清单](https://github.com/matterport/habitat-matterport-3dresearch#-downloading-hm3d-v02)

在 M4 16 GB 上顺序运行，每个模型每档 6 次四图推理。正确数只计含线索的三个原题，耗时取全部六次的中位数。权重、提示词和机位保持一致，逐题核对输入哈希。以下数字对应该套住宅的开发样本。

| 每张输入图 | 2B 答中 | 4B 答中 | 2B / 4B 中位耗时 | 2B / 4B MLX 峰值 |
|---|---:|---:|---:|---:|
| 480×270 | 1/3 | 0/3 | 1.42 / 2.57 秒 | 2.58 / 3.90 GB |
| 960×540 | 0/3 | 0/3 | 5.60 / 10.18 秒 | 2.80 / 4.08 GB |
| 1920×1080 | 0/3 | 0/3 | 45.76 / 86.32 秒 | 3.83 / 5.25 GB |

两个模型在三档下均指对沙发照片但答成 L 形（官方 C 形），对毛巾架用途均答 unknown。餐厨对话题仅 2B 在 270p 回答 yes，另外五个配置均答 unknown。所有衣帽间对照均回答 unknown。由此可降低“单纯提高当前视角的像素数就会修复错误”的优先级。分辨率改变过一个回答；多住宅、小物体或文字题上的分辨率效应仍待配对验证。下一次可先用同一分辨率从另一角度拍摄完整沙发，请人核验轮廓是否清楚，再给两个模型读图。

逐题输出见 [2B 540p](results/openeqa-mac-2b-540p.json)、[4B 540p](results/openeqa-mac-4b-540p.json)、[2B 1080p](results/openeqa-mac-2b-1080p.json) 和 [4B 1080p](results/openeqa-mac-4b-1080p.json)。

同一住宅的两份 GLB 均包含 206 个网格，206 组顶点位置数组逐组字节哈希相同。相机升分辨率可以让已有几何和纹理占更多像素，桌子遮挡的沙发底边仍然不可见。三档输入在本机 MLX 实际预处理后，每张图分别为 120、510、2040 个视觉 token，每次四图对应 480、2040、8160 个。模型确实收到了更多视觉信息，处理成本也随之增加。

组内本机的 `runs/resolution/compare.png` 是等视场裁剪对比；`runs/resolution/1080/` 保存全图；`runs/resolution/hm3d-probe-inputs-1080p.zip` 含 8 张推理原图及机位清单。Windows 解压到项目根目录后可运行以下命令，在 3060 6 GB 上取得真实显存和输出。

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check_windows_gpu.ps1 -Size 2 -Views runs/hm3d-views-1080p
```
