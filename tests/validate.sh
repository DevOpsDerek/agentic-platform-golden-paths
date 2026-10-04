#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
chart="${root}/charts/secure-service"
rendered="$(mktemp)"
untrusted_values="$(mktemp)"
invalid_values="$(mktemp)"
trap 'rm -f "$rendered" "$untrusted_values" "$invalid_values"' EXIT

helm lint "$chart"
helm template secure-service "$chart" \
  --namespace golden-path-demo \
  --values "${root}/gitops/values/secure-service/developer.yaml" \
  --values "${root}/gitops/values/secure-service/platform.yaml" > "$rendered"

grep -q 'runAsNonRoot: true' "$rendered"
grep -q 'type: RuntimeDefault' "$rendered"
grep -q 'allowPrivilegeEscalation: false' "$rendered"
grep -q 'readOnlyRootFilesystem: true' "$rendered"
grep -q 'drop:' "$rendered"
grep -q -- '- ALL' "$rendered"
grep -q 'automountServiceAccountToken: false' "$rendered"
grep -q 'cpu: 100m' "$rendered"
grep -q 'memory: 128Mi' "$rendered"
grep -q 'livenessProbe:' "$rendered"
grep -q 'readinessProbe:' "$rendered"
grep -q 'startupProbe:' "$rendered"
grep -q 'prometheus.io/scrape: "true"' "$rendered"
if grep -q 'NET_ADMIN\|runAsUser: 0\|runAsNonRoot: false\|type: Unconfined' "$rendered"; then
  echo "Platform security settings were overridden by developer values." >&2
  exit 1
fi

cat > "$untrusted_values" <<'EOF'
platform:
  containerSecurityContext:
    runAsNonRoot: false
    runAsUser: 0
    seccompProfile:
      type: Unconfined
    capabilities:
      add:
        - NET_ADMIN
EOF
helm template secure-service "$chart" \
  --namespace golden-path-demo \
  --values "${root}/gitops/values/secure-service/developer.yaml" \
  --values "$untrusted_values" \
  --values "${root}/gitops/values/secure-service/platform.yaml" > "$rendered"
if grep -q 'NET_ADMIN\|runAsUser: 0\|runAsNonRoot: false\|type: Unconfined' "$rendered"; then
  echo "Platform security settings were overridden by developer values." >&2
  exit 1
fi

cat > "$invalid_values" <<'EOF'
developer:
  containerSecurityContext:
    runAsNonRoot: false
EOF
if helm template secure-service "$chart" \
  --namespace golden-path-demo \
  --values "${root}/gitops/values/secure-service/developer.yaml" \
  --values "$invalid_values" \
  --values "${root}/gitops/values/secure-service/platform.yaml" > /dev/null 2>&1; then
  echo "The chart schema accepted an unsupported developer value." >&2
  exit 1
fi

cat > "$invalid_values" <<'EOF'
platform:
  serviceAccount:
    create: false
    name: ""
EOF
if helm template secure-service "$chart" \
  --namespace golden-path-demo \
  --values "$invalid_values" > /dev/null 2>&1; then
  echo "The chart schema accepted a disabled ServiceAccount with an empty name." >&2
  exit 1
fi

if ! command -v kyverno >/dev/null 2>&1; then
  echo "Kyverno CLI is required to validate the admission policy; install it and rerun 'make validate'." >&2
  exit 1
fi
kyverno test "${root}/tests/kyverno"
