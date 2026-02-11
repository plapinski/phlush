#!/usr/bin/env python3
"""
PHP Static Analysis Tool

Runs PHPMD and pdepend on PHP files via jakzal/phpqa Docker image.
Parses output into a clean, unified report for AI-powered analysis.

Usage:
    analyze.py --git-changed              # Default: git-changed PHP files
    analyze.py --all                      # All PHP files (skip vendor/node_modules)
    analyze.py path/to/File.php           # Specific file(s)
    analyze.py --git-changed --focus-critical  # Only high-impact findings

Exit codes:
    0 = success
    1 = infrastructure error (Docker not available, image pull failed)
    2 = no PHP files to analyze
    3 = tool execution error
"""

import argparse
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# ---------------------------------------------------------------------------
# Thresholds: (WARN_min, CRITICAL_min) — values >= threshold trigger that level
# For MI: inverted — lower is worse
# ---------------------------------------------------------------------------
METHOD_THRESHOLDS = {
    "ccn": (6, 11),
    "npath": (81, 201),
    "mi": None,  # handled specially (inverted)
    "loc": (21, 51),
}

CLASS_THRESHOLDS = {
    "wmc": (21, 51),
    "cbo": (9, 15),
    "dit": (4, 6),
    "lcom": (2, 4),
    "nom": (11, 21),
}

MI_THRESHOLDS = (84, 64)  # below 85 = WARN, below 65 = CRITICAL

# PHPMD noise rules to filter in --focus-critical mode
NOISE_RULES = {
    "ShortVariable",
    "LongVariable",
    "ShortMethodName",
    "BooleanGetMethodName",
    "ElseExpression",
    "StaticAccess",
    "LongClassName",
    "ShortClassName",
    "CamelCaseVariableName",
    "CamelCaseParameterName",
    "CamelCasePropertyName",
    "CamelCaseMethodName",
}

# Paths to always exclude
EXCLUDE_PATTERNS = [
    "vendor/",
    "node_modules/",
    "storage/",
    "bootstrap/cache/",
    "public/",
    "_ide_helper",
    ".phpstorm.meta.php",
]


def get_project_root():
    """Find the git root directory."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        return Path.cwd()


def get_changed_php_files():
    """Get PHP files changed in git (staged + unstaged), deduplicated."""
    project_root = get_project_root()
    files = set()

    for cmd in [
        ["git", "diff", "--name-only", "--diff-filter=d", "HEAD"],
        ["git", "diff", "--name-only", "--diff-filter=d", "--cached"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ]:
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=False, cwd=project_root
            )
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if line and line.endswith(".php"):
                    files.add(line)
        except subprocess.CalledProcessError:
            continue

    # Filter out excluded paths
    filtered = set()
    for f in files:
        if not any(excl in f for excl in EXCLUDE_PATTERNS):
            filtered.add(f)

    return sorted(filtered)


def get_all_php_files():
    """Get all PHP files in the project, excluding vendor/node_modules/etc."""
    project_root = get_project_root()
    files = []

    for php_file in project_root.rglob("*.php"):
        rel = str(php_file.relative_to(project_root))
        if not any(excl in rel for excl in EXCLUDE_PATTERNS):
            files.append(rel)

    return sorted(files)


def check_docker():
    """Verify Docker is available and running."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode != 0:
            print("ERROR: Docker is not running.", file=sys.stderr)
            print("Start Docker Desktop and try again.", file=sys.stderr)
            sys.exit(1)
    except FileNotFoundError:
        print("ERROR: Docker is not installed.", file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("ERROR: Docker is not responding (timeout).", file=sys.stderr)
        sys.exit(1)


def ensure_image():
    """Check if jakzal/phpqa:alpine is available, pull if needed."""
    result = subprocess.run(
        ["docker", "image", "inspect", "jakzal/phpqa:alpine"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print("Pulling jakzal/phpqa:alpine (first run)...", file=sys.stderr)
        pull = subprocess.run(
            ["docker", "pull", "jakzal/phpqa:alpine"],
            capture_output=True,
            text=True,
            check=False,
        )
        if pull.returncode != 0:
            print(f"ERROR: Failed to pull image: {pull.stderr}", file=sys.stderr)
            sys.exit(1)
        print("Image pulled successfully.", file=sys.stderr)


def run_docker(cmd, project_root, timeout=120):
    """Run a command inside the jakzal/phpqa Docker container."""
    docker_cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{project_root}:/project",
        "-w",
        "/project",
        "jakzal/phpqa:alpine",
        "sh",
        "-c",
        cmd,
    ]
    try:
        result = subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "Command timed out", 1
    except Exception as e:
        return "", str(e), 1


# ---------------------------------------------------------------------------
# PHPMD
# ---------------------------------------------------------------------------

def run_phpmd(files, project_root, focus_critical=False):
    """Run PHPMD with JSON output and parse violations."""
    # PHPMD accepts comma-separated paths
    paths_str = ",".join(files)
    rulesets = "cleancode,codesize,design,naming,unusedcode"

    cmd = f"phpmd {paths_str} json {rulesets}"
    stdout, stderr, returncode = run_docker(cmd, project_root)

    # PHPMD exits 2 when violations found — that's normal
    if returncode not in (0, 2):
        # Check for parse errors in stderr (PHP version mismatch, etc.)
        if stderr and "error" in stderr.lower():
            print(f"PHPMD warning: {stderr.strip()}", file=sys.stderr)

    violations = []
    if stdout.strip():
        # PHPMD may output PHP deprecation warnings before JSON — extract JSON robustly
        data = extract_json(stdout)
        if data is not None:
            for file_entry in data.get("files", []):
                filename = file_entry.get("file", "")
                # Strip /project/ prefix from Docker paths
                filename = filename.replace("/project/", "")

                for v in file_entry.get("violations", []):
                    rule = v.get("rule", "")
                    priority = v.get("priority", 5)

                    # Focus-critical filter
                    if focus_critical:
                        if priority > 2:
                            continue
                        if rule in NOISE_RULES:
                            continue

                    violations.append(
                        {
                            "file": filename,
                            "line": v.get("beginLine", 0),
                            "rule": rule,
                            "ruleset": v.get("ruleSet", ""),
                            "priority": priority,
                            "description": v.get("description", ""),
                        }
                    )
        else:
            print("PHPMD warning: Could not parse JSON output.", file=sys.stderr)

    return violations


def classify_phpmd_severity(priority):
    """Map PHPMD priority (1-5) to severity label."""
    if priority <= 1:
        return "CRITICAL"
    elif priority <= 2:
        return "WARNING"
    else:
        return "INFO"


# ---------------------------------------------------------------------------
# pdepend
# ---------------------------------------------------------------------------

def run_pdepend(files, project_root):
    """Run pdepend with summary XML output and parse metrics."""
    tmp_dir = project_root / ".tmp-phpqa"
    tmp_dir.mkdir(exist_ok=True)
    summary_file = ".tmp-phpqa/pdepend-summary.xml"

    paths_str = ",".join(files)
    cmd = f"pdepend --summary-xml={summary_file} {paths_str}"
    stdout, stderr, returncode = run_docker(cmd, project_root)

    summary_path = tmp_dir / "pdepend-summary.xml"
    if not summary_path.exists():
        if stderr:
            print(f"pdepend warning: {stderr.strip()}", file=sys.stderr)
        return {"classes": [], "summary": {}}

    return parse_pdepend_xml(summary_path)


def parse_pdepend_xml(xml_path):
    """Parse pdepend summary XML into structured metrics."""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"pdepend warning: XML parse error: {e}", file=sys.stderr)
        return {"classes": [], "summary": {}}

    result = {"summary": {}, "classes": []}

    # Project-level summary
    for attr in ["loc", "ncloc", "ccn", "ccn2", "nom", "noc", "nop"]:
        if attr in root.attrib:
            result["summary"][attr] = safe_int(root.attrib[attr])

    # Class and method metrics
    for pkg in root.findall(".//package"):
        for cls in pkg.findall("class"):
            class_info = {
                "name": cls.attrib.get("name", ""),
                "fqname": cls.attrib.get("fqname", ""),
                "loc": safe_int(cls.attrib.get("loc", "0")),
                "ncloc": safe_int(cls.attrib.get("ncloc", "0")),
                "nom": safe_int(cls.attrib.get("nom", "0")),
                "wmc": safe_int(cls.attrib.get("wmc", "0")),
                "cbo": safe_int(cls.attrib.get("cbo", "0")),
                "dit": safe_int(cls.attrib.get("dit", "0")),
                "lcom": safe_int(cls.attrib.get("lcom", "0")),
                "methods": [],
            }

            for method in cls.findall("method"):
                method_info = {
                    "name": method.attrib.get("name", ""),
                    "ccn": safe_int(method.attrib.get("ccn", "0")),
                    "ccn2": safe_int(method.attrib.get("ccn2", "0")),
                    "loc": safe_int(method.attrib.get("loc", "0")),
                    "npath": safe_int(method.attrib.get("npath", "0")),
                    "mi": safe_float(method.attrib.get("mi", "0")),
                }
                class_info["methods"].append(method_info)

            result["classes"].append(class_info)

    return result


# ---------------------------------------------------------------------------
# Severity classification
# ---------------------------------------------------------------------------

def classify_severity(metric, value):
    """Classify a metric value as OK, WARN, or CRITICAL."""
    # MI is inverted: lower is worse
    if metric == "mi":
        if value < MI_THRESHOLDS[1]:
            return "CRITICAL"
        elif value < MI_THRESHOLDS[0]:
            return "WARN"
        return "OK"

    # Check method-level thresholds
    if metric in METHOD_THRESHOLDS:
        thresholds = METHOD_THRESHOLDS[metric]
        if thresholds is None:
            return "OK"
        warn, crit = thresholds
        if value >= crit:
            return "CRITICAL"
        elif value >= warn:
            return "WARN"
        return "OK"

    # Check class-level thresholds
    if metric in CLASS_THRESHOLDS:
        warn, crit = CLASS_THRESHOLDS[metric]
        if value >= crit:
            return "CRITICAL"
        elif value >= warn:
            return "WARN"
        return "OK"

    return "OK"


def severity_tag(level):
    """Format severity for display."""
    if level == "CRITICAL":
        return "[CRITICAL]"
    elif level == "WARN":
        return "[WARN]"
    return ""


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

def format_report(phpmd_violations, pdepend_metrics, files_analyzed, focus_critical=False):
    """Build unified plain-text report."""
    lines = []
    lines.append("=== PHP STATIC ANALYSIS REPORT ===")
    lines.append(f"Files analyzed: {len(files_analyzed)}")

    if focus_critical:
        lines.append("Mode: focus-critical (filtered to high-impact findings only)")
    lines.append("")

    # --- PHPMD section ---
    lines.append("--- PHPMD VIOLATIONS ---")
    if not phpmd_violations:
        lines.append("No violations found.")
    else:
        # Group by file
        by_file = {}
        for v in phpmd_violations:
            by_file.setdefault(v["file"], []).append(v)

        for filename in sorted(by_file.keys()):
            lines.append(f"{filename}:")
            for v in sorted(by_file[filename], key=lambda x: x["priority"]):
                severity = classify_phpmd_severity(v["priority"])
                pad = " " * (10 - len(severity))
                lines.append(
                    f"  {severity}{pad}:{v['line']}  {v['rule']}  {v['description']}"
                )
            lines.append("")

    lines.append("")

    # --- pdepend section ---
    lines.append("--- PDEPEND METRICS ---")
    classes = pdepend_metrics.get("classes", [])

    if not classes:
        lines.append("No class metrics available.")
    else:
        for cls in sorted(classes, key=lambda c: c.get("wmc", 0), reverse=True):
            # Class header
            class_parts = []
            class_parts.append(f"LOC: {cls['loc']}")
            class_parts.append(f"Methods: {cls['nom']}")

            for metric in ["wmc", "cbo", "dit", "lcom"]:
                val = cls.get(metric, 0)
                sev = classify_severity(metric, val)
                tag = severity_tag(sev)
                class_parts.append(f"{metric.upper()}: {val} {tag}".strip())

            # Skip class entirely in focus-critical if everything is OK
            if focus_critical:
                has_issues = any(
                    classify_severity(m, cls.get(m, 0)) != "OK"
                    for m in ["wmc", "cbo", "dit", "lcom"]
                )
                method_has_issues = any(
                    classify_severity("ccn", meth.get("ccn", 0)) != "OK"
                    or classify_severity("npath", meth.get("npath", 0)) != "OK"
                    or classify_severity("mi", meth.get("mi", 100)) != "OK"
                    for meth in cls.get("methods", [])
                )
                if not has_issues and not method_has_issues:
                    continue

            display_name = cls.get("fqname", cls["name"]) or cls["name"]
            lines.append(f"Class: {display_name}")
            lines.append(f"  {' | '.join(class_parts)}")

            # Methods
            methods = cls.get("methods", [])
            if methods:
                # Sort by CCN descending
                methods_sorted = sorted(
                    methods, key=lambda m: m.get("ccn", 0), reverse=True
                )

                has_method_output = False
                for m in methods_sorted:
                    method_parts = []

                    for metric, val in [
                        ("ccn", m.get("ccn", 0)),
                        ("npath", m.get("npath", 0)),
                        ("mi", m.get("mi", 100)),
                        ("loc", m.get("loc", 0)),
                    ]:
                        sev = classify_severity(metric, val)
                        tag = severity_tag(sev)

                        # In focus-critical, skip methods where everything is OK
                        if metric == "ccn" and focus_critical:
                            all_ok = all(
                                classify_severity(met, m.get(met, 0 if met != "mi" else 100))
                                == "OK"
                                for met in ["ccn", "npath", "mi"]
                            )
                            if all_ok:
                                break

                        if metric == "mi":
                            method_parts.append(
                                f"MI: {val:.1f} {tag}".strip()
                            )
                        else:
                            method_parts.append(
                                f"{metric.upper()}: {val} {tag}".strip()
                            )
                    else:
                        if not has_method_output:
                            lines.append("  Methods:")
                            has_method_output = True
                        name = m.get("name", "?")
                        lines.append(f"    {name}()  {' | '.join(method_parts)}")

            lines.append("")

    lines.append("")

    # --- Summary ---
    lines.append("--- SUMMARY ---")

    # PHPMD summary
    total_violations = len(phpmd_violations)
    critical_count = sum(1 for v in phpmd_violations if v["priority"] <= 1)
    warning_count = sum(1 for v in phpmd_violations if v["priority"] == 2)
    info_count = sum(1 for v in phpmd_violations if v["priority"] > 2)
    lines.append(
        f"Total PHPMD violations: {total_violations} "
        f"(critical: {critical_count}, warning: {warning_count}, info: {info_count})"
    )

    # pdepend summary
    lines.append(f"Classes analyzed: {len(classes)}")

    if classes:
        # Find highest CCN across all methods
        max_ccn = 0
        max_ccn_method = ""
        max_ccn_class = ""
        for cls in classes:
            for m in cls.get("methods", []):
                if m.get("ccn", 0) > max_ccn:
                    max_ccn = m["ccn"]
                    max_ccn_method = m.get("name", "?")
                    max_ccn_class = cls.get("name", "?")

        if max_ccn > 0:
            lines.append(
                f"Highest CCN: {max_ccn} ({max_ccn_method} in {max_ccn_class})"
            )

        # Count CRITICAL/WARN classes
        critical_classes = sum(
            1
            for cls in classes
            if any(
                classify_severity(m, cls.get(m, 0)) == "CRITICAL"
                for m in ["wmc", "cbo", "dit", "lcom"]
            )
        )
        if critical_classes > 0:
            lines.append(f"Classes with CRITICAL metrics: {critical_classes}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def extract_json(text):
    """Extract JSON object from text that may contain leading noise (e.g. PHP deprecation warnings)."""
    # Find the first '{' character — JSON output starts there
    idx = text.find("{")
    if idx == -1:
        return None
    json_text = text[idx:]
    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        return None


def safe_int(value):
    """Safely convert to int, defaulting to 0."""
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return 0


def safe_float(value):
    """Safely convert to float, defaulting to 0.0."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run PHP static analysis via Docker (jakzal/phpqa)"
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Specific PHP file(s) or directories to analyze",
    )
    parser.add_argument(
        "--git-changed",
        action="store_true",
        help="Analyze git-changed PHP files (default if no paths given)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Analyze all PHP files (excluding vendor/node_modules)",
    )
    parser.add_argument(
        "--focus-critical",
        action="store_true",
        help="Filter to high-impact findings only",
    )

    args = parser.parse_args()

    # Determine which files to analyze
    project_root = get_project_root()

    if args.paths:
        # Specific paths provided — validate they exist
        files = []
        for p in args.paths:
            full_path = project_root / p
            if full_path.is_file():
                if p.endswith(".php"):
                    files.append(p)
                else:
                    print(f"Skipping non-PHP file: {p}", file=sys.stderr)
            elif full_path.is_dir():
                # Collect PHP files from directory
                for php_file in full_path.rglob("*.php"):
                    rel = str(php_file.relative_to(project_root))
                    if not any(excl in rel for excl in EXCLUDE_PATTERNS):
                        files.append(rel)
            else:
                print(f"WARNING: Path does not exist: {p}", file=sys.stderr)
    elif args.all:
        files = get_all_php_files()
    else:
        # Default: git-changed
        files = get_changed_php_files()

    if not files:
        print("No PHP files to analyze.", file=sys.stderr)
        sys.exit(2)

    # Pre-flight checks
    check_docker()
    ensure_image()

    print(f"Analyzing {len(files)} PHP file(s)...", file=sys.stderr)

    # Run tools
    phpmd_violations = run_phpmd(files, project_root, focus_critical=args.focus_critical)
    pdepend_metrics = run_pdepend(files, project_root)

    # Build and output report
    report = format_report(
        phpmd_violations, pdepend_metrics, files, focus_critical=args.focus_critical
    )
    print(report)

    # Cleanup
    tmp_dir = project_root / ".tmp-phpqa"
    if tmp_dir.exists():
        for f in tmp_dir.iterdir():
            if f.is_file():
                f.unlink()


if __name__ == "__main__":
    main()
