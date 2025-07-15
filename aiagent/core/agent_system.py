"""
🎯 AIAgentSystem - 메인 시스템 관리자

AI 에이전트 시스템의 중앙 관리자
- 에이전트 생성 및 관리
- 워크플로우 조정
- 성능 모니터링
- 시스템 상태 관리
"""

import asyncio
import time
from typing import Dict, Any, List, Optional, Type, Union
from dataclasses import dataclass, field
from enum import Enum

from loguru import logger

from .agent_base import BaseAgent, AgentConfig, AgentResult, AgentStatus, agent_registry
from .coordinator import AgentCoordinator, WorkflowTask, WorkflowResult
from ..utils.gemini_client import GeminiClient, ModelType
from ..utils.rate_limiter import RateLimiter, RateLimitConfig


class SystemStatus(Enum):
    """시스템 상태"""
    INITIALIZING = "initializing"
    READY = "ready"
    PROCESSING = "processing"
    ERROR = "error"
    MAINTENANCE = "maintenance"


@dataclass
class SystemConfig:
    """시스템 설정"""
    name: str = "AI Agent System"
    version: str = "2.3.0"
    environment: str = "development"
    debug_mode: bool = False
    
    # 성능 설정
    max_concurrent_agents: int = 10
    default_timeout: float = 30.0
    health_check_interval: float = 60.0
    
    # AI 설정
    default_model_type: ModelType = ModelType.GEMINI_1_5_FLASH
    default_temperature: float = 0.7
    default_max_tokens: int = 1000
    
    # 모니터링 설정
    enable_monitoring: bool = True
    metrics_retention_hours: int = 24
    log_level: str = "INFO"


@dataclass
class SystemMetrics:
    """시스템 메트릭"""
    total_agents: int = 0
    active_agents: int = 0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time: float = 0.0
    system_uptime: float = 0.0
    last_health_check: Optional[float] = None
    
    @property
    def success_rate(self) -> float:
        return self.successful_requests / self.total_requests if self.total_requests > 0 else 0.0


class AIAgentSystem:
    """
    🎯 AI 에이전트 시스템 메인 클래스
    
    Features:
    - 에이전트 생성 및 관리
    - 워크플로우 조정
    - 성능 모니터링
    - 시스템 상태 관리
    - 자동 복구 및 최적화
    """
    
    def __init__(self, config: SystemConfig = None):
        """
        AI 에이전트 시스템 초기화
        
        Args:
            config: 시스템 설정
        """
        self.config = config or SystemConfig()
        self.status = SystemStatus.INITIALIZING
        self.metrics = SystemMetrics()
        self.start_time = time.time()
        
        # 에이전트 관리
        self.agents: Dict[str, BaseAgent] = {}
        self.agent_classes: Dict[str, Type[BaseAgent]] = {}
        
        # 워크플로우 조정자
        self.coordinator = AgentCoordinator()
        
        # 공통 AI 클라이언트
        self.gemini_client = GeminiClient(
            model_type=self.config.default_model_type,
            temperature=self.config.default_temperature,
            max_tokens=self.config.default_max_tokens
        )
        
        # 요청 제한 관리자
        self.rate_limiter = RateLimiter()
        
        # 모니터링 태스크
        self.monitoring_task: Optional[asyncio.Task] = None
        
        # 시스템 초기화 완료
        self.status = SystemStatus.READY
        self.metrics.system_uptime = time.time() - self.start_time
        
        logger.info(f"🎯 AI 에이전트 시스템 초기화 완료 - {self.config.name} v{self.config.version}")
    
    def register_agent_class(self, agent_class: Type[BaseAgent], name: str = None):
        """
        에이전트 클래스 등록
        
        Args:
            agent_class: 에이전트 클래스
            name: 등록할 이름 (기본값: 클래스명)
        """
        class_name = name or agent_class.__name__
        self.agent_classes[class_name] = agent_class
        
        logger.info(f"📝 에이전트 클래스 등록: {class_name}")
    
    def create_agent(
        self,
        agent_type: str,
        agent_name: str,
        config_overrides: Dict[str, Any] = None
    ) -> BaseAgent:
        """
        에이전트 생성
        
        Args:
            agent_type: 에이전트 타입 (등록된 클래스명)
            agent_name: 에이전트 인스턴스 이름
            config_overrides: 설정 오버라이드
            
        Returns:
            생성된 에이전트 인스턴스
        """
        if agent_type not in self.agent_classes:
            raise ValueError(f"❌ 등록되지 않은 에이전트 타입: {agent_type}")
        
        if agent_name in self.agents:
            raise ValueError(f"❌ 이미 존재하는 에이전트 이름: {agent_name}")
        
        # 에이전트 설정 생성
        agent_config = AgentConfig(
            name=agent_name,
            model_type=self.config.default_model_type,
            temperature=self.config.default_temperature,
            max_tokens=self.config.default_max_tokens,
            debug_mode=self.config.debug_mode
        )
        
        # 설정 오버라이드 적용
        if config_overrides:
            for key, value in config_overrides.items():
                if hasattr(agent_config, key):
                    setattr(agent_config, key, value)
        
        # 에이전트 인스턴스 생성
        agent_class = self.agent_classes[agent_type]
        agent = agent_class(agent_config)
        
        # 에이전트 등록
        self.agents[agent_name] = agent
        agent_registry.register(agent)
        
        # 메트릭 업데이트
        self.metrics.total_agents += 1
        self.metrics.active_agents += 1
        
        logger.info(f"🤖 에이전트 생성: {agent_name} ({agent_type})")
        return agent
    
    def get_agent(self, agent_name: str) -> Optional[BaseAgent]:
        """에이전트 검색"""
        return self.agents.get(agent_name)
    
    def remove_agent(self, agent_name: str) -> bool:
        """에이전트 제거"""
        if agent_name in self.agents:
            agent = self.agents[agent_name]
            
            # 에이전트 제거
            del self.agents[agent_name]
            agent_registry.remove(agent_name)
            
            # 메트릭 업데이트
            self.metrics.total_agents -= 1
            if agent.status != AgentStatus.ERROR:
                self.metrics.active_agents -= 1
            
            logger.info(f"🗑️ 에이전트 제거: {agent_name}")
            return True
        
        return False
    
    async def process_single_task(
        self,
        agent_name: str,
        data: Dict[str, Any]
    ) -> AgentResult:
        """
        단일 작업 처리
        
        Args:
            agent_name: 에이전트 이름
            data: 처리할 데이터
            
        Returns:
            처리 결과
        """
        agent = self.get_agent(agent_name)
        if not agent:
            return AgentResult(
                success=False,
                error_message=f"에이전트를 찾을 수 없습니다: {agent_name}",
                processing_time=0.0,
                agent_name=agent_name
            )
        
        # 시스템 상태 확인
        if self.status != SystemStatus.READY:
            return AgentResult(
                success=False,
                error_message=f"시스템이 준비되지 않았습니다: {self.status.value}",
                processing_time=0.0,
                agent_name=agent_name
            )
        
        # 작업 처리
        self.status = SystemStatus.PROCESSING
        
        try:
            result = await agent.process(data)
            
            # 시스템 메트릭 업데이트
            self.metrics.total_requests += 1
            if result.success:
                self.metrics.successful_requests += 1
            else:
                self.metrics.failed_requests += 1
            
            # 평균 응답 시간 업데이트
            self._update_average_response_time(result.processing_time)
            
            return result
            
        finally:
            self.status = SystemStatus.READY
    
    async def process_workflow(
        self,
        workflow_tasks: List[WorkflowTask]
    ) -> WorkflowResult:
        """
        워크플로우 처리
        
        Args:
            workflow_tasks: 워크플로우 작업 목록
            
        Returns:
            워크플로우 결과
        """
        if self.status != SystemStatus.READY:
            return WorkflowResult(
                success=False,
                error_message=f"시스템이 준비되지 않았습니다: {self.status.value}",
                total_processing_time=0.0,
                task_results=[]
            )
        
        self.status = SystemStatus.PROCESSING
        
        try:
            # 워크플로우 실행
            result = await self.coordinator.execute_workflow(workflow_tasks, self.agents)
            
            # 시스템 메트릭 업데이트
            self.metrics.total_requests += len(workflow_tasks)
            for task_result in result.task_results:
                if task_result.success:
                    self.metrics.successful_requests += 1
                else:
                    self.metrics.failed_requests += 1
            
            # 평균 응답 시간 업데이트
            self._update_average_response_time(result.total_processing_time)
            
            return result
            
        finally:
            self.status = SystemStatus.READY
    
    async def process_batch(
        self,
        agent_name: str,
        data_list: List[Dict[str, Any]],
        max_concurrent: Optional[int] = None
    ) -> List[AgentResult]:
        """
        배치 처리
        
        Args:
            agent_name: 에이전트 이름
            data_list: 처리할 데이터 리스트
            max_concurrent: 최대 동시 처리 수
            
        Returns:
            처리 결과 리스트
        """
        agent = self.get_agent(agent_name)
        if not agent:
            return [
                AgentResult(
                    success=False,
                    error_message=f"에이전트를 찾을 수 없습니다: {agent_name}",
                    processing_time=0.0,
                    agent_name=agent_name
                )
                for _ in data_list
            ]
        
        max_concurrent = max_concurrent or self.config.max_concurrent_agents
        
        # 배치 처리 실행
        results = await agent.process_batch(data_list, max_concurrent)
        
        # 시스템 메트릭 업데이트
        self.metrics.total_requests += len(results)
        for result in results:
            if result.success:
                self.metrics.successful_requests += 1
            else:
                self.metrics.failed_requests += 1
            
            self._update_average_response_time(result.processing_time)
        
        return results
    
    def _update_average_response_time(self, processing_time: float):
        """평균 응답 시간 업데이트"""
        if self.metrics.total_requests == 1:
            self.metrics.average_response_time = processing_time
        else:
            # 지수 이동 평균 사용
            alpha = 0.1
            self.metrics.average_response_time = (
                alpha * processing_time +
                (1 - alpha) * self.metrics.average_response_time
            )
    
    async def health_check(self) -> Dict[str, Any]:
        """시스템 상태 확인"""
        try:
            # 시스템 기본 정보
            health_info = {
                "system_name": self.config.name,
                "version": self.config.version,
                "status": self.status.value,
                "uptime": time.time() - self.start_time,
                "timestamp": time.time()
            }
            
            # 에이전트 상태 확인
            agent_health = {}
            healthy_agents = 0
            
            for agent_name, agent in self.agents.items():
                agent_status = await agent.health_check()
                agent_health[agent_name] = agent_status
                
                if agent_status.get("status") == "healthy":
                    healthy_agents += 1
            
            # Gemini 클라이언트 상태 확인
            gemini_health = await self.gemini_client.health_check()
            
            # 요청 제한 관리자 상태 확인
            rate_limiter_health = await self.rate_limiter.health_check()
            
            # 전체 상태 결정
            overall_health = "healthy"
            if healthy_agents == 0 and len(self.agents) > 0:
                overall_health = "critical"
            elif healthy_agents < len(self.agents) * 0.7:
                overall_health = "warning"
            elif gemini_health["status"] == "critical":
                overall_health = "critical"
            elif rate_limiter_health["status"] == "critical":
                overall_health = "critical"
            
            health_info.update({
                "overall_health": overall_health,
                "agents": {
                    "total": len(self.agents),
                    "healthy": healthy_agents,
                    "details": agent_health
                },
                "gemini_client": gemini_health,
                "rate_limiter": rate_limiter_health,
                "metrics": self.get_metrics()
            })
            
            # 마지막 상태 확인 시간 업데이트
            self.metrics.last_health_check = time.time()
            
            return health_info
            
        except Exception as e:
            logger.error(f"❌ 시스템 상태 확인 실패: {e}")
            return {
                "system_name": self.config.name,
                "status": "error",
                "error": str(e),
                "timestamp": time.time()
            }
    
    def get_metrics(self) -> Dict[str, Any]:
        """시스템 메트릭 반환"""
        # 시스템 가동 시간 업데이트
        self.metrics.system_uptime = time.time() - self.start_time
        
        # 활성 에이전트 수 업데이트
        self.metrics.active_agents = sum(
            1 for agent in self.agents.values()
            if agent.status != AgentStatus.ERROR
        )
        
        return {
            "system": {
                "name": self.config.name,
                "version": self.config.version,
                "status": self.status.value,
                "uptime": self.metrics.system_uptime,
                "environment": self.config.environment
            },
            "agents": {
                "total": self.metrics.total_agents,
                "active": self.metrics.active_agents,
                "registered_classes": list(self.agent_classes.keys())
            },
            "performance": {
                "total_requests": self.metrics.total_requests,
                "successful_requests": self.metrics.successful_requests,
                "failed_requests": self.metrics.failed_requests,
                "success_rate": self.metrics.success_rate,
                "average_response_time": self.metrics.average_response_time
            },
            "last_health_check": self.metrics.last_health_check
        }
    
    def get_agent_metrics(self) -> Dict[str, Any]:
        """모든 에이전트 메트릭 반환"""
        return {
            agent_name: agent.get_metrics()
            for agent_name, agent in self.agents.items()
        }
    
    async def optimize_performance(self):
        """성능 최적화"""
        logger.info("🔧 시스템 성능 최적화 시작")
        
        # 에이전트별 성능 분석
        for agent_name, agent in self.agents.items():
            metrics = agent.get_metrics()
            
            # 성능이 낮은 에이전트 식별
            if metrics["metrics"]["success_rate"] < 0.8:
                logger.warning(f"⚠️ 성능 저하 에이전트: {agent_name}")
                
                # 에이전트 재시작 또는 설정 조정
                await self._restart_agent(agent_name)
        
        # Gemini API 키 상태 초기화
        self.gemini_client.reset_api_key_status()
        
        # 요청 제한 초기화
        self.rate_limiter.reset_limits()
        
        logger.info("✅ 시스템 성능 최적화 완료")
    
    async def _restart_agent(self, agent_name: str):
        """에이전트 재시작"""
        agent = self.agents.get(agent_name)
        if not agent:
            return
        
        logger.info(f"🔄 에이전트 재시작: {agent_name}")
        
        # 에이전트 메트릭 초기화
        agent.reset_metrics()
        
        # 체인 캐시 초기화
        agent.chain_cache.clear()
        
        # 상태 초기화
        agent.status = AgentStatus.IDLE
    
    async def start_monitoring(self):
        """모니터링 시작"""
        if self.monitoring_task and not self.monitoring_task.done():
            logger.warning("⚠️ 모니터링이 이미 실행 중입니다.")
            return
        
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("📊 시스템 모니터링 시작")
    
    async def stop_monitoring(self):
        """모니터링 중지"""
        if self.monitoring_task and not self.monitoring_task.done():
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
            
            logger.info("📊 시스템 모니터링 중지")
    
    async def _monitoring_loop(self):
        """모니터링 루프"""
        while True:
            try:
                # 상태 확인
                health_info = await self.health_check()
                
                # 성능 최적화 필요 시 실행
                if health_info.get("overall_health") == "warning":
                    await self.optimize_performance()
                
                # 다음 확인까지 대기
                await asyncio.sleep(self.config.health_check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ 모니터링 루프 오류: {e}")
                await asyncio.sleep(10)  # 오류 발생 시 10초 대기
    
    async def shutdown(self):
        """시스템 종료"""
        logger.info("🛑 AI 에이전트 시스템 종료 시작")
        
        # 모니터링 중지
        await self.stop_monitoring()
        
        # 모든 에이전트 제거
        agent_names = list(self.agents.keys())
        for agent_name in agent_names:
            self.remove_agent(agent_name)
        
        # 상태 업데이트
        self.status = SystemStatus.MAINTENANCE
        
        logger.info("✅ AI 에이전트 시스템 종료 완료")
    
    def __str__(self) -> str:
        return f"AIAgentSystem(status={self.status.value}, agents={len(self.agents)})"
    
    def __repr__(self) -> str:
        return f"<AIAgentSystem name='{self.config.name}' status='{self.status.value}' agents={len(self.agents)}>"


# 전역 시스템 인스턴스
_global_system: Optional[AIAgentSystem] = None


def get_agent_system() -> AIAgentSystem:
    """전역 AI 에이전트 시스템 인스턴스 반환"""
    global _global_system
    
    if _global_system is None:
        _global_system = AIAgentSystem()
    
    return _global_system


# 편의 함수들
async def create_agent(
    agent_type: str,
    agent_name: str,
    config_overrides: Dict[str, Any] = None
) -> BaseAgent:
    """편의 함수: 에이전트 생성"""
    system = get_agent_system()
    return system.create_agent(agent_type, agent_name, config_overrides)


async def process_task(
    agent_name: str,
    data: Dict[str, Any]
) -> AgentResult:
    """편의 함수: 단일 작업 처리"""
    system = get_agent_system()
    return await system.process_single_task(agent_name, data)


async def system_health_check() -> Dict[str, Any]:
    """편의 함수: 시스템 상태 확인"""
    system = get_agent_system()
    return await system.health_check() 