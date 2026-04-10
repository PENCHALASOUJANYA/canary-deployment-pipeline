#!/usr/bin/env python3
"""
★ Smart Auto-Rollback Controller
─────────────────────────────────
Novel feature: Continuously polls the canary pod's /api/info endpoint,
computes a rolling error rate, and automatically:
  • Promotes  v2 → full rollout if error rate stays below threshold
  • Rolls back v2 → deletes canary deployment if error rate exceeds threshold

Usage: python3 scripts/health-check.py
"""

import subprocess
import time
import sys
import logging
from collections import deque

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("auto-rollback")

# ── Configuration ────────────────────────────────────────────
NAMESPACE        = "canary-demo"
CANARY_SVC       = "canary-app-svc"
STABLE_DEPLOY    = "app-stable"
CANARY_DEPLOY    = "app-canary"

MONITOR_DURATION = 60          # seconds to observe before making a decision
POLL_INTERVAL    = 5           # seconds between health checks
ERROR_THRESHOLD  = 0.05        # 5% → trigger rollback
PROMOTE_MIN_OK   = 10          # need at least this many successful checks to promote

window = deque(maxlen=MONITOR_DURATION // POLL_INTERVAL)


def kubectl(cmd: str) -> str:
    """Run a kubectl command and return stdout."""
    result = subprocess.run(
        f"kubectl {cmd}",
        shell=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def get_service_url() -> str:
    """Get the Minikube service URL."""
    url = kubectl(
        f"get svc {CANARY_SVC} -n {NAMESPACE} "
        f"-o jsonpath='{{.spec.clusterIP}}'"
    )
    return f"http://{url}/api/info"


def check_canary_health(url: str) -> bool:
    """
    Poll canary pod. Returns True if healthy, False if error.
    Uses kubectl exec to reach ClusterIP from inside the cluster.
    """
    result = subprocess.run(
        f'kubectl exec -n {NAMESPACE} '
        f'$(kubectl get pod -n {NAMESPACE} -l version=canary '
        f'-o jsonpath="{{.items[0].metadata.name}}") '
        f'-- wget -qO- http://localhost:5000/api/info 2>&1',
        shell=True, capture_output=True, text=True
    )
    success = result.returncode == 0 and '"status": "healthy"' in result.stdout
    return success


def promote_canary():
    """Scale stable down → 0, scale canary up to full (10 replicas)."""
    log.info("🚀  PROMOTING canary v2 to full deployment (10 replicas)...")
    kubectl(f"scale deployment {STABLE_DEPLOY} --replicas=0 -n {NAMESPACE}")
    kubectl(f"scale deployment {CANARY_DEPLOY} --replicas=10 -n {NAMESPACE}")
    # Rename canary to stable for clarity
    kubectl(
        f"set image deployment/{CANARY_DEPLOY} "
        f"app=YOUR_DOCKERHUB_USER/canary-app:v2 -n {NAMESPACE}"
    )
    log.info("✅  Promotion complete. v2 is now serving 100% traffic.")


def rollback_canary():
    """Delete canary deployment, stable continues unchanged."""
    log.info("⚠️  ERROR RATE EXCEEDED THRESHOLD. Rolling back canary...")
    kubectl(f"delete deployment {CANARY_DEPLOY} -n {NAMESPACE} --ignore-not-found=true")
    # Ensure stable is at full replicas
    kubectl(f"scale deployment {STABLE_DEPLOY} --replicas=10 -n {NAMESPACE}")
    log.info("✅  Rollback complete. v1 stable is serving 100% traffic.")


def main():
    log.info("=" * 55)
    log.info("★  Smart Auto-Rollback Controller starting")
    log.info(f"   Monitoring for {MONITOR_DURATION}s | threshold={ERROR_THRESHOLD*100:.0f}%")
    log.info("=" * 55)

    elapsed    = 0
    total_ok   = 0
    total_fail = 0

    while elapsed < MONITOR_DURATION:
        healthy = check_canary_health(url="ignored")
        window.append(1 if healthy else 0)

        if healthy:
            total_ok += 1
        else:
            total_fail += 1

        total   = total_ok + total_fail
        err_pct = total_fail / total if total > 0 else 0.0

        log.info(
            f"  [{elapsed:>3}s]  checks={total:>3}  "
            f"ok={total_ok}  fail={total_fail}  "
            f"error_rate={err_pct*100:.1f}%"
        )

        # Early rollback if error rate already high
        if total >= 5 and err_pct > ERROR_THRESHOLD:
            log.warning(f"  Error rate {err_pct*100:.1f}% > {ERROR_THRESHOLD*100:.0f}% threshold!")
            rollback_canary()
            sys.exit(1)           # Jenkins marks stage as failed → post section cleans up

        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

    # ── Final decision ───────────────────────────────────────
    final_total   = total_ok + total_fail
    final_err_pct = total_fail / final_total if final_total > 0 else 0.0

    log.info(f"\n{'='*55}")
    log.info(f"  Final error rate: {final_err_pct*100:.1f}%")

    if final_err_pct <= ERROR_THRESHOLD and total_ok >= PROMOTE_MIN_OK:
        promote_canary()
        sys.exit(0)
    else:
        rollback_canary()
        sys.exit(1)


if __name__ == "__main__":
    main()