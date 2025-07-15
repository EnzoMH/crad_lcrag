"""
AI 에이전트 시스템 - 통합 설정 관리

Features:
- 환경별 설정 관리
- AI 모델 설정
- 성능 최적화 설정
- 모니터링 설정
"""

import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum


class Environment(str, Enum):
    """환경 구분"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """로그 레벨"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class DatabaseConfig:
    """데이터베이스 설정"""
    url: str = "sqlite:///./agent_system.db"
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600
    echo: bool = False


@dataclass  
class AIModelConfig:
    """AI 모델 설정"""
    model_name: str = "gemini-1.5-flash"
    temperature: float = 0.7
    max_tokens: int = 1000
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: int = 300
    
    # API 키 설정
    api_keys: List[str] = field(default_factory=list)
    
    # Rate Limiting
    rpm_limit: int = 2000  # 분당 요청 제한
    tpm_limit: int = 4000000  # 분당 토큰 제한


@dataclass
class PerformanceConfig:
    """성능 관련 설정"""
    max_concurrent_tasks: int = 10
    task_timeout: int = 300
    worker_pool_size: int = 5
    
    # 메모리 관리
    max_memory_usage_mb: int = 1024
    gc_threshold: int = 1000
    
    # 캐시 설정
    enable_caching: bool = True
    cache_ttl: int = 3600
    max_cache_size: int = 1000


@dataclass
class MonitoringConfig:
    """모니터링 설정"""
    enable_monitoring: bool = True
    metrics_interval: int = 60  # 초
    alert_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "cpu_usage": 80.0,
        "memory_usage": 85.0,
        "disk_usage": 90.0,
        "response_time": 10.0
    })
    
    # 알림 설정
    enable_alerts: bool = True
    alert_channels: List[str] = field(default_factory=list)
    
    # 로그 설정
    log_level: LogLevel = LogLevel.INFO
    log_retention_days: int = 30
    enable_request_logging: bool = True


@dataclass
class CrawlingConfig:
    """크롤링 서비스 설정"""
    max_concurrent_jobs: int = 5
    default_strategy: str = "balanced"
    job_timeout: int = 3600
    
    # 재시도 설정
    max_retries: int = 3
    retry_delay: float = 5.0
    
    # 정리 설정
    cleanup_interval: int = 86400  # 24시간
    max_job_history: int = 1000


@dataclass
class SecurityConfig:
    """보안 설정"""
    enable_cors: bool = True
    allowed_origins: List[str] = field(default_factory=lambda: ["*"])
    
    # API 키 관리
    api_key_rotation_interval: int = 86400  # 24시간
    require_https: bool = False
    
    # 세션 관리
    session_timeout: int = 3600  # 1시간
    max_login_attempts: int = 5


@dataclass
class SystemConfig:
    """시스템 전체 설정"""
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    
    # 서비스 설정
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    
    # 컴포넌트 설정
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    ai_model: AIModelConfig = field(default_factory=AIModelConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    crawling: CrawlingConfig = field(default_factory=CrawlingConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    
    # 환경 변수 오버라이드
    enable_env_override: bool = True


class ConfigManager:
    """설정 관리자"""
    
    def __init__(self, env: Optional[Environment] = None):
        """
        ConfigManager 초기화
        
        Args:
            env: 환경 구분 (기본값: 환경변수에서 가져옴)
        """
        self.env = env or self._detect_environment()
        self.config = self._load_config()
    
    def _detect_environment(self) -> Environment:
        """환경 자동 감지"""
        env_str = os.getenv("AGENT_ENV", "development").lower()
        
        env_mapping = {
            "dev": Environment.DEVELOPMENT,
            "development": Environment.DEVELOPMENT,
            "test": Environment.TESTING,
            "testing": Environment.TESTING,
            "prod": Environment.PRODUCTION,
            "production": Environment.PRODUCTION
        }
        
        return env_mapping.get(env_str, Environment.DEVELOPMENT)
    
    def _load_config(self) -> SystemConfig:
        """환경별 설정 로드"""
        config = SystemConfig(environment=self.env)
        
        # 환경별 기본 설정 적용
        if self.env == Environment.DEVELOPMENT:
            config.debug = True
            config.ai_model.temperature = 0.8
            config.monitoring.log_level = LogLevel.DEBUG
            config.performance.max_concurrent_tasks = 5
            
        elif self.env == Environment.TESTING:
            config.debug = False
            config.ai_model.max_retries = 1
            config.monitoring.log_level = LogLevel.INFO
            config.performance.max_concurrent_tasks = 3
            
        elif self.env == Environment.PRODUCTION:
            config.debug = False
            config.security.require_https = True
            config.security.allowed_origins = []  # 특정 도메인만 허용
            config.monitoring.log_level = LogLevel.WARNING
            config.performance.max_concurrent_tasks = 20
        
        # 환경 변수 오버라이드 적용
        if config.enable_env_override:
            self._apply_env_overrides(config)
        
        return config
    
    def _apply_env_overrides(self, config: SystemConfig):
        """환경 변수로 설정 오버라이드"""
        
        # 기본 서버 설정
        if host := os.getenv("HOST"):
            config.host = host
        if port := os.getenv("PORT"):
            config.port = int(port)
        
        # AI 모델 설정
        if api_key := os.getenv("GEMINI_API_KEY"):
            config.ai_model.api_keys = [api_key]
        if model_name := os.getenv("AI_MODEL_NAME"):
            config.ai_model.model_name = model_name
        if temperature := os.getenv("AI_TEMPERATURE"):
            config.ai_model.temperature = float(temperature)
        
        # 데이터베이스 설정
        if db_url := os.getenv("DATABASE_URL"):
            config.database.url = db_url
        
        # 성능 설정
        if max_tasks := os.getenv("MAX_CONCURRENT_TASKS"):
            config.performance.max_concurrent_tasks = int(max_tasks)
        if max_memory := os.getenv("MAX_MEMORY_MB"):
            config.performance.max_memory_usage_mb = int(max_memory)
        
        # 모니터링 설정
        if log_level := os.getenv("LOG_LEVEL"):
            config.monitoring.log_level = LogLevel(log_level.upper())
        if enable_monitoring := os.getenv("ENABLE_MONITORING"):
            config.monitoring.enable_monitoring = enable_monitoring.lower() == "true"
    
    def get_config(self) -> SystemConfig:
        """현재 설정 반환"""
        return self.config
    
    def update_config(self, updates: Dict[str, Any]):
        """설정 업데이트"""
        for key, value in updates.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
    
    def get_ai_model_config(self) -> Dict[str, Any]:
        """AI 모델 설정을 딕셔너리로 반환"""
        return {
            "model_name": self.config.ai_model.model_name,
            "temperature": self.config.ai_model.temperature,
            "max_tokens": self.config.ai_model.max_tokens,
            "max_retries": self.config.ai_model.max_retries,
            "retry_delay": self.config.ai_model.retry_delay,
            "timeout": self.config.ai_model.timeout,
            "api_keys": self.config.ai_model.api_keys,
            "rpm_limit": self.config.ai_model.rpm_limit,
            "tpm_limit": self.config.ai_model.tpm_limit
        }
    
    def get_database_config(self) -> Dict[str, Any]:
        """데이터베이스 설정을 딕셔너리로 반환"""
        return {
            "url": self.config.database.url,
            "pool_size": self.config.database.pool_size,
            "max_overflow": self.config.database.max_overflow,
            "pool_timeout": self.config.database.pool_timeout,
            "pool_recycle": self.config.database.pool_recycle,
            "echo": self.config.database.echo
        }
    
    def validate_config(self) -> List[str]:
        """설정 유효성 검증"""
        errors = []
        
        # AI 모델 설정 검증
        if not self.config.ai_model.api_keys:
            errors.append("AI 모델 API 키가 설정되지 않았습니다")
        
        if self.config.ai_model.temperature < 0 or self.config.ai_model.temperature > 2:
            errors.append("AI 모델 temperature는 0-2 사이여야 합니다")
        
        # 성능 설정 검증
        if self.config.performance.max_concurrent_tasks <= 0:
            errors.append("최대 동시 작업 수는 1 이상이어야 합니다")
        
        # 포트 설정 검증
        if self.config.port < 1 or self.config.port > 65535:
            errors.append("포트 번호는 1-65535 사이여야 합니다")
        
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        """설정을 딕셔너리로 변환"""
        return {
            "environment": self.config.environment.value,
            "debug": self.config.debug,
            "host": self.config.host,
            "port": self.config.port,
            "workers": self.config.workers,
            "ai_model": self.get_ai_model_config(),
            "database": self.get_database_config(),
            "performance": {
                "max_concurrent_tasks": self.config.performance.max_concurrent_tasks,
                "task_timeout": self.config.performance.task_timeout,
                "worker_pool_size": self.config.performance.worker_pool_size,
                "max_memory_usage_mb": self.config.performance.max_memory_usage_mb,
                "enable_caching": self.config.performance.enable_caching,
                "cache_ttl": self.config.performance.cache_ttl
            },
            "monitoring": {
                "enable_monitoring": self.config.monitoring.enable_monitoring,
                "metrics_interval": self.config.monitoring.metrics_interval,
                "alert_thresholds": self.config.monitoring.alert_thresholds,
                "log_level": self.config.monitoring.log_level.value,
                "log_retention_days": self.config.monitoring.log_retention_days
            },
            "crawling": {
                "max_concurrent_jobs": self.config.crawling.max_concurrent_jobs,
                "default_strategy": self.config.crawling.default_strategy,
                "job_timeout": self.config.crawling.job_timeout,
                "max_retries": self.config.crawling.max_retries
            },
            "security": {
                "enable_cors": self.config.security.enable_cors,
                "allowed_origins": self.config.security.allowed_origins,
                "require_https": self.config.security.require_https,
                "session_timeout": self.config.security.session_timeout
            }
        }


# 전역 설정 인스턴스
config_manager = ConfigManager()

# 편의 함수들
def get_config() -> SystemConfig:
    """현재 설정 반환"""
    return config_manager.get_config()

def get_ai_config() -> Dict[str, Any]:
    """AI 모델 설정 반환"""
    return config_manager.get_ai_model_config()

def get_db_config() -> Dict[str, Any]:
    """데이터베이스 설정 반환"""
    return config_manager.get_database_config()

def validate_config() -> List[str]:
    """설정 유효성 검증"""
    return config_manager.validate_config()

def reload_config():
    """설정 다시 로드"""
    global config_manager
    config_manager = ConfigManager()

# 환경별 설정 프리셋
DEVELOPMENT_PRESET = {
    "debug": True,
    "host": "127.0.0.1",
    "port": 8000,
    "ai_model": {
        "temperature": 0.8,
        "max_retries": 3
    },
    "performance": {
        "max_concurrent_tasks": 5
    },
    "monitoring": {
        "log_level": "DEBUG",
        "enable_monitoring": True
    }
}

PRODUCTION_PRESET = {
    "debug": False,
    "host": "0.0.0.0", 
    "port": 8000,
    "ai_model": {
        "temperature": 0.7,
        "max_retries": 5
    },
    "performance": {
        "max_concurrent_tasks": 20
    },
    "monitoring": {
        "log_level": "WARNING",
        "enable_monitoring": True
    },
    "security": {
        "require_https": True
    }
} 