{{- define "anubis-rag.labels" -}}
app.kubernetes.io/part-of: anubis-rag
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "img.ragApi" -}}{{ .Values.registry }}/{{ .Values.images.ragApi.repo }}:{{ .Values.images.ragApi.tag }}{{- end -}}
{{- define "img.embedder" -}}{{ .Values.registry }}/{{ .Values.images.embedder.repo }}:{{ .Values.images.embedder.tag }}{{- end -}}
{{- define "img.ingest" -}}{{ .Values.registry }}/{{ .Values.images.ingest.repo }}:{{ .Values.images.ingest.tag }}{{- end -}}
{{- define "img.ui" -}}{{ .Values.registry }}/{{ .Values.images.ui.repo }}:{{ .Values.images.ui.tag }}{{- end -}}
{{- define "img.qdrant" -}}{{ .Values.images.qdrant.repo }}:{{ .Values.images.qdrant.tag }}{{- end -}}

{{- define "gpu.nodeSelector" -}}
{{- with .Values.gpu.nodeSelector }}
nodeSelector:
{{ toYaml . | indent 2 }}
{{- end }}
{{- end -}}
