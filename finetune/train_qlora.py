"""GPU-only QLoRA SFT for the report-writing agent. Run after human review of examples."""
import argparse
from datasets import load_dataset
from peft import LoraConfig
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from trl import SFTConfig, SFTTrainer

parser = argparse.ArgumentParser()
parser.add_argument("--model", default="Qwen/Qwen2.5-3B-Instruct")
parser.add_argument("--dataset", default="data/research_sft.jsonl")
parser.add_argument("--output", default="output/proofgraph-qlora")
parser.add_argument("--epochs", type=int, default=2)
args = parser.parse_args()

tokenizer = AutoTokenizer.from_pretrained(args.model, use_fast=True)
tokenizer.pad_token = tokenizer.eos_token
model = AutoModelForCausalLM.from_pretrained(
    args.model, device_map="auto", quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4"),
)
dataset = load_dataset("json", data_files=args.dataset, split="train")
trainer = SFTTrainer(
    model=model, tokenizer=tokenizer, train_dataset=dataset,
    formatting_func=lambda row: tokenizer.apply_chat_template(row["messages"], tokenize=False),
    peft_config=LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, target_modules=["q_proj", "k_proj", "v_proj", "o_proj"]),
    args=SFTConfig(output_dir=args.output, num_train_epochs=args.epochs, per_device_train_batch_size=1, gradient_accumulation_steps=8, learning_rate=2e-4, logging_steps=5, save_strategy="epoch", report_to="none"),
)
trainer.train(); trainer.save_model(args.output); tokenizer.save_pretrained(args.output)
