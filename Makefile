PYTHON ?= python

.PHONY: agent-audit agent-bootstrap agent-security-bootstrap agent-security-remediations agent-sync agent-validate agent-security agent-compat agent-token-report agent-update-check agent-clean-temp

agent-audit:
	$(PYTHON) scripts/run-agent-audit.py

agent-bootstrap:
	$(PYTHON) scripts/bootstrap-graphify.py --check

agent-security-bootstrap:
	$(PYTHON) scripts/bootstrap-security-tools.py --check

agent-security-remediations:
	$(PYTHON) scripts/check-high-risk-remediations.py

agent-sync:
	$(PYTHON) scripts/sync-agent-skills.py

agent-validate:
	$(PYTHON) scripts/validate-agent-skills.py
	$(PYTHON) scripts/validate-agent-platform.py
	$(PYTHON) scripts/validate-workflow-command-parity.py
	$(PYTHON) scripts/check-agent-licenses.py
	$(PYTHON) scripts/check-agent-links.py
	$(PYTHON) scripts/build-agent-audit.py --check
	$(PYTHON) scripts/agent-token-report.py --check
	$(PYTHON) scripts/check-graph-freshness.py

agent-security:
	$(PYTHON) scripts/agent-security.py --npm-audit --full-scanners --write-evidence

agent-compat:
	$(PYTHON) scripts/agent-compat.py --write

agent-token-report:
	$(PYTHON) scripts/agent-token-report.py --write

agent-update-check:
	$(PYTHON) scripts/agent-update-check.py

agent-clean-temp:
	$(PYTHON) scripts/agent-clean-temp.py
