"""Drift -> retrain loop. If the implied coefficient moved, set it in params.yaml and rerun
the pipeline; the test stage's gate decides whether the new model becomes champion.
Usage: python -m property_price.monitoring.retrain_on_drift [--simulate]
  --simulate : act on the simulated 2027 check (demo); default acts on real recent DPEs."""

import json
import re
import subprocess
import sys
from pathlib import Path

from property_price.logging_config import get_logger, log_metric

log = get_logger(__name__)
REPORT = Path("reports/drift.json")
PARAMS = Path("params.yaml")


def set_coefficient(value: float) -> None:
    """Set the electricity coefficient in params.yaml, keeping its comments."""
   
    text = PARAMS.read_text(encoding="utf-8")
    PARAMS.write_text(re.sub(r"(elec_coefficient:\s*)[0-9.]+", rf"\g<1>{value}", text, count=1),
                      encoding="utf-8")


def main() -> None:
    """Check the drift report and, if a rule change is detected, set the new coefficient and retrain the model.
    If --simulate is given, act on the simulated 2027 check (demo); default acts on real recent DPEs.
    """
    simulate = "--simulate" in sys.argv
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    prefix = ("implied_coefficient_recent_simulated" if simulate
              else "implied_coefficient_recent_real")
    check = next(c for c in report["checks"] if c["name"].startswith(prefix))
    log_metric(log, "retrain_trigger", check=check["name"], status=check["status"],
               value=check["value"], simulate=simulate)

    if check["status"] != "drift":
        log.info("no rule change detected: no retraining")
        return

    new_coef = round(check["value"], 1)       # regulatory coefficients have one decimal
    log.warning("rule change detected: electricity coefficient -> %s; retraining", new_coef)
    set_coefficient(new_coef)
    subprocess.run([sys.executable, "-m", "dvc", "repro", "test"], check=True)
    log.info("retraining done. Promotion decided by the gate (see test logs). "
             "Review the params.yaml and dvc.lock diff, then commit.")


if __name__ == "__main__":
    main()