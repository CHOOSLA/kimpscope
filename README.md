# KimpScope

국내외 코인 시세 비교와 공식 문서 기반 리서치를 연결하는 웹 MVP입니다. 현재 저장소는 **정적 프론트엔드 + Python FastAPI 백엔드**로 구성되어 있습니다. 이전 프론트엔드 전용 데모에서 확장된 상태입니다.

## Windows 실행 (PowerShell 7 / Python 3.12)

```powershell
pwsh -File scripts/run.ps1 -Setup
# 다음 실행부터
pwsh -File scripts/run.ps1
```

http://127.0.0.1:4173 에 접속합니다. 포트 변경은 `-Port 4174`, 종료는 Ctrl+C입니다. 가상환경 활성화나 PowerShell 실행 정책 변경은 필요하지 않습니다.

macOS/Linux에서는 Python 가상환경 생성 및 requirements.txt 설치 후 `sh scripts/run.sh`로 실행할 수 있습니다.

## 모델 설정

`.env.example`을 `.env`로 복사하고 발급받은 키를 직접 설정하세요. 기존 `.env`는 덮어쓰지 마세요. 키를 Git에 올리지 않습니다.

- `OPENAI_API_KEY`: 선택한 API 제공자의 키
- `OPENAI_BASE_URL`: 예제는 SSAFY GMS 주소입니다. 다른 제공자를 사용하면 해당 주소로 변경합니다.
- `CHAT_MODEL`: 답변 생성 모델
- `EMBED_MODEL`: 임베딩 모델 (기본 text-embedding-3-small)

**현재 구현은 생성뿐 아니라 임베딩·벡터 질의에도 API 키가 필요합니다.** 키 없이 가능한 것은 시세, 메타데이터/원문 조회 및 규칙 기반 조건 탐색입니다. 화면에서 데이터 색인을 실행한 후 질문하세요. 모델 호출에는 제공자의 사용량이 발생할 수 있습니다.

## 현재 구조와 범위

- `dist/`: 시세표, 검색·필터, 관심 코인, 코인별 대화·인용 문서 UI
- `backend/main.py`: API와 정적 화면을 같은 포트에서 제공
- `backend/market.py`: 업비트·Binance REST 시세 조회, 5초 캐시 및 요청 직렬화. 대상은 업비트 KRW ∩ 바이낸스 거래 중(TRADING) 코인이며 화면에는 대표 10개를 보낸다. WebSocket 스트리밍은 아직 아닙니다.
- `backend/fx.py`: 김프 기준 원/달러 환율 (수출입은행 키가 있으면 매매기준율, 없으면 Frankfurter 공개 기준환율)
- `backend/exchange_status.py`: 빗썸 입출금 현황·경보, 업비트 유의/주의 수집 (상태 변화만 기록)
- `backend/live.py`: 시세·김프·거래소 상태를 기준 시각이 붙은 RAG 근거로 생성, 현재 값 질문 분류
- `scripts/cron_collect.py`: Render 크론 15분 주기 수집 (`requirements-cron.txt`만 사용)
- `backend/store.py`: Chroma의 항목/문서 컬렉션, OpenAI 호환 임베딩, 코인 범위 검색 및 MMR 선택
- `backend/pipeline.py`: LangGraph retrieve → generate, 번호 인용 검사
- `backend/collection.py`: 저장된 공식 문서 팩에서 후보 선택, 질문 캐시 및 문서 버전 해시
- `data/markets.json`, `data/documents.json`: 수집 시점 스냅샷. 최신 공지 실시간 수집기가 아닙니다.

김치 프리미엄은 원/달러 기준 환율로 계산합니다. 업비트 USDT/KRW 기준 차이와 테더 프리미엄은 따로 표시합니다. 환율을 받지 못하면 김프를 표시하지 않습니다. 자세한 기준과 실시간 근거 규칙은 [LIVE_EVIDENCE.md](docs/LIVE_EVIDENCE.md)를 확인하세요. 과거 차트는 업비트 캔들 종가이며 김치 프리미엄 이력이 아닙니다. 데이터 이용 조건과 출처는 [SOURCES.md](docs/SOURCES.md)를 확인하세요.

## 검증

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node --check dist/app.js
node --check dist/integration.js
```

기본 테스트는 외부 생성 모델을 호출하지 않습니다. `python -m scripts.verify_pipeline`과 `python -m scripts.evaluate`는 별도의 모델 설정과 색인이 필요하며 외부 API를 호출합니다. 기존 `docs/pipeline-verification.json`은 저장된 과거 결과이지 현재 PC의 검증 결과가 아닙니다.

## 배포와 남은 작업

`.openai/hosting.json`은 프론트 정적 파일만 배포하는 설정입니다. 이 설정만으로 Python 백엔드가 배포되지는 않습니다. 현재 전체 기능 검증은 위 FastAPI 실행 방식으로 진행합니다.

PDF의 전체 요구사항 충족은 아직 판정하지 않았습니다. 메타데이터/문서 색인, LangGraph, 인용 UI 등은 구현되어 있지만 실제 모델과의 통합 검증, 문서 갱신·이용 조건, 검색 품질 평가가 필요합니다. 로그인·주문·실거래·공용 커뮤니티는 구현하지 않았습니다.

최근 Windows 실연동 결과와 발견·수정한 RAG 오류는 [WINDOWS_VERIFICATION.md](docs/WINDOWS_VERIFICATION.md)에 기록했습니다. `docs/evaluation.json`에는 5개 질의 비교와 실패 사례의 수정 전후 응답이 있습니다.
