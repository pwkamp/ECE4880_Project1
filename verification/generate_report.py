#!/usr/bin/env python3
"""Build an evidence-rich Markdown/LaTeX qualification document from a run."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verification.core.paths import existing_run, within
from verification.core.outcomes import display_outcome

ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parent
ARTIFACTS = REPOSITORY / "artifacts" / "verification"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_run(value: str) -> Path:
    run = existing_run(ARTIFACTS, value)
    if run is None:
        raise FileNotFoundError(f"verification run not found: {value}")
    return run


def latex(value: Any) -> str:
    text = str(value if value is not None else "")
    replacements = {
        "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
        "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}", "<": r"\textless{}", ">": r"\textgreater{}",
    }
    return "".join(replacements.get(char, char) for char in text)


def anchor(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")


def outcome_for_test(requirement_coverage: dict[str, Any], test_result: dict[str, Any]) -> str:
    return str(test_result.get("outcome", "BLOCKED"))


def reported_outcome(data: dict[str, Any], value: Any, *, compact: bool = False) -> str:
    """Prevent legacy evidence from looking like current qualification."""

    outcome = display_outcome(str(value))
    if not data["catalog_frozen"] or not data["catalog_matches_current"]:
        return f"STALE ({outcome})" if compact else f"HISTORICAL {outcome} - RETEST REQUIRED"
    return outcome


def validity(test: dict[str, Any], requirement: dict[str, Any]) -> str:
    method = test.get("method", "automated")
    if method == "automated":
        approach = "repeatable software checks and controlled inputs"
    elif method == "semi-automated":
        approach = "guided physical actions with automatic state and timing capture"
    else:
        approach = "recorded physical inspection and measurement"
    return f"{test['id']} checks this requirement using {approach}. It passes only when every required observation and limit is satisfied."


def plot_timeline(csv_path: Path, destination: Path) -> Path | None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    if not rows:
        return None
    x = list(range(len(rows)))
    figure, axis = plt.subplots(figsize=(10.5, 4.2))
    for sensor, color in ((1, "#1565c0"), (2, "#c62828")):
        values = []
        for row in rows:
            raw = row.get(f"sensor{sensor}_c", "")
            status = row.get(f"sensor{sensor}_status", "")
            values.append(float(raw) if raw and status == "VALID" else float("nan"))
        axis.plot(x, values, label=f"Sensor {sensor}", color=color, linewidth=1.4)
    boundaries = []
    prior = None
    for index, row in enumerate(rows):
        if row.get("phase") != prior:
            boundaries.append((index, row.get("phase", "")))
            prior = row.get("phase")
    for index, label in boundaries:
        axis.axvline(index, color="#777", alpha=.25, linewidth=.7)
        axis.text(index, 1.01, label, rotation=30, fontsize=6, transform=axis.get_xaxis_transform())
    axis.set_xlabel("Captured sample order")
    axis.set_ylabel("Temperature (°C)")
    axis.grid(alpha=.2)
    axis.legend()
    figure.tight_layout()
    destination.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(destination, dpi=160)
    plt.close(figure)
    return destination


def gather(run: Path) -> dict[str, Any]:
    run = within(run, ARTIFACTS)
    requirements_path = run / "catalogs" / "requirements.yaml"
    tests_path = run / "catalogs" / "tests.yaml"
    setup_groups_path = run / "catalogs" / "setup_groups.yaml"
    frozen_catalog = requirements_path.is_file() and tests_path.is_file() and setup_groups_path.is_file()
    if not frozen_catalog:
        requirements_path = ROOT / "requirements.yaml"
        tests_path = ROOT / "tests.yaml"
    if not setup_groups_path.is_file():
        setup_groups_path = ROOT / "setup_groups.yaml"
    requirements = load_json(requirements_path)
    tests = load_json(tests_path)
    setup_groups = load_json(setup_groups_path)
    results = [json.loads(line) for line in (run / "results.jsonl").read_text(encoding="utf-8").splitlines() if line]
    for result in results:
        retained: list[str] = []
        for raw in result.get("evidence", []):
            try:
                source = within(run / str(raw), run)
            except ValueError:
                continue
            if source.is_file():
                retained.append(source.relative_to(run).as_posix())
        result["evidence"] = retained
    coverage = load_json(run / "requirements-coverage.json")
    run_metadata = load_json(run / "run.json")
    current_requirement_hash = hashlib.sha256((ROOT / "requirements.yaml").read_bytes()).hexdigest()
    current_test_hash = hashlib.sha256((ROOT / "tests.yaml").read_bytes()).hexdigest()
    current_setup_hash = hashlib.sha256((ROOT / "setup_groups.yaml").read_bytes()).hexdigest()
    catalog_matches = (
        run_metadata.get("requirements_catalog_sha256") == current_requirement_hash
        and run_metadata.get("test_catalog_sha256") == current_test_hash
        and run_metadata.get("setup_groups_catalog_sha256") == current_setup_hash
    )
    coverage_by_id = {item["uid"]: item for item in coverage["requirements"]}
    not_applicable_test_ids = {
        item["test_id"] for item in results if item.get("outcome") == "NOT_APPLICABLE"
    }
    not_applicable_requirement_ids = {
        item["uid"]
        for item in coverage["requirements"]
        if item.get("result") == "NOT_APPLICABLE"
    } | {
        item["uid"]
        for item in requirements
        if str(item.get("status", "active")).lower() == "not_applicable"
    }
    results = [item for item in results if item["test_id"] not in not_applicable_test_ids]
    visible_test_ids = {item["test_id"] for item in results}
    tests = [item for item in tests if item["id"] in visible_test_ids]
    requirements = [item for item in requirements if item["uid"] not in not_applicable_requirement_ids]
    visible_requirement_ids = {item["uid"] for item in requirements}
    visible_coverage = []
    for raw in coverage["requirements"]:
        if raw["uid"] not in visible_requirement_ids:
            continue
        item = dict(raw)
        for field in ("tests", "automated_tests", "human_tests"):
            item[field] = [test_id for test_id in item.get(field, []) if test_id in visible_test_ids]
        visible_coverage.append(item)
    coverage = {
        **coverage,
        "requirements": visible_coverage,
        "total": len(visible_coverage),
        "counts": {
            state: sum(1 for item in visible_coverage if item.get("result") == state)
            for state in ("PASS", "PASS_OVERRIDE", "FAIL", "BLOCKED", "SKIPPED")
        },
    }
    coverage_by_id = {item["uid"]: item for item in visible_coverage}
    children_by_id: dict[str, list[str]] = {item["uid"]: [] for item in requirements}
    for requirement in requirements:
        for parent in requirement.get("parents", []):
            if parent in children_by_id:
                children_by_id[parent].append(requirement["uid"])
    data = {
        "run": run_metadata,
        "catalog_frozen": frozen_catalog,
        "catalog_matches_current": catalog_matches,
        "requirements": requirements,
        "tests": tests,
        "setup_groups": setup_groups,
        "results": results,
        "coverage": coverage,
        "requirements_by_id": {item["uid"]: item for item in requirements},
        "tests_by_id": {item["id"]: item for item in tests},
        "results_by_id": {item["test_id"]: item for item in results},
        "coverage_by_id": coverage_by_id,
        "children_by_id": children_by_id,
        "not_applicable_test_ids": not_applicable_test_ids,
        "not_applicable_requirement_ids": not_applicable_requirement_ids,
    }
    generated = run / "document" / "generated"
    for result in results:
        for evidence in result.get("evidence", []):
            source = within(run / evidence, run)
            if source.name == "sample-timeline.csv" and source.is_file():
                graph = plot_timeline(source, generated / f"{result['test_id']}-temperature.png")
                if graph:
                    result.setdefault("report_images", []).append(graph.relative_to(run).as_posix())
    return data


def procedure_text(test: dict[str, Any]) -> list[str]:
    lines = []
    procedure = test.get("entrypoint", {}).get("procedure")
    if procedure:
        try:
            path = within(REPOSITORY / procedure, ROOT / "manual")
        except ValueError:
            path = None
        if path is not None and path.is_file():
            paragraphs = []
            current: list[str] = []
            for raw in path.read_text(encoding="utf-8").splitlines():
                stripped = raw.strip()
                if not stripped or stripped.startswith("#"):
                    if current:
                        paragraphs.append(" ".join(current))
                        current = []
                    continue
                current.append(stripped.lstrip("- "))
            if current:
                paragraphs.append(" ".join(current))
            lines.extend(paragraphs)
    for step in test.get("manual_steps", []):
        lines.append(f"{step.get('instruction', '')} Expected evidence: {step.get('expected', '')}.")
    if not lines:
        lines.append(f"Run the automated {test['id']} qualification check. The runner applies the defined inputs, records the observations, and evaluates every required assertion.")
    return lines


def plain_test_rationale(test: dict[str, Any]) -> str:
    description = str(test.get("description", test.get("title", "this behavior"))).strip()
    method = test.get("method", "automated")
    if method == "automated":
        explanation = "The inputs and expected results are controlled, so the check is repeatable and does not rely on operator judgment."
    elif method == "semi-automated":
        explanation = "A person performs the physical action; the runner records the resulting states or timing and applies the pass limits."
    else:
        explanation = "A person records the physical measurement or observation that software cannot make directly."
    return f"This test verifies the following behavior: {description} {explanation}"


def test_passing_criteria(test: dict[str, Any]) -> list[str]:
    criteria = [f"The observed result must match this test objective: {test.get('description', test['title'])}"]
    if test.get("pass_policy", {}).get("all_required"):
        criteria.append("Every required assertion and operator check must pass; no mandatory step may remain failed, skipped, or blocked.")
    expected = []
    for step in test.get("manual_steps", []):
        value = str(step.get("expected", "")).strip()
        if value and value.lower() not in {"yes", "yes/no"} and value not in expected:
            expected.append(value)
    if expected:
        criteria.append("Required operator observations: " + "; ".join(expected) + ".")
    return criteria


def requirement_revision_note(requirement: dict[str, Any]) -> str | None:
    explicit = requirement.get("revision_note") or requirement.get("change_note")
    if explicit:
        return str(explicit)
    text = str(requirement.get("text", "")).lower()
    notes = []
    if "directly to the python ble backend" in text or "shall not pass through a mysql command queue" in text or "control_commands table" in text:
        notes.append("The command path was revised so MySQL stores history while display commands go directly to the Python BLE backend.")
    if "no user accounts" in text or "shall not implement application user accounts" in text or "without application user accounts" in text or "application login is out of scope" in text:
        notes.append("Application accounts and role-based access were removed; the released system uses a trusted local deployment boundary.")
    if "sms" in text and "out of scope" in text:
        notes.append("Notification scope was narrowed to email only; SMS delivery is not part of this release.")
    return " ".join(notes) or None


def requirement_title(requirement: dict[str, Any]) -> str:
    summary = str(requirement.get("jira_summary", "")).strip()
    for separator in (" - ", " — "):
        prefix = requirement["uid"] + separator
        if summary.startswith(prefix):
            return summary[len(prefix):]
    return summary or requirement["uid"]


def requirement_links(data: dict[str, Any], requirement: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    requirements = data["requirements_by_id"]
    parents = [requirements[uid] for uid in requirement.get("parents", []) if uid in requirements]
    children = [requirements[uid] for uid in data["children_by_id"].get(requirement["uid"], []) if uid in requirements]
    return parents, children


def visible_linked_tests(data: dict[str, Any], requirement_uid: str) -> list[dict[str, Any]]:
    coverage = data["coverage_by_id"][requirement_uid]
    return [data["tests_by_id"][test_id] for test_id in coverage.get("tests", []) if test_id in data["tests_by_id"]]


def markdown_report(run_dir: Path, data: dict[str, Any], include_requirements: bool) -> Path:
    run_dir = within(run_dir, ARTIFACTS)
    destination = run_dir / "document" / "qualification-report.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    run = data["run"]
    counts = Counter(item["outcome"] for item in data["results"])
    lines = [
        "# ECE:4880 Group 21 Thermometer Quality Report", "",
        f"Run: `{run['run_id']}`  ", f"Profile: `{run['profile']}`  ",
        f"Overall outcome: **{reported_outcome(data, run['outcome'])}**  ",
        f"Results: {', '.join(f'{display_outcome(key)}={value}' for key, value in sorted(counts.items()))}", "",
    ]
    if not data["catalog_frozen"] or not data["catalog_matches_current"]:
        lines += [
            "> **Catalog provenance warning:** This legacy run did not retain frozen catalog files, or its recorded catalog hashes differ from the current repository. The test outcomes remain historical evidence; rerun qualification before treating current requirement mappings/rationales as a final approval basis.",
            "",
        ]
    lines += [
        "## Requirements traceability matrix", "",
        "| Requirement | Jira | Status | Linked test results |", "|---|---|---|---|",
    ]
    for req in data["requirements"]:
        coverage = data["coverage_by_id"][req["uid"]]
        links = ", ".join(f"[{test_id}](#test-{anchor(test_id)})" for test_id in coverage["tests"])
        lines.append(f"| [{req['uid']}](#requirement-{anchor(req['uid'])}) | [{req['jira']}]({req['jira_url']}) | **{reported_outcome(data, coverage['result'], compact=True)}** | {links or 'UNMAPPED'} |")
    lines += ["", "# Requirements", "", "Each applicable requirement begins on a new page in the PDF edition. The current Jira description is the acceptance basis.", ""]
    for req in data["requirements"]:
        coverage = data["coverage_by_id"][req["uid"]]
        parents, children = requirement_links(data, req)
        linked_tests = visible_linked_tests(data, req["uid"])
        revision = requirement_revision_note(req)
        lines += [
            '<div style="page-break-before: always;"></div>', "",
            f'<a id="requirement-{anchor(req["uid"])}"></a>',
            f"## {req['uid']} - {requirement_title(req)}", "",
            f"**Result:** {reported_outcome(data, coverage['result'])}  ",
            f"**Level / component:** {req.get('level', '')} / {req.get('component', '')}  ",
            f"**Jira:** [{req['jira']}]({req['jira_url']})  ", "",
            "### Current Jira description", "", req["text"], "",
        ]
        if revision:
            lines += ["### Revision note", "", f"**Edited requirement.** {revision} The description above is the newest frozen version used by this run.", ""]
        lines += ["### Derivation and relationships", "", f"**Source:** {req.get('source', 'Jira')} (snapshot {req.get('snapshot_date', 'unknown')})  "]
        if parents:
            lines.append("**Parents:** " + ", ".join(f"[{item['uid']}](#requirement-{anchor(item['uid'])})" for item in parents) + "  ")
        else:
            lines.append("**Parents:** None - top-level project or stakeholder requirement.  ")
        if children:
            lines.append("**Children:** " + ", ".join(f"[{item['uid']}](#requirement-{anchor(item['uid'])})" for item in children) + "  ")
        else:
            lines.append("**Children:** None.  ")
        lines += ["", "### Passing criteria", "", "The requirement passes only when every linked applicable test passes and the observed behavior satisfies the complete Jira description above.", ""]
        lines += ["### Tests that verify this requirement", ""]
        if linked_tests:
            for test in linked_tests:
                result = data["results_by_id"].get(test["id"], {})
                lines.append(f"- [{test['id']} - {test['title']}](#test-{anchor(test['id'])}) - **{reported_outcome(data, result.get('outcome', 'BLOCKED'), compact=True)}**. {test.get('description', '')}")
        else:
            lines.append("No applicable test is mapped.")
        lines.append("")
    lines += ["", "# Test results", ""]
    for result in data["results"]:
        test = data["tests_by_id"][result["test_id"]]
        setup_id = test.get("setup_group", "software")
        setup = data["setup_groups"][setup_id]
        lines += ["", "---", "", f"<a id=\"test-{anchor(test['id'])}\"></a>", f"## {test['id']} - {test['title']}", "",
                  f"**Outcome:** {reported_outcome(data, result['outcome'])}  ", f"**Method:** {test['method']}  ", f"**Subsystem:** {test['subsystem']}  ", "",
                  "### What this test proves and why", "", plain_test_rationale(test), "",
                  "### Passing criteria", ""]
        lines.extend(f"- {criterion}" for criterion in test_passing_criteria(test))
        lines += ["", "### Required setup", "", f"**{setup['title']}** (`{setup_id}`)", ""]
        lines.extend(f"- {instruction}" for instruction in setup["instructions"])
        lines += ["", "### Procedure", ""]
        lines.extend(f"{index}. {step}" for index, step in enumerate(procedure_text(test), 1))
        lines += ["", "### Requirements covered", ""]
        for uid in test["requirements"]:
            if uid not in data["requirements_by_id"]:
                continue
            req = data["requirements_by_id"][uid]
            lines.append(f"- [{uid}](#requirement-{anchor(uid)}) - **{reported_outcome(data, outcome_for_test(data['coverage_by_id'][uid], result))}**. {validity(test, req)}")
        lines += ["", "### Recorded results", "", "```json", json.dumps(result.get("metrics", {}), indent=2, sort_keys=True), "```", ""]
        if result.get("failure_reason"):
            lines.append(f"**Failure/block reason:** {result['failure_reason']}")
        if result.get("adjudication"):
            lines.append(f"**Operator decision:** {result['adjudication'].get('reason', '')}")
        limitations = result.get("limitations") or test.get("limitations") or []
        if limitations:
            lines += ["", "**Limitations:** " + "; ".join(limitations)]
        lines += ["", "### Selected evidence", "", "Raw evidence-file links are intentionally omitted. Selected graphs and screenshots are embedded in the PDF edition.", ""]
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return destination


def latex_report(run_dir: Path, data: dict[str, Any], include_requirements: bool) -> Path:
    run_dir = within(run_dir, ARTIFACTS)
    destination = run_dir / "document" / "qualification-report.tex"
    destination.parent.mkdir(parents=True, exist_ok=True)
    run = data["run"]
    lines = [r"\documentclass[10pt]{article}", r"\usepackage[margin=0.78in,includeheadfoot]{geometry}", r"\usepackage{longtable,booktabs,array,tabularx,graphicx,float,xcolor,hyperref,enumitem,fancyhdr,microtype}",
             r"\definecolor{GroupBlue}{HTML}{163A5F}", r"\definecolor{GroupTeal}{HTML}{1B7F79}", r"\definecolor{SoftBlue}{HTML}{EAF2F8}", r"\definecolor{SoftGreen}{HTML}{EAF7EF}", r"\definecolor{SoftGold}{HTML}{FFF5D6}",
             r"\hypersetup{colorlinks=true,linkcolor=GroupBlue,urlcolor=GroupTeal,pdftitle={ECE:4880 Group 21 Thermometer Quality Report},pdfauthor={ECE:4880 Group 21}}", r"\setlength{\parindent}{0pt}", r"\setlength{\parskip}{6pt}", r"\setlength{\emergencystretch}{3em}", r"\setlist{nosep,leftmargin=1.5em}",
             r"\pagestyle{fancy}", r"\fancyhf{}", r"\fancyhead[L]{\textcolor{GroupBlue}{ECE:4880 Group 21 Thermometer}}", rf"\fancyhead[R]{{\small Run {latex(run['run_id'])}}}", r"\fancyfoot[C]{\thepage}", r"\renewcommand{\headrulewidth}{0.4pt}",
             r"\begin{document}", r"\sloppy", r"\begin{titlepage}\centering", r"\vspace*{1.2in}", r"{\color{GroupBlue}\rule{\textwidth}{2pt}\par}\vspace{0.55in}", r"{\Huge\bfseries ECE:4880 Group 21\\[8pt]Thermometer Quality Report\par}\vspace{0.45in}", r"{\color{GroupBlue}\rule{\textwidth}{2pt}\par}\vspace{0.8in}",
             rf"{{\Large Run {latex(run['run_id'])}\par}}\vspace{{0.35in}}", rf"\fcolorbox{{GroupTeal}}{{SoftGreen}}{{\Large\strut Overall result: \textbf{{{latex(reported_outcome(data, run['outcome']))}}}}}\\[18pt]", rf"Profile: {latex(run['profile'])}\\",
             r"\vfill Group 21\quad |\quad ECE:4880\\[6pt]Generated from frozen requirements, test definitions, and retained run evidence.\end{titlepage}", r"\tableofcontents\clearpage",
             r"\section{Requirements traceability matrix}"]
    if not data["catalog_frozen"] or not data["catalog_matches_current"]:
        lines.append(r"\fcolorbox{red}{yellow!15}{\parbox{0.94\linewidth}{\textbf{Catalog provenance warning:} This legacy run did not retain frozen catalog files, or its recorded catalog hashes differ from the current repository. Outcomes remain historical evidence; rerun qualification before using current mappings as final approval.}}")
    lines += [r"\small", r"\begin{longtable}{p{0.23\linewidth}p{0.69\linewidth}}", r"\toprule Requirement & Qualification traceability\\\midrule\endhead"]
    for req in data["requirements"]:
        coverage = data["coverage_by_id"][req["uid"]]
        links = ", ".join(rf"\hyperlink{{test:{anchor(test_id)}}}{{{latex(test_id)}}}" for test_id in coverage["tests"]) or "UNMAPPED"
        lines.append(
            rf"\hyperlink{{requirement:{anchor(req['uid'])}}}{{\textbf{{{latex(req['uid'])}}}}}\newline\href{{{req['jira_url']}}}{{{latex(req['jira'])}}} & "
            rf"\textbf{{Status:}} {latex(reported_outcome(data, coverage['result'], compact=True))}\newline "
            rf"\textbf{{Linked tests:}} {links}\\[3pt]"
        )
    lines += [r"\bottomrule\end{longtable}\normalsize", r"\clearpage\section{Requirements}", r"Only applicable requirements are included. Each page records the current Jira description, its derivation, relationships, passing basis, and linked tests."]
    for req in data["requirements"]:
        coverage = data["coverage_by_id"][req["uid"]]
        parents, children = requirement_links(data, req)
        linked_tests = visible_linked_tests(data, req["uid"])
        revision = requirement_revision_note(req)
        lines += [
            r"\clearpage",
            rf"\hypertarget{{requirement:{anchor(req['uid'])}}}{{}}",
            rf"\subsection*{{{latex(req['uid'])} --- {latex(requirement_title(req))}}}",
            rf"\addcontentsline{{toc}}{{subsection}}{{{latex(req['uid'])} --- {latex(requirement_title(req))}}}",
            r"\begin{tabularx}{\textwidth}{@{}>{\bfseries}p{0.19\textwidth}X@{}}",
            rf"Result & {latex(reported_outcome(data, coverage['result']))}\\",
            rf"Level / component & {latex(req.get('level', ''))} / {latex(req.get('component', ''))}\\",
            rf"Jira & \href{{{req['jira_url']}}}{{{latex(req['jira'])} --- open requirement}}\\",
            r"\end{tabularx}",
            r"\subsubsection*{Current Jira description}",
            rf"\fcolorbox{{GroupBlue}}{{SoftBlue}}{{\parbox{{0.94\linewidth}}{{{latex(req['text'])}}}}}",
        ]
        if revision:
            lines += [r"\subsubsection*{Revision note}", rf"\fcolorbox{{GroupTeal}}{{SoftGold}}{{\parbox{{0.94\linewidth}}{{\textbf{{Edited requirement.}} {latex(revision)} The description above is the newest frozen version used by this run.}}}}"]
        lines += [r"\subsubsection*{Derivation and relationships}", rf"\textbf{{Source:}} {latex(req.get('source', 'Jira'))} (snapshot {latex(req.get('snapshot_date', 'unknown'))})\par"]
        if parents:
            parent_links = ", ".join(rf"\hyperlink{{requirement:{anchor(item['uid'])}}}{{{latex(item['uid'])}}}" for item in parents)
            lines.append(rf"\textbf{{Parents:}} {parent_links}\par")
        else:
            lines.append(r"\textbf{Parents:} None --- top-level project or stakeholder requirement.\par")
        if children:
            child_links = ", ".join(rf"\hyperlink{{requirement:{anchor(item['uid'])}}}{{{latex(item['uid'])}}}" for item in children)
            lines.append(rf"\textbf{{Children:}} {child_links}\par")
        else:
            lines.append(r"\textbf{Children:} None.\par")
        lines += [r"\subsubsection*{Passing criteria}", r"This requirement passes only when every linked applicable test passes and the observed behavior satisfies the complete Jira description above.", r"\subsubsection*{Tests that verify this requirement}", r"\begin{itemize}"]
        if linked_tests:
            for test in linked_tests:
                result = data["results_by_id"].get(test["id"], {})
                lines.append(rf"\item \hyperlink{{test:{anchor(test['id'])}}}{{\textbf{{{latex(test['id'])} --- {latex(test['title'])}}}}}: {latex(reported_outcome(data, result.get('outcome', 'BLOCKED'), compact=True))}. {latex(test.get('description', ''))}")
        else:
            lines.append(r"\item No applicable test is mapped.")
        lines.append(r"\end{itemize}")
    lines += [r"\clearpage\section{Test results}"]
    for result in data["results"]:
        test = data["tests_by_id"][result["test_id"]]
        setup_id = test.get("setup_group", "software")
        setup = data["setup_groups"][setup_id]
        lines += [r"\clearpage", rf"\hypertarget{{test:{anchor(test['id'])}}}{{}}", rf"\section{{{latex(test['id'])} --- {latex(test['title'])}}}",
                  rf"\textbf{{Outcome:}} {latex(reported_outcome(data, result['outcome']))}\\",
                  rf"\textbf{{Method:}} {latex(test['method'])}\\",
                  rf"\textbf{{Subsystem:}} {latex(test['subsystem'])}",
                  r"\subsection{What this test proves and why}", latex(plain_test_rationale(test)),
                  r"\subsection{Passing criteria}", r"\begin{itemize}"]
        for criterion in test_passing_criteria(test):
            lines.append(rf"\item {latex(criterion)}")
        lines += [r"\end{itemize}", r"\subsection{Required setup}", rf"\textbf{{{latex(setup['title'])}}} (\texttt{{{latex(setup_id)}}})", r"\begin{itemize}"]
        for instruction in setup["instructions"]:
            lines.append(rf"\item {latex(instruction)}")
        lines += [r"\end{itemize}", r"\subsection{Procedure}", r"\begin{enumerate}"]
        for step in procedure_text(test):
            lines.append(rf"\item {latex(step)}")
        lines += [r"\end{enumerate}", r"\subsection{Requirements covered}", r"\begin{itemize}"]
        for uid in test["requirements"]:
            if uid not in data["requirements_by_id"]:
                continue
            req = data["requirements_by_id"][uid]
            lines.append(rf"\item \hyperlink{{requirement:{anchor(uid)}}}{{\textbf{{{latex(uid)}}}}} --- {latex(reported_outcome(data, result['outcome'], compact=True))}. {latex(validity(test, req))}")
        lines += [r"\end{itemize}", r"\subsection{Recorded results and limitations}"]
        metrics = result.get("metrics", {})
        if metrics:
            for key, value in sorted(metrics.items()):
                rendered = json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else value
                lines.append(rf"\textbf{{{latex(key)}:}} {latex(rendered)}\par")
        else:
            lines.append("No structured measurements were recorded.")
        if result.get("failure_reason"):
            lines.append(rf"\textbf{{Failure/block reason:}} {latex(result['failure_reason'])}")
        if result.get("adjudication"):
            lines.append(rf"\textbf{{Operator decision:}} {latex(result['adjudication'].get('reason', ''))}")
        limitations = result.get("limitations") or test.get("limitations") or []
        if limitations:
            lines.append(rf"\textbf{{Limitations:}} {latex('; '.join(limitations))}")
        lines += [r"\subsection{Selected evidence}", r"Raw evidence-file links are intentionally omitted. Selected visual evidence is embedded below."]
        all_evidence = list(result.get("evidence", [])) + list(result.get("report_images", []))
        for image in [item for item in all_evidence if Path(item).suffix.lower() in IMAGE_SUFFIXES][:6]:
            image_path = (run_dir / image).resolve().as_posix()
            lines += [r"\begin{figure}[H]\centering", rf"\includegraphics[width=.92\textwidth,height=.55\textheight,keepaspectratio]{{\detokenize{{{image_path}}}}}", rf"\caption{{Selected visual evidence for {latex(test['id'])}}}", r"\end{figure}"]
    lines.append(r"\end{document}")
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return destination


def find_tectonic() -> str | None:
    """Locate Tectonic, including the compiler bundled with Codex on Windows."""

    configured = os.environ.get("TECTONIC")
    if configured:
        configured_path = Path(configured).expanduser()
        if configured_path.is_file():
            return str(configured_path.resolve())
        resolved = shutil.which(configured)
        if resolved:
            return resolved

    on_path = shutil.which("tectonic")
    if on_path:
        return on_path

    codex_root = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    executable_names = ("tectonic.exe", "tectonic")
    candidates: list[Path] = []
    versioned_cache = codex_root / "plugins" / "cache" / "openai-bundled" / "latex"
    if versioned_cache.is_dir():
        for executable_name in executable_names:
            candidates.extend(versioned_cache.glob(f"*/bin/{executable_name}"))
    marketplace = codex_root / ".tmp" / "bundled-marketplaces" / "openai-bundled" / "plugins" / "latex" / "bin"
    candidates.extend(marketplace / name for name in executable_names)
    existing = [candidate for candidate in candidates if candidate.is_file()]
    if not existing:
        return None
    return str(max(existing, key=lambda candidate: candidate.stat().st_mtime).resolve())


def _run_compiler(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        print(f"PDF compiler could not be started: {exc}", file=sys.stderr)
        return None


def _report_compiler_failure(process: subprocess.CompletedProcess[str], compiler: str) -> None:
    diagnostic = "\n".join(part.strip() for part in (process.stdout, process.stderr) if part and part.strip())
    if len(diagnostic) > 4000:
        diagnostic = diagnostic[-4000:]
    print(f"{Path(compiler).name} exited with code {process.returncode}.", file=sys.stderr)
    if diagnostic:
        print(diagnostic, file=sys.stderr)


def compile_pdf(tex: Path) -> Path | None:
    output = tex.with_suffix(".pdf")
    tectonic = find_tectonic()
    if tectonic:
        process = _run_compiler([tectonic, "--outdir", str(tex.parent), tex.name], tex.parent)
        if process is not None and process.returncode == 0 and output.is_file():
            return output
        if process is not None:
            _report_compiler_failure(process, tectonic)
        return None
    pdflatex = shutil.which("pdflatex")
    if pdflatex:
        process = _run_compiler([pdflatex, "-interaction=nonstopmode", "-halt-on-error", tex.name], tex.parent)
        if process is not None and process.returncode == 0 and output.is_file():
            return output
        if process is not None:
            _report_compiler_failure(process, pdflatex)
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id", nargs="?", default="latest")
    parser.add_argument("--include-requirement-pages", action="store_true", help="compatibility flag; applicable requirement pages are now always included")
    parser.add_argument("--pdf", action="store_true", help="compile with tectonic or pdflatex when available")
    args = parser.parse_args(argv)
    try:
        run = resolve_run(args.run_id)
        data = gather(run)
        markdown = markdown_report(run, data, args.include_requirement_pages)
        tex = latex_report(run, data, args.include_requirement_pages)
        print(markdown)
        print(tex)
        if args.pdf:
            pdf = compile_pdf(tex)
            if not pdf:
                print("PDF compiler not found or compilation failed; LaTeX remains available", file=sys.stderr)
                return 2
            print(pdf)
        return 0
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        print(f"report generation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
