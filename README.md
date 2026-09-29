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
  controls. Argo CD loads developer values first and platform values second, so
  platform values take precedence.
- `policies/kyverno/require-secure-workloads.yaml` enforces the core workload
  controls at admission. The intentionally failing example is
  `tests/kyverno/noncompliant-pod.yaml`.

The Argo CD example targets a non-production demo namespace. Configure the
repository URL and revision for your fork before applying it. Repository
permissions should prevent service developers from editing platform values or
the policy; Helm value precedence is not a substitute for Git authorization.

## Safe customization and image trust

Developers may change the application image, replica count, service port, and
approved application metadata in their values file. Do not weaken pod or
container security, resource requests/limits, probes, or image policy in
developer-owned values. Platform owners review changes to `platform.yaml`,
chart security defaults, Argo CD project/sync settings, and Kyverno policy.

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

Run `make validate` to lint and render the chart and verify its secure defaults.
It needs Helm but no Azure credentials, cluster, or image pull. If the Kyverno
CLI is installed, this also runs the offline policy tests:

```sh
kyverno test tests/kyverno
```

The tests expect the compliant fixture to pass and the deliberately
non-compliant fixture to fail. For a live admission demonstration, install the
policy into a disposable test cluster and submit
`tests/kyverno/noncompliant-pod.yaml`; Kyverno must reject the Pod. Do not use
that fixture as a deployment manifest.
