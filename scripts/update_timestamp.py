#!/usr/bin/env python3
"""更新 meta.json 中的时间戳为北京时间"""

import json
import os
from datetime import datetime, timedelta, timezone

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')

NOW_BJ = datetime.now(timezone.utc) + timedelta(hours=8)
BJ_TIME = NOW_BJ.strftime('%Y-%m-%d %H:%M:%S')
BJ_DATE = NOW_BJ.strftime('%Y-%m-%d')

meta_path = os.path.join(DATA_DIR, 'meta.json')

if os.path.exists(meta_path):
    with open(meta_path, 'r', encoding='utf-8') as f:
        m = json.load(f)
    m['lastUpdatedPrecise'] = BJ_TIME
    m['lastUpdated'] = BJ_DATE
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(m, f, ensure_ascii=False, indent=2)
    print(f'时间戳已更新: {BJ_TIME}')
else:
    os.makedirs(DATA_DIR, exist_ok=True)
    m = {
        'lastUpdatedPrecise': BJ_TIME,
        'lastUpdated': BJ_DATE,
        'totalProducts': 0,
        'recentUpdates': 0,
        'categories': {},
        'sourceTracking': {},
    }
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(m, f, ensure_ascii=False, indent=2)
    print(f'meta.json 已创建: {BJ_TIME}')
