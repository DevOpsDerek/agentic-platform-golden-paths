import json
import tempfile
import unittest
from pathlib import Path

from evaluate import _scope_allowed, evaluate_case, load_cases, load_changed_files


CASES_FILE = Path(__file__).with_name("cases.json")


class EvaluateAgentFeedbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluation_set, cls.cases = load_cases(CASES_FILE)

    def test_documented_synthetic_cases_match_expected_status(self):
        self.assertEqual("BG-012-synthetic-v2", self.evaluation_set)
        for case in self.cases:
            with self.subTest(case=case["id"]):
                result = evaluate_case(case)
                self.assertEqual(case["expected_status"], result["status"])
                self.assertFalse(result["merge_eligible"])

    def test_human_override_does_not_bypass_failed_validation(self):
        case = next(
            case
            for case in self.cases
            if case["id"] == "failed-check-with-diagnosis-and-rollback"
        )
        result = evaluate_case(case)
        checks = {check["name"]: check["passed"] for check in result["checks"]}
        self.assertTrue(result["human_override_present"])
        self.assertFalse(checks["deterministic_validation"])
        self.assertEqual("blocked", result["status"])

    def test_azure_deployment_access_is_blocked(self):
        case = dict(self.cases[0])
        case["agent_has_azure_deployment_access"] = True
        case["expected_status"] = "blocked"
        result = evaluate_case(case)
        checks = {check["name"]: check["passed"] for check in result["checks"]}
        self.assertFalse(checks["no_azure_deployment_access"])
        self.assertEqual("blocked", result["status"])

    def test_human_approval_does_not_authorize_merge(self):
        case = dict(self.cases[0])
        case["review_state"] = "approved"
        case["expected_status"] = "awaiting_repository_checks"
        result = evaluate_case(case)
        self.assertEqual("awaiting_repository_checks", result["status"])
        self.assertFalse(result["merge_eligible"])

    def test_failure_without_diagnosis_and_rollback_is_blocked(self):
        case = dict(self.cases[0])
        case.update(failure=True, expected_status="blocked")
        result = evaluate_case(case)
        checks = {check["name"]: check["passed"] for check in result["checks"]}
        self.assertFalse(checks["failure_diagnosis_and_rollback"])
        self.assertEqual("blocked", result["status"])

    def test_incomplete_human_override_is_not_recorded(self):
        case = dict(self.cases[0])
        case["human_override"] = {
            "decision": "accepted-with-rationale",
            "reviewer": "reviewer",
            "rationale": "",
            "follow_up_or_expiry": "",
        }
        result = evaluate_case(case)
        checks = {check["name"]: check["passed"] for check in result["checks"]}
        self.assertFalse(checks["human_override_recorded"])
        self.assertEqual("blocked", result["status"])

    def test_missing_human_override_follow_up_is_not_recorded(self):
        case = dict(self.cases[0])
        case["human_override"] = {
            "decision": "accepted-with-rationale",
            "reviewer": "reviewer",
            "rationale": "Documented synthetic exception.",
        }
        result = evaluate_case(case)
        checks = {check["name"]: check["passed"] for check in result["checks"]}
        self.assertFalse(checks["human_override_recorded"])
        self.assertEqual("blocked", result["status"])

    def test_scope_rejects_parent_traversal(self):
        case = dict(self.cases[0])
        case["changed_files"] = ["charts/../../outside.txt"]
        result = evaluate_case(case)
        checks = {check["name"]: check["passed"] for check in result["checks"]}
        self.assertFalse(checks["bounded_scope"])
        self.assertEqual("blocked", result["status"])

    def test_feedback_harness_and_workflow_are_excluded_from_agent_scope(self):
        protected_files = [
            ".github/workflows/evaluate-agent-pr.yml",
            "tests/agent_feedback/evaluate.py",
            "tests/agent_feedback/cases.json",
            "tests/agent_feedback/test_evaluate.py",
        ]
        for protected_file in protected_files:
            with self.subTest(path=protected_file):
                self.assertFalse(_scope_allowed([protected_file]))

    def test_empty_or_unidentified_dataset_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            invalid = Path(temp_dir) / "cases.json"
            invalid.write_text(json.dumps({"evaluation_set": "", "cases": [{}]}))
            with self.assertRaises(ValueError):
                load_cases(invalid)

    def test_duplicate_case_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            invalid = Path(temp_dir) / "cases.json"
            invalid.write_text(
                json.dumps(
                    {
                        "evaluation_set": self.evaluation_set,
                        "cases": [self.cases[0], self.cases[0]],
                    }
                )
            )
            with self.assertRaises(ValueError):
                load_cases(invalid)

    def test_changed_pr_paths_are_read_from_diff_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            changed_files = Path(temp_dir) / "pr-files.txt"
            changed_files.write_text(
                "charts/secure-service/values.yaml\nREADME.md\n"
            )
            self.assertEqual(
                ["charts/secure-service/values.yaml", "README.md"],
                load_changed_files(changed_files),
            )


if __name__ == "__main__":
    unittest.main()
