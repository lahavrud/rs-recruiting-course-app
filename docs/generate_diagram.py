from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import ECR
from diagrams.aws.database import RDS
from diagrams.aws.integration import SQS, Eventbridge
from diagrams.aws.management import SystemsManagerParameterStore
from diagrams.aws.network import CloudFront, Route53
from diagrams.aws.storage import S3
from diagrams.k8s.compute import Deploy
from diagrams.onprem.ci import GithubActions
from diagrams.onprem.client import Users
from diagrams.onprem.gitops import ArgoCD
from diagrams.onprem.monitoring import Grafana

graph_attr = {
    "fontsize": "14",
    "bgcolor": "white",
    "pad": "2.0",
    "splines": "curved",
    "nodesep": "1.0",
    "ranksep": "2.2",
    "overlap": "false",
}

node_attr = {
    "fontsize": "12",
    "margin": "0.4,0.3",
}

with Diagram(
    "RS Recruiting — EKS Architecture",
    filename="docs/screenshots/aws-architecture",
    outformat="png",
    show=False,
    graph_attr=graph_attr,
    node_attr=node_attr,
    direction="LR",
):
    # ── Left: ingress ──────────────────────────────────────────
    users = Users("Users")
    dns = Route53("Route 53")

    with Cluster("AWS  eu-central-1"):
        # CDN layer
        cf = CloudFront("CloudFront\nSPA + /api origin")

        # Serving layer
        s3_fe = S3("S3 Frontend\nSPA bundle")

        with Cluster("EKS cluster"):
            api = Deploy("api\nFastAPI")
            worker = Deploy("worker\nSQS consumer")
            argo = ArgoCD("ArgoCD")
            grafana = Grafana("kube-prometheus\nGrafana · Loki")

        # Data layer
        rds = RDS("RDS\nPostgreSQL (pgvector)")
        sqs = SQS("SQS\ntask queue")
        sched = Eventbridge("EventBridge\nnightly purge")
        s3_app = S3("S3\nuploads")
        ssm = SystemsManagerParameterStore("SSM\nParameter Store")

        # CI / CD
        with Cluster("CI / CD (ops account)"):
            github = GithubActions("GitHub Actions")
            ecr = ECR("ECR")

    # ── Request path ──────────────────────────────────────────
    users >> dns >> cf
    cf >> Edge(label="SPA") >> s3_fe
    cf >> Edge(label="/api /auth  (NLB → Envoy)") >> api
    api >> rds
    api >> sqs
    api >> s3_app
    sched >> Edge(label="cron") >> sqs
    sqs >> worker
    worker >> rds
    worker >> s3_app
    api >> Edge(style="dashed", label="External Secrets") >> ssm

    # ── GitOps CI / CD ────────────────────────────────────────
    github >> Edge(label="push images") >> ecr
    github >> Edge(label="bundle") >> s3_fe
    github >> Edge(label="tag bump") >> argo
    argo >> Edge(label="reconcile") >> api
    ecr >> Edge(label="pull") >> api

    # ── Observability ─────────────────────────────────────────
    api >> Edge(style="dashed", color="lightgray") >> grafana
    worker >> Edge(style="dashed", color="lightgray") >> grafana
