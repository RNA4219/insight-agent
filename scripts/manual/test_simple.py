"""Simple manual smoke script for Insight Agent."""

from pathlib import Path

from insight_core import run_insight

output_path = Path(__file__).resolve().parents[2] / "artifacts" / "manual-runs" / "test_output_simple.json"
output_path.parent.mkdir(parents=True, exist_ok=True)

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
for claim in response.claims:
    print(f"  - {claim.statement}")
print()
print(f"Limitations ({len(response.limitations)}):")
for limitation in response.limitations:
    print(f"  - {limitation.statement}")
print()
print(f"Problem Candidates ({len(response.problem_candidates)}):")
for candidate in response.problem_candidates:
    print(f"  [{candidate.decision.value}] {candidate.statement[:60]}...")

print()
print("-" * 50)
print("Done!")
output_path.write_text(response.model_dump_json(indent=2), encoding="utf-8")
print(f"Full output saved to {output_path}")
