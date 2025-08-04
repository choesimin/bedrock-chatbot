#!/bin/bash

# AWS SAM을 사용한 Seoul 지역 배포 스크립트

set -e

# 환경 변수 설정
ENVIRONMENT=${1:-dev}
REGION=ap-northeast-2  # Seoul 지역 고정
STACK_NAME="bedrock-chatbot-${ENVIRONMENT}"

echo "🚀 Seoul 지역 배포 시작: ${STACK_NAME} (${REGION})"

# 사전 요구사항 확인
echo "📋 사전 요구사항 확인 중..."

# AWS CLI 확인
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI가 설치되지 않았습니다."
    exit 1
fi

# SAM CLI 확인
if ! command -v sam &> /dev/null; then
    echo "❌ SAM CLI가 설치되지 않았습니다."
    echo "설치 방법: pip install aws-sam-cli"
    exit 1
fi

# AWS 자격 증명 확인
echo "🔐 AWS 자격 증명 확인 중..."
if ! aws sts get-caller-identity --region ${REGION} > /dev/null 2>&1; then
    echo "❌ AWS 자격 증명을 확인할 수 없습니다."
    echo "aws configure를 실행하여 설정하세요."
    exit 1
fi

# Bedrock 권한 확인
echo "🧠 Bedrock 권한 확인 중..."
if ! aws bedrock list-foundation-models --region ${REGION} > /dev/null 2>&1; then
    echo "❌ Bedrock 권한이 없거나 Seoul 지역에서 Bedrock을 사용할 수 없습니다."
    echo "IAM 권한을 확인하고 Model access를 활성화하세요."
    exit 1
fi

echo "✅ 모든 사전 요구사항이 충족되었습니다."

# SAM 빌드
echo "📦 애플리케이션 빌드 중..."
sam build --region ${REGION}

if [ $? -ne 0 ]; then
    echo "❌ 빌드 실패"
    exit 1
fi

# S3 버킷 확인/생성 (SAM에서 필요)
BUCKET_NAME="sam-deployments-${REGION}-$(aws sts get-caller-identity --query Account --output text)"
echo "📁 S3 배포 버킷 확인 중: ${BUCKET_NAME}"

if ! aws s3 ls "s3://${BUCKET_NAME}" --region ${REGION} > /dev/null 2>&1; then
    echo "🪣 S3 버킷 생성 중..."
    aws s3 mb "s3://${BUCKET_NAME}" --region ${REGION}
fi

# SAM 배포
echo "🔄 ${ENVIRONMENT} 환경으로 배포 중..."
sam deploy \
  --stack-name ${STACK_NAME} \
  --region ${REGION} \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides Environment=${ENVIRONMENT} \
  --s3-bucket ${BUCKET_NAME} \
  --no-fail-on-empty-changeset \
  --no-confirm-changeset

if [ $? -ne 0 ]; then
    echo "❌ 배포 실패"
    exit 1
fi

# 배포 결과 출력
echo ""
echo "✅ 배포 완료!"
echo "============================================"

# API 엔드포인트 정보
API_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name ${STACK_NAME} \
  --region ${REGION} \
  --query 'Stacks[0].Outputs[?OutputKey==`ChatbotApiEndpoint`].OutputValue' \
  --output text)

HEALTH_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name ${STACK_NAME} \
  --region ${REGION} \
  --query 'Stacks[0].Outputs[?OutputKey==`HealthCheckEndpoint`].OutputValue' \
  --output text)

echo "📋 배포 정보:"
echo "  - 환경: ${ENVIRONMENT}"
echo "  - 지역: ${REGION}"
echo "  - 스택명: ${STACK_NAME}"
echo "  - API 엔드포인트: ${API_ENDPOINT}"
echo "  - Health Check: ${HEALTH_ENDPOINT}"

echo ""
echo "🧪 테스트 명령어:"
echo ""
echo "# Health Check 테스트"
echo "curl -X GET ${HEALTH_ENDPOINT}"
echo ""
echo "# 기본 채팅 테스트"
echo "curl -X POST ${API_ENDPOINT} \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"message\": \"안녕하세요! Seoul 지역에서 잘 작동하나요?\"}'"
echo ""
echo "# 세션 기반 채팅 테스트"
echo "curl -X POST ${API_ENDPOINT} \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"message\": \"내 이름을 기억해주세요. 김철수입니다.\", \"session_id\": \"test-session-123\"}'"

echo ""
echo "🎯 다음 단계:"
echo "1. Health check로 API 상태 확인"
echo "2. 기본 채팅 테스트 실행"
echo "3. 세션 기반 대화 테스트"
echo "4. AWS 콘솔에서 CloudWatch 로그 확인"

echo ""
echo "📊 모니터링 링크:"
echo "  - Lambda 함수: https://ap-northeast-2.console.aws.amazon.com/lambda/home?region=ap-northeast-2#/functions/bedrock-chatbot-${ENVIRONMENT}"
echo "  - CloudWatch 로그: https://ap-northeast-2.console.aws.amazon.com/cloudwatch/home?region=ap-northeast-2#logsV2:log-groups/log-group/%2Faws%2Flambda%2Fbedrock-chatbot-${ENVIRONMENT}"
echo "  - DynamoDB 테이블: https://ap-northeast-2.console.#!/bin/bash

# AWS SAM을 사용한 배포 스크립트

set -e

# 환경 변수 설정
ENVIRONMENT=${1:-dev}
REGION=${2:-us-east-1}
STACK_NAME="chatbot-api-${ENVIRONMENT}"

echo "🚀 배포 시작: ${STACK_NAME} (${REGION})"

# SAM 빌드
echo "📦 애플리케이션 빌드 중..."
sam build

# SAM 배포
echo "🔄 배포 중..."
sam deploy \
  --stack-name ${STACK_NAME} \
  --region ${REGION} \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides Environment=${ENVIRONMENT} \
  --no-fail-on-empty-changeset \
  --resolve-s3

# 배포 결과 출력
echo "✅ 배포 완료!"
echo ""
echo "📋 배포 정보:"
aws cloudformation describe-stacks \
  --stack-name ${STACK_NAME} \
  --region ${REGION} \
  --query 'Stacks[0].Outputs[?OutputKey==`ChatbotApiEndpoint`].OutputValue' \
  --output text

echo ""
echo "🧪 테스트 명령어:"
echo "curl -X POST \$(aws cloudformation describe-stacks --stack-name ${STACK_NAME} --region ${REGION} --query 'Stacks[0].Outputs[?OutputKey==\`ChatbotApiEndpoint\`].OutputValue' --output text) \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"message\": \"안녕하세요!\", \"session_id\": \"test123\"}'"

