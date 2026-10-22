"""Finite, bounded test campaigns with process ownership and reproducible evidence."""
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
REPORTS = ROOT / "reports"
STATE = REPORTS / "running.json"
STOP = REPORTS / "stop.request"
CHILD = None


def save(path, value):
    """Publish complete result documents atomically."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, indent=2) + "\n")
    tmp.replace(path)


def birth(pid):
    """Avoid mistaking a recycled process ID for this campaign."""
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
    except FileNotFoundError:
        return None


def run(command, timeout=60, **kwargs):
    """Own every child process group and stop it on timeout or user request."""
    global CHILD
    if STOP.exists():
        raise InterruptedError("stop requested")
    start = time.monotonic()
    with subprocess.Popen(list(map(str, command)), start_new_session=True, **kwargs) as child:
        CHILD = child
        while child.poll() is None:
            if STOP.exists() or time.monotonic()-start > timeout:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
                CHILD = None
                raise TimeoutError(str(command))
            time.sleep(.02)
        CHILD = None
        return child.returncode, time.monotonic()-start


def logged(name, command, timeout=60, **kwargs):
    """Keep full compiler/test diagnostics, including expected red-suite output."""
    with (REPORTS / (name+".log")).open("wb") as log:
        code, seconds = run(command, timeout, stdout=log, stderr=subprocess.STDOUT, **kwargs)
    return {"exit": code, "seconds": seconds, "log": name+".log"}


def build(directory, sanitize=False):
    """Separate build trees prevent test flags from altering the learner's CLion build."""
    flags = "-fsanitize=address,undefined -fno-omit-frame-pointer -fno-pie -no-pie" if sanitize else ""
    for suffix, command in [("configure", ["cmake", "-S", ".", "-B", directory,
            "-DCMAKE_BUILD_TYPE="+("Debug" if sanitize else "Release"), "-DCMAKE_CXX_FLAGS="+flags]),
            ("build", ["cmake", "--build", directory, "-j2"])]:
        r = logged(directory+"-"+suffix, command)
        if r["exit"]:
            raise RuntimeError(r)


def provenance():
    """Tie measurements to source, compiler, platform and environment lock."""
    files = [Path(x) for x in ("src/titan.cpp", "src/titan.hpp", "src/main.cpp", "CMakeLists.txt", "pixi.lock")]
    files += list(Path("tests").glob("*.*"))
    return {"sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()},
            "platform": platform.platform(), "python": sys.version,
            "compiler": subprocess.check_output(["c++", "--version"], text=True).splitlines()[0]}


def check():
    """Run normal and sanitizer checks without hiding failures behind expected-failure markers."""
    results = {}
    for directory, sanitize in (("build-autotests", False), ("build-autotests-sanitize", True)):
        build(directory, sanitize)
        for name in ("titan-tests", "titan-no-heap"):
            results[directory+"/"+name] = logged(directory+"-"+name, [Path(directory)/name])
        env = dict(os.environ, TITAN_EXE=str(ROOT/directory/"recode"))
        results[directory+"/python"] = logged(directory+"-python", [sys.executable, "tests/test_yaml.py"], 120, env=env)
    save(REPORTS/"checks.json", {"provenance": provenance(), "results": results})
    return int(any(r["exit"] for r in results.values()))


# Each mutation has a specific behavioral purpose; only newly failing named checks kill it.
MUTATIONS = [
    ("accept_numeric_suffix", "(result.ptr==(message.data()+message.size()))", "true"),
    ("drop_integer_sign", "std::to_chars(out_chars, out_chars+sizeof(out_chars), message)",
     "std::to_chars(out_chars, out_chars+sizeof(out_chars), static_cast<std::uint64_t>(message))"),
    ("preview_31_bytes", "message.substr(0, 32)", "message.substr(0, 31)"),
    ("wrong_hex_nibble", "hex[byte & 15]", "hex[(byte & 15) ^ 1]"),
    ("suppress_read_failure", "error= DepacketError::input;", "error= DepacketError::none;"),
    ("reject_valid_housekeeping", "return PacketHousekeepingError::none;", "return PacketHousekeepingError::field_unconvertable;"),
    ("wrong_start_marker", "candidate_char[0]=='$'", "candidate_char[0]=='!'"),
    ("wrong_end_marker", "candidate_char[0]=='|'", "candidate_char[0]=='!'"),
    ("skip_first_payload_byte", "size_t last_separator = 0;", "size_t last_separator = 1;"),
    ("fix_overflow_boundary_control", "candidate_packet_size>workspace.input_buffer.size()", "candidate_packet_size>=workspace.input_buffer.size()"),
]


def failed_checks(path):
    """Read assertion identities; crashes and build failures are never assertion kills."""
    return {line[5:] for line in path.read_text(errors="replace").splitlines() if line.startswith("FAIL\t")}


def mutation():
    """Mutate disposable source copies; existing defects cannot inflate the score."""
    results = []
    source = Path("src/titan.cpp").read_text()
    baseline = None
    with tempfile.TemporaryDirectory(prefix="titan-mutations-") as tmp:
        for name, old, new in [("baseline", "", "")]+MUTATIONS:
            work = Path(tmp)
            if old and old not in source:
                raise RuntimeError("mutation no longer applies: "+name)
            (work/"titan.cpp").write_text(source.replace(old, new, 1) if old else source)
            result = logged("mutation-"+name+"-build", ["c++", "-std=c++20", "-O1", "-Isrc",
                work/"titan.cpp", "tests/tests.cpp", "-o", work/"test"])
            if result["exit"]:
                results.append({"name": name, "status": "build_error"}); continue
            result = logged("mutation-"+name, [work/"test"], 10)
            failures = failed_checks(REPORTS/result["log"])
            complete = "TOTAL " in (REPORTS/result["log"]).read_text(errors="replace")
            if name == "baseline":
                if not complete:
                    raise RuntimeError("baseline did not finish")
                baseline = failures
            newly = sorted(failures - baseline)
            results.append({"name": name, "status": "incomplete" if not complete else
                "killed" if newly else "baseline" if name=="baseline" else "survived",
                "new_failures": newly, "resolved_failures": sorted(baseline-failures)})
    save(REPORTS/"mutations.json", {"provenance": provenance(), "results": results,
        "note": "Boundary fix is a positive control, excluded from mutation score. Survivors are coverage gaps, not proof of equivalence."})
    return 0


def benchmark():
    """Measure finite CLI throughput/RSS with identical input and output redirected to /dev/null."""
    build("build-autotests")
    results=[]
    packets={"ping": b"$1;2;3;;|", "housekeeping": b"$10;2;3;0;-4;5;6;-7;|", "malformed": b"$x;bad;|"}
    with tempfile.TemporaryDirectory(prefix="titan-benchmark-") as tmp:
        for name, packet in packets.items():
            data=packet*100000
            path=Path(tmp)/"input"; path.write_bytes(data)
            trials=[]
            for i in range(3):
                metrics=Path(tmp)/"time"
                with path.open("rb") as source, open(os.devnull,"wb") as sink:
                    code, elapsed=run(["/usr/bin/time", "-f", "%U %S %M", "-o", metrics,
                        ROOT/"build-autotests/recode"], 30, stdin=source, stdout=sink)
                user, system, rss=map(float,metrics.read_text().split())
                trials.append({"seconds": elapsed,"user_seconds":user,"system_seconds":system,"max_rss_kib":rss,"exit":code})
            elapsed=statistics.median(t["seconds"] for t in trials)
            results.append({"workload":name,"bytes":len(data),"packets":100000,
                "sha256":hashlib.sha256(data).hexdigest(),"trials":trials,
                "median_mib_s":len(data)/1048576/elapsed,"median_packets_s":100000/elapsed})
    save(REPORTS/"performance.json", {"provenance":provenance(),"results":results,
        "callback_metrics":json.loads(subprocess.check_output([str(ROOT/"build-autotests/titan-resource-probe")], text=True, timeout=10)),
        "note":"Includes startup and syscalls, ~20ms polling resolution. Malformed throughput measures discarding, not successful archival conversion."})
    return 0


def profile():
    """Run profiling under the same status/stop ownership as other campaigns."""
    from profile_run import profile as collect
    return collect(sys.modules[__name__])


def main():
    REPORTS.mkdir(exist_ok=True)
    mode=sys.argv[1] if len(sys.argv)>1 else "status"
    state=json.loads(STATE.read_text()) if STATE.exists() else {}
    live=bool(state and birth(state["pid"])==state["birth"])
    if mode=="status":
        print(json.dumps({"live":live, **state})); return 0
    if mode=="stop":
        if live: STOP.touch()
        print("stop requested" if live else "no active campaign"); return 0
    if live: raise RuntimeError("another campaign is active")
    STOP.unlink(missing_ok=True)
    save(STATE,{"pid":os.getpid(),"birth":birth(os.getpid()),"mode":mode,"holds":"local build tree and owned child processes"})
    try:
        return {"check":check,"mutation":mutation,"benchmark":benchmark,"profile":profile}[mode]()
    finally:
        if CHILD and CHILD.poll() is None:
            os.killpg(CHILD.pid,signal.SIGKILL)
        STATE.unlink(missing_ok=True)
        STOP.unlink(missing_ok=True)


if __name__=="__main__":
    sys.exit(main())
