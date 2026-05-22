"""模拟 detail.js 的查找逻辑，验证每个产品的补丁信息是否可找到"""
import json, sys

meta = json.load(open(r'c:\Users\Administrator\Desktop\555\data\meta.json', encoding='utf-8'))
tracking = meta.get('sourceTracking', {}) or {}
print(f'sourceTracking 有 {len(tracking)} 个条目:')
for k in sorted(tracking.keys()):
    print(f'  {k}: version={tracking[k].get("version")} patch={tracking[k].get("patch","")[:20]}')

tracking_key_map = {'win11': 'windows_11', 'win10': 'windows_10'}

for cat in ['win11', 'win10']:
    tkey = tracking_key_map.get(cat)
    data = json.load(open(rf'c:\Users\Administrator\Desktop\555\data\{cat}.json', encoding='utf-8'))
    print(f'\n=== {cat} (sys_key={tkey}) ===')
    found = 0
    missing = 0
    for p in data['products']:
        cat_version = p.get('version') or ''
        if not cat_version or cat_version.lower() in ['arm', 'beta'] or 'lts' in cat_version.lower():
            missing += 1
            continue
        lookup_key = f'{tkey}_{cat_version.lower()}'
        t = tracking.get(lookup_key)
        if t:
            found += 1
        else:
            missing += 1
            print(f'  ❌ id={p["id"]} ver="{cat_version}" key="{lookup_key}" 未找到')
    print(f'  找到: {found}, 未找到: {missing}')

# 检查 detail.js 代码中的渲染逻辑
print('\n\n=== 检查 detail.js 渲染逻辑 ===')
with open(r'c:\Users\Administrator\Desktop\555\js\detail.js', 'r', encoding='utf-8') as f:
    js = f.read()
# 查找 patchInfo 相关代码
if 'patchInfo' in js:
    print('✅ 包含 patchInfo 变量')
if 'tracking' in js:
    print('✅ 包含 tracking 变量')
if 'lookupKey' in js:
    print('✅ 包含 lookupKey 变量')
if 'patchVersion' in js:
    print('✅ 包含 patchVersion')
if 'innerVersion' in js:
    print('✅ 包含 innerVersion')
if 'latestPatch' in js:
    print('✅ 包含 latestPatch')