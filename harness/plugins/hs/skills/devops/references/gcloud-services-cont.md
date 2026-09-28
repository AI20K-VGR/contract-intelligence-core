# Gcloud Services (continued)

## Cloud Functions

```bash
# Deploy function
gcloud functions deploy my-function \
  --runtime=python39 \
  --trigger-http \
  --allow-unauthenticated \
  --entry-point=main

# List functions
gcloud functions list

# Describe function
gcloud functions describe my-function

# Call function
gcloud functions call my-function

# Delete function
gcloud functions delete my-function
```

## BigQuery

```bash
# List datasets
bq ls

# Create dataset
bq mk my_dataset

# Load data
bq load --source_format=CSV my_dataset.my_table \
  gs://my-bucket/data.csv \
  schema.json

# Query
bq query --use_legacy_sql=false \
  'SELECT * FROM `my_dataset.my_table` LIMIT 10'

# Delete dataset
bq rm -r -f my_dataset
```

## Cloud Build

```bash
# Submit build
gcloud builds submit --tag=gcr.io/PROJECT_ID/my-image

# List builds
gcloud builds list

# Describe build
gcloud builds describe BUILD_ID

# Cancel build
gcloud builds cancel BUILD_ID
```

## Artifact Registry

```bash
# Create repository
gcloud artifacts repositories create my-repo \
  --repository-format=docker \
  --location=us-central1

# Configure Docker
gcloud auth configure-docker us-central1-docker.pkg.dev

# Push image
docker tag my-image us-central1-docker.pkg.dev/PROJECT_ID/my-repo/my-image
docker push us-central1-docker.pkg.dev/PROJECT_ID/my-repo/my-image

# List repositories
gcloud artifacts repositories list
```

## Networking

```bash
# Create VPC network
gcloud compute networks create my-network \
  --subnet-mode=auto

# Create firewall rule
gcloud compute firewall-rules create allow-http \
  --network=my-network \
  --allow=tcp:80

# List networks
gcloud compute networks list

# List firewall rules
gcloud compute firewall-rules list
```

## IAM

```bash
# List IAM policy
gcloud projects get-iam-policy PROJECT_ID

# Add IAM binding
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="user:user@example.com" \
  --role="roles/viewer"

# Remove IAM binding
gcloud projects remove-iam-policy-binding PROJECT_ID \
  --member="user:user@example.com" \
  --role="roles/viewer"

# List service accounts
gcloud iam service-accounts list
```

## Monitoring & Logging

```bash
# View logs
gcloud logging read "resource.type=gce_instance" \
  --limit=10 \
  --format=json

# Create log sink
gcloud logging sinks create my-sink \
  storage.googleapis.com/my-bucket \
  --log-filter="resource.type=gce_instance"

# List metrics
gcloud monitoring metrics-descriptors list
```

## Quick Reference

| Service | Command Prefix |
|---------|----------------|
| Compute Engine | `gcloud compute` |
| GKE | `gcloud container` |
| Cloud Run | `gcloud run` |
| App Engine | `gcloud app` |
| Cloud Storage | `gsutil` |
| BigQuery | `bq` |
| Cloud SQL | `gcloud sql` |
| Cloud Functions | `gcloud functions` |
| IAM | `gcloud iam` |

## Resources

- Compute Engine: https://cloud.google.com/compute/docs
- GKE: https://cloud.google.com/kubernetes-engine/docs
- Cloud Run: https://cloud.google.com/run/docs
- App Engine: https://cloud.google.com/appengine/docs
- Cloud Storage: https://cloud.google.com/storage/docs
