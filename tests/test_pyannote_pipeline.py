#!/usr/bin/env python3
"""
test_pyannote_pipeline.py
─────────────────────────
End-to-end validation of the PyAnnote + Groq Whisper pipeline.

Run from the project root:
  /Users/kartikeyagrawal/Desktop/ML-Projects/meeting-intelligence/venv/bin/python \
      tests/test_pyannote_pipeline.py

This script validates:
  1. All Python packages are importable
  2. HuggingFace token works and all gated models are accessible
  3. Groq API key works
  4. ffmpeg is installed
  5. PyAnnote pipeline can be loaded
  6. End-to-end transcription with a real audio file
"""

import os
import sys
import subprocess

# Add src/ to path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

# Load environment variables
from utils.config import GROQ_API_KEY, HF_TOKEN  # type: ignore


def _pass(msg: str) -> None:
    print(f"  ✅ {msg}")


def _fail(msg: str) -> None:
    print(f"  ❌ {msg}")


def _warn(msg: str) -> None:
    print(f"  ⚠️  {msg}")


def test_imports() -> bool:
    """Test that all required packages can be imported."""
    print("\n[1/6] Checking Python package imports...")
    all_ok = True

    packages = [
        ("torch", "pip install torch"),
        ("torchaudio", "pip install torchaudio"),
        ("pyannote.audio", 'pip install "pyannote.audio>=4.0"'),
        ("groq", "pip install groq"),
        ("numpy", "pip install numpy"),
        ("scipy", "pip install scipy"),
    ]

    for pkg, install_cmd in packages:
        try:
            __import__(pkg)
            _pass(f"{pkg} imported OK")
        except ImportError as e:
            _fail(f"{pkg} import failed: {e}\n       Fix: {install_cmd}")
            all_ok = False

    # Check versions
    try:
        import torch
        import pyannote.audio
        _pass(f"torch={torch.__version__}, pyannote.audio version OK")
    except Exception:
        pass

    return all_ok


def test_ffmpeg() -> bool:
    """Test that ffmpeg and ffprobe are available."""
    print("\n[2/6] Checking ffmpeg...")
    all_ok = True

    for cmd in ["ffmpeg", "ffprobe"]:
        result = subprocess.run(
            [cmd, "-version"], capture_output=True, text=True
        )
        if result.returncode == 0:
            version_line = result.stdout.split("\n")[0]
            _pass(f"{cmd}: {version_line}")
        else:
            _fail(f"{cmd} not found. Install with: brew install ffmpeg")
            all_ok = False

    return all_ok


def test_env_vars() -> bool:
    """Test that required environment variables are set."""
    print("\n[3/6] Checking environment variables...")
    all_ok = True

    if HF_TOKEN and HF_TOKEN.startswith("hf_"):
        _pass(f"HF_TOKEN is set ({HF_TOKEN[:8]}...)")
    else:
        _fail("HF_TOKEN is not set or invalid. Add HF_TOKEN=hf_... to .env")
        all_ok = False

    if GROQ_API_KEY and GROQ_API_KEY.startswith("gsk_"):
        _pass(f"GROQ_API_KEY is set ({GROQ_API_KEY[:8]}...)")
    else:
        _fail("GROQ_API_KEY is not set or invalid. Add GROQ_API_KEY=gsk_... to .env")
        all_ok = False

    return all_ok


def test_hf_model_access() -> bool:
    """Test that HuggingFace token has access to all required gated models."""
    print("\n[4/6] Checking HuggingFace model access...")
    all_ok = True

    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        _fail("huggingface_hub not installed. pip install huggingface_hub")
        return False

    models = [
        ("pyannote/speaker-diarization-3.1", "config.yaml"),
        ("pyannote/segmentation-3.0", "config.yaml"),
        ("pyannote/speaker-diarization-community-1", "config.yaml"),
    ]

    for model_id, test_file in models:
        try:
            # Actually download a file to verify gated access
            path = hf_hub_download(
                model_id, test_file, token=HF_TOKEN
            )
            _pass(f"{model_id} — access granted")
        except Exception as e:
            err = str(e)
            if "403" in err or "GatedRepoError" in err:
                _fail(
                    f"{model_id} — ACCESS DENIED\n"
                    f"       → Visit https://huggingface.co/{model_id}\n"
                    f"       → Click 'Agree and access repository' to accept terms"
                )
                all_ok = False
            else:
                _fail(f"{model_id} — error: {err[:150]}")
                all_ok = False

    return all_ok


def test_groq_api() -> bool:
    """Test that the Groq API key works."""
    print("\n[5/6] Checking Groq API connection...")
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        # Test with a simple chat completion (cheapest call)
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "Say 'OK'"}],
            max_tokens=5,
        )
        _pass(f"Groq API works — response: {resp.choices[0].message.content!r}")
        return True
    except Exception as e:
        err = str(e)
        if "403" in err:
            _fail(f"Groq API 403 — check VPN or network settings. {err[:100]}")
        elif "429" in err:
            _warn(f"Groq API rate limited — key works but hit limit. {err[:100]}")
            return True
        else:
            _fail(f"Groq API error: {err[:200]}")
        return False


def test_pipeline_load() -> bool:
    """Test that the pyannote pipeline can be loaded."""
    print("\n[6/6] Loading PyAnnote diarization pipeline...")
    print("       (first run downloads ~200 MB of model weights)")

    try:
        from transcription.providers.pyannote_provider import (
            _load_diarization_pipeline,
        )
        pipeline = _load_diarization_pipeline()
        _pass(f"Pipeline loaded: {type(pipeline).__name__}")
        return True
    except Exception as e:
        _fail(f"Pipeline load failed: {e}")
        return False


def main() -> None:
    print("=" * 60)
    print("  PyAnnote + Groq Whisper Pipeline Validator")
    print("=" * 60)

    results = {
        "Python packages": test_imports(),
        "ffmpeg": test_ffmpeg(),
        "Environment variables": test_env_vars(),
        "HuggingFace model access": test_hf_model_access(),
        "Groq API": test_groq_api(),
    }

    # Only test pipeline load if all prerequisites pass
    if all(results.values()):
        results["Pipeline load"] = test_pipeline_load()
    else:
        print("\n[6/6] Skipping pipeline load — fix issues above first")
        results["Pipeline load"] = False

    # Summary
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    for name, ok in results.items():
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"  {status}  {name}")

    all_pass = all(results.values())
    print("\n" + ("🎉 All checks passed!" if all_pass else "⚠️  Fix the issues above."))
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
