# Windows 검증 기록 — 2026-10-22

기준 커밋: 18294ffd10d2660c0ab4f9487081828f2e18ae55

- Python 3.12.10 가상환경 설치 완료. uvloop Windows 제외 적용.
- python -X utf8=0 -m pytest -q: 7 passed (한글 파일/캐시 회귀 포함)
- pip check: No broken requirements found.
- node --check dist/app.js / dist/integration.js: 통과
- python -m compileall -q backend scripts: 통과
- PowerShell run.ps1 -Port 4174: FastAPI 기동 성공
- GET /: HTTP 200
- GET /api/status: items=298, indexed=0, chunks=0, llm_ready=false
- GET /api/market: rows=10, stale=false, Upbit + Binance public API

현재 기기에는 모델 키와 색인이 없어 실제 임베딩·답변 생성은 검증하지 않았다. 외부 모델 호출을 수행하지 않았다. HTTP/API 검증이며 새 Windows 브라우저의 시각 검증은 수행하지 않았다.

## RAG 실연동 검증 — 2026-10-22

사용자가 로컬 키를 설정한 후 실제 API로 검증했다. 비밀 값은 기록하지 않았다.

- 메타데이터 298건 색인, 재실행 후 298건 유지
- 문서 중복 색인 방지, 질문 캐시 재사용, 항목 자체 문서 포함, BTC/ETH ID 분리 통과
- 첫 실행에 색인이 없으면 실패하던 검증 스크립트 수정
- 비트코인 공식 페이지의 메뉴/후원 안내가 후보 요약을 차지하던 문제 수정: HTML 바이트 인코딩 감지 및 #content 본문 선택, 원문 재수집
- 수정 후 BTC 질문에서 외부 공식 가이드 청크 검색 확인
- 5개 질문 RAG/비RAG 생성 비교 완료 (`evaluation.json`). 4개 문서 설명 질문은 인용 답변을 반환했다. 이것은 모든 사실의 정확성이나 검색 품질 점수 보장이 아니다.
- 실시간/미래 질문에서는 API 예시 가격을 실제 현재 가격으로 답한 오류 발견. 응답 생성 전 규칙 검사로 차단하고 동일 질문을 전체 그래프로 재실행: unsupported_live_query, 인용 0건. 이전 오류 답변은 evaluation.json의 before_fix에 보존했다.
- 회귀 포함 11 tests passed.

제한: 현재 실시간 질문 구분은 한국어 정규식 기반이며 우회 표현 전체를 보장하지 않는다. API 예시와 실제 시세의 데이터 타입 분리, 질의 분류 확장, 사실-인용 대응 평가가 추가로 필요하다. MMR/유사도 결과는 이번 BTC 질의에서 동일했으며 품질 우위를 입증하지 않았다.
