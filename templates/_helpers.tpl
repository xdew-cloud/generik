{{- define "generik.name" -}}
{{- default .Release.Name .Values.name -}}
{{- end }}

{{- define "generik.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "generik.labels" -}}
{{- include "generik.labelsOf" (dict "root" . "version" .Values.image.tag) -}}
{{- end }}

{{- /* The labels of an object, with the version of the image it runs (a component has its own). Called with root and version. */ -}}
{{- define "generik.labelsOf" -}}
helm.sh/chart: {{ include "generik.chart" .root }}
app.kubernetes.io/name: {{ include "generik.name" .root }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/version: {{ .version | quote }}
app.kubernetes.io/managed-by: {{ .root.Release.Service }}
{{- end }}

{{- /* A probe's keys without the ones set to null (null removes a default, also for a component). */ -}}
{{- define "generik.probe" -}}
{{- $clean := dict -}}
{{- range $key, $value := . -}}
{{- if not (kindIs "invalid" $value) -}}
{{- $_ := set $clean $key $value -}}
{{- end -}}
{{- end -}}
{{- toYaml $clean -}}
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
