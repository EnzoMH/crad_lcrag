"""
🧠 AI 에이전트 관리 API

Features:
- 에이전트 생성/삭제/조회
- 에이전트 상태 관리
- 에이전트 작업 실행
- 에이전트 설정 관리
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field

from aiagent.core import AIAgentSystem
from aiagent.agents import (
    SearchStrategyAgent,
    ContactAgent,
    ValidationAgent,
    OptimizerAgent
)
from aiagent.utils import AgentConfig

logger = logging.getLogger(__name__)
router = APIRouter()

# 글로벌 의존성
async def get_agent_system() -> AIAgentSystem:
    """AI 에이전트 시스템 의존성 - 메인 앱에서 주입"""
    from app import agent_system
    if not agent_system:
        raise HTTPException(status_code=503, detail="AI 에이전트 시스템이 초기화되지 않았습니다")
    return agent_system


# Pydantic 모델들
class AgentCreateRequest(BaseModel):
    """에이전트 생성 요청"""
    name: str = Field(..., description="에이전트 이름")
    type: str = Field(..., description="에이전트 타입 (search_strategy, contact, validation, optimizer)")
    description: Optional[str] = Field(None, description="에이전트 설명")
    config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="에이전트 설정")


class AgentTaskRequest(BaseModel):
    """에이전트 작업 요청"""
    task_type: str = Field(..., description="작업 타입")
    data: Dict[str, Any] = Field(..., description="작업 데이터")
    priority: int = Field(default=1, description="작업 우선순위 (1-10)")
    timeout: int = Field(default=300, description="작업 타임아웃 (초)")


class AgentConfigUpdate(BaseModel):
    """에이전트 설정 업데이트"""
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="AI 모델 온도")
    max_tokens: Optional[int] = Field(None, gt=0, description="최대 토큰 수")
    retry_count: Optional[int] = Field(None, ge=0, description="재시도 횟수")
    timeout: Optional[int] = Field(None, gt=0, description="타임아웃 (초)")


class AgentResponse(BaseModel):
    """에이전트 응답"""
    id: str
    name: str
    type: str
    status: str
    created_at: datetime
    config: Dict[str, Any]
    metrics: Dict[str, Any]


class TaskResponse(BaseModel):
    """작업 응답"""
    task_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    execution_time: Optional[float] = None


# 에이전트 관리 API
@router.get("/", summary="에이전트 목록 조회")
async def list_agents(
    system: AIAgentSystem = Depends(get_agent_system)
) -> List[AgentResponse]:
    """등록된 모든 에이전트 목록을 조회합니다."""
    try:
        agents = []
        for agent_id, agent in system.agents.items():
            agents.append(AgentResponse(
                id=agent_id,
                name=agent.config.name,
                type=agent.__class__.__name__,
                status=agent.status.value,
                created_at=datetime.now(),  # 실제로는 생성 시간을 저장해야 함
                config={
                    "temperature": agent.config.temperature,
                    "max_tokens": agent.config.max_tokens,
                    "max_retries": agent.config.max_retries,
                    "timeout": agent.config.timeout
                },
                metrics={
                    "total_requests": agent.metrics.total_requests,
                    "successful_requests": agent.metrics.successful_requests,
                    "failed_requests": agent.metrics.failed_requests,
                    "average_response_time": agent.metrics.average_response_time
                }
            ))
        
        return agents
        
    except Exception as e:
        logger.error(f"에이전트 목록 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"에이전트 목록 조회 실패: {str(e)}")


@router.get("/{agent_id}", summary="특정 에이전트 조회")
async def get_agent(
    agent_id: str,
    system: AIAgentSystem = Depends(get_agent_system)
) -> AgentResponse:
    """특정 에이전트의 상세 정보를 조회합니다."""
    try:
        agent = system.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=f"에이전트를 찾을 수 없습니다: {agent_id}")
        
        return AgentResponse(
            id=agent_id,
            name=agent.config.name,
            type=agent.__class__.__name__,
            status=agent.status.value,
            created_at=datetime.now(),
            config={
                "temperature": agent.config.temperature,
                "max_tokens": agent.config.max_tokens,
                "max_retries": agent.config.max_retries,
                "timeout": agent.config.timeout
            },
            metrics={
                "total_requests": agent.metrics.total_requests,
                "successful_requests": agent.metrics.successful_requests,
                "failed_requests": agent.metrics.failed_requests,
                "average_response_time": agent.metrics.average_response_time
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"에이전트 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"에이전트 조회 실패: {str(e)}")


@router.post("/", summary="새 에이전트 생성")
async def create_agent(
    request: AgentCreateRequest,
    system: AIAgentSystem = Depends(get_agent_system)
) -> AgentResponse:
    """새로운 AI 에이전트를 생성합니다."""
    try:
        # 에이전트 타입별 클래스 매핑
        agent_classes = {
            "search_strategy": SearchStrategyAgent,
            "contact": ContactAgent,
            "validation": ValidationAgent,
            "optimizer": OptimizerAgent
        }
        
        if request.type not in agent_classes:
            raise HTTPException(
                status_code=400, 
                detail=f"지원하지 않는 에이전트 타입: {request.type}"
            )
        
        # 에이전트 설정 생성
        config = AgentConfig(
            name=request.name,
            description=request.description or f"{request.type} 에이전트",
            **request.config
        )
        
        # 에이전트 생성 및 등록
        agent_class = agent_classes[request.type]
        agent = agent_class(config)
        agent_id = await system.register_agent(agent)
        
        return AgentResponse(
            id=agent_id,
            name=agent.config.name,
            type=agent.__class__.__name__,
            status=agent.status.value,
            created_at=datetime.now(),
            config={
                "temperature": agent.config.temperature,
                "max_tokens": agent.config.max_tokens,
                "max_retries": agent.config.max_retries,
                "timeout": agent.config.timeout
            },
            metrics={
                "total_requests": agent.metrics.total_requests,
                "successful_requests": agent.metrics.successful_requests,
                "failed_requests": agent.metrics.failed_requests,
                "average_response_time": agent.metrics.average_response_time
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"에이전트 생성 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"에이전트 생성 실패: {str(e)}")


@router.delete("/{agent_id}", summary="에이전트 삭제")
async def delete_agent(
    agent_id: str,
    system: AIAgentSystem = Depends(get_agent_system)
) -> Dict[str, str]:
    """특정 에이전트를 삭제합니다."""
    try:
        success = await system.unregister_agent(agent_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"에이전트를 찾을 수 없습니다: {agent_id}")
        
        return {"message": f"에이전트가 성공적으로 삭제되었습니다: {agent_id}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"에이전트 삭제 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"에이전트 삭제 실패: {str(e)}")


@router.put("/{agent_id}/config", summary="에이전트 설정 업데이트")
async def update_agent_config(
    agent_id: str,
    config_update: AgentConfigUpdate,
    system: AIAgentSystem = Depends(get_agent_system)
) -> AgentResponse:
    """에이전트의 설정을 업데이트합니다."""
    try:
        agent = system.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=f"에이전트를 찾을 수 없습니다: {agent_id}")
        
        # 설정 업데이트
        update_data = config_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            if hasattr(agent.config, key):
                setattr(agent.config, key, value)
        
        return AgentResponse(
            id=agent_id,
            name=agent.config.name,
            type=agent.__class__.__name__,
            status=agent.status.value,
            created_at=datetime.now(),
            config={
                "temperature": agent.config.temperature,
                "max_tokens": agent.config.max_tokens,
                "max_retries": agent.config.max_retries,
                "timeout": agent.config.timeout
            },
            metrics={
                "total_requests": agent.metrics.total_requests,
                "successful_requests": agent.metrics.successful_requests,
                "failed_requests": agent.metrics.failed_requests,
                "average_response_time": agent.metrics.average_response_time
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"에이전트 설정 업데이트 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"설정 업데이트 실패: {str(e)}")


# 에이전트 작업 실행 API
@router.post("/{agent_id}/tasks", summary="에이전트 작업 실행")
async def execute_agent_task(
    agent_id: str,
    task_request: AgentTaskRequest,
    background_tasks: BackgroundTasks,
    system: AIAgentSystem = Depends(get_agent_system)
) -> TaskResponse:
    """에이전트에게 작업을 실행하도록 요청합니다."""
    try:
        agent = system.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=f"에이전트를 찾을 수 없습니다: {agent_id}")
        
        # 작업 ID 생성
        task_id = f"{agent_id}_{int(datetime.now().timestamp() * 1000)}"
        
        # 백그라운드에서 작업 실행
        background_tasks.add_task(
            _execute_task_background,
            agent,
            task_id,
            task_request
        )
        
        return TaskResponse(
            task_id=task_id,
            status="running",
            created_at=datetime.now()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"작업 실행 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"작업 실행 실패: {str(e)}")


@router.get("/{agent_id}/tasks/{task_id}", summary="작업 상태 조회")
async def get_task_status(
    agent_id: str,
    task_id: str
) -> TaskResponse:
    """특정 작업의 실행 상태를 조회합니다."""
    try:
        # 실제로는 작업 상태 저장소에서 조회해야 함
        # 여기서는 간단한 예시로 구현
        return TaskResponse(
            task_id=task_id,
            status="completed",
            result={"message": "작업이 완료되었습니다"},
            created_at=datetime.now(),
            completed_at=datetime.now(),
            execution_time=5.0
        )
        
    except Exception as e:
        logger.error(f"작업 상태 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"작업 상태 조회 실패: {str(e)}")


# 유틸리티 함수들
async def _execute_task_background(agent, task_id: str, task_request: AgentTaskRequest):
    """백그라운드에서 에이전트 작업을 실행합니다."""
    try:
        logger.info(f"작업 시작: {task_id}")
        
        # 에이전트 작업 실행
        result = await agent.process(task_request.data)
        
        logger.info(f"작업 완료: {task_id}")
        
        # 실제로는 작업 결과를 저장소에 저장해야 함
        
    except Exception as e:
        logger.error(f"백그라운드 작업 오류 {task_id}: {str(e)}")


# 에이전트 상태 관리 API
@router.post("/{agent_id}/start", summary="에이전트 시작")
async def start_agent(
    agent_id: str,
    system: AIAgentSystem = Depends(get_agent_system)
) -> Dict[str, str]:
    """에이전트를 시작상태로 변경합니다."""
    try:
        agent = system.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=f"에이전트를 찾을 수 없습니다: {agent_id}")
        
        await agent.start()
        return {"message": f"에이전트가 시작되었습니다: {agent_id}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"에이전트 시작 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"에이전트 시작 실패: {str(e)}")


@router.post("/{agent_id}/stop", summary="에이전트 중지")
async def stop_agent(
    agent_id: str,
    system: AIAgentSystem = Depends(get_agent_system)
) -> Dict[str, str]:
    """에이전트를 중지상태로 변경합니다."""
    try:
        agent = system.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=f"에이전트를 찾을 수 없습니다: {agent_id}")
        
        await agent.stop()
        return {"message": f"에이전트가 중지되었습니다: {agent_id}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"에이전트 중지 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"에이전트 중지 실패: {str(e)}")


@router.get("/{agent_id}/metrics", summary="에이전트 메트릭 조회")
async def get_agent_metrics(
    agent_id: str,
    system: AIAgentSystem = Depends(get_agent_system)
) -> Dict[str, Any]:
    """에이전트의 상세 성능 메트릭을 조회합니다."""
    try:
        agent = system.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=f"에이전트를 찾을 수 없습니다: {agent_id}")
        
        return {
            "agent_id": agent_id,
            "agent_name": agent.config.name,
            "metrics": {
                "total_requests": agent.metrics.total_requests,
                "successful_requests": agent.metrics.successful_requests,
                "failed_requests": agent.metrics.failed_requests,
                "average_response_time": agent.metrics.average_response_time,
                "last_error": agent.metrics.last_error,
                "uptime": agent.get_uptime() if hasattr(agent, 'get_uptime') else 0
            },
            "status": agent.status.value,
            "timestamp": datetime.now()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"에이전트 메트릭 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"메트릭 조회 실패: {str(e)}") 