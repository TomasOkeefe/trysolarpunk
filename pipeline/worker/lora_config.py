"""Write the LTX trainer config for a video-only character LoRA on our distilled LTX-2.5 transformer.

usage: python lora_config.py MODELS_DIR TRAIN_DIR OUT_DIR STEPS VRAM_MIB > config.yaml
Under ~70 GB of VRAM the transformer is quantized to int8 so it fits a 48 GB card (slower).
"""
import json
import sys

L, T, OUT, steps, vram = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5] or 0)
small = vram < 70000
cfg = {
    "model": {
        "model_path": f"{L}/diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors",
        "text_encoder_path": f"{L}/text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors",
        "video_vae_path": f"{L}/vae/ltx-2.5-video-vae-conv-bf16.safetensors",
        "training_mode": "lora", "load_checkpoint": None,
    },
    "lora": {"rank": 32, "alpha": 32, "dropout": 0.0,
             "target_modules": [f"attn{a}.{m}" for a in (1, 2) for m in ("to_k", "to_q", "to_v", "to_out.0")]},
    "training_strategy": {"name": "flexible", "video": {"is_generated": True, "latents_dir": "latents"}},
    "optimization": {"learning_rate": 1e-4, "steps": steps, "batch_size": 1, "gradient_accumulation_steps": 1,
                     "max_grad_norm": 1.0, "optimizer_type": "adamw8bit" if small else "adamw",
                     "scheduler_type": "linear", "scheduler_params": {}, "enable_gradient_checkpointing": True},
    "acceleration": {"mixed_precision_mode": "bf16", "quantization": "int8-quanto" if small else None,
                     "load_text_encoder_in_8bit": False, "offload_optimizer_during_validation": False},
    "data": {"preprocessed_data_root": f"{T}/.precomputed", "num_dataloader_workers": 2},
    "validation": {"prompts": [], "interval": None, "skip_initial_validation": True},
    "checkpoints": {"interval": 250, "keep_last_n": -1, "precision": "bfloat16"},
    "flow_matching": {"timestep_sampling_mode": "shifted_logit_normal", "timestep_sampling_params": {}},
    "hub": {"push_to_hub": False, "hub_model_id": None},
    "wandb": {"enabled": False},
    "seed": 42,
    "output_dir": OUT,
}
print(json.dumps(cfg, indent=1))  # JSON is valid YAML
