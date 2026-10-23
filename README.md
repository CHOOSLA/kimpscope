# KimpScope — 김치 프리미엄 RAG

국내(업비트)와 해외 코인 가격 차이, 김치 프리미엄(김프)을 계산하고, **그 차이가 왜 생겼는지**를 거래소 공지·입출금 상태 근거로 설명하는 RAG 서비스입니다.

- 배포: https://kimpscope.onrender.com (Render 무료 플랜. 15분 이상 요청이 없으면 잠들어 첫 접속에 30초~1분 걸립니다)
- 과제: SSAFY AI 코어 프로젝트 2회차 — RAG 지식 서비스
- 셀프 체크리스트 결과: [docs/checklist/RESULTS.md](docs/checklist/RESULTS.md)

## 1. 왜 이 도메인인가

김프 수치 자체는 계산입니다. 국내 원화가 ÷ (해외 USDT가 × 원/달러 환율) − 1. RAG가 필요한 곳은 그 다음 질문입니다. "이 코인만 김프가 10%인 이유는?"에 답하려면 입출금 중지 공지, 거래소 경보, 네트워크 점검 같은 **문서 근거**가 필요하고, 모델 지식으로 답하면 틀립니다.

같은 이유로 가격·김프·입출금 상태 같은 **현재 값은 색인하지 않습니다.** 벡터 저장소에 넣는 순간 지난 값이 되기 때문입니다. 질문 시점에 조회해 기준 시각을 붙인 근거로 만들고, 문서 속 숫자를 현재 값으로 쓰지 못하게 막습니다.

## 2. 화면에서 할 수 있는 것

| 기능 | 내용 | 요구사항 |
| --- | --- | --- |
| 김프 시세표 | 대표 10개 코인의 국내가·해외가·김프·USDT 기준 차이·테더 프리미엄. 5초 조회. 지연·실패 시 원인 표시 | F2010 |
| 코인 선택·리서치 채팅 | 298개 업비트 KRW 코인 중 하나를 골라 질문. 코인별 대화 기록 분리 | F2009 |
| 근거 표시 | 답변의 [번호]와 화면 근거 목록이 일치. 메타데이터·공지·실시간 스냅샷을 출처 종류로 구분 | F2008, F2016 |
| 검색 설정 | 유사도 / MMR, 근거 수(Top-k) 3·5·8 | F2006, F2014 |
| 조건 탐색 | "유의종목이 아닌 비트코인"처럼 자연어 조건으로 코인 찾기 | F2011 |
| 안내 | 처리 중 표시, 색인 없음·키 없음 안내, 투자 조언 아님 안내, 예측·매매 판단 질문 보류 | F2012 |

## 3. 구조

```
                 ┌──────────────── 데이터 준비 ────────────────┐
업비트 마켓 목록 ─▶ 항목 텍스트 298건 ─▶ 임베딩 ─▶ Chroma "items"
빗썸 공지(+본문) ─▶ Postgres(Neon) 보관·개정 이력 ─┐
                                                    │ 질문 시 후보
질문 ─▶ [프롬프트 1] 검색어 추출 ─▶ 후보 ─▶ [프롬프트 2] 선별 ─▶ 청킹·임베딩 ─▶ Chroma "documents"
                                     (질문 캐시: 같은 질문은 다시 수집하지 않음)

LangGraph:  retrieve ──────────────────────────────▶ generate
            ├ 선택 코인 메타데이터 (항상 1번)              [프롬프트 3] 근거만 사용, 문장마다 [번호]
            ├ 실시간 시세·김프 스냅샷 (색인 안 함)          ├ 인용 번호가 실제 근거에 있는지 검사
            ├ 거래소 입출금·경보 스냅샷 (색인 안 함)        ├ 현재 값 질문인데 실시간 근거를 인용 안 하면 폐기
            └ 외부 문서 검색 (유사도 또는 MMR, Top-k)     └ 예측·매매 판단 질문은 보류
```

| 모듈 | 책임 |
| --- | --- |
| `backend/catalog.py` | 항목 메타데이터 로드, 항목 텍스트 구성 (도메인 종속 부분) |
| `backend/collection.py` | 후보 문서 모음, 프롬프트 1·2, 질문 캐시 |
| `backend/store.py` | Chroma 두 컬렉션, 청킹·색인·재색인, 유사도/MMR 검색 |
| `backend/pipeline.py`, `prompts.py` | LangGraph 두 노드, 프롬프트 3, 인용 검사 |
| `backend/live.py` | 실시간 근거 생성, 현재 값 질문 분류 |
| `backend/market.py`, `fx.py` | 시세·김프·환율 |
| `backend/bithumb_notices.py`, `exchange_status.py`, `notice_db.py` | 공지·상태 수집과 저장 |
| `backend/main.py` | API |
| `dist/` | 화면 (HTML·CSS·JS, F2013) |
| `scripts/cron_collect.py` | 15분 예약 수집 진입점 (GitHub Actions) |

### 주요 설계 결정

- **두 컬렉션.** `items`(코인 메타데이터)와 `documents`(외부 문서). 청크 ID는 `항목ID:문서ID:청크순번`이라 같은 공지가 여러 코인에 연결돼도 덮어쓰지 않습니다.
- **재색인 중복 방지.** 메타데이터는 고정 ID로 upsert. 외부 문서는 본문·청크 설정의 지문(SHA-256)이 같으면 건너뛰고, 바뀌면 이전 청크를 지운 뒤 다시 넣습니다. 청크 크기를 바꾸면 지문이 달라져 자동으로 다시 청킹됩니다.
- **항목 자체 문서 우선.** 프롬프트 2가 무엇을 고르든 선택 코인의 메타데이터 문서는 항상 색인·검색 결과 1번에 들어갑니다.
- **청크 설정.** `CHUNK_SIZE=800`, `CHUNK_OVERLAP=120`, `TOP_K=5` (환경변수로 변경). 빗썸 공지 본문은 대부분 수백~2천 자라 800자면 공지 1건이 1~3개 청크로 나뉘고, 중복 120자로 문단 경계의 "재개 일시" 같은 문장이 잘리지 않게 했습니다.
- **김프는 공식 환율 기준.** 업비트 USDT/KRW를 환율로 쓰면 테더 가격에 붙은 국내 프리미엄이 김프를 상쇄합니다(실측 BTC −0.01%). 수출입은행 매매기준율(키 필요) → Frankfurter 공개 기준환율 순으로 받고, 둘 다 실패하면 김프를 비워 둡니다. 고정 환율로 대체하지 않습니다.
- **현재 값 질문은 두 번 막습니다.** 생성 전: 최신 실시간 근거가 없으면 모델을 부르지 않음. 생성 후: 답변이 그 근거를 인용하지 않으면 폐기(`live_citation_missing`). 문서 속 API 예시 가격을 현재가로 답한 실제 오류(2026-10-22)에서 나온 규칙입니다.

자세한 기록: [김프 계산과 실시간 근거](docs/LIVE_EVIDENCE.md) · [공지 수집 파이프라인](docs/NOTICE_PIPELINE.md) · [저장소 선택](docs/FREE_STORAGE_PLAN.md)

## 4. 실행

### Windows (PowerShell 7, Python 3.12)

```powershell
copy .env.example .env      # 이미 .env가 있으면 덮어쓰지 마세요
# .env에 OPENAI_API_KEY 입력 (SSAFY GMS 키)
pwsh -File scripts/run.ps1 -Setup   # 처음 한 번: 가상환경 생성 + 의존성 설치
pwsh -File scripts/run.ps1          # 실행 → http://127.0.0.1:4173
```

macOS/Linux: `python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt && sh scripts/run.sh`

처음 실행하면 시세표 위 상태 줄의 **데이터 색인**을 한 번 누른 뒤 질문합니다(메타데이터 298건 임베딩). 배포 환경은 시작 명령이 색인이 비어 있을 때 자동으로 만듭니다(`render.yaml`).

### 환경변수 (`.env`, Git에 올리지 않음)

| 이름 | 필수 | 설명 |
| --- | --- | --- |
| `OPENAI_API_KEY` | 예 | 생성·임베딩. 없으면 시세·조건 탐색·원문 조회만 동작하고 질문에는 키 없음 안내 |
| `OPENAI_BASE_URL` | 예 | SSAFY GMS 주소 (`.env.example`에 있음) |
| `CHAT_MODEL`, `EMBED_MODEL` | 아니오 | 기본 `gpt-4.1-mini`, `text-embedding-3-small` |
| `CHUNK_SIZE`, `CHUNK_OVERLAP`, `TOP_K` | 아니오 | 기본 800, 120, 5 |
| `DATABASE_URL` | 아니오 | 공지·상태 저장용 PostgreSQL. 없으면 로컬 SQLite |
| `KOREAEXIM_API_KEY` | 아니오 | 수출입은행 환율. 없으면 Frankfurter |

## 5. 검증

```powershell
.\.venv\Scripts\python.exe -m pytest -q          # 외부 호출 없음
.\.venv\Scripts\python.exe -m scripts.checklist_local   # F2001·F2002·F2005·F2007 (임베딩 스텁)
node scripts/checklist_api.mjs https://kimpscope.onrender.com   # 운영 API로 나머지 항목 (모델 호출 발생)
```

체크리스트 27개 항목의 결과와 증빙: [docs/checklist/RESULTS.md](docs/checklist/RESULTS.md)

## 6. 데이터 출처와 이용 조건

[docs/SOURCES.md](docs/SOURCES.md)에 출처별 주소·키 필요 여부·호출 정책·이용 조건을 정리했습니다. 확인하지 못한 조건은 미확인으로 적었습니다. 이 저장소는 교육용 시연 범위로 운영합니다.

## 7. 한계

- 입출금 상태와 공지는 **빗썸 기준**입니다. 업비트 입출금 현황·공지는 API 키가 필요해 수집하지 못했고, 답변에 "빗썸 기준"을 밝힙니다.
- 원/달러는 고시 환율이라 고시 이후 환율 변동분이 김프에 섞입니다. 화면과 근거에 고시일을 표시합니다.
- 현재 값 질문 분류는 정규식입니다. 우회 표현을 모두 잡지는 못하고, 생성 후 인용 판정이 두 번째 방어선입니다.
- 빗썸 공지 API는 최근 20건만 줍니다. 예약 수집이 시작된 이후의 공지만 쌓입니다.
- Render 무료 플랜은 디스크가 재배포마다 비워집니다. Chroma 색인은 시작할 때 다시 만들고, 공지·상태는 외부 PostgreSQL에 둡니다.
