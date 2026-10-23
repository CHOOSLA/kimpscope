# 무료 영구 저장소 조사 (2026-10-23)

사용자 결정: 무료 플랜 유지. 계정 생성/결제/외부 DB 생성은 아직 하지 않았다.

권장 후보는 Neon Free PostgreSQL. 공식 현재 가격표: https://neon.com/pricing
- 프로젝트당 DB 1GB, 월 100 CU-hours, 비활성 5분 후 compute 중지. 무료 용량/계산량 한도 내 사용 전제.
- Supabase Free는 DB 500MB, 비활성 프로젝트 일시 중지 정책이 있다. https://supabase.com/pricing 및 https://supabase.com/docs/guides/platform/free-project-pausing

제안: 원문·개정 이력·수집 체크포인트를 PostgreSQL에 저장하고, 현재 Chroma는 복구 가능한 검색 캐시로 다룬다. 임베딩 벡터도 원문 버전/모델명과 함께 외부 DB에 보존하면 재배포 때 외부 임베딩 재호출을 줄일 수 있다. pgvector로 통합하는 변경은 별도 마이그레이션과 검색 검증이 필요하다.

남은 실행 조건: 사용자 소유 무료 프로젝트와 서버 전용 DB 연결값 확보. 비밀 연결값은 채팅/Git이 아닌 로컬 .env와 Render 환경변수에서 관리한다. 저장소 연결 전에는 데이터 영속성이 해결됐다고 표시하지 않는다.

주의: 외부 DB 보존과 수집기의 상시 실행은 별개다. Render 무료 서버가 쉬는 동안의 이벤트를 DB가 대신 수집하지는 않으며, 최신 20건 목록을 넘는 누락은 별도 이력 API가 있어야 복구 가능하다.
