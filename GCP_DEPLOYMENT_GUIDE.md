# 🚀 GCP Cloud Run Deployment Guide - SISL Connect Bot

## Prerequisites

1. **Google Cloud Account** with billing enabled
2. **Google Cloud SDK** installed locally
3. **GitHub repository** with code pushed (✅ You have this)
4. **Docker** installed locally (for testing)

---

## Step 1: Set Up Google Cloud Project

### 1.1 Create a new GCP Project
```bash
gcloud projects create sisl-connect-bot --name="SISL Connect Bot"
gcloud config set project sisl-connect-bot
```

### 1.2 Enable Required APIs
```bash
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  storage-api.googleapis.com \
  storage-component.googleapis.com \
  cloudscheduler.googleapis.com
```

### 1.3 Set your project ID
```powershell
$PROJECT_ID = "sisl-connect-bot"
$REGION = "asia-south1"  # or your preferred region

gcloud config set project $PROJECT_ID
gcloud config set run/region $REGION
```

---

## Step 2: Create Google Cloud Storage Bucket

This bucket stores the indexed content for the RAG system.

```bash
gsutil mb -p $PROJECT_ID -l asia-south1 gs://sisl-connect-content

# Set appropriate permissions
gsutil iam ch serviceAccount:$PROJECT_ID@appspot.gserviceaccount.com:roles/storage.objectViewer gs://sisl-connect-content
gsutil iam ch serviceAccount:$PROJECT_ID@appspot.gserviceaccount.com:roles/storage.objectEditor gs://sisl-connect-content
```

---

## Step 3: Create Service Account with Proper Permissions

```bash
# Create service account
gcloud iam service-accounts create sisl-connect-bot-sa \
  --display-name="SISL Connect Bot Service Account"

# Grant necessary permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member=serviceAccount:sisl-connect-bot-sa@$PROJECT_ID.iam.gserviceaccount.com \
  --role=roles/storage.objectAdmin

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member=serviceAccount:sisl-connect-bot-sa@$PROJECT_ID.iam.gserviceaccount.com \
  --role=roles/aiplatform.user
```

---

## Step 4: Deploy Chatbot Service to Cloud Run

### 4.1 Using Cloud Build (Recommended)

Create a `cloudbuild.yaml` file in root directory:

```yaml
steps:
  # Build the chatbot image
  - name: 'gcr.io/cloud-builders/docker'
    args: 
      - 'build'
      - '-t'
      - 'gcr.io/$PROJECT_ID/sisl-connect-chatbot:latest'
      - './MIDC-chatbot'
    id: 'build-chatbot'

  # Push to Container Registry
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'push'
      - 'gcr.io/$PROJECT_ID/sisl-connect-chatbot:latest'
    id: 'push-chatbot'

  # Deploy to Cloud Run
  - name: 'gcr.io/cloud-builders/gke-deploy'
    args:
      - 'run'
      - '--filename=.'
      - '--image=gcr.io/$PROJECT_ID/sisl-connect-chatbot:latest'
      - '--location=$_DEPLOY_REGION'
      - '--output=/workspace/deploy'
    id: 'deploy-chatbot'

  - name: 'gcr.io/cloud-builders/gke-deploy'
    args:
      - 'replace'
      - '--filename=/workspace/deploy/service.yaml'
      - '--image=gcr.io/$PROJECT_ID/sisl-connect-chatbot:latest'
    id: 'apply-chatbot'

substitutions:
  _DEPLOY_REGION: 'asia-south1'

images:
  - 'gcr.io/$PROJECT_ID/sisl-connect-chatbot:latest'

options:
  logging: CLOUD_LOGGING_ONLY
```

### 4.2 Deploy using gcloud command (Simpler)

```bash
cd MIDC-chatbot

gcloud run deploy sisl-connect-chatbot \
  --source . \
  --platform managed \
  --region asia-south1 \
  --allow-unauthenticated \
  --set-env-vars BUCKET_NAME=sisl-connect-content \
  --service-account sisl-connect-bot-sa@$PROJECT_ID.iam.gserviceaccount.com

cd ..
```

### 4.3 Save the Chatbot URL
```bash
gcloud run services describe sisl-connect-chatbot \
  --region asia-south1 \
  --format='value(status.url)'
```

### 4.4 Map Custom Domain: `contact.sislcloud.in`
1. Verify your domain is owned in Google Cloud:
```bash
gcloud domains registrations list
```
2. Create a Cloud Run domain mapping:
```bash
gcloud run domain-mappings create \
  --service sisl-connect-chatbot \
  --domain contact.sislcloud.in \
  --region asia-south1
```
3. Copy the DNS records shown by the command.
4. Add the required `A` and/or `CNAME` records in your DNS provider for `contact.sislcloud.in`.
5. Wait for DNS propagation, then verify:
```bash
gcloud run domain-mappings describe \
  --service sisl-connect-chatbot \
  --domain contact.sislcloud.in \
  --region asia-south1
```

**After mapping is complete, use the custom domain in the frontend:**
```javascript
const response = await fetch(
  "https://contact.sislcloud.in/chat",
  { ... }
);
```

---

## Step 5: Deploy Indexer Service to Cloud Run

The indexer can run as a Cloud Run service or a scheduled job. Here's the Cloud Run approach:

```bash
cd MIDC-indexer

gcloud run deploy sisl-connect-indexer \
  --source . \
  --platform managed \
  --region asia-south1 \
  --no-allow-unauthenticated \
  --set-env-vars BUCKET_NAME=sisl-connect-content \
  --service-account sisl-connect-bot-sa@$PROJECT_ID.iam.gserviceaccount.com \
  --timeout 3600 \
  --memory 2Gi

cd ..
```

---

## Step 6: Set Up Automated Indexing (Cloud Scheduler)

Run indexing automatically (e.g., daily):

```bash
# Create a Cloud Scheduler job
gcloud scheduler jobs create http sisl-index-daily \
  --schedule="0 2 * * *" \
  --uri="https://YOUR_INDEXER_URL/" \
  --http-method=GET \
  --location=asia-south1 \
  --oidc-service-account-email=sisl-connect-bot-sa@$PROJECT_ID.iam.gserviceaccount.com \
  --oidc-token-audience="https://YOUR_INDEXER_URL/"
```

Replace `YOUR_INDEXER_URL` with:
```bash
gcloud run services describe sisl-connect-indexer \
  --region asia-south1 \
  --format='value(status.url)'
```

---

## Step 7: Configure Environment Variables

For both services, set these environment variables in Cloud Run:

**For Chatbot:**
- `BUCKET_NAME`: `sisl-connect-content`
- `MODEL_NAME`: `gemini-1.5-flash`
- `PORT`: `8080`

**For Indexer:**
- `BUCKET_NAME`: `sisl-connect-content`

```bash
# Update chatbot service
gcloud run services update sisl-connect-chatbot \
  --update-env-vars BUCKET_NAME=sisl-connect-content \
  --region asia-south1

# Update indexer service  
gcloud run services update sisl-connect-indexer \
  --update-env-vars BUCKET_NAME=sisl-connect-content \
  --region asia-south1
```

---

## Step 8: Test the Deployment

### Test Chatbot API:
```bash
curl -X POST https://YOUR_CHATBOT_URL/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Tell me about SISL Infotech"}'
```

### Test Indexer:
```bash
curl -X POST https://YOUR_INDEXER_URL/ \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)"
```

### Test from Frontend:
1. Get the chatbot URL from Cloud Run
2. Update `frontend/index.html` with the chatbot endpoint
3. Open `frontend/index.html` in your browser
4. Click the chat button and ask a question

---

## Step 9: Monitor and Logs

### View logs for Chatbot:
```bash
gcloud run logs read sisl-connect-chatbot --region asia-south1 --limit 50
```

### View logs for Indexer:
```bash
gcloud run logs read sisl-connect-indexer --region asia-south1 --limit 50
```

### Monitor in Cloud Console:
1. Go to [Cloud Run Console](https://console.cloud.google.com/run)
2. Click on your service
3. View Metrics, Logs, and Revisions

---

## Step 10: Security Best Practices

✅ **Implement these security measures:**

```bash
# Restrict Chatbot access to specific origins (update CORS)
# Add HTTPS only
# Enable Cloud Armor for DDoS protection
# Set up VPC for private networking

# For Indexer - Keep it private (no public access)
gcloud run services update sisl-connect-indexer \
  --no-allow-unauthenticated \
  --region asia-south1
```

---

## Troubleshooting

### Issue: "Default credentials were not found"
**Solution:** Cloud Run automatically provides credentials. Make sure service account has proper permissions.

### Issue: "404 Error when scraping SISL website"
**Solution:** Update the URLs in `MIDC-indexer/main.py` to match actual website paths.

### Issue: "Cannot connect to Google Cloud Storage"
**Solution:** 
1. Verify bucket name is correct
2. Check service account permissions
3. Ensure APIs are enabled

---

## Full Deployment Script

Create `deploy.sh`:

```bash
#!/bin/bash

PROJECT_ID="sisl-connect-bot"
REGION="asia-south1"

gcloud config set project $PROJECT_ID

# Build and deploy chatbot
cd MIDC-chatbot
gcloud run deploy sisl-connect-chatbot \
  --source . \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated
cd ..

# Build and deploy indexer
cd MIDC-indexer
gcloud run deploy sisl-connect-indexer \
  --source . \
  --platform managed \
  --region $REGION \
  --no-allow-unauthenticated
cd ..

echo "✅ Deployment complete!"
gcloud run services list --region $REGION
```

Run with:
```bash
bash deploy.sh
```

---

## Cost Estimation

- **Cloud Run:** ~$0.20/million requests (first 2M free per month)
- **Cloud Storage:** ~$0.020/GB (first 5GB free per month)
- **Cloud Scheduler:** ~$0.10/job per month

**Estimated monthly cost for small usage: <$5**

---

## Next Steps

1. ✅ Complete all steps above
2. 📝 Update frontend with chatbot URL
3. 🧪 Test the chatbot
4. 🔄 Set up Cloud Scheduler for automatic indexing
5. 📊 Monitor logs and metrics
6. 🔐 Implement security controls

Need help with any step? Let me know! 🚀
