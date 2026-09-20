# Deploying Anubis RAG to k3s

## Prerequisites

- **k3s** reachable; `kubectl` + `helm` context set.
- **GPU node** with the NVIDIA device plugin + container runtime. Label it and set that label
  in `values.yaml → gpu.nodeSelector` (e.g. `{ nvidia.com/gpu.present: "true" }`). The
  embedder and ingestion Jobs schedule there.
- **Storage class(es)**: k3s ships `local-path` (RWO). Qdrant uses RWO (single pod). The
  uploads PVC is shared by the API and ingestion Jobs — prefer an **RWX** class (NFS/Longhorn)
  and set `storage.uploads.accessMode: ReadWriteMany`. With RWO, keep `ragApi.replicas: 1`
  (the chart pins the API to the GPU node so it co-mounts with the Jobs).
- **Traefik** ingress (k3s default) and a hostname pointing at the cluster.
- **External answer-LLM** reachable from cluster nodes: the llama.cpp OpenAI endpoint on
  `192.168.70.14`/`.15:8080`. Set `externalLLM.host`.
- **Image registry**: GHCR (private) — create a pull secret and list it in
  `imagePullSecrets`, or push to the cluster's own registry.

## 1. Build & push images

```bash
REG=ghcr.io/hussamkhalid
for s in rag-api embedder ingest ui; do
  docker build -t $REG/anubis-rag-$s:latest services/$s
  docker push  $REG/anubis-rag-$s:latest
done
```

(Or push to `main` and let `.github/workflows/build.yml` build them to GHCR.)

## 2. Configure secrets

Create a local override (never commit it):

```yaml
# my-values.yaml
gpu:
  nodeSelector: { nvidia.com/gpu.present: "true" }
externalLLM:
  host: 192.168.70.14
ingress:
  host: rag.anubis.local
storage:
  uploads: { className: nfs, accessMode: ReadWriteMany }   # if you have RWX
secrets:
  anubisApiToken: "$(openssl rand -hex 24)"
  jwtSecret: "$(openssl rand -hex 32)"
  uiUserPassword: "pick-one"
  uiAdminPassword: "pick-another"
imagePullSecrets: [{ name: ghcr }]
```

## 3. Install

```bash
kubectl create secret docker-registry ghcr \
  --docker-server=ghcr.io --docker-username=hussamkhalid \
  --docker-password=<GHCR_PAT> -n anubis-rag --dry-run=client -o yaml | kubectl apply -f -

helm upgrade --install anubis-rag deploy/helm/anubis-rag \
  -n anubis-rag --create-namespace -f my-values.yaml
```

## Verify (end-to-end)

```bash
kubectl -n anubis-rag get pods -o wide          # all Ready; embedder on the GPU node
kubectl -n anubis-rag exec deploy/embedder -- \
  wget -qO- localhost:8080/health               # model bge-base, dim 768
kubectl -n anubis-rag get pvc                    # qdrant + uploads Bound
```

1. Open `https://<ingress.host>` → sign in as `admin`.
2. **Ask** tab → drop a PDF → an ingestion Job starts.
3. **Admin** tab → the Job shows `Succeeded`; Qdrant vector count rises; all three
   dependencies (embedder / Qdrant / external LLM) show green; dimension match = consistent.
4. **Ask** a question → grounded answer + cited chunks (confirms retrieval + external LLM).
5. `kubectl delete pod` the rag-api / qdrant pod → it self-heals, data persists.

## Migrating the existing .17 vectors (optional)

The existing collection is mostly test data, so a fresh ingest is recommended. To carry it
over instead, snapshot on `.17` and restore into the cluster Qdrant:

```bash
# on .17
curl -X POST localhost:6333/collections/anubis_rag_chunks/snapshots
# copy the snapshot into the qdrant PVC, then POST the recover API in-cluster.
```

## Notes

- Retrieval knobs (`TOP_K`, `CONTEXT_TOP_K`, `MIN_SCORE`) live in `ragApi.env`; change and
  `helm upgrade` to apply. The Admin tab reads them live from `/status`.
- The answer-LLM stays external by design; only the embedder needs cluster GPU.
