# 검색 전략 최적화 에이전트
# 크롤링 검색 전략을 지능적으로 선택하고 최적화하는 AI 에이전트

from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from datetime import datetime
import asyncio
import json
import logging
from enum import Enum

from ..core.agent_base import BaseAgent, AgentResult, AgentConfig
from ..utils.gemini_client import GeminiClient
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

logger = logging.getLogger(__name__)

class SearchMethod(Enum):
    """검색 방법 열거형"""
    GOOGLE_SEARCH = "google_search"
    NAVER_MAP = "naver_map" 
    DIRECT_URL = "direct_url"
    ORGANIZATION_DB = "organization_db"
    EXTERNAL_API = "external_api"

@dataclass
class SearchTarget:
    """검색 대상 정보"""
    name: str                    # 기관명
    category: str               # 카테고리 (교회, 학원 등)
    address: Optional[str] = None  # 주소
    phone: Optional[str] = None   # 전화번호
    region: Optional[str] = None  # 지역
    keywords: List[str] = None    # 검색 키워드
    priority: int = 1            # 우선순위 (1: 높음, 3: 낮음)

@dataclass
class SearchStrategy:
    """검색 전략 정보"""
    target: SearchTarget
    methods: List[SearchMethod]   # 사용할 검색 방법 순서
    keywords: List[str]          # 최적화된 검색 키워드
    expected_success_rate: float # 예상 성공률 (0.0 ~ 1.0)
    estimated_time: int         # 예상 소요 시간 (초)
    confidence_score: float     # 전략 신뢰도
    reasoning: str              # 전략 선택 이유

@dataclass
class SearchResult:
    """검색 결과 정보"""
    target: SearchTarget
    method_used: SearchMethod
    success: bool
    data_found: Dict[str, Any]
    execution_time: float
    confidence: float
    error_message: Optional[str] = None

class SearchStrategyAgent(BaseAgent):
    """
    검색 전략 최적화 에이전트
    
    기능:
    - 기관 정보에 따른 최적 검색 전략 생성
    - 다중 검색 방법 조율 및 우선순위 결정
    - 검색 성공률 예측 및 최적화
    - 실시간 전략 조정 및 학습
    """
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.search_history: List[SearchResult] = []
        self.strategy_templates = self._load_strategy_templates()
        
        # Langchain 프롬프트 템플릿 정의
        self.strategy_prompt = PromptTemplate(
            input_variables=["target_info", "search_history", "available_methods"],
            template="""
            다음 기관 정보에 대한 최적 검색 전략을 생성해주세요:

            기관 정보:
            {target_info}

            사용 가능한 검색 방법:
            {available_methods}

            과거 검색 성과:
            {search_history}

            요청사항:
            1. 가장 효과적인 검색 방법 순서 결정
            2. 최적화된 검색 키워드 생성
            3. 예상 성공률과 소요시간 추정
            4. 전략 선택 이유 설명

            JSON 형식으로 응답해주세요:
            {{
                "methods": ["method1", "method2", "method3"],
                "keywords": ["keyword1", "keyword2"],
                "expected_success_rate": 0.85,
                "estimated_time": 30,
                "confidence_score": 0.9,
                "reasoning": "전략 선택 이유"
            }}
            """
        )
        
        # 키워드 최적화 프롬프트
        self.keyword_prompt = PromptTemplate(
            input_variables=["organization_name", "category", "address"],
            template="""
            다음 기관의 검색 키워드를 최적화해주세요:

            기관명: {organization_name}
            카테고리: {category}
            주소: {address}

            효과적인 검색을 위한 키워드를 생성해주세요:
            1. 기본 키워드: 기관명과 카테고리 조합
            2. 지역 키워드: 주소 기반 지역명
            3. 유사 키워드: 동의어나 약어
            4. 부정 키워드: 제외할 키워드

            JSON 형식으로 응답:
            {{
                "primary_keywords": ["keyword1", "keyword2"],
                "regional_keywords": ["region1", "region2"],
                "alternative_keywords": ["alt1", "alt2"],
                "negative_keywords": ["exclude1", "exclude2"]
            }}
            """
        )
    
    def _load_strategy_templates(self) -> Dict[str, Any]:
        """전략 템플릿 로드"""
        return {
            "church": {
                "primary_methods": [SearchMethod.GOOGLE_SEARCH, SearchMethod.NAVER_MAP],
                "keywords": ["교회", "성당", "예배", "목사", "신부"],
                "success_rate": 0.85
            },
            "academy": {
                "primary_methods": [SearchMethod.NAVER_MAP, SearchMethod.GOOGLE_SEARCH],
                "keywords": ["학원", "교습소", "과외", "교육"],
                "success_rate": 0.78
            },
            "community_center": {
                "primary_methods": [SearchMethod.GOOGLE_SEARCH, SearchMethod.ORGANIZATION_DB],
                "keywords": ["주민센터", "동사무소", "구청", "시청"],
                "success_rate": 0.92
            },
            "default": {
                "primary_methods": [SearchMethod.GOOGLE_SEARCH, SearchMethod.NAVER_MAP],
                "keywords": [],
                "success_rate": 0.70
            }
        }
    
    async def process(self, data: Dict[str, Any]) -> AgentResult:
        """
        검색 전략 생성 메인 프로세스
        
        Args:
            data: {
                "targets": List[SearchTarget] 또는 Dict,
                "constraints": Dict (시간 제한, 리소스 제한 등),
                "preferences": Dict (선호 검색 방법 등)
            }
        
        Returns:
            AgentResult: 생성된 검색 전략들
        """
        try:
            # 입력 데이터 파싱
            targets = self._parse_targets(data.get("targets", []))
            constraints = data.get("constraints", {})
            preferences = data.get("preferences", {})
            
            strategies = []
            
            for target in targets:
                # 개별 기관에 대한 검색 전략 생성
                strategy = await self._generate_strategy(target, constraints, preferences)
                strategies.append(strategy)
                
                # 메트릭 업데이트
                self.metrics.processed_items += 1
            
            result_data = {
                "strategies": [asdict(strategy) for strategy in strategies],
                "total_targets": len(targets),
                "average_success_rate": sum(s.expected_success_rate for s in strategies) / len(strategies) if strategies else 0,
                "total_estimated_time": sum(s.estimated_time for s in strategies)
            }
            
            self.metrics.success_count += len(strategies)
            
            return AgentResult(
                success=True,
                data=result_data,
                message=f"{len(strategies)}개 기관에 대한 검색 전략 생성 완료",
                execution_time=self.metrics.get_execution_time(),
                metadata={
                    "agent_type": "SearchStrategyAgent",
                    "strategy_count": len(strategies),
                    "processing_time": datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"검색 전략 생성 실패: {str(e)}")
            self.metrics.error_count += 1
            
            return AgentResult(
                success=False,
                data={},
                message=f"검색 전략 생성 실패: {str(e)}",
                execution_time=self.metrics.get_execution_time(),
                metadata={"error": str(e)}
            )
    
    def _parse_targets(self, targets_data: Union[List, Dict]) -> List[SearchTarget]:
        """검색 대상 데이터 파싱"""
        targets = []
        
        if isinstance(targets_data, dict):
            targets_data = [targets_data]
        
        for target_data in targets_data:
            if isinstance(target_data, dict):
                target = SearchTarget(
                    name=target_data.get("name", ""),
                    category=target_data.get("category", ""),
                    address=target_data.get("address"),
                    phone=target_data.get("phone"),
                    region=target_data.get("region"),
                    keywords=target_data.get("keywords", []),
                    priority=target_data.get("priority", 1)
                )
                targets.append(target)
        
        return targets
    
    async def _generate_strategy(self, target: SearchTarget, constraints: Dict, preferences: Dict) -> SearchStrategy:
        """개별 기관에 대한 검색 전략 생성"""
        try:
            # 기본 전략 템플릿 선택
            template = self.strategy_templates.get(target.category.lower(), self.strategy_templates["default"])
            
            # AI 기반 전략 최적화
            optimized_strategy = await self._optimize_strategy_with_ai(target, template, constraints)
            
            # 키워드 최적화
            optimized_keywords = await self._optimize_keywords(target)
            
            # 검색 방법 우선순위 결정
            methods = self._prioritize_methods(target, template, preferences)
            
            # 성공률 및 시간 추정
            success_rate = self._estimate_success_rate(target, methods)
            estimated_time = self._estimate_execution_time(target, methods)
            
            return SearchStrategy(
                target=target,
                methods=methods,
                keywords=optimized_keywords,
                expected_success_rate=success_rate,
                estimated_time=estimated_time,
                confidence_score=optimized_strategy.get("confidence_score", 0.8),
                reasoning=optimized_strategy.get("reasoning", "기본 템플릿 기반 전략")
            )
            
        except Exception as e:
            logger.error(f"전략 생성 실패 - {target.name}: {str(e)}")
            # 기본 전략 반환
            return self._get_fallback_strategy(target)
    
    async def _optimize_strategy_with_ai(self, target: SearchTarget, template: Dict, constraints: Dict) -> Dict:
        """AI를 이용한 검색 전략 최적화"""
        try:
            # 검색 히스토리 요약
            history_summary = self._summarize_search_history(target.category)
            
            # 사용 가능한 검색 방법 목록
            available_methods = [method.value for method in SearchMethod]
            
            # AI 체인 생성
            chain = LLMChain(
                llm=self.gemini_client.get_llm(),
                prompt=self.strategy_prompt
            )
            
            # AI 실행
            response = await chain.arun(
                target_info=f"이름: {target.name}, 카테고리: {target.category}, 주소: {target.address}",
                search_history=history_summary,
                available_methods=", ".join(available_methods)
            )
            
            # JSON 응답 파싱
            strategy_data = json.loads(response.strip())
            return strategy_data
            
        except Exception as e:
            logger.warning(f"AI 전략 최적화 실패: {str(e)}")
            return {
                "methods": [method.value for method in template["primary_methods"]],
                "keywords": template["keywords"],
                "expected_success_rate": template["success_rate"],
                "estimated_time": 30,
                "confidence_score": 0.7,
                "reasoning": "템플릿 기반 기본 전략"
            }
    
    async def _optimize_keywords(self, target: SearchTarget) -> List[str]:
        """키워드 최적화"""
        try:
            # AI 체인으로 키워드 최적화
            chain = LLMChain(
                llm=self.gemini_client.get_llm(),
                prompt=self.keyword_prompt
            )
            
            response = await chain.arun(
                organization_name=target.name,
                category=target.category,
                address=target.address or "주소 없음"
            )
            
            keyword_data = json.loads(response.strip())
            
            # 모든 키워드 합치기
            all_keywords = []
            all_keywords.extend(keyword_data.get("primary_keywords", []))
            all_keywords.extend(keyword_data.get("regional_keywords", []))
            all_keywords.extend(keyword_data.get("alternative_keywords", []))
            
            # 기존 키워드와 병합
            if target.keywords:
                all_keywords.extend(target.keywords)
            
            # 중복 제거 및 상위 10개 선택
            unique_keywords = list(set(all_keywords))
            return unique_keywords[:10]
            
        except Exception as e:
            logger.warning(f"키워드 최적화 실패: {str(e)}")
            # 기본 키워드 반환
            basic_keywords = [target.name, target.category]
            if target.keywords:
                basic_keywords.extend(target.keywords)
            return basic_keywords[:5]
    
    def _prioritize_methods(self, target: SearchTarget, template: Dict, preferences: Dict) -> List[SearchMethod]:
        """검색 방법 우선순위 결정"""
        methods = []
        
        # 템플릿 기본 방법
        primary_methods = template.get("primary_methods", [SearchMethod.GOOGLE_SEARCH])
        methods.extend(primary_methods)
        
        # 사용자 선호도 반영
        preferred_methods = preferences.get("preferred_methods", [])
        for method_name in preferred_methods:
            try:
                method = SearchMethod(method_name)
                if method not in methods:
                    methods.insert(0, method)  # 선호 방법을 앞으로
            except ValueError:
                continue
        
        # 기관 특성에 따른 조정
        if target.address and SearchMethod.NAVER_MAP not in methods:
            methods.append(SearchMethod.NAVER_MAP)
        
        if target.phone and SearchMethod.ORGANIZATION_DB not in methods:
            methods.append(SearchMethod.ORGANIZATION_DB)
        
        return methods[:4]  # 최대 4개 방법
    
    def _estimate_success_rate(self, target: SearchTarget, methods: List[SearchMethod]) -> float:
        """성공률 추정"""
        base_rate = 0.7
        
        # 카테고리별 조정
        category_multipliers = {
            "church": 1.2,
            "academy": 1.1,
            "community_center": 1.3,
        }
        
        category_multiplier = category_multipliers.get(target.category.lower(), 1.0)
        
        # 검색 방법 수에 따른 조정
        method_bonus = min(len(methods) * 0.1, 0.3)
        
        # 정보 완성도에 따른 조정
        info_bonus = 0
        if target.address:
            info_bonus += 0.1
        if target.phone:
            info_bonus += 0.1
        if target.keywords:
            info_bonus += 0.05
        
        # 과거 성과 반영
        history_bonus = self._get_historical_success_rate(target.category) * 0.1
        
        final_rate = base_rate * category_multiplier + method_bonus + info_bonus + history_bonus
        return min(final_rate, 0.98)  # 최대 98%
    
    def _estimate_execution_time(self, target: SearchTarget, methods: List[SearchMethod]) -> int:
        """실행 시간 추정 (초)"""
        method_times = {
            SearchMethod.GOOGLE_SEARCH: 15,
            SearchMethod.NAVER_MAP: 20,
            SearchMethod.DIRECT_URL: 10,
            SearchMethod.ORGANIZATION_DB: 5,
            SearchMethod.EXTERNAL_API: 8
        }
        
        total_time = sum(method_times.get(method, 15) for method in methods)
        
        # 기관 복잡도에 따른 조정
        if len(target.name) > 20:  # 긴 기관명
            total_time *= 1.2
        
        if target.category in ["church", "academy"]:  # 복잡한 카테고리
            total_time *= 1.1
        
        return int(total_time)
    
    def _get_historical_success_rate(self, category: str) -> float:
        """카테고리별 과거 성공률 조회"""
        if not self.search_history:
            return 0.0
        
        category_results = [r for r in self.search_history if r.target.category == category]
        if not category_results:
            return 0.0
        
        success_count = sum(1 for r in category_results if r.success)
        return success_count / len(category_results)
    
    def _summarize_search_history(self, category: str) -> str:
        """검색 히스토리 요약"""
        if not self.search_history:
            return "과거 검색 기록 없음"
        
        category_results = [r for r in self.search_history if r.target.category == category]
        if not category_results:
            return f"{category} 카테고리 검색 기록 없음"
        
        success_rate = sum(1 for r in category_results if r.success) / len(category_results)
        avg_time = sum(r.execution_time for r in category_results) / len(category_results)
        
        return f"{category} 카테고리: 성공률 {success_rate:.2%}, 평균 소요시간 {avg_time:.1f}초, 총 {len(category_results)}건"
    
    def _get_fallback_strategy(self, target: SearchTarget) -> SearchStrategy:
        """기본 전략 반환 (오류 시)"""
        return SearchStrategy(
            target=target,
            methods=[SearchMethod.GOOGLE_SEARCH, SearchMethod.NAVER_MAP],
            keywords=[target.name, target.category],
            expected_success_rate=0.6,
            estimated_time=30,
            confidence_score=0.5,
            reasoning="오류로 인한 기본 전략"
        )
    
    async def update_search_result(self, result: SearchResult):
        """검색 결과 업데이트 (학습용)"""
        self.search_history.append(result)
        
        # 히스토리 크기 제한 (최근 1000개만 유지)
        if len(self.search_history) > 1000:
            self.search_history = self.search_history[-1000:]
        
        logger.info(f"검색 결과 업데이트: {result.target.name} - {'성공' if result.success else '실패'}")
    
    async def get_strategy_performance(self) -> Dict[str, Any]:
        """전략 성능 분석"""
        if not self.search_history:
            return {"message": "검색 기록 없음"}
        
        total_searches = len(self.search_history)
        successful_searches = sum(1 for r in self.search_history if r.success)
        success_rate = successful_searches / total_searches
        
        # 방법별 성능
        method_performance = {}
        for method in SearchMethod:
            method_results = [r for r in self.search_history if r.method_used == method]
            if method_results:
                method_success_rate = sum(1 for r in method_results if r.success) / len(method_results)
                avg_time = sum(r.execution_time for r in method_results) / len(method_results)
                method_performance[method.value] = {
                    "success_rate": method_success_rate,
                    "average_time": avg_time,
                    "usage_count": len(method_results)
                }
        
        # 카테고리별 성능
        category_performance = {}
        categories = set(r.target.category for r in self.search_history)
        for category in categories:
            category_results = [r for r in self.search_history if r.target.category == category]
            category_success_rate = sum(1 for r in category_results if r.success) / len(category_results)
            category_performance[category] = {
                "success_rate": category_success_rate,
                "count": len(category_results)
            }
        
        return {
            "overall_performance": {
                "total_searches": total_searches,
                "success_rate": success_rate,
                "successful_searches": successful_searches
            },
            "method_performance": method_performance,
            "category_performance": category_performance,
            "last_updated": datetime.now().isoformat()
        } 