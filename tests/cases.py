#!/usr/bin/env python3
"""Render the cases of tests/cases and check what the old charts do not show: several hosts with their own middleware,
several Deployments (names, selectors, claims), the strategy, settings read from another Secret, and what the chart
refuses.

usage: cases.py
"""
import copy, os, subprocess, sys, tempfile, yaml

HERE = os.path.dirname(os.path.abspath(__file__))
CHART = os.path.dirname(HERE)
failed = []


def helm(case_file, namespace="ns"):
    return subprocess.run(["helm", "template", "x", CHART, "-n", namespace, "-f", case_file], capture_output=True, text=True)


def render(case, namespace="ns"):
    out = helm(f"{HERE}/cases/{case}.values.yaml", namespace)
    if out.returncode:
        sys.exit(out.stderr)
    return {(d["kind"], d["metadata"]["name"]): d for d in yaml.safe_load_all(out.stdout) if d}


def refused(label, change, message):
    """Render the `deployments` case with `change` applied to its values: helm must fail and say `message`."""
    values = yaml.safe_load(open(f"{HERE}/cases/deployments.values.yaml"))
    values = change(copy.deepcopy(values))
    with tempfile.NamedTemporaryFile("w", suffix=".yaml") as f:
        yaml.safe_dump(values, f)
        f.flush()
        out = helm(f.name)
    check(f"refused: {label}", out.returncode != 0 and message in out.stderr)
    if out.returncode == 0 or message not in out.stderr:
        print("          stderr:", out.stderr.strip()[:300])


def check(label, ok):
    print(("ok      " if ok else "FAILED  ") + label)
    if not ok:
        failed.append(label)


hosts = render("hosts")
check("the main Ingress holds the main host and the plain extra host, not the ones with a middleware",
      hosts[("Ingress", "shop")]["spec"]["tls"][0]["hosts"] == ["shop.example.org", "www.shop.example.org"]
      and [r["host"] for r in hosts[("Ingress", "shop")]["spec"]["rules"]] == ["shop.example.org", "www.shop.example.org"])
check("a host with a name gets <app>-<name>: a Middleware, an Ingress, a certificate",
      hosts[("Middleware", "shop-api")]["spec"] == {"stripPrefix": {"prefixes": ["/api"]}}
      and hosts[("Ingress", "shop-api")]["spec"]["tls"][0]["secretName"] == "shop-api-tls"
      and hosts[("Ingress", "shop-api")]["metadata"]["annotations"]["traefik.ingress.kubernetes.io/router.middlewares"] == "ns-shop-api@kubernetescrd")
check("a host with no name is named after its dots as hyphens",
      hosts[("Middleware", "shop-old-shop-example-org")]["spec"]["replacePathRegex"] == {"regex": "^/v1/(.*)", "replacement": "/$1"}
      and ("Ingress", "shop-old-shop-example-org") in hosts)
check("every host has a DNS record",
      sorted(n for k, n in hosts if k == "DNSRecord") == ["api-shop-example-org", "old-shop-example-org", "shop-example-org", "www-shop-example-org"])
check("each own Ingress routes / to the Service of the app",
      all(hosts[("Ingress", n)]["spec"]["rules"][0]["http"]["paths"][0]["backend"]["service"] == {"name": "shop", "port": {"name": "http"}}
          for n in ("shop-api", "shop-old-shop-example-org")))
check("an app of one entry has no component and is selected by its name alone",
      hosts[("Deployment", "shop")]["spec"]["selector"]["matchLabels"] == {"app.kubernetes.io/name": "shop"}
      and "app.kubernetes.io/component" not in hosts[("Deployment", "shop")]["spec"]["template"]["metadata"]["labels"]
      and hosts[("Service", "shop")]["spec"]["selector"] == {"app.kubernetes.io/name": "shop"}
      and not [k for k in hosts if k[0] == "PersistentVolumeClaim"])

c = render("deployments")
app, worker, queue = c[("Deployment", "jobs")], c[("Deployment", "jobs-worker")], c[("Deployment", "jobs-queue")]
check("the entry with no name is the app: its pods and its Service also carry component web, its selector is the name alone",
      app["spec"]["selector"]["matchLabels"] == {"app.kubernetes.io/name": "jobs"}
      and app["spec"]["template"]["metadata"]["labels"]["app.kubernetes.io/component"] == "web"
      and c[("Service", "jobs")]["spec"]["selector"] == {"app.kubernetes.io/name": "jobs", "app.kubernetes.io/component": "web"}
      and app["spec"]["template"]["spec"]["containers"][0]["name"] == "jobs")
check("an entry with a name is called <app>-<name> and selected by name and component",
      worker["spec"]["selector"]["matchLabels"] == {"app.kubernetes.io/name": "jobs", "app.kubernetes.io/component": "worker"}
      and c[("Service", "jobs-worker")]["spec"]["selector"] == worker["spec"]["selector"]["matchLabels"]
      and worker["spec"]["template"]["spec"]["containers"][0]["name"] == "worker")
wc = worker["spec"]["template"]["spec"]["containers"][0]
check("an entry inherits the image and the pull secret of the first, and has its own defaults",
      wc["image"] == "ghcr.io/example/jobs:2.0.0" and wc["ports"] == [{"name": "http", "containerPort": 3000}]
      and worker["spec"]["template"]["spec"]["imagePullSecrets"] == [{"name": "pull-secret"}]
      and wc["resources"] == {"requests": {"cpu": "25m", "memory": "128Mi"}, "limits": {"memory": "256Mi"}}
      and wc["readinessProbe"] == {"tcpSocket": {"port": "http"}, "initialDelaySeconds": 10, "timeoutSeconds": 5}
      and wc["env"] == [{"name": "MODE", "value": "worker"}] and worker["spec"]["replicas"] == 1
      and c[("Service", "jobs-worker")]["spec"]["ports"] == [{"name": "http", "protocol": "TCP", "port": 80, "targetPort": "http"}])
check("an entry can name its own image, port and Service",
      queue["spec"]["template"]["spec"]["containers"][0]["image"] == "redis:7-alpine"
      and queue["spec"]["template"]["spec"]["containers"][0]["readinessProbe"]["tcpSocket"]["port"] == "redis"
      and queue["metadata"]["labels"]["app.kubernetes.io/version"] == "7-alpine"
      and c[("Service", "jobs-queue")]["spec"]["ports"][0] == {"name": "redis", "protocol": "TCP", "port": 6379, "targetPort": "redis"})
check("an entry can have no Service and no replica",
      ("Service", "jobs-internal") not in c and c[("Deployment", "jobs-internal")]["spec"]["replicas"] == 0)
check("Recreate carries no rollingUpdate, a rolling update keeps a zero",
      app["spec"]["strategy"] == {"type": "Recreate"}
      and queue["spec"]["strategy"] == {"type": "RollingUpdate", "rollingUpdate": {"maxSurge": 0, "maxUnavailable": 0}})
check("the Service of the first entry listens on its service.port, and the Ingress routes to it",
      c[("Service", "jobs")]["spec"]["ports"][0]["port"] == 8080
      and c[("Ingress", "jobs")]["spec"]["rules"][0]["http"]["paths"][-1]["backend"]["service"] == {"name": "jobs", "port": {"name": "http"}})

n = render("named")
web, cache = n[("Deployment", "docs-web")], n[("Deployment", "docs-cache")]
check("every entry named: docs-web, docs-collaboration, docs-cache, each selected by its component",
      sorted(k[1] for k in n if k[0] == "Deployment") == ["docs-cache", "docs-collaboration", "docs-web"]
      and web["spec"]["selector"]["matchLabels"] == {"app.kubernetes.io/name": "docs", "app.kubernetes.io/component": "web"}
      and n[("Service", "docs-web")]["spec"]["selector"] == web["spec"]["selector"]["matchLabels"]
      and ("Service", "docs") not in n)
paths = n[("Ingress", "docs")]["spec"]["rules"][0]["http"]["paths"]
check("a path names an entry (docs-collaboration) or any other Service as written, and / goes to the first entry",
      [(p["path"], p["backend"]["service"]["name"]) for p in paths]
      == [("/collaboration", "docs-collaboration"), ("/self-service", "kratos-public"), ("/", "docs-web")])
claim = n[("PersistentVolumeClaim", "docs-web-uploads")]
check("a claim with no name is called <object>-<volume>, takes the default class and ReadWriteOnce",
      claim["spec"] == {"accessModes": ["ReadWriteOnce"], "resources": {"requests": {"storage": "5Gi"}}})
fast = n[("PersistentVolumeClaim", "docs-cache")]
check("a claim can name itself and choose its class, size and access modes",
      fast["spec"] == {"accessModes": ["ReadWriteMany"], "storageClassName": "fast", "resources": {"requests": {"storage": "1Gi"}}})
check("a claim is never pruned by ArgoCD nor deleted with the Application, and Helm keeps it",
      all(x["metadata"]["annotations"] == {"argocd.argoproj.io/sync-options": "Prune=false,Delete=false", "helm.sh/resource-policy": "keep"}
          for x in (claim, fast)))
cspec = cache["spec"]["template"]["spec"]
check("the pod mounts the claim, with its subPath, and a volume that is not a claim stays as written",
      web["spec"]["template"]["spec"]["volumes"] == [{"name": "uploads", "persistentVolumeClaim": {"claimName": "docs-web-uploads"}}]
      and web["spec"]["template"]["spec"]["containers"][0]["volumeMounts"] == [{"name": "uploads", "mountPath": "/data"}]
      and cspec["volumes"] == [{"name": "data", "persistentVolumeClaim": {"claimName": "docs-cache"}}, {"name": "tmp", "emptyDir": {}}]
      and cspec["containers"][0]["volumeMounts"] == [{"name": "data", "mountPath": "/cache", "subPath": "docs"}, {"name": "tmp", "mountPath": "/tmp"}]
      and "imagePullSecrets" not in cspec)

b = render("secretenv")
env = b[("Deployment", "bridge")]["spec"]["template"]["spec"]["containers"][0]["env"]
check("env passes a key of another Secret, optional, and keeps the order",
      [e["name"] for e in env] == ["MODE", "APP_ID", "APP_KEY", "RESYNC_SECONDS"]
      and env[1]["valueFrom"] == {"secretKeyRef": {"name": "bridge-app", "key": "appId", "optional": True}}
      and env[3] == {"name": "RESYNC_SECONDS", "value": "3600"})
check("the rules of the ClusterRole reach a resource and its status, in the order given",
      [(r["resources"], r["verbs"]) for r in b[("ClusterRole", "bridge")]["rules"]]
      == [(["versions"], ["get", "list", "create", "delete"]), (["versions/status"], ["get", "patch"])]
      and b[("ClusterRoleBinding", "bridge")]["subjects"][0]["name"] == "bridge"
      and b[("Deployment", "bridge")]["spec"]["template"]["spec"]["serviceAccountName"] == "bridge")


def two_unnamed(v):
    v["deployments"].append({"image": {"repository": "x", "tag": "1"}})
    return v


def same_name(v):
    v["deployments"].append({"name": "worker"})
    return v


def web_taken(v):
    v["deployments"].append({"name": "web"})
    return v


def claim_and_source(v):
    v["deployments"][0]["volumes"] = [{"name": "d", "emptyDir": {}, "claim": {"size": "1Gi"}}]
    return v


def same_claim(v):
    claim = {"name": "shared", "size": "1Gi"}
    v["deployments"][0]["volumes"] = [{"name": "a", "claim": claim}, {"name": "b", "claim": claim}]
    return v


def no_deployment(v):
    v["deployments"] = []
    return v


def no_image(v):
    del v["deployments"][0]["image"]
    return v


def flat(v):
    v["image"] = v["deployments"][0]["image"]
    return v


def other_without_tag(v):
    v["deployments"][1]["image"] = {"repository": "redis"}
    return v


def claim_without_size(v):
    v["deployments"][0]["volumes"] = [{"name": "a", "claim": {}}]
    return v


refused("two entries with no name", two_unnamed, "at most one entry has no name")
refused("the same name twice", same_name, "also called")
refused("a name that is the component of the unnamed entry", web_taken, "give it another name")
refused("a claim next to another volume source", claim_and_source, "a claim is the whole source")
refused("two volumes for one claim", same_claim, "two volumes ask for the claim")
refused("an app with no Deployment", no_deployment, "deployments")
refused("a first entry with no image", no_image, "image")
refused("the flat shape of generik 0.1 (image at the top)", flat, "image")
refused("an entry's own image with no tag", other_without_tag, "tag")
refused("a claim with no size", claim_without_size, "size")

sys.exit(1 if failed else 0)
