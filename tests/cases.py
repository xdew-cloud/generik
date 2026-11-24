#!/usr/bin/env python3
"""Render the cases of tests/cases and check what the old charts do not show: several hosts with their own middleware,
components, and the strategy.

usage: cases.py
"""
import os, subprocess, sys, yaml

HERE = os.path.dirname(os.path.abspath(__file__))
CHART = os.path.dirname(HERE)
failed = []


def render(case, namespace="ns"):
    out = subprocess.run(["helm", "template", case, CHART, "-n", namespace, "-f", f"{HERE}/cases/{case}.values.yaml"],
                         capture_output=True, text=True)
    if out.returncode:
        sys.exit(out.stderr)
    return {(d["kind"], d["metadata"]["name"]): d for d in yaml.safe_load_all(out.stdout) if d}


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

c = render("components")
app, worker, queue = c[("Deployment", "jobs")], c[("Deployment", "jobs-worker")], c[("Deployment", "jobs-queue")]
check("the app selects its pods by name alone, its pods and its Service also carry component web",
      app["spec"]["selector"]["matchLabels"] == {"app.kubernetes.io/name": "jobs"}
      and app["spec"]["template"]["metadata"]["labels"]["app.kubernetes.io/component"] == "web"
      and c[("Service", "jobs")]["spec"]["selector"] == {"app.kubernetes.io/name": "jobs", "app.kubernetes.io/component": "web"})
check("a component is named <app>-<component> and selected by name and component",
      worker["spec"]["selector"]["matchLabels"] == {"app.kubernetes.io/name": "jobs", "app.kubernetes.io/component": "worker"}
      and c[("Service", "jobs-worker")]["spec"]["selector"] == worker["spec"]["selector"]["matchLabels"])
wc = worker["spec"]["template"]["spec"]["containers"][0]
check("a component inherits the image and the pull secret, and has its own defaults",
      wc["name"] == "worker" and wc["image"] == "ghcr.io/example/jobs:2.0.0" and wc["ports"] == [{"name": "http", "containerPort": 3000}]
      and worker["spec"]["template"]["spec"]["imagePullSecrets"] == [{"name": "pull-secret"}]
      and wc["resources"] == {"requests": {"cpu": "25m", "memory": "128Mi"}, "limits": {"memory": "256Mi"}}
      and wc["readinessProbe"] == {"tcpSocket": {"port": "http"}, "initialDelaySeconds": 10, "timeoutSeconds": 5}
      and wc["env"] == [{"name": "MODE", "value": "worker"}] and worker["spec"]["replicas"] == 1
      and c[("Service", "jobs-worker")]["spec"]["ports"] == [{"name": "http", "protocol": "TCP", "port": 80, "targetPort": "http"}])
check("a component can name its own image, port and Service",
      queue["spec"]["template"]["spec"]["containers"][0]["image"] == "redis:7-alpine"
      and queue["spec"]["template"]["spec"]["containers"][0]["readinessProbe"]["tcpSocket"]["port"] == "redis"
      and c[("Service", "jobs-queue")]["spec"]["ports"][0] == {"name": "redis", "protocol": "TCP", "port": 6379, "targetPort": "redis"})
check("a component can have no Service and no replica",
      ("Service", "jobs-internal") not in c and c[("Deployment", "jobs-internal")]["spec"]["replicas"] == 0)
check("Recreate carries no rollingUpdate, a rolling update keeps a zero",
      app["spec"]["strategy"] == {"type": "Recreate"}
      and queue["spec"]["strategy"] == {"type": "RollingUpdate", "rollingUpdate": {"maxSurge": 0, "maxUnavailable": 0}})
check("the Service of the app listens on service.port",
      c[("Service", "jobs")]["spec"]["ports"][0]["port"] == 8080)

sys.exit(1 if failed else 0)
