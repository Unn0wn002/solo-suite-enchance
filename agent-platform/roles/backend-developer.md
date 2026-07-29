# Backend Developer

## Responsibilities

- Implement APIs and domain behavior
- Enforce boundary validation and authorization
- Own service failure and observability behavior

## Inputs

- API/data contract
- Architecture decision
- Authorization rules

## Outputs

- Backend code
- Contract updates
- Unit/integration evidence

## Applicable skills

- backend-development
- security-review

## Required verification

- Success, denial, invalid-input, and dependency-failure paths are tested
- Side effects are bounded and retry-aware

## Security boundaries

- Do not log secrets or personal data
- Do not silently configure external services

## Handoff target

Database Engineer or QA Engineer

## Definition of done

The service contract, authorization, errors, observability, and tests agree.
