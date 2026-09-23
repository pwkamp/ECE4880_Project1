#!/usr/bin/env python3
"""Build an evidence-rich Markdown/LaTeX qualification document from a run."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verification.core.paths import existing_run, within

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

    outcome = str(value)
    if not data["catalog_frozen"] or not data["catalog_matches_current"]:
        return f"STALE ({outcome})" if compact else f"HISTORICAL {outcome} - RETEST REQUIRED"
    return outcome


def validity(test: dict[str, Any], requirement: dict[str, Any]) -> str:
    override = (test.get("requirement_rationales") or {}).get(requirement["uid"])
    if override:
        return override
    instruments = ", ".join(test.get("instrumentation", [])[:3]) or "recorded assertions"
    return f"Directly evaluates “{requirement['text']}” using {instruments}; the test-level rationale and limitations define the evidence boundary."


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
        "coverage_by_id": {item["uid"]: item for item in coverage["requirements"]},
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
            lines.append(f"Detailed controlled procedure: `{path.relative_to(REPOSITORY).as_posix()}`.")
    for step in test.get("manual_steps", []):
        lines.append(f"{step.get('instruction', '')} Expected evidence: {step.get('expected', '')}.")
    if not lines:
        entrypoint = test.get("entrypoint", {})
        lines.append(f"Execute `{entrypoint.get('command', test['description'])}` and require {test.get('pass_policy', {})}.")
    return lines


def markdown_report(run_dir: Path, data: dict[str, Any], include_requirements: bool) -> Path:
    run_dir = within(run_dir, ARTIFACTS)
    destination = run_dir / "document" / "qualification-report.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    run = data["run"]
    counts = Counter(item["outcome"] for item in data["results"])
    lines = [
        "# ECE4880 Thermometer Qualification Report", "",
        f"Run: `{run['run_id']}`  ", f"Profile: `{run['profile']}`  ",
        f"Overall outcome: **{reported_outcome(data, run['outcome'])}**  ", f"Git revision: `{run.get('git_sha', 'unknown')}` ({run.get('git_state', 'unknown')})  ",
        f"Results: {', '.join(f'{key}={value}' for key, value in sorted(counts.items()))}", "",
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
        lines.append(f"| {req['uid']} | [{req['jira']}]({req['jira_url']}) | **{reported_outcome(data, coverage['result'], compact=True)}** | {links or 'UNMAPPED'} |")
    for result in data["results"]:
        test = data["tests_by_id"][result["test_id"]]
        setup_id = test.get("setup_group", "software")
        setup = data["setup_groups"][setup_id]
        lines += ["", "---", "", f"<a id=\"test-{anchor(test['id'])}\"></a>", f"## {test['id']} — {test['title']}", "",
                  f"**Outcome:** {reported_outcome(data, result['outcome'])}  ", f"**Method:** {test['method']}  ", f"**Subsystem:** {test['subsystem']}  ", "",
                  "### Rationale", "", test["rationale"], "", "### Required setup", "",
                  f"**{setup['title']}** (`{setup_id}`)", ""]
        lines.extend(f"- {instruction}" for instruction in setup["instructions"])
        lines += ["", "### Procedure", ""]
        lines.extend(f"{index}. {step}" for index, step in enumerate(procedure_text(test), 1))
        lines += ["", "### Requirement verdicts", "", "| Requirement | Test contribution | Why this evidence is valid |", "|---|---|---|"]
        for uid in test["requirements"]:
            req = data["requirements_by_id"][uid]
            lines.append(f"| [{uid}]({req['jira_url']}) | **{reported_outcome(data, outcome_for_test(data['coverage_by_id'][uid], result))}** | {validity(test, req)} |")
        lines += ["", "### Measurements and limitations", "", "```json", json.dumps(result.get("metrics", {}), indent=2, sort_keys=True), "```", ""]
        if result.get("failure_reason"):
            lines.append(f"**Failure/block reason:** {result['failure_reason']}")
        if result.get("adjudication"):
            lines.append(f"**Operator adjudication:** `{json.dumps(result['adjudication'], sort_keys=True)}`")
        limitations = result.get("limitations") or test.get("limitations") or []
        if limitations:
            lines += ["", "**Limitations:** " + "; ".join(limitations)]
        lines += ["", "### Evidence", ""]
        all_evidence = list(result.get("evidence", [])) + list(result.get("report_images", []))
        images = [item for item in all_evidence if Path(item).suffix.lower() in IMAGE_SUFFIXES]
        for evidence in all_evidence:
            relative = "../" + evidence
            lines.append(f"- [{evidence}]({relative})")
        for image in images[:6]:
            lines += ["", f"![{test['id']} evidence](../{image})"]
    if include_requirements:
        lines += ["", "# Requirement rationale appendix", ""]
        for req in data["requirements"]:
            coverage = data["coverage_by_id"][req["uid"]]
            parent_text = ", ".join(req.get("parents", [])) or "top-level project need"
            lines += [f"## {req['uid']} — {req.get('jira_summary', '')}", "", f"**Jira:** [{req['jira']}]({req['jira_url']})  ",
                      f"**Status:** {reported_outcome(data, coverage['result'])}  ", f"**Parent basis:** {parent_text}  ", "", req["text"], "",
                      f"This requirement exists to make the {req.get('component', 'system')} behavior objectively traceable from {parent_text}. Linked tests: {', '.join(coverage['tests']) or 'none'}. Qualification rationale: {coverage['reason']}.", ""]
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return destination


def latex_report(run_dir: Path, data: dict[str, Any], include_requirements: bool) -> Path:
    run_dir = within(run_dir, ARTIFACTS)
    destination = run_dir / "document" / "qualification-report.tex"
    destination.parent.mkdir(parents=True, exist_ok=True)
    run = data["run"]
    lines = [r"\documentclass[10pt]{article}", r"\usepackage[margin=0.72in]{geometry}", r"\usepackage{longtable,booktabs,array,graphicx,float,xcolor,hyperref}",
             r"\hypersetup{colorlinks=true,linkcolor=blue,urlcolor=blue}", r"\setlength{\parindent}{0pt}", r"\setlength{\parskip}{5pt}", r"\setlength{\emergencystretch}{2em}",
             r"\begin{document}", r"\begin{titlepage}\centering", r"{\Huge ECE4880 Thermometer\\Qualification Report\par}\vspace{1cm}",
             rf"{{\Large Run {latex(run['run_id'])}\par}}\vspace{{1cm}}", rf"Overall outcome: \textbf{{{latex(reported_outcome(data, run['outcome']))}}}\\", rf"Profile: {latex(run['profile'])}\\", rf"Git: {latex(run.get('git_sha', 'unknown'))} ({latex(run.get('git_state', 'unknown'))})\\",
             r"\vfill Generated from versioned requirements, test definitions, and retained run evidence.\end{titlepage}", r"\tableofcontents\clearpage",
             r"\section{Requirements traceability matrix}"]
    if not data["catalog_frozen"] or not data["catalog_matches_current"]:
        lines.append(r"\fcolorbox{red}{yellow!15}{\parbox{0.94\linewidth}{\textbf{Catalog provenance warning:} This legacy run did not retain frozen catalog files, or its recorded catalog hashes differ from the current repository. Outcomes remain historical evidence; rerun qualification before using current mappings as final approval.}}")
    lines += [r"\small", r"\begin{longtable}{p{0.23\linewidth}p{0.69\linewidth}}", r"\toprule Requirement & Qualification traceability\\\midrule\endhead"]
    for req in data["requirements"]:
        coverage = data["coverage_by_id"][req["uid"]]
        links = ", ".join(rf"\hyperlink{{test:{anchor(test_id)}}}{{{latex(test_id)}}}" for test_id in coverage["tests"]) or "UNMAPPED"
        lines.append(
            rf"\textbf{{{latex(req['uid'])}}}\newline\href{{{req['jira_url']}}}{{{latex(req['jira'])}}} & "
            rf"\textbf{{Status:}} {latex(reported_outcome(data, coverage['result'], compact=True))}\newline "
            rf"\textbf{{Linked tests:}} {links}\\[3pt]"
        )
    lines += [r"\bottomrule\end{longtable}\normalsize"]
    for result in data["results"]:
        test = data["tests_by_id"][result["test_id"]]
        setup_id = test.get("setup_group", "software")
        setup = data["setup_groups"][setup_id]
        lines += [r"\clearpage", rf"\hypertarget{{test:{anchor(test['id'])}}}{{}}", rf"\section{{{latex(test['id'])} --- {latex(test['title'])}}}",
                  rf"\textbf{{Outcome:}} {latex(reported_outcome(data, result['outcome']))}\\",
                  rf"\textbf{{Method:}} {latex(test['method'])}\\",
                  rf"\textbf{{Subsystem:}} {latex(test['subsystem'])}",
                  r"\subsection{Rationale}", latex(test["rationale"]),
                  r"\subsection{Required setup}", rf"\textbf{{{latex(setup['title'])}}} (\texttt{{{latex(setup_id)}}})", r"\begin{itemize}"]
        for instruction in setup["instructions"]:
            lines.append(rf"\item {latex(instruction)}")
        lines += [r"\end{itemize}", r"\subsection{Procedure}", r"\begin{enumerate}"]
        for step in procedure_text(test):
            lines.append(rf"\item {latex(step)}")
        lines += [r"\end{enumerate}", r"\subsection{Requirement verdicts}", r"\small\begin{longtable}{p{0.25\linewidth}p{0.67\linewidth}}", r"\toprule Requirement and result & Evidence validity rationale\\\midrule\endhead"]
        for uid in test["requirements"]:
            req = data["requirements_by_id"][uid]
            lines.append(rf"\href{{{req['jira_url']}}}{{\textbf{{{latex(uid)}}}}}\newline {latex(reported_outcome(data, result['outcome'], compact=True))} & {latex(validity(test, req))}\\[3pt]")
        lines += [r"\bottomrule\end{longtable}\normalsize", r"\subsection{Measurements, limitations, and disposition}"]
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
            lines.append(rf"\textbf{{Operator adjudication:}} {latex(json.dumps(result['adjudication'], sort_keys=True))}")
        limitations = result.get("limitations") or test.get("limitations") or []
        if limitations:
            lines.append(rf"\textbf{{Limitations:}} {latex('; '.join(limitations))}")
        lines += [r"\subsection{Evidence}", r"\begin{itemize}"]
        all_evidence = list(result.get("evidence", [])) + list(result.get("report_images", []))
        for evidence in all_evidence:
            lines.append(rf"\item \href{{run:../{evidence}}}{{\nolinkurl{{{evidence}}}}}")
        lines.append(r"\end{itemize}")
        for image in [item for item in all_evidence if Path(item).suffix.lower() in IMAGE_SUFFIXES][:6]:
            image_path = (run_dir / image).resolve().as_posix()
            lines += [r"\begin{figure}[H]\centering", rf"\includegraphics[width=.92\textwidth,height=.55\textheight,keepaspectratio]{{\detokenize{{{image_path}}}}}", rf"\caption{{{latex(test['id'])} retained evidence: {latex(Path(image).name)}}}", r"\end{figure}"]
    if include_requirements:
        lines += [r"\clearpage\section{Requirement rationale appendix}"]
        for req in data["requirements"]:
            coverage = data["coverage_by_id"][req["uid"]]
            parents = ", ".join(req.get("parents", [])) or "top-level project need"
            lines += [r"\clearpage", rf"\subsection{{{latex(req['uid'])} --- {latex(req.get('jira_summary', ''))}}}", rf"\href{{{req['jira_url']}}}{{{latex(req['jira'])}}}\quad \textbf{{Status:}} {latex(reported_outcome(data, coverage['result']))}", latex(req["text"]),
                      latex(f"This requirement exists to make the {req.get('component', 'system')} behavior objectively traceable from {parents}. Linked tests: {', '.join(coverage['tests']) or 'none'}. Qualification rationale: {coverage['reason']}.")]
    lines.append(r"\end{document}")
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return destination


def compile_pdf(tex: Path) -> Path | None:
    output = tex.with_suffix(".pdf")
    tectonic = shutil.which("tectonic")
    if tectonic:
        process = subprocess.run([tectonic, "--outdir", str(tex.parent), str(tex)], cwd=tex.parent, check=False)
        return output if process.returncode == 0 and output.is_file() else None
    pdflatex = shutil.which("pdflatex")
    if pdflatex:
        process = subprocess.run([pdflatex, "-interaction=nonstopmode", "-halt-on-error", tex.name], cwd=tex.parent, check=False)
        return output if process.returncode == 0 and output.is_file() else None
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id", nargs="?", default="latest")
    parser.add_argument("--include-requirement-pages", action="store_true", help="add one rationale/status page per requirement")
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
