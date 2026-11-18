"""Synthetic npm audit reports: no registry/network required."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import npm_audit_gate as gate


def fixture():
    lock = {"lockfileVersion": 3, "packages": {
        "": {"dependencies": {"next-intl": "^4.13.1"}},
        gate.NODES["next-intl"]: {"version": "4.13.1", "dependencies": {"@parcel/watcher": "^2.4.1"}},
        gate.NODES["@parcel/watcher"]: {"version": "2.5.6", "dependencies": {"picomatch": "^4.0.3"}},
        gate.NODES["picomatch"]: {"version": "4.0.5"},
        "node_modules/picomatch": {"version": "2.3.2", "dev": True},
    }}
    advisory = dict(name="picomatch", dependency="picomatch", severity="high",
                    url="https://github.com/advisories/GHSA-fc5q-39xc-vjpf")
    report = {"auditReportVersion": 2, "vulnerabilities": {
        "picomatch": dict(name="picomatch", severity="high", nodes=[gate.NODES["picomatch"]], via=[advisory]),
        "@parcel/watcher": dict(name="@parcel/watcher", severity="high", nodes=[gate.NODES["@parcel/watcher"]], via=["picomatch"]),
    }}
    return report, lock


class AuditGateTests(unittest.TestCase):
    def test_only_exception_and_its_transitive_parent_pass(self):
        report, lock = fixture()
        self.assertEqual(gate.blocked_packages(report, lock), [])

    def test_other_high_and_mixed_via_block(self):
        report, lock = fixture()
        other = dict(name="other", dependency="other", severity="high", url="https://github.com/advisories/GHSA-other")
        report["vulnerabilities"]["other"] = dict(name="other", severity="high", nodes=["node_modules/other"], via=[other])
        self.assertEqual(gate.blocked_packages(report, lock), ["other"])
        report["vulnerabilities"]["@parcel/watcher"]["via"].append("other")
        self.assertEqual(gate.blocked_packages(report, lock), ["@parcel/watcher", "other"])

    def test_additional_advisory_on_picomatch_blocks_parent_too(self):
        report, lock = fixture()
        other = deepcopy(report["vulnerabilities"]["picomatch"]["via"][0])
        other["url"] = "https://github.com/advisories/GHSA-other"
        report["vulnerabilities"]["picomatch"]["via"].append(other)
        self.assertEqual(gate.blocked_packages(report, lock), ["@parcel/watcher", "picomatch"])

    def test_critical_is_never_exempt_even_with_same_ghsa(self):
        for name in ("picomatch", "@parcel/watcher"):
            with self.subTest(name=name):
                report, lock = fixture()
                report["vulnerabilities"][name]["severity"] = "critical"
                self.assertIn(name, gate.blocked_packages(report, lock))
        report, lock = fixture()
        report["vulnerabilities"]["picomatch"]["severity"] = "moderate"
        report["vulnerabilities"]["picomatch"]["via"][0]["severity"] = "critical"
        self.assertEqual(gate.blocked_packages(report, lock), ["@parcel/watcher", "picomatch"])

    def test_other_audit_or_lock_paths_cannot_use_exception(self):
        for mutation in ("audit-node", "production-node", "consumer", "direct", "version", "parent-version"):
            with self.subTest(mutation=mutation):
                report, lock = fixture()
                if mutation == "audit-node":
                    report["vulnerabilities"]["picomatch"]["nodes"].append("node_modules/other/node_modules/picomatch")
                elif mutation == "production-node":
                    lock["packages"]["node_modules/picomatch"].pop("dev")
                elif mutation == "consumer":
                    lock["packages"]["node_modules/other"] = {"dependencies": {"@parcel/watcher": "*"}}
                elif mutation == "direct":
                    lock["packages"][""]["dependencies"]["picomatch"] = "*"
                elif mutation == "version":
                    lock["packages"][gate.NODES["picomatch"]]["version"] = "4.0.7"
                else:
                    lock["packages"][gate.NODES["next-intl"]]["version"] = "4.13.2"
                self.assertEqual(gate.blocked_packages(report, lock), ["@parcel/watcher", "picomatch"])

    def test_lower_severity_and_clean_reports_keep_existing_threshold(self):
        report, lock = fixture()
        report["vulnerabilities"] = {"other": dict(name="other", severity="moderate", nodes=["node_modules/other"],
                                                  via=[dict(severity="moderate", url="https://github.com/advisories/GHSA-other")])}
        self.assertEqual(gate.blocked_packages(report, lock), [])
        report["vulnerabilities"] = {}
        self.assertEqual(gate.blocked_packages(report, lock), [])

    def run_command(self, stdout, returncode=1, lock=None, error=None):
        _, default_lock = fixture()
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "package-lock.json").write_text(json.dumps(default_lock if lock is None else lock), encoding="utf-8")
            result = subprocess.CompletedProcess([], returncode, stdout, "not a valid audit report")
            with patch.object(gate.subprocess, "run", return_value=result, side_effect=error) as command:
                with patch("builtins.print"):
                    code = gate.main(directory)
                if error is None:
                    self.assertEqual(command.call_args.args[0][1:], ["audit", "--omit=dev", "--json"])
                return code

    def test_npm_exit_one_means_findings_not_execution_failure(self):
        report, _ = fixture()
        self.assertEqual(self.run_command(json.dumps(report)), 0)
        report["vulnerabilities"] = {}
        self.assertEqual(self.run_command(json.dumps(report), returncode=0), 0)

    def test_invalid_json_command_failure_and_invalid_reports_fail_closed(self):
        report, _ = fixture()
        cases = [("not JSON", 1), (json.dumps(report), 2), ('{"error":{"code":"network"}}', 1),
                 ('{"auditReportVersion":2,"vulnerabilities":{}}', 1), ('[]', 0), ('{}', 0)]
        for stdout, returncode in cases:
            with self.subTest(stdout=stdout, returncode=returncode):
                self.assertEqual(self.run_command(stdout, returncode), 2)
        self.assertEqual(self.run_command("", error=OSError("missing npm")), 2)
        self.assertEqual(self.run_command("", error=subprocess.TimeoutExpired("npm", 120)), 2)

    def test_unresolved_via_and_invalid_lock_fail_closed(self):
        report, _ = fixture()
        report["vulnerabilities"]["@parcel/watcher"]["via"] = ["missing"]
        self.assertEqual(self.run_command(json.dumps(report)), 2)
        report, _ = fixture()
        self.assertEqual(self.run_command(json.dumps(report), lock={}), 2)


if __name__ == "__main__":
    unittest.main()
