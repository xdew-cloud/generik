{{- /*
  One Deployment, for the app and for each of its components. Called with a dict:
    root               the chart context
    name               name of the Deployment
    container          name of the container
    component          app.kubernetes.io/component of the pods, or "" (the app alone has none)
    selectByComponent  true when the selector holds the component too (a component), false for the app
    serviceAccount     true when the pods run as the ServiceAccount of the release
    secrets            true when the container reads <release>-secrets
    env                the environment, a list in Kubernetes syntax
    w                  the workload: image, replicas, port, portName, strategy, probes, resources,
                       imagePullSecret, podSecurityContext, volumes, volumeMounts, command, args
*/ -}}
{{- define "generik.deployment" -}}
{{- $root := .root -}}
{{- $w := .w -}}
{{- $strategy := $w.strategy | default dict -}}
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
  name: {{ .name }}
  namespace: {{ $root.Release.Namespace }}
  labels:
    {{- include "generik.labelsOf" (dict "root" $root "version" $w.image.tag) | nindent 4 }}
    {{- with .component }}
    app.kubernetes.io/component: {{ . }}
    {{- end }}
spec:
  replicas: {{ $w.replicas }}
  strategy:
    type: {{ $type }}
    {{- if and (eq $type "RollingUpdate") $rolling }}
    rollingUpdate:
      {{- toYaml $rolling | nindent 6 }}
    {{- end }}
  selector:
    matchLabels:
      app.kubernetes.io/name: {{ include "generik.name" $root }}
      {{- if .selectByComponent }}
      app.kubernetes.io/component: {{ .component }}
      {{- end }}
  template:
    metadata:
      labels:
        {{- include "generik.labelsOf" (dict "root" $root "version" $w.image.tag) | nindent 8 }}
        {{- with .component }}
        app.kubernetes.io/component: {{ . }}
        {{- end }}
    spec:
      {{- if .serviceAccount }}
      serviceAccountName: {{ include "generik.name" $root }}
      {{- end }}
      {{- with $w.podSecurityContext }}
      securityContext:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with $w.imagePullSecret }}
      imagePullSecrets:
        - name: {{ . }}
      {{- end }}
      {{- with $w.volumes }}
      volumes:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      containers:
        - name: {{ .container }}
          image: "{{ $w.image.repository }}:{{ $w.image.tag }}"
          imagePullPolicy: {{ $w.image.pullPolicy }}
          {{- with $w.command }}
          command:
            {{- toYaml . | nindent 12 }}
          {{- end }}
          {{- with $w.args }}
          args:
            {{- toYaml . | nindent 12 }}
          {{- end }}
          ports:
            - name: {{ $w.portName }}
              containerPort: {{ $w.port }}
          {{- with .env }}
          env:
            {{- toYaml . | nindent 12 }}
          {{- end }}
          {{- if .secrets }}
          envFrom:
            - secretRef:
                name: {{ include "generik.name" $root }}-secrets
          {{- end }}
          resources:
            requests:
              cpu: {{ $w.resources.requests.cpu }}
              memory: {{ $w.resources.requests.memory }}
            limits:
              memory: {{ $w.resources.limits.memory }}
          readinessProbe:
            tcpSocket:
              port: {{ $w.portName }}
            {{- include "generik.probe" $w.probes.readiness | nindent 12 }}
          livenessProbe:
            tcpSocket:
              port: {{ $w.portName }}
            {{- include "generik.probe" $w.probes.liveness | nindent 12 }}
          {{- with $w.volumeMounts }}
          volumeMounts:
            {{- toYaml . | nindent 12 }}
          {{- end }}
{{- end }}

{{- /* A Service. Called with root, name, component, version, portName and port. */ -}}
{{- define "generik.service" -}}
apiVersion: v1
kind: Service
metadata:
  name: {{ .name }}
  namespace: {{ .root.Release.Namespace }}
  labels:
    {{- include "generik.labelsOf" (dict "root" .root "version" .version) | nindent 4 }}
    {{- with .component }}
    app.kubernetes.io/component: {{ . }}
    {{- end }}
spec:
  selector:
    app.kubernetes.io/name: {{ include "generik.name" .root }}
    {{- with .component }}
    app.kubernetes.io/component: {{ . }}
    {{- end }}
  ports:
    - name: {{ .portName }}
      protocol: TCP
      port: {{ .port }}
      targetPort: {{ .portName }}
{{- end }}
