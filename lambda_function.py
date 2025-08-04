import json
import boto3
import os
import time
from typing import Dict, Any, List
from botocore.exceptions import ClientError

# Seoul 지역 Bedrock 클라이언트 (Lambda 컨테이너 재사용을 위해 전역으로 선언)
bedrock_runtime = boto3.client(
    service_name='bedrock-runtime',
    region_name='ap-northeast-2'  # Seoul 지역
)

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda 핸들러 함수 - Seoul 지역 Bedrock 챗봇
    """
    try:
        print(f"Received event: {json.dumps(event)}")
        
        # CORS 헤더
        headers = {
            'Content-Type': 'application/json; charset=utf-8',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Requested-With'
        }
        
        # OPTIONS 요청 처리 (CORS preflight)
        if event.get('httpMethod') == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({'message': 'CORS preflight successful'})
            }
        
        # HTTP 메서드 확인
        if event.get('httpMethod') != 'POST':
            return {
                'statusCode': 405,
                'headers': headers,
                'body': json.dumps({
                    'error': 'Method not allowed. Use POST method.',
                    'allowed_methods': ['POST', 'OPTIONS']
                }, ensure_ascii=False)
            }
        
        # 요청 본문 파싱
        try:
            body = json.loads(event.get('body', '{}'))
        except json.JSONDecodeError:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': '잘못된 JSON 형식입니다.',
                    'status': 'error'
                }, ensure_ascii=False)
            }
        
        # 요청 파라미터 추출
        message = body.get('message', '').strip()
        session_id = body.get('session_id')
        model_id = body.get('model_id', 'anthropic.claude-sonnet-4-20250514-v1:0')
        max_tokens = int(body.get('max_tokens', os.environ.get('MAX_TOKENS', '1000')))
        temperature = float(body.get('temperature', os.environ.get('TEMPERATURE', '0.7')))
        
        # 입력 검증
        if not message:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': '메시지가 필요합니다.',
                    'required_fields': ['message'],
                    'optional_fields': ['session_id', 'model_id', 'max_tokens', 'temperature']
                }, ensure_ascii=False)
            }
        
        # 메시지 길이 검증
        if len(message) > 10000:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': '메시지가 너무 깁니다. 10,000자 이내로 입력해주세요.',
                    'current_length': len(message),
                    'max_length': 10000
                }, ensure_ascii=False)
            }
        
        # 대화 기록 처리
        conversation_history = []
        if session_id:
            conversation_history = get_conversation_history(session_id)
        
        # 현재 메시지 추가
        conversation_history.append({
            "role": "user",
            "content": message
        })
        
        # Bedrock 호출
        start_time = time.time()
        response_text = call_bedrock(conversation_history, model_id, max_tokens, temperature)
        end_time = time.time()
        
        # 대화 기록 저장 (세션 ID가 있는 경우)
        if session_id:
            save_conversation_history(session_id, conversation_history, response_text)
        
        # 성공 응답
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'response': response_text,
                'session_id': session_id,
                'model_used': model_id,
                'processing_time': round(end_time - start_time, 2),
                'region': 'ap-northeast-2',
                'status': 'success'
            }, ensure_ascii=False)
        }
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        print(f"AWS ClientError: {error_code} - {str(e)}")
        
        if error_code == 'AccessDeniedException':
            error_message = "모델 액세스 권한이 없습니다. AWS 콘솔에서 Model access를 활성화하세요."
        elif error_code == 'ThrottlingException':
            error_message = "요청이 너무 많습니다. 잠시 후 다시 시도해주세요."
        elif error_code == 'ValidationException':
            error_message = f"요청 형식이 잘못되었습니다: {e.response['Error']['Message']}"
        else:
            error_message = f"AWS 서비스 오류: {str(e)}"
        
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': error_message,
                'error_code': error_code,
                'status': 'aws_error'
            }, ensure_ascii=False)
        }
        
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': f'서버 내부 오류가 발생했습니다: {str(e)}',
                'status': 'internal_error'
            }, ensure_ascii=False)
        }

def call_bedrock(messages: List[Dict], model_id: str, max_tokens: int, temperature: float) -> str:
    """
    Seoul 지역 Bedrock 모델 호출
    """
    try:
        # Claude 4 모델용 요청 body
        if 'anthropic' in model_id:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "messages": messages,
                "temperature": temperature
            }
        
        # Amazon Titan 모델용 (Seoul 지역에서 사용 가능)
        elif 'amazon.titan' in model_id:
            # Titan 모델의 경우 다른 포맷 사용
            prompt = format_messages_for_titan(messages)
            body = {
                "inputText": prompt,
                "textGenerationConfig": {
                    "maxTokenCount": max_tokens,
                    "temperature": temperature,
                    "topP": 0.9
                }
            }
        
        else:
            raise ValueError(f"지원하지 않는 모델입니다: {model_id}")
        
        print(f"Calling Bedrock model: {model_id}")
        
        response = bedrock_runtime.invoke_model(
            body=json.dumps(body),
            modelId=model_id,
            accept='application/json',
            contentType='application/json'
        )
        
        response_body = json.loads(response.get('body').read())
        print(f"Bedrock response received successfully")
        
        # 모델별 응답 파싱
        if 'anthropic' in model_id:
            return response_body['content'][0]['text']
        elif 'amazon.titan' in model_id:
            return response_body['results'][0]['outputText']
            
    except ClientError as e:
        print(f"Bedrock ClientError: {str(e)}")
        raise
    except Exception as e:
        print(f"Bedrock call error: {str(e)}")
        raise Exception(f"모델 호출 중 오류가 발생했습니다: {str(e)}")

def get_conversation_history(session_id: str) -> List[Dict]:
    """
    DynamoDB에서 대화 기록 조회
    """
    if not os.environ.get('DYNAMODB_TABLE'):
        print("DynamoDB table not configured, using session-less mode")
        return []
    
    try:
        dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-2')
        table = dynamodb.Table(os.environ['DYNAMODB_TABLE'])
        
        response = table.get_item(Key={'session_id': session_id})
        
        if 'Item' in response:
            messages = response['Item'].get('messages', [])
            print(f"Retrieved {len(messages)} messages for session {session_id}")
            return messages
        else:
            print(f"No conversation history found for session {session_id}")
            return []
        
    except Exception as e:
        print(f"DynamoDB 조회 오류: {str(e)}")
        return []

def save_conversation_history(session_id: str, messages: List[Dict], bot_response: str):
    """
    DynamoDB에 대화 기록 저장
    """
    if not os.environ.get('DYNAMODB_TABLE'):
        print("DynamoDB table not configured, skipping save")
        return
    
    try:
        # 봇 응답 추가
        messages.append({
            "role": "assistant",
            "content": bot_response
        })
        
        dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-2')
        table = dynamodb.Table(os.environ['DYNAMODB_TABLE'])
        
        # 최근 20개 메시지만 유지 (10턴 대화)
        if len(messages) > 20:
            messages = messages[-20:]
        
        # TTL 설정 (24시간 후 자동 삭제)
        ttl = int(time.time()) + (24 * 60 * 60)
        
        table.put_item(
            Item={
                'session_id': session_id,
                'messages': messages,
                'updated_at': int(time.time()),
                'ttl': ttl
            }
        )
        
        print(f"Saved conversation history for session {session_id}")
        
    except Exception as e:
        print(f"DynamoDB 저장 오류: {str(e)}")

def format_messages_for_titan(messages: List[Dict]) -> str:
    """
    Amazon Titan 모델용 프롬프트 포맷팅
    """
    formatted = ""
    for msg in messages:
        if msg['role'] == 'user':
            formatted += f"User: {msg['content']}\n"
        elif msg['role'] == 'assistant':
            formatted += f"Assistant: {msg['content']}\n"
    
    formatted += "Assistant: "
    return formatted



