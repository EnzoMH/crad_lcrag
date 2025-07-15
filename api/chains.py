"""
🔗 Chain 관리 API

Features:
- Chain 생성/삭제/조회
- Chain 실행 및 관리
- Pipeline 관리
- Chain 템플릿 관리
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field

from aiagent.core import ChainService, ChainManager, ChainPipeline
from aiagent.utils import GeminiClient, PromptManager

logger = logging.getLogger(__name__)
router = APIRouter()


# 글로벌 의존성
async def get_chain_service() -> ChainService:
    """Chain 서비스 의존성 - 메인 앱에서 주입"""
    from app import agent_system
    if not agent_system:
        raise HTTPException(status_code=503, detail="AI 에이전트 시스템이 초기화되지 않았습니다")
    
    # ChainService는 agent_system에서 가져옴
    if not hasattr(agent_system, 'chain_service'):
        # 임시로 ChainService 생성
        chain_service = ChainService(
            gemini_client=agent_system.gemini_client,
            prompt_manager=agent_system.prompt_manager if hasattr(agent_system, 'prompt_manager') else PromptManager()
        )
        agent_system.chain_service = chain_service
    
    return agent_system.chain_service


# Enum 정의
class ChainType(str, Enum):
    SIMPLE = "simple"
    SEQUENTIAL = "sequential"
    CONDITIONAL = "conditional"
    PARALLEL = "parallel"
    LOOP = "loop"


class ChainStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Pydantic 모델들
class ChainCreateRequest(BaseModel):
    """Chain 생성 요청"""
    name: str = Field(..., description="Chain 이름")
    description: Optional[str] = Field(None, description="Chain 설명")
    chain_type: ChainType = Field(default=ChainType.SIMPLE, description="Chain 타입")
    prompt_template: str = Field(..., description="프롬프트 템플릿")
    output_parser: Optional[str] = Field(None, description="출력 파서")
    config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Chain 설정")


class ChainExecuteRequest(BaseModel):
    """Chain 실행 요청"""
    input_data: Dict[str, Any] = Field(..., description="입력 데이터")
    config_override: Optional[Dict[str, Any]] = Field(None, description="설정 오버라이드")
    timeout: int = Field(default=300, ge=30, le=1800, description="실행 타임아웃 (초)")


class PipelineCreateRequest(BaseModel):
    """Pipeline 생성 요청"""
    name: str = Field(..., description="Pipeline 이름")
    description: Optional[str] = Field(None, description="Pipeline 설명")
    steps: List[Dict[str, Any]] = Field(..., description="Pipeline 단계들")
    config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Pipeline 설정")


class ChainResponse(BaseModel):
    """Chain 응답"""
    chain_id: str
    name: str
    description: Optional[str]
    chain_type: ChainType
    status: ChainStatus
    created_at: datetime
    config: Dict[str, Any]
    metrics: Dict[str, Any]


class ExecutionResponse(BaseModel):
    """실행 응답"""
    execution_id: str
    chain_id: str
    status: ChainStatus
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    execution_time: Optional[float] = None


class PipelineResponse(BaseModel):
    """Pipeline 응답"""
    pipeline_id: str
    name: str
    description: Optional[str]
    steps_count: int
    status: str
    created_at: datetime
    config: Dict[str, Any]


# Chain 관리 API
@router.get("/", summary="Chain 목록 조회")
async def list_chains(
    chain_service: ChainService = Depends(get_chain_service)
) -> List[ChainResponse]:
    """등록된 모든 Chain 목록을 조회합니다."""
    try:
        chains = await chain_service.get_chains()
        
        return [
            ChainResponse(
                chain_id=chain["chain_id"],
                name=chain["name"],
                description=chain.get("description"),
                chain_type=ChainType(chain["chain_type"]),
                status=ChainStatus(chain["status"]),
                created_at=chain["created_at"],
                config=chain.get("config", {}),
                metrics=chain.get("metrics", {})
            )
            for chain in chains
        ]
        
    except Exception as e:
        logger.error(f"Chain 목록 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chain 목록 조회 실패: {str(e)}")


@router.get("/{chain_id}", summary="특정 Chain 조회")
async def get_chain(
    chain_id: str,
    chain_service: ChainService = Depends(get_chain_service)
) -> ChainResponse:
    """특정 Chain의 상세 정보를 조회합니다."""
    try:
        chain = await chain_service.get_chain(chain_id)
        if not chain:
            raise HTTPException(status_code=404, detail=f"Chain을 찾을 수 없습니다: {chain_id}")
        
        return ChainResponse(
            chain_id=chain["chain_id"],
            name=chain["name"],
            description=chain.get("description"),
            chain_type=ChainType(chain["chain_type"]),
            status=ChainStatus(chain["status"]),
            created_at=chain["created_at"],
            config=chain.get("config", {}),
            metrics=chain.get("metrics", {})
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chain 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chain 조회 실패: {str(e)}")


@router.post("/", summary="새 Chain 생성")
async def create_chain(
    request: ChainCreateRequest,
    chain_service: ChainService = Depends(get_chain_service)
) -> ChainResponse:
    """새로운 Chain을 생성합니다."""
    try:
        chain_id = await chain_service.create_chain(
            name=request.name,
            description=request.description,
            chain_type=request.chain_type.value,
            prompt_template=request.prompt_template,
            output_parser=request.output_parser,
            config=request.config
        )
        
        # 생성된 Chain 정보 조회
        chain = await chain_service.get_chain(chain_id)
        
        return ChainResponse(
            chain_id=chain["chain_id"],
            name=chain["name"],
            description=chain.get("description"),
            chain_type=ChainType(chain["chain_type"]),
            status=ChainStatus(chain["status"]),
            created_at=chain["created_at"],
            config=chain.get("config", {}),
            metrics=chain.get("metrics", {})
        )
        
    except Exception as e:
        logger.error(f"Chain 생성 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chain 생성 실패: {str(e)}")


@router.delete("/{chain_id}", summary="Chain 삭제")
async def delete_chain(
    chain_id: str,
    chain_service: ChainService = Depends(get_chain_service)
) -> Dict[str, str]:
    """특정 Chain을 삭제합니다."""
    try:
        success = await chain_service.delete_chain(chain_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Chain을 찾을 수 없습니다: {chain_id}")
        
        return {"message": f"Chain이 성공적으로 삭제되었습니다: {chain_id}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chain 삭제 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chain 삭제 실패: {str(e)}")


# Chain 실행 API
@router.post("/{chain_id}/execute", summary="Chain 실행")
async def execute_chain(
    chain_id: str,
    request: ChainExecuteRequest,
    background_tasks: BackgroundTasks,
    chain_service: ChainService = Depends(get_chain_service)
) -> ExecutionResponse:
    """Chain을 실행합니다."""
    try:
        # 실행 ID 생성
        execution_id = f"{chain_id}_{int(datetime.now().timestamp() * 1000)}"
        
        # 백그라운드에서 Chain 실행
        background_tasks.add_task(
            _execute_chain_background,
            chain_service,
            chain_id,
            execution_id,
            request
        )
        
        return ExecutionResponse(
            execution_id=execution_id,
            chain_id=chain_id,
            status=ChainStatus.RUNNING,
            input_data=request.input_data,
            started_at=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Chain 실행 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chain 실행 실패: {str(e)}")


@router.get("/{chain_id}/executions/{execution_id}", summary="Chain 실행 상태 조회")
async def get_execution_status(
    chain_id: str,
    execution_id: str,
    chain_service: ChainService = Depends(get_chain_service)
) -> ExecutionResponse:
    """Chain 실행 상태를 조회합니다."""
    try:
        execution = await chain_service.get_execution(execution_id)
        if not execution:
            raise HTTPException(status_code=404, detail=f"실행을 찾을 수 없습니다: {execution_id}")
        
        return ExecutionResponse(
            execution_id=execution["execution_id"],
            chain_id=execution["chain_id"],
            status=ChainStatus(execution["status"]),
            input_data=execution["input_data"],
            output_data=execution.get("output_data"),
            error=execution.get("error"),
            started_at=execution["started_at"],
            completed_at=execution.get("completed_at"),
            execution_time=execution.get("execution_time")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"실행 상태 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"실행 상태 조회 실패: {str(e)}")


@router.post("/{chain_id}/executions/{execution_id}/cancel", summary="Chain 실행 취소")
async def cancel_execution(
    chain_id: str,
    execution_id: str,
    chain_service: ChainService = Depends(get_chain_service)
) -> Dict[str, str]:
    """Chain 실행을 취소합니다."""
    try:
        success = await chain_service.cancel_execution(execution_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"실행을 찾을 수 없거나 취소할 수 없습니다: {execution_id}")
        
        return {"message": f"Chain 실행이 취소되었습니다: {execution_id}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"실행 취소 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"실행 취소 실패: {str(e)}")


# Pipeline 관리 API
@router.get("/pipelines", summary="Pipeline 목록 조회")
async def list_pipelines(
    chain_service: ChainService = Depends(get_chain_service)
) -> List[PipelineResponse]:
    """등록된 모든 Pipeline 목록을 조회합니다."""
    try:
        pipelines = await chain_service.get_pipelines()
        
        return [
            PipelineResponse(
                pipeline_id=pipeline["pipeline_id"],
                name=pipeline["name"],
                description=pipeline.get("description"),
                steps_count=pipeline["steps_count"],
                status=pipeline["status"],
                created_at=pipeline["created_at"],
                config=pipeline.get("config", {})
            )
            for pipeline in pipelines
        ]
        
    except Exception as e:
        logger.error(f"Pipeline 목록 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Pipeline 목록 조회 실패: {str(e)}")


@router.post("/pipelines", summary="새 Pipeline 생성")
async def create_pipeline(
    request: PipelineCreateRequest,
    chain_service: ChainService = Depends(get_chain_service)
) -> PipelineResponse:
    """새로운 Pipeline을 생성합니다."""
    try:
        pipeline_id = await chain_service.create_pipeline(
            name=request.name,
            description=request.description,
            steps=request.steps,
            config=request.config
        )
        
        # 생성된 Pipeline 정보 조회
        pipeline = await chain_service.get_pipeline(pipeline_id)
        
        return PipelineResponse(
            pipeline_id=pipeline["pipeline_id"],
            name=pipeline["name"],
            description=pipeline.get("description"),
            steps_count=pipeline["steps_count"],
            status=pipeline["status"],
            created_at=pipeline["created_at"],
            config=pipeline.get("config", {})
        )
        
    except Exception as e:
        logger.error(f"Pipeline 생성 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Pipeline 생성 실패: {str(e)}")


@router.post("/pipelines/{pipeline_id}/execute", summary="Pipeline 실행")
async def execute_pipeline(
    pipeline_id: str,
    request: ChainExecuteRequest,
    background_tasks: BackgroundTasks,
    chain_service: ChainService = Depends(get_chain_service)
) -> ExecutionResponse:
    """Pipeline을 실행합니다."""
    try:
        # 실행 ID 생성
        execution_id = f"pipeline_{pipeline_id}_{int(datetime.now().timestamp() * 1000)}"
        
        # 백그라운드에서 Pipeline 실행
        background_tasks.add_task(
            _execute_pipeline_background,
            chain_service,
            pipeline_id,
            execution_id,
            request
        )
        
        return ExecutionResponse(
            execution_id=execution_id,
            chain_id=pipeline_id,
            status=ChainStatus.RUNNING,
            input_data=request.input_data,
            started_at=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Pipeline 실행 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Pipeline 실행 실패: {str(e)}")


# Chain 템플릿 API
@router.get("/templates", summary="Chain 템플릿 목록")
async def list_chain_templates(
    chain_service: ChainService = Depends(get_chain_service)
) -> List[Dict[str, Any]]:
    """사용 가능한 Chain 템플릿 목록을 조회합니다."""
    try:
        templates = await chain_service.get_chain_templates()
        return templates
        
    except Exception as e:
        logger.error(f"Chain 템플릿 목록 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"템플릿 목록 조회 실패: {str(e)}")


@router.get("/templates/{template_name}", summary="특정 Chain 템플릿 조회")
async def get_chain_template(
    template_name: str,
    chain_service: ChainService = Depends(get_chain_service)
) -> Dict[str, Any]:
    """특정 Chain 템플릿의 상세 정보를 조회합니다."""
    try:
        template = await chain_service.get_chain_template(template_name)
        if not template:
            raise HTTPException(status_code=404, detail=f"템플릿을 찾을 수 없습니다: {template_name}")
        
        return template
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chain 템플릿 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"템플릿 조회 실패: {str(e)}")


@router.post("/templates/{template_name}/create", summary="템플릿으로 Chain 생성")
async def create_chain_from_template(
    template_name: str,
    name: str,
    config_override: Optional[Dict[str, Any]] = None,
    chain_service: ChainService = Depends(get_chain_service)
) -> ChainResponse:
    """템플릿을 사용하여 새로운 Chain을 생성합니다."""
    try:
        chain_id = await chain_service.create_chain_from_template(
            template_name=template_name,
            name=name,
            config_override=config_override or {}
        )
        
        # 생성된 Chain 정보 조회
        chain = await chain_service.get_chain(chain_id)
        
        return ChainResponse(
            chain_id=chain["chain_id"],
            name=chain["name"],
            description=chain.get("description"),
            chain_type=ChainType(chain["chain_type"]),
            status=ChainStatus(chain["status"]),
            created_at=chain["created_at"],
            config=chain.get("config", {}),
            metrics=chain.get("metrics", {})
        )
        
    except Exception as e:
        logger.error(f"템플릿으로 Chain 생성 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"템플릿으로 Chain 생성 실패: {str(e)}")


# Chain 메트릭 및 통계 API
@router.get("/{chain_id}/metrics", summary="Chain 메트릭 조회")
async def get_chain_metrics(
    chain_id: str,
    chain_service: ChainService = Depends(get_chain_service)
) -> Dict[str, Any]:
    """Chain의 상세 성능 메트릭을 조회합니다."""
    try:
        metrics = await chain_service.get_chain_metrics(chain_id)
        if not metrics:
            raise HTTPException(status_code=404, detail=f"Chain을 찾을 수 없습니다: {chain_id}")
        
        return {
            "chain_id": chain_id,
            "metrics": metrics,
            "timestamp": datetime.now()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chain 메트릭 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"메트릭 조회 실패: {str(e)}")


@router.get("/statistics/overview", summary="Chain 시스템 통계")
async def get_chains_statistics(
    chain_service: ChainService = Depends(get_chain_service)
) -> Dict[str, Any]:
    """Chain 시스템의 전체 통계를 조회합니다."""
    try:
        stats = await chain_service.get_statistics()
        return {
            "timestamp": datetime.now(),
            "total_chains": stats.get("total_chains", 0),
            "active_chains": stats.get("active_chains", 0),
            "total_executions": stats.get("total_executions", 0),
            "successful_executions": stats.get("successful_executions", 0),
            "failed_executions": stats.get("failed_executions", 0),
            "average_execution_time": stats.get("average_execution_time", 0.0),
            "chain_types_distribution": stats.get("chain_types_distribution", {}),
            "recent_activity": stats.get("recent_activity", [])
        }
        
    except Exception as e:
        logger.error(f"Chain 통계 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"통계 조회 실패: {str(e)}")


# 유틸리티 함수들
async def _execute_chain_background(
    chain_service: ChainService,
    chain_id: str,
    execution_id: str,
    request: ChainExecuteRequest
):
    """백그라운드에서 Chain을 실행합니다."""
    try:
        logger.info(f"Chain 실행 시작: {execution_id}")
        
        result = await chain_service.execute_chain(
            chain_id=chain_id,
            input_data=request.input_data,
            config_override=request.config_override,
            timeout=request.timeout
        )
        
        # 실행 결과 저장
        await chain_service.save_execution_result(
            execution_id=execution_id,
            result=result
        )
        
        logger.info(f"Chain 실행 완료: {execution_id}")
        
    except Exception as e:
        logger.error(f"Chain 백그라운드 실행 오류 {execution_id}: {str(e)}")
        
        # 오류 결과 저장
        await chain_service.save_execution_result(
            execution_id=execution_id,
            result={"error": str(e), "status": "failed"}
        )


async def _execute_pipeline_background(
    chain_service: ChainService,
    pipeline_id: str,
    execution_id: str,
    request: ChainExecuteRequest
):
    """백그라운드에서 Pipeline을 실행합니다."""
    try:
        logger.info(f"Pipeline 실행 시작: {execution_id}")
        
        result = await chain_service.execute_pipeline(
            pipeline_id=pipeline_id,
            input_data=request.input_data,
            config_override=request.config_override,
            timeout=request.timeout
        )
        
        # 실행 결과 저장
        await chain_service.save_execution_result(
            execution_id=execution_id,
            result=result
        )
        
        logger.info(f"Pipeline 실행 완료: {execution_id}")
        
    except Exception as e:
        logger.error(f"Pipeline 백그라운드 실행 오류 {execution_id}: {str(e)}")
        
        # 오류 결과 저장
        await chain_service.save_execution_result(
            execution_id=execution_id,
            result={"error": str(e), "status": "failed"}
        ) 