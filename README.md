# Secure service Helm golden path

This repository provides a small, GitOps-managed synthetic service example. The
Helm chart defaults to non-root execution, a RuntimeDefault seccomp profile,
read-only root filesystem, no added capabilities, no privilege escalation,
bounded CPU/memory, health probes, and Prometheus scrape annotations.

## Repository layout

- `charts/secure-service` is the reusable service chart.
- `gitops/argocd/secure-service.yaml` is an Argo CD `Application` that watches
  this repository and reconciles the chart from Git.
- `gitops/values/secure-service/developer.yaml` contains service-owned inputs;
  `platform.yaml` contains platform-owned image pull, resource, and security
  controls. Developers customize only the documented `developer` namespace;
  the platform file reapplies the complete `platform` namespace, and the chart
  schema rejects unknown keys in either namespace.
- `policies/kyverno/require-secure-workloads.yaml` enforces the core workload
  controls at admission. The intentionally failing example is
  `tests/kyverno/noncompliant-pod.yaml`.

The Argo CD example targets a non-production demo namespace. Configure the
repository URL and revision for your fork before applying it. A platform
administrator must first create the `golden-path-demo` namespace and apply
`gitops/argocd/secure-service-project.yaml`; then apply the Application. The
restricted AppProject permits only this repository, that namespace, and the
Deployment, Service, and ServiceAccount kinds used by the chart. It does not
permit cluster-scoped resources.

The included `.github/CODEOWNERS` requests platform-owner review for changes to
the chart, platform values, GitOps project, and admission policy. Configure
branch protection to require CODEOWNERS approval, and restrict writes to those
paths to platform owners. The chart's schema and value-file ordering are
additional guardrails, not substitutes for Git authorization.

## Safe customization and image trust

Developers may change only `developer.image.repository`, `developer.image.tag`
or `developer.image.digest`, `developer.replicaCount`, and
`developer.servicePort` in their values file. The schema rejects other developer
keys. Do not weaken pod or container security, resource requests/limits, probes,
or image policy in developer-owned values. Platform owners review changes to
`platform.yaml`, chart security defaults, Argo CD project/sync settings, and
Kyverno policy.

For production, build images in the approved pipeline and deploy an immutable
image digest rather than a mutable tag. Require provenance (for example, a
verifiable build attestation tied to the source revision) and a signature from
an approved workload identity; configure the cluster's Kyverno `verifyImages`
policy with the platform's trusted identity/key and registry rules. The sample
tag is illustrative and is not a signature or provenance claim. Never commit
registry credentials or signing keys to values files.

Overrides that cannot meet policy require a time-bounded, documented exception
approved by the platform/security owner. Record the workload, justification,
owner, compensating controls, and expiry; prefer a narrowly scoped namespace or
policy exception over weakening the shared policy. Remove the exception when
it expires or the workload is remediated.

## Validation without a cluster

Run `make validate` to lint and render the chart, verify its secure defaults,
and run the offline policy tests. It requires Helm and the Kyverno CLI but no
Azure credentials, cluster, or image pull:

```sh
kyverno test tests/kyverno
```

The tests expect the compliant fixture to pass and fixtures exercising
container-level overrides, init/ephemeral containers, privileged containers,
added capabilities, and invalid resource bounds to fail. For a live admission
demonstration, install the policy into a disposable test cluster and submit
`tests/kyverno/noncompliant-pod.yaml`; Kyverno must reject the Pod. Do not use
that fixture as a deployment manifest.

## Central automation adoption

`.github/workflows/validate-automation.yml` calls the published
[`DevOpsDerek/workflows` automation validator](https://github.com/DevOpsDerek/workflows/blob/57da3f99768c3403cb688b1729d3dfc146c7cd4b/docs/catalog.md)
at immutable commit `57da3f99768c3403cb688b1729d3dfc146c7cd4b`. It runs on pull
requests, pushes to `main`, or manual dispatch with only `contents: read` and
no inherited secrets. The central implementation lints Actions workflows and
uses gh-aw `v0.89.21` to validate source/compiled-lock consistency when gh-aw
sources exist. This repository currently has no runnable gh-aw sources or
locks, so the central check explicitly skips compilation; it is not a Helm
or admission-policy check.

The existing `make validate` remains the offline golden-path check. There were
no checked-in CI workflows before adoption (only GitHub-managed Copilot
workflows). The catalog's checked-script interface supports Go, Python, Node,
.NET, and Terraform, not this Bash/Helm/Kyverno toolchain; wrapping the existing
script in another language would not provide a matching central implementation.
A future central offline Helm/Kyverno interface should run the existing lint,
render, secure-default and override assertions, schema rejection checks, and
all 24 expected Kyverno rule results without cluster or cloud credentials.

Baseline validation is not green: Helm `4.3.0` passes the current lint/render
assertions, but Kyverno `1.19.1` rejects the test result field `resource`.
Kyverno `1.13.6` accepts the deprecated test schema but loads zero policies and
reports all 24 results as missing. Neither version is an approved working pin
for this repository. Resolve the fixture/policy compatibility and verify all
expected results before adopting a central policy-test toolchain; do not
suppress these failures or substitute workflow linting for policy validation.

An appropriate future gh-aw use case is a manually requested, repository-only,
read-only assessment of rendered manifests against the chart schema, documented
security defaults, and Kyverno rules. It should emit a bounded diagnostic report
through safe outputs for human review, not change the manifests or execute
deployment commands. The published catalog has no matching artifact-assessment
component: its test/documentation components propose draft PRs, and its CI
diagnosis component requires evidence from a completed triggering run. No
agentic workflow is enabled by this adoption. Any future consumer must use a
verified SHA-pinned central component, `inlined-imports: true`, and reviewed
source plus generated lock files, with read-only agent permissions and bounded
safe outputs.

Workflow and CODEOWNERS changes request platform-owner review. Require human
CODEOWNERS approval through branch protection before merging generated-artifact
changes; CODEOWNERS alone does not enforce approval. This is particularly
important because the Argo CD example watches `main` with automated sync,
pruning, and self-healing. Automation must never provision infrastructure,
apply manifests, publish, deploy, release, or autonomously merge.
