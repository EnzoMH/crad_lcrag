"""
🧠 AI 에이전트 관리 서비스

Features:
- 에이전트 라이프사이클 관리
- 작업 스케줄링 및 실행
- 성능 최적화
- 오류 처리 및 복구
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from aiagent.core import AIAgentSystem, BaseAgent
from aiagent.agents import (
    SearchStrategyAgent,
    ContactAgent,
    ValidationAgent,
    OptimizerAgent
)
from aiagent.utils import AgentConfig, GeminiClient

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """작업 우선순위"""
    LOW = 1
    NORMAL = 3
    HIGH = 7
    CRITICAL = 10


class TaskStatus(Enum):
    """작업 상태"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentTask:
    """에이전트 작업 정의"""
    task_id: str
    agent_id: str
    task_type: str
    data: Dict[str, Any]
    priority: TaskPriority
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout: int = 300


@dataclass
class AgentPerformanceMetrics:
    """에이전트 성능 메트릭"""
    agent_id: str
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    average_execution_time: float = 0.0
    success_rate: float = 0.0
    last_activity: Optional[datetime] = None
    uptime: float = 0.0


class AgentService:
    """
    AI 에이전트 관리 서비스
    
    Features:
    - 에이전트 등록/해제/조회
    - 작업 큐 관리
    - 성능 모니터링
    - 자동 복구 및 최적화
    """
    
    def __init__(self, agent_system: AIAgentSystem):
        """
        AgentService 초기화
        
        Args:
            agent_system: AI 에이전트 시스템 인스턴스
        """
        self.agent_system = agent_system
        self.logger = logging.getLogger(__name__)
        
        # 작업 큐 관리
        self.task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.running_tasks: Dict[str, AgentTask] = {}
        self.completed_tasks: Dict[str, AgentTask] = {}
        self.task_history: List[AgentTask] = []
        
        # 성능 메트릭
        self.performance_metrics: Dict[str, AgentPerformanceMetrics] = {}
        
        # 설정
        self.max_concurrent_tasks = 10
        self.task_timeout_default = 300
        self.cleanup_interval = 3600  # 1시간
        self.max_history_size = 1000
        
        # 작업 처리 태스크
        self.worker_tasks: List[asyncio.Task] = []
        self.is_running = False
        
        # 콜백 함수들
        self.task_callbacks: Dict[str, List[Callable]] = {
            'on_task_start': [],
            'on_task_complete': [],
            'on_task_fail': [],
            'on_agent_error': []
        }
    
    async def start_service(self):
        """서비스 시작"""
        try:
            self.is_running = True
            
            # 워커 태스크 시작
            for i in range(self.max_concurrent_tasks):
                worker_task = asyncio.create_task(self._task_worker(f"worker_{i}"))
                self.worker_tasks.append(worker_task)
            
            # 정리 태스크 시작
            cleanup_task = asyncio.create_task(self._cleanup_worker())
            self.worker_tasks.append(cleanup_task)
            
            self.logger.info(f"AgentService 시작됨 - {len(self.worker_tasks)}개 워커")
            
        except Exception as e:
            self.logger.error(f"AgentService 시작 오류: {str(e)}")
            raise
    
    async def stop_service(self):
        """서비스 중지"""
        try:
            self.is_running = False
            
            # 실행 중인 작업들을 기다림
            for task in self.worker_tasks:
                task.cancel()
            
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)
            
            self.logger.info("AgentService 중지됨")
            
        except Exception as e:
            self.logger.error(f"AgentService 중지 오류: {str(e)}")
    
    # 에이전트 관리 메서드들
    async def create_agent(
        self,
        agent_type: str,
        name: str,
        description: str = "",
        config: Optional[Dict[str, Any]] = None
    ) -> str:
        """새로운 에이전트 생성"""
        try:
            # 에이전트 타입별 클래스 매핑
            agent_classes = {
                "search_strategy": SearchStrategyAgent,
                "contact": ContactAgent,
                "validation": ValidationAgent,
                "optimizer": OptimizerAgent
            }
            
            if agent_type not in agent_classes:
                raise ValueError(f"지원하지 않는 에이전트 타입: {agent_type}")
            
            # 에이전트 설정 생성
            agent_config = AgentConfig(
                name=name,
                description=description,
                **(config or {})
            )
            
            # 에이전트 생성 및 등록
            agent_class = agent_classes[agent_type]
            agent = agent_class(agent_config)
            agent_id = await self.agent_system.register_agent(agent)
            
            # 성능 메트릭 초기화
            self.performance_metrics[agent_id] = AgentPerformanceMetrics(
                agent_id=agent_id
            )
            
            self.logger.info(f"에이전트 생성됨: {agent_id} ({agent_type})")
            return agent_id
            
        except Exception as e:
            self.logger.error(f"에이전트 생성 오류: {str(e)}")
            raise
    
    async def remove_agent(self, agent_id: str) -> bool:
        """에이전트 제거"""
        try:
            # 실행 중인 작업이 있는지 확인
            running_agent_tasks = [
                task for task in self.running_tasks.values()
                if task.agent_id == agent_id
            ]
            
            if running_agent_tasks:
                # 실행 중인 작업들을 취소
                for task in running_agent_tasks:
                    await self.cancel_task(task.task_id)
            
            # 에이전트 시스템에서 해제
            success = await self.agent_system.unregister_agent(agent_id)
            
            if success:
                # 성능 메트릭 정리
                if agent_id in self.performance_metrics:
                    del self.performance_metrics[agent_id]
                
                self.logger.info(f"에이전트 제거됨: {agent_id}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"에이전트 제거 오류: {str(e)}")
            return False
    
    async def get_agent_info(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """에이전트 정보 조회"""
        try:
            agent = self.agent_system.get_agent(agent_id)
            if not agent:
                return None
            
            metrics = self.performance_metrics.get(agent_id)
            
            return {
                "agent_id": agent_id,
                "name": agent.config.name,
                "type": agent.__class__.__name__,
                "status": agent.status.value,
                "config": {
                    "temperature": agent.config.temperature,
                    "max_tokens": agent.config.max_tokens,
                    "max_retries": agent.config.max_retries,
                    "timeout": agent.config.timeout
                },
                "metrics": {
                    "total_tasks": metrics.total_tasks if metrics else 0,
                    "completed_tasks": metrics.completed_tasks if metrics else 0,
                    "failed_tasks": metrics.failed_tasks if metrics else 0,
                    "success_rate": metrics.success_rate if metrics else 0.0,
                    "average_execution_time": metrics.average_execution_time if metrics else 0.0,
                    "last_activity": metrics.last_activity if metrics else None
                }
            }
            
        except Exception as e:
            self.logger.error(f"에이전트 정보 조회 오류: {str(e)}")
            return None
    
    async def list_agents(self) -> List[Dict[str, Any]]:
        """등록된 에이전트 목록 조회"""
        try:
            agents = []
            for agent_id in self.agent_system.agents.keys():
                agent_info = await self.get_agent_info(agent_id)
                if agent_info:
                    agents.append(agent_info)
            
            return agents
            
        except Exception as e:
            self.logger.error(f"에이전트 목록 조회 오류: {str(e)}")
            return []
    
    # 작업 관리 메서드들
    async def submit_task(
        self,
        agent_id: str,
        task_type: str,
        data: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout: Optional[int] = None,
        max_retries: int = 3
    ) -> str:
        """새로운 작업 제출"""
        try:
            # 에이전트 존재 확인
            agent = self.agent_system.get_agent(agent_id)
            if not agent:
                raise ValueError(f"에이전트를 찾을 수 없습니다: {agent_id}")
            
            # 작업 ID 생성
            task_id = f"{agent_id}_{task_type}_{int(time.time() * 1000)}"
            
            # 작업 객체 생성
            task = AgentTask(
                task_id=task_id,
                agent_id=agent_id,
                task_type=task_type,
                data=data,
                priority=priority,
                status=TaskStatus.PENDING,
                created_at=datetime.now(),
                timeout=timeout or self.task_timeout_default,
                max_retries=max_retries
            )
            
            # 우선순위 큐에 추가 (우선순위가 높을수록 먼저 처리)
            priority_value = -priority.value  # 높은 우선순위가 먼저 나오도록
            await self.task_queue.put((priority_value, time.time(), task))
            
            self.logger.info(f"작업 제출됨: {task_id} (우선순위: {priority.name})")
            return task_id
            
        except Exception as e:
            self.logger.error(f"작업 제출 오류: {str(e)}")
            raise
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """작업 상태 조회"""
        try:
            # 실행 중인 작업에서 찾기
            if task_id in self.running_tasks:
                task = self.running_tasks[task_id]
            # 완료된 작업에서 찾기
            elif task_id in self.completed_tasks:
                task = self.completed_tasks[task_id]
            else:
                return None
            
            return {
                "task_id": task.task_id,
                "agent_id": task.agent_id,
                "task_type": task.task_type,
                "status": task.status.value,
                "priority": task.priority.name,
                "created_at": task.created_at,
                "started_at": task.started_at,
                "completed_at": task.completed_at,
                "result": task.result,
                "error": task.error,
                "retry_count": task.retry_count,
                "execution_time": (
                    (task.completed_at - task.started_at).total_seconds()
                    if task.started_at and task.completed_at
                    else None
                )
            }
            
        except Exception as e:
            self.logger.error(f"작업 상태 조회 오류: {str(e)}")
            return None
    
    async def cancel_task(self, task_id: str) -> bool:
        """작업 취소"""
        try:
            if task_id in self.running_tasks:
                task = self.running_tasks[task_id]
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now()
                
                # 실행 중인 작업에서 완료된 작업으로 이동
                self.completed_tasks[task_id] = task
                del self.running_tasks[task_id]
                
                self.logger.info(f"작업 취소됨: {task_id}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"작업 취소 오류: {str(e)}")
            return False
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """작업 큐 상태 조회"""
        try:
            return {
                "pending_tasks": self.task_queue.qsize(),
                "running_tasks": len(self.running_tasks),
                "completed_tasks": len(self.completed_tasks),
                "total_history": len(self.task_history),
                "max_concurrent": self.max_concurrent_tasks,
                "active_workers": len([t for t in self.worker_tasks if not t.done()])
            }
            
        except Exception as e:
            self.logger.error(f"큐 상태 조회 오류: {str(e)}")
            return {}
    
    # 내부 워커 메서드들
    async def _task_worker(self, worker_name: str):
        """작업 처리 워커"""
        self.logger.info(f"작업 워커 시작: {worker_name}")
        
        while self.is_running:
            try:
                # 작업 큐에서 작업 가져오기 (타임아웃 설정)
                try:
                    priority, timestamp, task = await asyncio.wait_for(
                        self.task_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # 작업 실행
                await self._execute_task(task, worker_name)
                
                # 큐 작업 완료 표시
                self.task_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"워커 {worker_name} 오류: {str(e)}")
                await asyncio.sleep(1)
        
        self.logger.info(f"작업 워커 종료: {worker_name}")
    
    async def _execute_task(self, task: AgentTask, worker_name: str):
        """개별 작업 실행"""
        try:
            # 작업 시작
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            self.running_tasks[task.task_id] = task
            
            self.logger.info(f"작업 시작: {task.task_id} (워커: {worker_name})")
            
            # 콜백 실행
            await self._execute_callbacks('on_task_start', task)
            
            # 에이전트 가져오기
            agent = self.agent_system.get_agent(task.agent_id)
            if not agent:
                raise Exception(f"에이전트를 찾을 수 없습니다: {task.agent_id}")
            
            # 타임아웃과 함께 작업 실행
            try:
                result = await asyncio.wait_for(
                    agent.process(task.data),
                    timeout=task.timeout
                )
                
                # 작업 완료
                task.status = TaskStatus.COMPLETED
                task.result = result
                task.completed_at = datetime.now()
                
                # 성능 메트릭 업데이트
                await self._update_performance_metrics(task.agent_id, True, task)
                
                # 콜백 실행
                await self._execute_callbacks('on_task_complete', task)
                
                self.logger.info(f"작업 완료: {task.task_id}")
                
            except asyncio.TimeoutError:
                raise Exception(f"작업 타임아웃: {task.timeout}초")
            
        except Exception as e:
            # 작업 실패
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.now()
            
            # 재시도 가능한지 확인
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = TaskStatus.PENDING
                task.started_at = None
                task.completed_at = None
                task.error = None
                
                # 재시도를 위해 큐에 다시 추가
                priority_value = -task.priority.value
                await self.task_queue.put((priority_value, time.time(), task))
                
                self.logger.warning(f"작업 재시도: {task.task_id} ({task.retry_count}/{task.max_retries})")
                return
            
            # 성능 메트릭 업데이트
            await self._update_performance_metrics(task.agent_id, False, task)
            
            # 콜백 실행
            await self._execute_callbacks('on_task_fail', task)
            
            self.logger.error(f"작업 실패: {task.task_id} - {str(e)}")
        
        finally:
            # 실행 중인 작업에서 완료된 작업으로 이동
            if task.task_id in self.running_tasks:
                self.completed_tasks[task.task_id] = task
                del self.running_tasks[task.task_id]
            
            # 히스토리에 추가
            self.task_history.append(task)
    
    async def _update_performance_metrics(self, agent_id: str, success: bool, task: AgentTask):
        """성능 메트릭 업데이트"""
        try:
            metrics = self.performance_metrics.get(agent_id)
            if not metrics:
                metrics = AgentPerformanceMetrics(agent_id=agent_id)
                self.performance_metrics[agent_id] = metrics
            
            metrics.total_tasks += 1
            metrics.last_activity = datetime.now()
            
            if success:
                metrics.completed_tasks += 1
            else:
                metrics.failed_tasks += 1
            
            # 성공률 계산
            metrics.success_rate = metrics.completed_tasks / metrics.total_tasks * 100
            
            # 평균 실행 시간 계산
            if task.started_at and task.completed_at:
                execution_time = (task.completed_at - task.started_at).total_seconds()
                if metrics.average_execution_time == 0:
                    metrics.average_execution_time = execution_time
                else:
                    # 이동 평균 계산
                    metrics.average_execution_time = (
                        metrics.average_execution_time * 0.8 + execution_time * 0.2
                    )
            
        except Exception as e:
            self.logger.error(f"성능 메트릭 업데이트 오류: {str(e)}")
    
    async def _cleanup_worker(self):
        """정리 워커 - 오래된 데이터 정리"""
        self.logger.info("정리 워커 시작")
        
        while self.is_running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                
                # 완료된 작업 정리 (24시간 이상 된 것)
                cutoff_time = datetime.now() - timedelta(hours=24)
                tasks_to_remove = [
                    task_id for task_id, task in self.completed_tasks.items()
                    if task.completed_at and task.completed_at < cutoff_time
                ]
                
                for task_id in tasks_to_remove:
                    del self.completed_tasks[task_id]
                
                # 히스토리 크기 제한
                if len(self.task_history) > self.max_history_size:
                    self.task_history = self.task_history[-self.max_history_size:]
                
                if tasks_to_remove:
                    self.logger.info(f"정리 완료: {len(tasks_to_remove)}개 오래된 작업 제거")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"정리 워커 오류: {str(e)}")
        
        self.logger.info("정리 워커 종료")
    
    async def _execute_callbacks(self, event_type: str, task: AgentTask):
        """콜백 함수 실행"""
        try:
            callbacks = self.task_callbacks.get(event_type, [])
            for callback in callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(task)
                    else:
                        callback(task)
                except Exception as e:
                    self.logger.error(f"콜백 실행 오류 ({event_type}): {str(e)}")
        except Exception as e:
            self.logger.error(f"콜백 실행 오류: {str(e)}")
    
    # 콜백 관리 메서드들
    def add_callback(self, event_type: str, callback: Callable):
        """콜백 함수 등록"""
        if event_type in self.task_callbacks:
            self.task_callbacks[event_type].append(callback)
    
    def remove_callback(self, event_type: str, callback: Callable):
        """콜백 함수 제거"""
        if event_type in self.task_callbacks:
            try:
                self.task_callbacks[event_type].remove(callback)
            except ValueError:
                pass
    
    # 통계 및 모니터링 메서드들
    async def get_statistics(self) -> Dict[str, Any]:
        """서비스 통계 조회"""
        try:
            total_agents = len(self.performance_metrics)
            total_tasks = sum(m.total_tasks for m in self.performance_metrics.values())
            completed_tasks = sum(m.completed_tasks for m in self.performance_metrics.values())
            failed_tasks = sum(m.failed_tasks for m in self.performance_metrics.values())
            
            return {
                "total_agents": total_agents,
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "failed_tasks": failed_tasks,
                "success_rate": (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0,
                "queue_status": await self.get_queue_status(),
                "service_uptime": time.time() - (self.start_time if hasattr(self, 'start_time') else time.time()),
                "active_agents": len([m for m in self.performance_metrics.values() if m.last_activity]),
                "average_response_time": sum(m.average_execution_time for m in self.performance_metrics.values()) / total_agents if total_agents > 0 else 0
            }
            
        except Exception as e:
            self.logger.error(f"통계 조회 오류: {str(e)}")
            return {}
    
    async def get_health_status(self) -> Dict[str, Any]:
        """서비스 건강 상태 조회"""
        try:
            queue_status = await self.get_queue_status()
            stats = await self.get_statistics()
            
            # 건강 상태 판단
            is_healthy = (
                self.is_running and
                queue_status.get("active_workers", 0) > 0 and
                stats.get("success_rate", 0) > 80  # 성공률 80% 이상
            )
            
            return {
                "status": "healthy" if is_healthy else "degraded",
                "is_running": self.is_running,
                "queue_status": queue_status,
                "performance": {
                    "total_agents": stats.get("total_agents", 0),
                    "success_rate": stats.get("success_rate", 0),
                    "average_response_time": stats.get("average_response_time", 0)
                },
                "timestamp": datetime.now()
            }
            
        except Exception as e:
            self.logger.error(f"건강 상태 조회 오류: {str(e)}")
            return {"status": "unhealthy", "error": str(e)} 