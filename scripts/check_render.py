import urllib.request, ssl, time, json
ctx = ssl.create_default_context()
url = 'https://kimpscope.onrender.com/api/market'

for i in range(10):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
            data = json.loads(r.read().decode('utf-8'))
            rows = data.get('rows', [])
            source = data.get('source', '')
            stale = data.get('stale', True)
            print(f"[{i+1}] rows: {len(rows)}, stale: {stale}, source: {source}")
            if len(rows) > 0 and not stale:
                print("===> 배포 완료 및 시세 수신 정상 확인!")
                break
    except Exception as e:
        print(f"[{i+1}] 에러: {e}")
    time.sleep(15)
