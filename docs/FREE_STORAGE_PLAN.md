# 무료 영구 저장소 조사 (2026-10-23)

사용자 결정: 무료 플랜 유지. 계정 생성/결제/외부 DB 생성은 아직 하지 않았다.

권장 후보는 Neon Free PostgreSQL. 공식 현재 가격표: https://neon.com/pricing
- 프로젝트당 DB 1GB, 월 100 CU-hours, 비활성 5분 후 compute 중지. 무료 용량/계산량 한도 내 사용 전제.
- Supabase Free는 DB 500MB, 비활성 프로젝트 일시 중지 정책이 있다. https://supabase.com/pricing 및 https://supabase.com/docs/guides/platform/free-project-pausing

제안: 원문·개정 이력·수집 체크포인트를 PostgreSQL에 저장하고, 현재 Chroma는 복구 가능한 검색 캐시로 다룬다. 임베딩 벡터도 원문 버전/모델명과 함께 외부 DB에 보존하면 재배포 때 외부 임베딩 재호출을 줄일 수 있다. pgvector로 통합하는 변경은 별도 마이그레이션과 검색 검증이 필요하다.

남은 실행 조건: 사용자 소유 무료 프로젝트와 서버 전용 DB 연결값 확보. 비밀 연결값은 채팅/Git이 아닌 로컬 .env와 Render 환경변수에서 관리한다. 저장소 연결 전에는 데이터 영속성이 해결됐다고 표시하지 않는다.

주의: 외부 DB 보존과 수집기의 상시 실행은 별개다. Render 무료 서버가 쉬는 동안의 이벤트를 DB가 대신 수집하지는 않으며, 최신 20건 목록을 넘는 누락은 별도 이력 API가 있어야 복구 가능하다.

## PostgreSQL 연결 구현 (2026-10-23)

`.env` 또는 Render 서버 환경변수에 `DATABASE_URL`을 설정하면 공지 원문과 수집 체크포인트가 PostgreSQL에 저장된다. Neon 대시보드의 SSL 연결 문자열을 그대로 사용한다. 미설정 시 로컬 SQLite를 사용하며, 설정된 PostgreSQL 연결에 실패하면 로컬로 자동 전환하지 않는다. `/api/notices/status`의 storage 필드로 선택된 저장 방식을 확인한다 (외부 저장 성공 검증을 대신하지 않음).

로컬 원문 이전: 수집 서버를 먼저 정지하고 `.env`에 대상 DB 연결값 설정 후 `python -m scripts.migrate_notices` 실행. 원본 SQLite는 읽기 전용 스냅샷으로 읽는다. 대상에 이미 존재하는 ID는 보존하며 덮어쓰지 않는다. 이전 후 DB 문서 건수와 실제 문서를 확인하고 서버를 재시작한다. 최신 버전끼리 병합하거나 과거 개정 전체를 복원하는 도구는 아니다.

검증: 별도 로컬 PostgreSQL 17 컨테이너에서 저장·중복·역순 수정 거절·64비트 시각·거래소별 문서 범위 확인. SQLite 자료 2건 이전 후 재실행 삽입 0건, 새 Python 프로세스에서 유지 확인. 기존 테스트 21개 통과. Neon과 운영 Render의 실제 연결은 아직 검증하지 않았다.

현재 외부 DB 대상은 공지 최신 원문/수집 상태뿐이다. 과거 개정의 append-only 원장, 임베딩 보존, 질문 캐시는 아직 외부 DB 대상이 아니다. Chroma는 여전히 재생성해야 하며 임베딩 비용이 생길 수 있다. Render의 수면 중 누락도 별개로 남는다.
