"""
AI 에이전트 시스템 - 핵심 모듈

이 패키지는 AI 에이전트 시스템의 핵심 구성 요소들을 포함합니다:
- BaseAgent: 모든 에이전트의 기반 클래스
- AIAgentSystem: 전체 에이전트 시스템 관리자
- ChainManager: Langchain Chain 관리자
- ChainPipeline: Chain 기반 파이프라인 시스템
- ChainService: Chain 시스템 통합 서비스
- PerformanceMonitor: 성능 모니터링 및 추적 시스템
- MonitoringIntegration: 통합 모니터링 시스템
- CrawlingAgentIntegration: 크롤링 시스템과 AI 에이전트 통합
- IntelligentCrawlingService: 지능형 크롤링 서비스
"""

from .base_agent import BaseAgent
from .ai_agent_system import AIAgentSystem

# Chain 시스템 컴포넌트들
from .chain_manager import (
    ChainManager,
    ChainConfig,
    ChainResult,
    ChainType,
    ChainOutputParser,
    PREDEFINED_CHAIN_CONFIGS,
    get_predefined_chain_config,
    list_predefined_chains
)

from .chain_pipeline import (
    ChainPipeline,
    PipelineConfig,
    PipelineResult,
    PipelineStep,
    PipelineStepType,
    PIPELINE_TEMPLATES,
    get_pipeline_template,
    list_pipeline_templates,
    create_contact_enrichment_pipeline,
    create_document_analysis_pipeline,
    create_quality_assessment_pipeline
)

from .chain_service import (
    ChainService,
    ChainServiceConfig,
    create_chain_service
)

# 성능 모니터링 시스템
from .performance_monitor import (
    PerformanceMonitor,
    PerformanceMetric,
    PerformanceAlert,
    SystemSnapshot,
    PerformanceThresholds,
    MetricType,
    AlertLevel
)

from .monitoring_integration import (
    MonitoringIntegration,
    MonitoringConfig
)

# GCP 최적화 시스템
from .gcp_optimizer import (
    GCPOptimizer,
    GCPOptimizationRecommendation,
    GCPWorkloadProfile,
    GCPResourceSpec,
    GCPInstanceType,
    OptimizationLevel,
    ResourceConstraint
)

from .gcp_optimization_service import (
    GCPOptimizationService,
    OptimizationServiceConfig,
    OptimizationTask,
    OptimizationMetrics,
    OptimizationServiceStatus,
    AutoOptimizationMode
)

# 크롤링 시스템 통합
from .crawling_integration import (
    CrawlingAgentIntegration,
    CrawlingStrategy,
    CrawlingPhase,
    CrawlingTarget,
    CrawlingResult,
    CrawlingJobConfig,
    CrawlingJobStatus,
    create_crawling_target,
    create_crawling_job_config
)

from .intelligent_crawling_service import (
    IntelligentCrawlingService,
    IntelligentCrawlingConfig,
    JobSchedule,
    ServiceStatus,
    create_intelligent_crawling_service,
    create_crawling_targets_from_dict
)

__all__ = [
    # 기존 컴포넌트들
    'BaseAgent',
    'AIAgentSystem',
    
    # Chain Manager
    'ChainManager',
    'ChainConfig', 
    'ChainResult',
    'ChainType',
    'ChainOutputParser',
    'PREDEFINED_CHAIN_CONFIGS',
    'get_predefined_chain_config',
    'list_predefined_chains',
    
    # Chain Pipeline
    'ChainPipeline',
    'PipelineConfig',
    'PipelineResult', 
    'PipelineStep',
    'PipelineStepType',
    'PIPELINE_TEMPLATES',
    'get_pipeline_template',
    'list_pipeline_templates',
    'create_contact_enrichment_pipeline',
    'create_document_analysis_pipeline',
    'create_quality_assessment_pipeline',
    
    # Chain Service
    'ChainService',
    'ChainServiceConfig',
    'create_chain_service',
    
    # 성능 모니터링
    'PerformanceMonitor',
    'PerformanceMetric',
    'PerformanceAlert',
    'SystemSnapshot',
    'PerformanceThresholds',
    'MetricType',
    'AlertLevel',
    
    # 통합 모니터링
    'MonitoringIntegration',
    'MonitoringConfig',
    
    # GCP 최적화
    'GCPOptimizer',
    'GCPOptimizationRecommendation',
    'GCPWorkloadProfile',
    'GCPResourceSpec',
    'GCPInstanceType',
    'OptimizationLevel',
    'ResourceConstraint',
    
    # GCP 최적화 서비스
    'GCPOptimizationService',
    'OptimizationServiceConfig',
    'OptimizationTask',
    'OptimizationMetrics',
    'OptimizationServiceStatus',
    'AutoOptimizationMode',
    
    # 크롤링 시스템 통합
    'CrawlingAgentIntegration',
    'CrawlingStrategy',
    'CrawlingPhase',
    'CrawlingTarget',
    'CrawlingResult',
    'CrawlingJobConfig',
    'CrawlingJobStatus',
    'create_crawling_target',
    'create_crawling_job_config',
    
    # 지능형 크롤링 서비스
    'IntelligentCrawlingService',
    'IntelligentCrawlingConfig',
    'JobSchedule',
    'ServiceStatus',
    'create_intelligent_crawling_service',
    'create_crawling_targets_from_dict'
] 