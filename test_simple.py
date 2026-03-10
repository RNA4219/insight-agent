"""Simple test script for Insight Agent."""

from insight_core import run_insight
import json

# Simple test
print("Running Insight Agent...")
print("-" * 50)

response = run_insight(
    sources=[{
        "source_id": "test_001",
        "content": "The model achieved 92% accuracy on the benchmark dataset. However, it was only tested on English text."
    }],
    domain="machine_learning"
)

print(f"Status: {response.run.status.value}")
print(f"Run ID: {response.run.run_id}")
print(f"Confidence: {response.confidence:.2f}")
print()
print(f"Claims ({len(response.claims)}):")
for c in response.claims:
    print(f"  - {c.statement}")
print()
print(f"Limitations ({len(response.limitations)}):")
for l in response.limitations:
    print(f"  - {l.statement}")
print()
print(f"Problem Candidates ({len(response.problem_candidates)}):")
for p in response.problem_candidates:
    print(f"  [{p.decision.value}] {p.statement[:60]}...")

print()
print("-" * 50)
print("Done!")

# Save full output
with open("test_output.json", "w", encoding="utf-8") as f:
    f.write(response.model_dump_json(indent=2))
print("Full output saved to test_output.json")