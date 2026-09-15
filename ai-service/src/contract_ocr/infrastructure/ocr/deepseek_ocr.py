import io
from contextlib import redirect_stdout
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
from PIL import Image

from contract_ocr.application.ports.ocr_engine import EngineUnavailable, OCREngine
from contract_ocr.domain.entities import Context, Line, OCRResult


class DeepSeekOCRAdapter(OCREngine):
    """Local-only inference. Raw grounding is retained but not treated as word geometry."""

    name = "deepseek_ocr"

    def __init__(self, **config: Any) -> None:
        self.config = config
        self.model = config.get("model", "deepseek-ai/DeepSeek-OCR-2")
        self.backend = config.get("backend", "transformers")
        self.prompt = config.get(
            "prompt", "<image>\n<|grounding|>Convert the document to markdown."
        )
        self.runtime_info = {
            "backend": self.backend,
            "model": self.model,
            "cuda_device": config.get("device", "cuda:0"),
            "gpu_name": None,
        }
        self._engine = None
        self._unavailable = None

    def _load(self) -> None:
        if self._unavailable:
            raise EngineUnavailable(self._unavailable)
        if self._engine is not None:
            return
        start = perf_counter()
        try:
            if not self.config.get("enabled", True):
                raise RuntimeError("DeepSeek disabled in configuration")
            import torch

            if not torch.cuda.is_available():
                raise RuntimeError("NVIDIA CUDA is unavailable")
            self.runtime_info["gpu_name"] = torch.cuda.get_device_name(
                self.runtime_info["cuda_device"]
            )
            if self.backend == "transformers":
                from transformers import AutoModel, AutoTokenizer

                kwargs = {
                    "trust_remote_code": True,
                    "local_files_only": not self.config.get("allow_download", False),
                }
                if self.config.get("revision"):
                    kwargs["revision"] = self.config["revision"]
                self._tokenizer = AutoTokenizer.from_pretrained(self.model, **kwargs)
                self._engine = (
                    AutoModel.from_pretrained(
                        self.model,
                        _attn_implementation=self.config.get("attention", "flash_attention_2"),
                        use_safetensors=True,
                        **kwargs,
                    )
                    .eval()
                    .to(self.runtime_info["cuda_device"])
                    .to(torch.bfloat16)
                )
            elif self.backend == "vllm":
                from huggingface_hub import snapshot_download
                from vllm import LLM

                local_model = self.model
                if not Path(local_model).is_dir():
                    local_model = snapshot_download(
                        self.model,
                        revision=self.config.get("revision"),
                        local_files_only=not self.config.get("allow_download", False),
                    )
                self._engine = LLM(
                    model=local_model,
                    trust_remote_code=True,
                    max_model_len=self.config.get("max_model_len", 8192),
                    gpu_memory_utilization=self.config.get("gpu_memory_utilization", 0.8),
                )
            else:
                raise ValueError(f"unsupported backend: {self.backend}")
        except Exception as exc:
            self._unavailable = f"DeepSeek unavailable: {type(exc).__name__}: {exc}"
            raise EngineUnavailable(self._unavailable) from exc
        finally:
            self.initialization_ms = (perf_counter() - start) * 1000

    def recognize_page(self, page_image: np.ndarray, context: Context) -> OCRResult:
        self._load()
        directory = Path(context.output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        image = Image.fromarray(page_image).convert("RGB")
        if self.backend == "vllm":
            from vllm import SamplingParams

            outputs = self._engine.generate(
                [{"prompt": self.prompt, "multi_modal_data": {"image": image}}],
                SamplingParams(temperature=0, max_tokens=self.config.get("max_tokens", 4096)),
                use_tqdm=False,
            )
            markdown = outputs[0].outputs[0].text
        else:
            image_path = directory / "input.png"
            image.save(image_path)
            stdout = io.StringIO()
            # Upstream infer can print document contents and return None.
            with redirect_stdout(stdout):
                result = self._engine.infer(
                    self._tokenizer,
                    prompt=self.prompt,
                    image_file=str(image_path),
                    output_path=str(directory),
                    base_size=1024,
                    image_size=768 if "OCR-2" in self.model else 640,
                    crop_mode=True,
                    save_results=True,
                )
            (directory / "inference_stdout.txt").write_text(stdout.getvalue(), encoding="utf-8")
            if isinstance(result, str):
                markdown = result
            elif (directory / "result.mmd").exists():
                markdown = (directory / "result.mmd").read_text(encoding="utf-8")
            else:
                raise RuntimeError(
                    "DeepSeek returned no text and no result.mmd; inspect raw output"
                )
        path = directory / "raw.md"
        path.write_text(markdown, encoding="utf-8")
        import torch

        self.runtime_info["gpu_peak_allocated_bytes"] = torch.cuda.max_memory_allocated(
            self.runtime_info["cuda_device"]
        )
        lines = [
            Line(line_id=f"{context.document_id}-p{context.page:03d}-l{i:04d}", text=text)
            for i, text in enumerate(markdown.splitlines(), 1)
            if text.strip()
        ]
        return OCRResult(lines=lines, raw_markdown=markdown, raw_output_path=str(path.resolve()))


DeepSeekOCREngine = DeepSeekOCRAdapter
