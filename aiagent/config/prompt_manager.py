# Langchain PromptTemplate 기반 프롬프트 관리 시스템
# 모든 AI 프롬프트를 중앙 집중식으로 관리하고 동적으로 생성하는 시스템

from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
import json
import logging
from enum import Enum
from pathlib import Path
import yaml

from langchain.prompts import PromptTemplate, ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain.prompts.few_shot import FewShotPromptTemplate
from langchain.prompts.example_selector import SemanticSimilarityExampleSelector
from langchain.schema import BaseMessage
from ..utils.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

class PromptType(Enum):
    """프롬프트 유형"""
    SIMPLE = "simple"                    # 단순 텍스트 프롬프트
    CHAT = "chat"                       # 채팅 형식 프롬프트
    FEW_SHOT = "few_shot"              # Few-shot 학습 프롬프트
    CHAIN_OF_THOUGHT = "chain_of_thought"  # 사고 과정 프롬프트
    SYSTEM_INSTRUCTION = "system_instruction"  # 시스템 지시사항
    EXTRACTION = "extraction"           # 데이터 추출 프롬프트
    VALIDATION = "validation"           # 검증 프롬프트
    OPTIMIZATION = "optimization"       # 최적화 프롬프트

class PromptCategory(Enum):
    """프롬프트 카테고리"""
    SEARCH_STRATEGY = "search_strategy"
    CONTACT_EXTRACTION = "contact_extraction"  
    DATA_VALIDATION = "data_validation"
    PERFORMANCE_OPTIMIZATION = "performance_optimization"
    WORKFLOW_COORDINATION = "workflow_coordination"
    GENERAL_ANALYSIS = "general_analysis"

@dataclass
class PromptMetadata:
    """프롬프트 메타데이터"""
    id: str                             # 프롬프트 ID
    name: str                           # 프롬프트 이름
    description: str                    # 설명
    category: PromptCategory            # 카테고리
    prompt_type: PromptType             # 프롬프트 타입
    version: str = "1.0"                # 버전
    created_at: datetime = None         # 생성 시간
    updated_at: datetime = None         # 수정 시간
    tags: List[str] = None              # 태그
    usage_count: int = 0                # 사용 횟수
    success_rate: float = 0.0           # 성공률

@dataclass  
class PromptExample:
    """Few-shot 학습용 예시"""
    input_data: Dict[str, Any]          # 입력 데이터
    expected_output: str                # 예상 출력
    explanation: Optional[str] = None    # 설명

@dataclass
class PromptTemplate:
    """프롬프트 템플릿 정의"""
    metadata: PromptMetadata            # 메타데이터
    template: str                       # 템플릿 텍스트
    input_variables: List[str]          # 입력 변수들
    output_format: str = "text"         # 출력 형식 (text, json, xml)
    examples: List[PromptExample] = None  # Few-shot 예시들
    system_message: Optional[str] = None  # 시스템 메시지
    validation_rules: List[str] = None   # 검증 규칙들

class PromptManager:
    """
    Langchain PromptTemplate 기반 프롬프트 관리 시스템
    
    기능:
    - 중앙 집중식 프롬프트 저장소 관리
    - 동적 프롬프트 생성 및 최적화
    - Few-shot 학습 지원
    - 프롬프트 버전 관리
    - 사용 통계 및 성능 분석
    - 다국어 프롬프트 지원
    """
    
    def __init__(self, config_dir: Optional[str] = None):
        self.config_dir = Path(config_dir) if config_dir else Path(__file__).parent / "prompts"
        self.prompts: Dict[str, PromptTemplate] = {}
        self.langchain_templates: Dict[str, Any] = {}
        self.usage_stats: Dict[str, Dict] = {}
        self.gemini_client = GeminiClient()
        
        # 프롬프트 로드
        self._load_default_prompts()
        self._load_custom_prompts()
        
        logger.info(f"프롬프트 관리자 초기화 완료: {len(self.prompts)}개 프롬프트 로드")
    
    def _load_default_prompts(self):
        """기본 프롬프트 세트 로드"""
        
        # 1. 검색 전략 프롬프트들
        self._register_search_strategy_prompts()
        
        # 2. 연락처 추출 프롬프트들
        self._register_contact_extraction_prompts()
        
        # 3. 데이터 검증 프롬프트들
        self._register_validation_prompts()
        
        # 4. 성능 최적화 프롬프트들
        self._register_optimization_prompts()
        
        # 5. 워크플로우 조정 프롬프트들
        self._register_workflow_prompts()
        
        # 6. 일반 분석 프롬프트들
        self._register_general_analysis_prompts()
    
    def _register_search_strategy_prompts(self):
        """검색 전략 관련 프롬프트 등록"""
        
        # 검색 전략 생성 프롬프트
        strategy_generation_prompt = PromptTemplate(
            metadata=PromptMetadata(
                id="search_strategy_generation",
                name="검색 전략 생성",
                description="기관 정보를 기반으로 최적의 검색 전략을 생성합니다",
                category=PromptCategory.SEARCH_STRATEGY,
                prompt_type=PromptType.CHAIN_OF_THOUGHT,
                tags=["strategy", "optimization", "crawling"]
            ),
            template="""
다음 기관 정보를 분석하여 최적의 크롤링 검색 전략을 단계별로 생성해주세요:

기관 정보:
- 이름: {organization_name}
- 카테고리: {category}
- 주소: {address}
- 기존 정보: {existing_info}

사용 가능한 검색 방법:
{available_methods}

과거 성과 데이터:
{performance_history}

단계별 분석:
1. 기관 특성 분석:
   - 카테고리별 특성 파악
   - 정보 완성도 평가
   - 검색 난이도 추정

2. 검색 방법 선택:
   - 각 방법의 적합성 평가
   - 우선순위 결정 근거
   - 예상 성공률 계산

3. 키워드 최적화:
   - 기본 키워드 선정
   - 지역 기반 키워드 추가
   - 유사 키워드 확장

4. 실행 계획:
   - 검색 순서 결정
   - 시간 할당 계획
   - 실패 시 대안 방안

JSON 형식으로 최종 전략을 제시해주세요:
{{
    "analysis": {{
        "organization_characteristics": "분석 결과",
        "search_difficulty": "easy/medium/hard",
        "completeness_score": 0.75
    }},
    "strategy": {{
        "primary_methods": ["method1", "method2"],
        "keywords": ["keyword1", "keyword2", "keyword3"],
        "execution_order": ["step1", "step2", "step3"],
        "expected_success_rate": 0.85,
        "estimated_time_minutes": 15
    }},
    "reasoning": "전략 선택의 상세한 근거"
}}
            """,
            input_variables=["organization_name", "category", "address", "existing_info", "available_methods", "performance_history"],
            output_format="json",
            examples=[
                PromptExample(
                    input_data={
                        "organization_name": "새생명교회",
                        "category": "교회",
                        "address": "서울시 강남구",
                        "existing_info": "전화번호만 있음",
                        "available_methods": "Google 검색, 네이버 지도",
                        "performance_history": "교회 카테고리 성공률: 87%"
                    },
                    expected_output='{"strategy": {"primary_methods": ["naver_map", "google_search"], "keywords": ["새생명교회", "강남구", "교회"], "expected_success_rate": 0.89}}',
                    explanation="교회는 네이버 지도에서 높은 성공률을 보이므로 우선 사용"
                )
            ]
        )
        
        # 키워드 최적화 프롬프트
        keyword_optimization_prompt = PromptTemplate(
            metadata=PromptMetadata(
                id="keyword_optimization",
                name="검색 키워드 최적화",
                description="효과적인 검색을 위한 키워드를 생성하고 최적화합니다",
                category=PromptCategory.SEARCH_STRATEGY,
                prompt_type=PromptType.FEW_SHOT
            ),
            template="""
다음 기관의 검색 성공률을 높이기 위한 최적화된 키워드를 생성해주세요:

기관 정보:
- 이름: {organization_name}
- 카테고리: {category}  
- 지역: {region}
- 추가 정보: {additional_info}

키워드 생성 원칙:
1. 기본 키워드: 정확한 기관명 및 약어
2. 지역 키워드: 시/구/동 단위 지역명
3. 카테고리 키워드: 동의어 및 관련 용어
4. 부정 키워드: 제외할 혼동 용어

JSON 형식으로 응답해주세요:
{{
    "primary_keywords": ["핵심 키워드들"],
    "regional_keywords": ["지역 기반 키워드들"],
    "category_keywords": ["카테고리 관련 키워드들"],
    "negative_keywords": ["제외할 키워드들"],
    "combined_queries": ["조합된 검색 쿼리들"]
}}
            """,
            input_variables=["organization_name", "category", "region", "additional_info"],
            output_format="json"
        )
        
        self.prompts["search_strategy_generation"] = strategy_generation_prompt
        self.prompts["keyword_optimization"] = keyword_optimization_prompt
    
    def _register_contact_extraction_prompts(self):
        """연락처 추출 관련 프롬프트 등록"""
        
        # 연락처 정보 추출 프롬프트
        contact_extraction_prompt = PromptTemplate(
            metadata=PromptMetadata(
                id="contact_extraction",
                name="연락처 정보 추출",
                description="웹페이지 내용에서 기관의 연락처 정보를 추출합니다",
                category=PromptCategory.CONTACT_EXTRACTION,
                prompt_type=PromptType.EXTRACTION
            ),
            template="""
다음 웹페이지 내용에서 '{organization_name}' 기관의 연락처 정보를 정확하게 추출해주세요:

기관명: {organization_name}
카테고리: {category}

웹페이지 내용:
{webpage_content}

추출 규칙:
1. 전화번호: 02-1234-5678, 010-1234-5678 형식
2. 이메일: 유효한 이메일 주소 형식 확인
3. 주소: 완전한 주소 정보 우선
4. 홈페이지: http/https로 시작하는 URL
5. 운영시간: 요일별 시간 정보

신뢰도 평가 기준:
- 기관명과의 일치성
- 정보의 완성도
- 출처의 신뢰성

JSON 형식으로 응답해주세요:
{{
    "contact_info": {{
        "phone": "02-1234-5678 또는 null",
        "mobile": "010-1234-5678 또는 null",
        "fax": "02-1234-5679 또는 null",
        "email": "info@example.com 또는 null",
        "website": "https://example.com 또는 null",
        "address": "전체 주소 또는 null",
        "business_hours": "운영시간 또는 null"
    }},
    "confidence_score": 0.95,
    "extraction_notes": "추출 과정에서의 주요 발견사항",
    "data_quality": "excellent/good/fair/poor"
}}
            """,
            input_variables=["organization_name", "category", "webpage_content"],
            output_format="json"
        )
        
        # 연락처 정보 검증 프롬프트
        contact_verification_prompt = PromptTemplate(
            metadata=PromptMetadata(
                id="contact_verification",
                name="연락처 정보 검증",
                description="추출된 연락처 정보의 정확성을 검증합니다",
                category=PromptCategory.CONTACT_EXTRACTION,
                prompt_type=PromptType.VALIDATION
            ),
            template="""
다음 연락처 정보가 '{organization_name}' 기관의 것인지 검증해주세요:

기관 정보:
- 이름: {organization_name}
- 카테고리: {category}
- 예상 지역: {expected_region}

추출된 연락처:
{contact_data}

검증 소스:
{verification_sources}

검증 항목:
1. 전화번호 지역번호와 주소의 일치성
2. 이메일 도메인의 적절성
3. 웹사이트 URL의 유효성
4. 기관명과 연락처 정보의 연관성
5. 정보 간의 일관성

JSON 형식으로 검증 결과를 제시해주세요:
{{
    "verification_result": {{
        "is_valid": true/false,
        "confidence_level": "high/medium/low",
        "verified_fields": ["phone", "email", "website"],
        "questionable_fields": ["fax"],
        "missing_fields": ["mobile"]
    }},
    "detailed_analysis": {{
        "phone_analysis": "지역번호 분석 결과",
        "email_analysis": "이메일 도메인 분석 결과", 
        "website_analysis": "웹사이트 유효성 분석 결과",
        "consistency_check": "정보 간 일관성 분석"
    }},
    "recommendations": ["개선 권장사항들"],
    "overall_score": 0.85
}}
            """,
            input_variables=["organization_name", "category", "expected_region", "contact_data", "verification_sources"],
            output_format="json"
        )
        
        self.prompts["contact_extraction"] = contact_extraction_prompt
        self.prompts["contact_verification"] = contact_verification_prompt
    
    def _register_validation_prompts(self):
        """데이터 검증 관련 프롬프트 등록"""
        
        # 데이터 품질 분석 프롬프트
        data_quality_analysis_prompt = PromptTemplate(
            metadata=PromptMetadata(
                id="data_quality_analysis",
                name="데이터 품질 분석",
                description="크롤링된 데이터의 품질을 종합적으로 분석합니다",
                category=PromptCategory.DATA_VALIDATION,
                prompt_type=PromptType.CHAIN_OF_THOUGHT
            ),
            template="""
다음 기관 데이터의 품질을 종합적으로 분석하고 평가해주세요:

기관 데이터:
{organization_data}

품질 분석 기준:
1. 완성도 (Completeness): 필수 필드 존재 여부
2. 정확성 (Accuracy): 데이터 형식 및 논리적 정확성
3. 일관성 (Consistency): 필드 간 정보 일치성
4. 신뢰성 (Reliability): 출처 및 검증 가능성
5. 시의성 (Timeliness): 정보의 최신성

단계별 분석:

1단계 - 완성도 분석:
- 필수 필드 (이름, 카테고리) 존재 확인
- 연락처 정보 (전화, 이메일 등) 완성도
- 주소 정보 완성도

2단계 - 정확성 분석:
- 전화번호 형식 검증
- 이메일 주소 형식 검증
- 주소 정보 논리성 검증

3단계 - 일관성 분석:
- 기관명과 카테고리 일치성
- 주소와 전화번호 지역 일치성
- 홈페이지와 기관 정보 일치성

4단계 - 종합 평가:
- 각 영역별 점수 계산
- 전체 품질 점수 산출
- 개선 권장사항 제시

JSON 형식으로 분석 결과를 제시해주세요:
{{
    "quality_analysis": {{
        "completeness": {{
            "score": 0.85,
            "missing_fields": ["fax", "business_hours"],
            "critical_missing": []
        }},
        "accuracy": {{
            "score": 0.92,
            "format_errors": [],
            "logical_errors": ["전화번호 지역 불일치"]
        }},
        "consistency": {{
            "score": 0.78,
            "inconsistencies": ["기관명과 홈페이지 도메인 불일치"],
            "suggestions": ["기관명 재확인 필요"]
        }},
        "reliability": {{
            "score": 0.88,
            "source_quality": "good",
            "verification_status": "partially_verified"
        }}
    }},
    "overall_quality": {{
        "total_score": 0.86,
        "grade": "B+",
        "classification": "good_quality"
    }},
    "recommendations": [
        "누락된 팩스번호 보완 필요",
        "전화번호 지역 정보 재확인",
        "홈페이지 도메인 검증 필요"
    ],
    "priority_actions": ["high", "medium", "low"]
}}
            """,
            input_variables=["organization_data"],
            output_format="json"
        )
        
        # 일관성 검증 프롬프트
        consistency_validation_prompt = PromptTemplate(
            metadata=PromptMetadata(
                id="consistency_validation",
                name="데이터 일관성 검증",
                description="데이터 필드 간의 논리적 일관성을 검증합니다",
                category=PromptCategory.DATA_VALIDATION,
                prompt_type=PromptType.VALIDATION
            ),
            template="""
다음 기관 데이터의 논리적 일관성을 검증해주세요:

기관 정보:
- 이름: {organization_name}
- 카테고리: {category}
- 주소: {address}
- 전화번호: {phone}
- 이메일: {email}
- 홈페이지: {website}

검증 규칙:
1. 기관명-카테고리 일치성: 이름에 카테고리 관련 키워드 포함 여부
2. 주소-전화번호 일치성: 지역번호와 주소 지역 일치성
3. 이메일-홈페이지 일치성: 도메인 일치성
4. 카테고리별 특수 규칙 적용

JSON 형식으로 검증 결과를 제시해주세요:
{{
    "consistency_checks": {{
        "name_category_match": {{
            "is_consistent": true/false,
            "confidence": 0.95,
            "details": "분석 세부사항"
        }},
        "address_phone_match": {{
            "is_consistent": true/false,
            "expected_area_code": "02",
            "actual_area_code": "031",
            "details": "지역번호 분석"
        }},
        "email_website_match": {{
            "is_consistent": true/false,
            "email_domain": "example.com",
            "website_domain": "example.org",
            "details": "도메인 일치성 분석"
        }}
    }},
    "overall_consistency": {{
        "score": 0.87,
        "status": "mostly_consistent",
        "major_issues": [],
        "minor_issues": ["도메인 불일치"]
    }},
    "recommendations": [
        "권장 수정사항들"
    ]
}}
            """,
            input_variables=["organization_name", "category", "address", "phone", "email", "website"],
            output_format="json"
        )
        
        self.prompts["data_quality_analysis"] = data_quality_analysis_prompt
        self.prompts["consistency_validation"] = consistency_validation_prompt
    
    def _register_optimization_prompts(self):
        """성능 최적화 관련 프롬프트 등록"""
        
        # 시스템 성능 분석 프롬프트
        performance_analysis_prompt = PromptTemplate(
            metadata=PromptMetadata(
                id="performance_analysis",
                name="시스템 성능 분석",
                description="시스템 지표를 분석하여 성능 병목점을 찾고 최적화 방안을 제시합니다",
                category=PromptCategory.PERFORMANCE_OPTIMIZATION,
                prompt_type=PromptType.CHAIN_OF_THOUGHT
            ),
            template="""
다음 시스템 성능 지표를 분석하여 최적화 방안을 제시해주세요:

현재 시스템 상태:
- CPU 사용률: {cpu_usage}%
- 메모리 사용률: {memory_usage}%
- 디스크 사용률: {disk_usage}%
- 네트워크 I/O: {network_io}

크롤링 성능 지표:
- 분당 처리량: {requests_per_minute}개
- 성공률: {success_rate}%
- 평균 응답시간: {avg_response_time}초
- 오류율: {error_rate}%

시스템 환경:
- 플랫폼: GCP e2-small (2 vCPU, 4GB RAM)
- 동시 워커 수: {concurrent_workers}개
- 배치 크기: {batch_size}개

분석 단계:

1단계 - 리소스 사용 패턴 분석:
- 각 리소스의 사용률 평가
- 병목 지점 식별
- 리소스 간 상관관계 분석

2단계 - 성능 지표 분석:
- 처리량과 리소스 사용률 비교
- 성공률 저하 원인 분석
- 응답시간 지연 요인 파악

3단계 - 최적화 기회 식별:
- 단기 개선 가능 영역
- 장기 최적화 방향
- 비용 대비 효과 분석

4단계 - 구체적 권장사항:
- 즉시 적용 가능한 조치
- 단계별 개선 계획
- 예상 성능 향상률

JSON 형식으로 분석 결과를 제시해주세요:
{{
    "performance_analysis": {{
        "bottlenecks": [
            {{
                "resource": "cpu/memory/network/disk",
                "severity": "high/medium/low",
                "impact": "처리량에 미치는 영향",
                "cause": "병목 원인 분석"
            }}
        ],
        "efficiency_metrics": {{
            "resource_efficiency": 0.75,
            "throughput_efficiency": 0.68,
            "cost_efficiency": 0.82
        }}
    }},
    "optimization_recommendations": [
        {{
            "type": "immediate/short_term/long_term",
            "action": "구체적 조치 사항",
            "expected_improvement": "25% 처리량 향상",
            "implementation_effort": "low/medium/high",
            "risk_level": "low/medium/high"
        }}
    ],
    "predicted_outcomes": {{
        "cpu_reduction": "15%",
        "memory_optimization": "20%", 
        "throughput_increase": "30%",
        "success_rate_improvement": "5%"
    }}
}}
            """,
            input_variables=["cpu_usage", "memory_usage", "disk_usage", "network_io", 
                            "requests_per_minute", "success_rate", "avg_response_time", "error_rate",
                            "concurrent_workers", "batch_size"],
            output_format="json"
        )
        
        self.prompts["performance_analysis"] = performance_analysis_prompt
    
    def _register_workflow_prompts(self):
        """워크플로우 관련 프롬프트 등록"""
        
        # 워크플로우 최적화 프롬프트
        workflow_optimization_prompt = PromptTemplate(
            metadata=PromptMetadata(
                id="workflow_optimization",
                name="워크플로우 최적화",
                description="워크플로우 실행 히스토리를 분석하여 최적화 방안을 제시합니다",
                category=PromptCategory.WORKFLOW_COORDINATION,
                prompt_type=PromptType.OPTIMIZATION
            ),
            template="""
다음 워크플로우의 실행 히스토리를 분석하여 최적화 방안을 제시해주세요:

워크플로우 정의:
{workflow_definition}

실행 히스토리 (최근 5회):
{execution_history}

성능 통계:
- 평균 실행 시간: {avg_execution_time}초
- 평균 성공률: {avg_success_rate}%
- 공통 실패 패턴: {common_failures}
- 병목 작업: {bottleneck_tasks}

분석 영역:
1. 작업 순서 최적화
2. 병렬처리 기회 식별
3. 실패 처리 개선
4. 리소스 효율성 향상

JSON 형식으로 최적화 방안을 제시해주세요:
{{
    "analysis_summary": {{
        "current_performance": "good/fair/poor",
        "main_issues": ["주요 문제점들"],
        "optimization_potential": "high/medium/low"
    }},
    "optimizations": [
        {{
            "type": "task_reordering/parallelization/error_handling/resource_management",
            "description": "최적화 설명",
            "current_approach": "현재 방식",
            "proposed_approach": "제안 방식",
            "expected_improvement": "30% 시간 단축",
            "implementation_complexity": "low/medium/high"
        }}
    ],
    "recommended_workflow": {{
        "workflow_type": "sequential/parallel/pipeline/conditional",
        "task_modifications": [
            "수정 사항들"
        ],
        "new_dependencies": [
            "추가 의존성들"
        ]
    }},
    "implementation_plan": [
        "1단계: 즉시 적용 가능한 변경",
        "2단계: 중기 개선 사항",
        "3단계: 장기 최적화 계획"
    ]
}}
            """,
            input_variables=["workflow_definition", "execution_history", "avg_execution_time", 
                            "avg_success_rate", "common_failures", "bottleneck_tasks"],
            output_format="json"
        )
        
        self.prompts["workflow_optimization"] = workflow_optimization_prompt
    
    def _register_general_analysis_prompts(self):
        """일반 분석 프롬프트 등록"""
        
        # 종합 분석 프롬프트
        comprehensive_analysis_prompt = PromptTemplate(
            metadata=PromptMetadata(
                id="comprehensive_analysis",
                name="종합 데이터 분석",
                description="수집된 모든 데이터를 종합하여 인사이트를 도출합니다",
                category=PromptCategory.GENERAL_ANALYSIS,
                prompt_type=PromptType.CHAIN_OF_THOUGHT
            ),
            template="""
다음 데이터를 종합적으로 분석하여 의미있는 인사이트를 도출해주세요:

분석 대상 데이터:
{analysis_data}

분석 컨텍스트:
- 데이터 수집 기간: {collection_period}
- 데이터 소스: {data_sources}
- 분석 목적: {analysis_purpose}

분석 관점:
1. 데이터 품질 관점
2. 비즈니스 인사이트 관점
3. 운영 최적화 관점
4. 향후 개선 방향

JSON 형식으로 분석 결과를 제시해주세요:
{{
    "executive_summary": "핵심 발견사항 요약",
    "key_insights": [
        {{
            "category": "data_quality/business/operations/improvement",
            "insight": "구체적 인사이트",
            "evidence": "근거 데이터",
            "impact": "high/medium/low",
            "actionable": true/false
        }}
    ],
    "trends_and_patterns": [
        "식별된 트렌드 및 패턴들"
    ],
    "recommendations": [
        {{
            "priority": "high/medium/low",
            "recommendation": "구체적 권장사항",
            "expected_benefit": "예상 효과",
            "implementation_timeline": "구현 일정"
        }}
    ],
    "risk_factors": [
        "주의해야 할 위험 요소들"
    ]
}}
            """,
            input_variables=["analysis_data", "collection_period", "data_sources", "analysis_purpose"],
            output_format="json"
        )
        
        self.prompts["comprehensive_analysis"] = comprehensive_analysis_prompt
    
    def _load_custom_prompts(self):
        """사용자 정의 프롬프트 로드"""
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True, exist_ok=True)
            return
        
        for prompt_file in self.config_dir.glob("*.yaml"):
            try:
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    prompt_data = yaml.safe_load(f)
                
                # YAML에서 프롬프트 객체 생성
                prompt = self._create_prompt_from_yaml(prompt_data)
                if prompt:
                    self.prompts[prompt.metadata.id] = prompt
                    logger.info(f"사용자 정의 프롬프트 로드: {prompt.metadata.id}")
                    
            except Exception as e:
                logger.error(f"프롬프트 파일 로드 실패 {prompt_file}: {str(e)}")
    
    def get_prompt(self, prompt_id: str, **kwargs) -> Optional[str]:
        """프롬프트 조회 및 포맷팅"""
        if prompt_id not in self.prompts:
            logger.error(f"프롬프트를 찾을 수 없습니다: {prompt_id}")
            return None
        
        prompt_template = self.prompts[prompt_id]
        
        try:
            # 사용 통계 업데이트
            self._update_usage_stats(prompt_id)
            
            # Langchain 템플릿 생성 또는 재사용
            langchain_template = self._get_or_create_langchain_template(prompt_template)
            
            # 프롬프트 포맷팅
            if prompt_template.prompt_type == PromptType.CHAT:
                # 채팅 형식 프롬프트
                formatted_prompt = langchain_template.format(**kwargs)
            elif prompt_template.prompt_type == PromptType.FEW_SHOT:
                # Few-shot 프롬프트
                formatted_prompt = langchain_template.format(**kwargs)
            else:
                # 일반 프롬프트
                formatted_prompt = langchain_template.format(**kwargs)
            
            return formatted_prompt
            
        except Exception as e:
            logger.error(f"프롬프트 포맷팅 실패 {prompt_id}: {str(e)}")
            return None
    
    def _get_or_create_langchain_template(self, prompt_template: PromptTemplate):
        """Langchain 템플릿 생성 또는 캐시에서 조회"""
        prompt_id = prompt_template.metadata.id
        
        if prompt_id in self.langchain_templates:
            return self.langchain_templates[prompt_id]
        
        # 프롬프트 타입에 따른 Langchain 템플릿 생성
        if prompt_template.prompt_type == PromptType.CHAT:
            # 채팅 프롬프트 템플릿
            if prompt_template.system_message:
                system_template = SystemMessagePromptTemplate.from_template(prompt_template.system_message)
                human_template = HumanMessagePromptTemplate.from_template(prompt_template.template)
                langchain_template = ChatPromptTemplate.from_messages([system_template, human_template])
            else:
                langchain_template = ChatPromptTemplate.from_template(prompt_template.template)
                
        elif prompt_template.prompt_type == PromptType.FEW_SHOT and prompt_template.examples:
            # Few-shot 프롬프트 템플릿
            examples = [
                {
                    "input": json.dumps(ex.input_data, ensure_ascii=False),
                    "output": ex.expected_output
                }
                for ex in prompt_template.examples
            ]
            
            example_prompt = PromptTemplate(
                input_variables=["input", "output"],
                template="입력: {input}\n출력: {output}"
            )
            
            langchain_template = FewShotPromptTemplate(
                examples=examples,
                example_prompt=example_prompt,
                prefix=prompt_template.template,
                suffix="입력: {input}\n출력:",
                input_variables=prompt_template.input_variables
            )
        else:
            # 일반 프롬프트 템플릿
            langchain_template = PromptTemplate(
                template=prompt_template.template,
                input_variables=prompt_template.input_variables
            )
        
        # 캐시에 저장
        self.langchain_templates[prompt_id] = langchain_template
        return langchain_template
    
    def _update_usage_stats(self, prompt_id: str):
        """프롬프트 사용 통계 업데이트"""
        if prompt_id not in self.usage_stats:
            self.usage_stats[prompt_id] = {
                "usage_count": 0,
                "success_count": 0,
                "failure_count": 0,
                "last_used": None,
                "avg_response_time": 0.0
            }
        
        stats = self.usage_stats[prompt_id]
        stats["usage_count"] += 1
        stats["last_used"] = datetime.now()
        
        # 프롬프트 객체의 사용 횟수도 업데이트
        if prompt_id in self.prompts:
            self.prompts[prompt_id].metadata.usage_count += 1
    
    def record_prompt_result(self, prompt_id: str, success: bool, response_time: float):
        """프롬프트 실행 결과 기록"""
        if prompt_id not in self.usage_stats:
            return
        
        stats = self.usage_stats[prompt_id]
        
        if success:
            stats["success_count"] += 1
        else:
            stats["failure_count"] += 1
        
        # 평균 응답 시간 업데이트
        total_executions = stats["success_count"] + stats["failure_count"]
        stats["avg_response_time"] = (
            (stats["avg_response_time"] * (total_executions - 1) + response_time) / total_executions
        )
        
        # 성공률 업데이트
        success_rate = stats["success_count"] / total_executions
        if prompt_id in self.prompts:
            self.prompts[prompt_id].metadata.success_rate = success_rate
    
    def get_prompt_list(self, category: Optional[PromptCategory] = None) -> List[PromptMetadata]:
        """프롬프트 목록 조회"""
        prompts = list(self.prompts.values())
        
        if category:
            prompts = [p for p in prompts if p.metadata.category == category]
        
        return [p.metadata for p in prompts]
    
    def get_usage_statistics(self) -> Dict[str, Any]:
        """프롬프트 사용 통계 조회"""
        total_usage = sum(stats["usage_count"] for stats in self.usage_stats.values())
        
        # 가장 많이 사용된 프롬프트
        most_used = sorted(
            self.usage_stats.items(),
            key=lambda x: x[1]["usage_count"],
            reverse=True
        )[:5]
        
        # 카테고리별 사용 통계
        category_stats = defaultdict(int)
        for prompt in self.prompts.values():
            category_stats[prompt.metadata.category.value] += prompt.metadata.usage_count
        
        return {
            "total_prompts": len(self.prompts),
            "total_usage": total_usage,
            "most_used_prompts": [
                {
                    "prompt_id": prompt_id,
                    "usage_count": stats["usage_count"],
                    "success_rate": stats["success_count"] / (stats["success_count"] + stats["failure_count"]) if (stats["success_count"] + stats["failure_count"]) > 0 else 0
                }
                for prompt_id, stats in most_used
            ],
            "category_statistics": dict(category_stats),
            "analysis_timestamp": datetime.now().isoformat()
        }
    
    def export_prompts(self, export_path: str):
        """프롬프트를 YAML 파일로 내보내기"""
        export_dir = Path(export_path)
        export_dir.mkdir(parents=True, exist_ok=True)
        
        for prompt_id, prompt in self.prompts.items():
            prompt_data = {
                "metadata": asdict(prompt.metadata),
                "template": prompt.template,
                "input_variables": prompt.input_variables,
                "output_format": prompt.output_format,
                "system_message": prompt.system_message,
                "examples": [asdict(ex) for ex in prompt.examples] if prompt.examples else None
            }
            
            file_path = export_dir / f"{prompt_id}.yaml"
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(prompt_data, f, default_flow_style=False, allow_unicode=True)
        
        logger.info(f"{len(self.prompts)}개 프롬프트를 {export_dir}에 내보냄")
    
    def _create_prompt_from_yaml(self, prompt_data: Dict) -> Optional[PromptTemplate]:
        """YAML 데이터에서 프롬프트 객체 생성"""
        try:
            metadata_data = prompt_data["metadata"]
            metadata = PromptMetadata(
                id=metadata_data["id"],
                name=metadata_data["name"],
                description=metadata_data["description"],
                category=PromptCategory(metadata_data["category"]),
                prompt_type=PromptType(metadata_data["prompt_type"]),
                version=metadata_data.get("version", "1.0"),
                tags=metadata_data.get("tags", [])
            )
            
            examples = None
            if prompt_data.get("examples"):
                examples = [
                    PromptExample(
                        input_data=ex["input_data"],
                        expected_output=ex["expected_output"],
                        explanation=ex.get("explanation")
                    )
                    for ex in prompt_data["examples"]
                ]
            
            prompt = PromptTemplate(
                metadata=metadata,
                template=prompt_data["template"],
                input_variables=prompt_data["input_variables"],
                output_format=prompt_data.get("output_format", "text"),
                examples=examples,
                system_message=prompt_data.get("system_message")
            )
            
            return prompt
            
        except Exception as e:
            logger.error(f"YAML 프롬프트 생성 실패: {str(e)}")
            return None 