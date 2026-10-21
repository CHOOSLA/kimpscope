# 데이터 출처와 이용 조건

수집일 2026-10-22 (사용자 시간대). 298개 업비트 KRW 마켓 스냅샷.

- 메타데이터 https://api.upbit.com/v1/market/all?is_details=true : 공식 API. 마켓 그룹 초당10회 제한. 본 앱은 초기 스냅샷을 사용한다. 최초 원문은 data/markets.json.
- 시세 https://api.upbit.com/v1/ticker : 5초 캐시, 호출 병합. Binance https://data-api.binance.vision/api/v3/ticker/price. USDT 환산은 업비트 USDT/KRW 체결가이며 달러 환율이 아니다.
- 공식 API 문서 https://docs.upbit.com/kr/reference/list-trading-pairs 및 https://docs.upbit.com/kr/reference/websocket-ticker.
- 비트코인 가이드 https://bitcoin.org/en/how-it-works.
- 이더리움 가스 문서 https://ethereum.org/en/developers/docs/gas/.

교육용 로컬 검색 자료로 저장. 공식 출처라는 사실은 재배포 허가를 뜻하지 않는다. 원문 저작권은 각 권리자에게 있으며 외부 문서 팩은 공개 Site 배포 대상에서 제외한다. 상용/공개 배포 전 각 사이트 이용 약관과 라이선스의 실제 허용 범위를 확인해야 한다. 따라서 NF2007의 이용 조건 준수 완료 판정은 아직 보류한다.

수집 스크립트는 4개 고정 URL만 조회, 1초 간격, 최대3회 백오프 재시도, Retry-After 존중, 프로젝트 식별 User-Agent. 사용자 임의 URL 요청을 허용하지 않는다. 추후 공지 API 도입 시 robots/이용약관 및 개정 정책 확인이 필요하다.
