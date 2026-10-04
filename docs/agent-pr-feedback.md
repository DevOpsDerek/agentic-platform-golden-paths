# Evaluated agent PR feedback loop

## Scope and trust boundary

The loop demonstrates review of bounded, synthetic golden-path or policy
proposals. An agent may propose a change in a pull request; it must not apply
manifests, provision infrastructure, deploy, or merge. The evaluation workflow
has only `contents: read`, uses no secrets, and runs on `pull_request` (never
`pull_request_target`). It checks out the base revision into a separate trusted
directory and runs evaluator code, tests, and case data from that revision.
The PR checkout is used only to obtain a changed-path list; its code is never
executed by the evaluation job. No Azure deployment credential or deployment
job is configured here.

The evaluation set is `tests/agent_feedback/cases.json`, version
`BG-012-synthetic-v2`. The Python evaluator and its unit tests are deterministic
and use only the standard library. They check bounded file scope, no production
mutation, no Azure deployment access, successful deterministic validation,
identified evaluation-set and CI evidence, human override recording, and
diagnosis/rollback evidence for a simulated failure. The cases and evidence
references are synthetic: passing them demonstrates evaluator behavior, not
the performance or safety of a live coding agent. The fixtures are not
measurements of changed-file contents or runtime permissions. The trusted
workflow separately checks the actual PR's changed path names against the
bounded path allowlist.

Run the evaluation locally:

```sh
python3 -m unittest discover -s tests/agent_feedback -p 'test_*.py' -v
python3 tests/agent_feedback/evaluate.py
```

The workflow publishes each run's case results and aggregate counts in its
GitHub Actions job summary. Preserve the pull request URL, head commit, run URL,
summary, and review outcome as the evidence record. A green evaluation is
necessary evidence for human review, not a merge authorization. This repository
change does not alter branch protections; repository owners must verify that
the intended checks and CODEOWNERS approvals are required by the existing
repository rules before treating any check as merge-blocking.
Even a fixture marked human-approved reports `awaiting_repository_checks`;
existing required checks and repository rules remain authoritative.
This workflow does not run `make validate`; run the repository's existing chart
and admission-policy validation separately with its approved toolchain. A green
synthetic evaluation is not evidence that those chart or policy tests passed.

## Review evidence and human overrides

For each actual agent-authored proposal, reviewers record the PR/head commit,
the evaluation-set version and result, the deterministic validation result,
and links to current-head CI runs. Record a human override in the PR discussion
or review summary with:

```text
Human override: <request-changes | exception-requested | accepted-with-rationale>
Reviewer: <human reviewer>
Rationale and scope: <why the automated result was overridden>
Follow-up or expiry: <specific owner and next action/date or exception expiry>
```

An override is an audit record, not a bypass: it cannot turn a failed
deterministic check into a pass, substitute for required review, or authorize a
merge or deployment. Exceptions to security policy still require the
time-bounded platform/security-owner approval described in the README. An
override without a non-empty follow-up or expiry is incomplete and fails the
evaluation.

Do not report productivity improvements from this synthetic suite. Its output
only describes the tested cases and their guardrail results.

## Failure diagnosis and rollback

When evaluation or CI fails:

1. Keep the failing run and head commit as evidence; identify the failed
   evaluation case/assertion or CI check and compare it with the documented
   expected result.
2. Check the changed-file scope, rendered/chart or policy validation output,
   and the linked check's logs. Record the observed cause and the reviewer
   decision; do not suppress the failed check or use an override as a bypass.
3. Before merge, request changes or close the PR. If a change was merged, revert
   it through a reviewed revert PR under the repository's normal rules.
4. If a human-approved deployment has already applied the change, the platform
   owner diagnoses the deployed revision and restores the last known-good
   immutable image/configuration through the separately approved deployment
   process. Record that approval and its resulting CI/deployment evidence.

The synthetic `failed-check-with-diagnosis-and-rollback` case checks that
failure evidence is recorded. It does not execute a real rollback. This
repository does not expose production deployment, branch-protection
configuration, or live Copilot-agent capabilities to this evaluation, so those
capabilities cannot be independently verified here.

The first PR that introduces this harness has no trusted evaluator on its base
revision. The workflow therefore fails closed instead of executing the PR's
evaluator or cases. This bootstrap PR's local synthetic run is not trusted CI
evidence; after the harness is present on the base branch, subsequent PR runs
execute the protected-base version and evaluate the proposed changed paths.

## Remaining trust blocker

GitHub loads a `pull_request` workflow definition from the PR merge ref. A PR
that changes this workflow can therefore replace or skip the guardrail steps,
even though the configured steps use evaluator code and cases from the base
revision. The workflow path is listed in the existing CODEOWNERS file, but no
required status checks are configured, and this task does not change
protections. No approved immutable reusable workflow or other protected
workflow source is available in this repository. Accordingly, this evaluation
report remains advisory/non-required; workflow-source integrity cannot be
guaranteed here without a separately approved protected-workflow mechanism.
