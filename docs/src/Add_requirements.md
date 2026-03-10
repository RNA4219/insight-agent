## Overview
This document defines additional requirements for persona routing in the Insight pipeline.
The goal is to replace the current all-persona evaluation flow with a lead-persona-driven routing flow that reduces noise, improves evidence fit, and keeps the system configurable.

## Objective
The system must introduce a lead persona that is responsible for selecting which downstream personas should be invoked for a given input.
The default lead persona is `bright_generalist`.

The routing design must satisfy the following goals:

- reduce unnecessary persona invocation
- improve fit between problem type and evaluator persona
- preserve explainability of routing decisions
- allow easy configuration changes without code modification
- keep a minimum audit path for grounding and operational realism

## Scope
These requirements apply only to persona selection and routing inside the Insight pipeline.
They do not redefine the existing claim extraction, limitation extraction, or evidence storage contracts, except where routing metadata must be added.

## Functional Requirements

### FR-ADD-001 Lead persona introduction
The system must always invoke exactly one lead persona before invoking any downstream evaluation personas.

### FR-ADD-002 Default lead persona
The default lead persona must be `bright_generalist`.

### FR-ADD-003 Configurable lead persona
The lead persona must be changeable through configuration or runtime options.
Changing the lead persona must not require code edits.

### FR-ADD-004 Lead persona responsibility
The lead persona must determine which downstream personas should be invoked for the current input.

The routing decision must consider at least:

- claims
- limitations
- assumptions, if any
- problem typing result, if available
- evidence density
- optional execution context

### FR-ADD-005 Routing plan output
The lead persona must return a structured `routing_plan`.

The `routing_plan` must include at least:

- `lead_persona`
- `selected_personas`
- `skipped_personas`
- `role_assignments`
- `routing_reason`
- `skip_reasons`
- `routing_confidence`

### FR-ADD-006 Role-based dispatch
The lead persona must assign a role to each selected downstream persona.

Supported roles may include:

- `evidence_checker`
- `hypothesis_refiner`
- `operational_risk_reviewer`
- `structural_abstraction`
- `novelty_probe`

The implementation may extend this list later.

### FR-ADD-007 Evidence-density-aware routing
The lead persona must reduce the number of invoked personas when evidence density is low.

Minimum expected behavior:

- low evidence density: usually 2 to 3 personas
- medium evidence density: usually 3 to 4 personas
- high evidence density: may expand if justified

### FR-ADD-008 Skip reason retention
The system must store explicit skip reasons for personas that were not selected.

### FR-ADD-009 Mandatory audit persona
The system must include at least one audit-oriented persona in the selected set, regardless of routing outcome, unless explicitly disabled by configuration.

Recommended audit personas:

- `data_researcher`
- `researcher`
- `operator`

### FR-ADD-010 Routing fallback
If the lead persona fails to return a valid `routing_plan`, the system must apply a fallback routing rule.

Recommended fallback:

- lead persona: `bright_generalist`
- downstream personas:
  - `data_researcher`
  - `operator`

### FR-ADD-011 Deterministic mode support
The routing layer should support a deterministic mode so that the same input and configuration produce stable routing results.

### FR-ADD-012 Routing metadata persistence
The system must persist routing metadata together with the run result so that the selected personas and reasons are traceable later.

## Non-Functional Requirements

### NFR-ADD-001 Explainability
A human reviewer must be able to understand why each persona was selected or skipped.

### NFR-ADD-002 Cost efficiency
The routing design should reduce average persona invocation count compared with the current all-persona flow.

### NFR-ADD-003 Evidence discipline
The routing layer must not treat weakly supported hypotheses as strongly grounded facts.
If evidence density is low, routing should favor audit and clarification roles over speculative expansion.

### NFR-ADD-004 Extensibility
New personas must be addable through configuration and routing rule updates without requiring major architectural changes.

### NFR-ADD-005 Isolation of responsibility
The lead persona is responsible for routing, not for replacing all downstream review work.
Downstream personas remain responsible for their assigned role outputs.

## Constraints

### CR-ADD-001 Lead persona bias control
The system must prevent the lead persona from selecting only personas that reinforce its own perspective.
At least one selected persona should serve as an independent audit or counterbalance role.

### CR-ADD-002 Novelty suppression by default
Novelty-heavy personas such as `curiosity_entertainer` must not be invoked by default for every input.
They should be selected only when the lead persona identifies a specific benefit.

### CR-ADD-003 Low-evidence suppression
When evidence density is low, the system must suppress excessive persona fan-out and reduce insight overreach.

## Execution Flow Changes

### Current flow
1. Extract evidence
2. Generate problem candidates
3. Invoke all personas
4. Aggregate scores
5. Generate insights

### Revised flow
1. Extract evidence
2. Estimate evidence density
3. Run problem typing, if available
4. Invoke lead persona
5. Receive `routing_plan`
6. Invoke only selected personas
7. Aggregate role-based outputs
8. Generate insights
9. Persist routing metadata

## Routing Plan Contract

### Example JSON
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
````

## Configuration Requirements

### Example YAML

```yaml
persona_routing:
  enabled: true
  lead_persona: bright_generalist
  lead_persona_mutable: true

  fallback_personas:
    - data_researcher
    - operator

  mandatory_audit_personas:
    - data_researcher

  max_personas_by_evidence_density:
    low: 3
    medium: 4
    high: 6

  routing_rules:
    evaluation_gap:
      preferred:
        - data_researcher
        - operator
        - researcher
      optional:
        - strategist

    generalization_gap:
      preferred:
        - researcher
        - strategist
        - data_researcher

    deployment_risk:
      preferred:
        - operator
        - strategist
        - researcher

    novelty_opportunity:
      preferred:
        - curiosity_entertainer
        - bright_generalist
```

## Acceptance Criteria

### AC-ADD-001

When no explicit configuration is given, the lead persona is `bright_generalist`.

### AC-ADD-002

When the lead persona is changed in configuration, the system uses the new lead persona without code modification.

### AC-ADD-003

For low-evidence inputs, the average number of invoked personas is lower than in the current all-persona design.

### AC-ADD-004

Every run stores a machine-readable `routing_plan`.

### AC-ADD-005

Every selected persona has an explicit assigned role.

### AC-ADD-006

At least one audit-oriented persona is included unless explicitly disabled.

### AC-ADD-007

If routing output is invalid, fallback routing is applied and recorded.

## Notes

This change intentionally treats `bright_generalist` as an orchestrator rather than a simple evaluator.
Its primary job is to shape the downstream review path, not to dominate final interpretation.
The routing layer should bias toward fewer, better-matched personas rather than broad parallel invocation.