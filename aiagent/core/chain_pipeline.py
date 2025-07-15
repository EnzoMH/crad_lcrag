"""
AI 에이전트 시스템 - Langchain Chain 파이프라인

이 모듈은 여러 개의 Chain을 연결하여 복잡한 AI 처리 
워크플로우를 구성하는 파이프라인 시스템입니다.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, asdict
from enum import Enum

from .chain_manager import ChainManager, ChainConfig, ChainResult, ChainType


class PipelineStepType(Enum):
    """파이프라인 단계 유형"""
    SEQUENTIAL = "sequential"       # 순차 실행
    PARALLEL = "parallel"          # 병렬 실행  
    CONDITIONAL = "conditional"    # 조건부 실행
    LOOP = "loop"                 # 반복 실행
    MERGE = "merge"               # 결과 병합
    FILTER = "filter"             # 결과 필터링
    TRANSFORM = "transform"       # 데이터 변환


@dataclass
class PipelineStep:
    """파이프라인 단계 정의"""
    step_id: str
    step_type: PipelineStepType
    chain_ids: List[str]
    condition_func: Optional[Callable] = None  # 조건부 실행용 함수
    transform_func: Optional[Callable] = None  # 데이터 변환용 함수
    merge_strategy: str = "concat"             # 병합 전략
    max_iterations: int = 1                    # 반복 최대 횟수
    timeout_seconds: Optional[float] = None    # 타임아웃
    retry_count: int = 0                       # 재시도 횟수
    dependencies: List[str] = None             # 의존성 단계들
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


@dataclass
class PipelineConfig:
    """파이프라인 설정"""
    pipeline_id: str
    name: str
    description: str = ""
    steps: List[PipelineStep] = None
    global_timeout: Optional[float] = None     # 전체 파이프라인 타임아웃
    error_handling: str = "stop"               # 오류 처리 방식 (stop, continue, retry)
    max_retries: int = 3                       # 전체 재시도 횟수
    enable_logging: bool = True                # 로깅 활성화
    metadata: Dict[str, Any] = None            # 추가 메타데이터
    
    def __post_init__(self):
        if self.steps is None:
            self.steps = []
        if self.metadata is None:
            self.metadata = {}


@dataclass
class PipelineResult:
    """파이프라인 실행 결과"""
    success: bool
    pipeline_id: str
    execution_time: float
    steps_executed: int
    steps_failed: int
    results: Dict[str, Any]                    # 단계별 결과
    final_output: Any                          # 최종 출력
    error: Optional[str] = None               # 오류 메시지
    step_results: List[Dict[str, Any]] = None  # 각 단계별 상세 결과
    metadata: Dict[str, Any] = None           # 실행 메타데이터
    
    def __post_init__(self):
        if self.step_results is None:
            self.step_results = []
        if self.metadata is None:
            self.metadata = {}


class ChainPipeline:
    """Chain 기반 처리 파이프라인 클래스"""
    
    def __init__(self, chain_manager: ChainManager):
        """
        파이프라인 초기화
        
        Args:
            chain_manager: Chain 관리자
        """
        self.chain_manager = chain_manager
        self.logger = logging.getLogger(__name__)
        
        # 활성 파이프라인 저장소
        self.active_pipelines: Dict[str, PipelineConfig] = {}
        
        # 파이프라인 실행 통계
        self.pipeline_stats = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "execution_times": [],
            "step_stats": {}
        }
        
        self.logger.info("ChainPipeline 초기화 완료")
    
    def register_pipeline(self, config: PipelineConfig) -> bool:
        """
        파이프라인 등록
        
        Args:
            config: 파이프라인 설정
            
        Returns:
            등록 성공 여부
        """
        try:
            # 의존성 검증
            if not self._validate_pipeline_dependencies(config):
                raise ValueError("파이프라인 의존성 검증 실패")
            
            # 체인 존재 여부 확인
            if not self._validate_chain_existence(config):
                raise ValueError("참조된 체인이 존재하지 않음")
            
            self.active_pipelines[config.pipeline_id] = config
            self.logger.info(f"파이프라인 등록 완료: {config.pipeline_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"파이프라인 등록 오류: {str(e)}")
            return False
    
    def _validate_pipeline_dependencies(self, config: PipelineConfig) -> bool:
        """파이프라인 의존성 검증"""
        step_ids = {step.step_id for step in config.steps}
        
        for step in config.steps:
            for dep in step.dependencies:
                if dep not in step_ids:
                    self.logger.error(f"존재하지 않는 의존성: {dep}")
                    return False
        
        # 순환 의존성 검사
        if self._has_circular_dependencies(config.steps):
            self.logger.error("순환 의존성 발견")
            return False
        
        return True
    
    def _has_circular_dependencies(self, steps: List[PipelineStep]) -> bool:
        """순환 의존성 검사"""
        step_deps = {step.step_id: step.dependencies for step in steps}
        
        def visit(step_id: str, visited: set, rec_stack: set) -> bool:
            visited.add(step_id)
            rec_stack.add(step_id)
            
            for dep in step_deps.get(step_id, []):
                if dep not in visited:
                    if visit(dep, visited, rec_stack):
                        return True
                elif dep in rec_stack:
                    return True
            
            rec_stack.remove(step_id)
            return False
        
        visited = set()
        for step in steps:
            if step.step_id not in visited:
                if visit(step.step_id, visited, set()):
                    return True
        
        return False
    
    def _validate_chain_existence(self, config: PipelineConfig) -> bool:
        """체인 존재 여부 확인"""
        active_chains = set(self.chain_manager.active_chains.keys())
        
        for step in config.steps:
            for chain_id in step.chain_ids:
                if chain_id not in active_chains:
                    self.logger.error(f"존재하지 않는 체인: {chain_id}")
                    return False
        
        return True
    
    async def execute_pipeline(self, pipeline_id: str, 
                             initial_input: Dict[str, Any],
                             **kwargs) -> PipelineResult:
        """
        파이프라인 실행
        
        Args:
            pipeline_id: 실행할 파이프라인 ID
            initial_input: 초기 입력 데이터
            **kwargs: 추가 실행 옵션
            
        Returns:
            파이프라인 실행 결과
        """
        start_time = time.time()
        
        try:
            if pipeline_id not in self.active_pipelines:
                raise ValueError(f"파이프라인을 찾을 수 없음: {pipeline_id}")
            
            config = self.active_pipelines[pipeline_id]
            self.logger.info(f"파이프라인 실행 시작: {pipeline_id}")
            
            # 실행 컨텍스트 초기화
            execution_context = {
                "input": initial_input,
                "step_outputs": {},
                "current_data": initial_input,
                "metadata": kwargs
            }
            
            # 단계 실행 순서 결정
            execution_order = self._determine_execution_order(config.steps)
            
            steps_executed = 0
            steps_failed = 0
            step_results = []
            
            # 각 단계 실행
            for step in execution_order:
                try:
                    step_result = await self._execute_pipeline_step(
                        step, execution_context, config
                    )
                    
                    step_results.append({
                        "step_id": step.step_id,
                        "step_type": step.step_type.value,
                        "success": step_result["success"],
                        "execution_time": step_result["execution_time"],
                        "output": step_result["output"]
                    })
                    
                    if step_result["success"]:
                        steps_executed += 1
                        execution_context["step_outputs"][step.step_id] = step_result["output"]
                        execution_context["current_data"] = step_result["output"]
                    else:
                        steps_failed += 1
                        if config.error_handling == "stop":
                            raise Exception(f"단계 실행 실패: {step.step_id}")
                        
                except Exception as e:
                    steps_failed += 1
                    step_results.append({
                        "step_id": step.step_id,
                        "step_type": step.step_type.value,
                        "success": False,
                        "execution_time": 0.0,
                        "output": None,
                        "error": str(e)
                    })
                    
                    if config.error_handling == "stop":
                        raise e
            
            execution_time = time.time() - start_time
            
            # 최종 결과 생성
            final_output = execution_context["current_data"]
            success = steps_failed == 0
            
            # 통계 업데이트
            self._update_pipeline_stats(execution_time, success)
            
            result = PipelineResult(
                success=success,
                pipeline_id=pipeline_id,
                execution_time=execution_time,
                steps_executed=steps_executed,
                steps_failed=steps_failed,
                results=execution_context["step_outputs"],
                final_output=final_output,
                step_results=step_results,
                metadata={
                    "total_steps": len(config.steps),
                    "config": asdict(config)
                }
            )
            
            self.logger.info(f"파이프라인 실행 완료: {pipeline_id} ({execution_time:.2f}초)")
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)
            
            self._update_pipeline_stats(execution_time, False)
            self.logger.error(f"파이프라인 실행 오류: {error_msg}")
            
            return PipelineResult(
                success=False,
                pipeline_id=pipeline_id,
                execution_time=execution_time,
                steps_executed=0,
                steps_failed=len(config.steps) if pipeline_id in self.active_pipelines else 0,
                results={},
                final_output=None,
                error=error_msg
            )
    
    def _determine_execution_order(self, steps: List[PipelineStep]) -> List[PipelineStep]:
        """실행 순서 결정 (토폴로지 정렬)"""
        # 의존성 그래프 생성
        step_map = {step.step_id: step for step in steps}
        in_degree = {step.step_id: 0 for step in steps}
        
        for step in steps:
            for dep in step.dependencies:
                in_degree[step.step_id] += 1
        
        # 토폴로지 정렬
        queue = [step_id for step_id, degree in in_degree.items() if degree == 0]
        ordered_steps = []
        
        while queue:
            current_id = queue.pop(0)
            current_step = step_map[current_id]
            ordered_steps.append(current_step)
            
            # 종속 단계들의 in_degree 감소
            for step in steps:
                if current_id in step.dependencies:
                    in_degree[step.step_id] -= 1
                    if in_degree[step.step_id] == 0:
                        queue.append(step.step_id)
        
        return ordered_steps
    
    async def _execute_pipeline_step(self, step: PipelineStep,
                                   execution_context: Dict[str, Any],
                                   config: PipelineConfig) -> Dict[str, Any]:
        """파이프라인 단계 실행"""
        step_start_time = time.time()
        
        try:
            self.logger.info(f"단계 실행 시작: {step.step_id} ({step.step_type.value})")
            
            # 조건부 실행 확인
            if step.step_type == PipelineStepType.CONDITIONAL and step.condition_func:
                if not step.condition_func(execution_context["current_data"]):
                    self.logger.info(f"조건부 단계 스킵: {step.step_id}")
                    return {
                        "success": True,
                        "output": execution_context["current_data"],
                        "execution_time": time.time() - step_start_time,
                        "skipped": True
                    }
            
            # 단계 유형별 실행
            if step.step_type == PipelineStepType.SEQUENTIAL:
                output = await self._execute_sequential_step(step, execution_context)
            elif step.step_type == PipelineStepType.PARALLEL:
                output = await self._execute_parallel_step(step, execution_context)
            elif step.step_type == PipelineStepType.LOOP:
                output = await self._execute_loop_step(step, execution_context)
            elif step.step_type == PipelineStepType.MERGE:
                output = await self._execute_merge_step(step, execution_context)
            elif step.step_type == PipelineStepType.FILTER:
                output = await self._execute_filter_step(step, execution_context)
            elif step.step_type == PipelineStepType.TRANSFORM:
                output = await self._execute_transform_step(step, execution_context)
            else:
                # 기본값: 순차 실행
                output = await self._execute_sequential_step(step, execution_context)
            
            execution_time = time.time() - step_start_time
            
            self.logger.info(f"단계 실행 완료: {step.step_id} ({execution_time:.2f}초)")
            
            return {
                "success": True,
                "output": output,
                "execution_time": execution_time
            }
            
        except Exception as e:
            execution_time = time.time() - step_start_time
            self.logger.error(f"단계 실행 오류 {step.step_id}: {str(e)}")
            
            return {
                "success": False,
                "output": None,
                "execution_time": execution_time,
                "error": str(e)
            }
    
    async def _execute_sequential_step(self, step: PipelineStep,
                                     execution_context: Dict[str, Any]) -> Any:
        """순차 단계 실행"""
        current_data = execution_context["current_data"]
        
        for chain_id in step.chain_ids:
            result = await self.chain_manager.execute_chain(chain_id, {"input": current_data})
            if not result.success:
                raise Exception(f"체인 실행 실패: {chain_id} - {result.error}")
            current_data = result.output
        
        return current_data
    
    async def _execute_parallel_step(self, step: PipelineStep,
                                   execution_context: Dict[str, Any]) -> Any:
        """병렬 단계 실행"""
        current_data = execution_context["current_data"]
        
        # 모든 체인을 병렬로 실행
        tasks = []
        for chain_id in step.chain_ids:
            task = self.chain_manager.execute_chain(chain_id, {"input": current_data})
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 결과 처리
        outputs = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                raise Exception(f"병렬 체인 실행 실패: {step.chain_ids[i]} - {str(result)}")
            elif not result.success:
                raise Exception(f"병렬 체인 실행 실패: {step.chain_ids[i]} - {result.error}")
            else:
                outputs.append(result.output)
        
        # 병합 전략에 따른 결과 결합
        if step.merge_strategy == "concat":
            return outputs
        elif step.merge_strategy == "first":
            return outputs[0] if outputs else None
        elif step.merge_strategy == "last":
            return outputs[-1] if outputs else None
        else:
            return outputs
    
    async def _execute_loop_step(self, step: PipelineStep,
                               execution_context: Dict[str, Any]) -> Any:
        """반복 단계 실행"""
        current_data = execution_context["current_data"]
        iteration = 0
        
        while iteration < step.max_iterations:
            iteration += 1
            
            # 체인들을 순차적으로 실행
            for chain_id in step.chain_ids:
                result = await self.chain_manager.execute_chain(chain_id, {"input": current_data})
                if not result.success:
                    raise Exception(f"반복 체인 실행 실패: {chain_id} - {result.error}")
                current_data = result.output
            
            # 조건 함수가 있으면 종료 조건 확인
            if step.condition_func and step.condition_func(current_data):
                break
        
        return current_data
    
    async def _execute_merge_step(self, step: PipelineStep,
                                execution_context: Dict[str, Any]) -> Any:
        """병합 단계 실행"""
        # 이전 단계들의 결과를 수집
        step_outputs = execution_context["step_outputs"]
        merge_data = []
        
        for dep_step_id in step.dependencies:
            if dep_step_id in step_outputs:
                merge_data.append(step_outputs[dep_step_id])
        
        # 병합 전략에 따른 데이터 결합
        if step.merge_strategy == "concat":
            if all(isinstance(data, list) for data in merge_data):
                result = []
                for data in merge_data:
                    result.extend(data)
                return result
            else:
                return merge_data
        elif step.merge_strategy == "dict":
            result = {}
            for i, data in enumerate(merge_data):
                result[f"step_{i}"] = data
            return result
        else:
            return merge_data
    
    async def _execute_filter_step(self, step: PipelineStep,
                                 execution_context: Dict[str, Any]) -> Any:
        """필터링 단계 실행"""
        current_data = execution_context["current_data"]
        
        if step.condition_func:
            if isinstance(current_data, list):
                return [item for item in current_data if step.condition_func(item)]
            elif step.condition_func(current_data):
                return current_data
            else:
                return None
        
        return current_data
    
    async def _execute_transform_step(self, step: PipelineStep,
                                    execution_context: Dict[str, Any]) -> Any:
        """변환 단계 실행"""
        current_data = execution_context["current_data"]
        
        if step.transform_func:
            return step.transform_func(current_data)
        
        return current_data
    
    def _update_pipeline_stats(self, execution_time: float, success: bool):
        """파이프라인 통계 업데이트"""
        self.pipeline_stats["total_executions"] += 1
        
        if success:
            self.pipeline_stats["successful_executions"] += 1
        else:
            self.pipeline_stats["failed_executions"] += 1
        
        self.pipeline_stats["execution_times"].append(execution_time)
    
    def get_pipeline_info(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        """파이프라인 정보 조회"""
        if pipeline_id not in self.active_pipelines:
            return None
        
        config = self.active_pipelines[pipeline_id]
        
        return {
            "pipeline_id": pipeline_id,
            "name": config.name,
            "description": config.description,
            "steps": [
                {
                    "step_id": step.step_id,
                    "step_type": step.step_type.value,
                    "chain_ids": step.chain_ids,
                    "dependencies": step.dependencies
                }
                for step in config.steps
            ],
            "total_steps": len(config.steps),
            "config": asdict(config)
        }
    
    def list_active_pipelines(self) -> List[Dict[str, Any]]:
        """활성 파이프라인 목록 조회"""
        return [self.get_pipeline_info(pipeline_id) 
                for pipeline_id in self.active_pipelines.keys()]
    
    def delete_pipeline(self, pipeline_id: str) -> bool:
        """파이프라인 삭제"""
        if pipeline_id in self.active_pipelines:
            del self.active_pipelines[pipeline_id]
            self.logger.info(f"파이프라인 삭제 완료: {pipeline_id}")
            return True
        return False
    
    def get_pipeline_stats(self) -> Dict[str, Any]:
        """파이프라인 실행 통계 조회"""
        stats = self.pipeline_stats.copy()
        
        if stats["execution_times"]:
            stats["avg_execution_time"] = sum(stats["execution_times"]) / len(stats["execution_times"])
            stats["min_execution_time"] = min(stats["execution_times"])
            stats["max_execution_time"] = max(stats["execution_times"])
        else:
            stats["avg_execution_time"] = 0.0
            stats["min_execution_time"] = 0.0
            stats["max_execution_time"] = 0.0
        
        if stats["total_executions"] > 0:
            stats["success_rate"] = stats["successful_executions"] / stats["total_executions"]
        else:
            stats["success_rate"] = 0.0
        
        return stats


# 사전 정의된 파이프라인 템플릿들
def create_contact_enrichment_pipeline() -> PipelineConfig:
    """연락처 보강 파이프라인 템플릿"""
    return PipelineConfig(
        pipeline_id="contact_enrichment_pipeline",
        name="연락처 정보 보강 파이프라인",
        description="기관 정보를 바탕으로 연락처를 자동 보강하는 파이프라인",
        steps=[
            PipelineStep(
                step_id="search_strategy",
                step_type=PipelineStepType.SEQUENTIAL,
                chain_ids=["search_strategy_chain"]
            ),
            PipelineStep(
                step_id="contact_extraction",
                step_type=PipelineStepType.SEQUENTIAL,
                chain_ids=["contact_extraction_chain"],
                dependencies=["search_strategy"]
            ),
            PipelineStep(
                step_id="validation",
                step_type=PipelineStepType.SEQUENTIAL,
                chain_ids=["data_validation_chain"],
                dependencies=["contact_extraction"]
            )
        ],
        error_handling="continue",
        max_retries=2
    )


def create_document_analysis_pipeline() -> PipelineConfig:
    """문서 분석 파이프라인 템플릿"""
    return PipelineConfig(
        pipeline_id="document_analysis_pipeline",
        name="문서 분석 파이프라인",
        description="대용량 문서를 분석하고 요약하는 파이프라인",
        steps=[
            PipelineStep(
                step_id="document_chunking",
                step_type=PipelineStepType.TRANSFORM,
                chain_ids=[],
                transform_func=lambda x: x.get("text", "").split("\n\n")  # 문단별 분할
            ),
            PipelineStep(
                step_id="parallel_analysis",
                step_type=PipelineStepType.PARALLEL,
                chain_ids=["document_analysis_chain"],
                dependencies=["document_chunking"],
                merge_strategy="concat"
            ),
            PipelineStep(
                step_id="final_summary",
                step_type=PipelineStepType.SEQUENTIAL,
                chain_ids=["text_summarization_chain"],
                dependencies=["parallel_analysis"]
            )
        ],
        global_timeout=300.0,  # 5분 타임아웃
        error_handling="retry"
    )


def create_quality_assessment_pipeline() -> PipelineConfig:
    """품질 평가 파이프라인 템플릿"""
    return PipelineConfig(
        pipeline_id="quality_assessment_pipeline",
        name="데이터 품질 평가 파이프라인",
        description="수집된 데이터의 품질을 종합적으로 평가하는 파이프라인",
        steps=[
            PipelineStep(
                step_id="format_validation",
                step_type=PipelineStepType.SEQUENTIAL,
                chain_ids=["data_validation_chain"]
            ),
            PipelineStep(
                step_id="content_analysis",
                step_type=PipelineStepType.PARALLEL,
                chain_ids=["quality_assessment_chain", "document_analysis_chain"],
                merge_strategy="dict"
            ),
            PipelineStep(
                step_id="optimization_suggestions",
                step_type=PipelineStepType.SEQUENTIAL,
                chain_ids=["performance_optimization_chain"],
                dependencies=["format_validation", "content_analysis"]
            )
        ],
        error_handling="continue"
    )


# 파이프라인 템플릿 팩토리
PIPELINE_TEMPLATES = {
    "contact_enrichment": create_contact_enrichment_pipeline,
    "document_analysis": create_document_analysis_pipeline,
    "quality_assessment": create_quality_assessment_pipeline
}


def get_pipeline_template(template_name: str) -> Optional[PipelineConfig]:
    """
    파이프라인 템플릿 가져오기
    
    Args:
        template_name: 템플릿 이름
        
    Returns:
        파이프라인 설정 또는 None
    """
    if template_name in PIPELINE_TEMPLATES:
        return PIPELINE_TEMPLATES[template_name]()
    return None


def list_pipeline_templates() -> List[str]:
    """사용 가능한 파이프라인 템플릿 목록"""
    return list(PIPELINE_TEMPLATES.keys()) 