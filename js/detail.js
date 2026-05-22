document.addEventListener('DOMContentLoaded', async () => {
  const params = new URLSearchParams(window.location.search);
  const productId = params.get('id');
  const category = params.get('cat') || 'win11';

  if (!productId) {
    document.getElementById('detail-content').innerHTML = `
      <div style="text-align:center;padding:80px 20px;color:var(--text-muted);">
        <i class="fas fa-exclamation-triangle" style="font-size:3rem;display:block;margin-bottom:16px;opacity:0.5;"></i>
        <p style="font-size:1.125rem;">未指定资源 ID</p>
        <a href="../index.html" class="btn btn-primary" style="margin-top:24px;">返回首页</a>
      </div>`;
    return;
  }

  const data = await loadData(category);
  if (!data || !data.products) {
    document.getElementById('detail-content').innerHTML = `
      <div style="text-align:center;padding:80px 20px;color:var(--text-muted);">
        <i class="fas fa-database" style="font-size:3rem;display:block;margin-bottom:16px;opacity:0.5;"></i>
        <p style="font-size:1.125rem;">数据加载失败</p>
        <a href="../index.html" class="btn btn-primary" style="margin-top:24px;">返回首页</a>
      </div>`;
    return;
  }

  const product = data.products.find(p => p.id === productId);
  if (!product) {
    document.getElementById('detail-content').innerHTML = `
      <div style="text-align:center;padding:80px 20px;color:var(--text-muted);">
        <i class="fas fa-search" style="font-size:3rem;display:block;margin-bottom:16px;opacity:0.5;"></i>
        <p style="font-size:1.125rem;">未找到该资源</p>
        <a href="../index.html" class="btn btn-primary" style="margin-top:24px;">返回首页</a>
      </div>`;
    return;
  }

  // 加载 meta.json 获取追踪数据
  let tracking = null;
  try {
    const metaResp = await fetch('../data/meta.json');
    const meta = await metaResp.json();
    tracking = meta.sourceTracking || null;
  } catch (e) {}

  renderDetail(product, category, tracking);
});

const SOURCE_CONFIG = {
  'HelloWindows': { icon: 'fa-solid fa-globe', color: '#00d4ff', label: 'HelloWindows 下载' },
  '山己几子木': { icon: 'fa-solid fa-database', color: '#a855f7', label: '山己几子木 下载' },
  '系统库': { icon: 'fa-solid fa-server', color: '#f59e0b', label: '系统库 下载' },
};

function groupSourcesByWebsite(sources, fallbackSource) {
  const groups = {};
  for (const s of sources) {
    const src = s._source || fallbackSource || '其他';
    if (!groups[src]) groups[src] = [];
    groups[src].push(s);
  }
  return groups;
}

function renderDetail(product, category, tracking) {
  const versionLabel = product.version ? ` ${product.version}` : '';
  document.title = `${product.name}${versionLabel} 下载 - SCM Pavilion`;

  const categoryNames = {
    win11: 'Windows 11', win10: 'Windows 10', win81: 'Windows 8.1',
    win7: 'Windows 7', server: 'Windows Server', office: 'Microsoft Office'
  };
  const categoryLinks = {
    win11: 'win11.html', win10: 'win10.html', win81: 'win8.html',
    win7: 'win7.html', server: 'server.html', office: 'office.html'
  };

  document.getElementById('breadcrumb-category').textContent = categoryNames[category] || category;
  document.getElementById('breadcrumb-category').href = categoryLinks[category] || 'index.html';

  const container = document.getElementById('detail-content');

  const sourceGroups = groupSourcesByWebsite(product.sources || [], product._source);
  const sourceEntries = Object.entries(sourceGroups);

  let sourcesHtml = '';
  if (sourceEntries.length > 0) {
    for (const [srcName, links] of sourceEntries) {
      const cfg = SOURCE_CONFIG[srcName] || { icon: 'fa-solid fa-link', color: 'var(--text-muted)', label: srcName };
      let linkIcons = { ed2k: 'fa-solid fa-plug', magnet: 'fa-solid fa-magnet', 'redirect': 'fa-solid fa-download' };
      sourcesHtml += `
        <div class="source-group" style="margin-bottom:20px;">
          <div class="source-group-header" style="display:flex;align-items:center;gap:10px;margin-bottom:12px;padding:10px 16px;background:rgba(255,255,255,0.02);border-radius:10px;border:1px solid rgba(255,255,255,0.04);">
            <i class="${cfg.icon}" style="color:${cfg.color};font-size:1.125rem;"></i>
            <span style="font-weight:600;font-size:0.9375rem;color:var(--text-primary);">${cfg.label}</span>
            <span style="margin-left:auto;font-size:0.75rem;color:var(--text-muted);font-family:var(--font-mono);">${links.length} 个链接</span>
          </div>
          <div class="download-links" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:8px;">
            ${links.map(s => {
              const icon = linkIcons[s.type] || 'fa-solid fa-link';
              return `<a href="${s.url}" target="_blank" rel="noopener" class="btn btn-outline" style="display:flex;align-items:center;gap:8px;padding:10px 16px;font-size:0.8125rem;border-radius:8px;">
                <i class="${icon}" style="font-size:0.875rem;color:${cfg.color};"></i>
                <span>${s.name}</span>
                <i class="fa-solid fa-up-right-from-square" style="margin-left:auto;font-size:0.6875rem;opacity:0.4;"></i>
              </a>`;
            }).join('')}
          </div>
        </div>`;
    }
  } else {
    sourcesHtml = '<p style="color:var(--text-muted);">暂无可用下载链接</p>';
  }

  const sourcesList = product._sources || (product.sources ? [...new Set(product.sources.map(s => s._source || '未知'))] : []);

  // 从追踪数据中查找当前产品的补丁信息
  const catVersion = product.version || '';
  let patchInfo = null;
  if (tracking) {
    const trackingKeyMap = { win11: 'windows_11', win10: 'windows_10' };
    const tKey = trackingKeyMap[category];
    if (tKey && catVersion && tracking) {
      const lookupKey = `${tKey}_${catVersion.toLowerCase()}`;
      const t = tracking[lookupKey];
      if (t) {
        patchInfo = {
          innerVersion: t.innerVersion || '',
          patchVersion: t.patchVersion || '',
          patch: t.patch || '',
          updatedAt: t.updatedAt || '',
        };
      }
    }
  }

  container.innerHTML = `
    <!-- Basic Info -->
    <div class="info-section">
      <div class="info-grid">
        <div class="info-item">
          <span class="info-label">版本名称</span>
          <span class="info-value">${product.name}</span>
        </div>
        <div class="info-item">
          <span class="info-label">版本号</span>
          <span class="info-value" style="font-family:var(--font-mono);">${product.version || '-'}</span>
        </div>
        <div class="info-item">
          <span class="info-label">Build 版本</span>
          <span class="info-value" style="font-family:var(--font-mono);">${product.build || '-'}</span>
        </div>
        ${patchInfo ? `
        <div class="info-item">
          <span class="info-label">最新补丁</span>
          <span class="info-value" style="font-family:var(--font-mono);color:var(--accent-green);">
            ${patchInfo.patch || `${patchInfo.innerVersion}.${patchInfo.patchVersion}`}
            <span style="color:var(--text-muted);font-size:0.75rem;margin-left:8px;">${patchInfo.updatedAt}</span>
          </span>
        </div>` : ''}
        <div class="info-item">
          <span class="info-label">版本类型</span>
          <span class="info-value"><span class="badge ${getEditionBadgeClass(product.edition)}">${product.edition || product.sku || '-'}</span></span>
        </div>
        <div class="info-item">
          <span class="info-label">SKU</span>
          <span class="info-value" style="font-family:var(--font-mono);">${product.sku || '-'}</span>
        </div>
        <div class="info-item">
          <span class="info-label">语言</span>
          <span class="info-value"><span class="badge badge-cyan">${product.language || '-'}</span></span>
        </div>
        <div class="info-item">
          <span class="info-label">架构</span>
          <span class="info-value">${product.architecture || '-'}</span>
        </div>
        <div class="info-item">
          <span class="info-label">文件大小</span>
          <span class="info-value" style="font-family:var(--font-mono);">${product.fileSize || '-'}</span>
        </div>
        <div class="info-item">
          <span class="info-label">发布日期</span>
          <span class="info-value" style="font-family:var(--font-mono);">${formatDate(product.releaseDate)}</span>
        </div>
        <div class="info-item">
          <span class="info-label">数据来源</span>
          <span class="info-value">
            ${sourcesList.map(s => {
              const cfg = SOURCE_CONFIG[s] || { icon: 'fa-solid fa-link', color: 'var(--text-muted)' };
              return `<span class="badge" style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);margin-right:6px;margin-bottom:4px;"><i class="${cfg.icon}" style="color:${cfg.color};margin-right:4px;"></i>${s}</span>`;
            }).join('')}
          </span>
        </div>
      </div>
    </div>

    <!-- Hash Verification -->
    <div class="info-section">
      <h2 class="section-subtitle"><i class="fas fa-fingerprint"></i> 哈希校验码</h2>
      <p style="color:var(--text-muted);font-size:0.875rem;margin-bottom:16px;">
        下载完成后，请务必使用校验工具比对以下哈希值，确保文件完整且未被篡改。
      </p>

      ${product.hashes && product.hashes.sha1 ? `
      <div class="hash-item">
        <div class="hash-label"><i class="fas fa-tag"></i> SHA-1</div>
        <div class="code-block">
          <button class="copy-btn">复制</button>
          ${product.hashes.sha1}
        </div>
      </div>` : ''}

      ${product.hashes && product.hashes.sha256 ? `
      <div class="hash-item">
        <div class="hash-label"><i class="fas fa-tag"></i> SHA-256</div>
        <div class="code-block">
          <button class="copy-btn">复制</button>
          ${product.hashes.sha256}
        </div>
      </div>` : ''}

      ${product.hashes && product.hashes.md5 ? `
      <div class="hash-item">
        <div class="hash-label"><i class="fas fa-tag"></i> MD5</div>
        <div class="code-block">
          <button class="copy-btn">复制</button>
          ${product.hashes.md5}
        </div>
      </div>` : ''}
    </div>

    <!-- Download -->
    <div class="info-section">
      <h2 class="section-subtitle"><i class="fas fa-download"></i> 下载链接</h2>
      <p style="color:var(--text-muted);font-size:0.875rem;margin-bottom:16px;">
        以下链接来自多个第三方镜像站点，均为原版文件，已按来源分类展示。下载后请校验哈希值。
      </p>
      ${sourcesHtml}
    </div>

    <!-- Verification Notice -->
    <div class="info-section">
      <div class="alert alert-warning">
        <strong><i class="fas fa-shield-halved"></i> 安全提示：</strong>
        请务必在下载完成后使用 <code style="background:rgba(0,0,0,0.2);padding:2px 6px;border-radius:2px;font-family:var(--font-mono);">certutil -hashfile 文件名 SHA1</code> 
        或 <code style="background:rgba(0,0,0,0.2);padding:2px 6px;border-radius:2px;font-family:var(--font-mono);">Get-FileHash 文件名 -Algorithm SHA256</code> 
        命令验证哈希值。如哈希值不匹配，请勿安装使用。
      </div>
    </div>
  `;

  setupCopyButtons();
}
