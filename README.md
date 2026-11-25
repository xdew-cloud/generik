# generik

Generic Helm chart for the web apps of the XDEW platform. One chart replaces the near-identical charts `account`, `console`, `explore`, `login`, `static`, `status`, `www`, `api` and `docs`: an app is a block of values in its `App`.

For each entry of `deployments` it renders a Deployment and a Service; for the app, an Ingress with a TLS certificate, a Cloudflare DNS record per host, and optionally a ServiceAccount with a ClusterRole and an Ory Hydra `OAuth2Client`; for each volume with a `claim`, a PersistentVolumeClaim that nothing prunes. Published as `oci://ghcr.io/xdew-cloud/generik`.

## Use

A simple app is a list of one:

```yaml
# apps/core/console.yaml (xdew-cloud/manifests)
spec:
  chart:
    url: ghcr.io/xdew-cloud
    name: generik
    version: 0.2.0               # version of generik, pinned per app
    values:
      name: console
      ingress: {host: console.xdew.cloud}
      serviceAccount: {create: true}
      rbac:
        clusterRules:
          - {apiGroups: [""], resources: [pods], verbs: [get, list, watch]}
      oauth2: {enabled: true, clientName: Console, audience: api}
      deployments:
        - image: {repository: ghcr.io/xdew-cloud/console, tag: 4.4.3}   # the line a version bump edits
          secrets: true
          env:
            - {name: API_URL, value: "http://api:3000"}
```

The complete values of the nine apps are in [tests/apps](tests/apps).

**From 0.1.0.** Version 0.1.0 had the keys of an entry (`image`, `env`, `resources`...) at the top of the values and a `components` map for the other Deployments. 0.2.0 puts them all in `deployments`; the schema refuses the old shape with the name of the key. An App pinned to 0.1.0 keeps working with the old shape until its version is raised; raising it is changing its values (the rendered objects are the same, the pods restart because their `helm.sh/chart` label changes).

## Values of the app

| Key | Default | Meaning |
|---|---|---|
| `name` | release name | Name of the app and of the objects that are not a Deployment |
| `deployments` | required | The Deployments, see Deployments. The first is the app |
| `serviceAccount.create` | `false` | The ServiceAccount of the first entry |
| `rbac.clusterRules` | `[]` | Rules of a ClusterRole bound to the ServiceAccount |
| `ingress.host` | required | |
| `ingress.extraHosts` | `[]` | A string joins the Ingress of the app (a TLS host, a rule, a DNS record). An object `{host, name, middleware}` gets its own Ingress, certificate and Traefik Middleware: see Several hosts |
| `ingress.extraPaths` | `[]` | `[{path, service, port}]` of the main host, routed to another Service before `/`. `service` is the `name` of an entry of `deployments`, or any other Service as written |
| `ingress.className`, `ingress.clusterIssuer` | `traefik`, `xdew-cloudflare` | |
| `dns.enabled`, `dns.target`, `dns.proxied` | `true`, `origin.xdew.cloud`, `true` | |
| `oauth2.enabled` | `false` | Creates the `OAuth2Client`; its id and secret are added to the `env` of the first entry from `<name>-client-secrets` |
| `oauth2.clientName`, `audience`, `scope`, `redirectPaths` | | Redirect URIs are `https://<ingress.host><path>`; an empty `scope` or `redirectPaths` leaves it out |
| `oauth2.grantTypes`, `responseTypes` | `[authorization_code, refresh_token]`, `[code]` | A web login. A service that calls other services: `grantTypes: [client_credentials]`, `responseTypes: []`, `redirectPaths: []` |
| `oauth2.tokenEndpointAuthMethod` | `client_secret_basic` | Or `client_secret_post`, `private_key_jwt`, `none` |
| `oauth2.clientIdEnv`, `clientSecretEnv` | `CLIENT_ID`, `CLIENT_SECRET` | The variables of the container that carry them |

`values.schema.json` rejects unknown keys (the flat shape of generik 0.1, with `image` at the top, among them), a first entry with no image, an image with no tag and a missing host.

## Deployments

`deployments` is a list; each entry is a Deployment and its Service. **The first entry is the app**: the Ingress routes `/` to it, the OAuth2 client and the ServiceAccount are its, and the other entries take its image unless they name their own.

**Names.** An entry with no `name` is called `<name>`; one named `x` is called `<name>-x`. So an app of one entry is `api`, not `api-api`, and Outline is `docs`, `docs-collaboration` and `docs-redis`. The name does not depend on how many entries there are: adding one never renames another. At most one entry has no name, and the names are unique (the chart fails otherwise).

| Key of an entry | Default | Meaning |
|---|---|---|
| `name` | none | See above |
| `image.repository`, `image.tag`, `image.pullPolicy` | required on the first; `pullPolicy` `Always` | The tag is explicit; there is no appVersion fallback. An entry that has an `image` takes it whole, the others take the first's |
| `imagePullSecret` | `pull-secret` | Existing dockerconfigjson Secret; empty for a public image; the others take the first's |
| `replicas`, `port`, `portName` | `1`, `3000`, `http` | The port of the container and its name |
| `service.enabled`, `service.port` | `true`, `80` | The Service of the entry, which targets `portName` |
| `strategy` | `{}` | `type` (`RollingUpdate`, the default, or `Recreate`), and `maxUnavailable` and `maxSurge` of the rolling update |
| `command`, `args` | `[]` | What the container runs instead of its image's entrypoint |
| `podSecurityContext` | `{}` | `fsGroup`... |
| `probes.readiness`, `probes.liveness` | 10 s / 15 s delay, 5 s timeout | TCP probes on `portName`. Every key is passed as is; `null` removes a default |
| `resources` | 25m / 128Mi, limit 256Mi | |
| `env` | `[]` | Kubernetes syntax (`name` + `value`, or `valueFrom`, see Settings from another Secret) |
| `secrets` | `false` | `true`: the container reads the Secret `<app>-secrets` (`envFrom`) |
| `volumes` | `[]` | See Volumes |

The pods and the Service of the app also carry `app.kubernetes.io/component: web` when there are several entries, so that its Service does not select the pods of the others; its Deployment keeps the name of the app as its only selector. An entry with a name is selected by the name of the app and its own name. A Deployment's selector cannot be changed afterwards, so an app that moves here from another chart keeps its selectors: check them in the parity test.

```yaml
# docs (Outline): the app is the web server; collaboration is the same image with another role; Redis is another image
ingress:
  host: docs.xdew.cloud
  extraPaths: [{path: /collaboration, service: collaboration, port: 80}]   # docs-collaboration
deployments:
  - image: {repository: outlinewiki/outline, tag: 1.10.1}                 # docs
    strategy: {type: Recreate}
    secrets: true
    volumes:
      - {name: uploads, mountPath: /var/lib/outline/data, claim: {name: docs-uploads, size: 10Gi, storageClass: xdew-storage}}
  - name: collaboration                                                   # docs-collaboration
    env: [{name: SERVICES, value: collaboration}, {name: REDIS_URL, value: "redis://docs-redis:6379"}]
    secrets: true
  - name: redis                                                           # docs-redis
    image: {repository: redis, tag: 7-alpine, pullPolicy: IfNotPresent}
    imagePullSecret: ""
    port: 6379
    portName: redis
    service: {port: 6379}
    args: [--save, "60", "1"]
    strategy: {type: Recreate}
    volumes:
      - {name: data, mountPath: /data, claim: {name: docs-redis, size: 1Gi, storageClass: xdew-storage}}
```

## Volumes

A volume of an entry is a Kubernetes volume, with `mountPath` (and `subPath`, `readOnly`) for its mount. With a `claim` it is a PersistentVolumeClaim that this chart renders:

| Key of a `claim` | Default | |
|---|---|---|
| `size` | required | |
| `name` | `<Deployment>-<volume>` | **Never change it**: a new name is a new, empty claim, and the pod mounts it without complaint while the data stays in the old one. Write it, as the examples do |
| `storageClass` | the cluster's default | A claim's class cannot be changed afterwards |
| `accessModes` | `[ReadWriteOnce]` | |

A claim holds data and the storage class deletes a volume with its claim. So the chart gives every claim `argocd.argoproj.io/sync-options: Prune=false,Delete=false` and `helm.sh/resource-policy: keep`: ArgoCD never prunes it and keeps it when the Application is deleted. Taking a volume out of the values leaves its claim, and its data, where it is; deleting it is a decision made by hand. The size can be raised in the values, never lowered. A claim next to another volume source (`emptyDir`...) is refused.

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
deployments:
  - image: {repository: ghcr.io/xdew-cloud/api, tag: 3.5.0}
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

## What is not in the chart

- **The `SopsSecret`.** It carries its own `sops:` block, with a MAC computed on the whole file, so it does not fit inside values. It is a plain file next to the `App` in `manifests` (`deploy/<group>/<name>/secrets.sops.yaml`).
- **Objects specific to one app** (Traefik IngressRoutes and Middlewares that are not a host rewrite, database clusters, policies): plain YAML in the same directory. There is no `extraObjects`: it would bypass the Steward's admission rules.

## Parity with the old charts

`tests/parity.py` renders each old chart and generik with the same intent and compares the objects one by one (labels and namespaces ignored). Every accepted difference is listed in the script with its reason.

```
python3 -I tests/parity.py <directory holding the old charts>
```

It covers the nine apps of `tests/apps`, among them `api` (client credentials, a host that adds a prefix) and `docs` (three Deployments, `Recreate`, two claims: they are the same as the old chart's but for the annotations that protect them). `tests/cases.py` checks what no old chart shows (a rewrite by regular expression, a host named after its dots, every entry named, claims, an entry with no Service, a rolling update that stops at zero) and what the chart refuses; the files it renders are in `tests/cases`. Both need Python with PyYAML and Helm; neither runs in CI, which lints and renders every file of `tests/apps` and `tests/cases`.

## Release

The version is the single line of `.version`. Pushing a `[version]` commit to `main` runs lint, packages the chart with `helm package --version <.version>`, pushes it to `ghcr.io/<owner>/generik` and creates the GitHub release. `Chart.yaml` keeps `version: 0.0.0`.
