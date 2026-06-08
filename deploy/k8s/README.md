# SmartCourse — Kubernetes deployment (production)

These manifests deploy the **stateless** SmartCourse workloads. They are the
production counterpart to `backend/docker-compose.yml` (which is for local dev
only). Same Docker image, different orchestrator.

## Architecture decision: stateful infra is *managed*, not in-cluster

We deliberately do **not** run Postgres, Kafka, Redis, RabbitMQ, MongoDB,
Temporal, or MinIO inside Kubernetes in production. Running stateful systems on
k8s is an operational burden (storage classes, backups, failover, upgrades)
that managed services solve far better:

| Component (dev container) | Production (managed)                         |
|---------------------------|----------------------------------------------|
| postgres (pgvector)       | AWS RDS / Aurora / Cloud SQL (pgvector on)   |
| kafka                     | MSK / Confluent Cloud / Redpanda Cloud       |
| redis                     | ElastiCache / Memorystore                    |
| rabbitmq                  | CloudAMQP / Amazon MQ                         |
| mongodb                   | MongoDB Atlas                                |
| temporal                  | Temporal Cloud                               |
| minio                     | Cloudflare R2 / AWS S3                        |
| prometheus/grafana/jaeger/loki | Grafana Cloud / Datadog / managed         |

So k8s runs only **our code** — the FastAPI API and the long-running workers —
and reaches the managed services via endpoints injected from the Secret +
ConfigMap. Each workload here corresponds 1:1 to a docker-compose service.

## What runs in-cluster

| Manifest | Replicas | docker-compose equivalent |
|---|---|---|
| `api-deployment.yaml` + `api-service.yaml` | 3 | `api` |
| `worker-deployment.yaml` | 2 | `worker` (Temporal) |
| `relay-deployment.yaml` | 2 | `relay` (outbox → Kafka) |
| `welcome-email-consumer-deployment.yaml` | 2 | `welcome-email-consumer` |
| `events-archiver-deployment.yaml` | 2 | `events-archiver` |
| `celery-worker-deployment.yaml` | 2 | `celery-worker` |
| `migrate-job.yaml` | (one-shot) | `migrate` |
| `ingress.yaml` | — | the `ports: 8000` exposure |

Workers scale horizontally safely:
- Kafka consumers partition work by consumer-group (welcome-email, events-archiver).
- The relay uses `FOR UPDATE SKIP LOCKED`, so N replicas never double-send.
- Temporal distributes activities across worker replicas.

## Config & secrets

Even though AWS *runs* the managed services, **we still store their endpoints +
credentials somewhere the pods can read.** Source-of-truth flow:

```
AWS Secrets Manager   ← values live here (AWS stores + rotates)
      │  External Secrets Operator syncs (~hourly)
      ▼
k8s Secret smartcourse-secrets   ← created in-cluster automatically
      │  envFrom: secretRef
      ▼
our pods                          ← read via env vars
```

- **`configmap.yaml`** — non-secret per-env values (managed-service *hostnames*,
  bucket name, flags). Safe to commit.
- **`secret.example.yaml`** — TEMPLATE only, shows the Secret's shape. Not used
  in real prod.
- **`external-secret.example.yaml`** — the REAL prod mechanism: an ESO
  `ExternalSecret` maps AWS Secrets Manager keys → the `smartcourse-secrets` k8s
  Secret. Credentials never touch git or a manifest; auth to AWS uses IRSA (no
  static keys). This is the concrete answer to "where do the managed-service
  connection strings live?" → Secrets Manager, synced in by ESO.

## Autoscaling

- **`hpa.yaml`** — HorizontalPodAutoscalers scale pod *count* on CPU (api 3→10,
  worker 2→6, …). Needs metrics-server in the cluster.
- Two layers: **HPA adds pods**; when nodes fill, the **cluster autoscaler**
  (EKS-managed) adds EC2 nodes. You never pin a service to an instance — pods
  bin-pack onto the shared node group.

## Deploy

```bash
# 1. image: build + push to your registry, then set it once
#    (replace REGISTRY/smart-course-app:TAG everywhere, or use kustomize image edits)
docker build -t REGISTRY/smart-course-app:TAG backend/
docker push REGISTRY/smart-course-app:TAG

# 2. namespace + config + secret (secret comes from your secrets manager in real life)
kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml
kubectl apply -f secret.example.yaml      # replace with the real, managed Secret

# 3. run migrations (Job runs to completion before the app rolls out)
kubectl apply -f migrate-job.yaml
kubectl wait --for=condition=complete job/smartcourse-migrate -n smartcourse --timeout=300s

# 4. workloads
kubectl apply -f api-deployment.yaml -f api-service.yaml
kubectl apply -f worker-deployment.yaml
kubectl apply -f relay-deployment.yaml
kubectl apply -f welcome-email-consumer-deployment.yaml
kubectl apply -f events-archiver-deployment.yaml
kubectl apply -f celery-worker-deployment.yaml
kubectl apply -f ingress.yaml
```

(Or `kubectl apply -f .` once the Secret is real and migrations are gated in CI.)

## Notes vs dev

- No `--reload` / `watchfiles` / bind mounts — code is baked into the image.
- API runs under gunicorn + uvicorn workers (see `api-deployment.yaml` command).
- Probes use `/health`; metrics scraped at `/metrics` by a ServiceMonitor (if
  using the Prometheus Operator) — not included here.
- This is intentionally **not** a Helm chart — plain manifests are clearer for
  review. Helm/Kustomize is the natural next step for multi-env (staging/prod)
  value overrides.
