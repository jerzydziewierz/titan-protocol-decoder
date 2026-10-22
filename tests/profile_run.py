"""Collect bounded CPU, syscall and optional perf evidence; render an offline report."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


def profile(campaign):
    """Use normal Release timings separately from intrusive trace/sample runs."""
    c = campaign
    c.build("build-autotests")
    directory = c.REPORTS / "profile"
    directory.mkdir(exist_ok=True)
    result = {"provenance": c.provenance(), "workloads": [], "notes": [
        "Normal timings use an uninstrumented Release binary and /dev/null output.",
        "strace uses a smaller workload; its timings include tracing effects and are not normal-run cost estimates.",
        "perf samples userspace only. Kernel CPU time is measured separately; it is not present in the flame graph."]}
    executable = c.ROOT / "build-autotests/recode"
    # Test access rather than assuming the sysctl alone determines perf availability.
    with (directory/"perf-access.log").open("wb") as log:
        code, _ = c.run(["perf", "stat", "-e", "task-clock:u", "--", "true"], stdout=log, stderr=log)
    result["perf_available"] = code == 0
    sampled_executable = executable
    if result["perf_available"]:
        # Keep Release optimization; add debug information only in a separate tree.
        for label, command in (("configure", ["cmake", "-S", ".", "-B", "build-autotests-profile",
                "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_CXX_FLAGS=-g", "-DBUILD_TESTING=OFF"]),
                ("build", ["cmake", "--build", "build-autotests-profile", "-j2"])):
            status = c.logged("profile-"+label, command)
            if status["exit"]:
                raise RuntimeError(status)
        sampled_executable = c.ROOT / "build-autotests-profile/recode"
    result["executables"] = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                             for path in (executable, sampled_executable)}
    with tempfile.TemporaryDirectory(prefix="titan-profile-") as temporary:
        temporary = Path(temporary)
        for name, packet in (("ping", b"$1;2;3;;|"), ("housekeeping", b"$10;2;3;0;-4;5;6;-7;|")):
            source_path = temporary/"input"
            source_path.write_bytes(packet*300000)
            row = {"name": name, "packets": 300000, "input_bytes": len(packet)*300000, "trials": []}
            # Three untraced trials establish where total CPU time is spent.
            for i in range(3):
                timing = directory/f"{name}-time-{i}.txt"
                with source_path.open("rb") as source, open(os.devnull,"wb") as sink:
                    code, _ = c.run(["/usr/bin/time", "-f", "%e %U %S %M", "-o", timing, executable],
                                    stdin=source, stdout=sink, timeout=30)
                if code:
                    raise RuntimeError(f"profile baseline failed: {name}, {code}")
                wall, user, system, rss = map(float, timing.read_text().split())
                row["trials"].append(dict(wall=wall, user=user, system=system, rss_kib=rss))
            if result["perf_available"]:
                # DWARF unwinding preserves optimized Release code; no production edits.
                data = directory/f"{name}.perf.data"
                with source_path.open("rb") as source, open(os.devnull,"wb") as sink, (directory/f"{name}-perf.log").open("wb") as log:
                    code, _ = c.run(["perf", "record", "-e", "cpu-clock:u", "-F", "999", "--call-graph", "dwarf,8192", "-o", data, "--", sampled_executable], stdin=source, stdout=sink, stderr=log, timeout=45)
                if code:
                    raise RuntimeError(f"perf record failed; see {name}-perf.log")
                with (directory/f"{name}-stacks.txt").open("wb") as stacks, (directory/f"{name}-script.log").open("wb") as log:
                    code, _ = c.run(["perf", "script", "-i", data], stdout=stacks, stderr=log)
                if code:
                    raise RuntimeError("perf script failed")
                row["stacks"] = parse_stacks((directory/f"{name}-stacks.txt").read_text())
            # Syscall counts identify the I/O pattern without tracing millions of calls.
            source_path.write_bytes(packet*1000)
            trace = directory/f"{name}-strace.txt"
            with source_path.open("rb") as source, open(os.devnull,"wb") as sink:
                code, _ = c.run(["strace", "-c", "-o", trace, executable], stdin=source, stdout=sink, timeout=45)
            if code:
                raise RuntimeError(f"strace failed: {code}")
            row["trace_packets"] = 1000
            row["trace"] = trace.read_text()
            result["workloads"].append(row)
    c.save(directory/"profile.json", result)
    render(directory/"index.html", result)
    print(f"Profile report: {directory/'index.html'}", flush=True)
    return 0


def parse_stacks(text):
    """Aggregate sampled call stacks; preserve unresolved frames instead of guessing."""
    counts = {}
    for block in text.strip().split("\n\n"):
        frames = []
        for line in block.splitlines()[1:]:
            match = re.match(r"\s+[0-9a-f]+\s+(.+?)\s+\((.*)\)\s*$", line)
            if match:
                frames.append(re.sub(r"\+0x[0-9a-f]+$", "", match.group(1)))
        if frames:
            key = tuple(reversed(frames))
            counts[key] = counts.get(key,0)+1
    return [{"frames": list(k), "samples": v} for k,v in counts.items()]


def render(path, result):
    """Render a dependency-free interactive report that works directly from disk."""
    data = json.dumps(result).replace("<", "\\u003c")
    page = '''<!doctype html><html lang="en"><meta charset="utf-8">
<title>Titan · performance profile</title><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{margin:0;background:#101827;color:#e6edf7;font:17px system-ui,sans-serif}main{max-width:1400px;margin:auto;padding:44px}h1{font-size:42px;margin:8px 0}h2{margin-top:32px}.muted{color:#a8b9ce}button,select,input{background:#22334b;color:white;border:1px solid #48617d;border-radius:6px;padding:10px;margin:8px 8px 8px 0}button{cursor:pointer}.cards{display:flex;gap:16px;flex-wrap:wrap}.card{background:#1a273b;padding:22px;border-radius:12px;flex:1;min-width:180px}.value{font-size:32px;font-weight:700}.bar{height:42px;display:flex;border-radius:7px;overflow:hidden;margin:16px 0}.bar span{display:flex;align-items:center;justify-content:center;white-space:nowrap}pre{overflow:auto;background:#0b1120;padding:20px;font-size:14px}svg{width:100%;background:#0b1120;border-radius:10px}svg text{fill:#101827;font:12px monospace;pointer-events:none}.hint{padding:15px;background:#25354b;border-left:4px solid #78b8ef}a{color:#8fceff}#tip{min-height:28px;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:12px;border-bottom:1px solid #33435a}
</style><main><div class="muted">TITAN / SOLUTION 4 / MEASURED PROFILE</div><h1>Where does the time go?</h1><p class="muted">Release executable · regular-file input · output to /dev/null · no decoder changes</p>
<label>Workload <select id="workload"></select></label><div id="cards" class="cards"></div><p id="finding" class="hint"></p><h2>CPU time: userspace versus kernel</h2><div id="cpu" class="bar"></div><p class="muted">Median user and system CPU seconds from three untraced runs. These are CPU-time proportions, not a wall-time partition.</p>
<h2>Userspace call stacks</h2><div class="hint">Width means sample count, not elapsed time. Click a frame to zoom; hover for its name. Kernel work is excluded. Inlining and missing unwind information can hide frames.</div><button id="reset">Reset zoom</button><input id="search" placeholder="Highlight function…"><div id="tip"></div><svg id="flame"></svg><p id="sampling" class="muted"></p>
<h2>Userspace hotspots</h2><p class="muted">Leaf samples only: where the instruction pointer was observed. These percentages cover sampled userspace, not total CPU time. Kernel time is excluded.</p><table><thead><tr><th>Function</th><th>Samples</th><th>Share</th></tr></thead><tbody id="hotspots"></tbody></table><h2>System calls</h2><p class="muted">Separate strace run: 1,000 packets. Use the calls column to understand frequency. Traced time is distorted by instrumentation and must not be compared with the normal-run timings above.</p><pre id="trace"></pre><h2>Individual untraced runs</h2><table><thead><tr><th>Trial</th><th>Wall seconds</th><th>User CPU</th><th>Kernel CPU</th><th>Peak RSS KiB</th></tr></thead><tbody id="trials"></tbody></table>
<details><summary>Method and provenance</summary><pre id="meta"></pre></details><p><a href="profile.json">Raw profile JSON</a> · Keep this directory together to retain the raw logs and samples.</p></main><script>
const DATA=__DATA__;const $=id=>document.getElementById(id);const med=a=>a.slice().sort((a,b)=>a-b)[Math.floor(a.length/2)];let tree,focus;
DATA.workloads.forEach((r,i)=>{let o=document.createElement('option');o.value=i;o.textContent=r.name;$('workload').append(o)});
function node(name){return {name,count:0,children:new Map()}}
function makeTree(rows){let root=node('all userspace samples');for(let r of rows){let n=root;n.count+=r.samples;for(let f of r.frames){if(!n.children.has(f))n.children.set(f,node(f));n=n.children.get(f);n.count+=r.samples}}return root}
function depth(n){return 1+Math.max(0,...Array.from(n.children.values(),depth))}
function draw(){let svg=$('flame');svg.replaceChildren();if(!focus||!focus.count){svg.setAttribute('viewBox','0 0 1200 60');$('sampling').textContent='No userspace samples available. Read perf-access.log for access diagnostics.';return}let h=depth(focus)*26;svg.setAttribute('viewBox',`0 0 1200 ${h}`);let term=$('search').value.toLowerCase();function rect(n,x,y,w){let r=document.createElementNS('http://www.w3.org/2000/svg','rect');r.setAttribute('x',x);r.setAttribute('y',y);r.setAttribute('width',Math.max(0,w-1));r.setAttribute('height',24);r.setAttribute('fill',term&&n.name.toLowerCase().includes(term)?'#f4eb6d':`hsl(${24+y%65} 82% 65%)`);r.style.cursor='pointer';r.onmouseenter=()=>{$('tip').textContent=`${n.name} — ${n.count} samples (${(100*n.count/tree.count).toFixed(1)}% of total)`};r.onclick=()=>{focus=n;draw()};svg.append(r);if(w>65){let t=document.createElementNS(svg.namespaceURI,'text');t.setAttribute('x',x+4);t.setAttribute('y',y+17);t.textContent=n.name.split('(')[0].slice(0,Math.floor(w/7)-1);svg.append(t)}let p=x;for(let child of n.children.values()){let cw=w*child.count/n.count;rect(child,p,y+26,cw);p+=cw}}rect(focus,0,0,1200);$('sampling').textContent=`${tree.count} sampled stacks. Sampling frequency requested: 999 Hz.`}
function show(){let r=DATA.workloads[+$('workload').value],wall=med(r.trials.map(t=>t.wall)),user=med(r.trials.map(t=>t.user)),sys=med(r.trials.map(t=>t.system));$('cards').innerHTML=`<div class="card">Packets<div class="value">${r.packets.toLocaleString()}</div></div><div class="card">Median elapsed<div class="value">${wall.toFixed(2)} s</div></div><div class="card">Throughput<div class="value">${Math.round(r.packets/wall).toLocaleString()}/s</div></div><div class="card">Kernel share of CPU<div class="value">${(100*sys/(user+sys)).toFixed(1)}%</div></div>`;$('cpu').innerHTML=`<span style="width:${100*user/(user+sys)}%;background:#5ca9ec;color:#101827">User ${user.toFixed(2)} s</span><span style="flex:1;background:#eead6b;color:#101827">Kernel ${sys.toFixed(2)} s</span>`;$('trace').textContent=r.trace;$('trials').innerHTML=r.trials.map((t,i)=>`<tr><td>${i+1}</td><td>${t.wall}</td><td>${t.user}</td><td>${t.system}</td><td>${t.rss_kib}</td></tr>`).join('');tree=makeTree(r.stacks||[]);focus=tree;draw();let leaves=new Map();for(let s of r.stacks||[]){let f=s.frames.at(-1);leaves.set(f,(leaves.get(f)||0)+s.samples)}$('hotspots').replaceChildren();for(let [name,count] of [...leaves].sort((a,b)=>b[1]-a[1]).slice(0,12)){let tr=document.createElement('tr');for(let value of [name,count,(100*count/tree.count).toFixed(1)+'%']){let td=document.createElement('td');td.textContent=value;tr.append(td)}$('hotspots').append(tr)}let io=[...leaves].filter(([n])=>n==='__libc_write'||n==='__libc_read'||n.startsWith('outer::write_bytes(')||n.startsWith('outer::read_bytes(')).reduce((sum,[n,c])=>sum+c,0);$('finding').textContent=`${(100*sys/(user+sys)).toFixed(1)}% of normal-run CPU time is kernel work. ${tree.count?(100*io/tree.count).toFixed(1)+'% of observed userspace samples land in read/write wrappers.':'No userspace samples were collected.'} Combined with the syscall counts below, this points to frequent small I/O calls as the first optimization candidate. It does not measure the speedup buffering would deliver.`;$('meta').textContent=JSON.stringify({notes:DATA.notes,perf_available:DATA.perf_available,provenance:DATA.provenance},null,2)}
$('workload').onchange=show;$('search').oninput=draw;$('reset').onclick=()=>{focus=tree;draw()};show();
</script></html>'''
    path.write_text(page.replace("__DATA__", data))
