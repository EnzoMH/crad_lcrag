# 연락처 정보 추출 및 보강 에이전트
# 기관의 연락처 정보(전화번호, 이메일, 팩스 등)를 자동으로 찾고 검증하는 AI 에이전트

from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import asyncio
import json
import logging
import re
import requests
from urllib.parse import urljoin, urlparse

from ..core.agent_base import BaseAgent, AgentResult, AgentConfig
from ..utils.gemini_client import GeminiClient
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

logger = logging.getLogger(__name__)

@dataclass
class ContactInfo:
    """연락처 정보 구조"""
    phone: Optional[str] = None        # 일반 전화번호
    mobile: Optional[str] = None       # 휴대폰 번호
    fax: Optional[str] = None          # 팩스 번호
    email: Optional[str] = None        # 이메일 주소
    homepage: Optional[str] = None     # 홈페이지 URL
    address: Optional[str] = None      # 주소
    postal_code: Optional[str] = None  # 우편번호
    business_hours: Optional[str] = None  # 운영시간
    
    # 메타데이터
    source_url: Optional[str] = None   # 정보 출처 URL
    extraction_method: Optional[str] = None  # 추출 방법
    confidence_score: float = 0.0      # 신뢰도 점수
    last_verified: Optional[datetime] = None  # 마지막 검증 시간

@dataclass
class ContactTarget:
    """연락처 추출 대상"""
    name: str                          # 기관명
    category: str                      # 카테고리
    existing_info: ContactInfo         # 기존 연락처 정보
    search_keywords: List[str] = None  # 검색 키워드
    target_urls: List[str] = None      # 대상 URL 목록
    priority: int = 1                  # 우선순위

@dataclass
class ExtractionResult:
    """추출 결과"""
    target: ContactTarget
    extracted_info: ContactInfo
    success: bool
    extraction_time: float
    error_message: Optional[str] = None
    sources_checked: List[str] = None

class ContactAgent(BaseAgent):
    """
    연락처 정보 추출 및 보강 에이전트
    
    기능:
    - 웹 크롤링을 통한 연락처 정보 자동 추출
    - 기존 연락처 정보 검증 및 업데이트
    - 다양한 소스에서 연락처 정보 수집
    - AI 기반 정보 정확도 향상
    """
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.phone_patterns = self._compile_phone_patterns()
        self.email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        self.url_pattern = re.compile(r'https?://(?:[-\w.])+(?:\:[0-9]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:\#(?:[\w.])*)?)?')
        
        # Langchain 프롬프트 템플릿
        self.extraction_prompt = PromptTemplate(
            input_variables=["organization_name", "category", "webpage_content"],
            template="""
            다음 웹페이지 내용에서 '{organization_name}' 기관의 연락처 정보를 추출해주세요:

            기관명: {organization_name}
            카테고리: {category}

            웹페이지 내용:
            {webpage_content}

            다음 형식의 JSON으로 응답해주세요:
            {{
                "phone": "전화번호 (02-123-4567 형식)",
                "mobile": "휴대폰번호 (010-1234-5678 형식)",
                "fax": "팩스번호",
                "email": "이메일주소",
                "address": "주소",
                "business_hours": "운영시간",
                "confidence": 0.95
            }}

            주의사항:
            1. 정확하지 않은 정보는 null로 설정
            2. 전화번호는 하이픈(-) 포함 형식으로 정리
            3. 신뢰도는 0.0~1.0 사이 값
            4. 기관명과 일치하지 않는 정보는 제외
            """
        )
        
        # 정보 검증 프롬프트
        self.verification_prompt = PromptTemplate(
            input_variables=["organization_name", "contact_info", "source_content"],
            template="""
            다음 연락처 정보가 '{organization_name}' 기관의 것인지 검증해주세요:

            기관명: {organization_name}
            연락처 정보: {contact_info}

            출처 내용:
            {source_content}

            검증 결과를 JSON 형식으로 응답:
            {{
                "is_valid": true/false,
                "confidence": 0.95,
                "issues": ["문제점1", "문제점2"],
                "recommendations": ["권장사항1", "권장사항2"]
            }}
            """
        )
    
    def _compile_phone_patterns(self) -> List[re.Pattern]:
        """전화번호 패턴 컴파일"""
        patterns = [
            # 일반 전화번호: 02-123-4567, 031-123-4567
            re.compile(r'\b0\d{1,2}-\d{3,4}-\d{4}\b'),
            # 휴대폰: 010-1234-5678
            re.compile(r'\b010-\d{4}-\d{4}\b'),
            # 공백 포함: 02 123 4567
            re.compile(r'\b0\d{1,2}\s\d{3,4}\s\d{4}\b'),
            # 점 구분: 02.123.4567
            re.compile(r'\b0\d{1,2}\.\d{3,4}\.\d{4}\b'),
            # 괄호 포함: (02)123-4567
            re.compile(r'\(\d{2,3}\)\d{3,4}-\d{4}'),
        ]
        return patterns
    
    async def process(self, data: Dict[str, Any]) -> AgentResult:
        """
        연락처 추출 메인 프로세스
        
        Args:
            data: {
                "targets": List[ContactTarget] 또는 Dict,
                "extraction_methods": List[str] (web_crawling, ai_analysis, etc.),
                "verification_required": bool,
                "max_sources_per_target": int
            }
        
        Returns:
            AgentResult: 추출된 연락처 정보들
        """
        try:
            # 입력 데이터 파싱
            targets = self._parse_targets(data.get("targets", []))
            extraction_methods = data.get("extraction_methods", ["web_crawling", "ai_analysis"])
            verification_required = data.get("verification_required", True)
            max_sources = data.get("max_sources_per_target", 5)
            
            results = []
            
            # 병렬 처리를 위한 세마포어 설정
            semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)
            
            # 각 대상에 대해 연락처 추출
            tasks = []
            for target in targets:
                task = self._extract_contact_with_semaphore(
                    semaphore, target, extraction_methods, verification_required, max_sources
                )
                tasks.append(task)
            
            # 병렬 실행
            extraction_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 결과 처리
            successful_extractions = 0
            for i, result in enumerate(extraction_results):
                if isinstance(result, Exception):
                    logger.error(f"추출 실패 - {targets[i].name}: {str(result)}")
                    results.append(ExtractionResult(
                        target=targets[i],
                        extracted_info=ContactInfo(),
                        success=False,
                        extraction_time=0.0,
                        error_message=str(result)
                    ))
                    self.metrics.error_count += 1
                else:
                    results.append(result)
                    if result.success:
                        successful_extractions += 1
                        self.metrics.success_count += 1
                
                self.metrics.processed_items += 1
            
            # 결과 데이터 구성
            result_data = {
                "extractions": [asdict(result) for result in results],
                "total_targets": len(targets),
                "successful_extractions": successful_extractions,
                "success_rate": successful_extractions / len(targets) if targets else 0,
                "extraction_summary": self._generate_extraction_summary(results)
            }
            
            return AgentResult(
                success=True,
                data=result_data,
                message=f"{successful_extractions}/{len(targets)}개 기관 연락처 추출 완료",
                execution_time=self.metrics.get_execution_time(),
                metadata={
                    "agent_type": "ContactAgent",
                    "extraction_count": len(results),
                    "processing_time": datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"연락처 추출 프로세스 실패: {str(e)}")
            self.metrics.error_count += 1
            
            return AgentResult(
                success=False,
                data={},
                message=f"연락처 추출 실패: {str(e)}",
                execution_time=self.metrics.get_execution_time(),
                metadata={"error": str(e)}
            )
    
    async def _extract_contact_with_semaphore(
        self,
        semaphore: asyncio.Semaphore,
        target: ContactTarget,
        methods: List[str],
        verification_required: bool,
        max_sources: int
    ) -> ExtractionResult:
        """세마포어를 사용한 연락처 추출"""
        async with semaphore:
            return await self._extract_contact_info(target, methods, verification_required, max_sources)
    
    async def _extract_contact_info(
        self,
        target: ContactTarget,
        methods: List[str],
        verification_required: bool,
        max_sources: int
    ) -> ExtractionResult:
        """개별 기관 연락처 정보 추출"""
        start_time = datetime.now()
        sources_checked = []
        
        try:
            extracted_info = ContactInfo()
            
            # 웹 크롤링 추출
            if "web_crawling" in methods:
                web_info, web_sources = await self._extract_from_web(target, max_sources)
                sources_checked.extend(web_sources)
                extracted_info = self._merge_contact_info(extracted_info, web_info)
            
            # AI 기반 추출
            if "ai_analysis" in methods and sources_checked:
                ai_info = await self._extract_with_ai(target, sources_checked[:3])
                extracted_info = self._merge_contact_info(extracted_info, ai_info)
            
            # 기존 정보와 병합
            if target.existing_info:
                extracted_info = self._merge_contact_info(target.existing_info, extracted_info)
            
            # 검증 수행
            if verification_required and extracted_info:
                verification_result = await self._verify_contact_info(target, extracted_info, sources_checked)
                extracted_info.confidence_score = verification_result.get("confidence", 0.5)
            
            # 최종 정리
            extracted_info = self._clean_contact_info(extracted_info)
            extracted_info.last_verified = datetime.now()
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return ExtractionResult(
                target=target,
                extracted_info=extracted_info,
                success=bool(extracted_info.phone or extracted_info.email or extracted_info.homepage),
                extraction_time=execution_time,
                sources_checked=sources_checked
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"연락처 추출 실패 - {target.name}: {str(e)}")
            
            return ExtractionResult(
                target=target,
                extracted_info=ContactInfo(),
                success=False,
                extraction_time=execution_time,
                error_message=str(e),
                sources_checked=sources_checked
            )
    
    async def _extract_from_web(self, target: ContactTarget, max_sources: int) -> Tuple[ContactInfo, List[str]]:
        """웹 크롤링을 통한 연락처 추출"""
        contact_info = ContactInfo()
        sources_checked = []
        
        # 검색 URL 생성
        search_urls = self._generate_search_urls(target)
        
        # 대상 URL이 있으면 우선 처리
        urls_to_check = []
        if target.target_urls:
            urls_to_check.extend(target.target_urls[:max_sources])
        
        # 검색 URL 추가
        remaining_slots = max_sources - len(urls_to_check)
        if remaining_slots > 0:
            urls_to_check.extend(search_urls[:remaining_slots])
        
        # 각 URL에서 정보 추출
        for url in urls_to_check:
            try:
                content = await self._fetch_webpage_content(url)
                if content:
                    sources_checked.append(url)
                    url_contact_info = self._extract_contact_from_content(content, url)
                    contact_info = self._merge_contact_info(contact_info, url_contact_info)
                    
                # 충분한 정보를 얻었으면 중단
                if self._is_sufficient_info(contact_info):
                    break
                    
            except Exception as e:
                logger.warning(f"URL 처리 실패 - {url}: {str(e)}")
                continue
        
        return contact_info, sources_checked
    
    async def _extract_with_ai(self, target: ContactTarget, source_urls: List[str]) -> ContactInfo:
        """AI를 이용한 고급 연락처 추출"""
        try:
            # 소스 내용 수집
            contents = []
            for url in source_urls:
                try:
                    content = await self._fetch_webpage_content(url)
                    if content and len(content) > 100:  # 최소 내용 확인
                        contents.append(content[:2000])  # 길이 제한
                except:
                    continue
            
            if not contents:
                return ContactInfo()
            
            # AI 체인으로 정보 추출
            chain = LLMChain(
                llm=self.gemini_client.get_llm(),
                prompt=self.extraction_prompt
            )
            
            # 모든 내용 합치기
            combined_content = "\n\n".join(contents)
            
            response = await chain.arun(
                organization_name=target.name,
                category=target.category,
                webpage_content=combined_content
            )
            
            # JSON 파싱
            ai_data = json.loads(response.strip())
            
            return ContactInfo(
                phone=ai_data.get("phone"),
                mobile=ai_data.get("mobile"),
                fax=ai_data.get("fax"),
                email=ai_data.get("email"),
                address=ai_data.get("address"),
                business_hours=ai_data.get("business_hours"),
                confidence_score=ai_data.get("confidence", 0.7),
                extraction_method="ai_analysis"
            )
            
        except Exception as e:
            logger.warning(f"AI 추출 실패 - {target.name}: {str(e)}")
            return ContactInfo()
    
    async def _verify_contact_info(self, target: ContactTarget, contact_info: ContactInfo, sources: List[str]) -> Dict:
        """연락처 정보 검증"""
        try:
            # 검증할 소스 내용 수집
            source_content = ""
            for url in sources[:2]:  # 최대 2개 소스만 사용
                try:
                    content = await self._fetch_webpage_content(url)
                    if content:
                        source_content += content[:1000] + "\n\n"
                except:
                    continue
            
            if not source_content:
                return {"is_valid": True, "confidence": 0.5}
            
            # AI 체인으로 검증
            chain = LLMChain(
                llm=self.gemini_client.get_llm(),
                prompt=self.verification_prompt
            )
            
            contact_str = f"전화: {contact_info.phone}, 이메일: {contact_info.email}, 주소: {contact_info.address}"
            
            response = await chain.arun(
                organization_name=target.name,
                contact_info=contact_str,
                source_content=source_content
            )
            
            return json.loads(response.strip())
            
        except Exception as e:
            logger.warning(f"검증 실패 - {target.name}: {str(e)}")
            return {"is_valid": True, "confidence": 0.5}
    
    def _generate_search_urls(self, target: ContactTarget) -> List[str]:
        """검색 URL 생성"""
        urls = []
        
        # 구글 검색 URL
        search_terms = [target.name]
        if target.search_keywords:
            search_terms.extend(target.search_keywords)
        
        query = " ".join(search_terms[:3])  # 최대 3개 키워드
        google_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        urls.append(google_url)
        
        # 네이버 검색 URL
        naver_url = f"https://search.naver.com/search.naver?query={query.replace(' ', '+')}"
        urls.append(naver_url)
        
        return urls
    
    async def _fetch_webpage_content(self, url: str) -> Optional[str]:
        """웹페이지 내용 가져오기"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # 비동기 HTTP 요청 시뮬레이션 (실제로는 aiohttp 사용 권장)
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            return response.text
            
        except Exception as e:
            logger.warning(f"웹페이지 가져오기 실패 - {url}: {str(e)}")
            return None
    
    def _extract_contact_from_content(self, content: str, source_url: str) -> ContactInfo:
        """HTML 내용에서 연락처 정보 추출"""
        contact_info = ContactInfo(source_url=source_url, extraction_method="regex_parsing")
        
        # 전화번호 추출
        for pattern in self.phone_patterns:
            matches = pattern.findall(content)
            if matches:
                phone = matches[0].replace(" ", "-").replace(".", "-")
                if phone.startswith("010"):
                    contact_info.mobile = phone
                else:
                    contact_info.phone = phone
                break
        
        # 이메일 추출
        email_matches = self.email_pattern.findall(content)
        if email_matches:
            # 가장 적절한 이메일 선택 (info@, contact@ 등 우선)
            preferred_emails = [email for email in email_matches if any(prefix in email for prefix in ['info@', 'contact@', 'admin@'])]
            contact_info.email = preferred_emails[0] if preferred_emails else email_matches[0]
        
        # URL 추출
        url_matches = self.url_pattern.findall(content)
        if url_matches:
            # 홈페이지로 보이는 URL 선택
            for url in url_matches:
                if not any(domain in url for domain in ['google.com', 'naver.com', 'facebook.com', 'youtube.com']):
                    contact_info.homepage = url
                    break
        
        # 기본 신뢰도 설정
        score = 0.0
        if contact_info.phone or contact_info.mobile:
            score += 0.4
        if contact_info.email:
            score += 0.3
        if contact_info.homepage:
            score += 0.2
        
        contact_info.confidence_score = min(score, 0.9)
        
        return contact_info
    
    def _merge_contact_info(self, base_info: ContactInfo, new_info: ContactInfo) -> ContactInfo:
        """연락처 정보 병합"""
        merged = ContactInfo()
        
        # 각 필드별로 더 신뢰도 높은 정보 선택
        fields = ['phone', 'mobile', 'fax', 'email', 'homepage', 'address', 'postal_code', 'business_hours']
        
        for field in fields:
            base_value = getattr(base_info, field, None)
            new_value = getattr(new_info, field, None)
            
            if not base_value:
                setattr(merged, field, new_value)
            elif not new_value:
                setattr(merged, field, base_value)
            else:
                # 둘 다 있으면 신뢰도로 선택
                if new_info.confidence_score > base_info.confidence_score:
                    setattr(merged, field, new_value)
                else:
                    setattr(merged, field, base_value)
        
        # 메타데이터 병합
        merged.confidence_score = max(base_info.confidence_score, new_info.confidence_score)
        merged.extraction_method = f"{base_info.extraction_method or ''},{new_info.extraction_method or ''}".strip(',')
        merged.last_verified = max(
            base_info.last_verified or datetime.min,
            new_info.last_verified or datetime.min
        ) if any([base_info.last_verified, new_info.last_verified]) else None
        
        return merged
    
    def _clean_contact_info(self, contact_info: ContactInfo) -> ContactInfo:
        """연락처 정보 정리 및 검증"""
        # 전화번호 정리
        if contact_info.phone:
            contact_info.phone = self._normalize_phone_number(contact_info.phone)
        
        if contact_info.mobile:
            contact_info.mobile = self._normalize_phone_number(contact_info.mobile)
        
        if contact_info.fax:
            contact_info.fax = self._normalize_phone_number(contact_info.fax)
        
        # 이메일 검증
        if contact_info.email and not self.email_pattern.match(contact_info.email):
            contact_info.email = None
        
        # URL 정리
        if contact_info.homepage and not contact_info.homepage.startswith('http'):
            contact_info.homepage = 'http://' + contact_info.homepage
        
        return contact_info
    
    def _normalize_phone_number(self, phone: str) -> str:
        """전화번호 정규화"""
        if not phone:
            return phone
        
        # 숫자만 추출
        digits = re.sub(r'[^\d]', '', phone)
        
        # 형식별 정리
        if len(digits) == 11 and digits.startswith('010'):
            return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
        elif len(digits) == 10 and digits.startswith('02'):
            return f"{digits[:2]}-{digits[2:6]}-{digits[6:]}"
        elif len(digits) == 11 and not digits.startswith('010'):
            return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
        
        return phone  # 정리할 수 없으면 원본 반환
    
    def _is_sufficient_info(self, contact_info: ContactInfo) -> bool:
        """충분한 정보인지 확인"""
        score = 0
        if contact_info.phone or contact_info.mobile:
            score += 2
        if contact_info.email:
            score += 2
        if contact_info.homepage:
            score += 1
        if contact_info.address:
            score += 1
        
        return score >= 4  # 충분한 정보 기준
    
    def _parse_targets(self, targets_data: Union[List, Dict]) -> List[ContactTarget]:
        """추출 대상 데이터 파싱"""
        targets = []
        
        if isinstance(targets_data, dict):
            targets_data = [targets_data]
        
        for target_data in targets_data:
            if isinstance(target_data, dict):
                # 기존 연락처 정보 파싱
                existing_info_data = target_data.get("existing_info", {})
                existing_info = ContactInfo(
                    phone=existing_info_data.get("phone"),
                    mobile=existing_info_data.get("mobile"),
                    fax=existing_info_data.get("fax"),
                    email=existing_info_data.get("email"),
                    homepage=existing_info_data.get("homepage"),
                    address=existing_info_data.get("address"),
                    postal_code=existing_info_data.get("postal_code"),
                    business_hours=existing_info_data.get("business_hours")
                )
                
                target = ContactTarget(
                    name=target_data.get("name", ""),
                    category=target_data.get("category", ""),
                    existing_info=existing_info,
                    search_keywords=target_data.get("search_keywords", []),
                    target_urls=target_data.get("target_urls", []),
                    priority=target_data.get("priority", 1)
                )
                targets.append(target)
        
        return targets
    
    def _generate_extraction_summary(self, results: List[ExtractionResult]) -> Dict[str, Any]:
        """추출 결과 요약 생성"""
        if not results:
            return {}
        
        total = len(results)
        successful = sum(1 for r in results if r.success)
        
        # 추출된 정보 통계
        phone_extracted = sum(1 for r in results if r.extracted_info.phone)
        email_extracted = sum(1 for r in results if r.extracted_info.email)
        homepage_extracted = sum(1 for r in results if r.extracted_info.homepage)
        
        # 평균 신뢰도
        avg_confidence = sum(r.extracted_info.confidence_score for r in results if r.success) / successful if successful else 0
        
        # 평균 처리 시간
        avg_time = sum(r.extraction_time for r in results) / total
        
        return {
            "total_processed": total,
            "successful_extractions": successful,
            "success_rate": successful / total,
            "extracted_stats": {
                "phone_numbers": phone_extracted,
                "email_addresses": email_extracted,
                "homepages": homepage_extracted
            },
            "average_confidence": avg_confidence,
            "average_processing_time": avg_time,
            "most_common_sources": self._get_common_sources(results)
        }
    
    def _get_common_sources(self, results: List[ExtractionResult]) -> List[str]:
        """가장 많이 사용된 소스 URL들"""
        source_counts = {}
        
        for result in results:
            if result.sources_checked:
                for source in result.sources_checked:
                    domain = urlparse(source).netloc
                    source_counts[domain] = source_counts.get(domain, 0) + 1
        
        # 상위 5개 도메인 반환
        sorted_sources = sorted(source_counts.items(), key=lambda x: x[1], reverse=True)
        return [domain for domain, count in sorted_sources[:5]] 