"""
🔗 모니터링 통합 시스템

Langchain 기반 AI 에이전트 시스템의 모든 컴포넌트를 통합 모니터링하는 시스템
- 에이전트 시스템과 모니터링 연동
- 체인 매니저와 성능 추적 연동  
- 워크플로우 조정자와 효율성 모니터링 연동
- 실시간 성능 데이터 수집 및 분석
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass

from loguru import logger

from .performance_monitor import PerformanceMonitor, MetricType, AlertLevel
from .agent_system import AIAgentSystem, SystemStatus
from .chain_manager import ChainManager
from .chain_service import ChainService
from .coordinator import AgentCoordinator, WorkflowExecution
from .agent_base import BaseAgent, AgentResult


@dataclass
class MonitoringConfig:
    """모니터링 통합 설정"""
    enable_agent_monitoring: bool = True
    enable_chain_monitoring: bool = True
    enable_workflow_monitoring: bool = True
    enable_system_monitoring: bool = True
    
    # 수집 간격 (초)
    agent_metrics_interval: float = 30.0
    chain_metrics_interval: float = 15.0
    system_metrics_interval: float = 60.0
    
    # 성능 임계값
    agent_response_time_threshold: float = 10.0
    chain_execution_threshold: float = 30.0
    system_cpu_threshold: float = 80.0
    system_memory_threshold: float = 85.0


class MonitoringIntegration:
    """
    🔗 모니터링 통합 시스템
    
    기능:
    - 전체 시스템 컴포넌트 모니터링 통합
    - 실시간 성능 데이터 수집
    - 통합 성능 분석 및 최적화
    - 자동화된 성능 튜닝
    """
    
    def __init__(
        self,
        agent_system: AIAgentSystem,
        chain_manager: ChainManager,
        chain_service: ChainService,
        coordinator: AgentCoordinator,
        config: MonitoringConfig = None
    ):
        """
        모니터링 통합 시스템 초기화
        
        Args:
            agent_system: AI 에이전트 시스템
            chain_manager: 체인 매니저
            chain_service: 체인 서비스
            coordinator: 워크플로우 조정자
            config: 모니터링 설정
        """
        self.config = config or MonitoringConfig()
        
        # 핵심 시스템 컴포넌트
        self.agent_system = agent_system
        self.chain_manager = chain_manager
        self.chain_service = chain_service
        self.coordinator = coordinator
        
        # 성능 모니터
        self.performance_monitor = PerformanceMonitor({
            'monitoring_interval': self.config.system_metrics_interval
        })
        
        # 모니터링 태스크들
        self.monitoring_tasks: List[asyncio.Task] = []
        self.is_monitoring = False
        
        # 성능 훅 등록
        self._register_performance_hooks()
        
        logger.info("🔗 모니터링 통합 시스템 초기화 완료")

    def _register_performance_hooks(self):
        """성능 모니터링 훅 등록"""
        
        # 에이전트 시스템 훅
        self._register_agent_hooks()
        
        # 체인 매니저 훅
        self._register_chain_hooks()
        
        # 워크플로우 조정자 훅
        self._register_workflow_hooks()

    def _register_agent_hooks(self):
        """에이전트 시스템 성능 훅 등록"""
        
        # 원본 process_single_task 메서드 백업
        original_process_single_task = self.agent_system.process_single_task
        
        async def monitored_process_single_task(
            agent_name: str,
            data: Dict[str, Any]
        ) -> AgentResult:
            """모니터링이 적용된 단일 작업 처리"""
            start_time = time.time()
            
            try:
                # 원본 메서드 실행
                result = await original_process_single_task(agent_name, data)
                
                # 성능 메트릭 기록
                execution_time = time.time() - start_time
                self.performance_monitor.record_agent_metric(
                    agent_name=agent_name,
                    metric_name="execution_time",
                    value=execution_time,
                    unit="seconds",
                    metadata={
                        'success': result.success,
                        'data_size': len(str(data))
                    }
                )
                
                # 성공률 메트릭
                self.performance_monitor.record_agent_metric(
                    agent_name=agent_name,
                    metric_name="success_rate",
                    value=1.0 if result.success else 0.0,
                    unit="ratio"
                )
                
                # 임계값 확인
                if execution_time > self.config.agent_response_time_threshold:
                    logger.warning(
                        f"⚠️ 에이전트 {agent_name} 응답 시간 초과: {execution_time:.2f}초"
                    )
                
                return result
                
            except Exception as e:
                execution_time = time.time() - start_time
                
                # 오류 메트릭 기록
                self.performance_monitor.record_agent_metric(
                    agent_name=agent_name,
                    metric_name="error_count",
                    value=1.0,
                    unit="count",
                    metadata={'error_type': type(e).__name__}
                )
                
                raise
        
        # 메서드 교체
        self.agent_system.process_single_task = monitored_process_single_task

    def _register_chain_hooks(self):
        """체인 매니저 성능 훅 등록"""
        
        # 체인 서비스의 실행 메서드에 훅 추가
        if hasattr(self.chain_service, 'execute_chain'):
            original_execute_chain = self.chain_service.execute_chain
            
            async def monitored_execute_chain(
                chain_name: str,
                input_data: Dict[str, Any],
                context: Optional[Dict[str, Any]] = None
            ):
                """모니터링이 적용된 체인 실행"""
                start_time = time.time()
                
                try:
                    # 원본 메서드 실행
                    result = await original_execute_chain(chain_name, input_data, context)
                    
                    # 성능 메트릭 기록
                    execution_time = time.time() - start_time
                    self.performance_monitor.record_chain_metric(
                        chain_name=chain_name,
                        execution_result=result,
                        execution_time=execution_time
                    )
                    
                    # 임계값 확인
                    if execution_time > self.config.chain_execution_threshold:
                        logger.warning(
                            f"⚠️ 체인 {chain_name} 실행 시간 초과: {execution_time:.2f}초"
                        )
                    
                    return result
                    
                except Exception as e:
                    execution_time = time.time() - start_time
                    
                    # 오류 메트릭 기록
                    self.performance_monitor.record_chain_metric(
                        chain_name=chain_name,
                        execution_result=None,
                        execution_time=execution_time
                    )
                    
                    raise
            
            # 메서드 교체
            self.chain_service.execute_chain = monitored_execute_chain

    def _register_workflow_hooks(self):
        """워크플로우 조정자 성능 훅 등록"""
        
        # 워크플로우 실행 메서드에 훅 추가
        if hasattr(self.coordinator, 'execute_workflow'):
            original_execute_workflow = self.coordinator.execute_workflow
            
            async def monitored_execute_workflow(
                workflow_tasks,
                agents_dict
            ):
                """모니터링이 적용된 워크플로우 실행"""
                start_time = time.time()
                
                try:
                    # 원본 메서드 실행
                    result = await original_execute_workflow(workflow_tasks, agents_dict)
                    
                    # 워크플로우 성능 메트릭 기록
                    execution_time = time.time() - start_time
                    
                    self.performance_monitor.record_agent_metric(
                        agent_name="workflow_coordinator",
                        metric_name="workflow_execution_time",
                        value=execution_time,
                        unit="seconds",
                        metadata={
                            'task_count': len(workflow_tasks),
                            'success': result.success,
                            'completed_tasks': result.completed_tasks if hasattr(result, 'completed_tasks') else 0
                        }
                    )
                    
                    # 워크플로우 효율성 메트릭
                    if hasattr(result, 'completed_tasks') and hasattr(result, 'total_tasks'):
                        efficiency = result.completed_tasks / result.total_tasks if result.total_tasks > 0 else 0
                        
                        self.performance_monitor.record_agent_metric(
                            agent_name="workflow_coordinator",
                            metric_name="workflow_efficiency",
                            value=efficiency,
                            unit="ratio"
                        )
                    
                    return result
                    
                except Exception as e:
                    execution_time = time.time() - start_time
                    
                    # 오류 메트릭 기록
                    self.performance_monitor.record_agent_metric(
                        agent_name="workflow_coordinator",
                        metric_name="workflow_error_count",
                        value=1.0,
                        unit="count",
                        metadata={'error_type': type(e).__name__}
                    )
                    
                    raise
            
            # 메서드 교체
            self.coordinator.execute_workflow = monitored_execute_workflow

    async def start_integrated_monitoring(self):
        """통합 모니터링 시작"""
        if self.is_monitoring:
            logger.warning("⚠️ 통합 모니터링이 이미 실행 중입니다")
            return
        
        self.is_monitoring = True
        
        # 기본 성능 모니터 시작
        await self.performance_monitor.start_monitoring()
        
        # 추가 모니터링 태스크 시작
        if self.config.enable_agent_monitoring:
            task = asyncio.create_task(self._agent_monitoring_loop())
            self.monitoring_tasks.append(task)
        
        if self.config.enable_chain_monitoring:
            task = asyncio.create_task(self._chain_monitoring_loop())
            self.monitoring_tasks.append(task)
        
        if self.config.enable_workflow_monitoring:
            task = asyncio.create_task(self._workflow_monitoring_loop())
            self.monitoring_tasks.append(task)
        
        logger.info("📊 통합 모니터링 시작 완료")

    async def stop_integrated_monitoring(self):
        """통합 모니터링 중지"""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        
        # 기본 성능 모니터 중지
        await self.performance_monitor.stop_monitoring()
        
        # 추가 모니터링 태스크 중지
        for task in self.monitoring_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        self.monitoring_tasks.clear()
        
        logger.info("📊 통합 모니터링 중지 완료")

    async def _agent_monitoring_loop(self):
        """에이전트 모니터링 루프"""
        while self.is_monitoring:
            try:
                # 에이전트 시스템 메트릭 수집
                system_metrics = self.agent_system.get_metrics()
                
                # 시스템 상태 메트릭 기록
                self.performance_monitor.record_agent_metric(
                    agent_name="agent_system",
                    metric_name="total_requests",
                    value=system_metrics['performance']['total_requests'],
                    unit="count"
                )
                
                self.performance_monitor.record_agent_metric(
                    agent_name="agent_system",
                    metric_name="success_rate",
                    value=system_metrics['performance']['success_rate'] * 100,
                    unit="%"
                )
                
                # 개별 에이전트 메트릭 수집
                agent_metrics = self.agent_system.get_agent_metrics()
                for agent_name, metrics in agent_metrics.items():
                    if 'metrics' in metrics:
                        agent_data = metrics['metrics']
                        
                        self.performance_monitor.record_agent_metric(
                            agent_name=agent_name,
                            metric_name="total_requests",
                            value=agent_data.get('total_requests', 0),
                            unit="count"
                        )
                        
                        self.performance_monitor.record_agent_metric(
                            agent_name=agent_name,
                            metric_name="success_rate",
                            value=agent_data.get('success_rate', 0) * 100,
                            unit="%"
                        )
                
                await asyncio.sleep(self.config.agent_metrics_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ 에이전트 모니터링 루프 오류: {e}")
                await asyncio.sleep(10)

    async def _chain_monitoring_loop(self):
        """체인 모니터링 루프"""
        while self.is_monitoring:
            try:
                # 체인 매니저 통계 수집
                if hasattr(self.chain_manager, 'get_execution_stats'):
                    chain_stats = self.chain_manager.get_execution_stats()
                    
                    for chain_name, stats in chain_stats.items():
                        self.performance_monitor.record_chain_metric(
                            chain_name=chain_name,
                            execution_result=stats,
                            execution_time=stats.get('average_execution_time', 0)
                        )
                
                # 체인 서비스 통계 수집
                if hasattr(self.chain_service, 'get_service_stats'):
                    service_stats = self.chain_service.get_service_stats()
                    
                    self.performance_monitor.record_agent_metric(
                        agent_name="chain_service",
                        metric_name="active_executions",
                        value=service_stats.get('active_executions', 0),
                        unit="count"
                    )
                
                await asyncio.sleep(self.config.chain_metrics_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ 체인 모니터링 루프 오류: {e}")
                await asyncio.sleep(10)

    async def _workflow_monitoring_loop(self):
        """워크플로우 모니터링 루프"""
        while self.is_monitoring:
            try:
                # 워크플로우 조정자 통계 수집
                if hasattr(self.coordinator, 'get_execution_stats'):
                    workflow_stats = self.coordinator.get_execution_stats()
                    
                    self.performance_monitor.record_agent_metric(
                        agent_name="workflow_coordinator",
                        metric_name="total_workflows",
                        value=workflow_stats.get('total_workflows', 0),
                        unit="count"
                    )
                    
                    self.performance_monitor.record_agent_metric(
                        agent_name="workflow_coordinator",
                        metric_name="active_workflows",
                        value=workflow_stats.get('active_workflows', 0),
                        unit="count"
                    )
                
                await asyncio.sleep(self.config.agent_metrics_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ 워크플로우 모니터링 루프 오류: {e}")
                await asyncio.sleep(10)

    async def get_integrated_report(
        self,
        time_range: str = "1hour"
    ) -> Dict[str, Any]:
        """통합 성능 리포트 생성"""
        
        # 기본 성능 리포트
        base_report = await self.performance_monitor.get_performance_report(time_range)
        
        # 시스템별 추가 정보
        agent_system_info = {
            "system_status": self.agent_system.status.value,
            "registered_agents": len(self.agent_system.agents),
            "system_metrics": self.agent_system.get_metrics()
        }
        
        chain_system_info = {
            "registered_chains": len(self.chain_manager.chains) if hasattr(self.chain_manager, 'chains') else 0,
            "available_chain_types": len(self.chain_manager.chain_types) if hasattr(self.chain_manager, 'chain_types') else 0
        }
        
        workflow_system_info = {
            "workflow_definitions": len(self.coordinator.workflow_definitions) if hasattr(self.coordinator, 'workflow_definitions') else 0,
            "execution_history": len(self.coordinator.execution_history) if hasattr(self.coordinator, 'execution_history') else 0
        }
        
        # 통합 리포트 구성
        integrated_report = {
            **base_report,
            "system_integration": {
                "agent_system": agent_system_info,
                "chain_system": chain_system_info,
                "workflow_system": workflow_system_info
            },
            "monitoring_config": {
                "agent_monitoring": self.config.enable_agent_monitoring,
                "chain_monitoring": self.config.enable_chain_monitoring,
                "workflow_monitoring": self.config.enable_workflow_monitoring,
                "system_monitoring": self.config.enable_system_monitoring
            }
        }
        
        return integrated_report

    async def optimize_integrated_performance(self):
        """통합 성능 최적화"""
        logger.info("🔧 통합 성능 최적화 시작")
        
        try:
            # 1. 에이전트 시스템 최적화
            if hasattr(self.agent_system, 'optimize_performance'):
                await self.agent_system.optimize_performance()
            
            # 2. 체인 캐시 정리
            if hasattr(self.chain_manager, 'clear_cache'):
                self.chain_manager.clear_cache()
            
            # 3. 워크플로우 히스토리 정리
            if hasattr(self.coordinator, 'cleanup_history'):
                self.coordinator.cleanup_history()
            
            # 4. 성능 모니터 데이터 정리
            self.performance_monitor.clear_old_data(hours=24)
            
            logger.info("✅ 통합 성능 최적화 완료")
            
        except Exception as e:
            logger.error(f"❌ 통합 성능 최적화 실패: {e}")

    def get_monitoring_status(self) -> Dict[str, Any]:
        """모니터링 상태 반환"""
        return {
            "is_monitoring": self.is_monitoring,
            "monitoring_tasks": len(self.monitoring_tasks),
            "performance_monitor_status": self.performance_monitor.get_current_status(),
            "config": {
                "agent_monitoring": self.config.enable_agent_monitoring,
                "chain_monitoring": self.config.enable_chain_monitoring,
                "workflow_monitoring": self.config.enable_workflow_monitoring,
                "system_monitoring": self.config.enable_system_monitoring
            },
            "component_status": {
                "agent_system": self.agent_system.status.value,
                "chain_manager": "active" if hasattr(self.chain_manager, 'chains') else "inactive",
                "coordinator": "active" if hasattr(self.coordinator, 'workflow_definitions') else "inactive"
            }
        } 