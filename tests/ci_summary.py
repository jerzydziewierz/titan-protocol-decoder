"""Write a Markdown summary of reports/ for the GitHub Actions job page.

Usage: python tests/ci_summary.py <test.sh log>  (prints Markdown on stdout)
Reads only files that test.sh made; a missing file gives a "not run" line, not an error.
"""
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


def load(name):
    path = REPORTS / name
    return json.loads(path.read_text()) if path.is_file() else None


def stages(log):
    lines = Path(log).read_text(errors="replace").splitlines() if Path(log).is_file() else []
    rows = [(l[:4], l[6:]) for l in lines if l.startswith(("PASS  ", "FAIL  "))]
    out = ["## Stages", "", "| Result | Stage |", "| --- | --- |"]
    out += [f"| {'✅' if r == 'PASS' else '❌'} {r} | {name} |" for r, name in rows] or ["| ⚠️ | test.sh did not finish |"]
    return out


def cpp():
    out = ["## C++ assertions and heap guard", "", "| Build | Assertions | Heap guard |", "| --- | --- | --- |"]
    for tree in ("build-autotests", "build-autotests-sanitize"):
        log = REPORTS / f"{tree}-titan-tests.log"
        total = re.search(r"^TOTAL (\d+) FAILED (\d+)", log.read_text(), re.M) if log.is_file() else None
        heap = REPORTS / f"{tree}-titan-no-heap.log"
        heap_ok = heap.is_file() and heap.read_text().startswith("PASS")
        out.append(f"| `{tree}` | {f'{int(total[1]) - int(total[2])}/{total[1]} pass' if total else 'not run'} | {'pass' if heap_ok else 'FAIL'} |")
    return out


def python():
    out = ["## Python suite (failing subcases)", ""]
    for name in ("build-autotests-python.log", "build-autotests-sanitize-python.log",
                 "extensive-build-autotests-python.log", "extensive-build-autotests-sanitize-python.log"):
        log = REPORTS / name
        if not log.is_file():
            out.append(f"* `{name}`: not run"); continue
        text = log.read_text(errors="replace")
        ran = re.search(r"^Ran (\d+) tests", text, re.M)
        fails = re.findall(r"^(FAIL|ERROR): (test_\w+) \([^)]*\)(.*)$", text, re.M)
        out.append(f"* `{name}`: {ran[1] if ran else '?'} tests, {len(fails)} failing subcases")
        out += [f"  * {kind} `{test}`{rest}" for kind, test, rest in fails]
    out += ["", "See `DEFECTS.md` for the defect that each failure belongs to."]
    return out


def mutations():
    data = load("mutations.json")
    if not data:
        return ["## Mutations", "", "not run"]
    rows = [r for r in data["results"] if r["name"] != "baseline"]
    killed = sum(r["status"] == "killed" for r in rows)
    out = ["## Mutations", "", f"{killed} of {len(rows)} killed.", "", "| Mutation | Status | New failures |", "| --- | --- | --- |"]
    out += [f"| `{r['name']}` | {r['status']} | {len(r.get('new_failures', []))} |" for r in rows]
    return out


def performance():
    data = load("performance.json")
    if not data:
        return ["## Benchmark", "", "not run"]
    out = ["## Benchmark (100,000 packets, median of 3 Release trials)", "",
           "| Workload | packets/s | MiB/s | peak RSS KiB |", "| --- | --- | --- | --- |"]
    out += [f"| {r['workload']} | {r['median_packets_s']:,.0f} | {r['median_mib_s']:.2f} | {max(t['max_rss_kib'] for t in r['trials']):,.0f} |"
            for r in data["results"]]
    m = data["callback_metrics"]
    out += ["", f"Resource probe: {m['read_calls']:,} reads, {m['write_calls']:,} writes, {m['output_bytes']:,} output bytes for {m['packets']:,} ping packets; workspace {m['workspace_bytes']:,} bytes."]
    return out


def profile():
    data = load("profile/profile.json")
    if not data:
        return ["## Profile", "", "not run"]
    out = ["## Profile (300,000 packets, median of 3 Release trials)", "",
           "| Workload | wall s | user s | system s |", "| --- | --- | --- | --- |"]
    for w in data["workloads"]:
        med = {k: statistics.median(t[k] for t in w["trials"]) for k in ("wall", "user", "system")}
        out.append(f"| {w['name']} | {med['wall']:.2f} | {med['user']:.2f} | {med['system']:.2f} |")
    out += ["", f"perf flame graph: {'included' if data.get('perf_available') else 'not available (perf restricted or missing)'}. Open `reports/profile/index.html` from the `reports` artifact."]
    return out


def main():
    sections = [stages(sys.argv[1] if len(sys.argv) > 1 else ""), cpp(), python(), mutations(), performance(), profile()]
    print("# Titan decoder test report\n")
    print("\n\n".join("\n".join(s) for s in sections))


if __name__ == "__main__":
    main()
