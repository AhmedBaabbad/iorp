"""Fail closed on shipped npm high/critical findings, with a path-scoped exception."""
import json
from pathlib import Path
import shutil
import subprocess


# Reviewed in .github/security-exceptions.md; never exempt critical findings.
EXCEPTIONS = {"GHSA-fc5q-39xc-vjpf"}
NODES = {
    "next-intl": "node_modules/next-intl",
    "@parcel/watcher": "node_modules/@parcel/watcher",
    "picomatch": "node_modules/@parcel/watcher/node_modules/picomatch",
}
VERSIONS = {"next-intl": "4.13.1", "@parcel/watcher": "2.5.6", "picomatch": "4.0.5"}
SEVERITIES = {"info", "low", "moderate", "high", "critical"}


def exception_path_matches(lock):
    """An unrelated production consumer or a changed lock path requires review."""
    packages = lock["packages"]
    if lock["lockfileVersion"] != 3 or "next-intl" not in packages[""]["dependencies"]:
        return False
    if any(packages[NODES[name]]["version"] != version for name, version in VERSIONS.items()):
        return False
    allowed_edges = {(NODES["next-intl"], "@parcel/watcher"), (NODES["@parcel/watcher"], "picomatch")}
    edges = set()
    for path, package in packages.items():
        if package.get("dev"):
            continue
        if path.endswith("/picomatch") and path != NODES["picomatch"]:
            return False
        for field in ("dependencies", "optionalDependencies", "peerDependencies"):
            for dependency in package.get(field, {}):
                if dependency in ("@parcel/watcher", "picomatch"):
                    edges.add((path, dependency))
    return edges == allowed_edges


def blocked_packages(report, lock):
    if report.get("auditReportVersion") != 2 or "error" in report:
        raise ValueError("Invalid audit report")
    vulnerabilities = report["vulnerabilities"]
    if not isinstance(vulnerabilities, dict):
        raise ValueError("Invalid vulnerabilities")
    for name, finding in vulnerabilities.items():
        if (finding["name"] != name or finding["severity"] not in SEVERITIES
                or not isinstance(finding["nodes"], list) or not finding["nodes"]
                or not all(isinstance(node, str) for node in finding["nodes"])
                or not isinstance(finding["via"], list) or not finding["via"]):
            raise ValueError("Invalid finding")
        for via in finding["via"]:
            if isinstance(via, str):
                if via not in vulnerabilities:
                    raise ValueError("Unresolved via")
            elif not isinstance(via, dict) or via.get("severity") not in SEVERITIES or not isinstance(via.get("url"), str):
                raise ValueError("Invalid advisory")

    def exempt(name, visiting):
        if name in visiting:
            raise ValueError("Cyclic via")
        finding = vulnerabilities[name]
        if (finding["severity"] == "critical" or name not in NODES
                or set(finding["nodes"]) != {NODES[name]} or not exception_path_matches(lock)):
            return False
        for via in finding["via"]:
            if isinstance(via, str):
                if not exempt(via, visiting | {name}):
                    return False
            elif (name != "picomatch" or via.get("name") != "picomatch"
                  or via.get("dependency") != "picomatch" or via["severity"] != "high"
                  or via["url"] not in {f"https://github.com/advisories/{ghsa}" for ghsa in EXCEPTIONS}):
                return False
        return True

    return sorted(name for name, finding in vulnerabilities.items()
                  if (finding["severity"] in {"high", "critical"}
                      or any(isinstance(via, dict) and via["severity"] in {"high", "critical"}
                             for via in finding["via"])) and not exempt(name, set()))


def main(project=None):
    project = Path(project) if project else Path(__file__).resolve().parents[2] / "frontend"
    try:
        result = subprocess.run(
            [shutil.which("npm") or "npm", "audit", "--omit=dev", "--json"],
            cwd=project, capture_output=True, text=True, timeout=120, check=False,
        )
        # npm returns 1 for a successful audit that found vulnerabilities.
        if result.returncode not in (0, 1):
            raise ValueError("Audit command failed")
        report = json.loads(result.stdout)
        if result.returncode == 1 and not report.get("vulnerabilities"):
            raise ValueError("Audit command failed")
        lock = json.loads((project / "package-lock.json").read_text(encoding="utf-8"))
        blocked = blocked_packages(report, lock)
    except Exception:
        print("npm-audit-gate: failed (command, report or lockfile invalid)")
        return 2
    if blocked:
        print("npm-audit-gate: blocked high/critical findings: " + ", ".join(blocked))
        return 1
    print("npm-audit-gate: passed (only documented path-scoped exceptions permitted)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
