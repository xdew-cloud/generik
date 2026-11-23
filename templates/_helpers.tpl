{{- define "generik.name" -}}
{{- default .Release.Name .Values.name -}}
{{- end }}

{{- define "generik.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "generik.labels" -}}
helm.sh/chart: {{ include "generik.chart" . }}
app.kubernetes.io/name: {{ include "generik.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Values.image.tag | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}
