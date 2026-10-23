# 자동 테스트 결과표

실행: `python -m pytest -q` → **60 passed** (2026-10-23, Python 3.13, 외부 네트워크·모델 호출 없음)

테스트는 실측 응답과 같은 모양의 모의 데이터를 씁니다. 운영 환경에서 직접 실행한 결과는 [체크리스트 결과](checklist/RESULTS.md)에 따로 있습니다.

| 파일 | 테스트 | 확인하는 것 | 연결 요구사항 |
| --- | --- | --- | --- |
| `test_contracts.py` | `test_catalog_unique_and_large` | 항목 100건 이상, ID 중복 없음 | F2001 |
| | `test_own_document_unconditional` | 선별과 무관하게 항목 자체 문서 포함 | F2003·F2004 |
| | `test_filter_excludes_nonmatching` / `test_unsupported_filter_abstains` | 조건 탐색이 조건과 다른 항목을 섞지 않음, 지원하지 않는 조건은 거절 | F2011 |
| | `test_unknown_item` / `test_limits` | 없는 항목 404, 범위 밖 Top-k 422 | NF2004 |
| `test_collection_report.py` | `test_selection_reports_kept_and_discarded` | 프롬프트 1 검색어, 프롬프트 2 선별·제외 목록, 재질문 시 프롬프트 재호출 없음 | F2003·F2004·NF2002 |
| `test_encoding.py` | `test_korean_source_and_cache_round_trip` | 한글 원문·질문 캐시가 Windows에서도 깨지지 않음 | F2004 |
| `test_notices.py` | 5개 | 업비트 공지: 중복·순서 역전 수신, 비공식 출처 거부, 미검증 문서 팩 제외, 개정 시 질문 캐시 무효화 | F2004·F2005·NF2007 |
| `test_bithumb_notices.py` | 11개 | 빗썸 공지: 개정 이력 보존, 최신 개정만 색인, 본문 없는 공지 제외·재시도, 리다이렉트·외부 도메인 거부, 동시 갱신, 본문 실패 사유 기록 | F2004·F2005·NF2006 |
| `test_live_query_boundary.py` | 4개 | 문서 속 API 예시 가격으로 현재가를 답하지 않음 | F2007·F2008 |
| `test_kimp_live.py` 환율 | 3개 | 수출입은행 휴일 역추적·쉼표 파싱, 키 없을 때 Frankfurter, 모두 실패해도 고정 환율을 쓰지 않음 | F2010 |
| `test_kimp_live.py` 시세 | 6개 | 공식 환율 기준 김프, 거래 중단(BREAK) 심볼 제외, 환율 없으면 김프 보류, 지연 시 원인 표시, 바이낸스 차단 시 OKX 대체·소스별 실패 사유 | F2010·NF2006 |
| `test_kimp_live.py` 거래소 상태 | 6개 | 상태 변화만 기록, 호출 실패를 "경보 0건"으로 처리하지 않음, 거래소별 독립, 45분 넘은 상태는 최신 아님 | F2010 |
| `test_kimp_live.py` 실시간 근거 | 15개 | 질문 분류(현재 값 / 과거 / 예측), 최신 근거 없으면 생성하지 않음, 실시간 근거 미인용 답변 폐기, 예측 질문 보류 | F2007·F2008·F2012 |
| `test_kimp_live.py` 수집·API | 2개 | 예약 수집 종료 코드, `/api/notices/status`의 거래소 상태 요약 | NF2006 |

## 테스트가 다루지 않는 것

- 실제 임베딩 품질과 검색 순위. 운영 API로 Top-k·MMR 결과를 따로 비교했다.
- 생성 모델 답변의 사실 정확성. `docs/evaluation.json`에 RAG 전후 5개 질문 비교가 있다.
- 화면 동작(항목 전환·진행 표시). 브라우저에서 직접 확인했다.
