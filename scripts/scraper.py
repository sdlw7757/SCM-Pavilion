#!/usr/bin/env python3
"""
SCM Pavilion 全源全量数据抓取脚本
========================================
主源: HelloWindows     (https://hellowindows.cn/)
补充者: 山己几子木    (https://msdn.sjjzm.com/)
补充者: 系统库         (https://www.xitongku.com/)

输出:
  data/*.json         - 各类产品数据
  data/meta.json      - 版本信息/更新时间/今日更新数
"""

import json
import os
import re
import hashlib
import requests
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote, quote, urljoin, urlparse

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPTS_DIR, '..', 'data')
os.makedirs(DATA_DIR, exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}
TIMEOUT = 60
NOW = datetime.now(timezone.utc)
TODAY_STR = NOW.strftime('%Y-%m-%d')
NOW_BJ = NOW + timedelta(hours=8)

# 分类映射
CATS = ['win11', 'win10', 'win81', 'win7', 'server', 'office']
CAT_NAMES = {
    'win11': 'Windows 11',
    'win10': 'Windows 10',
    'win81': 'Windows 8.1',
    'win7': 'Windows 7',
    'server': 'Windows Server',
    'office': 'Microsoft Office',
}

def extract_patch_month(url_or_text):
    """从URL或文本中提取ISO整合补丁月份，如 updated_may_2026 → 2026-05"""
    m = re.search(r'updated[_\s](\w+)[_\s](\d{4})', url_or_text, re.I)
    if not m:
        return ''
    month_map = {
        'jan': '01', 'january': '01', '1': '01',
        'feb': '02', 'february': '02', '2': '02',
        'mar': '03', 'march': '03', '3': '03',
        'apr': '04', 'april': '04', '4': '04',
        'may': '05', '5': '05',
        'jun': '06', 'june': '06', '6': '06',
        'jul': '07', 'july': '07', '7': '07',
        'aug': '08', 'august': '08', '8': '08',
        'sep': '09', 'sept': '09', 'september': '09', '9': '09',
        'oct': '10', 'october': '10', '10': '10',
        'nov': '11', 'november': '11', '11': '11',
        'dec': '12', 'december': '12', '12': '12',
    }
    month_str = month_map.get(m.group(1).lower(), '')
    if month_str:
        return f'{m.group(2)}-{month_str}'
    return ''

def make_product_id(icat, version, edition, arch, lang='zh-cn'):
    """生成产品唯一ID（标准化输入以合并不同来源的相同产品）"""
    v = (version or '').strip().lower()
    e = (edition or '').strip()
    a = (arch or 'x64').strip().lower()
    l = (lang or 'zh-cn').strip().lower()
    key = f'{icat}|{v}|{e}|{a}|{l}'
    return 'win-' + hashlib.md5(key.encode()).hexdigest()[:8]

def clean(s):
    """清理多余空格"""
    return re.sub(r'\s+', ' ', s).strip()

def parse_info_block(text):
    """从文本中提取 SHA256, SHA1, MD5, 文件大小, 日期"""
    r = {'fileSize': '', 'releaseDate': '', 'sha1': '', 'sha256': '', 'md5': ''}
    t = clean(text)
    
    # 提取文件大小
    m = re.search(r'大小[:：\s]*([\d.]+(GB|MB))', t)
    if m:
        r['fileSize'] = m.group(1)
    
    # 提取日期（优先标准格式）
    m = re.search(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})', t)
    if m:
        r['releaseDate'] = m.group(1)
    if not r['releaseDate']:
        # 提取 年 月 格式
        m = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月', t)
        if m:
            r['releaseDate'] = f'{m.group(1)}-{int(m.group(2)):02d}'
    
    # 提取哈希值
    m = re.search(r'SHA256[:：\s]*([A-Fa-f0-9]{64})', t)
    if m:
        r['sha256'] = m.group(1).upper()
    m = re.search(r'SHA1[:：\s]*([A-Fa-f0-9]{40})', t)
    if m:
        r['sha1'] = m.group(1).upper()
    m = re.search(r'MD5[:：\s]*([A-Fa-f0-9]{32})', t)
    if m:
        r['md5'] = m.group(1).upper()
    
    return r

def extract_arch(text):
    """提取架构（x64/x86/arm64）"""
    t = text.lower()
    if 'arm64' in t:
        return 'arm64'
    if 'x86' in t or '32位' in t:
        return 'x86'
    return 'x64'

def extract_lang(filename):
    """提取语言（默认zh-cn）"""
    if not filename:
        return 'zh-cn'
    f = filename.lower()
    if 'zh-cn' in f or 'chinese' in f or 'cn_' in f:
        return 'zh-cn'
    if 'en-us' in f or 'english' in f:
        return 'en-us'
    return 'zh-cn'

def extract_version(text):
    """提取版本号"""
    # 匹配 version xxx
    m = re.search(r'version\s+(\S+)', text, re.I)
    if m:
        return m.group(1)
    # 匹配 LTSC/LTSB 年份
    m = re.search(r'(LTSC|LTSB)\s*(\d{4})', text, re.I)
    if m:
        return m.group(0)
    # 匹配 数字H数字 格式
    m = re.search(r'(\d+H\d+)', text, re.I)
    if m:
        return m.group(1)
    # 匹配 Office 年份
    m = re.search(r'Office\s*(\d{4})', text, re.I)
    if m:
        return m.group(1)
    return ''

def extract_edition(text):
    """提取版本类型"""
    t = text.lower()
    if 'business' in t or '商业版' in t:
        return 'Business'
    if 'consumer' in t or '消费版' in t or '零售版' in t:
        return 'Consumer'
    if 'ltsc' in t:
        return 'LTSC'
    if 'ltsb' in t:
        return 'LTSB'
    if 'enterprise' in t or '企业版' in t:
        return 'Enterprise'
    if 'professional' in t or '专业版' in t:
        return 'Professional'
    if 'ultimate' in t or '旗舰版' in t:
        return 'Ultimate'
    if 'home' in t or '家庭版' in t:
        return 'Home'
    if 'education' in t or '教育版' in t:
        return 'Education'
    if 'standard' in t or '标准版' in t:
        return 'Standard'
    if 'datacenter' in t:
        return 'Datacenter'
    return 'Consumer'

def make_name(cat_name, edition, arch):
    """生成产品显示名称"""
    n = cat_name
    if edition and edition not in ('Consumer', 'Business'):
        n += f' {edition}'
    if arch and arch not in ('x64',):
        n += f' ({arch})'
    return n

# ==================== 数据源1: HelloWindows ====================
HELLO_CAT_MAP = {
    'Windows11 LTSC': 'win11',
    'Windows11 version 26H1': 'win11',
    'Windows11 version 25H2': 'win11',
    'Windows11 version 24H2': 'win11',
    'Windows11 version 23H2': 'win11',
    'Windows11 version 22H2': 'win11',
    'Windows11 version 21H2': 'win11',
    'Windows10 LTSC/B': 'win10',
    'Windows10 version 22H2': 'win10',
    'Windows10 version 21H2': 'win10',
    'Windows10 version 21H1': 'win10',
    'Windows10 version 20H2': 'win10',
    'Windows10 version 2004': 'win10',
    'Windows10 version 1909': 'win10',
    'Windows10 version 1903': 'win10',
    'Windows10 version 1809': 'win10',
    'Windows10 version 1803': 'win10',
    'Windows10 version 1709': 'win10',
    'Windows10 version 1703': 'win10',
    'Windows10 version 1607': 'win10',
    'Windows10 version 1511': 'win10',
    'Windows10 version 1507': 'win10',
    'Windows 8.1': 'win81',
    'Windows 8': 'win81',
    'Windows 7': 'win7',
    'Server 2022-2099': 'server',
    'Server 2012-2019': 'server',
    'Server 2008-2008': 'server',
    'Office/WPS': 'office',
}
SKIP_HELLO = {'其他版本', 'Windows Vista', 'Windows XP'}

def scrape_hellowindows():
    """爬取 HelloWindows 数据"""
    print('\n数据源1: HelloWindows 开始爬取')
    url = 'https://hellowindows.cn/'
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.encoding = 'utf-8'
    html = r.text

    # 提取 items JSON
    start = html.find('items: [')
    end_marker = html.find('methods:', start + 7)
    raw = html[start + 7: end_marker].strip().rstrip(',').rstrip()
    last_close = raw.rfind(']')
    items = json.loads(raw[:last_close + 1])
    item_count = len(items)

    print(f'  发现{item_count} 个分类项')

    result = {c: [] for c in CATS}
    for item in items:
        cat_name = item.get('category', '')
        if cat_name in SKIP_HELLO:
            continue
        icat = HELLO_CAT_MAP.get(cat_name)
        if not icat:
            continue

        seen = set()
        for entry in item.get('list', []):
            title = entry.get('title', '')
            info = entry.get('info', '')
            if not title or not info:
                continue
            
            parsed = parse_info_block(info)
            if not (parsed['sha1'] or parsed['sha256'] or parsed['md5']):
                continue

            # 提取文件名（.iso）
            mf = re.search(r'(\S+?\.iso)', info)
            fn = mf.group(1) if mf else ''
            if not fn:
                continue

            arch = extract_arch(title + entry.get('bit', ''))
            lang = extract_lang(fn)
            ver = extract_version(title)
            edition = extract_edition(title)
            cat_full = CAT_NAMES.get(icat, 'Windows')
            name = make_name(cat_full, edition, arch)

            # 整理哈希值
            hashes = {}
            if parsed['sha256']:
                hashes['sha256'] = parsed['sha256']
            if parsed['sha1']:
                hashes['sha1'] = parsed['sha1']
            if not hashes and parsed['md5']:
                hashes['md5'] = parsed['md5']

            # 生成产品ID并去重
            pid = make_product_id(icat, ver, edition, arch, lang)
            if pid in seen:
                continue
            seen.add(pid)

            # 整理下载链接
            links = entry.get('links', [])
            sources = []
            for l in links:
                if not l.get('url'):
                    continue
                s = {
                    'name': l.get('name', 'HelloWindows'),
                    'url': l.get('url', ''),
                    'type': 'redirect',
                    '_source': 'HelloWindows'
                }
                pm = extract_patch_month(info)
                if pm:
                    s['patchMonth'] = pm
                sources.append(s)
            if not sources:
                s = {
                    'name': 'HelloWindows',
                    'url': url,
                    'type': 'redirect',
                    '_source': 'HelloWindows'
                }
                pm = extract_patch_month(info)
                if pm:
                    s['patchMonth'] = pm
                sources = [s]

            # 添加到结果
            result[icat].append({
                'id': pid,
                'name': name,
                'version': ver,
                'build': '',
                'releaseDate': parsed['releaseDate'],
                'language': lang,
                'architecture': arch,
                'edition': edition,
                'sku': edition,
                'fileSize': parsed['fileSize'],
                'hashes': hashes,
                'sources': sources,
                'originalSource': 'Microsoft MSDN',
                'verified': True,
                '_source': 'HelloWindows',
            })

        if result[icat]:
            print(f'  [{cat_name}] 分类 {icat}: {len(result[icat])} 个产品')
    
    return result

# ==================== 数据源2: 山己几子木 ====================
MSDN_BASE = 'https://msdn.sjjzm.com'

def parse_msdn_table_from_html(table_html, surrounding_text, icat='', raw_after_html=''):
    """解析HTML表格内容，提取文件信息和下载链接"""
    full = clean(surrounding_text)

    # 提取表格基础信息
    fn = ''
    sha256_val = ''
    sha1_val = ''
    md5_val = ''
    size_val = ''

    rows = re.findall(r'<tr[^>]*>.*?</tr>', table_html, re.DOTALL)
    for row in rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        if len(cells) >= 2:
            key = clean(cells[0]).lower()
            val = clean(re.sub(r'<[^>]+>', '', cells[1]))
            if '文件名' in key:
                fn = val
            elif 'sha-256' in key:
                sha256_val = val.upper()
            elif 'sha-1' in key:
                sha1_val = val.upper()
            elif 'md5' in key:
                md5_val = val.upper()
            elif '大小' in key:
                size_val = val

    if not fn:
        return None

    # 提取补充信息
    info = parse_info_block(full)
    if sha256_val:
        info['sha256'] = sha256_val
    if sha1_val:
        info['sha1'] = sha1_val
    if md5_val:
        info['md5'] = md5_val
    if size_val:
        info['fileSize'] = size_val
    if not info['releaseDate']:
        m = re.search(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})', full)
        if m:
            info['releaseDate'] = m.group(1)

    # 提取下载链接
    sources = []
    # 旧版链接格式（直接跟在文字后）
    link_pattern_old = [
        (r'阿里云盘地址\s*(https?://[^\s<]+)', '阿里云盘'),
        (r'百度网盘链接\s*(https://[^\s<]+)', '百度网盘'),
        (r'夸克网盘链接\s*[^<]*?(https://[^\s<]+)', '夸克网盘'),
        (r'189网盘链接\s*(https://[^\s<]+)', '189网盘'),
        (r'迅雷网盘链接\s*(https://[^\s<]+)', '迅雷网盘'),
        (r'ed2k下载\s*(ed2k://[^\s<]+)', 'ed2k'),
        (r'BT磁力链接下载\s*(magnet:[^\s<]+)', 'BT磁力链接'),
        (r'直链下载\s*(https://[^\s<]+)', '直链下载'),
        (r'天翼网盘链接\s*(https://[^\s<]+)', '天翼网盘'),
    ]
    # 新版链接格式（文字后带value="URL"）
    link_pattern_new = [
        (r'阿里云盘链接.{0,200}value\s+(https://[^\s]+)', '阿里云盘'),
        (r'百度网盘链接.{0,200}value\s+(https://[^\s]+)', '百度网盘'),
        (r'夸克网盘链接.{0,200}value\s+(https://[^\s]+)', '夸克网盘'),
        (r'189网盘链接.{0,200}value\s+(https://[^\s]+)', '189网盘'),
        (r'迅雷网盘链接.{0,200}value\s+(https://[^\s]+)', '迅雷网盘'),
        (r'ed2k下载.{0,200}value\s+(ed2k://[^\s]+)', 'ed2k'),
        (r'BT磁力链接下载.{0,200}value\s+(magnet:[^\s]+)', 'BT磁力链接'),
        (r'直链下载.{0,200}value\s+(https://[^\s]+)', '直链下载'),
        (r'天翼网盘链接.{0,200}value\s+(https://[^\s]+)', '天翼网盘'),
    ]
    seen_urls = set()
    
    # 匹配旧版链接
    for pat, name in link_pattern_old:
        m = re.search(pat, full, re.I)
        if m and m.group(1) not in seen_urls:
            seen_urls.add(m.group(1))
            sources.append({
                'name': name,
                'url': m.group(1),
                'type': 'redirect',
                '_source': '山己几子木'
            })
    
    # 匹配新版链接（与旧版互补，不互斥）
    for pat, name in link_pattern_new:
        m = re.search(pat, full, re.I | re.DOTALL)
        if m and m.group(1) not in seen_urls:
            seen_urls.add(m.group(1))
            sources.append({
                'name': name,
                'url': m.group(1),
                'type': 'redirect',
                '_source': '山己几子木'
            })

    # 最后从原始HTML提取value属性（进一步补充）
    if raw_after_html:
        raw_link_patterns = [
            (r'<div class="label">阿里云盘地址</div>.*?<input[^>]*value="(https://[^"]+)"', '阿里云盘'),
            (r'<div class="label">腾讯微云地址</div>.*?<input[^>]*value="(https://[^"]+)"', '腾讯微云'),
            (r'<div class="label">百度网盘地址</div>.*?<input[^>]*value="(https://[^"]+)"', '百度网盘'),
            (r'<div class="label">天翼云盘地址</div>.*?<input[^>]*value="(https://[^"]+)"', '天翼云盘'),
            (r'<div class="label">移动云盘地址</div>.*?<input[^>]*value="(https://[^"]+)"', '移动云盘'),
            (r'<div class="label">夸克网盘地址</div>.*?<input[^>]*value="(https://[^"]+)"', '夸克网盘'),
            (r'<div class="label">189网盘地址</div>.*?<input[^>]*value="(https://[^"]+)"', '189网盘'),
            (r'<div class="label">迅雷网盘地址</div>.*?<input[^>]*value="(https://[^"]+)"', '迅雷网盘'),
            (r'<div class="label">ed2k下载</div>.*?<input[^>]*value="(ed2k://[^"]+)"', 'ed2k'),
            (r'<div class="label">BT磁力下载</div>.*?<input[^>]*value="(magnet:[^"]+)"', 'BT磁力链接'),
            (r'<div class="label">直链下载</div>.*?<input[^>]*value="(https?://[^"]+)"', '直链下载'),
        ]
        for pat, name in raw_link_patterns:
            m = re.search(pat, raw_after_html, re.I | re.DOTALL)
            if m and m.group(1) not in seen_urls:
                seen_urls.add(m.group(1))
                sources.append({
                    'name': name,
                    'url': m.group(1),
                    'type': 'redirect',
                    '_source': '山己几子木'
                })

    # 为所有链接添加patchMonth（从URL或上下文提取）
    for s in sources:
        pm = extract_patch_month(s['url']) or extract_patch_month(full)
        if pm:
            s['patchMonth'] = pm

    # 提取产品属性
    arch = extract_arch(full)
    lang = extract_lang(fn)
    edition = extract_edition(full)
    ver = extract_version(full)

    # 确定产品分类全称
    cat_full = ''
    if 'windows 11' in full.lower():
        cat_full = 'Windows 11'
    elif 'windows 10' in full.lower():
        cat_full = 'Windows 10'
    elif 'windows 8.1' in full.lower():
        cat_full = 'Windows 8.1'
    elif 'windows 8' in full.lower():
        cat_full = 'Windows 8.1'
    elif 'windows 7' in full.lower():
        cat_full = 'Windows 7'
    elif 'server' in full.lower():
        cat_full = 'Windows Server'
    elif 'office' in full.lower():
        cat_full = 'Microsoft Office'

    # 生成名称和哈希
    name = make_name(cat_full, edition, arch)
    hashes = {}
    if info['sha256']:
        hashes['sha256'] = info['sha256']
    if info['sha1']:
        hashes['sha1'] = info['sha1']
    if not hashes and info['md5']:
        hashes['md5'] = info['md5']

    # 生成产品ID
    pid = make_product_id(icat, ver, edition, arch, lang)

    return {
        'id': pid,
        'name': name,
        'version': ver,
        'build': '',
        'releaseDate': info['releaseDate'],
        'language': lang,
        'architecture': arch,
        'edition': edition,
        'sku': edition,
        'fileSize': info['fileSize'],
        'hashes': hashes,
        'sources': sources,
        'originalSource': 'Microsoft MSDN',
        'verified': True,
        '_source': '山己几子木',
    }

def scrape_msdn_page(url, icat):
    """爬取单个山己几子木页面 - 解析h1 + table结构"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.encoding = 'utf-8'
    except Exception as e:
        print(f'  [ERR] {url}: {e}')
        return []
    
    html = r.text
    blocks = re.split(r'<h1[^>]*>', html)
    products = []
    seen = set()

    for i, block in enumerate(blocks[1:], 1):
        # 提取h1标题
        title_end = block.find('</h1>')
        title = block[:title_end] if title_end > 0 else ''
        title = re.sub(r'<[^>]+>', '', title).strip()
        if not title:
            continue

        # 提取标题日期
        tag_date = ''
        m_date = re.search(r'<span class="date">(\d{4}[-/]\d{1,2}[-/]\d{1,2})</span>', block)
        if m_date:
            tag_date = m_date.group(1)

        # 提取表格
        tables = re.findall(r'<table[^>]*>(.*?)</table>', block, re.DOTALL)
        table_splits = re.split(r'</tbody>\s*</table>', block)

        for j, tbl in enumerate(tables):
            tbl_html = '<table>' + tbl + '</table>'
            # 获取表格后的内容
            after_table = table_splits[j + 1] if (j + 1) < len(table_splits) else ''
            next_tbl = after_table.find('<table')
            after_table_content = after_table[:next_tbl] if next_tbl > 0 else after_table[:2500]
            after_clean = re.sub(r'<[^>]+>', ' ', after_table_content)

            # 拼接上下文
            extra = f' {tag_date} ' if tag_date else ''
            context = title + extra + re.sub(r'<[^>]+>', ' ', tbl[:500]) + ' ' + after_clean

            # 解析表格数据
            p = parse_msdn_table_from_html(tbl_html, context, icat, raw_after_html=after_table_content)
            if p and p['hashes'] and p['id'] not in seen:
                seen.add(p['id'])
                products.append(p)

    return products

def get_msdn_subpages(url, base_url):
    """获取子页面链接"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.encoding = 'utf-8'
    except Exception:
        return []
    
    links = re.findall(r'href=[\'"]([^\'"]+)[\'"]', r.text)
    subpages = []
    for l in links:
        full = urljoin(base_url, l)
        if l.startswith('/') and (l.startswith('/win10/') or l.startswith('/office/') or l.startswith('/win7/') or l.startswith('/win8') or l.startswith('/server/')):
            subpages.append(full)
    return subpages

def scrape_msdn():
    """爬取山己几子木全站数据"""
    print('\n数据源2: 山己几子木 开始爬取')
    result = []

    # Win11 数据
    for p in scrape_msdn_page(MSDN_BASE + '/win11/', 'win11'):
        result.append(('win11', p))
    for u in [
        f'{MSDN_BASE}/win11/26h1.html', f'{MSDN_BASE}/win11/25h2.html',
        f'{MSDN_BASE}/win11/24h2.html', f'{MSDN_BASE}/win11/23h2.html',
        f'{MSDN_BASE}/win11/22h2.html', f'{MSDN_BASE}/win11/21h2.html',
    ]:
        for p in scrape_msdn_page(u, 'win11'):
            result.append(('win11', p))
    print(f'  win11: 共获取 {sum(1 for c,_ in result if c=="win11")} 个产品')

    # Win10 数据
    win10_pages = get_msdn_subpages(MSDN_BASE + '/win10.html', MSDN_BASE)
    if not win10_pages:
        win10_pages = [
            f'{MSDN_BASE}/win10/22h2.html', f'{MSDN_BASE}/win10/21h2.html',
            f'{MSDN_BASE}/win10/2104.html', f'{MSDN_BASE}/win10/2009.html',
            f'{MSDN_BASE}/win10/2004.html', f'{MSDN_BASE}/win10/1909.html',
            f'{MSDN_BASE}/win10/1903.html', f'{MSDN_BASE}/win10/1809.html',
            f'{MSDN_BASE}/win10/1803.html', f'{MSDN_BASE}/win10/1709.html',
            f'{MSDN_BASE}/win10/1703.html', f'{MSDN_BASE}/win10/1607.html',
            f'{MSDN_BASE}/win10/1511.html', f'{MSDN_BASE}/win10/other.html',
        ]
    for u in win10_pages:
        for p in scrape_msdn_page(u, 'win10'):
            result.append(('win10', p))
    print(f'  win10: 共获取 {sum(1 for c,_ in result if c=="win10")} 个产品')

    # Win8.1 数据
    for p in scrape_msdn_page(MSDN_BASE + '/win81.html', 'win81'):
        result.append(('win81', p))
    for u in [MSDN_BASE + '/win81/update.html', MSDN_BASE + '/win81/first.html']:
        for p in scrape_msdn_page(u, 'win81'):
            result.append(('win81', p))
    print(f'  win81: 共获取 {sum(1 for c,_ in result if c=="win81")} 个产品')

    # Win7 数据
    for p in scrape_msdn_page(MSDN_BASE + '/win7.html', 'win7'):
        result.append(('win7', p))
    for u in [MSDN_BASE + '/win7/sp1.html', MSDN_BASE + '/win7/first.html']:
        for p in scrape_msdn_page(u, 'win7'):
            result.append(('win7', p))
    print(f'  win7: 共获取 {sum(1 for c,_ in result if c=="win7")} 个产品')

    # Office 数据
    office_pages = get_msdn_subpages(MSDN_BASE + '/office.html', MSDN_BASE)
    if not office_pages:
        office_pages = [
            f'{MSDN_BASE}/office/2024.html', f'{MSDN_BASE}/office/2021.html',
            f'{MSDN_BASE}/office/2019.html', f'{MSDN_BASE}/office/2016.html',
            f'{MSDN_BASE}/office/2013.html', f'{MSDN_BASE}/office/2010.html',
            f'{MSDN_BASE}/office/2007.html', f'{MSDN_BASE}/office/2003.html',
        ]
    for u in office_pages:
        for p in scrape_msdn_page(u, 'office'):
            result.append(('office', p))
    print(f'  office: 共获取 {sum(1 for c,_ in result if c=="office")} 个产品')

    # Server 数据
    server_pages = get_msdn_subpages(MSDN_BASE + '/server.html', MSDN_BASE)
    if not server_pages:
        server_pages = [
            f'{MSDN_BASE}/server/2025.html', f'{MSDN_BASE}/server/2022.html',
            f'{MSDN_BASE}/server/2019.html', f'{MSDN_BASE}/server/2016.html',
            f'{MSDN_BASE}/server/2012r2.html', f'{MSDN_BASE}/server/2012.html',
            f'{MSDN_BASE}/server/2008r2.html', f'{MSDN_BASE}/server/2008.html',
        ]
    for u in server_pages:
        for p in scrape_msdn_page(u, 'server'):
            result.append(('server', p))
    print(f'  server: 共获取 {sum(1 for c,_ in result if c=="server")} 个产品')

    return result

# ==================== 数据源3: 系统库 (xitongku.com) ====================
XTK_CAT_MAP = {
    'Win11': 'win11',
    'Win10': 'win10',
    'Win8.1': 'win81',
    'Win7': 'win7',
    'WinServer': 'server',
    'Server': 'server',
}

def scrape_xitongku():
    """爬取系统库 JSON API 数据"""
    print('\n数据源3: 系统库 开始爬取')
    result = {c: [] for c in CATS}

    def _fetch_json(url, label):
        """获取JSON数据"""
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            r.encoding = 'utf-8-sig'
            raw = r.text
            if raw.startswith('\ufeff'):
                raw = raw[1:]
            return json.loads(raw)
        except Exception as e:
            print(f'  [ERR] {label}: {e}')
            return []

    # 1. 获取Windows数据
    windows_data = _fetch_json(win_url := 'https://www.xitongku.com/data/windows.json', 'windows.json')
    if windows_data:
        print(f'  windows.json: {len(windows_data)} 个节点')

    # 2. 获取Office数据
    office_data = _fetch_json(off_url := 'https://www.xitongku.com/data/office.json', 'office.json')
    if office_data:
        print(f'  office.json: {len(office_data)} 个节点')

    seen_ids = set()

    def parse_xtk_tree(items, path_info):
        """递归遍历系统库树形结构，提取产品信息"""
        for item in items:
            name = item.get('name', '')
            keywords_raw = item.get('keywords', '')
            description = item.get('description', '')
            children = item.get('children', [])

            # 当前路径
            cur_path = path_info + [name]

            if keywords_raw and keywords_raw.strip():
                # 解析下载链接
                try:
                    links_dict = json.loads(keywords_raw)
                except Exception:
                    links_dict = {}

                if not links_dict:
                    continue

                # 提取描述信息
                desc_text = clean(description)
                parsed = parse_info_block(desc_text)

                # 提取文件名
                fn = ''
                mf = re.search(r'(\S+?\.(iso|img))', desc_text)
                if mf:
                    fn = mf.group(1)

                if not fn:
                    continue

                # 提取平台分类
                platform = path_info[0] if len(path_info) > 0 else ''
                icat = XTK_CAT_MAP.get(platform)
                if not icat:
                    # 处理Office版本
                    if platform in ('2024', '2021', '2019', '2016', '2013', '2010', '2007', '2003'):
                        icat = 'office'

                if not icat:
                    continue

                # 提取架构
                arch = 'x64'
                for p in cur_path:
                    if 'arm64' in p.lower():
                        arch = 'arm64'
                        break
                    if '32位' in p or 'x86' in p.lower():
                        arch = 'x86'
                        break
                    if '64位' in p:
                        arch = 'x64'

                # 提取版本类型
                edition = 'Consumer'
                for p in path_info:
                    if '商业版' in p or 'business' in p.lower():
                        edition = 'Business'
                        break
                    if '消费版' in p or 'consumer' in p.lower():
                        edition = 'Consumer'

                # 提取版本号
                ver = ''
                if icat == 'office':
                    if path_info:
                        ver = path_info[0]
                    # Office版本细化（如 ProPlus.Consumer）
                    if len(path_info) >= 2 and path_info[1] and edition in ('Consumer', 'Business'):
                        edition = f'{path_info[1]}.{edition}'
                elif len(path_info) >= 2:
                    ver = path_info[1]
                if not ver:
                    m = re.search(r'version\s+(\S+)', desc_text, re.I)
                    if m:
                        ver = m.group(1)

                # 提取发布日期
                release_date = parsed['releaseDate']
                if not release_date:
                    for p in path_info:
                        m = re.search(r'(\d{4})[.](\d{2})', p)
                        if m:
                            release_date = f'{m.group(1)}-{m.group(2)}'
                            break

                # 生成显示名称
                cat_full = CAT_NAMES.get(icat, 'Windows')
                edition_label = ''
                product_type = ''
                raw_edition = edition
                if icat == 'office' and '.' in edition:
                    # 拆分 Office 版本类型
                    parts = edition.split('.', 1)
                    product_type = parts[0]
                    raw_edition = parts[1]
                
                if raw_edition == 'Consumer':
                    edition_label = '消费版'
                elif raw_edition == 'Business':
                    edition_label = '商业版'
                
                name_display = cat_full
                if ver:
                    name_display += f' {ver}'
                if product_type:
                    name_display += f' {product_type}'
                if edition_label:
                    name_display += f' {edition_label}'
                if arch and arch != 'x64':
                    name_display += f' ({arch})'

                # 整理哈希值
                hashes = {}
                if parsed['sha256']:
                    hashes['sha256'] = parsed['sha256']
                if parsed['sha1']:
                    hashes['sha1'] = parsed['sha1']
                if not hashes and parsed['md5']:
                    hashes['md5'] = parsed['md5']

                # 整理下载链接
                sources = []
                link_type_map = {
                    'ED2K': ('ed2k', 'ED2K'),
                    '磁力链接': ('magnet', '磁力链接'),
                    '夸克网盘': ('pan.quark', '夸克网盘'),
                    '123网盘': ('123pan', '123网盘'),
                    '189网盘': ('cloud.189', '189网盘'),
                    '阿里云盘': ('aliyundrive', '阿里云盘'),
                    '迅雷网盘': ('xunlei', '迅雷网盘'),
                    '谷歌网盘': ('drive.google', '谷歌网盘'),
                }
                
                for link_name, link_url in links_dict.items():
                    if not link_url or link_url.startswith('https://www.xitongku.com/'):
                        continue
                    link_type = 'redirect'
                    for key, (type_val, _) in link_type_map.items():
                        if key in link_name or key.lower() in link_name.lower():
                            link_type = type_val
                            break
                    s = {
                        'name': link_name,
                        'url': link_url,
                        'type': link_type,
                        '_source': '系统库',
                    }
                    pm = extract_patch_month(link_url) or extract_patch_month(desc_text)
                    if pm:
                        s['patchMonth'] = pm
                    sources.append(s)

                # 生成产品ID并去重
                pid = make_product_id(icat, ver, edition, arch, 'zh-cn')
                if pid in seen_ids:
                    continue
                seen_ids.add(pid)

                # 提取build号
                build = ''
                mb = re.search(r'内部版本\s*(\S+)', desc_text)
                if mb:
                    build = mb.group(1)

                # 添加到结果
                result[icat].append({
                    'id': pid,
                    'name': name_display,
                    'version': ver,
                    'build': build,
                    'releaseDate': release_date,
                    'language': 'zh-cn',
                    'architecture': arch,
                    'edition': edition,
                    'sku': edition,
                    'fileSize': parsed['fileSize'],
                    'hashes': hashes,
                    'sources': sources,
                    'originalSource': 'Microsoft MSDN',
                    'verified': True,
                    '_source': '系统库',
                })

            # 递归处理子节点
            if children:
                parse_xtk_tree(children, cur_path)

    # 解析Windows数据
    parse_xtk_tree(windows_data, [])
    # 解析Office数据
    parse_xtk_tree(office_data, [])

    # 输出各分类数量
    for cat in CATS:
        if result[cat]:
            print(f'  [{cat}] {len(result[cat])} 个产品')

    return result

# ==================== 版本追踪数据（综合构建） ====================
XTK_TRACKING_URL = 'https://xtk-api.hipcapi.com/index/windowVersion/list'

def scrape_xitongku_tracking():
    """构建完整的版本追踪数据表（API最新版 + 静态补充历史版本）"""
    api_data = {}
    try:
        r = requests.get(XTK_TRACKING_URL, headers=HEADERS, timeout=TIMEOUT)
        data = r.json()
        entries = data.get('data', {}).get('list', [])
        for e in entries:
            name = e.get('system_name', '')
            ver = e.get('system_version', '')
            if name:
                key = (name.lower().replace(' ', '_'), ver.lower()) if ver else (name.lower().replace(' ', '_'), '')
                api_data[key] = {
                    'systemName': name,
                    'version': ver,
                    'innerVersion': e.get('system_inner_version', ''),
                    'patchVersion': e.get('patch_version', ''),
                    'updatedAt': e.get('updated_at', ''),
                    'publishDate': e.get('system_pulish_date', ''),
                    'patch': e.get('system_patch', ''),
                }
    except Exception as e:
        print(f'  [WARN] 系统库版本追踪API: {e}')

    # 已知版本追踪数据（API未覆盖的历史版本）
    TRACKING_DB = {
        ('windows_11', '26h1'): (28000, '', ''),
        ('windows_11', '25h2'): (26100, '', ''),
        ('windows_11', '24h2'): (26100, '', ''),
        ('windows_11', '23h2'): (22631, '', ''),
        ('windows_11', '22h2'): (22621, '', ''),
        ('windows_11', '21h2'): (22000, '', ''),
        ('windows_10', '22h2'): (19045, '', ''),
        ('windows_10', '21h2'): (19044, '已停止服务', ''),
        ('windows_10', '21h1'): (19043, '已停止服务', ''),
        ('windows_10', '20h2'): (19042, '已停止服务', ''),
        ('windows_10', '2004'): (19041, '已停止服务', ''),
        ('windows_10', '1909'): (18363, '已停止服务', ''),
        ('windows_10', '1903'): (18362, '已停止服务', ''),
        ('windows_10', '1809'): (17763, '已停止服务', ''),
        ('windows_10', '1803'): (17134, '已停止服务', ''),
        ('windows_10', '1709'): (16299, '已停止服务', ''),
        ('windows_10', '1703'): (15063, '已停止服务', ''),
        ('windows_10', '1607'): (14393, '已停止服务', ''),
        ('windows_10', '1511'): (10586, '已停止服务', ''),
    }

    tracking = {}
    for (sys_key, ver_key), (inner, status, _) in TRACKING_DB.items():
        lookup_key = f'{sys_key}_{ver_key}'
        api_entry = api_data.get((sys_key, ver_key), api_data.get((sys_key, ''), {}))
        entry = {
            'systemName': f'Windows {sys_key.replace("windows_", "").title()}' if not api_entry.get('systemName') else api_entry['systemName'],
            'version': ver_key,
            'innerVersion': api_entry.get('innerVersion', '') or inner,
            'patchVersion': api_entry.get('patchVersion', ''),
            'updatedAt': api_entry.get('updatedAt', status),
            'publishDate': api_entry.get('publishDate', ''),
            'patch': api_entry.get('patch', '') or status,
        }
        # 从 updatedAt 推导 latestPatchMonth（如 2026-06-02 → 2026-06）
        updated_at = entry.get('updatedAt', '')
        if updated_at and re.match(r'\d{4}-\d{2}', updated_at):
            entry['latestPatchMonth'] = updated_at[:7]
        tracking[lookup_key] = entry

    return tracking

# ==================== 主函数（示例） ====================
if __name__ == '__main__':
    all_data = {cat: [] for cat in CATS}
    has_any_data = False

    # 爬取所有数据源（逐个防护，一个失败不影响其他）
    try:
        print('\n========== 数据源1: HelloWindows ==========')
        hello_data = scrape_hellowindows()
        for cat in CATS:
            all_data[cat].extend(hello_data.get(cat, []))
        has_any_data = has_any_data or any(hello_data.get(cat) for cat in CATS)
    except Exception as e:
        print(f'  [ERROR] HelloWindows 爬取失败: {e}')

    try:
        print('\n========== 数据源2: 山己几子木 ==========')
        msdn_data = scrape_msdn()
        for cat, product in msdn_data:
            all_data[cat].append(product)
        has_any_data = has_any_data or bool(msdn_data)
    except Exception as e:
        print(f'  [ERROR] 山己几子木 爬取失败: {e}')

    try:
        print('\n========== 数据源3: 系统库 ==========')
        xtk_data = scrape_xitongku()
        for cat in CATS:
            all_data[cat].extend(xtk_data.get(cat, []))
        has_any_data = has_any_data or any(xtk_data.get(cat) for cat in CATS)
    except Exception as e:
        print(f'  [ERROR] 系统库 爬取失败: {e}')

    if has_any_data:
        # 去重并按ID合并来源（不同网站的同一个产品，合并下载链接）
        for cat in CATS:
            merged = {}
            for p in all_data[cat]:
                pid = p['id']
                if pid in merged:
                    existing = merged[pid]
                    # 合并下载链接（按URL去重）
                    seen_urls = {s['url'] for s in existing.get('sources', [])}
                    for s in p.get('sources', []):
                        if s['url'] not in seen_urls:
                            seen_urls.add(s['url'])
                            existing['sources'].append(s)
                    # 补充缺失的哈希值
                    for h in ('sha256', 'sha1', 'md5'):
                        if not existing.get('hashes', {}).get(h) and p.get('hashes', {}).get(h):
                            if 'hashes' not in existing:
                                existing['hashes'] = {}
                            existing['hashes'][h] = p['hashes'][h]
                    # 记录来源标记
                    p_source = p.get('_source', '')
                    if p_source and p_source not in existing.setdefault('_sources', [existing.get('_source', '')]):
                        existing['_sources'].append(p_source)
                else:
                    merged[pid] = dict(p)
                    if '_sources' not in merged[pid]:
                        merged[pid]['_sources'] = [merged[pid].get('_source', '')]
            all_data[cat] = list(merged.values())

        # 保存到文件
        for cat in CATS:
            if all_data[cat]:
                with open(os.path.join(DATA_DIR, f'{cat}.json'), 'w', encoding='utf-8') as f:
                    json.dump({'products': all_data[cat]}, f, ensure_ascii=False, indent=2)

    # 保存元数据（无论是否有数据都保存）
    try:
        xtk_tracking = scrape_xitongku_tracking()
    except Exception as e:
        print(f'  [WARN] 版本追踪数据获取失败: {e}')
        xtk_tracking = {}

    # 从所有数据源的产品数据中构建版本追踪（补充系统库API未覆盖的版本）
    product_tracking = {}
    cat_sys_names = {
        'win11': 'Windows 11', 'win10': 'Windows 10',
        'win81': 'Windows 8.1', 'win7': 'Windows 7',
        'server': 'Windows Server', 'office': 'Microsoft Office',
    }
    for cat, products in all_data.items():
        sys_name = cat_sys_names.get(cat, cat)
        versions = {}
        for p in products:
            ver = (p.get('version', '') or '').strip().lower()
            if not ver:
                continue
            rdate = p.get('releaseDate', '')
            if ver not in versions or rdate > versions[ver].get('releaseDate', ''):
                versions[ver] = {
                    'releaseDate': rdate,
                    'build': p.get('build', ''),
                    'arch': p.get('architecture', ''),
                }
        for ver, info in versions.items():
            key = f'{sys_name.lower().replace(" ", "_")}_{ver}'
            # 如果系统库API已有该版本追踪数据，保留它（包含innerVersion/patch等详细信息）
            if key in xtk_tracking:
                product_tracking[key] = xtk_tracking[key]
            else:
                entry = {
                    'systemName': sys_name,
                    'version': ver,
                    'innerVersion': '',
                    'patchVersion': '',
                    'updatedAt': info['releaseDate'],
                    'publishDate': info['releaseDate'],
                    'patch': '',
                }
                # 从 updatedAt 推导 latestPatchMonth
                updated_at = entry.get('updatedAt', '')
                if updated_at and re.match(r'\d{4}-\d{2}', updated_at):
                    entry['latestPatchMonth'] = updated_at[:7]
                product_tracking[key] = entry

    # 合并：以产品数据为主，用系统库API补充完整字段
    merged_tracking = dict(product_tracking)
    for key, xtk_entry in xtk_tracking.items():
        if key not in merged_tracking:
            merged_tracking[key] = xtk_entry
        else:
            for field in ('innerVersion', 'patchVersion', 'patch', 'updatedAt', 'publishDate', 'latestPatchMonth'):
                if xtk_entry.get(field) and not merged_tracking[key].get(field):
                    merged_tracking[key][field] = xtk_entry[field]

    # 为 tracking 条目添加对应的产品 ID（供首页直接链接，避免前端重复加载 JSON）
    cat_key_map = {
        'windows_11': 'win11', 'windows_10': 'win10', 'windows_8.1': 'win81',
        'windows_7': 'win7', 'windows_server': 'server', 'microsoft_office': 'office',
    }
    for key, entry in merged_tracking.items():
        cat = cat_key_map.get(key.rsplit('_', 1)[0] if '_' in key else '')
        ver = entry.get('version', '')
        if cat and ver:
            for p in all_data.get(cat, []):
                if p.get('version', '').lower() == ver.lower():
                    entry['productId'] = p['id']
                    break

    # 近30日更新数
    recent_count = 0
    try:
        thirty_days_ago = (NOW - timedelta(days=30)).strftime('%Y-%m-%d')
        recent_count = sum(
            1 for e in merged_tracking.values()
            if e.get('updatedAt', '') and e['updatedAt'] not in ('已停止服务', '')
            and e['updatedAt'] >= thirty_days_ago and e['updatedAt'] <= TODAY_STR
        )
    except Exception:
        pass

    meta = {
        'totalProducts': sum(len(all_data[cat]) for cat in CATS),
        'recentUpdates': recent_count,
        'lastUpdated': TODAY_STR,
        'lastUpdatedPrecise': NOW_BJ.strftime('%Y-%m-%d %H:%M:%S'),
        'categories': {cat: len(all_data[cat]) for cat in CATS},
        'sourceTracking': merged_tracking,
    }
    with open(os.path.join(DATA_DIR, 'meta.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f'\n爬取完成！总计 {meta["totalProducts"]} 个产品，已保存到 {DATA_DIR} 目录')

    # 动态生成 sitemap.xml（包含分类页和所有详情页）
    SITE_URL = 'https://517757.xyz'
    cat_pages = {
        'win11': 'pages/win11.html', 'win10': 'pages/win10.html',
        'win81': 'pages/win8.html', 'win7': 'pages/win7.html',
        'server': 'pages/server.html', 'office': 'pages/office.html',
    }
    sitemap_urls = [
        {'loc': f'{SITE_URL}/', 'priority': '1.0', 'changefreq': 'daily'},
        {'loc': f'{SITE_URL}/pages/guide.html', 'priority': '0.7', 'changefreq': 'monthly'},
    ]
    for cat, page in cat_pages.items():
        sitemap_urls.append({'loc': f'{SITE_URL}/{page}', 'priority': '0.9', 'changefreq': 'daily'})
    for cat in CATS:
        for p in all_data.get(cat, []):
            sitemap_urls.append({
                'loc': f'{SITE_URL}/pages/detail.html?id={p["id"]}&cat={cat}',
                'priority': '0.6', 'changefreq': 'weekly',
            })

    sitemap_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    sitemap_xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for u in sitemap_urls:
        sitemap_xml += f'  <url>\n    <loc>{u["loc"]}</loc>\n    <priority>{u["priority"]}</priority>\n    <changefreq>{u["changefreq"]}</changefreq>\n  </url>\n'
    sitemap_xml += '</urlset>'

    sitemap_path = os.path.join(DATA_DIR, '..', 'sitemap.xml')
    with open(sitemap_path, 'w', encoding='utf-8') as f:
        f.write(sitemap_xml)
    print(f'sitemap.xml 已生成，共 {len(sitemap_urls)} 个 URL')