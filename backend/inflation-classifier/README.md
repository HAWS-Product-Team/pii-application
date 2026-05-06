# Dependencies
The standard library: 🤗 Transformers

The go-to is Hugging Face's transformers library. It's the central hub for downloading, loading, and running pretrained models. 
For this use case, use its pipeline API, which is a high-level wrapper that handles tokenization, inference, and decoding in one call.

What's needed and why:
transformers — the HF library itself, has the pipeline and model classes
PyTorch — Transformers supports PyTorch and JAX; PyTorch is the default and most widely supported
datasets — optional but useful HF library for loading/processing data cleanly
accelerate — HF library that handles device management (CPU/GPU/MPS); transformers will ask for it

# PyTorch and GPUs
## Mac
If you're on a Mac with Apple Silicon, PyTorch will automatically use the MPS (Metal) backend which gives you a meaningful speedup over CPU — no extra config needed.
```uv add transformers torch accelerate datasets```

There is a configuration parameter in the code for Metal (Apple Silicon), versus CPU/GPU.  My experiance has been that explicitly
setting the device to "mps" didn't make a difference, and per the above paragraph, it will automatically use MPS if available.
```python
    # Load the zero-shot pipeline
    # device=0 uses GPU if available, remove or set device="cpu" to force CPU
    classifier = pipeline(
        "zero-shot-classification",
        model="facebook/bart-large-mnli",
        device=0  # or "mps" on Apple Silicon, or "cpu"
    )
```

## Regarding GPU support with torch,
If you're on Linux with an NVIDIA GPU, replace torch with:
```uv add transformers accelerate datasets```
```uv add torch --index-url https://download.pytorch.org/whl/cu121```
Note: Adjust cu121 to match your CUDA version.

# How to run the CLI
The first step gets the dependencies installed. The second step runs the CLI.

From the UV project root (inflation-classifier directory):
1. uv sync
2. uv run inflation_classifier [--help, --list-wrong] path-to-csv-file

Example: ```uv run inflation-classifier ../tests/data/small\ test\ set/synthetic_purchases_2024_evaluation_data.csv```

## WIP
Test running inference against S3.  Need to sort out S3 creation and wether to use env variables or commandline args
to pass argument to the inferencer.
