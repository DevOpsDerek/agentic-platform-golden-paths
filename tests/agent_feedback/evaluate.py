#!/usr/bin/env python3
"""Evaluate the checked-in synthetic agent PR feedback scenarios."""

from __future__ import annotations

import argparse
import json
import sys
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any


DEFAULT_CASES = Path(__file__).with_name("cases.json")
ALLOWED_PATHS = (
    ".github/**",
    "charts/**",
    "docs/**",
    "gitops/**",
    "policies/**",
    "tests/**",
    "Makefile",
    "README.md",
)


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_case(case: dict[str, Any]) -> None:
    required = {
        "id",
        "changed_files",
        "production_mutation",
        "agent_has_azure_deployment_access",
        "deterministic_validation",
        "ci_evidence",
        "review_state",
        "failure",
        "failure_diagnosis",
        "rollback",
        "human_override",
        "expected_status",
    }
    missing = required - case.keys()
    if missing:
        raise ValueError(f"case is missing fields: {', '.join(sorted(missing))}")
    if not _non_empty_string(case["id"]):
        raise ValueError("case id must be a non-empty string")
    if not isinstance(case["changed_files"], list):
        raise ValueError(f"{case['id']}: changed_files must be a list")
    if not isinstance(case["ci_evidence"], list):
        raise ValueError(f"{case['id']}: ci_evidence must be a list")
    for field in ("production_mutation", "agent_has_azure_deployment_access", "failure"):
        if not isinstance(case[field], bool):
            raise ValueError(f"{case['id']}: {field} must be a boolean")
    if not isinstance(case["deterministic_validation"], str) or case[
        "deterministic_validation"
    ] not in ("passed", "failed", "not_run"):
        raise ValueError(f"{case['id']}: invalid deterministic_validation")
    if not isinstance(case["review_state"], str) or case["review_state"] not in (
        "pending",
        "approved",
        "changes_requested",
    ):
        raise ValueError(f"{case['id']}: invalid review_state")
    if not isinstance(case["expected_status"], str) or case["expected_status"] not in (
        "blocked",
        "awaiting_human_review",
        "awaiting_repository_checks",
    ):
        raise ValueError(f"{case['id']}: invalid expected_status")
    override = case["human_override"]
    if override is not None and not isinstance(override, dict):
        raise ValueError(f"{case['id']}: human_override must be an object or null")
    if override is not None and (
        not isinstance(override.get("decision"), str)
        or override["decision"]
        not in (
            "request-changes",
            "exception-requested",
            "accepted-with-rationale",
        )
    ):
        raise ValueError(f"{case['id']}: invalid human override decision")


def _scope_allowed(changed_files: list[Any]) -> bool:
    return bool(changed_files) and all(
        _non_empty_string(path)
        and not path.startswith("/")
        and ".." not in Path(path).parts
        and any(fnmatchcase(path, pattern) for pattern in ALLOWED_PATHS)
        for path in changed_files
    )


def load_changed_files(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _override_recorded(value: Any) -> bool:
    if value is None:
        return True
    return isinstance(value, dict) and all(
        _non_empty_string(value.get(field))
        for field in ("decision", "reviewer", "rationale", "follow_up_or_expiry")
    )


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    _validate_case(case)
    failure_details_present = (
        _non_empty_string(case["failure_diagnosis"])
        and _non_empty_string(case["rollback"])
    )
    checks = [
        ("bounded_scope", _scope_allowed(case["changed_files"])),
        ("no_production_mutation", case["production_mutation"] is False),
        (
            "no_azure_deployment_access",
            case["agent_has_azure_deployment_access"] is False,
        ),
        ("deterministic_validation", case["deterministic_validation"] == "passed"),
        ("evaluation_set_identified", True),
        (
            "ci_evidence_captured",
            bool(case["ci_evidence"])
            and all(_non_empty_string(item) for item in case["ci_evidence"]),
        ),
        (
            "failure_diagnosis_and_rollback",
            not case["failure"] or failure_details_present,
        ),
        ("human_override_recorded", _override_recorded(case["human_override"])),
        ("human_review_not_changes_requested", case["review_state"] != "changes_requested"),
    ]
    failed_checks = [name for name, passed in checks if not passed]
    if failed_checks:
        status = "blocked"
    elif case["review_state"] == "approved":
        status = "awaiting_repository_checks"
    else:
        status = "awaiting_human_review"
    return {
        "id": case["id"],
        "status": status,
        "review_state": case["review_state"],
        "merge_eligible": False,
        "checks": [{"name": name, "passed": passed} for name, passed in checks],
        "failed_checks": failed_checks,
        "human_override_present": case["human_override"] is not None,
    }


def load_cases(path: Path) -> tuple[str, list[dict[str, Any]]]:
    dataset = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(dataset, dict) or not _non_empty_string(dataset.get("evaluation_set")):
        raise ValueError("evaluation set must have a non-empty evaluation_set identifier")
    cases = dataset.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("evaluation set must contain at least one case")
    if not all(isinstance(case, dict) for case in cases):
        raise ValueError("each evaluation case must be an object")
    case_ids = [case.get("id") for case in cases]
    if not all(_non_empty_string(case_id) for case_id in case_ids):
        raise ValueError("each evaluation case must have a non-empty string id")
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("evaluation case identifiers must be unique")
    return dataset["evaluation_set"], cases


def render_summary(
    evaluation_set: str,
    results: list[dict[str, Any]],
    proposal_scope: tuple[bool, int] | None,
) -> str:
    passed = sum(result["status"] == result["expected_status"] for result in results)
    blocked = sum(result["status"] == "blocked" for result in results)
    lines = [
        "## Synthetic agent PR feedback evaluation",
        "",
        f"- Evaluation set: `{evaluation_set}`",
        f"- Cases matching expected status: **{passed}/{len(results)}**",
        f"- Cases blocked by guardrails: **{blocked}/{len(results)}**",
        "- Merge authorization: **not granted by this evaluation**",
    ]
    if proposal_scope is not None:
        scope_passed, changed_file_count = proposal_scope
        lines.append(
            f"- PR changed-file scope: **{'passed' if scope_passed else 'blocked'}** "
            f"({changed_file_count} file(s))"
        )
    lines.extend(
        [
            "",
            "| Case | Observed status | Expected status | Guardrail failures |",
            "|---|---|---|---|",
        ]
    )
    for result in results:
        failed = ", ".join(result["failed_checks"]) or "none"
        lines.append(
            f"| `{result['id']}` | {result['status']} | "
            f"{result['expected_status']} | {failed} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument(
        "--summary",
        type=Path,
        help="append a Markdown run summary to this file (for GitHub Actions)",
    )
    parser.add_argument(
        "--changed-files-file",
        type=Path,
        help="check newline-separated paths from the proposed PR diff",
    )
    args = parser.parse_args()

    try:
        evaluation_set, cases = load_cases(args.cases)
        results = []
        for case in cases:
            result = evaluate_case(case)
            result["expected_status"] = case["expected_status"]
            results.append(result)
        proposal_scope = None
        if args.changed_files_file:
            changed_files = load_changed_files(args.changed_files_file)
            proposal_scope = (_scope_allowed(changed_files), len(changed_files))
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"Evaluation set error: {error}", file=sys.stderr)
        return 2

    summary = render_summary(evaluation_set, results, proposal_scope)
    print(summary, end="")
    if args.summary:
        with args.summary.open("a", encoding="utf-8") as summary_file:
            summary_file.write(summary)

    mismatches = [
        result
        for result in results
        if result["status"] != result["expected_status"]
    ]
    if mismatches or (proposal_scope is not None and not proposal_scope[0]):
        print(
            "Evaluation status mismatch: "
            + ", ".join(result["id"] for result in mismatches),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
