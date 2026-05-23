document.addEventListener('DOMContentLoaded', () => {
  initParticles();
  loadMetaStats();
  loadLatestResources();
  initSupportModal();
});

async function loadMetaStats() {
  const container = document.getElementById('hero-stats');
  if (!container) return;
  try {
    const resp = await fetch('data/meta.json');
    const meta = await resp.json();
    const catNames = {
      win11: 'Win11', win10: 'Win10', win81: 'Win8.1',
      win7: 'Win7', server: 'Server', office: 'Office',
    };
    const catIcons = {
      win11: 'fa-brands fa-windows', win10: 'fa-brands fa-windows', win81: 'fa-brands fa-windows',
      win7: 'fa-brands fa-windows', server: 'fa-solid fa-server', office: 'fa-brands fa-microsoft',
    };
    const catColors = {
      win11: '#00d4ff', win10: '#3b82f6', win81: '#7c3aed',
      win7: '#a855f7', server: '#f59e0b', office: '#10b981',
    };
    let html = '';
    // 总计 + 今日更新
    html += `<div class="hero-stat highlight">
      <i class="fa-solid fa-database"></i>
      <span><span class="stat-value">${meta.totalProducts}</span> <span class="stat-label">个版本</span></span>
    </div>`;
    html += `<div class="hero-stat">
      <i class="fa-solid fa-calendar-day"></i>
      <span><span class="stat-value">${meta.todayUpdates || 0}</span> <span class="stat-label">今日更新</span></span>
    </div>`;
    html += `<div class="hero-stat">
      <i class="fa-solid fa-clock"></i>
      <span class="stat-label">${meta.lastUpdated || '-'}</span>
    </div>`;
    // 各分类数量
    if (meta.categories) {
      for (const [cat, count] of Object.entries(meta.categories)) {
        const name = catNames[cat] || cat;
        const icon = catIcons[cat] || 'fa-brands fa-windows';
        const color = catColors[cat] || 'var(--accent-cyan)';
        html += `<div class="hero-stat">
          <i class="${icon}" style="color:${color}"></i>
          <span><span class="stat-value">${count}</span> <span class="stat-label">${name}</span></span>
        </div>`;
      }
    }
    container.innerHTML = html;

    // 填充分类卡片中的数量徽章
    if (meta.categories) {
      for (const [cat, count] of Object.entries(meta.categories)) {
        const badge = document.getElementById(`cat-count-${cat}`);
        if (badge) {
          badge.innerHTML = `<i class="fa-solid fa-layer-group"></i> ${count}`;
        }
      }
    }

    // 如果存在来源追踪数据，更新"数据来源更新时间"显示
    if (meta.sourceLastUpdated) {
      const timeEl = document.querySelector('.hero-stat i.fa-clock');
      if (timeEl) {
        const parent = timeEl.closest('.hero-stat');
        if (parent) {
          parent.innerHTML = `<i class="fa-solid fa-clock"></i><span class="stat-label">来源更新: ${meta.sourceLastUpdated}</span>`;
        }
      }
    }

    // 显示各系统最新构建版本（从 tracking 数据取）
    if (meta.sourceTracking) {
      const trackingInfo = meta.sourceTracking;
      const systemBuilds = {};
      const latestBuilds = [];
      const trackIcons = {
        'Windows 11': 'fa-brands fa-windows',
        'Windows 10': 'fa-brands fa-windows',
        'Windows Server 2025': 'fa-solid fa-server',
        'Windows Server 2022': 'fa-solid fa-server',
      };
      const trackColors = {
        'Windows 11': '#00d4ff',
        'Windows 10': '#3b82f6',
        'Windows Server 2025': '#f59e0b',
        'Windows Server 2022': '#f59e0b',
      };

      // 遍历所有 tracking 条目，按系统名分组，取最新版本
      for (const [key, info] of Object.entries(trackingInfo)) {
        const sysName = info.systemName;
        if (!sysName) continue;
        const existing = systemBuilds[sysName];
        if (!existing || (info.innerVersion || 0) > (existing.innerVersion || 0)) {
          systemBuilds[sysName] = info;
        }
      }

      for (const [sysName, info] of Object.entries(systemBuilds)) {
        const version = info.version || '';
        const innerVer = info.innerVersion || '';
        const patchVer = info.patchVersion || '';
        const updatedAt = info.updatedAt || '';
        const patch = info.patch || '';
        let buildStr = '';
        if (innerVer) buildStr += innerVer;
        if (patchVer) buildStr += `.${patchVer}`;
        if (!buildStr) continue;
        const icon = trackIcons[sysName] || 'fa-brands fa-windows';
        const color = trackColors[sysName] || 'var(--accent-cyan)';
        const verDisplay = version ? `${version} ` : '';
        const patchDisplay = patch ? `（${patch}）` : '';
        latestBuilds.push(`
          <div class="hero-stat" title="来自系统库版本追踪：该版本已包含累计更新补丁后的完整版本号，与实际可下载的ISO版本可能存在差异">
            <i class="${icon}" style="color:${color}"></i>
            <span>
              <span class="stat-label">${sysName}:</span>
              <span class="stat-value">${verDisplay}(Build ${buildStr})</span>
              <span class="stat-label"> 最新补丁: </span><span class="stat-patch">${updatedAt}${patchDisplay}</span>
            </span>
          </div>
        `);
      }
      if (latestBuilds.length > 0) {
        const statsContainer = document.getElementById('hero-stats');
        if (statsContainer) {
          statsContainer.insertAdjacentHTML('afterbegin', latestBuilds.join(''));
        }
      }
    }
  } catch (e) {
    container.innerHTML = `<div class="hero-stat"><i class="fa-solid fa-triangle-exclamation" style="color:var(--accent-orange)"></i><span class="stat-label">数据加载失败</span></div>`;
  }
}

function initParticles() {
  const canvas = document.getElementById('particle-canvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  let particles = [];
  let animationId;
  let mouseX = 0;
  let mouseY = 0;

  function resize() {
    canvas.width = canvas.parentElement.offsetWidth;
    canvas.height = canvas.parentElement.offsetHeight;
  }

  function createParticles() {
    const count = Math.floor((canvas.width * canvas.height) / 15000);
    particles = [];
    for (let i = 0; i < count; i++) {
      particles.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        vx: (Math.random() - 0.5) * 0.5,
        vy: (Math.random() - 0.5) * 0.5,
        r: Math.random() * 1.5 + 0.5,
        opacity: Math.random() * 0.5 + 0.2
      });
    }
  }

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    for (let i = 0; i < particles.length; i++) {
      const p = particles[i];
      p.x += p.vx;
      p.y += p.vy;

      if (p.x < 0) p.x = canvas.width;
      if (p.x > canvas.width) p.x = 0;
      if (p.y < 0) p.y = canvas.height;
      if (p.y > canvas.height) p.y = 0;

      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(0, 212, 255, ${p.opacity})`;
      ctx.fill();

      for (let j = i + 1; j < particles.length; j++) {
        const p2 = particles[j];
        const dx = p.x - p2.x;
        const dy = p.y - p2.y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist < 120) {
          ctx.beginPath();
          ctx.moveTo(p.x, p.y);
          ctx.lineTo(p2.x, p2.y);
          ctx.strokeStyle = `rgba(0, 212, 255, ${0.08 * (1 - dist / 120)})`;
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
      }

      const dxm = p.x - mouseX;
      const dym = p.y - mouseY;
      const distM = Math.sqrt(dxm * dxm + dym * dym);
      if (distM < 160) {
        ctx.beginPath();
        ctx.moveTo(p.x, p.y);
        ctx.lineTo(mouseX, mouseY);
        ctx.strokeStyle = `rgba(0, 212, 255, ${0.04 * (1 - distM / 160)})`;
        ctx.lineWidth = 0.5;
        ctx.stroke();
      }
    }

    animationId = requestAnimationFrame(draw);
  }

  canvas.addEventListener('mousemove', (e) => {
    const rect = canvas.getBoundingClientRect();
    mouseX = e.clientX - rect.left;
    mouseY = e.clientY - rect.top;
  });

  canvas.addEventListener('mouseleave', () => {
    mouseX = -9999;
    mouseY = -9999;
  });

  resize();
  createParticles();
  draw();

  window.addEventListener('resize', () => {
    resize();
    createParticles();
  });
}

async function loadLatestResources() {
  const container = document.getElementById('latest-list');
  if (!container) return;

  const categories = ['win11', 'win10', 'win81', 'win7', 'server', 'office'];
  const allProducts = [];
  const icons = {
    win11: ['fab fa-windows', 'Windows 11'],
    win10: ['fab fa-windows', 'Windows 10'],
    win81: ['fab fa-windows', 'Windows 8.1'],
    win7: ['fab fa-windows', 'Windows 7'],
    server: ['fas fa-server', 'Windows Server'],
    office: ['fab fa-microsoft', 'Microsoft Office']
  };

  for (const cat of categories) {
    const data = await loadData(cat);
    if (data && data.products) {
      data.products.forEach(p => {
        allProducts.push({ ...p, _cat: cat, _icon: icons[cat] });
      });
    }
  }

  allProducts.sort((a, b) => {
    if (a.releaseDate < b.releaseDate) return 1;
    if (a.releaseDate > b.releaseDate) return -1;
    return 0;
  });

  const latest = allProducts.slice(0, 6);

  if (latest.length === 0) {
    const isFileProtocol = window.location.protocol === 'file:';
    container.innerHTML = `<div style="grid-column:1/-1;text-align:center;padding:60px 20px;color:var(--text-muted);font-family:var(--font-mono);font-size:0.875rem;">
      <i class="fas fa-database" style="font-size:2.5rem;display:block;margin-bottom:16px;opacity:0.5;"></i>
      <p style="color:var(--text-secondary);margin-bottom:8px;font-family:var(--font-sans);font-size:1rem;">${
        isFileProtocol ? '无法加载数据' : '暂无数据'
      }</p>
      <p style="color:var(--text-muted);margin-bottom:16px;">${
        isFileProtocol
          ? '请通过 HTTP 服务器访问网站，而非直接打开 HTML 文件'
          : '数据文件缺失，请运行 python scripts/scraper.py 抓取数据'
      }</p>
      ${isFileProtocol ? '<div style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:8px;padding:12px 20px;display:inline-block;"><code style="color:var(--accent-cyan);font-size:0.8125rem;">python -m http.server 8080</code></div>' : ''}
    </div>`;
    return;
  }

  container.innerHTML = latest.map(p => {
    const icon = p._icon || ['fab fa-windows', 'Windows'];
    return `<a href="pages/detail.html?id=${p.id}&cat=${p._cat}" class="latest-card glass-card">
      <div class="latest-icon"><i class="${icon[0]}"></i></div>
      <div class="latest-info">
        <div class="latest-name">${p.name} ${p.version ? '(' + p.version + ')' : ''}</div>
        <div class="latest-meta">
          <span><i class="fas fa-tag"></i>${p.edition || p.sku || '-'}</span>
          <span><i class="fas fa-calendar"></i>${formatDate(p.releaseDate)}</span>
        </div>
      </div>
      <span class="latest-link">查看详情 <i class="fas fa-arrow-right"></i></span>
    </a>`;
  }).join('');
}

function initSupportModal() {
  const btn = document.getElementById('supportBtn');
  const modal = document.getElementById('supportModal');
  const overlay = document.getElementById('supportOverlay');
  const closeBtn = document.getElementById('supportModalClose');
  if (!btn || !modal || !overlay || !closeBtn) return;

  function openModal() {
    modal.classList.add('active');
    overlay.classList.add('active');
    document.body.style.overflow = 'hidden';
  }

  function closeModal() {
    modal.classList.remove('active');
    overlay.classList.remove('active');
    document.body.style.overflow = '';
  }

  btn.addEventListener('click', openModal);
  closeBtn.addEventListener('click', closeModal);
  overlay.addEventListener('click', closeModal);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
  });
}
