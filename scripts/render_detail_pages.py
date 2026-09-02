#!/usr/bin/env python3
"""
SCM Pavilion 详情页静态化生成脚本
========================================
遍历 data/*.json 的全部产品，为每个产品生成静态详情页 pages/detail/<id>.html。

为什么需要静态化：
  原详情页 pages/detail.html 是单一模板，标题/描述/正文全部由 detail.js
  从 JSON 动态渲染。百度蜘蛛对纯 JS 渲染页面的收录质量不稳定（标题常常
  停留在通用的「资源详情 - SCM Pavilion」）。静态化后：
    - 每个详情页拥有独立的 <title> / <meta description> / JSON-LD Product 数据；
    - 下载链接、哈希校验码、版本信息全部写死在 HTML 中，蜘蛛无需执行 JS 即可读取。

渲染约定：
  - 页面结构与 js/detail.js 的输出保持一致（相同的 DOM 结构与 CSS 类名），
    保证静态页与原动态页视觉完全一致；
  - 静态页位于 pages/detail/ 目录，规范 URL 为 https://517757.xyz/pages/detail/<id>
    （托管平台自动把无后缀路径解析到 <id>.html）；
  - 生成文件为构建产物，已加入 .gitignore，由部署工作流在每次抓取后重新生成。

用法：python scripts/render_detail_pages.py
"""

import json
import os
import re
import sys
from html import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, 'data')
OUT_DIR = os.path.join(ROOT, 'pages', 'detail')
SITE_URL = 'https://517757.xyz'

# 分类配置：文件、展示名、分类页文件名、meta.json 追踪键前缀
CATEGORIES = {
    'win11':  {'file': 'win11.json',  'name': 'Windows 11',      'page': 'win11.html',  'track': 'windows_11'},
    'win10':  {'file': 'win10.json',  'name': 'Windows 10',      'page': 'win10.html',  'track': 'windows_10'},
    'win81':  {'file': 'win81.json',  'name': 'Windows 8.1',     'page': 'win8.html',   'track': 'windows_8.1'},
    'win7':   {'file': 'win7.json',   'name': 'Windows 7',       'page': 'win7.html',   'track': 'windows_7'},
    'server': {'file': 'server.json', 'name': 'Windows Server',  'page': 'server.html', 'track': 'windows_server'},
    'office': {'file': 'office.json', 'name': 'Microsoft Office', 'page': 'office.html', 'track': 'microsoft_office'},
}

SOURCE_CONFIG = {
    'HelloWindows': {'icon': 'fa-solid fa-globe',   'color': '#00d4ff', 'label': 'HelloWindows 下载'},
    '山己几子木':    {'icon': 'fa-solid fa-database', 'color': '#a855f7', 'label': '山己几子木 下载'},
    '系统库':        {'icon': 'fa-solid fa-server',  'color': '#f59e0b', 'label': '系统库 下载'},
}

LINK_ICONS = {
    'ed2k': 'fa-solid fa-plug',
    'magnet': 'fa-solid fa-magnet',
    'redirect': 'fa-solid fa-download',
}

PATCH_LABEL_URLS = {
    'win11': 'https://learn.microsoft.com/zh-cn/windows/release-health/windows11-release-information',
    'win10': 'https://learn.microsoft.com/zh-cn/windows/release-health/release-information',
    'server': 'https://learn.microsoft.com/zh-cn/windows/release-health/windows-server-release-info',
}

EDITION_BADGE = {
    'Professional': 'badge-cyan',
    'Enterprise': 'badge-purple',
    'Education': 'badge-blue',
    'Home': 'badge-green',
    'LTSC': 'badge-orange',
    'Datacenter': 'badge-purple',
    'Standard': 'badge-blue',
    'Pro for Workstations': 'badge-cyan',
}

ID_SAFE = re.compile(r'^[A-Za-z0-9_-]+$')


def esc(value):
    """HTML 转义（文本与属性通用）"""
    return escape('' if value is None else str(value), quote=True)


def fmt_date(value):
    """格式化日期，与 js/main.js formatDate 保持一致"""
    if not value:
        return '-'
    parts = str(value).replace('/', '-').split('-')
    if len(parts) >= 3:
        return '{}-{:0>2}-{:0>2}'.format(parts[0], parts[1], parts[2])
    return str(value)


def badge_class(edition):
    return EDITION_BADGE.get(edition or '', 'badge-cyan')


def smart_version_label(name, version):
    """生成版本标签，避免与产品名重复（如 "Windows 11 LTSC" + "LTSC 2024" -> " 2024"）。
    逻辑与 js/main.js 的 smartVersionLabel 保持一致：
      版本开头的连续分词只要已出现在名称末尾 4 个分词内，就去掉这部分，
      只显示未重叠的部分（"LTSC 2024" -> "2024"；"LTSC" -> ''），否则原样返回 " <version>"。
      例如："Windows 11 LTSC 消费版" + "LTSC" -> ''；"Windows 10 LTSC (x86)" + "LTSC 2019" -> " 2019"；
           "Microsoft Office 2016 专业版 消费版 (x86)" + "2016" -> ''。
    """
    if not version:
        return ''
    name_tokens = str(name).lower().split()
    ver_tokens = str(version).lower().split()
    m = len(ver_tokens)
    if m == 0:
        return ''
    k = 0
    while k < m and ver_tokens[k] in name_tokens[-4:]:
        k += 1
    if k == 0:
        return ' ' + str(version)
    rest = str(version).split()[k:]
    return (' ' + ' '.join(rest)) if rest else ''


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_patch_info(tracking, category, version):
    """从 meta.json sourceTracking 中查找产品补丁信息，与 detail.js 逻辑一致"""
    if not tracking:
        return None
    tkey = CATEGORIES[category]['track']
    lookup_key = '{}_{}'.format(tkey, (version or '').lower())
    t = tracking.get(lookup_key)
    if not t:
        return None
    return {
        'innerVersion': t.get('innerVersion', ''),
        'patchVersion': t.get('patchVersion', ''),
        'patch': t.get('patch', ''),
        'updatedAt': t.get('updatedAt', ''),
        'latestPatchMonth': t.get('latestPatchMonth', ''),
    }


def group_sources(product):
    """按来源（_source）分组下载链接，与 detail.js groupSourcesByWebsite 一致"""
    groups = {}
    for s in product.get('sources') or []:
        src = s.get('_source') or product.get('_source') or '其他'
        groups.setdefault(src, []).append(s)
    return groups


def source_list(product):
    """数据来源名列表（用于「数据来源」徽章）"""
    lst = product.get('_sources') or []
    if not lst:
        lst = list(dict.fromkeys(s.get('_source', '未知') for s in product.get('sources') or []))
    return lst


# ---------------------------------------------------------------- 页面片段

def build_info_grid(category, product, patch_info):
    items = []
    items.append(('版本名称', '<span class="info-value">{}</span>'.format(esc(product.get('name', '')))))
    items.append(('版本号', '<span class="info-value" style="font-family:var(--font-mono);">{}</span>'.format(esc(product.get('version') or '-'))))
    items.append(('Build 版本', '<span class="info-value" style="font-family:var(--font-mono);">{}</span>'.format(esc(product.get('build') or '-'))))

    if patch_info:
        url = PATCH_LABEL_URLS.get(category)
        if url:
            label = '<a href="{}" target="_blank" rel="noopener" style="color:#22c55e;font-weight:600;text-decoration:none;">微软最新补丁</a>'.format(esc(url))
        else:
            label = '<span style="color:#22c55e;font-weight:600;">微软最新补丁</span>'
        patch_value = patch_info['patch'] or (
            '{}.{}'.format(patch_info['innerVersion'], patch_info['patchVersion'])
            if patch_info['innerVersion'] else '暂无')
        value = ('<span class="info-value" style="font-family:var(--font-mono);color:var(--accent-green);">{}'
                 '<span style="color:var(--text-muted);font-size:0.75rem;margin-left:8px;">{}</span></span>'
                 .format(esc(patch_value), esc(patch_info['updatedAt'])))
        items.append((label, value))

    items.append(('版本类型', '<span class="info-value"><span class="badge {}">{}</span></span>'.format(
        badge_class(product.get('edition')), esc(product.get('edition') or product.get('sku') or '-'))))
    items.append(('SKU', '<span class="info-value" style="font-family:var(--font-mono);">{}</span>'.format(esc(product.get('sku') or '-'))))
    items.append(('语言', '<span class="info-value"><span class="badge badge-cyan">{}</span></span>'.format(esc(product.get('language') or '-'))))
    items.append(('架构', '<span class="info-value">{}</span>'.format(esc(product.get('architecture') or '-'))))
    items.append(('文件大小', '<span class="info-value" style="font-family:var(--font-mono);">{}</span>'.format(esc(product.get('fileSize') or '-'))))
    items.append(('发布日期', '<span class="info-value" style="font-family:var(--font-mono);">{}</span>'.format(fmt_date(product.get('releaseDate')))))

    badges = ''
    for s in source_list(product):
        cfg = SOURCE_CONFIG.get(s, {'icon': 'fa-solid fa-link', 'color': 'var(--text-muted)'})
        badges += ('<span class="badge" style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);'
                   'margin-right:6px;margin-bottom:4px;"><i class="{}" style="color:{};margin-right:4px;"></i>{}</span>'
                   .format(cfg['icon'], cfg['color'], esc(s)))
    items.append(('数据来源', '<span class="info-value">{}</span>'.format(badges)))

    rows = ''.join(
        '<div class="info-item">\n          <span class="info-label">{}</span>\n          {}\n        </div>'.format(label, value)
        for label, value in items)
    return ('<div class="info-section">\n      <div class="info-grid">\n        {}\n      </div>\n    </div>'
            .format(rows))


def build_hash_section(product):
    hashes = product.get('hashes') or {}
    blocks = ''
    for algo, key in (('SHA-1', 'sha1'), ('SHA-256', 'sha256'), ('MD5', 'md5')):
        if hashes.get(key):
            blocks += ('<div class="hash-item">\n        <div class="hash-label"><i class="fas fa-tag"></i> {}</div>\n'
                       '        <div class="code-block">\n          <button class="copy-btn">复制</button>\n          {}\n        </div>\n      </div>'
                       .format(algo, esc(hashes[key])))
    if not blocks:
        return ''
    return ('<div class="info-section">\n      <h2 class="section-subtitle"><i class="fas fa-fingerprint"></i> 哈希校验码</h2>\n'
            '<p style="color:var(--text-muted);font-size:0.875rem;margin-bottom:16px;">'
            '下载完成后，请务必使用校验工具比对以下哈希值，确保文件完整且未被篡改。</p>\n      {}\n    </div>'
            .format(blocks))


def build_download_section(product, patch_info):
    groups = group_sources(product)
    html = ''
    if groups:
        for src_name, links in groups.items():
            cfg = SOURCE_CONFIG.get(src_name, {'icon': 'fa-solid fa-link', 'color': 'var(--text-muted)', 'label': src_name})
            xtk_ver = ''
            if src_name == '系统库' and patch_info and patch_info['innerVersion']:
                xtk_ver = ('{}.{}'.format(patch_info['innerVersion'], patch_info['patchVersion'])
                           if patch_info['patchVersion'] else str(patch_info['innerVersion']))
            xtk_html = ('<span style="font-size:0.75rem;color:#22c55e;font-weight:500;font-family:var(--font-mono);">{}</span>'
                        .format(esc(xtk_ver))) if xtk_ver else ''
            links_html = ''
            for s in links:
                icon = LINK_ICONS.get(s.get('type'), 'fa-solid fa-link')
                links_html += ('<a href="{}" target="_blank" rel="noopener" class="btn btn-outline" '
                               'style="display:flex;align-items:center;gap:8px;padding:10px 16px;font-size:0.8125rem;border-radius:8px;">'
                               '<i class="{}" style="font-size:0.875rem;color:{};"></i>'
                               '<span>{}</span>'
                               '<i class="fa-solid fa-up-right-from-square" style="margin-left:auto;font-size:0.6875rem;opacity:0.4;"></i></a>'
                               .format(esc(s.get('url', '')), icon, cfg['color'], esc(s.get('name', ''))))
            html += ('<div class="source-group" style="margin-bottom:20px;">\n'
                     '          <div class="source-group-header" style="display:flex;align-items:center;gap:10px;margin-bottom:12px;'
                     'padding:10px 16px;background:rgba(255,255,255,0.02);border-radius:10px;border:1px solid rgba(255,255,255,0.04);">\n'
                     '            <i class="{}" style="color:{};font-size:1.125rem;"></i>\n'
                     '            <span style="font-weight:600;font-size:0.9375rem;color:var(--text-primary);">{}</span>\n'
                     '            {}\n'
                     '            <span style="margin-left:auto;font-size:0.75rem;color:var(--text-muted);font-family:var(--font-mono);">{} 个链接</span>\n'
                     '          </div>\n'
                     '          <div class="download-links" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:8px;">\n'
                     '            {}\n'
                     '          </div>\n'
                     '        </div>'
                     .format(cfg['icon'], cfg['color'], esc(cfg['label']), xtk_html, len(links), links_html))
    else:
        html = '<p style="color:var(--text-muted);">暂无可用下载链接</p>'
    return ('<div class="info-section">\n      <h2 class="section-subtitle"><i class="fas fa-download"></i> 下载链接</h2>\n'
            '<p style="color:var(--text-muted);font-size:0.875rem;margin-bottom:16px;">'
            '以下链接来自多个第三方镜像站点，均为原版文件，已按来源分类展示。下载后请校验哈希值。</p>\n      {}\n    </div>'
            .format(html))


def build_notice_section():
    return ('<div class="info-section">\n      <div class="alert alert-warning">\n'
            '        <strong><i class="fas fa-shield-halved"></i> 安全提示：</strong>\n'
            '        请务必在下载完成后使用 <code style="background:rgba(0,0,0,0.2);padding:2px 6px;border-radius:2px;font-family:var(--font-mono);">'
            'certutil -hashfile 文件名 SHA1</code> \n'
            '        或 <code style="background:rgba(0,0,0,0.2);padding:2px 6px;border-radius:2px;font-family:var(--font-mono);">'
            'Get-FileHash 文件名 -Algorithm SHA256</code> \n'
            '        命令验证哈希值。如哈希值不匹配，请勿安装使用。\n'
            '      </div>\n    </div>')


NAV_HTML = '''
  <nav class="nav">
    <div class="nav-inner">
      <a href="../../index.html" class="nav-brand">
        <div class="nav-brand-icon">S</div>
        <span>SCM Pavilion<small style="display:block;font-size:0.625rem;font-weight:400;opacity:0.5;margin-top:2px;">SeaCloud Mirror Pavilion</small></span>
      </a>
      <button class="nav-toggle" aria-label="菜单"><i class="fas fa-bars"></i></button>
      <ul class="nav-links">
        <li><a href="../../index.html">首页</a></li>
        <li><a href="../win11.html">Win11</a></li>
        <li><a href="../win10.html">Win10</a></li>
        <li><a href="../win8.html">Win8.1</a></li>
        <li><a href="../win7.html">Win7</a></li>
        <li><a href="../server.html">Server</a></li>
        <li><a href="../office.html">Office</a></li>
        <li><a href="../guide.html">教程</a></li>
      </ul>
    </div>
  </nav>
'''

FOOTER_HTML = '''
  <footer class="footer">
    <div class="container">
      <div class="footer-grid">
        <div>
          <div class="footer-brand">
            <span>SCM Pavilion</span>
            <small style="display:block;font-size:0.75rem;font-weight:400;opacity:0.45;margin-top:4px;">SeaCloud Mirror Pavilion · 海云典藏镜像</small>
          </div>
          <p class="footer-desc">第三方微软原版系统镜像索引站，致力于为装机用户提供纯净、安全、可追溯的下载资源。本站不存储任何镜像文件，仅做资源整理与索引。</p>
        </div>
        <div>
          <div class="footer-heading">系统分类</div>
          <ul class="footer-links">
            <li><a href="../win11.html">Windows 11</a></li>
            <li><a href="../win10.html">Windows 10</a></li>
            <li><a href="../win8.html">Windows 8.1</a></li>
            <li><a href="../win7.html">Windows 7</a></li>
          </ul>
        </div>
        <div>
          <div class="footer-heading">更多资源</div>
          <ul class="footer-links">
            <li><a href="../server.html">Windows Server</a></li>
            <li><a href="../office.html">Microsoft Office</a></li>
            <li><a href="../guide.html">安装教程</a></li>
          </ul>
        </div>
        <div>
          <div class="footer-heading">数据来源</div>
          <ul class="footer-links">
            <li><a href="https://hellowindows.cn/" target="_blank" rel="noopener">HelloWindows</a></li>
            <li><a href="https://www.xitongku.com/" target="_blank" rel="noopener">系统库</a></li>
            <li><a href="https://msdn.sjjzm.com/" target="_blank" rel="noopener">山己几子木</a></li>
          </ul>
        </div>
      </div>
      <div class="footer-bottom">
        <p>&copy; 2026 SCM Pavilion. 正版提示：Windows/Office 为微软商业软件，请购买正版授权合法激活。</p>
        <div class="footer-source-links">
          <a href="https://hellowindows.cn/" target="_blank" rel="noopener">HelloWindows</a>
          <a href="https://www.xitongku.com/" target="_blank" rel="noopener">系统库</a>
          <a href="https://msdn.sjjzm.com/" target="_blank" rel="noopener">山己几子木</a>
        </div>
      </div>
    </div>
  </footer>
'''


def render_page_html(category, product, patch_info):
    """生成单个产品的完整静态详情页 HTML（与 detail.js 渲染结构一致）"""
    cat_cfg = CATEGORIES[category]
    version_label = smart_version_label(product.get('name', ''), product.get('version', ''))
    full_name = '{}{}'.format(product.get('name', ''), version_label)
    title = '{} 下载 - SCM Pavilion'.format(full_name)
    description = '{} 原版镜像下载，包含 SHA-1/SHA-256 校验码，纯净无捆绑。'.format(full_name)
    page_url = '{}/pages/detail/{}'.format(SITE_URL, product['id'])

    jsonld = json.dumps({
        '@context': 'https://schema.org',
        '@type': 'Product',
        'name': full_name,
        'description': '{} 原版系统镜像下载'.format(full_name),
        'url': page_url,
        'category': category,
    }, ensure_ascii=False)

    info_grid = build_info_grid(category, product, patch_info)
    hash_section = build_hash_section(product)
    download_section = build_download_section(product, patch_info)
    notice_section = build_notice_section()

    return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="{description}">
  <title>{title}</title>
  <script type="application/ld+json">
  {jsonld}
  </script>
  <link rel="icon" href="../../assets/favicon.ico" type="image/x-icon">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800&family=Noto+Sans+SC:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
  <link rel="stylesheet" href="../../css/style.css?v=3">
  <link rel="stylesheet" href="../../css/detail.css?v=3">
</head>
<body>{nav}
  <section class="page-hero">
    <div class="container">
      <div style="max-width:860px;margin:0 auto;">
        <a href="../{cat_page}" class="back-link">
          <i class="fas fa-arrow-left"></i> 返回分类
        </a>
        <div class="breadcrumb">
          <a href="../../index.html">首页</a>
          <span class="sep">/</span>
          <a href="../{cat_page}">{cat_name}</a>
          <span class="sep">/</span>
          <span>{product_name}</span>
        </div>
      </div>
      <div id="detail-content" class="detail-content page-enter">
        {info_grid}

        {hash_section}

        {download_section}

        {notice_section}
      </div>
    </div>
  </section>{footer}
  <script src="../../js/main.js?v=5"></script>
</body>
</html>'''.format(
        description=esc(description),
        title=esc(title),
        jsonld=jsonld,
        nav=NAV_HTML,
        cat_page=cat_cfg['page'],
        cat_name=esc(cat_cfg['name']),
        product_name=esc(product.get('name', '')),
        info_grid=info_grid,
        hash_section=hash_section,
        download_section=download_section,
        notice_section=notice_section,
        footer=FOOTER_HTML,
    )


def main():
    meta_path = os.path.join(DATA_DIR, 'meta.json')
    tracking = load_json(meta_path).get('sourceTracking') if os.path.exists(meta_path) else None

    os.makedirs(OUT_DIR, exist_ok=True)
    generated = 0
    skipped = 0
    per_cat = {}

    for category, cfg in CATEGORIES.items():
        path = os.path.join(DATA_DIR, cfg['file'])
        if not os.path.exists(path):
            print('[跳过] 数据文件不存在: {}'.format(cfg['file']))
            continue
        data = load_json(path)
        products = data.get('products') or []
        per_cat[category] = len(products)
        for p in products:
            pid = p.get('id', '')
            if not ID_SAFE.match(pid):
                print('[警告] 跳过非法产品 ID: {} ({})'.format(repr(pid), p.get('name', '')))
                skipped += 1
                continue
            patch_info = get_patch_info(tracking, category, p.get('version', ''))
            html = render_page_html(category, p, patch_info)
            out_path = os.path.join(OUT_DIR, '{}.html'.format(pid))
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(html)
            generated += 1

    # 汇总 + 与 meta.json 统计核对
    print('\n静态详情页生成完成：')
    for cat, count in per_cat.items():
        print('  {}: {} 页'.format(CATEGORIES[cat]['name'], count))
    print('共生成 {} 页，跳过 {} 个非法 ID'.format(generated, skipped))

    if tracking is None:
        print('[警告] meta.json 不存在，补丁信息将缺失（不影响页面生成）')
    meta = load_json(meta_path) if os.path.exists(meta_path) else {}
    expected = meta.get('categories')
    if expected and expected != per_cat:
        print('[警告] 各类产品数量与 meta.json 不一致：生成 {} vs meta {}'.format(per_cat, expected))
    if expected:
        total = sum(expected.values())
        if generated != total:
            print('[警告] 生成总数 {} 与 meta.json 总数 {} 不一致'.format(generated, total))

    return 0


if __name__ == '__main__':
    sys.exit(main())