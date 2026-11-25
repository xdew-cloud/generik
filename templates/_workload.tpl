{{- /*
  One Deployment. Called with root (the chart context) and d, one resolved entry of generik.deployments.
*/ -}}
{{- define "generik.deployment" -}}
{{- $root := .root -}}
{{- $d := .d -}}
{{- $strategy := $d.strategy | default dict -}}
{{- $type := $strategy.type | default "RollingUpdate" -}}
{{- $rolling := dict -}}
{{- range $key := list "maxUnavailable" "maxSurge" -}}
{{- if hasKey $strategy $key -}}
{{- $_ := set $rolling $key (get $strategy $key) -}}
{{- end -}}
{{- end -}}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ $d.object }}
  namespace: {{ $root.Release.Namespace }}
  labels:
    {{- include "generik.labelsOf" (dict "root" $root "version" $d.image.tag) | nindent 4 }}
    {{- with $d.component }}
    app.kubernetes.io/component: {{ . }}
    {{- end }}
spec:
  replicas: {{ $d.replicas | int }}
  strategy:
    type: {{ $type }}
    {{- if and (eq $type "RollingUpdate") $rolling }}
    rollingUpdate:
      {{- toYaml $rolling | nindent 6 }}
    {{- end }}
  selector:
    matchLabels:
      app.kubernetes.io/name: {{ include "generik.name" $root }}
      {{- if $d.selectByComponent }}
      app.kubernetes.io/component: {{ $d.component }}
      {{- end }}
  template:
    metadata:
      labels:
        {{- include "generik.labelsOf" (dict "root" $root "version" $d.image.tag) | nindent 8 }}
        {{- with $d.component }}
        app.kubernetes.io/component: {{ . }}
        {{- end }}
    spec:
      {{- if $d.serviceAccount }}
      serviceAccountName: {{ include "generik.name" $root }}
      {{- end }}
      {{- with $d.podSecurityContext }}
      securityContext:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with $d.imagePullSecret }}
      imagePullSecrets:
        - name: {{ . }}
      {{- end }}
      {{- with $d.volumes }}
      volumes:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      containers:
        - name: {{ $d.container }}
          image: "{{ $d.image.repository }}:{{ $d.image.tag }}"
          imagePullPolicy: {{ $d.image.pullPolicy }}
          {{- with $d.command }}
          command:
            {{- toYaml . | nindent 12 }}
          {{- end }}
          {{- with $d.args }}
          args:
            {{- toYaml . | nindent 12 }}
          {{- end }}
          ports:
            - name: {{ $d.portName }}
              containerPort: {{ $d.port | int }}
          {{- with $d.env }}
          env:
            {{- toYaml . | nindent 12 }}
          {{- end }}
          {{- if $d.secrets }}
          envFrom:
            - secretRef:
                name: {{ include "generik.name" $root }}-secrets
          {{- end }}
          resources:
            requests:
              cpu: {{ $d.resources.requests.cpu }}
              memory: {{ $d.resources.requests.memory }}
            limits:
              memory: {{ $d.resources.limits.memory }}
          readinessProbe:
            tcpSocket:
              port: {{ $d.portName }}
            {{- toYaml $d.probes.readiness | nindent 12 }}
          livenessProbe:
            tcpSocket:
              port: {{ $d.portName }}
            {{- toYaml $d.probes.liveness | nindent 12 }}
          {{- with $d.volumeMounts }}
          volumeMounts:
            {{- toYaml . | nindent 12 }}
          {{- end }}
{{- end }}

{{- /* The Service of a Deployment. Called with root and d. */ -}}
{{- define "generik.service" -}}
{{- $d := .d -}}
apiVersion: v1
kind: Service
metadata:
  name: {{ $d.object }}
  namespace: {{ .root.Release.Namespace }}
  labels:
    {{- include "generik.labelsOf" (dict "root" .root "version" $d.image.tag) | nindent 4 }}
    {{- with $d.component }}
    app.kubernetes.io/component: {{ . }}
    {{- end }}
spec:
  selector:
    app.kubernetes.io/name: {{ include "generik.name" .root }}
    {{- with $d.component }}
    app.kubernetes.io/component: {{ . }}
    {{- end }}
  ports:
    - name: {{ $d.portName }}
      protocol: TCP
      port: {{ $d.service.port | int }}
      targetPort: {{ $d.portName }}
{{- end }}
