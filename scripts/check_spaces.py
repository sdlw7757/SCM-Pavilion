"""检查所有产品的 version 字段是否有多余空格"""
import json

for cat in ['win11', 'win10']:
    data = json.load(open(rf'c:\Users\Administrator\Desktop\555\data\{cat}.json', encoding='utf-8'))
    for p in data['products']:
        v = p.get('version')
        if v and (v.startswith(' ') or v.endswith(' ') or v != v.strip()):
            print(f'❌ {cat} id={p["id"]} version={repr(v)}')
    print(f'✅ {cat}: 版本无空格问题')

# 直接模拟JS逻辑检查一个具体产品
print('\n=== 模拟 JS 查找逻辑 ===')
meta = json.load(open(r'c:\Users\Administrator\Desktop\555\data\meta.json', encoding='utf-8'))
tracking = meta.get('sourceTracking', {})

for pid in ['win-33e09125', 'win-52daf469', 'win-0be2efad', 'win-bc7b4a9c']:
    found = False
    for cat in ['win11', 'win10']:
        data = json.load(open(rf'c:\Users\Administrator\Desktop\555\data\{cat}.json', encoding='utf-8'))
        for p in data['products']:
            if p['id'] == pid:
                tkey = {'win11': 'windows_11', 'win10': 'windows_10'}.get(cat)
                cv = p.get('version', '')
                lk = f'{tkey}_{cv.lower()}' if tkey and cv else None
                t = tracking.get(lk) if lk else None
                print(f'pid={pid} cat={cat} version={repr(cv)} lookup_key={lk} found={t is not None}')
                if t: print(f'  patchInfo: {json.dumps(t, ensure_ascii=False)[:100]}')
                found = True
                break
        if found: break