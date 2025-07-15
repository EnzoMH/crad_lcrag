"""
🔗 크롤링 시스템 - AI 에이전트 통합 사용 예제

기존 크롤링 시스템과 AI 에이전트 시스템의 통합 사용법을 보여주는 예제들
- 기본 지능형 크롤링 작업
- 대량 크롤링 작업 관리
- 스케줄된 크롤링 작업
- 성능 최적화 통합
- 실시간 모니터링
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any
import json

from loguru import logger

from ..core.agent_system import AIAgentSystem, SystemConfig
from ..core.performance_monitor import PerformanceMonitor, PerformanceThresholds, MetricType
from ..core.monitoring_integration import MonitoringIntegration, MonitoringConfig
from ..core.gcp_optimization_service import GCPOptimizationService, OptimizationServiceConfig
from ..core.gcp_optimizer import GCPOptimizer
from ..core.crawling_integration import (
    CrawlingAgentIntegration, CrawlingStrategy, create_crawling_target, create_crawling_job_config
)
from ..core.intelligent_crawling_service import (
    IntelligentCrawlingService, IntelligentCrawlingConfig, create_intelligent_crawling_service
)
from ..config.gemini_client import GeminiClient
from ..config.prompt_manager import PromptManager


class CrawlingIntegrationExamples:
    """크롤링 시스템 통합 예제 클래스"""
    
    def __init__(self):
        """예제 시스템 초기화"""
        self.examples_run = []
    
    async def run_all_examples(self):
        """모든 예제 실행"""
        logger.info("🚀 크롤링 시스템 통합 예제 시작")
        
        examples = [
            ("기본 지능형 크롤링", self.example_basic_intelligent_crawling),
            ("고급 크롤링 전략", self.example_advanced_crawling_strategies),
            ("대량 크롤링 관리", self.example_bulk_crawling_management),
            ("스케줄된 크롤링", self.example_scheduled_crawling),
            ("성능 최적화 통합", self.example_performance_optimization_integration),
            ("실시간 모니터링", self.example_real_time_monitoring),
            ("종합 데모", self.example_comprehensive_demo)
        ]
        
        for name, example_func in examples:
            try:
                logger.info(f"\n📋 {name} 예제 시작")
                await example_func()
                self.examples_run.append(name)
                logger.info(f"✅ {name} 예제 완료")
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"❌ {name} 예제 실패: {e}")
        
        logger.info(f"\n🎉 크롤링 시스템 통합 예제 완료 ({len(self.examples_run)}/{len(examples)}개 성공)")
    
    async def example_basic_intelligent_crawling(self):
        """예제 1: 기본 지능형 크롤링"""
        logger.info("🎯 기본 지능형 크롤링 시작")
        
        # AI 에이전트 시스템 초기화
        system_config = SystemConfig(
            name="CrawlingIntegrationSystem",
            version="1.0.0",
            max_concurrent_agents=10
        )
        agent_system = AIAgentSystem(system_config)
        
        # 성능 모니터 초기화
        performance_monitor = PerformanceMonitor()
        await performance_monitor.start_monitoring()
        
        # 통합 모니터링 초기화
        monitoring_config = MonitoringConfig(
            enable_agent_monitoring=True,
            enable_system_monitoring=True,
            agent_monitoring_interval=30,
            system_monitoring_interval=60
        )
        monitoring_integration = MonitoringIntegration(
            agent_system=agent_system,
            performance_monitor=performance_monitor,
            config=monitoring_config
        )
        
        # 크롤링 통합 시스템 초기화
        crawling_integration = CrawlingAgentIntegration(
            agent_system=agent_system,
            performance_monitor=performance_monitor,
            monitoring_integration=monitoring_integration
        )
        
        # 크롤링 대상 정의
        targets = [
            create_crawling_target(
                name="삼성교회",
                category="교회",
                existing_data={"address": "서울시 강남구"},
                target_urls=["http://samsung.church"],
                search_keywords=["삼성교회", "강남구", "교회"]
            ),
            create_crawling_target(
                name="영어수학학원",
                category="학원",
                existing_data={"phone": "02-123-4567"},
                search_keywords=["영어수학학원", "학원", "수학"]
            ),
            create_crawling_target(
                name="강남구청",
                category="주민센터",
                existing_data={"address": "서울시 강남구"},
                search_keywords=["강남구청", "구청", "행정"]
            )
        ]
        
        # 크롤링 작업 설정
        job_config = create_crawling_job_config(
            targets=targets,
            strategy=CrawlingStrategy.BALANCED,
            max_concurrent=3,
            enable_ai_validation=True,
            enable_enrichment=True,
            enable_optimization=False
        )
        
        # 지능형 크롤링 실행
        result = await crawling_integration.start_intelligent_crawling_job(job_config)
        
        # 결과 출력
        logger.info(f"📊 크롤링 결과:")
        logger.info(f"  - 작업 ID: {result.job_id}")
        logger.info(f"  - 상태: {result.status}")
        logger.info(f"  - 총 대상: {result.total_targets}개")
        logger.info(f"  - 성공: {result.completed_targets}개")
        logger.info(f"  - 실패: {result.failed_targets}개")
        logger.info(f"  - 성공률: {result.success_rate:.1%}")
        logger.info(f"  - 처리 시간: {result.total_processing_time:.1f}초")
        
        # 개별 결과 확인
        for i, crawling_result in enumerate(result.results):
            logger.info(f"  [{i+1}] {crawling_result.target_id}:")
            logger.info(f"      성공: {crawling_result.success}")
            logger.info(f"      신뢰도: {crawling_result.confidence_score:.3f}")
            logger.info(f"      처리시간: {crawling_result.processing_time:.2f}초")
            if crawling_result.extracted_data:
                phone = crawling_result.extracted_data.get("phone", "없음")
                email = crawling_result.extracted_data.get("email", "없음")
                logger.info(f"      전화번호: {phone}")
                logger.info(f"      이메일: {email}")
        
        # 정리
        await performance_monitor.stop_monitoring()
        await crawling_integration.cleanup()
        
        logger.info("✅ 기본 지능형 크롤링 완료")
    
    async def example_advanced_crawling_strategies(self):
        """예제 2: 고급 크롤링 전략"""
        logger.info("🎯 고급 크롤링 전략 테스트")
        
        # 시스템 초기화 (간소화)
        agent_system = AIAgentSystem()
        performance_monitor = PerformanceMonitor()
        await performance_monitor.start_monitoring()
        
        monitoring_integration = MonitoringIntegration(
            agent_system=agent_system,
            performance_monitor=performance_monitor
        )
        
        crawling_integration = CrawlingAgentIntegration(
            agent_system=agent_system,
            performance_monitor=performance_monitor,
            monitoring_integration=monitoring_integration
        )
        
        # 다양한 전략으로 크롤링 테스트
        strategies = [
            CrawlingStrategy.CONSERVATIVE,
            CrawlingStrategy.BALANCED,
            CrawlingStrategy.AGGRESSIVE,
            CrawlingStrategy.AI_ADAPTIVE
        ]
        
        test_targets = [
            create_crawling_target(
                name="테스트교회",
                category="교회",
                search_keywords=["테스트교회", "교회"]
            )
        ]
        
        strategy_results = {}
        
        for strategy in strategies:
            logger.info(f"🔬 {strategy.value} 전략 테스트")
            
            job_config = create_crawling_job_config(
                targets=test_targets,
                strategy=strategy,
                max_concurrent=2 if strategy == CrawlingStrategy.CONSERVATIVE else 5,
                enable_ai_validation=strategy in [CrawlingStrategy.BALANCED, CrawlingStrategy.AI_ADAPTIVE],
                enable_enrichment=strategy != CrawlingStrategy.CONSERVATIVE,
                enable_optimization=strategy == CrawlingStrategy.AGGRESSIVE
            )
            
            start_time = time.time()
            result = await crawling_integration.start_intelligent_crawling_job(job_config)
            end_time = time.time()
            
            strategy_results[strategy.value] = {
                "success_rate": result.success_rate,
                "processing_time": end_time - start_time,
                "confidence_score": sum(r.confidence_score for r in result.results) / len(result.results) if result.results else 0
            }
            
            logger.info(f"  성공률: {result.success_rate:.1%}")
            logger.info(f"  처리시간: {end_time - start_time:.1f}초")
            logger.info(f"  평균 신뢰도: {strategy_results[strategy.value]['confidence_score']:.3f}")
        
        # 전략 비교 결과
        logger.info("📊 전략별 성능 비교:")
        for strategy, metrics in strategy_results.items():
            logger.info(f"  {strategy}: 성공률 {metrics['success_rate']:.1%}, "
                       f"시간 {metrics['processing_time']:.1f}초, "
                       f"신뢰도 {metrics['confidence_score']:.3f}")
        
        # 정리
        await performance_monitor.stop_monitoring()
        await crawling_integration.cleanup()
        
        logger.info("✅ 고급 크롤링 전략 테스트 완료")
    
    async def example_bulk_crawling_management(self):
        """예제 3: 대량 크롤링 관리"""
        logger.info("🎯 대량 크롤링 관리 시작")
        
        # 지능형 크롤링 서비스 초기화
        agent_system = AIAgentSystem()
        performance_monitor = PerformanceMonitor()
        await performance_monitor.start_monitoring()
        
        monitoring_integration = MonitoringIntegration(
            agent_system=agent_system,
            performance_monitor=performance_monitor
        )
        
        service_config = IntelligentCrawlingConfig(
            max_concurrent_jobs=3,
            job_queue_size=20,
            enable_monitoring=True
        )
        
        crawling_service = await create_intelligent_crawling_service(
            agent_system=agent_system,
            performance_monitor=performance_monitor,
            monitoring_integration=monitoring_integration,
            config=service_config
        )
        
        # 대량 크롤링 대상 생성 (50개)
        bulk_targets = []
        for i in range(50):
            target_data = {
                "name": f"테스트기관{i+1:02d}",
                "category": "교회" if i % 3 == 0 else "학원" if i % 3 == 1 else "주민센터",
                "search_keywords": [f"테스트기관{i+1:02d}"]
            }
            bulk_targets.append(target_data)
        
        # 10개씩 나누어 5개 작업으로 제출
        chunk_size = 10
        job_ids = []
        
        for i in range(0, len(bulk_targets), chunk_size):
            chunk = bulk_targets[i:i+chunk_size]
            
            job_id = await crawling_service.submit_crawling_job(
                targets=chunk,
                strategy=CrawlingStrategy.BALANCED,
                job_options={
                    "max_concurrent": 5,
                    "enable_ai_validation": True,
                    "enable_enrichment": True
                }
            )
            
            job_ids.append(job_id)
            logger.info(f"📝 작업 제출: {job_id} ({len(chunk)}개 대상)")
        
        # 작업 진행 상황 모니터링
        logger.info("📊 작업 진행 상황 모니터링 시작")
        
        completed_jobs = 0
        while completed_jobs < len(job_ids):
            await asyncio.sleep(5)
            
            # 서비스 메트릭 조회
            metrics = crawling_service.get_service_metrics()
            active_jobs = crawling_service.get_active_jobs()
            
            logger.info(f"  활성 작업: {len(active_jobs)}개")
            logger.info(f"  큐 크기: {metrics['current_queue_size']}")
            logger.info(f"  완료된 작업: {metrics['successful_jobs'] + metrics['failed_jobs']}/{len(job_ids)}")
            
            # 완료된 작업 수 확인
            completed_jobs = metrics['successful_jobs'] + metrics['failed_jobs']
        
        # 최종 결과 확인
        final_metrics = crawling_service.get_service_metrics()
        recent_jobs = crawling_service.get_recent_jobs(len(job_ids))
        
        logger.info("📊 대량 크롤링 최종 결과:")
        logger.info(f"  총 작업: {len(job_ids)}개")
        logger.info(f"  성공한 작업: {final_metrics['successful_jobs']}개")
        logger.info(f"  실패한 작업: {final_metrics['failed_jobs']}개")
        logger.info(f"  총 처리 대상: {final_metrics['total_targets_processed']}개")
        logger.info(f"  평균 작업 시간: {final_metrics['average_job_duration']:.1f}초")
        
        # 개별 작업 결과 요약
        total_success_rate = 0
        for job in recent_jobs:
            if job.get('success_rate') is not None:
                total_success_rate += job['success_rate']
        
        average_success_rate = total_success_rate / len(recent_jobs) if recent_jobs else 0
        logger.info(f"  평균 성공률: {average_success_rate:.1%}")
        
        # 서비스 중지
        await crawling_service.stop_service()
        await performance_monitor.stop_monitoring()
        
        logger.info("✅ 대량 크롤링 관리 완료")
    
    async def example_scheduled_crawling(self):
        """예제 4: 스케줄된 크롤링"""
        logger.info("🎯 스케줄된 크롤링 시작")
        
        # 지능형 크롤링 서비스 초기화
        agent_system = AIAgentSystem()
        performance_monitor = PerformanceMonitor()
        await performance_monitor.start_monitoring()
        
        monitoring_integration = MonitoringIntegration(
            agent_system=agent_system,
            performance_monitor=performance_monitor
        )
        
        service_config = IntelligentCrawlingConfig(
            enable_scheduling=True,
            enable_monitoring=True
        )
        
        crawling_service = await create_intelligent_crawling_service(
            agent_system=agent_system,
            performance_monitor=performance_monitor,
            monitoring_integration=monitoring_integration,
            config=service_config
        )
        
        # 스케줄된 크롤링 작업 등록
        scheduled_targets = [
            {
                "name": "일일점검대상",
                "category": "교회",
                "search_keywords": ["일일점검대상", "교회"]
            }
        ]
        
        # 매시간 실행되는 스케줄 등록
        schedule_success = await crawling_service.schedule_crawling_job(
            schedule_id="hourly_crawling",
            targets=scheduled_targets,
            cron_expression="0 * * * *",  # 매시간 0분에 실행
            strategy=CrawlingStrategy.CONSERVATIVE,
            job_options={
                "max_concurrent": 2,
                "enable_ai_validation": False,
                "enable_enrichment": False
            },
            enabled=True
        )
        
        logger.info(f"📅 스케줄 등록 결과: {schedule_success}")
        
        # 즉시 실행 테스트용 스케줄 등록
        test_targets = [
            {
                "name": "테스트즉시실행",
                "category": "학원",
                "search_keywords": ["테스트즉시실행", "학원"]
            }
        ]
        
        # 1분 후 실행되는 테스트 스케줄
        test_schedule_success = await crawling_service.schedule_crawling_job(
            schedule_id="test_immediate",
            targets=test_targets,
            cron_expression="* * * * *",  # 매분 실행 (테스트용)
            strategy=CrawlingStrategy.BALANCED,
            enabled=True
        )
        
        logger.info(f"📅 테스트 스케줄 등록: {test_schedule_success}")
        
        # 스케줄된 작업 목록 확인
        scheduled_jobs = crawling_service.get_scheduled_jobs()
        logger.info(f"📋 등록된 스케줄: {len(scheduled_jobs)}개")
        
        for schedule in scheduled_jobs:
            logger.info(f"  - {schedule['schedule_id']}: {schedule['cron_expression']} "
                       f"(활성화: {schedule['enabled']})")
        
        # 스케줄 실행 모니터링 (2분간)
        logger.info("📊 스케줄 실행 모니터링 시작 (2분간)")
        
        for i in range(12):  # 10초씩 12번 = 2분
            await asyncio.sleep(10)
            
            metrics = crawling_service.get_service_metrics()
            active_jobs = crawling_service.get_active_jobs()
            
            logger.info(f"  [{i+1}/12] 활성 작업: {len(active_jobs)}개, "
                       f"완료: {metrics['successful_jobs'] + metrics['failed_jobs']}개")
            
            # 스케줄 실행 결과 확인
            recent_jobs = crawling_service.get_recent_jobs(5)
            scheduled_executions = [job for job in recent_jobs 
                                  if job['job_id'].startswith('scheduled_')]
            
            if scheduled_executions:
                logger.info(f"  스케줄된 작업 실행: {len(scheduled_executions)}개")
        
        # 최종 결과
        final_scheduled_jobs = crawling_service.get_scheduled_jobs()
        final_recent_jobs = crawling_service.get_recent_jobs(10)
        
        scheduled_executions = [job for job in final_recent_jobs 
                              if job['job_id'].startswith('scheduled_')]
        
        logger.info("📊 스케줄된 크롤링 최종 결과:")
        logger.info(f"  등록된 스케줄: {len(final_scheduled_jobs)}개")
        logger.info(f"  실행된 스케줄 작업: {len(scheduled_executions)}개")
        
        for schedule in final_scheduled_jobs:
            logger.info(f"  - {schedule['schedule_id']}: 실행횟수 {schedule['run_count']}회")
        
        # 서비스 중지
        await crawling_service.stop_service()
        await performance_monitor.stop_monitoring()
        
        logger.info("✅ 스케줄된 크롤링 완료")
    
    async def example_performance_optimization_integration(self):
        """예제 5: 성능 최적화 통합"""
        logger.info("🎯 성능 최적화 통합 시작")
        
        # GCP 최적화를 포함한 전체 시스템 초기화
        agent_system = AIAgentSystem()
        
        # 성능 모니터 초기화
        performance_monitor = PerformanceMonitor()
        await performance_monitor.start_monitoring()
        
        # GCP 최적화 시스템 초기화
        gcp_optimizer = GCPOptimizer()
        optimization_service_config = OptimizationServiceConfig(
            auto_optimization_mode=True,
            optimization_interval=300,  # 5분마다
            analysis_interval=180       # 3분마다
        )
        
        monitoring_integration = MonitoringIntegration(
            agent_system=agent_system,
            performance_monitor=performance_monitor
        )
        
        gcp_optimization_service = GCPOptimizationService(
            gcp_optimizer=gcp_optimizer,
            performance_monitor=performance_monitor,
            monitoring_integration=monitoring_integration,
            agent_system=agent_system,
            config=optimization_service_config
        )
        
        # 크롤링 통합 시스템 (최적화 포함)
        crawling_integration = CrawlingAgentIntegration(
            agent_system=agent_system,
            performance_monitor=performance_monitor,
            monitoring_integration=monitoring_integration,
            gcp_optimization_service=gcp_optimization_service
        )
        
        # GCP 최적화 서비스 시작
        await gcp_optimization_service.start_service()
        
        # 성능 부하를 주는 크롤링 작업 실행
        performance_test_targets = []
        for i in range(20):
            target = create_crawling_target(
                name=f"성능테스트대상{i+1:02d}",
                category="교회",
                search_keywords=[f"성능테스트대상{i+1:02d}", "교회"],
                priority=1 if i < 10 else 2
            )
            performance_test_targets.append(target)
        
        # 적극적 전략으로 성능 부하 생성
        job_config = create_crawling_job_config(
            targets=performance_test_targets,
            strategy=CrawlingStrategy.AGGRESSIVE,
            max_concurrent=8,
            enable_ai_validation=True,
            enable_enrichment=True,
            enable_optimization=True  # 최적화 활성화
        )
        
        logger.info("🚀 성능 최적화가 포함된 크롤링 시작")
        
        # 크롤링 실행 (백그라운드)
        crawling_task = asyncio.create_task(
            crawling_integration.start_intelligent_crawling_job(job_config)
        )
        
        # 성능 모니터링 및 최적화 추적 (1분간)
        logger.info("📊 성능 최적화 추적 시작")
        
        for i in range(6):  # 10초씩 6번 = 1분
            await asyncio.sleep(10)
            
            # 성능 메트릭 조회
            current_metrics = performance_monitor.get_current_metrics()
            system_snapshot = performance_monitor.get_system_snapshot()
            
            logger.info(f"  [{i+1}/6] 시스템 상태:")
            logger.info(f"    CPU: {system_snapshot.cpu_percent:.1f}%")
            logger.info(f"    메모리: {system_snapshot.memory_percent:.1f}%")
            logger.info(f"    수집된 메트릭: {len(current_metrics)}개")
            
            # GCP 최적화 서비스 상태
            optimization_metrics = gcp_optimization_service.get_service_metrics()
            logger.info(f"    최적화 작업: {optimization_metrics.total_optimizations}개")
            logger.info(f"    개선 사항: {optimization_metrics.successful_optimizations}개")
        
        # 크롤링 완료 대기
        crawling_result = await crawling_task
        
        # 최종 성능 최적화 결과
        final_optimization_metrics = gcp_optimization_service.get_service_metrics()
        final_performance_report = performance_monitor.generate_performance_report(
            time_range_minutes=5
        )
        
        logger.info("📊 성능 최적화 통합 최종 결과:")
        logger.info(f"  크롤링 성공률: {crawling_result.success_rate:.1%}")
        logger.info(f"  크롤링 처리 시간: {crawling_result.total_processing_time:.1f}초")
        logger.info(f"  최적화 작업 수행: {final_optimization_metrics.total_optimizations}개")
        logger.info(f"  성공한 최적화: {final_optimization_metrics.successful_optimizations}개")
        
        if final_performance_report:
            logger.info(f"  평균 CPU 사용률: {final_performance_report.get('avg_cpu', 0):.1f}%")
            logger.info(f"  평균 메모리 사용률: {final_performance_report.get('avg_memory', 0):.1f}%")
            logger.info(f"  성능 알림 수: {final_performance_report.get('alert_count', 0)}개")
        
        # 서비스 중지
        await gcp_optimization_service.stop_service()
        await performance_monitor.stop_monitoring()
        await crawling_integration.cleanup()
        
        logger.info("✅ 성능 최적화 통합 완료")
    
    async def example_real_time_monitoring(self):
        """예제 6: 실시간 모니터링"""
        logger.info("🎯 실시간 모니터링 시작")
        
        # 전체 통합 모니터링 시스템 초기화
        agent_system = AIAgentSystem()
        performance_monitor = PerformanceMonitor()
        await performance_monitor.start_monitoring()
        
        monitoring_config = MonitoringConfig(
            enable_agent_monitoring=True,
            enable_system_monitoring=True,
            enable_performance_tracking=True,
            agent_monitoring_interval=15,
            system_monitoring_interval=30,
            performance_tracking_interval=10
        )
        
        monitoring_integration = MonitoringIntegration(
            agent_system=agent_system,
            performance_monitor=performance_monitor,
            config=monitoring_config
        )
        
        # 통합 모니터링 시작
        await monitoring_integration.start_integrated_monitoring()
        
        # 지능형 크롤링 서비스 (모니터링 활성화)
        service_config = IntelligentCrawlingConfig(
            enable_monitoring=True,
            max_concurrent_jobs=2
        )
        
        crawling_service = await create_intelligent_crawling_service(
            agent_system=agent_system,
            performance_monitor=performance_monitor,
            monitoring_integration=monitoring_integration,
            config=service_config
        )
        
        # 모니터링 대상 크롤링 작업들 제출
        monitoring_targets = [
            {
                "name": f"모니터링대상{i+1}",
                "category": "교회" if i % 2 == 0 else "학원",
                "search_keywords": [f"모니터링대상{i+1}"]
            }
            for i in range(10)
        ]
        
        # 여러 작업을 순차적으로 제출하여 모니터링 데이터 생성
        job_ids = []
        for i in range(3):
            job_id = await crawling_service.submit_crawling_job(
                targets=monitoring_targets[i*3:(i+1)*3],
                strategy=CrawlingStrategy.BALANCED
            )
            job_ids.append(job_id)
            logger.info(f"📝 모니터링 테스트 작업 제출: {job_id}")
        
        # 실시간 모니터링 데이터 수집 및 출력 (2분간)
        logger.info("📊 실시간 모니터링 데이터 수집 시작 (2분간)")
        
        monitoring_data = []
        
        for i in range(12):  # 10초씩 12번 = 2분
            await asyncio.sleep(10)
            
            # 통합 모니터링 상태 조회
            monitoring_status = monitoring_integration.get_monitoring_status()
            service_metrics = crawling_service.get_service_metrics()
            system_snapshot = performance_monitor.get_system_snapshot()
            
            # 모니터링 데이터 기록
            timestamp = datetime.now()
            data_point = {
                "timestamp": timestamp.isoformat(),
                "system": {
                    "cpu_percent": system_snapshot.cpu_percent,
                    "memory_percent": system_snapshot.memory_percent,
                    "disk_usage": system_snapshot.disk_usage_percent
                },
                "crawling_service": {
                    "active_jobs": service_metrics["active_jobs_count"],
                    "completed_jobs": service_metrics["completed_jobs_count"],
                    "queue_size": service_metrics["current_queue_size"],
                    "success_rate": service_metrics.get("successful_jobs", 0) / max(service_metrics.get("total_jobs_processed", 1), 1)
                },
                "monitoring": {
                    "agents_monitored": monitoring_status.get("active_agents", 0),
                    "performance_alerts": monitoring_status.get("recent_alerts", 0),
                    "monitoring_uptime": monitoring_status.get("uptime_seconds", 0)
                }
            }
            
            monitoring_data.append(data_point)
            
            # 실시간 출력
            logger.info(f"  [{i+1:2d}/12] {timestamp.strftime('%H:%M:%S')}")
            logger.info(f"    시스템: CPU {data_point['system']['cpu_percent']:.1f}%, "
                       f"메모리 {data_point['system']['memory_percent']:.1f}%")
            logger.info(f"    크롤링: 활성 {data_point['crawling_service']['active_jobs']}개, "
                       f"완료 {data_point['crawling_service']['completed_jobs']}개")
            logger.info(f"    모니터링: 에이전트 {data_point['monitoring']['agents_monitored']}개 추적 중")
        
        # 모니터링 데이터 분석
        logger.info("📈 실시간 모니터링 데이터 분석:")
        
        # CPU/메모리 사용률 통계
        cpu_values = [d['system']['cpu_percent'] for d in monitoring_data]
        memory_values = [d['system']['memory_percent'] for d in monitoring_data]
        
        logger.info(f"  CPU 사용률: 평균 {sum(cpu_values)/len(cpu_values):.1f}%, "
                   f"최대 {max(cpu_values):.1f}%, 최소 {min(cpu_values):.1f}%")
        logger.info(f"  메모리 사용률: 평균 {sum(memory_values)/len(memory_values):.1f}%, "
                   f"최대 {max(memory_values):.1f}%, 최소 {min(memory_values):.1f}%")
        
        # 크롤링 서비스 활동 통계
        max_active_jobs = max(d['crawling_service']['active_jobs'] for d in monitoring_data)
        total_completed = max(d['crawling_service']['completed_jobs'] for d in monitoring_data)
        
        logger.info(f"  최대 동시 작업: {max_active_jobs}개")
        logger.info(f"  총 완료 작업: {total_completed}개")
        
        # 통합 성능 리포트 생성
        performance_report = monitoring_integration.generate_integrated_report(
            time_range_minutes=2
        )
        
        if performance_report:
            logger.info("📋 통합 성능 리포트:")
            logger.info(f"  모니터링 기간: {performance_report.get('monitoring_duration', 0):.0f}초")
            logger.info(f"  수집된 메트릭: {performance_report.get('total_metrics', 0)}개")
            logger.info(f"  발생한 알림: {performance_report.get('total_alerts', 0)}개")
            logger.info(f"  시스템 안정성: {performance_report.get('system_stability', 0):.1%}")
        
        # 서비스 중지
        await crawling_service.stop_service()
        await monitoring_integration.stop_integrated_monitoring()
        await performance_monitor.stop_monitoring()
        
        logger.info("✅ 실시간 모니터링 완료")
    
    async def example_comprehensive_demo(self):
        """예제 7: 종합 데모"""
        logger.info("🎯 크롤링 시스템 통합 종합 데모 시작")
        
        # 전체 시스템 초기화 (모든 구성 요소 포함)
        logger.info("🔧 전체 시스템 초기화")
        
        # 1. AI 에이전트 시스템
        system_config = SystemConfig(
            name="ComprehensiveDemo",
            version="1.0.0",
            max_concurrent_agents=15
        )
        agent_system = AIAgentSystem(system_config)
        
        # 2. 성능 모니터
        performance_monitor = PerformanceMonitor()
        await performance_monitor.start_monitoring()
        
        # 3. 통합 모니터링
        monitoring_config = MonitoringConfig(
            enable_agent_monitoring=True,
            enable_system_monitoring=True,
            enable_performance_tracking=True
        )
        monitoring_integration = MonitoringIntegration(
            agent_system=agent_system,
            performance_monitor=performance_monitor,
            config=monitoring_config
        )
        await monitoring_integration.start_integrated_monitoring()
        
        # 4. GCP 최적화 (선택적)
        gcp_optimizer = GCPOptimizer()
        gcp_optimization_service = GCPOptimizationService(
            gcp_optimizer=gcp_optimizer,
            performance_monitor=performance_monitor,
            monitoring_integration=monitoring_integration,
            agent_system=agent_system
        )
        await gcp_optimization_service.start_service()
        
        # 5. 지능형 크롤링 서비스
        service_config = IntelligentCrawlingConfig(
            max_concurrent_jobs=4,
            enable_scheduling=True,
            enable_monitoring=True,
            enable_optimization=True
        )
        
        crawling_service = await create_intelligent_crawling_service(
            agent_system=agent_system,
            performance_monitor=performance_monitor,
            monitoring_integration=monitoring_integration,
            gcp_optimization_service=gcp_optimization_service,
            config=service_config
        )
        
        logger.info("✅ 전체 시스템 초기화 완료")
        
        # 종합 데모 시나리오
        demo_scenarios = [
            ("즉시 크롤링 작업", self._demo_immediate_crawling),
            ("스케줄된 크롤링 설정", self._demo_scheduled_setup),
            ("대량 크롤링 처리", self._demo_bulk_processing),
            ("성능 최적화 테스트", self._demo_optimization_test),
            ("실시간 모니터링", self._demo_real_time_tracking)
        ]
        
        demo_results = {}
        
        for scenario_name, scenario_func in demo_scenarios:
            logger.info(f"\n🎬 시나리오: {scenario_name}")
            
            try:
                result = await scenario_func(crawling_service, monitoring_integration, gcp_optimization_service)
                demo_results[scenario_name] = {"success": True, "result": result}
                logger.info(f"✅ {scenario_name} 완료")
            except Exception as e:
                demo_results[scenario_name] = {"success": False, "error": str(e)}
                logger.error(f"❌ {scenario_name} 실패: {e}")
            
            await asyncio.sleep(2)
        
        # 종합 결과 리포트
        logger.info("\n📊 크롤링 시스템 통합 종합 데모 결과:")
        
        successful_scenarios = len([r for r in demo_results.values() if r["success"]])
        total_scenarios = len(demo_scenarios)
        
        logger.info(f"  실행된 시나리오: {total_scenarios}개")
        logger.info(f"  성공한 시나리오: {successful_scenarios}개")
        logger.info(f"  성공률: {successful_scenarios/total_scenarios:.1%}")
        
        # 시스템 전체 메트릭
        final_service_metrics = crawling_service.get_service_metrics()
        final_monitoring_status = monitoring_integration.get_monitoring_status()
        final_optimization_metrics = gcp_optimization_service.get_service_metrics()
        
        logger.info(f"  총 처리된 크롤링 작업: {final_service_metrics['total_jobs_processed']}개")
        logger.info(f"  전체 처리 대상: {final_service_metrics['total_targets_processed']}개")
        logger.info(f"  평균 작업 시간: {final_service_metrics['average_job_duration']:.1f}초")
        logger.info(f"  최적화 개선 사항: {final_optimization_metrics.successful_optimizations}개")
        
        # 시나리오별 상세 결과
        for scenario_name, result in demo_results.items():
            if result["success"]:
                logger.info(f"  ✅ {scenario_name}: 성공")
            else:
                logger.info(f"  ❌ {scenario_name}: 실패 - {result['error']}")
        
        # 통합 성능 리포트 생성
        comprehensive_report = monitoring_integration.generate_integrated_report(
            time_range_minutes=10
        )
        
        if comprehensive_report:
            logger.info("📋 종합 성능 리포트:")
            logger.info(f"  전체 모니터링 시간: {comprehensive_report.get('monitoring_duration', 0):.0f}초")
            logger.info(f"  수집된 총 메트릭: {comprehensive_report.get('total_metrics', 0)}개")
            logger.info(f"  시스템 안정성: {comprehensive_report.get('system_stability', 0):.1%}")
            logger.info(f"  AI 에이전트 효율성: {comprehensive_report.get('agent_efficiency', 0):.1%}")
        
        # 전체 시스템 정리
        logger.info("🧹 전체 시스템 정리 중...")
        
        await crawling_service.stop_service()
        await gcp_optimization_service.stop_service()
        await monitoring_integration.stop_integrated_monitoring()
        await performance_monitor.stop_monitoring()
        
        logger.info("✅ 크롤링 시스템 통합 종합 데모 완료")
        
        return demo_results
    
    async def _demo_immediate_crawling(self, crawling_service, monitoring_integration, gcp_optimization_service):
        """즉시 크롤링 작업 데모"""
        targets = [
            {"name": "데모교회1", "category": "교회", "search_keywords": ["데모교회1"]},
            {"name": "데모학원1", "category": "학원", "search_keywords": ["데모학원1"]},
            {"name": "데모구청1", "category": "주민센터", "search_keywords": ["데모구청1"]}
        ]
        
        job_id = await crawling_service.submit_crawling_job(
            targets=targets,
            strategy=CrawlingStrategy.BALANCED
        )
        
        # 작업 완료 대기
        for _ in range(30):
            await asyncio.sleep(2)
            status = crawling_service.get_job_status(job_id)
            if status and status.get("status") in ["completed", "failed"]:
                break
        
        final_status = crawling_service.get_job_status(job_id)
        return {
            "job_id": job_id,
            "status": final_status.get("status") if final_status else "timeout",
            "targets_processed": len(targets)
        }
    
    async def _demo_scheduled_setup(self, crawling_service, monitoring_integration, gcp_optimization_service):
        """스케줄된 크롤링 설정 데모"""
        schedule_targets = [
            {"name": "스케줄데모", "category": "교회", "search_keywords": ["스케줄데모"]}
        ]
        
        success = await crawling_service.schedule_crawling_job(
            schedule_id="demo_schedule",
            targets=schedule_targets,
            cron_expression="*/1 * * * *",  # 매분 실행 (데모용)
            strategy=CrawlingStrategy.CONSERVATIVE
        )
        
        # 스케줄 확인
        scheduled_jobs = crawling_service.get_scheduled_jobs()
        
        return {
            "schedule_created": success,
            "total_schedules": len(scheduled_jobs),
            "schedule_id": "demo_schedule"
        }
    
    async def _demo_bulk_processing(self, crawling_service, monitoring_integration, gcp_optimization_service):
        """대량 크롤링 처리 데모"""
        bulk_targets = [
            {"name": f"벌크{i:02d}", "category": "교회", "search_keywords": [f"벌크{i:02d}"]}
            for i in range(15)
        ]
        
        job_id = await crawling_service.submit_crawling_job(
            targets=bulk_targets,
            strategy=CrawlingStrategy.AGGRESSIVE,
            job_options={"max_concurrent": 8}
        )
        
        # 처리 상황 모니터링
        for _ in range(45):
            await asyncio.sleep(2)
            status = crawling_service.get_job_status(job_id)
            if status and status.get("status") in ["completed", "failed"]:
                break
        
        final_status = crawling_service.get_job_status(job_id)
        
        return {
            "job_id": job_id,
            "targets_count": len(bulk_targets),
            "status": final_status.get("status") if final_status else "timeout",
            "success_rate": final_status.get("success_rate", 0) if final_status else 0
        }
    
    async def _demo_optimization_test(self, crawling_service, monitoring_integration, gcp_optimization_service):
        """성능 최적화 테스트 데모"""
        # 최적화 트리거
        await gcp_optimization_service.trigger_optimization_analysis()
        
        # 최적화 상태 확인
        await asyncio.sleep(5)
        
        optimization_metrics = gcp_optimization_service.get_service_metrics()
        
        return {
            "optimization_triggered": True,
            "total_optimizations": optimization_metrics.total_optimizations,
            "successful_optimizations": optimization_metrics.successful_optimizations
        }
    
    async def _demo_real_time_tracking(self, crawling_service, monitoring_integration, gcp_optimization_service):
        """실시간 모니터링 데모"""
        # 모니터링 상태 수집
        tracking_data = []
        
        for i in range(6):  # 30초간 5초씩 수집
            await asyncio.sleep(5)
            
            service_metrics = crawling_service.get_service_metrics()
            monitoring_status = monitoring_integration.get_monitoring_status()
            
            tracking_data.append({
                "timestamp": datetime.now().isoformat(),
                "active_jobs": service_metrics["active_jobs_count"],
                "completed_jobs": service_metrics["completed_jobs_count"],
                "monitoring_agents": monitoring_status.get("active_agents", 0)
            })
        
        return {
            "tracking_duration": 30,
            "data_points": len(tracking_data),
            "final_metrics": tracking_data[-1] if tracking_data else {}
        }


# 사용 예제 실행 함수
async def run_crawling_integration_examples():
    """크롤링 통합 예제 실행"""
    examples = CrawlingIntegrationExamples()
    await examples.run_all_examples()


if __name__ == "__main__":
    # 개별 예제 실행
    asyncio.run(run_crawling_integration_examples()) 