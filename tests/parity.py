#!/usr/bin/env python3
"""Render each old chart and generik with the same intent and compare the objects one by one.

usage: parity.py <directory holding the old charts> [app ...]

Labels and namespaces are ignored (the old charts and generik name their helper labels differently).
Every other difference is printed. A difference is only accepted if it is listed in EXPECTED below,
with the reason: nothing is hidden silently.
"""
import copy, json, os, subprocess, sys, yaml

HERE = os.path.dirname(os.path.abspath(__file__))
CHART = os.path.dirname(HERE)
NAMESPACE = {"login": "system-identity-apps"}  # every other app lives in system-apps-core

# (app, kind, name) -> {"path": reason}; the empty path key "" accepts the whole object missing on one side.
EXPECTED = {
    ("account", "SopsSecret", "account-secrets"): {"": "only in the old chart: the SopsSecret moves to a file next to the App"},
    ("explore", "SopsSecret", "explore-secrets"): {"": "only in the old chart: the SopsSecret moves to a file next to the App"},
    ("console", "SopsSecret", "console-secrets"): {"": "only in the old chart: the SopsSecret moves to a file next to the App"},
    ("api", "IngressRoute", "api-block-registrations"): {"": "only in the old chart: Traefik objects that move to a file next to the App"},
    ("api", "Middleware", "api-block-registrations"): {"": "only in the old chart: Traefik objects that move to a file next to the App"},
    ("docs", "SopsSecret", "docs-secrets"): {"": "only in the old chart: the SopsSecret moves to a file next to the App"},
    ("docs", "PersistentVolumeClaim", "docs-uploads"): {".metadata.annotations": "generik protects a claim: ArgoCD never prunes nor deletes it, Helm keeps it"},
    ("docs", "PersistentVolumeClaim", "docs-redis"): {".metadata.annotations": "generik protects a claim: ArgoCD never prunes nor deletes it, Helm keeps it"},
    ("docs", "Ingress", "docs"): {
        ".spec.rules[0].http.paths[0].backend.service.port.number": "the old chart addresses the collaboration Service by port name http, generik by number 80: the same port",
        ".spec.rules[0].http.paths[0].backend.service.port.name": "see port.number"},
    ("login", "Ingress", "login"): {
        ".spec.rules[0].http.paths[4].backend.service.port.number": "the old chart addresses its own Service by port number 80, generik by the port name http: the same port",
        ".spec.rules[0].http.paths[4].backend.service.port.name": "see port.number"},
}

def render(args):
    out = subprocess.run(["helm", "template"] + args, capture_output=True, text=True)
    if out.returncode:
        sys.exit(out.stderr)
    return {(d["kind"], d["metadata"]["name"]): d for d in yaml.safe_load_all(out.stdout) if d}

def strip(o):
    o = copy.deepcopy(o)
    o["metadata"].pop("labels", None); o["metadata"].pop("namespace", None)
    o.get("spec", {}).get("template", {}).get("metadata", {}).pop("labels", None)
    return o

def diff(a, b, path=""):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a: yield path + "." + k, "only in generik", None, b[k]
            elif k not in b: yield path + "." + k, "only in old chart", a[k], None
            else: yield from diff(a[k], b[k], path + "." + k)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b): yield path, f"list of {len(a)} (old) vs {len(b)} (generik)", a, b
        for i, (x, y) in enumerate(zip(a, b)): yield from diff(x, y, f"{path}[{i}]")
    elif a != b:
        yield path, "different value", a, b

def main():
    old_dir = sys.argv[1]
    apps = sys.argv[2:] or sorted(f.split(".")[0] for f in os.listdir(f"{HERE}/apps"))
    bad = 0
    for app in apps:
        ns = NAMESPACE.get(app, "system-apps-core")
        old = render([app, f"{old_dir}/{app}", "-n", ns])
        new = render([app, CHART, "-n", ns, "-f", f"{HERE}/apps/{app}.values.yaml"])
        report = []
        for key in sorted(set(old) | set(new)):
            exp = EXPECTED.get((app, key[0], key[1]), {})
            if key not in new or key not in old:
                if "" not in exp:
                    report.append(f"  {key[0]}/{key[1]}: only in {'old chart' if key in old else 'generik'}")
                continue
            for path, why, x, y in diff(strip(old[key]), strip(new[key])):
                if path in exp: continue
                report.append(f"  {key[0]}/{key[1]}{path}: {why}  old={json.dumps(x)[:70]} new={json.dumps(y)[:70]}")
        print(f"{app:8} {len(old):2} objects (old) / {len(new):2} (generik): " + ("identical apart from the expected differences" if not report else f"{len(report)} difference(s)"))
        for line in report: print(line)
        bad += len(report)
    sys.exit(1 if bad else 0)

main()
