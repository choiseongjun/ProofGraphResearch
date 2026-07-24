"""Create instruction data from reviewed research report pairs.

Input JSON: [{"topic": ..., "audience": ..., "approved_report": ...}]
Output JSONL uses a portable chat schema accepted by the QLoRA trainer.
"""
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
parser.add_argument("--output", default="data/research_sft.jsonl")
args = parser.parse_args()

records = json.loads(Path(args.input).read_text(encoding="utf-8"))
output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
with output.open("w", encoding="utf-8") as file:
    for record in records:
        messages = [
            {"role": "system", "content": "You are an evidence-first Korean research analyst. Never invent citations."},
            {"role": "user", "content": f"주제: {record['topic']}\n독자: {record.get('audience', '임원')}\n근거 기반 심층 보고서를 작성하세요."},
            {"role": "assistant", "content": record["approved_report"]},
        ]
        file.write(json.dumps({"messages": messages}, ensure_ascii=False) + "\n")
print(f"Wrote {len(records)} reviewed examples to {output}")
