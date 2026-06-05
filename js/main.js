// Global navigation

document.addEventListener('DOMContentLoaded', () => {

  initNav();

  initScrollEffects();

  setActiveNav();

});



function initNav() {

  const toggle = document.querySelector('.nav-toggle');

  const links = document.querySelector('.nav-links');

  if (toggle && links) {

    toggle.addEventListener('click', () => {

      links.classList.toggle('open');

      const icon = toggle.querySelector('i');

      if (icon) {

        icon.className = links.classList.contains('open') ? 'fas fa-times' : 'fas fa-bars';

      }

    });

    document.addEventListener('click', (e) => {

      if (!toggle.parentElement.contains(e.target) && links.classList.contains('open')) {

        links.classList.remove('open');

        const icon = toggle.querySelector('i');

        if (icon) icon.className = 'fas fa-bars';

      }

    });

  }

}



function initScrollEffects() {

  const nav = document.querySelector('.nav');

  if (!nav) return;

  window.addEventListener('scroll', () => {

    nav.classList.toggle('scrolled', window.scrollY > 50);

  }, { passive: true });

}



function setActiveNav() {

  const path = window.location.pathname.split('/').pop() || 'index.html';

  document.querySelectorAll('.nav-links a').forEach(link => {

    const href = link.getAttribute('href');

    link.classList.toggle('active', href === path);

  });

}



// Copy to clipboard utility

function setupCopyButtons() {

  document.querySelectorAll('.copy-btn').forEach(btn => {

    btn.addEventListener('click', () => {

      const codeBlock = btn.closest('.code-block');

      const text = codeBlock ? codeBlock.textContent.replace(btn.textContent, '').trim() : '';

      navigator.clipboard.writeText(text).then(() => {

        btn.textContent = '已复制';

        btn.classList.add('copied');

        setTimeout(() => {

          btn.textContent = '复制';

          btn.classList.remove('copied');

        }, 2000);

      }).catch(() => {

        btn.textContent = '复制失败';

        setTimeout(() => {

          btn.textContent = '复制';

        }, 2000);

      });

    });

  });

}



// Dynamic JSON data loader

async function loadData(category) {
  if (window.location.protocol === 'file:') {
    console.warn('数据加载失败：请通过 HTTP 服务器访问（python -m http.server 8080），而非直接打开 HTML 文件');
    return null;
  }
  try {
    const scriptSrc = (document.querySelector('script[src*="main.js"]')?.getAttribute('src') || '').split('?')[0];
    const match = scriptSrc.match(/^(\.\.\/)*/);
    const prefix = match ? match[0] : '';
    const response = await fetch(`${prefix}data/${category}.json`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } catch (e) {
    console.warn(`Failed to load data for ${category}:`, e);
    return null;
  }
}



function formatDate(dateStr) {

  if (!dateStr) return '-';

  // 使用 replace 避免时区偏移问题
  const parts = dateStr.replace(/\//g, '-').split('-');
  if (parts.length >= 3) {
    return `${parts[0]}-${parts[1].padStart(2, '0')}-${parts[2].padStart(2, '0')}`;
  }

  return dateStr;

}



function formatFileSize(size) {

  if (!size) return '-';

  return size;

}



function getEditionBadgeClass(edition) {

  const map = {

    'Professional': 'badge-cyan',

    'Enterprise': 'badge-purple',

    'Education': 'badge-blue',

    'Home': 'badge-green',

    'LTSC': 'badge-orange',

    'Datacenter': 'badge-purple',

    'Standard': 'badge-blue',

    'Pro for Workstations': 'badge-cyan'

  };

  return map[edition] || 'badge-cyan';

}



function truncateHash(hash) {

  if (!hash || hash.length <= 16) return hash;

  return hash.substring(0, 8) + '...' + hash.substring(hash.length - 8);

}

