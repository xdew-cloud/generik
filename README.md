# generik

Generic Helm chart for the web apps of the XDEW platform. One chart replaces the near-identical charts `account`, `console`, `explore`, `login`, `static`, `status` and `www`: an app is a block of values in its `App`.

It renders a Deployment, a Service (port 80), an Ingress with a TLS certificate, a Cloudflare DNS record per host, and optionally a ServiceAccount with a ClusterRole and an Ory Hydra `OAuth2Client`. Published as `oci://ghcr.io/xdew-cloud/generik`.

## Use

```yaml
# apps/core/console.yaml (xdew-cloud/manifests)
spec:
  chart:
    url: ghcr.io/xdew-cloud
    name: generik
    version: 0.2.0               # version of generik, pinned per app
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
| `imagePullSecret` | `pull-secret` | Existing dockerconfigjson Secret; empty for a public image |
| `replicas`, `port` | `1`, `3000` | The container port is named `http` |
| `service.port` | `80` | The port of the Service, which targets `http` |
| `strategy` | `{}` | `type` (`RollingUpdate`, the default, or `Recreate`), and `maxUnavailable` and `maxSurge` of the rolling update |
| `command`, `args` | `[]` | What the container runs instead of its image's entrypoint |
| `podSecurityContext`, `volumes`, `volumeMounts` | empty | Kubernetes syntax. The claim a volume uses is a file next to the App |
| `probes.readiness`, `probes.liveness` | 10 s / 15 s delay, 5 s timeout | TCP probes on `http`. Every key is passed as is; `null` removes a default |
| `resources` | 25m / 128Mi, limit 256Mi | |
| `env` | `[]` | Kubernetes syntax (`name` + `value`, or `valueFrom`, see Settings from another Secret) |
| `secrets` | `false` | `true`: the container reads the Secret `<name>-secrets` (`envFrom`) |
| `serviceAccount.create` | `false` | |
| `rbac.clusterRules` | `[]` | Rules of a ClusterRole bound to the ServiceAccount |
| `ingress.host` | required | |
| `ingress.extraHosts` | `[]` | A string joins the Ingress of the app (a TLS host, a rule, a DNS record). An object `{host, name, middleware}` gets its own Ingress, certificate and Traefik Middleware: see Several hosts |
| `ingress.extraPaths` | `[]` | `[{path, service, port}]` of the main host, routed to another Service before `/` |
| `ingress.className`, `ingress.clusterIssuer` | `traefik`, `xdew-cloudflare` | |
| `dns.enabled`, `dns.target`, `dns.proxied` | `true`, `origin.xdew.cloud`, `true` | |
| `oauth2.enabled` | `false` | Creates the `OAuth2Client`; `CLIENT_ID` and `CLIENT_SECRET` are added to `env` from `<name>-client-secrets` |
| `oauth2.clientName`, `audience`, `scope`, `redirectPaths` | | Redirect URIs are `https://<ingress.host><path>`; an empty `scope` or `redirectPaths` leaves it out |
| `oauth2.grantTypes`, `responseTypes` | `[authorization_code, refresh_token]`, `[code]` | A web login. A service that calls other services: `grantTypes: [client_credentials]`, `responseTypes: []`, `redirectPaths: []` |
| `oauth2.tokenEndpointAuthMethod` | `client_secret_basic` | Or `client_secret_post`, `private_key_jwt`, `none` |
| `oauth2.clientIdEnv`, `clientSecretEnv` | `CLIENT_ID`, `CLIENT_SECRET` | The variables of the container that carry them |
| `components` | `{}` | More Deployments of the app, see Components |

`values.schema.json` rejects unknown keys, an empty image tag and a missing host.

## Several hosts

An extra host that is a string shares the Ingress, the certificate and the middleware-less routing of the app. One that is an object with a `middleware` gets its own Ingress, its own certificate (`<name>-<slug>-tls`) and its own Traefik Middleware named `<name>-<slug>`, where `slug` is its `name` or its host with the dots as hyphens. `middleware` is the `spec` of the Middleware as is, so any rewrite works:

```yaml
ingress:
  host: api.xdew.cloud
  extraHosts:
    - www.api.xdew.cloud                                            # the Ingress of the app
    - host: webhook.xdew.cloud                                      # /x becomes /webhook/x
      name: webhook
      middleware: {addPrefix: {prefix: /webhook}}
    - host: old.xdew.cloud                                          # /v1/x becomes /x
      middleware: {replacePathRegex: {regex: "^/v1/(.*)", replacement: "/$1"}}
```

Every host has a DNS record. The paths of `ingress.extraPaths` apply to the main host only.

## Settings from another Secret

`secrets: true` hands the whole Secret `<name>-secrets` to the container. A setting that lives in a Secret of its own, under a key that is not the variable's name, is an `env` entry with `valueFrom`. `optional: true` lets the pod start without the key, so the app works with or without it. The same goes for the rights an app needs on its own resources (`rbac.clusterRules`, a status is its own resource, `versions/status`):

```yaml
env:
  - name: GITHUB_APP_ID
    valueFrom:
      secretKeyRef: {name: xdew-cloud-github-app, key: appId, optional: true}
rbac:
  clusterRules:
    - {apiGroups: [xdew.cloud], resources: [versions], verbs: [get, list, create, delete]}
    - {apiGroups: [xdew.cloud], resources: [versions/status], verbs: [get, patch]}
```

The `api` of the platform does exactly this for its GitHub App (the Secret is a file next to the App); `tests/cases/secretenv.values.yaml` renders it.

## Components

An app made of more than one Deployment (a web server, a collaboration server, a Redis) puts the others in `components`. Each is named `<name>-<component>`, has its own Service and is selected by `app.kubernetes.io/name` and `app.kubernetes.io/component`. Everything is optional: the image is the app's, the port is 3000 on a Service on 80, the resources are the chart's, and `env`, `args`, `volumes` are the component's own. `secrets: true` reads the app's `<name>-secrets`. The main Deployment is the app itself: with components, its pods and its Service also carry `app.kubernetes.io/component: web` so that its Service does not select theirs, and its own selector stays the name alone. A Deployment's selector cannot be changed afterwards, so an app that moves here from another chart keeps its selectors: check them in the parity test.

```yaml
# docs (Outline): the app is the web server; collaboration is the same image with another role; Redis is another image
strategy: {type: Recreate}
ingress:
  host: docs.xdew.cloud
  extraPaths: [{path: /collaboration, service: docs-collaboration, port: 80}]
components:
  collaboration:
    env: [{name: SERVICES, value: collaboration}, {name: REDIS_URL, value: "redis://docs-redis:6379"}]
    secrets: true
  redis:
    image: {repository: redis, tag: 7-alpine, pullPolicy: IfNotPresent}
    imagePullSecret: ""
    port: 6379
    portName: redis
    service: {port: 6379}
    args: [--save, "60", "1"]
    strategy: {type: Recreate}
    volumes: [{name: data, persistentVolumeClaim: {claimName: docs-redis}}]
    volumeMounts: [{name: data, mountPath: /data}]
```

The complete values of `docs` and `api` are in [tests/apps](tests/apps).

## What is not in the chart

- **The `SopsSecret`.** It carries its own `sops:` block, with a MAC computed on the whole file, so it does not fit inside values. It is a plain file next to the `App` in `manifests` (`deploy/<group>/<name>/secrets.sops.yaml`).
- **Objects specific to one app** (a PersistentVolumeClaim, Traefik IngressRoutes and Middlewares that are not a host rewrite, database clusters, policies): plain YAML in the same directory. There is no `extraObjects`: it would bypass the Steward's admission rules.

## Parity with the old charts

`tests/parity.py` renders each old chart and generik with the same intent and compares the objects one by one (labels and namespaces ignored). Every accepted difference is listed in the script with its reason.

```
python3 -I tests/parity.py <directory holding the old charts>
```

It covers the nine apps of `tests/apps`, among them `api` (client credentials, a host that adds a prefix) and `docs` (components, `Recreate`, a volume). `tests/cases.py` checks what no old chart shows (a rewrite by regular expression, a host named after its dots, a component with no Service, a rolling update that stops at zero); the files it renders are in `tests/cases`. Both need Python with PyYAML and Helm; neither runs in CI, which lints and renders every file of `tests/apps` and `tests/cases`.

## Release

The version is the single line of `.version`. Pushing a `[version]` commit to `main` runs lint, packages the chart with `helm package --version <.version>`, pushes it to `ghcr.io/<owner>/generik` and creates the GitHub release. `Chart.yaml` keeps `version: 0.0.0`.
