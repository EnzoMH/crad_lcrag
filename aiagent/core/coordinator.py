# 에이전트 조정자 및 워크플로우 관리 시스템
# 여러 전문 에이전트들을 조율하고 복합 작업을 수행하는 중앙 관리자

from typing import Dict, List, Optional, Any, Union, Callable, Awaitable
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import asyncio
import json
import logging
from enum import Enum
from collections import defaultdict
import uuid

from .agent_base import BaseAgent, AgentResult, AgentConfig, AgentRegistry
from .agent_system import AIAgentSystem
from ..agents import (
    SearchStrategyAgent, ContactAgent, ValidationAgent, OptimizerAgent,
    SearchTarget, ContactTarget, ValidationTarget
)
from ..utils.gemini_client import GeminiClient
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

logger = logging.getLogger(__name__)

class WorkflowType(Enum):
    """워크플로우 유형"""
    SEQUENTIAL = "sequential"         # 순차 실행
    PARALLEL = "parallel"            # 병렬 실행
    CONDITIONAL = "conditional"       # 조건부 실행
    PIPELINE = "pipeline"            # 파이프라인 실행
    ADAPTIVE = "adaptive"            # 적응형 실행

class TaskStatus(Enum):
    """작업 상태"""
    PENDING = "pending"              # 대기 중
    RUNNING = "running"              # 실행 중
    COMPLETED = "completed"          # 완료
    FAILED = "failed"                # 실패
    CANCELLED = "cancelled"          # 취소
    RETRY = "retry"                  # 재시도

@dataclass
class WorkflowTask:
    """워크플로우 작업"""
    id: str                          # 작업 ID
    agent_type: str                  # 에이전트 타입
    input_data: Dict[str, Any]       # 입력 데이터
    dependencies: List[str] = None   # 의존성 작업 IDs
    priority: int = 1                # 우선순위 (1: 높음, 5: 낮음)
    timeout: Optional[int] = None    # 타임아웃 (초)
    retry_count: int = 0             # 재시도 횟수
    max_retries: int = 3             # 최대 재시도 횟수
    
    # 실행 상태
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[AgentResult] = None
    error_message: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    execution_time: float = 0.0

@dataclass
class WorkflowDefinition:
    """워크플로우 정의"""
    id: str                          # 워크플로우 ID
    name: str                        # 워크플로우 이름
    description: str                 # 설명
    workflow_type: WorkflowType      # 워크플로우 타입
    tasks: List[WorkflowTask]        # 작업 목록
    global_timeout: Optional[int] = None  # 전체 타임아웃
    failure_policy: str = "stop"     # 실패 정책 (stop, continue, retry)
    
    # 메타데이터
    created_at: datetime = None
    created_by: str = "system"
    version: str = "1.0"

@dataclass
class WorkflowExecution:
    """워크플로우 실행 상태"""
    workflow_id: str                 # 워크플로우 ID
    execution_id: str                # 실행 ID
    status: TaskStatus               # 전체 상태
    started_at: datetime             # 시작 시간
    completed_at: Optional[datetime] = None  # 완료 시간
    
    # 실행 통계
    total_tasks: int = 0             # 전체 작업 수
    completed_tasks: int = 0         # 완료된 작업 수
    failed_tasks: int = 0            # 실패한 작업 수
    success_rate: float = 0.0        # 성공률
    
    # 결과 데이터
    results: Dict[str, AgentResult] = None
    final_output: Dict[str, Any] = None
    execution_log: List[str] = None

class AgentCoordinator:
    """
    에이전트 조정자 및 워크플로우 관리자
    
    기능:
    - 다중 에이전트 조율 및 협업 관리
    - 복합 워크플로우 정의 및 실행
    - 동적 작업 스케줄링 및 우선순위 관리
    - 실시간 모니터링 및 오류 처리
    - AI 기반 워크플로우 최적화
    """
    
    def __init__(self, agent_system: AIAgentSystem):
        self.agent_system = agent_system
        self.active_workflows: Dict[str, WorkflowExecution] = {}
        self.workflow_definitions: Dict[str, WorkflowDefinition] = {}
        self.execution_history: List[WorkflowExecution] = []
        
        # 사전 정의된 워크플로우 로드
        self._load_predefined_workflows()
        
        # Langchain 프롬프트 템플릿
        self.workflow_optimization_prompt = PromptTemplate(
            input_variables=["workflow_definition", "execution_history", "performance_data"],
            template="""
            다음 워크플로우를 분석하여 최적화 방안을 제안해주세요:

            워크플로우 정의:
            {workflow_definition}

            실행 히스토리:
            {execution_history}

            성능 데이터:
            {performance_data}

            최적화 관점:
            1. 작업 순서 및 병렬성 개선
            2. 에이전트 선택 최적화
            3. 리소스 효율성 향상
            4. 실패 처리 개선

            JSON 형식으로 응답:
            {{
                "optimizations": [
                    {{
                        "type": "task_ordering/parallelization/resource/error_handling",
                        "description": "최적화 설명",
                        "expected_improvement": 25.5,
                        "implementation": ["구현 단계들"]
                    }}
                ],
                "recommended_workflow": {{
                    "workflow_type": "sequential/parallel/pipeline",
                    "task_adjustments": ["조정 사항들"]
                }}
            }}
            """
        )
        
        # 동적 에이전트 선택 프롬프트
        self.agent_selection_prompt = PromptTemplate(
            input_variables=["task_description", "available_agents", "context"],
            template="""
            다음 작업에 가장 적합한 에이전트를 선택해주세요:

            작업 설명:
            {task_description}

            사용 가능한 에이전트:
            {available_agents}

            컨텍스트 정보:
            {context}

            선택 기준:
            1. 작업 특성과 에이전트 전문성 매칭
            2. 현재 리소스 상황
            3. 과거 성능 데이터
            4. 의존성 고려

            JSON 응답:
            {{
                "selected_agent": "agent_type",
                "confidence": 0.95,
                "reasoning": "선택 이유",
                "alternative_agents": ["대안1", "대안2"],
                "estimated_performance": {{
                    "success_probability": 0.9,
                    "execution_time": 30
                }}
            }}
            """
        )
    
    def _load_predefined_workflows(self):
        """사전 정의된 워크플로우 로드"""
        
        # 1. 기본 크롤링 워크플로우
        basic_crawling_workflow = WorkflowDefinition(
            id="basic_crawling",
            name="기본 크롤링 워크플로우",
            description="기관 정보 크롤링, 연락처 추출, 데이터 검증의 기본 파이프라인",
            workflow_type=WorkflowType.PIPELINE,
            tasks=[
                WorkflowTask(
                    id="strategy_planning",
                    agent_type="SearchStrategyAgent",
                    input_data={"operation": "generate_strategy"},
                    priority=1
                ),
                WorkflowTask(
                    id="contact_extraction", 
                    agent_type="ContactAgent",
                    input_data={"operation": "extract_contacts"},
                    dependencies=["strategy_planning"],
                    priority=2
                ),
                WorkflowTask(
                    id="data_validation",
                    agent_type="ValidationAgent", 
                    input_data={"operation": "validate_data"},
                    dependencies=["contact_extraction"],
                    priority=3
                )
            ],
            global_timeout=300,  # 5분
            failure_policy="retry"
        )
        
        # 2. 고급 품질 보증 워크플로우
        quality_assurance_workflow = WorkflowDefinition(
            id="quality_assurance",
            name="고급 품질 보증 워크플로우", 
            description="다중 검증 및 성능 최적화가 포함된 고급 워크플로우",
            workflow_type=WorkflowType.CONDITIONAL,
            tasks=[
                WorkflowTask(
                    id="initial_validation",
                    agent_type="ValidationAgent",
                    input_data={"validation_level": "basic"},
                    priority=1
                ),
                WorkflowTask(
                    id="performance_check",
                    agent_type="OptimizerAgent",
                    input_data={"operation_type": "monitor"},
                    priority=1
                ),
                WorkflowTask(
                    id="advanced_validation",
                    agent_type="ValidationAgent", 
                    input_data={"validation_level": "advanced"},
                    dependencies=["initial_validation"],
                    priority=2
                ),
                WorkflowTask(
                    id="contact_enrichment",
                    agent_type="ContactAgent",
                    input_data={"operation": "enrich_contacts"},
                    dependencies=["advanced_validation"],
                    priority=3
                )
            ],
            global_timeout=600,  # 10분
            failure_policy="continue"
        )
        
        # 3. 성능 최적화 워크플로우
        optimization_workflow = WorkflowDefinition(
            id="performance_optimization",
            name="성능 최적화 워크플로우",
            description="시스템 성능 모니터링, 분석, 최적화의 연속 프로세스",
            workflow_type=WorkflowType.PARALLEL,
            tasks=[
                WorkflowTask(
                    id="system_monitoring",
                    agent_type="OptimizerAgent",
                    input_data={"operation_type": "monitor"},
                    priority=1
                ),
                WorkflowTask(
                    id="performance_analysis",
                    agent_type="OptimizerAgent",
                    input_data={"operation_type": "analyze"},
                    priority=1
                ),
                WorkflowTask(
                    id="optimization_recommendations",
                    agent_type="OptimizerAgent", 
                    input_data={"operation_type": "optimize"},
                    dependencies=["system_monitoring", "performance_analysis"],
                    priority=2
                )
            ],
            global_timeout=180,  # 3분
            failure_policy="continue"
        )
        
        # 워크플로우 등록
        self.workflow_definitions[basic_crawling_workflow.id] = basic_crawling_workflow
        self.workflow_definitions[quality_assurance_workflow.id] = quality_assurance_workflow  
        self.workflow_definitions[optimization_workflow.id] = optimization_workflow
        
        logger.info(f"{len(self.workflow_definitions)}개 사전 정의 워크플로우 로드 완료")
    
    async def execute_workflow(
        self,
        workflow_id: str,
        input_data: Dict[str, Any],
        execution_options: Dict[str, Any] = None
    ) -> WorkflowExecution:
        """
        워크플로우 실행
        
        Args:
            workflow_id: 실행할 워크플로우 ID
            input_data: 워크플로우 입력 데이터
            execution_options: 실행 옵션 (timeout, retry_policy 등)
        
        Returns:
            WorkflowExecution: 워크플로우 실행 결과
        """
        try:
            # 워크플로우 정의 조회
            if workflow_id not in self.workflow_definitions:
                raise ValueError(f"워크플로우를 찾을 수 없습니다: {workflow_id}")
            
            workflow_def = self.workflow_definitions[workflow_id]
            execution_id = str(uuid.uuid4())
            
            # 워크플로우 실행 상태 초기화
            execution = WorkflowExecution(
                workflow_id=workflow_id,
                execution_id=execution_id,
                status=TaskStatus.RUNNING,
                started_at=datetime.now(),
                total_tasks=len(workflow_def.tasks),
                results={},
                final_output={},
                execution_log=[]
            )
            
            self.active_workflows[execution_id] = execution
            execution.execution_log.append(f"워크플로우 실행 시작: {workflow_def.name}")
            
            # 워크플로우 타입에 따른 실행
            if workflow_def.workflow_type == WorkflowType.SEQUENTIAL:
                await self._execute_sequential_workflow(workflow_def, execution, input_data)
            elif workflow_def.workflow_type == WorkflowType.PARALLEL:
                await self._execute_parallel_workflow(workflow_def, execution, input_data)
            elif workflow_def.workflow_type == WorkflowType.PIPELINE:
                await self._execute_pipeline_workflow(workflow_def, execution, input_data)
            elif workflow_def.workflow_type == WorkflowType.CONDITIONAL:
                await self._execute_conditional_workflow(workflow_def, execution, input_data)
            elif workflow_def.workflow_type == WorkflowType.ADAPTIVE:
                await self._execute_adaptive_workflow(workflow_def, execution, input_data)
            
            # 실행 완료 처리
            execution.completed_at = datetime.now()
            execution.success_rate = execution.completed_tasks / execution.total_tasks if execution.total_tasks > 0 else 0
            
            if execution.failed_tasks == 0:
                execution.status = TaskStatus.COMPLETED
            elif execution.completed_tasks > 0:
                execution.status = TaskStatus.COMPLETED  # 부분 성공
            else:
                execution.status = TaskStatus.FAILED
            
            # 최종 결과 생성
            execution.final_output = self._generate_final_output(execution)
            
            # 실행 히스토리에 저장
            self.execution_history.append(execution)
            if execution_id in self.active_workflows:
                del self.active_workflows[execution_id]
            
            execution.execution_log.append(f"워크플로우 실행 완료: {execution.status.value}")
            logger.info(f"워크플로우 실행 완료 - {workflow_id}: {execution.status.value}")
            
            return execution
            
        except Exception as e:
            logger.error(f"워크플로우 실행 실패 - {workflow_id}: {str(e)}")
            
            # 오류 상태 설정
            if execution_id in self.active_workflows:
                execution = self.active_workflows[execution_id]
                execution.status = TaskStatus.FAILED
                execution.completed_at = datetime.now()
                execution.execution_log.append(f"워크플로우 실행 실패: {str(e)}")
                del self.active_workflows[execution_id]
                return execution
            
            # 새로운 실패 상태 생성
            failed_execution = WorkflowExecution(
                workflow_id=workflow_id,
                execution_id=execution_id,
                status=TaskStatus.FAILED,
                started_at=datetime.now(),
                completed_at=datetime.now(),
                execution_log=[f"워크플로우 실행 실패: {str(e)}"]
            )
            
            return failed_execution
    
    async def _execute_sequential_workflow(
        self,
        workflow_def: WorkflowDefinition,
        execution: WorkflowExecution,
        input_data: Dict[str, Any]
    ):
        """순차 워크플로우 실행"""
        current_data = input_data.copy()
        
        for task in workflow_def.tasks:
            try:
                execution.execution_log.append(f"작업 시작: {task.id} ({task.agent_type})")
                
                # 의존성 확인
                if task.dependencies:
                    missing_deps = [dep for dep in task.dependencies if dep not in execution.results]
                    if missing_deps:
                        raise ValueError(f"의존성 작업 미완료: {missing_deps}")
                
                # 작업 실행
                task.start_time = datetime.now()
                task.status = TaskStatus.RUNNING
                
                # 이전 작업 결과를 현재 작업 입력에 병합
                task_input = self._prepare_task_input(task, current_data, execution.results)
                
                # 에이전트 실행
                result = await self._execute_task(task, task_input)
                
                # 결과 처리
                task.end_time = datetime.now()
                task.execution_time = (task.end_time - task.start_time).total_seconds()
                task.result = result
                
                if result.success:
                    task.status = TaskStatus.COMPLETED
                    execution.completed_tasks += 1
                    execution.results[task.id] = result
                    # 다음 작업을 위해 결과 데이터 업데이트
                    current_data.update(result.data)
                    execution.execution_log.append(f"작업 완료: {task.id}")
                else:
                    task.status = TaskStatus.FAILED
                    execution.failed_tasks += 1
                    task.error_message = result.message
                    execution.execution_log.append(f"작업 실패: {task.id} - {result.message}")
                    
                    # 실패 정책에 따른 처리
                    if workflow_def.failure_policy == "stop":
                        break
                    elif workflow_def.failure_policy == "retry" and task.retry_count < task.max_retries:
                        await self._retry_task(task, task_input, execution)
                
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error_message = str(e)
                execution.failed_tasks += 1
                execution.execution_log.append(f"작업 오류: {task.id} - {str(e)}")
                
                if workflow_def.failure_policy == "stop":
                    break
    
    async def _execute_parallel_workflow(
        self,
        workflow_def: WorkflowDefinition,
        execution: WorkflowExecution,
        input_data: Dict[str, Any]
    ):
        """병렬 워크플로우 실행"""
        # 의존성 그래프 분석
        dependency_groups = self._analyze_task_dependencies(workflow_def.tasks)
        
        for group in dependency_groups:
            # 각 그룹 내의 작업들을 병렬 실행
            tasks_to_run = []
            
            for task in group:
                # 의존성 확인
                if task.dependencies:
                    missing_deps = [dep for dep in task.dependencies if dep not in execution.results]
                    if missing_deps:
                        execution.execution_log.append(f"작업 건너뜀 - 의존성 미완료: {task.id}")
                        continue
                
                task_input = self._prepare_task_input(task, input_data, execution.results)
                tasks_to_run.append(self._execute_task_with_tracking(task, task_input, execution))
            
            if tasks_to_run:
                # 병렬 실행
                results = await asyncio.gather(*tasks_to_run, return_exceptions=True)
                
                # 결과 처리
                for i, result in enumerate(results):
                    task = group[i] if i < len(group) else None
                    if task:
                        if isinstance(result, Exception):
                            task.status = TaskStatus.FAILED
                            task.error_message = str(result)
                            execution.failed_tasks += 1
                        else:
                            execution.results[task.id] = result
                            if result.success:
                                execution.completed_tasks += 1
                            else:
                                execution.failed_tasks += 1
    
    async def _execute_pipeline_workflow(
        self,
        workflow_def: WorkflowDefinition,
        execution: WorkflowExecution,
        input_data: Dict[str, Any]
    ):
        """파이프라인 워크플로우 실행 (순차 + 데이터 흐름)"""
        pipeline_data = input_data.copy()
        
        for task in workflow_def.tasks:
            try:
                execution.execution_log.append(f"파이프라인 단계 시작: {task.id}")
                
                # 작업 실행
                task.start_time = datetime.now()
                task.status = TaskStatus.RUNNING
                
                # 파이프라인 데이터 전달
                task_input = {**task.input_data, **pipeline_data}
                
                result = await self._execute_task(task, task_input)
                
                # 결과 처리
                task.end_time = datetime.now()
                task.execution_time = (task.end_time - task.start_time).total_seconds()
                task.result = result
                
                if result.success:
                    task.status = TaskStatus.COMPLETED
                    execution.completed_tasks += 1
                    execution.results[task.id] = result
                    
                    # 파이프라인 데이터 업데이트 (다음 단계로 전달)
                    pipeline_data = result.data
                    execution.execution_log.append(f"파이프라인 단계 완료: {task.id}")
                else:
                    task.status = TaskStatus.FAILED
                    execution.failed_tasks += 1
                    execution.execution_log.append(f"파이프라인 단계 실패: {task.id}")
                    break  # 파이프라인에서는 실패 시 중단
                
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error_message = str(e)
                execution.failed_tasks += 1
                execution.execution_log.append(f"파이프라인 오류: {task.id} - {str(e)}")
                break
    
    async def _execute_conditional_workflow(
        self,
        workflow_def: WorkflowDefinition,
        execution: WorkflowExecution,
        input_data: Dict[str, Any]
    ):
        """조건부 워크플로우 실행"""
        current_data = input_data.copy()
        
        for task in workflow_def.tasks:
            try:
                # 조건 평가 (간단한 예시)
                should_execute = await self._evaluate_task_condition(task, current_data, execution.results)
                
                if not should_execute:
                    execution.execution_log.append(f"작업 건너뜀 - 조건 불만족: {task.id}")
                    continue
                
                execution.execution_log.append(f"조건부 작업 시작: {task.id}")
                
                # 작업 실행
                task.start_time = datetime.now()
                task.status = TaskStatus.RUNNING
                
                task_input = self._prepare_task_input(task, current_data, execution.results)
                result = await self._execute_task(task, task_input)
                
                # 결과 처리
                task.end_time = datetime.now()
                task.execution_time = (task.end_time - task.start_time).total_seconds()
                task.result = result
                
                if result.success:
                    task.status = TaskStatus.COMPLETED
                    execution.completed_tasks += 1
                    execution.results[task.id] = result
                    current_data.update(result.data)
                else:
                    task.status = TaskStatus.FAILED
                    execution.failed_tasks += 1
                
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error_message = str(e)
                execution.failed_tasks += 1
    
    async def _execute_adaptive_workflow(
        self,
        workflow_def: WorkflowDefinition,
        execution: WorkflowExecution,
        input_data: Dict[str, Any]
    ):
        """적응형 워크플로우 실행 (AI 기반 동적 조정)"""
        current_data = input_data.copy()
        remaining_tasks = workflow_def.tasks.copy()
        
        while remaining_tasks:
            # AI를 통한 다음 작업 선택
            next_task = await self._select_next_task_ai(remaining_tasks, current_data, execution)
            
            if not next_task:
                break
            
            remaining_tasks.remove(next_task)
            
            try:
                execution.execution_log.append(f"적응형 작업 선택: {next_task.id}")
                
                # 작업 실행
                next_task.start_time = datetime.now()
                next_task.status = TaskStatus.RUNNING
                
                task_input = self._prepare_task_input(next_task, current_data, execution.results)
                result = await self._execute_task(next_task, task_input)
                
                # 결과 처리
                next_task.end_time = datetime.now()
                next_task.execution_time = (next_task.end_time - next_task.start_time).total_seconds()
                next_task.result = result
                
                if result.success:
                    next_task.status = TaskStatus.COMPLETED
                    execution.completed_tasks += 1
                    execution.results[next_task.id] = result
                    current_data.update(result.data)
                else:
                    next_task.status = TaskStatus.FAILED
                    execution.failed_tasks += 1
                
            except Exception as e:
                next_task.status = TaskStatus.FAILED
                next_task.error_message = str(e)
                execution.failed_tasks += 1
    
    async def _execute_task(self, task: WorkflowTask, input_data: Dict[str, Any]) -> AgentResult:
        """개별 작업 실행"""
        # 에이전트 타입에 따른 실행
        if task.agent_type == "SearchStrategyAgent":
            agent = self.agent_system.get_agent("search_strategy")
            if not agent:
                agent = SearchStrategyAgent(AgentConfig(name="search_strategy"))
                self.agent_system.register_agent(agent)
            
        elif task.agent_type == "ContactAgent":
            agent = self.agent_system.get_agent("contact")
            if not agent:
                agent = ContactAgent(AgentConfig(name="contact"))
                self.agent_system.register_agent(agent)
                
        elif task.agent_type == "ValidationAgent":
            agent = self.agent_system.get_agent("validation")
            if not agent:
                agent = ValidationAgent(AgentConfig(name="validation"))
                self.agent_system.register_agent(agent)
                
        elif task.agent_type == "OptimizerAgent":
            agent = self.agent_system.get_agent("optimizer")
            if not agent:
                agent = OptimizerAgent(AgentConfig(name="optimizer"))
                self.agent_system.register_agent(agent)
        else:
            raise ValueError(f"지원하지 않는 에이전트 타입: {task.agent_type}")
        
        # 타임아웃 설정
        if task.timeout:
            try:
                result = await asyncio.wait_for(agent.process(input_data), timeout=task.timeout)
            except asyncio.TimeoutError:
                return AgentResult(
                    success=False,
                    data={},
                    message=f"작업 타임아웃: {task.timeout}초",
                    execution_time=task.timeout
                )
        else:
            result = await agent.process(input_data)
        
        return result
    
    async def _execute_task_with_tracking(
        self,
        task: WorkflowTask,
        input_data: Dict[str, Any],
        execution: WorkflowExecution
    ) -> AgentResult:
        """추적 기능이 포함된 작업 실행"""
        task.start_time = datetime.now()
        task.status = TaskStatus.RUNNING
        
        try:
            result = await self._execute_task(task, input_data)
            
            task.end_time = datetime.now()
            task.execution_time = (task.end_time - task.start_time).total_seconds()
            task.result = result
            
            if result.success:
                task.status = TaskStatus.COMPLETED
                execution.execution_log.append(f"병렬 작업 완료: {task.id}")
            else:
                task.status = TaskStatus.FAILED
                task.error_message = result.message
                execution.execution_log.append(f"병렬 작업 실패: {task.id}")
            
            return result
            
        except Exception as e:
            task.end_time = datetime.now()
            task.execution_time = (task.end_time - task.start_time).total_seconds()
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            execution.execution_log.append(f"병렬 작업 오류: {task.id} - {str(e)}")
            
            return AgentResult(
                success=False,
                data={},
                message=str(e),
                execution_time=task.execution_time
            )
    
    def _analyze_task_dependencies(self, tasks: List[WorkflowTask]) -> List[List[WorkflowTask]]:
        """작업 의존성 분석하여 병렬 실행 그룹 생성"""
        groups = []
        processed_tasks = set()
        
        while len(processed_tasks) < len(tasks):
            current_group = []
            
            for task in tasks:
                if task.id in processed_tasks:
                    continue
                
                # 의존성이 모두 처리되었는지 확인
                if not task.dependencies or all(dep in processed_tasks for dep in task.dependencies):
                    current_group.append(task)
            
            if not current_group:
                # 순환 의존성이나 오류 상황
                remaining_tasks = [task for task in tasks if task.id not in processed_tasks]
                current_group.extend(remaining_tasks)
                logger.warning("의존성 분석 오류 - 남은 작업들을 강제 추가")
            
            groups.append(current_group)
            processed_tasks.update(task.id for task in current_group)
        
        return groups
    
    def _prepare_task_input(
        self,
        task: WorkflowTask,
        current_data: Dict[str, Any],
        previous_results: Dict[str, AgentResult]
    ) -> Dict[str, Any]:
        """작업 입력 데이터 준비"""
        task_input = task.input_data.copy()
        
        # 현재 데이터 병합
        task_input.update(current_data)
        
        # 의존성 작업 결과 병합
        if task.dependencies:
            for dep_id in task.dependencies:
                if dep_id in previous_results:
                    dep_result = previous_results[dep_id]
                    task_input[f"{dep_id}_result"] = dep_result.data
        
        return task_input
    
    async def _evaluate_task_condition(
        self,
        task: WorkflowTask,
        current_data: Dict[str, Any],
        previous_results: Dict[str, AgentResult]
    ) -> bool:
        """작업 실행 조건 평가"""
        # 기본 조건들
        
        # 의존성 확인
        if task.dependencies:
            for dep_id in task.dependencies:
                if dep_id not in previous_results:
                    return False
                if not previous_results[dep_id].success:
                    return False
        
        # 우선순위 기반 조건 (예시)
        if task.priority > 3:
            # 낮은 우선순위 작업은 시스템 부하가 낮을 때만 실행
            system_load = current_data.get("system_load", 50)
            if system_load > 80:
                return False
        
        # 에이전트별 특별 조건
        if task.agent_type == "OptimizerAgent":
            # 최적화 작업은 충분한 데이터가 있을 때만 실행
            data_count = len(previous_results)
            if data_count < 2:
                return False
        
        return True
    
    async def _select_next_task_ai(
        self,
        remaining_tasks: List[WorkflowTask],
        current_data: Dict[str, Any],
        execution: WorkflowExecution
    ) -> Optional[WorkflowTask]:
        """AI 기반 다음 작업 선택"""
        if not remaining_tasks:
            return None
        
        try:
            # 사용 가능한 작업들만 필터링
            available_tasks = []
            for task in remaining_tasks:
                if not task.dependencies or all(dep in execution.results for dep in task.dependencies):
                    available_tasks.append(task)
            
            if not available_tasks:
                return None
            
            if len(available_tasks) == 1:
                return available_tasks[0]
            
            # AI를 통한 작업 선택
            gemini_client = GeminiClient()
            chain = LLMChain(
                llm=gemini_client.get_llm(),
                prompt=self.agent_selection_prompt
            )
            
            task_descriptions = [f"{task.id}: {task.agent_type}" for task in available_tasks]
            available_agents = [task.agent_type for task in available_tasks]
            
            response = await chain.arun(
                task_description=", ".join(task_descriptions),
                available_agents=", ".join(set(available_agents)),
                context=f"현재 완료된 작업 수: {execution.completed_tasks}, 실패 수: {execution.failed_tasks}"
            )
            
            ai_data = json.loads(response.strip())
            selected_agent_type = ai_data.get("selected_agent")
            
            # 선택된 에이전트 타입에 해당하는 작업 반환
            for task in available_tasks:
                if task.agent_type == selected_agent_type:
                    return task
            
            # AI 선택이 실패하면 우선순위 기반 선택
            return min(available_tasks, key=lambda t: t.priority)
            
        except Exception as e:
            logger.warning(f"AI 작업 선택 실패: {str(e)}")
            # 우선순위 기반 대체 선택
            available_tasks = [task for task in remaining_tasks 
                             if not task.dependencies or all(dep in execution.results for dep in task.dependencies)]
            if available_tasks:
                return min(available_tasks, key=lambda t: t.priority)
            return None
    
    async def _retry_task(
        self,
        task: WorkflowTask,
        input_data: Dict[str, Any],
        execution: WorkflowExecution
    ):
        """작업 재시도"""
        task.retry_count += 1
        execution.execution_log.append(f"작업 재시도 ({task.retry_count}/{task.max_retries}): {task.id}")
        
        # 지수 백오프 대기
        wait_time = min(2 ** task.retry_count, 30)  # 최대 30초
        await asyncio.sleep(wait_time)
        
        try:
            task.status = TaskStatus.RETRY
            result = await self._execute_task(task, input_data)
            
            if result.success:
                task.status = TaskStatus.COMPLETED
                execution.completed_tasks += 1
                execution.results[task.id] = result
                execution.execution_log.append(f"작업 재시도 성공: {task.id}")
            else:
                task.status = TaskStatus.FAILED
                execution.failed_tasks += 1
                task.error_message = result.message
                execution.execution_log.append(f"작업 재시도 실패: {task.id}")
                
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            execution.failed_tasks += 1
            execution.execution_log.append(f"작업 재시도 오류: {task.id} - {str(e)}")
    
    def _generate_final_output(self, execution: WorkflowExecution) -> Dict[str, Any]:
        """최종 출력 데이터 생성"""
        final_output = {
            "execution_summary": {
                "workflow_id": execution.workflow_id,
                "execution_id": execution.execution_id,
                "status": execution.status.value,
                "total_tasks": execution.total_tasks,
                "completed_tasks": execution.completed_tasks,
                "failed_tasks": execution.failed_tasks,
                "success_rate": execution.success_rate,
                "execution_time": (execution.completed_at - execution.started_at).total_seconds() if execution.completed_at else 0
            },
            "task_results": {},
            "aggregated_data": {},
            "recommendations": []
        }
        
        # 작업별 결과 수집
        for task_id, result in execution.results.items():
            final_output["task_results"][task_id] = {
                "success": result.success,
                "data": result.data,
                "message": result.message,
                "execution_time": result.execution_time
            }
        
        # 데이터 집계
        all_data = {}
        for result in execution.results.values():
            if result.success and result.data:
                all_data.update(result.data)
        
        final_output["aggregated_data"] = all_data
        
        # 권장사항 생성
        if execution.failed_tasks > 0:
            final_output["recommendations"].append("실패한 작업들을 검토하고 재실행을 고려하세요.")
        
        if execution.success_rate < 0.8:
            final_output["recommendations"].append("워크플로우 성공률이 낮습니다. 작업 정의를 검토하세요.")
        
        return final_output
    
    def get_workflow_status(self, execution_id: str) -> Optional[WorkflowExecution]:
        """워크플로우 실행 상태 조회"""
        return self.active_workflows.get(execution_id)
    
    def list_active_workflows(self) -> List[WorkflowExecution]:
        """활성 워크플로우 목록 조회"""
        return list(self.active_workflows.values())
    
    def get_workflow_definitions(self) -> List[WorkflowDefinition]:
        """사용 가능한 워크플로우 정의 목록"""
        return list(self.workflow_definitions.values())
    
    async def cancel_workflow(self, execution_id: str) -> bool:
        """워크플로우 실행 취소"""
        if execution_id in self.active_workflows:
            execution = self.active_workflows[execution_id]
            execution.status = TaskStatus.CANCELLED
            execution.completed_at = datetime.now()
            execution.execution_log.append("워크플로우 실행이 사용자에 의해 취소되었습니다")
            
            # 활성 목록에서 제거
            del self.active_workflows[execution_id]
            
            # 히스토리에 추가
            self.execution_history.append(execution)
            
            logger.info(f"워크플로우 실행 취소: {execution_id}")
            return True
        
        return False
    
    async def optimize_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """AI 기반 워크플로우 최적화"""
        try:
            if workflow_id not in self.workflow_definitions:
                return {"error": "워크플로우를 찾을 수 없습니다"}
            
            workflow_def = self.workflow_definitions[workflow_id]
            
            # 실행 히스토리 분석
            relevant_executions = [
                ex for ex in self.execution_history 
                if ex.workflow_id == workflow_id
            ]
            
            if not relevant_executions:
                return {"message": "최적화할 실행 히스토리가 없습니다"}
            
            # 성능 데이터 수집
            performance_data = {
                "average_success_rate": sum(ex.success_rate for ex in relevant_executions) / len(relevant_executions),
                "average_execution_time": sum(
                    (ex.completed_at - ex.started_at).total_seconds() 
                    for ex in relevant_executions if ex.completed_at
                ) / len(relevant_executions),
                "common_failures": self._analyze_common_failures(relevant_executions)
            }
            
            # AI 체인으로 최적화 분석
            gemini_client = GeminiClient()
            chain = LLMChain(
                llm=gemini_client.get_llm(),
                prompt=self.workflow_optimization_prompt
            )
            
            response = await chain.arun(
                workflow_definition=json.dumps(asdict(workflow_def)),
                execution_history=json.dumps([asdict(ex) for ex in relevant_executions[-5:]]),
                performance_data=json.dumps(performance_data)
            )
            
            optimization_result = json.loads(response.strip())
            
            return {
                "workflow_id": workflow_id,
                "current_performance": performance_data,
                "optimizations": optimization_result.get("optimizations", []),
                "recommended_workflow": optimization_result.get("recommended_workflow", {}),
                "analysis_timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"워크플로우 최적화 실패: {str(e)}")
            return {"error": f"최적화 분석 실패: {str(e)}"}
    
    def _analyze_common_failures(self, executions: List[WorkflowExecution]) -> List[str]:
        """공통 실패 패턴 분석"""
        failure_patterns = defaultdict(int)
        
        for execution in executions:
            for log_entry in execution.execution_log:
                if "실패" in log_entry or "오류" in log_entry:
                    failure_patterns[log_entry] += 1
        
        # 상위 5개 실패 패턴 반환
        common_failures = sorted(failure_patterns.items(), key=lambda x: x[1], reverse=True)
        return [pattern for pattern, count in common_failures[:5]]
    
    def get_execution_statistics(self) -> Dict[str, Any]:
        """워크플로우 실행 통계"""
        if not self.execution_history:
            return {"message": "실행 기록이 없습니다"}
        
        total_executions = len(self.execution_history)
        successful_executions = sum(1 for ex in self.execution_history if ex.status == TaskStatus.COMPLETED)
        
        # 워크플로우별 통계
        workflow_stats = defaultdict(lambda: {"count": 0, "success": 0})
        for execution in self.execution_history:
            workflow_stats[execution.workflow_id]["count"] += 1
            if execution.status == TaskStatus.COMPLETED:
                workflow_stats[execution.workflow_id]["success"] += 1
        
        # 평균 실행 시간
        completed_executions = [ex for ex in self.execution_history if ex.completed_at]
        avg_execution_time = 0
        if completed_executions:
            avg_execution_time = sum(
                (ex.completed_at - ex.started_at).total_seconds() 
                for ex in completed_executions
            ) / len(completed_executions)
        
        return {
            "overall_statistics": {
                "total_executions": total_executions,
                "successful_executions": successful_executions,
                "success_rate": successful_executions / total_executions if total_executions > 0 else 0,
                "average_execution_time": avg_execution_time
            },
            "workflow_statistics": dict(workflow_stats),
            "active_workflows": len(self.active_workflows),
            "analysis_timestamp": datetime.now().isoformat()
        } 