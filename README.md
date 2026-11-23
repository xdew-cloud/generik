# generik

Generic Helm chart for the web apps of the XDEW platform. One chart replaces the near-identical charts `account`, `console`, `explore`, `login`, `static`, `status` and `www`: an app is a block of values in its `App`.

It renders a Deployment, a Service (port 80), an Ingress with a TLS certificate, a Cloudflare DNS record per host, and optionally a ServiceAccount with a ClusterRole and an Ory Hydra `OAuth2Client`. Published as `oci://ghcr.io/xdew-cloud/generik`.

## Use

```yaml
# apps/core/console.yaml (xdew-cloud/manifests)
spec:
  type: chart
  chart:
    repoUrl: ghcr.io/xdew-cloud
    chart: generik
    version: 0.1.0               # version of generik, pinned per app
    releaseName: console
    values:
      name: console
      image: {repository: ghcr.io/xdew-cloud/console, tag: 4.4.3}   # the line a version bump edits
      ingress: {host: console.xdew.cloud}
      secrets: true
      serviceAccount: {create: true}
      rbac:
        clusterRules:
          - {apiGroups: [""], resources: [pods], verbs: [get, list, watch]}
      env:
        - {name: API_URL, value: "http://api:3000"}
      oauth2: {enabled: true, clientName: Console, audience: api}
```

The complete values of the seven apps are in [tests/apps](tests/apps).

## Values

| Key | Default | Meaning |
|---|---|---|
| `name` | release name | Name of every object |
| `image.repository`, `image.tag` | required | The tag is explicit; there is no appVersion fallback |
| `image.pullPolicy` | `Always` | |
| `imagePullSecret` | `pull-secret` | Existing dockerconfigjson Secret |
| `replicas`, `port` | `1`, `3000` | The container port is named `http`; the Service exposes it on 80 |
| `strategy` | `{}` | `maxUnavailable` and `maxSurge` of the rolling update |
| `probes.readiness`, `probes.liveness` | 10 s / 15 s delay, 5 s timeout | TCP probes on `http`. Every key is passed as is; `null` removes a default |
| `resources` | 25m / 128Mi, limit 256Mi | |
| `env` | `[]` | Kubernetes syntax (`name` + `value`, or `valueFrom`) |
| `secrets` | `false` | `true`: the container reads the Secret `<name>-secrets` (`envFrom`) |
| `serviceAccount.create` | `false` | |
| `rbac.clusterRules` | `[]` | Rules of a ClusterRole bound to the ServiceAccount |
| `ingress.host` | required | |
| `ingress.extraHosts` | `[]` | Each one gets a TLS host, a rule and a DNS record |
| `ingress.extraPaths` | `[]` | `[{path, service, port}]` of the main host, routed to another Service before `/` |
| `ingress.className`, `ingress.clusterIssuer` | `traefik`, `xdew-cloudflare` | |
| `dns.enabled`, `dns.target`, `dns.proxied` | `true`, `origin.xdew.cloud`, `true` | |
| `oauth2.enabled` | `false` | Creates the `OAuth2Client`; `CLIENT_ID` and `CLIENT_SECRET` are added to `env` from `<name>-client-secrets` |
| `oauth2.clientName`, `audience`, `scope`, `redirectPaths` | | Redirect URIs are `https://<ingress.host><path>` |

`values.schema.json` rejects unknown keys, an empty image tag and a missing host.

## What is not in the chart

- **The `SopsSecret`.** It carries its own `sops:` block, with a MAC computed on the whole file, so it does not fit inside values. It is a plain file next to the `App` in `manifests` (`deploy/<group>/<name>/secrets.sops.yaml`).
- **Objects specific to one app** (Redis, extra routes, database clusters, policies): plain YAML in the same directory. There is no `extraObjects`: it would bypass the Steward's admission rules.

## Parity with the old charts

`tests/parity.py` renders each old chart and generik with the same intent and compares the objects one by one (labels and namespaces ignored). Every accepted difference is listed in the script with its reason.

```
python3 -I tests/parity.py <directory holding the old charts>
```

## Release

The version is the single line of `.version`. Pushing a `[version]` commit to `main` runs lint, packages the chart with `helm package --version <.version>`, pushes it to `ghcr.io/<owner>/generik` and creates the GitHub release. `Chart.yaml` keeps `version: 0.0.0`.
