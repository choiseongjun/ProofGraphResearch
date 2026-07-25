# QLoRA fine-tuning

This is a GPU-only optional pipeline, not a replacement for RAG. Use it after collecting **human-reviewed** instruction/report pairs; never train on raw web search output.

```powershell
python .\finetune\prepare_dataset.py --input .\reviewed-reports.json --output .\finetune\data\research_sft.jsonl
docker compose --profile finetune run --rm --gpus all finetune python train_qlora.py --dataset data/research_sft.jsonl
```

For a notebook GPU, begin with Qwen 3B, 4-bit QLoRA, batch size 1. Keep a held-out evaluation set and compare citation validity, factual support, and executive usefulness against the base model before deployment.
