# 2회차 셀프 체크리스트 결과

점검 유형 셀프 · 앱 작성자 추창우 · 점검자 추창우 (실행: Claude) · 점검 일시 2026-10-23 15:50~16:25 KST

대상: 운영 https://kimpscope.onrender.com (커밋 01b7672 배포본, 원/달러 Frankfurter, 해외 시세 OKX 대체 중) + 로컬 실행(scripts/checklist_local.py, pytest 67개)

집계 — 통과 26 · 실패 1 · 미확인 0 · 해당없음 0 / 전체 27

기입 기준은 양식 그대로입니다. 직접 실행해 기대한 결과를 확인한 것만 통과로 적었습니다.
증빙은 `evidence/` 폴더에 있습니다. 화면 캡처는 `evidence/screenshots/`, 실행 결과는 `api_run.json`(운영 API)·`local_index.json`(로컬)입니다. 엑셀 기입본은 `2회차_셀프·상호_체크리스트_셀프점검.xlsx`입니다.

| 번호 | 요구사항 | 확인 항목 | 결과 | 증빙 | 비고 |
| --- | --- | --- | --- | --- | --- |
| 1 | F2001 | 로드한 항목 수와 색인된 청크 수가 일치하고, 항목 1건의 색인 텍스트에 의도한 속성이 모두 들어 있다 | **통과** | [local_index.json](evidence/local_index.json)<br>[api_run.json](evidence/api_run.json) | 로드 298건 = items 컬렉션 298건(로컬·운영 모두). BTC 색인 텍스트에 한글명·영문명·심볼·거래 페어·기준 통화·거래소·유의종목 여부가 모두 있다. |
| 2 | F2002 | 색인 작업을 두 번 실행해도 청크 수가 늘지 않는다 | **통과** | [local_index.json](evidence/local_index.json)<br>[api_run.json](evidence/api_run.json) | 로컬: 메타데이터 298→298, 외부 문서 청크 7→7(같은 문서 두 번 색인). 운영: /api/index 재실행 후 indexed 298 유지('298건 색인 완료'). |
| 3 | F2003 · F2004 | 검색어 추출(프롬프트 1)이 뽑은 검색어 목록이 확인되고, 후보 선별(프롬프트 2)에 따라 색인된 문서와 버려진 문서가 구분된다 | **통과** | [api_run.json](evidence/api_run.json)<br>[screenshots/08_citation_list_and_keywords.jpg](evidence/screenshots/08_citation_list_and_keywords.jpg) | SOL 질문 1개: 프롬프트 1 검색어 6개(솔라나, SOL, 솔라나 입출금 중지 …), 프롬프트 2 선별 결과 색인 2건(자체 메타데이터, 빗썸 SOL 공지) / 제외 2건(업비트 API 문서 2). 화면 답변 아래에도 '검색어 … · 색인 n건 · 제외 m건' 표시. 검색어·선별 결과 출력은 이번 점검 중 추가한 기능(collection 응답). |
| 4 | F2004 · NF2002 | 같은 질문을 다시 물었을 때 수집이 다시 일어나지 않는다 | **통과** | [api_run.json](evidence/api_run.json)<br>[tests/test_collection_report.py](../../tests/test_collection_report.py) | 같은 질문 두 번: 1회차 cache_hit=false 23.3초, 2회차 cache_hit=true 13.8초, 문서 청크 수 6 유지. 2회차는 프롬프트 1·2와 수집을 건너뛰고 답변 생성만 다시 한다(테스트로 프롬프트 재호출 0회 확인). |
| 5 | F2005 | 청크 크기 또는 중복 길이를 설정에서 바꿔 색인하면 청크 수가 달라진다 | **통과** | [local_index.json](evidence/local_index.json) | 청크 크기/중복 800/120 → 7개, 400/60 → 15개, 1200/200 → 5개. 로컬 실행이며 임베딩은 결정적 스텁, 문서는 저장소 장문(docs/LIVE_EVIDENCE.md 3,566자)을 썼다. 운영 문서로는 설정 변경 재배포가 필요해 실행하지 않았다. 청크 ID는 항목ID:문서ID:순번이라 BTC·ETH 간 겹침 0. |
| 6 | F2006 | 검색할 근거 수(Top-k)를 설정에서 바꾸면 같은 질문의 근거 목록이 달라진다 | **통과** | [api_run.json](evidence/api_run.json) | 같은 SOL 질문에서 Top-k 3 → 외부 문서 청크 2개, Top-k 8 → 5개(해당 공지의 청크 전부). 3이 2개인 것은 검색 상위에 든 자체 메타데이터 청크가 이미 넣은 항목 메타데이터와 같아 중복 제거됐기 때문이다. 메타데이터는 항상 1번. |
| 7 | F2007 | LangGraph가 retrieve와 generate 두 노드로 구성되어 있다 | **통과** | [local_index.json](evidence/local_index.json)<br>[backend/pipeline.py](../../backend/pipeline.py) | 그래프 노드 __start__ → retrieve → generate → __end__. |
| 8 | F2008 | 답변 본문의 근거 번호와 화면의 근거 목록이 일치하고, 항목 메타데이터와 외부 문서가 구분되어 표시된다 | **통과** | [api_run.json](evidence/api_run.json)<br>[screenshots/08_answer_with_numbers.jpg](evidence/screenshots/08_answer_with_numbers.jpg)<br>[screenshots/08_citation_list_and_keywords.jpg](evidence/screenshots/08_citation_list_and_keywords.jpg) | 답변 본문 번호 [1][3][4][5][6] = 화면 근거 목록 [1][3][4][5][6]. 출처 종류가 '항목 메타데이터'와 '빗썸 공지 원문 (업비트 상태 아님)'으로 나뉘어 표시된다. |
| 9 | F2007 · F2008 | 문서에 없는 것을 물으면 추측하지 않고 확인되지 않는다고 답하며, 인용된 근거가 없으면 그 사실이 화면에 안내된다 | **통과** | [api_run.json](evidence/api_run.json)<br>[screenshots/09_14_no_citation_and_disclaimer.jpg](evidence/screenshots/09_14_no_citation_and_disclaimer.jpg) | '사토시 나카모토의 실제 거주지 주소'는 '제공된 근거에 없습니다'로 답했다. 다만 이 답에도 메타데이터·시세 스냅샷을 [1][2]로 붙였다(근거 없음을 말하면서 인용한 것). 인용이 없는 답(투자 판단 질문)에서는 화면에 '생성 답변의 인용 문서 없음'이 표시된다. |
| 10 | F2009 | 항목을 바꿨을 때 이전 대화가 섞이지 않는다 | **통과** | [screenshots/10_history_per_coin_sol.jpg](evidence/screenshots/10_history_per_coin_sol.jpg)<br>[screenshots/12_live_kimp_answer.jpg](evidence/screenshots/12_live_kimp_answer.jpg) | SOL에서 질문 → BTC로 바꿔 질문 → SOL로 돌아오면 SOL 대화 2건만 남아 있고 BTC 대화가 섞이지 않는다. 코인 전환은 화면의 selectCoin을 직접 호출했다(시세표가 5초마다 다시 그려져 행 클릭 참조가 계속 바뀜). |
| 11 | F2011 | 조건 기반 탐색 결과에 조건과 맞지 않는 항목이 섞이지 않는다 | **통과** | [api_run.json](evidence/api_run.json)<br>[api_rerun_after_fix.json](evidence/api_rerun_after_fix.json)<br>[screenshots/11_condition_search.jpg](evidence/screenshots/11_condition_search.jpg)<br>[screenshots/11_condition_result_to_chat.jpg](evidence/screenshots/11_condition_result_to_chat.jpg) | '유의종목인 코인' → 6건, 6건 모두 warning=true. 결과를 누르면 해당 코인 채팅으로 이동. 처음 실행에서 '유의종목이 아닌 비트코인'이 0건이었다(모델이 symbol에 '비트코인'을 넣음). 이름을 티커로 바꾸도록 고친 뒤 재실행: 조건 {symbol: BTC, warning: false} → 1건. |
| 12 | F2010 | 도메인 특화 기능의 결과에도 근거가 함께 제시된다 | **통과** | [api_run.json](evidence/api_run.json)<br>[api_rerun_after_fix.json](evidence/api_rerun_after_fix.json)<br>[screenshots/12_live_kimp_answer.jpg](evidence/screenshots/12_live_kimp_answer.jpg) | 특화 기능(김프 실시간 근거): '지금 비트코인 김프 몇 %야?' → 기준 시각과 +0.86~0.87%를 '실시간 시세 스냅샷' 근거로 인용. 처음 실행에서 '솔라나 김프가 다르게 움직인 이유'에 전제(SOL만 다르다)를 받아들이고 입출금 중지를 원인으로 단정했다. 프롬프트에 전제 확인 규칙을 넣은 뒤 재실행에서는 전제가 근거와 맞지 않는다고 답했다. 입출금 상태 근거는 15분 수집이 아직 돌지 않아 비어 있다(상태 질문은 근거 없음으로 거절). |
| 13 | F2012 | 처리 중 진행 상태가 표시되고, 색인이 없을 때와 API 키가 없을 때 각각 안내가 표시된다 | **통과** | [screenshots/13_progress.jpg](evidence/screenshots/13_progress.jpg)<br>[local_index.json](evidence/local_index.json) | 질문 처리 중 '문서 준비 · 의미 검색 · 답변 처리 중…' 표시. 색인 없음 → 409 '검색 색인이 없습니다. 데이터 색인을 먼저 실행하세요.', 키 없음 → 'missing_key' 안내와 검색 결과 표시(로컬 실행). 운영에서 색인 삭제·키 제거는 하지 않았다. |
| 14 | F2012 | (해당 도메인만) 건강 · 금융처럼 판단이 위험한 도메인이면 전문가 조언을 대신하지 않는다는 안내가 표시된다 | **통과** | [screenshots/09_14_no_citation_and_disclaimer.jpg](evidence/screenshots/09_14_no_citation_and_disclaimer.jpg)<br>[api_run.json](evidence/api_run.json) | 채팅 하단 상시 안내 '문서 수집 시점과 현재 상태는 다를 수 있습니다. 투자 조언을 대체하지 않습니다.' 투자 판단·예측 질문은 근거가 있어도 보류한다. |
| 15 | F2013 | 화면이 HTML · CSS · JavaScript로 동작하고 질문 · 답변 · 근거가 모두 표시된다 | **통과** | [screenshots/01_main_market.jpg](evidence/screenshots/01_main_market.jpg)<br>[screenshots/08_answer_with_numbers.jpg](evidence/screenshots/08_answer_with_numbers.jpg)<br>[screenshots/19_citation_source_type.jpg](evidence/screenshots/19_citation_source_type.jpg) | dist/의 HTML·CSS·JS 화면이 FastAPI API와 분리돼 동작. 질문·답변·근거 목록·근거 원문 보기까지 확인. |
| 16 | F2014 | 같은 질문에 유사도 검색과 MMR 검색을 각각 적용했을 때 근거 목록이 어떻게 달라지는지 확인된다 | **통과** | [api_run.json](evidence/api_run.json) | 같은 SOL 질문(Top-k 5): 유사도는 공지 청크 2·0·3·1, MMR은 2·0·4·3. MMR이 유사도 4위 청크(1) 대신 앞 청크와 덜 겹치는 청크(4)를 골랐다. 근거 문서가 공지 1건뿐이라 차이가 작다. |
| 17 | F2015 | 대표 질문 5개 이상(근거 없이 답하면 틀리기 쉬운 질문)을 RAG 없이 / 근거를 붙여 각각 답하게 해, 사실 정확성 · 근거 제시 여부 · 모르는 것을 모른다고 답하는지를 비교해 기록했다 | **통과** | [docs/RAG_COMPARISON.md](../../docs/RAG_COMPARISON.md)<br>[docs/evaluation.json](../../docs/evaluation.json) | 질문 5개를 RAG 없이/RAG로 실행(2026-10-22, 실제 모델). RAG 없이 틀림 1(업비트 trade_time을 KST로 답함)·맥락 이탈 1, RAG는 수정 전 문서 속 예시 가격을 현재가로 답한 1건. 질문 세트가 김프 도메인 확정 전이고 판정은 작성 측 수동 대조다. |
| 18 | F2015 | 비교 결과를 문서로 작성해 제출물에 포함했다 | **통과** | [docs/RAG_COMPARISON.md](../../docs/RAG_COMPARISON.md) |  |
| 19 | F2016 | 근거 목록에 출처의 종류가 구분되어 표시된다 | **통과** | [screenshots/19_citation_source_type.jpg](evidence/screenshots/19_citation_source_type.jpg)<br>[screenshots/12_live_kimp_answer.jpg](evidence/screenshots/12_live_kimp_answer.jpg)<br>[api_run.json](evidence/api_run.json) | 출처 종류 4가지가 구분 표시된다: 항목 메타데이터, 빗썸 공지 원문(업비트 상태 아님), 실시간 시세 스냅샷, 거래소 API 문서·프로젝트 공식 가이드. 근거 원문 보기에서 거래소·게시·개정 시각도 보인다. |
| 20 | NF2001 | 대표 질문의 전체 처리 시간이 사용에 지장이 없다 | **통과** | [api_run.json](evidence/api_run.json)<br>[screenshots/12_live_kimp_answer.jpg](evidence/screenshots/12_live_kimp_answer.jpg) | 팀 기준을 '30초 이내 + 처리 중 표시'로 정했다. 첫 질문 23.3초, 같은 질문 재실행 13.8초, 다른 첫 질문 14~26초. 대부분이 생성 모델 호출 시간이다. 투자 판단 질문도 수집을 먼저 해 14초가 걸린다(보류 판정을 앞당기면 줄일 수 있음). 무료 서버가 잠든 뒤 첫 접속은 별도로 30초~1분 더 걸린다. |
| 21 | NF2003 · NF2004 | 소스코드와 제출물에 API 키가 남아 있지 않고, 화면에 API 키 · 프롬프트 전문 · 오류 추적 정보가 노출되지 않는다 | **통과** | [api_run.json](evidence/api_run.json)<br>[.gitignore](../../.gitignore) | 저장소 전체 커밋 이력에서 키 형식 문자열(sk-, npg_, 비밀번호 포함 DB URL) 0건, .env는 .gitignore. 오류 상황(없는 코인 404, Top-k 99 422, 잘못된 기간 400, 잘못된 공지 ID 404)은 짧은 안내만 돌려주고 스택 추적·프롬프트·키가 없다. 422는 입력값 검증 내용(필드·한도)을 보여 준다. 화면 오류는 API 응답으로 확인했다. |
| 22 | NF2005 | 수집 · 색인 · 검색 · 생성 · UI가 모듈로 분리되어 있다 | **통과** | [README.md](../../README.md) | 수집 collection.py·bithumb_notices.py·official_docs.py / 색인·검색 store.py / 생성 pipeline.py·prompts.py / 실시간 근거 live.py·market.py·fx.py / API main.py / UI dist/. 도메인 종속 부분은 catalog.py와 수집 모듈. |
| 23 | NF2006 | 외부 호출의 재시도 · 호출 간격과 출처가 요구하는 식별 정보(예: 위키백과 User-Agent 연락처)를 지켰다 | **통과** | [docs/SOURCES.md](../../docs/SOURCES.md)<br>[backend/market.py](../../backend/market.py)<br>[backend/official_docs.py](../../backend/official_docs.py) | 시세 429·502·503 재시도 2회(Retry-After 존중)·5초 캐시, 공식 문서 3회 백오프·요청 간 1초, 빗썸 요청 간 1.1초. 빗썸·공식 문서 요청에 프로젝트 식별 User-Agent. 위키백과는 쓰지 않는다. 빗썸 공지 본문 페이지가 서버 요청을 403으로 막아 관리자 브라우저로 받은 원문을 넘기는 경로를 썼다(우회용 User-Agent 위장은 하지 않음). |
| 24 | NF2007 | 사용한 데이터와 문서의 출처 · 이용 조건을 기록했다 | **통과** | [docs/SOURCES.md](../../docs/SOURCES.md)<br>[README.md](../../README.md) | 출처별 주소·키·호출 정책·이용 조건을 기록했다. 바이낸스·OKX 등 해외 시세 표시 조건, Frankfurter 약관, 빗썸 공지 본문 수집 허용 범위는 '미확인'으로 적었다. |
| 25 | 필수 | 필수 기능 F2001 ~ F2012가 모두 동작하고, 선택한 심화 기능은 필수 기능의 결과와 비교되어 있다 | **통과** | 이 문서 | 필수 1~14번 통과. 선택 심화(F2013 화면, F2014 MMR, F2015 RAG 전후, F2016 출처 종류)는 기본 결과와 비교해 기록했다. 점검 중 실패 2건(조건 탐색 0건, 김프 원인 단정)은 고친 뒤 재실행 결과로 적었다. |
| 26 | 필수 | 증명을 위한 스크린샷 항목을 모두 첨부했다 | **통과** | [screenshots/](evidence/screenshots/) | 증빙 칸의 캡처 10장을 screenshots/에 넣었다. 캡처에 키·오류 상세는 없다. 나머지 증빙은 실행 결과 JSON(api_run.json, local_index.json)이다. |
| 27 | 필수 | 요구사항 정의서 · RAG 파이프라인 설계문서 · 소스코드 · README.md · 검증 결과(요구사항 대조표, 테스트 결과표, 셀프 · 상호 체크리스트)를 모두 포함했다 | **실패** | [README.md](../../README.md)<br>[docs/TEST_RESULTS.md](../../docs/TEST_RESULTS.md)<br>이 문서 | 포함: 소스코드, README, 테스트 결과표(docs/TEST_RESULTS.md), 셀프 체크리스트·요구사항별 대조(이 문서), RAG 전후 비교. 빠짐: 요구사항 정의서, RAG 파이프라인 설계문서(별도 문서). 설계 내용은 README 3절에만 있다. 조치: 두 문서 작성 후 재점검. 상호 체크리스트는 상호 점검 시간에 작성. |

## 점검 중 고친 것

- 운영 외부 문서 0건: 빗썸 공지 본문이 서버 요청에 403, 문서 팩 17건은 실제 수집본이 아닌 예시였다. 공식 문서 4건을 서버가 받아 저장소에 보관하고, 빗썸 공지 21건은 관리자 브라우저 경유로 본문을 채웠다.
- 시세표 0건: Render IP가 바이낸스에서 418(IP 차단). OKX → Gate → Bybit 대체.
- 조건 탐색 0건, 김프 원인 단정: 위 11·12번.
- 문서 목록 패널이 빗썸 공지가 있는 코인에서 '연결 후 확인'으로 바뀌던 화면 오류(날짜 필드가 숫자).
- 과거형 질문('최근에 중지된 적 있어?')을 현재 상태 질문으로 오분류해 거절.

## 남은 것

- 15분 예약 수집(GitHub Actions)이 아직 한 번도 기록을 남기지 않았다. 그 전까지 입출금·경보 상태 질문은 근거 없음으로 거절된다.
- 새 빗썸 공지는 서버가 본문을 받지 못한다(403). 관리자 브라우저 경유가 다시 필요하다.
- 요구사항 정의서·설계문서(27번).
