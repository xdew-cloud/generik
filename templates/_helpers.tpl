{{- define "generik.name" -}}
{{- default .Release.Name .Values.name -}}
{{- end }}

{{- define "generik.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- /* The labels of an object that is not a workload: the version is the tag of the app's image (the first entry). */ -}}
{{- define "generik.labels" -}}
{{- $first := index .Values.deployments 0 -}}
{{- include "generik.labelsOf" (dict "root" . "version" $first.image.tag) -}}
{{- end }}

{{- /* The labels of an object, with the version of the image it runs (each Deployment has its own). Called with root and version. */ -}}
{{- define "generik.labelsOf" -}}
helm.sh/chart: {{ include "generik.chart" .root }}
app.kubernetes.io/name: {{ include "generik.name" .root }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/version: {{ .version | quote }}
app.kubernetes.io/managed-by: {{ .root.Release.Service }}
{{- end }}

{{- /* Every host of the app, as a JSON list: the main one, then the extra ones (a string, or an object with a host). */ -}}
{{- define "generik.hosts" -}}
{{- $hosts := list .Values.ingress.host -}}
{{- range .Values.ingress.extraHosts -}}
{{- if kindIs "string" . -}}
{{- $hosts = append $hosts . -}}
{{- else -}}
{{- $hosts = append $hosts .host -}}
{{- end -}}
{{- end -}}
{{- toJson $hosts -}}
{{- end }}

{{- /* The hosts of the main Ingress: the extra hosts that have no middleware of their own. */ -}}
{{- define "generik.sharedHosts" -}}
{{- $hosts := list .Values.ingress.host -}}
{{- range .Values.ingress.extraHosts -}}
{{- if kindIs "string" . -}}
{{- $hosts = append $hosts . -}}
{{- else if not .middleware -}}
{{- $hosts = append $hosts .host -}}
{{- end -}}
{{- end -}}
{{- toJson $hosts -}}
{{- end }}
