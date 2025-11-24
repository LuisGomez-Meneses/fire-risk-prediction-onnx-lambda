AQUÍ TIENES EL COMANDO ÚNICO PARA PEGAR TODO EL README

Este comando sobrescribe tu README.md con el contenido completo, profesional y final.

📌 Cópialo COMPLETO y pégalo tal cual en Git Bash dentro del repositorio.

cat > README.md << 'EOF'
# 🔥 Fire Risk Prediction – ONNX Model on AWS Lambda  
Service for computing **fire probability maps** using MODIS NDVI & LST products, an **ONNX model**, and an AWS serverless backend based on **Lambda + Docker + API Gateway**.

This repository is **fully replicable**: anyone can deploy the same architecture from scratch.

---

# 🚀 1. Architecture Overview  



Client → API Gateway → Lambda (Docker Image + ONNXRuntime) → S3 (NDVI, LST, Results)


The Lambda function:

1. Downloads NDVI and LST GeoTIFFs from S3  
2. Reprojects NDVI onto LST grid  
3. Runs inference using an **XGBoost ONNX model**  
4. Generates a fire probability GeoTIFF  
5. Saves the output to S3  

---

# 📁 2. Repository Structure  



fire-risk-prediction-onnx-lambda/
│── Dockerfile
│── lambda_function.py
│── requirements.txt
│── request.json
│── response.json
│── output.json
│── README.md


---

# 🗂️ 3. Required S3 Structure  

Bucket must contain:



tsbiomassmodeldata/
│── model/
│ └── xgb_fire_model.onnx
│
│── img__...NDVI....tif
│── img__...LST....tif
│
└── results/ <-- lambda writes output here


---

# 🐳 4. Build & Tag Docker Image  

From directory:



C:\lambda-fire\lambda-fire-docker\


Build:

```sh
docker build -t fire-lambda .


Tag:

docker tag fire-lambda:latest 036134507423.dkr.ecr.us-east-1.amazonaws.com/fire-lambda:latest


Push:

docker push 036134507423.dkr.ecr.us-east-1.amazonaws.com/fire-lambda:latest

🟧 5. Update AWS Lambda (Container Image)
aws lambda update-function-code \
  --function-name fire_detection_lambda \
  --image-uri 036134507423.dkr.ecr.us-east-1.amazonaws.com/fire-lambda:latest \
  --region us-east-1

🧪 6. Test via AWS CLI

Use request.json.

aws lambda invoke \
  --function-name fire_detection_lambda \
  --cli-binary-format raw-in-base64-out \
  --payload file://request.json \
  output.json \
  --region us-east-1

🌐 7. API Gateway (HTTP API)
Create API
aws apigatewayv2 create-api \
  --name FireDetectionAPI \
  --protocol-type HTTP \
  --target arn:aws:lambda:us-east-1:036134507423:function:fire_detection_lambda \
  --region us-east-1

Add permission
aws lambda add-permission \
  --function-name fire_detection_lambda \
  --statement-id apigw-access \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:us-east-1:ACCOUNT_ID:API_ID/*/*" \
  --region us-east-1

Add route “POST /infer”
aws apigatewayv2 create-route \
  --api-id API_ID \
  --route-key "POST /infer" \
  --target "integrations/INTEGRATION_ID"

🌍 8. Test Via API Gateway (Curl)
curl -X POST \
  -H "Content-Type: application/json" \
  -d @request.json \
  https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/infer

📄 9. Example Request (request.json)
{
  "bucket": "tsbiomassmodeldata",
  "ndvi_key": "img__20251121115911__MOD13A1__NDVI_EVI_DetailedQA_sur_refl_b01_sur_refl___2025_10_15__1517.tif",
  "lst_key":  "img__20251121120054__MOD11A1__LST_Day_1km_LST_Night_1km_QC_Day_Day_view___2025_10_06__2219.tif"
}

📄 10. Example Lambda Response
{
  "message": "Fire probability map generated",
  "input_NDVI": "s3://tsbiomassmodeldata/...NDVI...tif",
  "input_LST": "s3://tsbiomassmodeldata/...LST...tif",
  "output": "s3://tsbiomassmodeldata/results/fire_prob_XXXX.tif"
}

🧱 11. Reproducibility Checklist

To replicate in another AWS account:

Create S3 bucket + upload NDVI/LST and model

Build & push Docker image to ECR

Create Lambda function

Configure memory + timeout

Create API Gateway

Add invoke permissions

Send POST /infer requests

👥 12. Authors

Luis Miguel Gómez Meneses — Implementation, AWS setup, ONNX pipeline

Suan Blockchain / Terrasacha — Cloud integration support