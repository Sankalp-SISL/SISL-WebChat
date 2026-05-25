#!/bin/bash

# 🚀 SISL Connect Bot - GCP Cloud Run Deployment Script
# This script automates the deployment of both chatbot and indexer to Google Cloud Run

set -e

echo "════════════════════════════════════════════════════════════════"
echo "🚀 SISL Connect Bot - GCP Cloud Run Deployment"
echo "════════════════════════════════════════════════════════════════"

# Configuration
PROJECT_ID=${1:-"sisl-connect-bot"}
REGION=${2:-"asia-south1"}
BUCKET_NAME="sisl-connect-content"

echo ""
echo "📋 Configuration:"
echo "   Project ID: $PROJECT_ID"
echo "   Region: $REGION"
echo "   Bucket: $BUCKET_NAME"
echo ""

# Step 1: Set Project
echo "Step 1️⃣: Setting GCP Project..."
gcloud config set project $PROJECT_ID
echo "✅ Project set to $PROJECT_ID"
echo ""

# Step 2: Enable APIs
echo "Step 2️⃣: Enabling Required APIs..."
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  storage-api.googleapis.com \
  storage-component.googleapis.com \
  cloudscheduler.googleapis.com \
  iam.googleapis.com
echo "✅ APIs enabled"
echo ""

# Step 3: Create Storage Bucket
echo "Step 3️⃣: Creating Google Cloud Storage Bucket..."
if gsutil ls -b gs://$BUCKET_NAME &>/dev/null; then
  echo "✅ Bucket gs://$BUCKET_NAME already exists"
else
  gsutil mb -p $PROJECT_ID -l $REGION gs://$BUCKET_NAME
  echo "✅ Created bucket gs://$BUCKET_NAME"
fi
echo ""

# Step 4: Create Service Account
echo "Step 4️⃣: Creating Service Account..."
SERVICE_ACCOUNT="sisl-connect-bot-sa@$PROJECT_ID.iam.gserviceaccount.com"

if gcloud iam service-accounts describe $SERVICE_ACCOUNT &>/dev/null; then
  echo "✅ Service account already exists"
else
  gcloud iam service-accounts create sisl-connect-bot-sa \
    --display-name="SISL Connect Bot Service Account"
  echo "✅ Created service account"
fi

# Grant permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member=serviceAccount:$SERVICE_ACCOUNT \
  --role=roles/storage.objectAdmin \
  --quiet
echo "✅ Granted storage permissions"
echo ""

# Step 5: Deploy Chatbot
echo "Step 5️⃣: Deploying Chatbot Service..."
cd MIDC-chatbot

gcloud run deploy sisl-connect-chatbot \
  --source . \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars BUCKET_NAME=$BUCKET_NAME \
  --service-account $SERVICE_ACCOUNT \
  --memory 512Mi \
  --timeout 300 \
  --max-instances 100 \
  --quiet

CHATBOT_URL=$(gcloud run services describe sisl-connect-chatbot \
  --region $REGION \
  --format='value(status.url)')

echo "✅ Chatbot deployed!"
echo "   URL: $CHATBOT_URL"
cd ..
echo ""

# Step 6: Deploy Indexer
echo "Step 6️⃣: Deploying Indexer Service..."
cd MIDC-indexer

gcloud run deploy sisl-connect-indexer \
  --source . \
  --platform managed \
  --region $REGION \
  --no-allow-unauthenticated \
  --set-env-vars BUCKET_NAME=$BUCKET_NAME \
  --service-account $SERVICE_ACCOUNT \
  --memory 1Gi \
  --timeout 3600 \
  --max-instances 1 \
  --quiet

INDEXER_URL=$(gcloud run services describe sisl-connect-indexer \
  --region $REGION \
  --format='value(status.url)')

echo "✅ Indexer deployed!"
echo "   URL: $INDEXER_URL"
cd ..
echo ""

# Step 7: Create Cloud Scheduler Job
echo "Step 7️⃣: Setting up Cloud Scheduler (Daily Indexing)..."

JOB_NAME="sisl-index-daily"
SCHEDULE="0 2 * * *"  # 2 AM daily

# Delete existing job if it exists
gcloud scheduler jobs delete $JOB_NAME --location $REGION --quiet 2>/dev/null || true

# Create new job
gcloud scheduler jobs create http $JOB_NAME \
  --location $REGION \
  --schedule="$SCHEDULE" \
  --uri="$INDEXER_URL/" \
  --http-method=GET \
  --oidc-service-account-email=$SERVICE_ACCOUNT \
  --oidc-token-audience="$INDEXER_URL/" \
  --quiet

echo "✅ Cloud Scheduler job created"
echo "   Job: $JOB_NAME"
echo "   Schedule: Daily at 2:00 AM"
echo ""

# Step 8: Summary
echo "════════════════════════════════════════════════════════════════"
echo "✅ DEPLOYMENT COMPLETE!"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "📊 Deployment Summary:"
echo "   Chatbot URL: $CHATBOT_URL"
echo "   Indexer URL: $INDEXER_URL"
echo "   Storage: gs://$BUCKET_NAME"
echo "   Region: $REGION"
echo ""
echo "🔧 Next Steps:"
echo "   1. Update frontend/index.html with the Chatbot URL"
echo "   2. Test the chatbot via the frontend"
echo "   3. Monitor logs: gcloud run logs read sisl-connect-chatbot"
echo "   4. Manually run indexer: curl -X POST $INDEXER_URL/ \\"
echo "      -H 'Authorization: Bearer \$(gcloud auth print-identity-token)'"
echo ""
echo "📚 Documentation:"
echo "   - Full guide: GCP_DEPLOYMENT_GUIDE.md"
echo "   - Cloud Run Console: https://console.cloud.google.com/run"
echo ""
