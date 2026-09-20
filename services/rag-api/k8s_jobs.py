"""Create and inspect ingestion Jobs from inside the cluster.

The RAG API pod runs with a ServiceAccount bound to a Role that can create/list
Jobs in its own namespace (see deploy/helm templates ragapi-rbac.yaml). On upload
we launch one Job running the ingest image against a sub-directory of the shared
uploads PVC. The UI polls list_jobs() for status.
"""
import time
import re

from kubernetes import client, config as kconfig

import config as appconfig

_BATCH = None


def _api():
    global _BATCH
    if _BATCH is None:
        # In-cluster: uses the pod's ServiceAccount token.
        kconfig.load_incluster_config()
        _BATCH = client.BatchV1Api()
    return _BATCH


def _safe(name: str) -> str:
    s = re.sub(r"[^a-z0-9-]", "-", name.lower()).strip("-")
    return s[:40] or "src"


def launch_ingest_job(subdir: str, label: str) -> str:
    """Launch a Job that ingests /uploads/<subdir>. Returns the Job name."""
    ts = time.strftime("%Y%m%d-%H%M%S")
    job_name = f"ingest-{_safe(label)}-{ts}"

    container = client.V1Container(
        name="ingest",
        image=appconfig.INGEST_IMAGE,
        args=[f"{appconfig.UPLOADS_DIR}/{subdir}"],
        env=[
            client.V1EnvVar("QDRANT_URL", appconfig.QDRANT_URL),
            client.V1EnvVar("COLLECTION_NAME", appconfig.COLLECTION_NAME),
            client.V1EnvVar("EMBED_URL", appconfig.EMBED_URL),
        ],
        volume_mounts=[client.V1VolumeMount(name="uploads", mount_path=appconfig.UPLOADS_DIR)],
    )
    node_selector = None
    if appconfig.INGEST_GPU_NODE_SELECTOR and "=" in appconfig.INGEST_GPU_NODE_SELECTOR:
        k, v = appconfig.INGEST_GPU_NODE_SELECTOR.split("=", 1)
        node_selector = {k: v}

    pod_spec = client.V1PodSpec(
        restart_policy="Never",
        service_account_name=appconfig.INGEST_SERVICE_ACCOUNT,
        node_selector=node_selector,
        containers=[container],
        volumes=[client.V1Volume(
            name="uploads",
            persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                claim_name=appconfig.INGEST_UPLOADS_PVC),
        )],
    )
    job = client.V1Job(
        metadata=client.V1ObjectMeta(
            name=job_name,
            labels={"app": "anubis-rag", "component": "ingest"},
        ),
        spec=client.V1JobSpec(
            backoff_limit=1,
            ttl_seconds_after_finished=3600,
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels={"app": "anubis-rag", "component": "ingest"}),
                spec=pod_spec,
            ),
        ),
    )
    _api().create_namespaced_job(namespace=appconfig.INGEST_NAMESPACE, body=job)
    return job_name


def list_jobs(limit: int = 20):
    jobs = _api().list_namespaced_job(
        namespace=appconfig.INGEST_NAMESPACE,
        label_selector="app=anubis-rag,component=ingest",
    ).items
    jobs.sort(key=lambda j: j.metadata.creation_timestamp or 0, reverse=True)
    out = []
    for j in jobs[:limit]:
        st = j.status
        if st and st.succeeded:
            status = "Succeeded"
        elif st and st.failed:
            status = "Failed"
        elif st and st.active:
            status = "Running"
        else:
            status = "Pending"
        created = j.metadata.creation_timestamp
        out.append({
            "name": j.metadata.name,
            "status": status,
            "created": created.isoformat() if created else None,
            "source": (j.metadata.name or "").replace("ingest-", "", 1),
        })
    return out
