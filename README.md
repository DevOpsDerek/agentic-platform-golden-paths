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
