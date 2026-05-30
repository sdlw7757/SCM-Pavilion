document.addEventListener('DOMContentLoaded', () => {
  const category = document.body.dataset.category || 'win11';
  const categoryNames = {
    win11: ['Windows 11', 'fab fa-windows'],
    win10: ['Windows 10', 'fab fa-windows'],
    win81: ['Windows 8.1', 'fab fa-windows'],
    win7: ['Windows 7', 'fab fa-windows'],
    server: ['Windows Server', 'fas fa-server'],
    office: ['Microsoft Office', 'fab fa-microsoft']
  };

  const [catName, catIcon] = categoryNames[category] || ['Windows', 'fab fa-windows'];

  document.getElementById('category-title').textContent = catName;
  document.getElementById('category-icon').className = catIcon;
  document.title = `${catName} 镜像下载 - SCM Pavilion`;

  let allProducts = [];
  let filteredProducts = [];
  let currentFilters = { edition: 'all', language: 'all' };
  let patchLookup = {};

  const searchInput = document.getElementById('search-input');
  const resourceBody = document.getElementById('resource-body');
  const versionCount = document.getElementById('version-count');
  const filterBtns = document.querySelectorAll('.filter-btn');

  // Load data
  Promise.all([
    loadData(category),
    fetch(`../data/meta.json?t=${Date.now()}`).then(r => r.json()).catch(() => ({})),
  ]).then(([data, meta]) => {
    // 构建补丁查询表: version -> { patch, updatedAt }
    if (meta.sourceTracking) {
      for (const [key, t] of Object.entries(meta.sourceTracking)) {
        if (t.version) {
          patchLookup[t.version.toLowerCase()] = {
            patch: t.patch || (t.innerVersion ? `${t.innerVersion}.${t.patchVersion}` : ''),
            updatedAt: t.updatedAt || '',
          };
        }
      }
    }

    if (data && data.products && data.products.length > 0) {
      allProducts = data.products;
      renderFilters();
      applyFilters();
    } else {
      const isFile = window.location.protocol === 'file:';
      resourceBody.innerHTML = `
        <tr><td colspan="7">
          <div class="empty-state">
            <i class="fas fa-${isFile ? 'globe' : 'database'}"></i>
            <p>${isFile ? '请通过 HTTP 服务器访问' : '暂无数据，请运行数据抓取脚本更新'}</p>
          </div>
        </td></tr>`;
      if (versionCount) versionCount.textContent = '0';
    }
  }).catch(() => {
    const isFile = window.location.protocol === 'file:';
    resourceBody.innerHTML = `
      <tr><td colspan="7">
        <div class="empty-state">
          <i class="fas fa-exclamation-triangle"></i>
          <p>${isFile ? '请通过 HTTP 服务器访问（python -m http.server 8080）' : '数据加载失败，请刷新页面重试'}</p>
        </div>
      </td></tr>`;
  });

  function renderFilters() {
    const editions = [...new Set(allProducts.map(p => p.edition))];
    const languages = [...new Set(allProducts.map(p => p.language))];
    const editionFilter = document.getElementById('filter-edition');
    const languageFilter = document.getElementById('filter-language');

    if (editionFilter) {
      editionFilter.innerHTML = '<button class="filter-btn active" data-filter="edition" data-value="all">全部</button>';
      editions.forEach(ed => {
        editionFilter.innerHTML += `<button class="filter-btn" data-filter="edition" data-value="${ed}">${ed}</button>`;
      });
      editionFilter.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          editionFilter.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          currentFilters.edition = btn.dataset.value;
          applyFilters();
        });
      });
    }

    if (languageFilter) {
      languageFilter.innerHTML = '<button class="filter-btn active" data-filter="language" data-value="all">全部</button>';
      languages.forEach(lang => {
        const langName = lang === 'zh-cn' ? '中文' : lang === 'en-us' ? 'English' : lang;
        languageFilter.innerHTML += `<button class="filter-btn" data-filter="language" data-value="${lang}">${langName}</button>`;
      });
      languageFilter.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          languageFilter.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          currentFilters.language = btn.dataset.value;
          applyFilters();
        });
      });
    }
  }

  function applyFilters() {
    let result = [...allProducts];

    if (currentFilters.edition !== 'all') {
      result = result.filter(p => p.edition === currentFilters.edition);
    }
    if (currentFilters.language !== 'all') {
      result = result.filter(p => p.language === currentFilters.language);
    }

    const query = searchInput ? searchInput.value.toLowerCase().trim() : '';
    if (query) {
      result = result.filter(p =>
        p.name.toLowerCase().includes(query) ||
        p.version.toLowerCase().includes(query) ||
        p.build.toLowerCase().includes(query) ||
        p.sku.toLowerCase().includes(query)
      );
    }

    filteredProducts = result;
    renderTable();
  }

  function renderTable() {
    if (versionCount) versionCount.textContent = filteredProducts.length;

    if (filteredProducts.length === 0) {
      resourceBody.innerHTML = `
        <tr><td colspan="7">
          <div class="empty-state">
            <i class="fas fa-search"></i>
            <p>没有匹配的资源</p>
          </div>
        </td></tr>`;
      return;
    }

    resourceBody.innerHTML = filteredProducts.map(p => {
      const patch = patchLookup[(p.version || '').toLowerCase()];
      return `
      <tr onclick="window.location.href='detail.html?id=${p.id}&cat=${category}'">
        <td class="version-cell">
          ${p.name}
          <small>${p.build}</small>
        </td>
        <td><span class="badge ${getEditionBadgeClass(p.edition)}">${p.edition || p.sku}</span></td>
        <td>${p.version || '-'}</td>
        <td>${formatDate(p.releaseDate)}</td>
        <td style="font-size:0.8125rem;">${patch ? `<span class="badge badge-green" style="font-family:var(--font-mono);">${patch.patch}</span><br><small style="color:var(--text-muted);font-family:var(--font-mono);">${patch.updatedAt}</small>` : '<span style="color:var(--text-muted);font-size:0.75rem;">-</span>'}</td>
        <td><span class="badge badge-cyan">${p.language || '-'}</span></td>
        <td class="action-cell">
          <a href="detail.html?id=${p.id}&cat=${category}">查看 <i class="fas fa-arrow-right" style="font-size:0.75rem;"></i></a>
        </td>
      </tr>`;
    }).join('');
  }

  // Search input
  if (searchInput) {
    let debounceTimer;
    searchInput.addEventListener('input', () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(applyFilters, 300);
    });
  }
});
