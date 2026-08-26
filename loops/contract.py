"""The repo contract.

A target repo is valid when its `Taskfile.yml` exposes the required tasks and
`task test` writes `reports/junit.xml` and `reports/coverage.xml`.

`junit.xml` and `coverage.xml` are universal formats. Any language emits them.
That is what makes the loops repo-agnostic.

`.loop.yml` is optional. It carries what a Taskfile cannot express: write scope
per role, rubric thresholds, the ticket source, and the budget.
"""

from __future__ import annotations

import os
import re
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

REQUIRED_TASKS = ("setup", "test", "e2e", "lint", "format-check")

# pytest exits 5 when it collects nothing. Task wraps that as 201.
# An empty suite is not a failing suite. The rubric decides whether one was
# required; the contract only reports what it found.
NO_TESTS_COLLECTED = (5, 201)

DEFAULTS: dict = {
    "roles": {
        "planner": {"write_allow": ["steps.jsonl"], "write_deny": []},
        "test_implementer": {"write_allow": ["tests/**"], "write_deny": []},
        "code_implementer": {"write_allow": ["app/**", "src/**"], "write_deny": ["tests/**"]},
        "judge": {"write_allow": [], "write_deny": ["**"]},
    },
    "rubric": {"coverage_floor": 80.0, "require_red": True, "ui_paths": []},
    "tickets": {"source": "local", "path": "tickets"},
    "budget": {"iterations": 3, "usd": 2.0},
}


class ContractError(RuntimeError):
    """The target repo does not satisfy the contract."""


@dataclass
class TestReport:
    """One parsed junit file."""

    exists: bool = False
    tests: int = 0
    failures: int = 0
    errors: int = 0
    skipped: int = 0
    passed_ids: set[str] = field(default_factory=set)
    failed_ids: set[str] = field(default_factory=set)
    path: Path | None = None

    @property
    def green(self) -> bool:
        """True only when the file exists, ran something, and nothing failed."""
        return self.exists and self.tests > 0 and self.failures == 0 and self.errors == 0

    @property
    def empty(self) -> bool:
        return self.exists and self.tests == 0


@dataclass
class CoverageReport:
    exists: bool = False
    line_rate: float = 0.0  # percent, 0..100
    lines_valid: int = 0
    lines_covered: int = 0


@dataclass
class RunResult:
    task: str
    exit_code: int
    output: str
    junit: TestReport
    coverage: CoverageReport

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    @property
    def no_tests(self) -> bool:
        return self.exit_code in NO_TESTS_COLLECTED or self.junit.empty


def parse_junit(path: Path) -> TestReport:
    """Read a junit XML file. A missing file is not a pass."""
    report = TestReport(path=path)
    if not path.exists():
        return report
    report.exists = True
    root = ET.parse(path).getroot()

    # Junit is a family of shapes, not one schema. pytest nests <testcase> under
    # <testsuite> under <testsuites> and puts counts on the suite. Node's runner
    # puts <testcase> straight under <testsuites> with no counts at all. Read the
    # test cases, which every producer emits, and treat suite attributes as a
    # cross-check rather than the source of truth.
    for case in root.iter("testcase"):
        name = case.get("name", "")
        classname = case.get("classname", "")
        node_id = f"{classname}::{name}" if classname else name
        children = {child.tag for child in case}
        if "skipped" in children:
            report.skipped += 1
            continue
        failed = bool(children & {"failure", "error"}) or case.get("failure") is not None
        if "error" in children:
            report.errors += 1
        elif failed:
            report.failures += 1
        (report.failed_ids if failed else report.passed_ids).add(node_id)

    report.tests = len(report.passed_ids) + len(report.failed_ids) + report.skipped

    # A producer that reports counts but emits no cases still has to be believed.
    for suite in root.iter("testsuite"):
        declared = int(suite.get("tests", 0))
        if declared and report.tests == 0:
            report.tests = declared
            report.failures = int(suite.get("failures", 0))
            report.errors = int(suite.get("errors", 0))
            report.skipped = int(suite.get("skipped", 0))
    return report


def parse_coverage(path: Path) -> CoverageReport:
    """Read a Cobertura XML file and return the line rate as a percentage."""
    if not path.exists():
        return CoverageReport()
    root = ET.parse(path).getroot()
    return CoverageReport(
        exists=True,
        line_rate=round(float(root.get("line-rate", 0.0)) * 100, 2),
        lines_valid=int(root.get("lines-valid", 0)),
        lines_covered=int(root.get("lines-covered", 0)),
    )


def _load_yaml(path: Path) -> dict:
    """Read a small YAML file. Uses PyYAML when present, else a narrow fallback."""
    if not path.exists():
        return {}
    try:
        import yaml  # type: ignore

        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except ImportError:
        return _mini_yaml(path.read_text(encoding="utf-8"))


def _mini_yaml(text: str) -> dict:
    """Parse the subset of YAML that .loop.yml uses. Two levels, lists, scalars.

    ponytail: deliberately narrow. PyYAML is optional in the class venv, and a
    target repo must stay readable without it. Anything richer than .loop.yml
    needs the real parser.
    """
    root: dict = {}
    stack: list[tuple[int, dict]] = [(-1, root)]

    def scalar(raw: str):
        raw = raw.strip()
        if raw.startswith("[") and raw.endswith("]"):
            inner = raw[1:-1].strip()
            return [scalar(p) for p in _split_inline(inner)] if inner else []
        if raw.startswith(("'", '"')) and raw[:1] == raw[-1:] and len(raw) > 1:
            return raw[1:-1]
        if re.fullmatch(r"-?\d+", raw):
            return int(raw)
        if re.fullmatch(r"-?\d*\.\d+", raw):
            return float(raw)
        low = raw.lower()
        if low in ("true", "yes"):
            return True
        if low in ("false", "no"):
            return False
        if low in ("null", "~", ""):
            return None
        return raw

    for line in text.splitlines():
        stripped = line.split("#", 1)[0].rstrip() if "#" in line else line.rstrip()
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip())
        body = stripped.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if body.startswith("- "):
            parent.setdefault("__list__", []).append(scalar(body[2:]))
            continue
        if ":" not in body:
            continue
        key, _, raw = body.partition(":")
        key = key.strip()
        if raw.strip():
            parent[key] = scalar(raw)
        else:
            child: dict = {}
            parent[key] = child
            stack.append((indent, child))
    return _fold_lists(root)


def _split_inline(inner: str) -> list[str]:
    parts, buf, quote = [], "", ""
    for ch in inner:
        if quote:
            buf += ch
            if ch == quote:
                quote = ""
        elif ch in "'\"":
            quote = ch
            buf += ch
        elif ch == ",":
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    if buf.strip():
        parts.append(buf)
    return parts


def _fold_lists(node):
    if not isinstance(node, dict):
        return node
    if set(node) == {"__list__"}:
        return node["__list__"]
    return {k: _fold_lists(v) for k, v in node.items()}


def _deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for key, value in (over or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


class Contract:
    """A validated view of one target repo."""

    def __init__(self, repo: str | Path):
        self.repo = Path(repo).expanduser().resolve()
        if not self.repo.is_dir():
            raise ContractError(f"target repo does not exist: {self.repo}")
        self.taskfile = self.repo / "Taskfile.yml"
        self.config = _deep_merge(DEFAULTS, _load_yaml(self.repo / ".loop.yml"))

    # -- validation ---------------------------------------------------------

    def missing_tasks(self) -> list[str]:
        """Return the required tasks the target does not define."""
        if not self.taskfile.exists():
            return list(REQUIRED_TASKS)
        declared = set(re.findall(r"^  ([A-Za-z][\w:-]*):\s*$", self.taskfile.read_text(), re.M))
        return [name for name in REQUIRED_TASKS if name not in declared]

    def validate(self) -> None:
        """Raise unless the target satisfies the contract."""
        if not self.taskfile.exists():
            raise ContractError(f"no Taskfile.yml in {self.repo}. Not a valid target repo.")
        missing = self.missing_tasks()
        if missing:
            raise ContractError(
                f"{self.repo}/Taskfile.yml is missing required tasks: {', '.join(missing)}"
            )

    # -- config -------------------------------------------------------------

    @property
    def rubric(self) -> dict:
        return self.config["rubric"]

    @property
    def budget(self) -> dict:
        return self.config["budget"]

    @property
    def tickets(self) -> dict:
        return self.config["tickets"]

    def role(self, name: str) -> dict:
        """Write scope for one role. An unknown role gets no write path."""
        return self.config["roles"].get(name, {"write_allow": [], "write_deny": ["**"]})

    # -- reports ------------------------------------------------------------

    @property
    def reports_dir(self) -> Path:
        return self.repo / "reports"

    def junit(self, name: str = "junit.xml") -> TestReport:
        return parse_junit(self.reports_dir / name)

    def coverage(self) -> CoverageReport:
        return parse_coverage(self.reports_dir / "coverage.xml")

    # -- running ------------------------------------------------------------

    def run(self, task: str, timeout: int = 900) -> RunResult:
        """Run one contract task inside the target repo and read its reports."""
        junit_name = "junit-e2e.xml" if task == "e2e" else "junit.xml"
        stale = self.reports_dir / junit_name
        before = stale.stat().st_mtime if stale.exists() else None

        proc = subprocess.run(
            ["task", task],
            cwd=self.repo,
            text=True,
            capture_output=True,
            timeout=timeout,
            env={**os.environ, "FORCE_COLOR": "0", "NO_COLOR": "1"},
        )
        report = self.junit(junit_name)

        # A report that did not move is a report from a previous run. Saying
        # "green" off a stale file is the silent-skip bug this workshop is about.
        if before is not None and report.exists and stale.stat().st_mtime == before:
            report.exists = False

        return RunResult(
            task=task,
            exit_code=proc.returncode,
            output=(proc.stdout or "") + (proc.stderr or ""),
            junit=report,
            coverage=self.coverage() if task == "test" else CoverageReport(),
        )
