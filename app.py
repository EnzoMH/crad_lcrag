"""
🚀 AI 에이전트 시스템 - FastAPI 메인 애플리케이션

Features:
- AI 에이전트 시스템 통합
- RESTful API 엔드포인트
- 웹 UI 인터페이스
- 실시간 모니터링
- 성능 최적화
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional

import uvicorn
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from aiagent.core import (
    AIAgentSystem, 
    PerformanceMonitor,
    MonitoringIntegration,
    CrawlingAgentIntegration,
    IntelligentCrawlingService
)
from aiagent.utils import GeminiClient
from aiagent.agents import (
    SearchStrategyAgent,
    ContactAgent, 
    ValidationAgent,
    OptimizerAgent
)
from config import get_config, validate_config

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 글로벌 변수
agent_system: Optional[AIAgentSystem] = None
performance_monitor: Optional[PerformanceMonitor] = None
monitoring_integration: Optional[MonitoringIntegration] = None
crawling_integration: Optional[CrawlingAgentIntegration] = None
intelligent_crawling_service: Optional[IntelligentCrawlingService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 애플리케이션 생명주기 관리
    - 시작 시: AI 에이전트 시스템 초기화
    - 종료 시: 리소스 정리
    """
    global agent_system, performance_monitor, monitoring_integration
    global crawling_integration, intelligent_crawling_service
    
    try:
        logger.info("🚀 AI 에이전트 시스템 초기화 시작...")
        
        # 1. AI 에이전트 시스템 초기화
        agent_system = AIAgentSystem()
        await agent_system.initialize()
        
        # 2. 성능 모니터링 시스템 초기화
        performance_monitor = PerformanceMonitor()
        await performance_monitor.start_monitoring()
        
        # 3. 통합 모니터링 시스템 초기화
        monitoring_integration = MonitoringIntegration(
            agent_system=agent_system,
            performance_monitor=performance_monitor
        )
        await monitoring_integration.start_monitoring()
        
        # 4. 크롤링 시스템 통합 초기화
        crawling_integration = CrawlingAgentIntegration(agent_system)
        
        # 5. 지능형 크롤링 서비스 초기화
        intelligent_crawling_service = IntelligentCrawlingService(crawling_integration)
        await intelligent_crawling_service.start_service()
        
        logger.info("✅ AI 에이전트 시스템 초기화 완료!")
        
        yield
        
    except Exception as e:
        logger.error(f"❌ 시스템 초기화 오류: {str(e)}")
        raise
    
    finally:
        # 리소스 정리
        logger.info("🔄 시스템 종료 중...")
        
        try:
            if intelligent_crawling_service:
                await intelligent_crawling_service.stop_service()
            
            if monitoring_integration:
                await monitoring_integration.stop_monitoring()
            
            if performance_monitor:
                await performance_monitor.stop_monitoring()
            
            if agent_system:
                await agent_system.shutdown()
                
            logger.info("✅ 시스템 종료 완료")
            
        except Exception as e:
            logger.error(f"❌ 시스템 종료 오류: {str(e)}")


# 설정 로드 및 검증
config = get_config()
config_errors = validate_config()
if config_errors:
    logger.warning(f"설정 검증 경고: {config_errors}")

# FastAPI 애플리케이션 생성
app = FastAPI(
    title="AI 에이전트 시스템",
    description="Langchain 기반 AI 에이전트 시스템 - 지능형 데이터 처리 및 크롤링",
    version="1.0.0",
    debug=config.debug,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS 설정
if config.security.enable_cors:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.security.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# 정적 파일 및 템플릿 설정
app.mount("/static", StaticFiles(directory="template"), name="static")
templates = Jinja2Templates(directory="template/html")


# 의존성 함수들
async def get_agent_system() -> AIAgentSystem:
    """AI 에이전트 시스템 의존성"""
    if not agent_system:
        raise HTTPException(status_code=503, detail="AI 에이전트 시스템이 초기화되지 않았습니다")
    return agent_system


async def get_performance_monitor() -> PerformanceMonitor:
    """성능 모니터 의존성"""
    if not performance_monitor:
        raise HTTPException(status_code=503, detail="성능 모니터링 시스템이 초기화되지 않았습니다")
    return performance_monitor


async def get_crawling_service() -> IntelligentCrawlingService:
    """크롤링 서비스 의존성"""
    if not intelligent_crawling_service:
        raise HTTPException(status_code=503, detail="크롤링 서비스가 초기화되지 않았습니다")
    return intelligent_crawling_service


# 기본 라우트들
@app.get("/", response_class=HTMLResponse, summary="메인 페이지")
async def main_page(request: Request):
    """AI 에이전트 시스템 메인 페이지"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health", summary="시스템 상태 확인")
async def health_check():
    """시스템 건강 상태 확인"""
    try:
        status = {
            "status": "healthy",
            "timestamp": time.time(),
            "components": {
                "agent_system": agent_system is not None and agent_system.is_healthy(),
                "performance_monitor": performance_monitor is not None,
                "crawling_service": intelligent_crawling_service is not None,
                "monitoring_integration": monitoring_integration is not None
            }
        }
        
        # 전체 상태 확인
        all_healthy = all(status["components"].values())
        status["status"] = "healthy" if all_healthy else "degraded"
        
        return status
        
    except Exception as e:
        logger.error(f"헬스체크 오류: {str(e)}")
        return {
            "status": "unhealthy",
            "timestamp": time.time(),
            "error": str(e)
        }


@app.get("/system/info", summary="시스템 정보")
async def system_info(
    system: AIAgentSystem = Depends(get_agent_system)
):
    """시스템 기본 정보 조회"""
    try:
        info = {
            "system_name": "AI 에이전트 시스템",
            "version": "1.0.0",
            "status": system.status.value,
            "uptime": system.get_uptime(),
            "agents": {
                "total_count": len(system.agents),
                "active_agents": [
                    {
                        "name": agent.config.name,
                        "type": agent.__class__.__name__,
                        "status": agent.status.value
                    }
                    for agent in system.agents.values()
                    if agent.is_active()
                ]
            },
            "performance": {
                "total_requests": system.metrics.total_requests,
                "successful_requests": system.metrics.successful_requests,
                "failed_requests": system.metrics.failed_requests,
                "average_response_time": system.metrics.average_response_time
            }
        }
        
        return info
        
    except Exception as e:
        logger.error(f"시스템 정보 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"시스템 정보 조회 실패: {str(e)}")


@app.get("/system/metrics", summary="시스템 메트릭")
async def system_metrics(
    monitor: PerformanceMonitor = Depends(get_performance_monitor)
):
    """실시간 시스템 메트릭 조회"""
    try:
        current_metrics = await monitor.get_current_metrics()
        recent_alerts = await monitor.get_recent_alerts(limit=10)
        
        return {
            "current_metrics": current_metrics,
            "recent_alerts": [
                {
                    "level": alert.level.value,
                    "message": alert.message,
                    "timestamp": alert.timestamp,
                    "metric_type": alert.metric_type.value if alert.metric_type else None
                }
                for alert in recent_alerts
            ],
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"메트릭 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"메트릭 조회 실패: {str(e)}")


# API 라우터 등록
from api import agents_router, crawling_router, monitoring_router, chains_router

app.include_router(agents_router, prefix="/api/agents", tags=["agents"])
app.include_router(crawling_router, prefix="/api/crawling", tags=["crawling"])
app.include_router(monitoring_router, prefix="/api/monitoring", tags=["monitoring"])
app.include_router(chains_router, prefix="/api/chains", tags=["chains"])


if __name__ == "__main__":
    """개발 서버 실행"""
    logger.info("🚀 AI 에이전트 시스템 서버 시작...")
    logger.info(f"환경: {config.environment.value}")
    logger.info(f"디버그 모드: {config.debug}")
    
    uvicorn.run(
        "app:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
        log_level=config.monitoring.log_level.value.lower(),
        access_log=config.monitoring.enable_request_logging,
        workers=config.workers  # lifespan 이벤트 처리를 위해 단일 워커 사용
    )
