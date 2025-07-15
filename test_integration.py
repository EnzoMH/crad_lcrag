#!/usr/bin/env python3
"""
FastAPI-AI 에이전트 시스템 통합 테스트

이 스크립트는 다음을 확인합니다:
1. 필수 의존성 패키지 설치 상태
2. AI 에이전트 시스템 모듈 import 가능 여부  
3. FastAPI 애플리케이션 기본 기능 테스트
"""

import sys
import os
import traceback
from datetime import datetime

def test_dependencies():
    """필수 의존성 패키지 테스트"""
    print("=" * 50)
    print("1. 의존성 패키지 테스트")
    print("=" * 50)
    
    dependencies = [
        'fastapi',
        'uvicorn', 
        'pydantic',
        'langchain',
        'langchain_google_genai',
        'asyncio',
        'logging'
    ]
    
    success_count = 0
    
    for dep in dependencies:
        try:
            __import__(dep)
            print(f"✅ {dep} - 설치됨")
            success_count += 1
        except ImportError as e:
            print(f"❌ {dep} - 설치 필요: {e}")
    
    print(f"\n의존성 상태: {success_count}/{len(dependencies)} 설치됨")
    return success_count == len(dependencies)


def test_ai_agent_modules():
    """AI 에이전트 시스템 모듈 import 테스트"""
    print("\n" + "=" * 50)
    print("2. AI 에이전트 모듈 import 테스트")
    print("=" * 50)
    
    modules = [
        'aiagent.core',
        'aiagent.utils', 
        'aiagent.agents'
    ]
    
    success_count = 0
    
    for module in modules:
        try:
            __import__(module)
            print(f"✅ {module} - import 성공")
            success_count += 1
        except ImportError as e:
            print(f"❌ {module} - import 실패: {e}")
        except Exception as e:
            print(f"⚠️ {module} - 기타 오류: {e}")
    
    print(f"\n모듈 상태: {success_count}/{len(modules)} import 성공")
    return success_count == len(modules)


def test_fastapi_app():
    """FastAPI 애플리케이션 기본 테스트"""
    print("\n" + "=" * 50)  
    print("3. FastAPI 애플리케이션 테스트")
    print("=" * 50)
    
    try:
        # FastAPI 앱 생성 테스트
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        
        # 간단한 테스트 앱 생성
        test_app = FastAPI(title="Test App")
        
        @test_app.get("/test")
        async def test_endpoint():
            return {"message": "테스트 성공", "timestamp": datetime.now().isoformat()}
        
        # 테스트 클라이언트로 테스트
        client = TestClient(test_app)
        response = client.get("/test")
        
        if response.status_code == 200:
            print("✅ FastAPI 애플리케이션 기본 기능 - 정상")
            print(f"   응답: {response.json()}")
            return True
        else:
            print(f"❌ FastAPI 애플리케이션 - 응답 오류: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ FastAPI 애플리케이션 테스트 실패: {e}")
        print(traceback.format_exc())
        return False


def test_project_structure():
    """프로젝트 구조 확인"""
    print("\n" + "=" * 50)
    print("4. 프로젝트 구조 확인")
    print("=" * 50)
    
    required_files = [
        'app.py',
        'requirements.txt',
        'aiagent/__init__.py',
        'api/__init__.py',
        'service/__init__.py',
        'template/html/index.html'
    ]
    
    success_count = 0
    
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"✅ {file_path} - 존재함")
            success_count += 1
        else:
            print(f"❌ {file_path} - 누락됨")
    
    print(f"\n파일 상태: {success_count}/{len(required_files)} 존재함")
    return success_count == len(required_files)


def main():
    """통합 테스트 실행"""
    print("🚀 FastAPI-AI 에이전트 시스템 통합 테스트 시작")
    print(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python 버전: {sys.version}")
    print(f"작업 디렉토리: {os.getcwd()}")
    
    # 테스트 실행
    tests = [
        ("의존성 패키지", test_dependencies),
        ("AI 에이전트 모듈", test_ai_agent_modules), 
        ("FastAPI 애플리케이션", test_fastapi_app),
        ("프로젝트 구조", test_project_structure)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ {test_name} 테스트 중 예외 발생: {e}")
            results.append((test_name, False))
    
    # 결과 요약
    print("\n" + "=" * 50)
    print("📊 테스트 결과 요약")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 통과" if result else "❌ 실패"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n전체 결과: {passed}/{total} 테스트 통과")
    
    if passed == total:
        print("🎉 모든 테스트가 통과했습니다! 시스템이 정상적으로 구성되었습니다.")
        return True
    else:
        print("⚠️ 일부 테스트가 실패했습니다. 누락된 의존성이나 설정을 확인해주세요.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 