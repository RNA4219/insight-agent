```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.local/schemas/routing_plan.schema.json",
  "title": "routing_plan",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "lead_persona",
    "selected_personas",
    "skipped_personas",
    "role_assignments",
    "routing_reason",
    "skip_reasons",
    "routing_confidence"
  ],
  "properties": {
    "lead_persona": {
      "type": "string",
      "minLength": 1,
      "description": "The persona acting as the lead router for this run."
    },
    "problem_type": {
      "type": "string",
      "minLength": 1,
      "description": "Optional coarse-grained problem classification used for routing."
    },
    "evidence_density": {
      "type": "string",
      "enum": ["low", "medium", "high"],
      "description": "Estimated evidence density for the current input."
    },
    "selected_personas": {
      "type": "array",
      "description": "Personas selected for downstream invocation.",
      "minItems": 1,
      "uniqueItems": true,
      "items": {
        "type": "string",
        "minLength": 1
      }
    },
    "skipped_personas": {
      "type": "array",
      "description": "Personas explicitly not selected for this run.",
      "uniqueItems": true,
      "items": {
        "type": "string",
        "minLength": 1
      }
    },
    "role_assignments": {
      "type": "object",
      "description": "Assigned role for each selected persona.",
      "minProperties": 1,
      "additionalProperties": {
        "type": "string",
        "enum": [
          "evidence_checker",
          "hypothesis_refiner",
          "operational_risk_reviewer",
          "structural_abstraction",
          "novelty_probe"
        ]
      }
    },
    "routing_reason": {
      "type": "array",
      "description": "Human-readable reasons for persona selection.",
      "minItems": 1,
      "items": {
        "type": "string",
        "minLength": 1
      }
    },
    "skip_reasons": {
      "type": "object",
      "description": "Reason map for skipped personas.",
      "additionalProperties": {
        "type": "string",
        "minLength": 1
      }
    },
    "routing_confidence": {
      "type": "number",
      "minimum": 0,
      "maximum": 1,
      "description": "Confidence score for the routing decision."
    }
  },
  "allOf": [
    {
      "description": "Every selected persona must have an assigned role.",
      "properties": {
        "selected_personas": {
          "type": "array"
        },
        "role_assignments": {
          "type": "object"
        }
      }
    }
  ],
  "$comment": "Cross-field constraints such as 'all selected_personas must appear as keys in role_assignments' and 'selected_personas and skipped_personas must not overlap' should be enforced in application logic if the validator does not support custom keywords."
}
```

## 補足

この schema で表現できているのは主に次です。

* `lead_persona` は必須
* `selected_personas` は1件以上必須
* `skipped_personas` は配列
* `role_assignments` は persona ごとの役割マップ
* `routing_reason` は最低1件
* `routing_confidence` は 0〜1

一方で、**JSON Schema 単体では表現しにくい制約**が2つあります。

1. `selected_personas` に入っている全 persona が `role_assignments` の key に存在すること
2. `selected_personas` と `skipped_personas` が重複しないこと

なので、この2つは要件上は **application logic で検証**する前提にするのが現実的です。

## そのまま使えるサンプル

```json
{
  "lead_persona": "bright_generalist",
  "problem_type": "evaluation_gap",
  "evidence_density": "low",
  "selected_personas": [
    "data_researcher",
    "operator",
    "researcher"
  ],
  "skipped_personas": [
    "curiosity_entertainer",
    "strategist"
  ],
  "role_assignments": {
    "data_researcher": "evidence_checker",
    "operator": "operational_risk_reviewer",
    "researcher": "hypothesis_refiner"
  },
  "routing_reason": [
    "single-metric evaluation concern is dominant",
    "evidence density is low, so fan-out is constrained",
    "operational misread risk is material"
  ],
  "skip_reasons": {
    "curiosity_entertainer": "novelty contribution is low for this input",
    "strategist": "insufficient evidence for higher-order escalation"
  },
  "routing_confidence": 0.82
}