import json
import os
from pathlib import Path
from typing import Dict, Any, Optional


def extract_model_config(config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract the relevant model configuration, handling both flat and nested structures.

    Args:
        config: Full configuration dictionary

    Returns:
        Extracted model configuration or None if not found
    """
    # Check if it's a multimodal model with text_config
    if "text_config" in config:
        return config["text_config"]

    # Otherwise, assume it's a flat configuration
    return config


def calculate_kv_cache(config: Dict[str, Any], seq_len: int = 32768) -> Dict[str, Any]:
    """
    Calculate KV Cache memory requirements for a given model configuration.

    Args:
        config: Model configuration dictionary
        seq_len: Sequence length (default: 32768 tokens)

    Returns:
        Dictionary with calculation results
    """
    # Extract the relevant config (handle nested structures)
    model_config = extract_model_config(config)

    if model_config is None:
        raise ValueError("Could not extract model configuration")

    # Extract necessary parameters
    num_layers = model_config.get("num_hidden_layers", 0)
    num_kv_heads = model_config.get("num_key_value_heads", model_config.get("num_attention_heads", 0))
    head_dim = model_config.get("head_dim")

    # Calculate head_dim if not provided
    if head_dim is None:
        hidden_size = model_config.get("hidden_size", 0)
        num_attention_heads = model_config.get("num_attention_heads", 1)
        head_dim = hidden_size // num_attention_heads if num_attention_heads > 0 else 0

    # Determine bytes per parameter based on dtype
    # Check both at root level and in model_config
    dtype = config.get("torch_dtype") or model_config.get("dtype") or model_config.get("text_config").get("dtype")
    bytes_per_param = {
        "float32": 4,
        "float16": 2,
        "bfloat16": 2,
        "int8": 1,
        "int4": 0.5
    }.get(dtype, 4)

    # Calculate KV Cache
    # Formula: 2 (K and V) × num_layers × seq_len × num_kv_heads × head_dim × bytes_per_param
    kv_cache_bytes = 2 * num_layers * seq_len * num_kv_heads * head_dim * bytes_per_param

    # Convert to different units
    kv_cache_gb = kv_cache_bytes / (1024 ** 3)
    kv_cache_mb = kv_cache_bytes / (1024 ** 2)

    # Determine architecture type
    arch_type = config.get("model_type", "unknown")
    if "text_config" in config:
        arch_type = f"{arch_type} (multimodal - text only)"

    return {
        "bytes": int(kv_cache_bytes),
        "mb": round(kv_cache_mb, 2),
        "gb": round(kv_cache_gb, 2),
        "num_layers": num_layers,
        "num_kv_heads": num_kv_heads,
        "head_dim": head_dim,
        "dtype": dtype,
        "seq_len": seq_len,
        "arch_type": arch_type
    }


def process_configs(configs_dir: str = "configs", seq_len: int = 32768):
    """
    Process all .json files in the specified directory.

    Args:
        configs_dir: Directory containing .json files (nomDuModele.json)
        seq_len: Sequence length for KV cache calculation
    """
    configs_path = Path(configs_dir)

    if not configs_path.exists():
        print(f"❌ Directory '{configs_dir}' not found!")
        return

    # Find all .json files in the directory (not recursive)
    config_files = list(configs_path.glob("*.json"))

    if not config_files:
        print(f"❌ No .json files found in '{configs_dir}'")
        return

    print(f"📁 Found {len(config_files)} config file(s) in '{configs_dir}'\n")
    print("=" * 100)

    results = []

    for config_file in sorted(config_files):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # Get model name from filename (remove .json extension)
            model_name = config_file.stem

            # Calculate KV cache
            kv_info = calculate_kv_cache(config, seq_len)

            # Store results
            results.append({
                "model": model_name,
                "file": config_file.name,
                **kv_info
            })

            # Print results
            print(f"\n🤖 Model: {model_name}")
            print(f"   File: {config_file.name}")
            print(f"   Architecture: {kv_info['arch_type']}")
            print(f"   Layers: {kv_info['num_layers']}")
            print(f"   KV Heads: {kv_info['num_kv_heads']}")
            print(f"   Head Dim: {kv_info['head_dim']}")
            print(f"   Dtype: {kv_info['dtype']}")
            print(f"   📊 KV Cache ({seq_len:,} tokens):")
            print(f"      • {kv_info['gb']:.2f} GB")
            print(f"      • {kv_info['mb']:.2f} MB")
            print(f"      • {kv_info['bytes']:,} bytes, {kv_info['head_dim']} * {kv_info['num_kv_heads']} * {kv_info['num_layers']} * {seq_len} * 2 * {kv_info['dtype']} bytes")
            print("-" * 100)

        except json.JSONDecodeError:
            print(f"❌ Error reading {config_file.name}: Invalid JSON")
        except Exception as e:
            print(f"❌ Error processing {config_file.name}: {str(e)}")

    # Summary
    if results:
        print(f"\n📈 SUMMARY")
        print("=" * 100)
        results_sorted = sorted(results, key=lambda x: x['gb'], reverse=True)

        print(f"\n{'Model':<40} {'Layers':<8} {'KV Heads':<10} {'KV Cache (GB)':<15}")
        print("-" * 100)
        for r in results_sorted:
            print(f"{r['model']:<40} {r['num_layers']:<8} {r['num_kv_heads']:<10} {r['gb']:<15.2f}")

        print(f"\n✅ Total models analyzed: {len(results)}")
        print(f"📊 Average KV Cache: {sum(r['gb'] for r in results) / len(results):.2f} GB")
        print(
            f"📈 Max KV Cache: {max(r['gb'] for r in results):.2f} GB ({max(results, key=lambda x: x['gb'])['model']})")
        print(
            f"📉 Min KV Cache: {min(r['gb'] for r in results):.2f} GB ({min(results, key=lambda x: x['gb'])['model']})")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Calculate KV Cache for model configurations")
    parser.add_argument("--dir", default="configs", help="Directory containing .json files")
    parser.add_argument("--seq-len", type=int, default=32768, help="Sequence length (default: 32768)")

    args = parser.parse_args()

    process_configs(args.dir, args.seq_len)