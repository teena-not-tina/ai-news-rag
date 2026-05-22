# ADR 001: 기술스택 선택

- **결정일**: 2026-05-22
- **상태**: 컨펌됨
- **관련 Task**: Task 01

---

## 🦜 LangChain

- **배경**: RAG 6단계(파서→청크→임베딩→DB→검색→LLM)를 일관된 인터페이스로 묶어주는 프레임워크.
- **임팩트**: OpenAI ↔ Gemini 갈아끼우기 한 줄. 이 프로젝트 평가 Task의 핵심 인프라.
- **대안 비교**:
  | 옵션 | 장단점 |
  |---|---|
  | **LangChain ✅** | 생태계 1위, 자료 많음 / API 자주 바뀜 |
  | LlamaIndex | RAG 특화, 깔끔 / 생태계 작음 |
  | 직접 짜기 | 100% 통제 / 3일 안에 불가 |
- **동작 원리**: 모든 데이터가 `Document{page_content, metadata}` 객체로 흐름.
- **사이드 이펙트** ⚠️: 버전 호환성 잘 깨짐 → `requirements.txt` 정확히 핀.

---

## 🔍 FAISS

- **배경**: Meta가 만든 벡터 검색 라이브러리, 로컬 파일 기반.
- **임팩트**: 약 260개 벡터 검색 1ms 미만. 0원, API 키 불필요.
- **대안 비교**:
  | 옵션 | 장단점 |
  |---|---|
  | **FAISS ✅** | 무료·빠름·로컬 / 메타데이터 필터 약함 |
  | Chroma | 메타데이터 강함 / 파일 큼 |
  | Qdrant/Pinecone | 프로덕션급 / 서버·비용 부담 |
- **동작 원리**: MVP는 `IndexFlatL2` (brute force). LangChain이 메타데이터를 `docstore`에 별도 매핑.
- **사이드 이펙트** ⚠️: M1/M2는 `faiss-cpu`만 (`faiss-gpu`는 CUDA 필요).

---

## 🖥️ CLI > Streamlit (v2로 defer)

- **배경 + 결정**: Streamlit은 웹 UI용. MVP 목표가 "RAG 동작 + 모델 비교"라 UI는 부차적.
- **임팩트**: CLI는 1시간이면 끝. 평가 자동화도 더 쉬움.
- **사이드 이펙트** ⚠️: 포트폴리오 스크린샷 빈약 → README에 터미널 녹화로 보완.
- **v2 확장**: `search.py`를 그대로 `import`만 하면 됨 → 잃는 거 없음.

---

## 🔧 잔 도구 (한 줄)

| 도구 | 왜 |
|---|---|
| Python 3.11 | LangChain 호환성 최선 |
| `python-frontmatter` | 옵시디언 YAML 헤더 파싱 표준 |
| `python-dotenv` | API 키 하드코딩 방지 |
| `pytest` | 파이썬 테스트 표준 |
| `tiktoken` | OpenAI 토큰 카운팅 (비용 추정) |

---

## 📦 최종 `requirements.txt`

```
langchain==0.3.7
langchain-community==0.3.5
langchain-openai==0.2.5
langchain-google-genai==2.0.4
faiss-cpu==1.9.0
openai>=1.50.0
google-generativeai>=0.8.0
python-frontmatter==1.1.0
python-dotenv==1.0.1
pytest==8.3.3
tiktoken>=0.8.0
```
