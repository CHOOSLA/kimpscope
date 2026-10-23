// 운영(또는 로컬) API로 체크리스트 항목을 실행하고 결과를 JSON으로 남긴다.
// 실행: node scripts/checklist_api.mjs https://kimpscope.onrender.com > docs/checklist/evidence/api_run.json
// 브라우저 콘솔에서도 같은 run(base)를 쓸 수 있다(Node 18+ / 브라우저 fetch).
// 주의: 생성 모델과 임베딩을 실제로 호출한다(질문 약 14회, 메타데이터 재색인 1회).

export async function run(base) {
  const t0 = Date.now();
  const get = async (p) => { const r = await fetch(base + p); return { status: r.status, body: await r.json().catch(() => null) }; };
  const post = async (p, data) => {
    const s = Date.now();
    const r = await fetch(base + p, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data ?? {}) });
    return { status: r.status, ms: Date.now() - s, body: await r.json().catch(() => null) };
  };
  const ask = (symbol, question, k = 5, mode = 'similarity') => post('/api/query', { symbol, question, k, mode });
  const evidenceIds = (b) => (b?.evidence || []).map((e) => e.id);
  const cited = (b) => [...new Set([...String(b?.answer || '').matchAll(/\[(\d+)\]/g)].map((m) => Number(m[1])))].sort((a, b) => a - b);
  const brief = (q) => ({ http: q.status, status: q.body?.status, ms: q.ms, elapsed_ms: q.body?.elapsed_ms, cache_hit: q.body?.cache_hit,
    answer: q.body?.answer ?? q.body?.detail, cited_in_answer: cited(q.body),
    citations: (q.body?.citations || []).map((c) => ({ number: c.number, title: c.title, source_type: c.source_type, live: c.live || null })),
    evidence: (q.body?.evidence || []).map((e) => ({ id: e.id, title: e.title, source_type: e.source_type, score: e.score })) });
  const out = { base, started_at: new Date().toISOString() };

  // 상태 · F2001
  out.status_before = (await get('/api/status')).body;

  // F2002: 메타데이터 색인을 다시 실행해도 수가 늘지 않는다
  await post('/api/index');
  for (let i = 0; i < 90; i++) { const s = (await get('/api/status')).body; if (s.state !== 'indexing') break; await new Promise((r) => setTimeout(r, 2000)); }
  out.status_after_reindex = (await get('/api/status')).body;

  // F2003·F2004·NF2002·NF2001: 같은 질문 두 번(검색어·선별 결과, 캐시, 처리 시간)
  const q1 = '솔라나 입출금이 최근에 중지된 적 있어? 이유는?';
  const a = await ask('SOL', q1); const b = await ask('SOL', q1);
  out.same_question = { question: q1, first: { ...brief(a), collection: a.body?.collection }, second: { ...brief(b), collection: b.body?.collection } };
  out.chunks_after_same_question = (await get('/api/status')).body.chunks;

  // F2006: Top-k 3 / 8
  const k3 = await ask('SOL', q1, 3); const k8 = await ask('SOL', q1, 8);
  out.top_k = { k3: evidenceIds(k3.body), k8: evidenceIds(k8.body) };

  // F2014: 유사도 / MMR
  const sim = await ask('SOL', q1, 5, 'similarity'); const mmr = await ask('SOL', q1, 5, 'mmr');
  out.similarity_vs_mmr = { similarity: brief(sim).evidence, mmr: brief(mmr).evidence };

  // F2007·F2008: 문서에 없는 질문
  out.not_in_documents = brief(await ask('BTC', '비트코인 창시자 사토시 나카모토의 실제 거주지 주소는?'));

  // F2010: 김프 브리핑(실시간 근거) · 원인 질문 · 상태 질문
  out.live_kimp = brief(await ask('BTC', '지금 비트코인 김프 몇 %야?'));
  out.why_kimp = brief(await ask('SOL', '솔라나 김프가 다른 코인과 다르게 움직인 이유가 있어?'));
  out.live_state = brief(await ask('SOL', '지금 빗썸에서 솔라나 입금 돼?'));
  // F2012(금융 위험 도메인): 투자 판단 보류
  out.forecast = brief(await ask('BTC', '지금 비트코인 사도 될까? 내일 오를까?'));

  // F2011: 조건 탐색
  const ex1 = await post('/api/explore', { query: '유의종목인 코인' });
  const ex2 = await post('/api/explore', { query: '유의종목이 아닌 비트코인' });
  out.explore = [ex1, ex2].map((e) => ({ conditions: e.body?.conditions, message: e.body?.message,
    count: (e.body?.items || []).length, mismatches: (e.body?.items || []).filter((x) => Object.entries(e.body?.conditions || {}).some(([k, v]) => k !== 'name_contains' && x[k] !== v)).map((x) => x.id),
    sample: (e.body?.items || []).slice(0, 5).map((x) => ({ id: x.id, name: x.name, warning: x.warning })) }));

  // NF2004: 오류 상황에서 내부 정보가 노출되지 않는다
  out.errors = {
    unknown_item: await post('/api/query', { symbol: 'NOPE', question: 'x' }),
    bad_top_k: await post('/api/query', { symbol: 'BTC', question: 'x', k: 99 }),
    bad_candles: await get('/api/candles/BTC?period=1Y'),
    bad_notice_id: await get('/api/notices/bithumb/..%2F..%2Fetc/versions'),
  };
  out.market = await get('/api/market').then((r) => ({ ...r.body, rows: (r.body?.rows || []).map((x) => ({ symbol: x.symbol, premium: x.premium, premium_usdt: x.premium_usdt })) }));
  out.notices_status = (await get('/api/notices/status')).body;
  out.elapsed_s = Math.round((Date.now() - t0) / 100) / 10;
  return out;
}

if (typeof process !== 'undefined' && process.argv?.[1]?.endsWith('checklist_api.mjs')) {
  const base = (process.argv[2] || 'http://127.0.0.1:4173').replace(/\/$/, '');
  run(base).then((r) => console.log(JSON.stringify(r, null, 2)));
}
