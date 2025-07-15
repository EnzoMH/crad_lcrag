"""
🤖 Langchain GoogleGenerativeAI 기반 Gemini 클라이언트

멀티 API 키 지원 및 로드밸런싱 기능
- 자동 API 키 순환
- 요청 제한 관리
- 실패 시 자동 재시도
- 성능 모니터링
"""

import os
import time
import asyncio
import random
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from collections import deque
from enum import Enum

from langchain_google_genai import GoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain.chains import LLMChain

from loguru import logger
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()


class ModelType(Enum):
    """Gemini 모델 타입"""
    GEMINI_PRO = "gemini-pro"
    GEMINI_PRO_VISION = "gemini-pro-vision"
    GEMINI_1_5_FLASH = "gemini-1.5-flash"
    GEMINI_1_5_PRO = "gemini-1.5-pro"


@dataclass
class APIKeyStatus:
    """API 키 상태 정보"""
    key: str
    is_active: bool = True
    request_count: int = 0
    last_request_time: float = 0.0
    error_count: int = 0
    success_count: int = 0
    
    @property
    def success_rate(self) -> float:
        total = self.success_count + self.error_count
        return self.success_count / total if total > 0 else 0.0


@dataclass
class RequestMetrics:
    """요청 메트릭 정보"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time: float = 0.0
    requests_per_minute: float = 0.0
    
    @property
    def success_rate(self) -> float:
        return self.successful_requests / self.total_requests if self.total_requests > 0 else 0.0


class GeminiClient:
    """
    🤖 Langchain 기반 Gemini API 클라이언트
    
    Features:
    - 멀티 API 키 지원
    - 자동 로드밸런싱
    - 요청 제한 관리
    - 실패 시 자동 재시도
    - 성능 모니터링
    """
    
    def __init__(
        self,
        model_type: ModelType = ModelType.GEMINI_1_5_FLASH,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        rpm_limit: int = 2000,
        tpm_limit: int = 4000000
    ):
        """
        Gemini 클라이언트 초기화
        
        Args:
            model_type: 사용할 Gemini 모델 타입
            temperature: 응답 창의성 (0.0-1.0)
            max_tokens: 최대 토큰 수
            max_retries: 최대 재시도 횟수
            retry_delay: 재시도 지연 시간 (초)
            rpm_limit: 분당 요청 제한
            tpm_limit: 분당 토큰 제한
        """
        self.model_type = model_type
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.rpm_limit = rpm_limit
        self.tpm_limit = tpm_limit
        
        # API 키 로드 및 초기화
        self.api_keys = self._load_api_keys()
        self.api_key_status = {
            key: APIKeyStatus(key=key) for key in self.api_keys
        }
        
        # LLM 인스턴스 생성
        self.llm_instances = {}
        self._initialize_llm_instances()
        
        # 요청 추적
        self.request_history = deque(maxlen=10000)
        self.metrics = RequestMetrics()
        
        # 현재 사용 중인 API 키 인덱스
        self.current_key_index = 0
        
        logger.info(f"🤖 Gemini 클라이언트 초기화 완료 - {len(self.api_keys)}개 API 키 로드")
    
    def _load_api_keys(self) -> List[str]:
        """환경 변수에서 API 키들을 로드"""
        keys = []
        
        # 기본 API 키
        primary_key = os.getenv("GEMINI_API_KEY")
        if primary_key:
            keys.append(primary_key)
        
        # 추가 API 키들
        for i in range(2, 10):  # GEMINI_API_KEY_2 ~ GEMINI_API_KEY_9
            key = os.getenv(f"GEMINI_API_KEY_{i}")
            if key:
                keys.append(key)
        
        if not keys:
            raise ValueError("❌ GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
        
        logger.info(f"🔑 {len(keys)}개의 Gemini API 키 로드 완료")
        return keys
    
    def _initialize_llm_instances(self):
        """각 API 키에 대해 LLM 인스턴스 생성"""
        for key in self.api_keys:
            try:
                self.llm_instances[key] = GoogleGenerativeAI(
                    model=self.model_type.value,
                    google_api_key=key,
                    temperature=self.temperature,
                    max_output_tokens=self.max_tokens
                )
                logger.debug(f"✅ LLM 인스턴스 생성 성공: {key[:10]}...")
            except Exception as e:
                logger.error(f"❌ LLM 인스턴스 생성 실패: {key[:10]}... - {e}")
                self.api_key_status[key].is_active = False
    
    def _get_next_api_key(self) -> str:
        """다음 사용 가능한 API 키 반환 (로드밸런싱)"""
        active_keys = [
            key for key, status in self.api_key_status.items()
            if status.is_active
        ]
        
        if not active_keys:
            raise RuntimeError("❌ 사용 가능한 API 키가 없습니다.")
        
        # 성공률 기반 가중치 선택
        weights = [
            max(0.1, self.api_key_status[key].success_rate) 
            for key in active_keys
        ]
        
        # 가중치 기반 랜덤 선택
        selected_key = random.choices(active_keys, weights=weights)[0]
        
        return selected_key
    
    def _check_rate_limit(self, api_key: str) -> bool:
        """API 키의 요청 제한 확인"""
        status = self.api_key_status[api_key]
        current_time = time.time()
        
        # 1분 내 요청 수 확인
        recent_requests = [
            req for req in self.request_history
            if req.get('api_key') == api_key and 
               current_time - req.get('timestamp', 0) < 60
        ]
        
        if len(recent_requests) >= self.rpm_limit:
            logger.warning(f"⚠️ API 키 {api_key[:10]}... RPM 제한 초과")
            return False
        
        return True
    
    async def _execute_with_retry(
        self,
        prompt: str,
        api_key: str,
        **kwargs
    ) -> str:
        """재시도 로직이 포함된 요청 실행"""
        llm = self.llm_instances[api_key]
        status = self.api_key_status[api_key]
        
        for attempt in range(self.max_retries):
            try:
                start_time = time.time()
                
                # 요청 실행
                response = await llm.ainvoke(prompt, **kwargs)
                
                # 성공 메트릭 업데이트
                execution_time = time.time() - start_time
                status.success_count += 1
                status.last_request_time = time.time()
                
                # 요청 히스토리 추가
                self.request_history.append({
                    'api_key': api_key,
                    'timestamp': time.time(),
                    'execution_time': execution_time,
                    'success': True
                })
                
                logger.debug(f"✅ 요청 성공: {api_key[:10]}... ({execution_time:.2f}s)")
                return response
                
            except Exception as e:
                status.error_count += 1
                logger.warning(f"⚠️ 요청 실패 (시도 {attempt + 1}/{self.max_retries}): {e}")
                
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))  # 지수 백오프
                else:
                    # 최종 실패 시 API 키 비활성화 (일시적)
                    status.is_active = False
                    logger.error(f"❌ API 키 {api_key[:10]}... 일시적 비활성화")
                    
                    # 요청 히스토리 추가
                    self.request_history.append({
                        'api_key': api_key,
                        'timestamp': time.time(),
                        'success': False,
                        'error': str(e)
                    })
                    
                    raise e
    
    async def generate_content(
        self,
        prompt: str,
        **kwargs
    ) -> str:
        """
        컨텐츠 생성 (멀티 API 키 지원)
        
        Args:
            prompt: 입력 프롬프트
            **kwargs: 추가 매개변수
            
        Returns:
            생성된 컨텐츠
        """
        # 사용 가능한 API 키 선택
        api_key = self._get_next_api_key()
        
        # 요청 제한 확인
        if not self._check_rate_limit(api_key):
            # 다른 API 키 시도
            for key in self.api_keys:
                if key != api_key and self._check_rate_limit(key):
                    api_key = key
                    break
            else:
                raise RuntimeError("❌ 모든 API 키가 요청 제한에 도달했습니다.")
        
        # 요청 실행
        return await self._execute_with_retry(prompt, api_key, **kwargs)
    
    def create_chain(self, prompt_template: str) -> LLMChain:
        """
        Langchain Chain 생성
        
        Args:
            prompt_template: 프롬프트 템플릿
            
        Returns:
            LLMChain 인스턴스
        """
        # 현재 활성 API 키 선택
        api_key = self._get_next_api_key()
        llm = self.llm_instances[api_key]
        
        # 프롬프트 템플릿 생성
        prompt = PromptTemplate.from_template(prompt_template)
        
        # 체인 생성
        chain = LLMChain(
            llm=llm,
            prompt=prompt,
            output_parser=StrOutputParser()
        )
        
        return chain
    
    def create_runnable_chain(self, prompt_template: str):
        """
        Langchain Runnable Chain 생성
        
        Args:
            prompt_template: 프롬프트 템플릿
            
        Returns:
            Runnable Chain
        """
        # 현재 활성 API 키 선택
        api_key = self._get_next_api_key()
        llm = self.llm_instances[api_key]
        
        # 프롬프트 템플릿 생성
        prompt = PromptTemplate.from_template(prompt_template)
        
        # Runnable Chain 생성
        chain = (
            {"input": RunnablePassthrough()}
            | prompt
            | llm
            | StrOutputParser()
        )
        
        return chain
    
    def get_metrics(self) -> Dict[str, Any]:
        """성능 메트릭 반환"""
        # 메트릭 업데이트
        self._update_metrics()
        
        return {
            "total_requests": self.metrics.total_requests,
            "successful_requests": self.metrics.successful_requests,
            "failed_requests": self.metrics.failed_requests,
            "success_rate": self.metrics.success_rate,
            "average_response_time": self.metrics.average_response_time,
            "requests_per_minute": self.metrics.requests_per_minute,
            "api_key_status": {
                key[:10] + "...": {
                    "is_active": status.is_active,
                    "success_rate": status.success_rate,
                    "request_count": status.request_count,
                    "error_count": status.error_count
                }
                for key, status in self.api_key_status.items()
            }
        }
    
    def _update_metrics(self):
        """메트릭 업데이트"""
        current_time = time.time()
        
        # 최근 1분간 요청 필터링
        recent_requests = [
            req for req in self.request_history
            if current_time - req.get('timestamp', 0) < 60
        ]
        
        # 메트릭 계산
        self.metrics.total_requests = len(self.request_history)
        self.metrics.successful_requests = sum(
            1 for req in self.request_history if req.get('success', False)
        )
        self.metrics.failed_requests = self.metrics.total_requests - self.metrics.successful_requests
        self.metrics.requests_per_minute = len(recent_requests)
        
        # 평균 응답 시간 계산
        successful_requests = [
            req for req in self.request_history
            if req.get('success', False) and 'execution_time' in req
        ]
        
        if successful_requests:
            self.metrics.average_response_time = sum(
                req['execution_time'] for req in successful_requests
            ) / len(successful_requests)
    
    def reset_api_key_status(self):
        """API 키 상태 초기화 (복구)"""
        for status in self.api_key_status.values():
            status.is_active = True
            status.error_count = 0
        
        logger.info("🔄 API 키 상태 초기화 완료")
    
    async def health_check(self) -> Dict[str, Any]:
        """시스템 상태 확인"""
        health_status = {
            "status": "healthy",
            "active_keys": 0,
            "total_keys": len(self.api_keys),
            "key_details": {}
        }
        
        for key, status in self.api_key_status.items():
            key_id = key[:10] + "..."
            
            if status.is_active:
                health_status["active_keys"] += 1
                
                # 간단한 테스트 요청
                try:
                    await self._execute_with_retry("테스트", key)
                    health_status["key_details"][key_id] = "healthy"
                except Exception as e:
                    health_status["key_details"][key_id] = f"error: {str(e)}"
                    status.is_active = False
            else:
                health_status["key_details"][key_id] = "inactive"
        
        # 전체 상태 결정
        if health_status["active_keys"] == 0:
            health_status["status"] = "critical"
        elif health_status["active_keys"] < health_status["total_keys"] / 2:
            health_status["status"] = "warning"
        
        return health_status


# 전역 클라이언트 인스턴스
_global_client: Optional[GeminiClient] = None


def get_gemini_client() -> GeminiClient:
    """전역 Gemini 클라이언트 인스턴스 반환"""
    global _global_client
    
    if _global_client is None:
        _global_client = GeminiClient()
    
    return _global_client


# 편의 함수들
async def generate_content(prompt: str, **kwargs) -> str:
    """편의 함수: 컨텐츠 생성"""
    client = get_gemini_client()
    return await client.generate_content(prompt, **kwargs)


def create_chain(prompt_template: str) -> LLMChain:
    """편의 함수: Chain 생성"""
    client = get_gemini_client()
    return client.create_chain(prompt_template)


def create_runnable_chain(prompt_template: str):
    """편의 함수: Runnable Chain 생성"""
    client = get_gemini_client()
    return client.create_runnable_chain(prompt_template) 