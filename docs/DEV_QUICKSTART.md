# DEV QUICKSTART
Instructions to get local environment set up for development and contributing.

## Get Started

**Code Conventions and pre-commit**

This repo is set up to use black for code formatting. Before you start development, please do the following:

<details>
<summary>Install pre-commit (Mac)</summary>
Run the following:

```bash
# Homebrew
brew install pre-commit
# Pip
pip install pre-commit

cd bgmp-kokoro-fastapi
pre-commit install
```
</details>
<br>

This will just run a code formatter every time you commit changes to the repo to maintain consistent formatting across the codebase. If there are any formatting issues, it will fix them, then you just need to rerun ```git add``` and ```git commit```.

**Run the API locally**

<details>
<summary>Quickest Start (docker run)</summary>

Pre-built multi-arch images with models baked in. 

`:latest` is available, but please pin to a release tag for stable usage.

| Your hardware | Image |
|---|---|
| No GPU (any laptop, VPS, CPU-only server) | `kokoro-fastapi-cpu:latest` |
| Apple Silicon (M1/M2/M3) | `kokoro-fastapi-cpu:latest` in Docker, or `./start-gpu_mac.sh` natively for MPS |
| NVIDIA GTX 9xx, 10xx, 20xx, 30xx, 40xx (x86_64) | `kokoro-fastapi-gpu:latest-cu126` or `kokoro-fastapi-gpu:latest` |
| NVIDIA RTX 50-series / Blackwell (x86_64) | `kokoro-fastapi-gpu:latest-cu128` |
| NVIDIA on arm64 (Jetson, GH200) | `kokoro-fastapi-gpu:latest` (ships cu129, no cu126 arm64 wheels upstream) |
| AMD GPU | `kokoro-fastapi-rocm:latest` (experimental, x86_64 only) |

```bash
docker run -p 8880:8880 ghcr.io/remsky/kokoro-fastapi-cpu:latest                                       # CPU
docker run --gpus all -p 8880:8880 ghcr.io/remsky/kokoro-fastapi-gpu:latest                            # NVIDIA (x86_64 or arm64)
docker run --gpus all -p 8880:8880 ghcr.io/remsky/kokoro-fastapi-gpu:latest-cu128                      # NVIDIA Blackwell / RTX 50-series
docker run --device=/dev/kfd --device=/dev/dri -p 8880:8880 ghcr.io/remsky/kokoro-fastapi-rocm:latest  # AMD
```

Configuration via environment variables, see `core/config.py`. The `:latest` and `:latest-cu126` tags resolve to the same multi-arch image.

</details>

<details>

<summary>Quick Start (docker compose) </summary>

1. Install prerequisites, and start the service using Docker Compose (Full setup including UI):
   - Install [Docker](https://www.docker.com/products/docker-desktop/)
   - Clone the repository:
        ```bash
        git clone https://github.com/remsky/Kokoro-FastAPI.git
        cd Kokoro-FastAPI

        cd docker/gpu   # For NVIDIA GPU support
        # or cd docker/cpu   # For CPU support
        # or cd docker/rocm  # For AMD GPU (ROCm, experimental, amd64 only)
        docker compose up --build

        # *Note for Apple Silicon (M1/M2/M3) users:
        # The Docker GPU image is CUDA-only and won't run on Apple Silicon. With Docker, use `docker/cpu`.
        # For native MPS (Apple GPU) acceleration, run directly via UV with `./start-gpu_mac.sh`.

        cd ../..  # back to repo root for the paths below

        # Models will auto-download, but if needed you can manually download:
        python docker/scripts/download_model.py --output api/src/models/v1_0

        # Or run directly via UV:
        ./start-gpu.sh  # For GPU support
        ./start-cpu.sh  # For CPU support
        ```
</details>
<details>
<summary>Direct Run (via uv) </summary>

1. Install prerequisites ():
   - Install [astral-uv](https://docs.astral.sh/uv/)
   - Install [espeak-ng](https://github.com/espeak-ng/espeak-ng) in your system if you want it available as a fallback for unknown words/sounds. The upstream libraries may attempt to handle this, but results have varied.
   - Clone the repository:
        ```bash
        git clone https://github.com/remsky/Kokoro-FastAPI.git
        cd Kokoro-FastAPI
        ```
        
        Run the [model download script](https://github.com/remsky/Kokoro-FastAPI/blob/master/docker/scripts/download_model.py) if you haven't already
     
        Start directly via UV (with hot-reload)
        
        Linux and macOS
        ```bash
        ./start-cpu.sh OR
        ./start-gpu.sh 
        ```

        Windows
        ```powershell
        .\start-cpu.ps1 OR
        .\start-gpu.ps1 
        ```

</details>

<details open>
<summary> Up and Running? </summary>


Run locally as an OpenAI-Compatible Speech Endpoint
    
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8880/v1", api_key="not-needed"
)

with client.audio.speech.with_streaming_response.create(
    model="kokoro",
    voice="af_sky+af_bella", #single or multiple voicepack combo
    input="Hello world!"
  ) as response:
      response.stream_to_file("output.mp3")
```
  
- The API will be available at http://localhost:8880
- API Documentation: http://localhost:8880/docs

- Web Interface: http://localhost:8880/web

<div align="center" style="display: flex; justify-content: center; gap: 10px;">
  <img src="assets/docs-screenshot.png" width="42%" alt="API Documentation" style="border: 2px solid #333; padding: 10px;">
  <img src="assets/webui-screenshot.png" width="42%" alt="Web UI Screenshot" style="border: 2px solid #333; padding: 10px;">
</div>

</details>
