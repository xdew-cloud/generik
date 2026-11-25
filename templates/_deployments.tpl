{{- /*
  The Deployments of the app, resolved, as a JSON list (one object per Deployment).

  `deployments` is a list. The first entry is the app: the Ingress, the OAuth2 client and the ServiceAccount are its,
  and the other entries take its image unless they name their own. An entry with no `name` is called <app>, one named x
  is called <app>-x (so a one-entry app is `api`, not `api-api`). At most one entry has no name, the names are unique.

  What every object holds: name (as written, or ""), object (the name of the Deployment and of its Service), container,
  component (app.kubernetes.io/component, "" for an app alone), selectByComponent (the selector holds the component:
  true for a named entry; the unnamed one is selected by the name of the app alone, as it always was), serviceAccount,
  secrets, env, image {repository, tag, pullPolicy}, imagePullSecret, replicas, port, portName, service {enabled, port},
  strategy, probes {readiness, liveness}, resources, podSecurityContext, command, args, volumes and volumeMounts (in
  Kubernetes syntax) and claims [{name, size, storageClass, accessModes, volume}], the PersistentVolumeClaims the
  chart renders for the entry.
*/ -}}
{{- define "generik.deployments" -}}
{{- $app := include "generik.name" . -}}
{{- $list := .Values.deployments | default list -}}
{{- if not $list -}}
{{- fail "deployments: at least one entry is needed, the first is the app itself" -}}
{{- end -}}
{{- $first := index $list 0 -}}
{{- $multi := gt (len $list) 1 -}}
{{- $out := list -}}
{{- $objects := dict -}}
{{- $components := dict -}}
{{- $claimNames := dict -}}
{{- range $i, $d := $list -}}
{{- $name := dig "name" "" $d -}}
{{- $object := $app -}}
{{- if $name -}}
{{- $object = printf "%s-%s" $app $name -}}
{{- end -}}
{{- if hasKey $objects $object -}}
{{- fail (printf "deployments: the entry %d is also called %q: at most one entry has no name, and the names are unique" $i $object) -}}
{{- end -}}
{{- $_ := set $objects $object true -}}
{{- /* With several entries the unnamed one is "web", so that its Service does not select the pods of the others. */ -}}
{{- $component := $name -}}
{{- if and (not $name) $multi -}}
{{- $component = "web" -}}
{{- end -}}
{{- if $component -}}
{{- if hasKey $components $component -}}
{{- fail (printf "deployments: an entry is called %q, which is the component of the entry that has no name when there are several: give it another name" $component) -}}
{{- end -}}
{{- $_ := set $components $component true -}}
{{- end -}}

{{- /* An entry that has an image takes it whole; the others take the app's. */ -}}
{{- $image := $first.image -}}
{{- if hasKey $d "image" -}}
{{- $image = get $d "image" -}}
{{- end -}}
{{- $image = dict "repository" $image.repository "tag" $image.tag "pullPolicy" (dig "pullPolicy" "Always" $image) -}}
{{- $pullSecret := "pull-secret" -}}
{{- if hasKey $first "imagePullSecret" -}}
{{- $pullSecret = get $first "imagePullSecret" -}}
{{- end -}}
{{- if hasKey $d "imagePullSecret" -}}
{{- $pullSecret = get $d "imagePullSecret" -}}
{{- end -}}

{{- /* The client of the app is the first entry's. */ -}}
{{- $env := dig "env" list $d -}}
{{- if and (eq $i 0) $.Values.oauth2.enabled -}}
{{- $secret := printf "%s-client-secrets" $app -}}
{{- $env = concat $env (list (dict "name" $.Values.oauth2.clientIdEnv "valueFrom" (dict "secretKeyRef" (dict "name" $secret "key" "CLIENT_ID"))) (dict "name" $.Values.oauth2.clientSecretEnv "valueFrom" (dict "secretKeyRef" (dict "name" $secret "key" "CLIENT_SECRET")))) -}}
{{- end -}}

{{- /* A key set to null removes the default of a probe. */ -}}
{{- $probes := dict -}}
{{- range $kind, $defaults := (dict "readiness" (dict "initialDelaySeconds" 10 "timeoutSeconds" 5) "liveness" (dict "initialDelaySeconds" 15 "timeoutSeconds" 5)) -}}
{{- $p := deepCopy $defaults -}}
{{- range $k, $v := (dig "probes" $kind dict $d) -}}
{{- if kindIs "invalid" $v -}}
{{- $_ := unset $p $k -}}
{{- else -}}
{{- $_ := set $p $k $v -}}
{{- end -}}
{{- end -}}
{{- $_ := set $probes $kind $p -}}
{{- end -}}

{{- /* A volume is a Kubernetes volume with, besides, mountPath (and subPath, readOnly) for its mount and claim for a
       PersistentVolumeClaim that this chart renders and keeps. */ -}}
{{- $volumes := list -}}
{{- $mounts := list -}}
{{- $claims := list -}}
{{- range $v := (dig "volumes" list $d) -}}
{{- $source := omit $v "mountPath" "subPath" "readOnly" "claim" -}}
{{- if hasKey $v "claim" -}}
{{- if gt (len $source) 1 -}}
{{- fail (printf "deployments: the volume %q has a claim and another source: a claim is the whole source" $v.name) -}}
{{- end -}}
{{- $claim := get $v "claim" -}}
{{- $claimName := dig "name" (printf "%s-%s" $object $v.name) $claim -}}
{{- if hasKey $claimNames $claimName -}}
{{- fail (printf "deployments: two volumes ask for the claim %q" $claimName) -}}
{{- end -}}
{{- $_ := set $claimNames $claimName true -}}
{{- $source = dict "name" $v.name "persistentVolumeClaim" (dict "claimName" $claimName) -}}
{{- $claims = append $claims (dict "name" $claimName "volume" $v.name "size" $claim.size "storageClass" (dig "storageClass" "" $claim) "accessModes" (dig "accessModes" (list "ReadWriteOnce") $claim)) -}}
{{- end -}}
{{- $volumes = append $volumes $source -}}
{{- if hasKey $v "mountPath" -}}
{{- $mount := dict "name" $v.name "mountPath" $v.mountPath -}}
{{- if hasKey $v "subPath" -}}
{{- $_ := set $mount "subPath" (get $v "subPath") -}}
{{- end -}}
{{- if hasKey $v "readOnly" -}}
{{- $_ := set $mount "readOnly" (get $v "readOnly") -}}
{{- end -}}
{{- $mounts = append $mounts $mount -}}
{{- end -}}
{{- end -}}

{{- $out = append $out (dict
    "name" $name
    "object" $object
    "container" ($name | default $app)
    "component" $component
    "selectByComponent" (ne $name "")
    "serviceAccount" (and (eq $i 0) $.Values.serviceAccount.create)
    "secrets" (dig "secrets" false $d)
    "env" $env
    "image" $image
    "imagePullSecret" $pullSecret
    "replicas" (dig "replicas" 1 $d)
    "port" (dig "port" 3000 $d)
    "portName" (dig "portName" "http" $d)
    "service" (dict "enabled" (dig "service" "enabled" true $d) "port" (dig "service" "port" 80 $d))
    "strategy" (dig "strategy" dict $d)
    "probes" $probes
    "resources" (dict "requests" (dict "cpu" (dig "resources" "requests" "cpu" "25m" $d) "memory" (dig "resources" "requests" "memory" "128Mi" $d)) "limits" (dict "memory" (dig "resources" "limits" "memory" "256Mi" $d)))
    "podSecurityContext" (dig "podSecurityContext" dict $d)
    "command" (dig "command" list $d)
    "args" (dig "args" list $d)
    "volumes" $volumes
    "volumeMounts" $mounts
    "claims" $claims) -}}
{{- end -}}
{{- toJson $out -}}
{{- end }}

