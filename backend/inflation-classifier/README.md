# Dependencies
The standard library: 🤗 Transformers
The go-to is Hugging Face's transformers library. It's the central hub for downloading, loading, and running pretrained models. For your use case you'll use its pipeline API, which is a high-level wrapper that handles tokenization, inference, and decoding in one call.
What you need and why:
transformers — the HF library itself, gives you the pipeline and model classes
torch — the ML backend. Transformers supports PyTorch and JAX; PyTorch is the default and most widely supported
datasets — optional but useful HF library for loading/processing data cleanly
accelerate — HF library that handles device management (CPU/GPU/MPS); transformers will ask for it

# PyTorch and GPUs
## Mac
If you're on a Mac with Apple Silicon, PyTorch will automatically use the MPS (Metal) backend which gives you a meaningful speedup over CPU — no extra config needed.
```uv add transformers torch accelerate datasets```

## Regarding GPU support with torch,
If you're on Linux with an NVIDIA GPU, replace torch with:
bashuv add transformers accelerate datasets
```uv add torch --index-url https://download.pytorch.org/whl/cu121```
Note: Adjust cu121 to match your CUDA version.

# How to run the CLI
The first step gets the dependencies installed. The second step runs the CLI.

From the UV project root (inflation-classifier directory):
1. uv sync
2. uv run inflation_classifier.py