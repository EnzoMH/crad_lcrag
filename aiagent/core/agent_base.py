"""
🧠 BaseAgent - 모든 에이전트의 기본 클래스

Langchain 기반 AI 에이전트 시스템의 기본 클래스
- 공통 AI 기능 제공
- 성능 추적 및 모니터링
- 에러 처리 및 재시도 로직
- 설정 관리
"""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from enum import Enum

from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser, PydanticOutputParser
from langchain.chains import LLMChain
from pydantic import BaseModel, Field

from loguru import logger

from ..utils.gemini_client import GeminiClient, ModelType
from ..utils.rate_limiter import RateLimiter, RateLimitConfig


class AgentStatus(Enum):
    """에이전트 상태"""
    IDLE = "idle"
    PROCESSING = "processing"
    ERROR = "error"
    COMPLETED = "completed"


@dataclass
class AgentConfig:
    """에이전트 설정"""
    name: str
    model_type: ModelType = ModelType.GEMINI_1_5_FLASH
    temperature: float = 0.7
    max_tokens: int = 1000
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: float = 30.0
    enable_monitoring: bool = True
    debug_mode: bool = False
    
    # 성능 설정
    batch_size: int = 10
    max_concurrent: int = 3
    
    # 요청 제한 설정
    rate_limit_config: RateLimitConfig = field(default_factory=RateLimitConfig)


@dataclass
class AgentMetrics:
    """에이전트 메트릭"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_processing_time: float = 0.0
    average_processing_time: float = 0.0
    last_request_time: Optional[float] = None
    
    @property
    def success_rate(self) -> float:
        return self.successful_requests / self.total_requests if self.total_requests > 0 else 0.0


class AgentResult(BaseModel):
    """에이전트 처리 결과"""
    success: bool = Field(description="처리 성공 여부")
    data: Optional[Dict[str, Any]] = Field(default=None, description="처리 결과 데이터")
    error_message: Optional[str] = Field(default=None, description="에러 메시지")
    processing_time: float = Field(description="처리 시간 (초)")
    agent_name: str = Field(description="에이전트 이름")
    timestamp: float = Field(default_factory=time.time, description="처리 시간")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "data": {"extracted_info": "연락처 정보"},
                "error_message": None,
                "processing_time": 2.5,
                "agent_name": "ContactAgent",
                "timestamp": 1640995200.0
            }
        }


class BaseAgent(ABC):
    """
    🧠 기본 에이전트 클래스
    
    모든 전문 에이전트의 기본 클래스
    - Langchain 기반 AI 기능
    - 성능 추적 및 모니터링
    - 에러 처리 및 재시도
    - 설정 관리
    """
    
    def __init__(self, config: AgentConfig):
        """
        BaseAgent 초기화
        
        Args:
            config: 에이전트 설정
        """
        self.config = config
        self.status = AgentStatus.IDLE
        self.metrics = AgentMetrics()
        
        # AI 클라이언트 초기화
        self.gemini_client = GeminiClient(
            model_type=config.model_type,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            max_retries=config.max_retries,
            retry_delay=config.retry_delay
        )
        
        # 요청 제한 관리자
        self.rate_limiter = RateLimiter(config.rate_limit_config)
        
        # 에이전트별 프롬프트 템플릿
        self.prompt_templates = self._initialize_prompts()
        
        # 체인 캐시
        self.chain_cache: Dict[str, LLMChain] = {}
        
        logger.info(f"🧠 {self.config.name} 에이전트 초기화 완료")
    
    @abstractmethod
    def _initialize_prompts(self) -> Dict[str, str]:
        """에이전트별 프롬프트 템플릿 초기화"""
        pass
    
    @abstractmethod
    async def _process_core_logic(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """핵심 처리 로직 (각 에이전트에서 구현)"""
        pass
    
    def _get_or_create_chain(self, prompt_key: str) -> LLMChain:
        """프롬프트 키에 해당하는 체인 반환 (캐시 사용)"""
        if prompt_key not in self.chain_cache:
            if prompt_key not in self.prompt_templates:
                raise ValueError(f"❌ 프롬프트 키 '{prompt_key}'를 찾을 수 없습니다.")
            
            template = self.prompt_templates[prompt_key]
            self.chain_cache[prompt_key] = self.gemini_client.create_chain(template)
            
            logger.debug(f"🔧 체인 생성: {self.config.name}.{prompt_key}")
        
        return self.chain_cache[prompt_key]
    
    async def _execute_with_monitoring(
        self,
        func,
        *args,
        **kwargs
    ) -> AgentResult:
        """모니터링과 함께 함수 실행"""
        start_time = time.time()
        self.status = AgentStatus.PROCESSING
        
        try:
            # 핵심 로직 실행
            result_data = await func(*args, **kwargs)
            
            # 성공 메트릭 업데이트
            processing_time = time.time() - start_time
            self._update_success_metrics(processing_time)
            
            self.status = AgentStatus.COMPLETED
            
            return AgentResult(
                success=True,
                data=result_data,
                processing_time=processing_time,
                agent_name=self.config.name
            )
            
        except Exception as e:
            # 실패 메트릭 업데이트
            processing_time = time.time() - start_time
            self._update_error_metrics(processing_time)
            
            self.status = AgentStatus.ERROR
            
            error_message = f"{self.config.name} 처리 실패: {str(e)}"
            logger.error(error_message)
            
            return AgentResult(
                success=False,
                error_message=error_message,
                processing_time=processing_time,
                agent_name=self.config.name
            )
        finally:
            if self.status != AgentStatus.ERROR:
                self.status = AgentStatus.IDLE
    
    def _update_success_metrics(self, processing_time: float):
        """성공 메트릭 업데이트"""
        self.metrics.total_requests += 1
        self.metrics.successful_requests += 1
        self.metrics.total_processing_time += processing_time
        self.metrics.average_processing_time = (
            self.metrics.total_processing_time / self.metrics.total_requests
        )
        self.metrics.last_request_time = time.time()
    
    def _update_error_metrics(self, processing_time: float):
        """에러 메트릭 업데이트"""
        self.metrics.total_requests += 1
        self.metrics.failed_requests += 1
        self.metrics.total_processing_time += processing_time
        self.metrics.average_processing_time = (
            self.metrics.total_processing_time / self.metrics.total_requests
        )
        self.metrics.last_request_time = time.time()
    
    async def process(self, data: Dict[str, Any]) -> AgentResult:
        """
        데이터 처리 (공통 인터페이스)
        
        Args:
            data: 처리할 데이터
            
        Returns:
            처리 결과
        """
        if self.config.debug_mode:
            logger.debug(f"🔍 {self.config.name} 처리 시작: {data}")
        
        # 입력 검증
        if not self._validate_input(data):
            return AgentResult(
                success=False,
                error_message="입력 데이터 검증 실패",
                processing_time=0.0,
                agent_name=self.config.name
            )
        
        # 모니터링과 함께 처리 실행
        return await self._execute_with_monitoring(
            self._process_core_logic,
            data
        )
    
    def _validate_input(self, data: Dict[str, Any]) -> bool:
        """입력 데이터 검증"""
        if not isinstance(data, dict):
            logger.error(f"❌ {self.config.name}: 입력 데이터가 딕셔너리가 아닙니다.")
            return False
        
        return True
    
    async def process_batch(
        self,
        data_list: List[Dict[str, Any]],
        max_concurrent: Optional[int] = None
    ) -> List[AgentResult]:
        """
        배치 처리
        
        Args:
            data_list: 처리할 데이터 리스트
            max_concurrent: 최대 동시 처리 수
            
        Returns:
            처리 결과 리스트
        """
        max_concurrent = max_concurrent or self.config.max_concurrent
        
        logger.info(f"🔄 {self.config.name} 배치 처리 시작: {len(data_list)}개 항목")
        
        # 세마포어를 사용한 동시 처리 제한
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_semaphore(data):
            async with semaphore:
                return await self.process(data)
        
        # 배치 처리 실행
        tasks = [process_with_semaphore(data) for data in data_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 예외 처리
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(AgentResult(
                    success=False,
                    error_message=f"배치 처리 예외: {str(result)}",
                    processing_time=0.0,
                    agent_name=self.config.name
                ))
            else:
                processed_results.append(result)
        
        # 배치 처리 결과 로깅
        success_count = sum(1 for r in processed_results if r.success)
        logger.info(f"✅ {self.config.name} 배치 처리 완료: {success_count}/{len(data_list)} 성공")
        
        return processed_results
    
    async def generate_ai_response(
        self,
        prompt_key: str,
        variables: Dict[str, Any]
    ) -> str:
        """
        AI 응답 생성
        
        Args:
            prompt_key: 프롬프트 키
            variables: 템플릿 변수
            
        Returns:
            AI 응답
        """
        chain = self._get_or_create_chain(prompt_key)
        
        try:
            response = await chain.arun(**variables)
            
            if self.config.debug_mode:
                logger.debug(f"🤖 {self.config.name} AI 응답: {response[:100]}...")
            
            return response
            
        except Exception as e:
            logger.error(f"❌ {self.config.name} AI 응답 생성 실패: {e}")
            raise
    
    def get_metrics(self) -> Dict[str, Any]:
        """에이전트 메트릭 반환"""
        return {
            "agent_name": self.config.name,
            "status": self.status.value,
            "metrics": {
                "total_requests": self.metrics.total_requests,
                "successful_requests": self.metrics.successful_requests,
                "failed_requests": self.metrics.failed_requests,
                "success_rate": self.metrics.success_rate,
                "average_processing_time": self.metrics.average_processing_time,
                "last_request_time": self.metrics.last_request_time
            },
            "gemini_metrics": self.gemini_client.get_metrics(),
            "rate_limiter_stats": self.rate_limiter.get_all_usage_stats()
        }
    
    def reset_metrics(self):
        """메트릭 초기화"""
        self.metrics = AgentMetrics()
        logger.info(f"🔄 {self.config.name} 메트릭 초기화 완료")
    
    async def health_check(self) -> Dict[str, Any]:
        """에이전트 상태 확인"""
        try:
            # 간단한 테스트 실행
            test_data = {"test": "health_check"}
            result = await self.process(test_data)
            
            # Gemini 클라이언트 상태 확인
            gemini_health = await self.gemini_client.health_check()
            
            # 요청 제한 관리자 상태 확인
            rate_limiter_health = await self.rate_limiter.health_check()
            
            # 전체 상태 결정
            is_healthy = (
                result.success and
                gemini_health["status"] in ["healthy", "warning"] and
                rate_limiter_health["status"] in ["healthy", "warning"]
            )
            
            return {
                "agent_name": self.config.name,
                "status": "healthy" if is_healthy else "unhealthy",
                "agent_status": self.status.value,
                "test_result": result.success,
                "gemini_health": gemini_health,
                "rate_limiter_health": rate_limiter_health,
                "metrics": self.get_metrics()
            }
            
        except Exception as e:
            logger.error(f"❌ {self.config.name} 상태 확인 실패: {e}")
            return {
                "agent_name": self.config.name,
                "status": "unhealthy",
                "error": str(e)
            }
    
    def update_config(self, new_config: Dict[str, Any]):
        """설정 업데이트"""
        for key, value in new_config.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                logger.info(f"🔧 {self.config.name} 설정 업데이트: {key} = {value}")
            else:
                logger.warning(f"⚠️ {self.config.name} 알 수 없는 설정: {key}")
    
    def __str__(self) -> str:
        return f"{self.config.name}(status={self.status.value}, requests={self.metrics.total_requests})"
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name='{self.config.name}' status='{self.status.value}'>"


class AgentRegistry:
    """
    🗂️ 에이전트 레지스트리
    
    에이전트 인스턴스 관리 및 검색
    """
    
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        logger.info("🗂️ 에이전트 레지스트리 초기화")
    
    def register(self, agent: BaseAgent):
        """에이전트 등록"""
        self.agents[agent.config.name] = agent
        logger.info(f"📝 에이전트 등록: {agent.config.name}")
    
    def get(self, name: str) -> Optional[BaseAgent]:
        """에이전트 검색"""
        return self.agents.get(name)
    
    def get_all(self) -> Dict[str, BaseAgent]:
        """모든 에이전트 반환"""
        return self.agents.copy()
    
    def remove(self, name: str) -> bool:
        """에이전트 제거"""
        if name in self.agents:
            del self.agents[name]
            logger.info(f"🗑️ 에이전트 제거: {name}")
            return True
        return False
    
    def get_status_summary(self) -> Dict[str, Any]:
        """모든 에이전트 상태 요약"""
        summary = {
            "total_agents": len(self.agents),
            "agents_by_status": {},
            "total_requests": 0,
            "total_success_rate": 0.0
        }
        
        status_counts = {}
        total_requests = 0
        total_success_rate = 0.0
        
        for agent in self.agents.values():
            status = agent.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
            
            total_requests += agent.metrics.total_requests
            total_success_rate += agent.metrics.success_rate
        
        summary["agents_by_status"] = status_counts
        summary["total_requests"] = total_requests
        summary["total_success_rate"] = total_success_rate / len(self.agents) if self.agents else 0.0
        
        return summary


# 전역 에이전트 레지스트리
agent_registry = AgentRegistry() 