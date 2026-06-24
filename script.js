/* =========================================================
   CURATED. — Frontend logic
   - Load data
   - Render hero (3 highest-priced with photos)
   - Render featured (7 picks, asymmetric)
   - Render full grid (filter + search + sort + price range)
   - IntersectionObserver reveal + analytics
   - Web Share API
   - Plausible (privacy analytics) events
   ========================================================= */

(async function() {
  'use strict';

  const grid = document.getElementById('grid');
  const featuredGrid = document.getElementById('featuredGrid');
  const chipsEl = document.getElementById('chips');
  const searchEl = document.getElementById('search');
  const sortEl = document.getElementById('sort');
  const priceMinEl = document.getElementById('priceMin');
  const priceMaxEl = document.getElementById('priceMax');
  const countLabel = document.getElementById('countLabel');
  const empty = document.getElementById('empty');
  const weekLabel = document.getElementById('weekLabel');
  const stickyCta = document.getElementById('stickyCta');

  // Week label
  const now = new Date();
  const start = new Date(now.getFullYear(), 0, 1);
  const diff = (now - start) / 86400000;
  const wk = Math.ceil((diff + start.getDay() + 1) / 7);
  if (weekLabel) weekLabel.textContent = `Minggu ke-${wk}, ${now.getFullYear()}`;

  // Marquee strip: populate + duplicate for seamless loop
  const stripTrack = document.getElementById('stripTrack');
  if (stripTrack) {
  const stripItems = ['Pakaian','Tas','Kecantikan','Hijab','Sepatu','Aksesoris','Gadget','Otomotif','Rumah','Bayi'];
  const build = () => stripItems.map(i => `<span class="strip-item">${i}</span><span class="strip-dot">●</span>`).join('');
  stripTrack.innerHTML = build() + build();
  }

  // Load data
  let data = [];
  try {
    const res = await fetch('data.json');
    data = await res.json();
  } catch (e) {
    if (grid) grid.innerHTML = '<p style="text-align:center;padding:3rem;color:var(--ink-mute)">Gagal memuat data. Pastikan data.json tersedia.</p>';
    return;
  }

  // ----- Helpers -----
  const escapeHtml = s => String(s ?? '').replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));

  const monogram = s => {
    const clean = (s||'').trim();
    if (!clean) return '·';
    for (const c of clean) {
      if (/[A-Za-z0-9]/.test(c)) return c.toUpperCase();
    }
    return clean[0].toUpperCase();
  };

  const catLabel = c => ({
    clothing: 'Pakaian',
    bags: 'Tas',
    beauty: 'Kecantikan',
    beauty_storage: 'Beauty Storage',
    shoes: 'Sepatu',
    accessories: 'Aksesoris',
    hijab: 'Hijab',
    home: 'Rumah',
    sleepwear: 'Sleepwear',
    occasion: 'Occasion',
    gadget: 'Gadget',
    automotive: 'Otomotif',
    kids: 'Kids',
    baby: 'Bayi'
  }[c] || c);

  // Analytics helper (Plausible + custom event)
  const track = (name, props) => {
    try {
      if (window.plausible) window.plausible(name, { props });
    } catch (e) {}
    // Local storage as backup
    try {
      const key = 'curated_events';
      const arr = JSON.parse(localStorage.getItem(key) || '[]');
      arr.push({ name, props, t: Date.now() });
      // Keep last 100
      if (arr.length > 100) arr.shift();
      localStorage.setItem(key, JSON.stringify(arr));
    } catch (e) {}
  };

  // Web Share API
  const shareProduct = async (p) => {
    const shareData = {
      title: p.name,
      text: p.editorial_note || p.name,
      url: p.url
    };
    if (navigator.share) {
      try {
        await navigator.share(shareData);
        track('Share', { method: 'native', product_id: p.id });
      } catch (e) {}
    } else {
      // Fallback: copy link
      try {
        await navigator.clipboard.writeText(p.url);
        showToast('Tautan disalin ke clipboard');
        track('Share', { method: 'clipboard', product_id: p.id });
      } catch (e) {
        showToast('Gagal menyalin tautan');
      }
    }
  };

  // Toast notification
  const showToast = (msg) => {
    let toast = document.getElementById('toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'toast';
      toast.className = 'toast';
      document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.classList.add('toast-show');
    clearTimeout(toast._timeout);
    toast._timeout = setTimeout(() => toast.classList.remove('toast-show'), 2500);
  };

  // ----- Hero (3 highest-priced with images) -----
  const heroEl = document.getElementById('heroVisual');
  if (heroEl) {
    const withImg = data.filter(p => p.image_webp);
    const top3 = [...withImg].sort((a, b) => b.price - a.price).slice(0, 3);
    heroEl.innerHTML = top3.map((p, i) => `
      <a href="${escapeHtml(p.url)}" target="_blank" rel="noopener sponsored nofollow" class="hero-card hero-card-${String.fromCharCode(97 + i)}" data-id="${escapeHtml(p.id)}">
        <picture>
          <source type="image/webp" srcset="${escapeHtml(p.image_srcset)}" sizes="200px">
          <img class="hero-card-img" src="${escapeHtml(p.image_webp)}" alt="${escapeHtml(p.name)}" loading="eager" decoding="async" width="800" height="800">
        </picture>
        <div class="hero-card-meta">${escapeHtml((p.store || '').toUpperCase())} · ${escapeHtml(p.price_label)}</div>
      </a>
    `).join('');
    // Click tracking on hero cards
    heroEl.querySelectorAll('a').forEach(a => {
      a.addEventListener('click', () => {
        track('ClickAffiliate', { position: 'hero', product_id: a.dataset.id });
      });
    });
  }

  // ----- Featured (7 picks) -----
  const sortedByPrice = [...data].sort((a,b) => b.price - a.price);
  const seenCat = new Set();
  const featured = [];
  featured.push(sortedByPrice[0]);
  if (sortedByPrice[0]) seenCat.add(sortedByPrice[0].category);
  for (const p of sortedByPrice) {
    if (featured.length >= 7) break;
    if (!seenCat.has(p.category)) {
      featured.push(p);
      seenCat.add(p.category);
    }
  }
  let i = 0;
  while (featured.length < 7 && i < sortedByPrice.length) {
    if (!featured.includes(sortedByPrice[i])) featured.push(sortedByPrice[i]);
    i++;
  }

  function renderFeaturedCard(p, idx) {
    const img = p.image_webp
      ? `<picture><source type="image/webp" srcset="${escapeHtml(p.image_srcset)}" sizes="(max-width: 900px) 100vw, 50vw"><img class="featured-img" src="${escapeHtml(p.image_webp)}" alt="${escapeHtml(p.name)}" loading="lazy" decoding="async" width="800" height="800" onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'featured-monogram',textContent:'${escapeHtml(monogram(p.store || p.name))}'}))"></picture>`
      : `<div class="featured-monogram">${escapeHtml(monogram(p.store || p.name))}</div>`;
    return `
      <a href="${escapeHtml(p.url)}" target="_blank" rel="noopener sponsored nofollow" class="featured-card reveal" data-id="${escapeHtml(p.id)}">
        <div class="featured-thumb">
          <div class="featured-tag">${catLabel(p.category)}</div>
          ${img}
        </div>
        <div class="featured-body">
          <div class="featured-meta">${escapeHtml(p.store || '')}</div>
          <div class="featured-name">${escapeHtml(p.name)}</div>
          ${p.editorial_note ? `<div class="featured-note">${escapeHtml(p.editorial_note)}</div>` : ''}
          <div class="featured-footer">
            <div class="featured-price">${escapeHtml(p.price_label)}</div>
            <div class="featured-cta">Lihat di Shopee →</div>
          </div>
        </div>
      </a>
    `;
  }
  if (featuredGrid) {
    featuredGrid.innerHTML = featured.map(renderFeaturedCard).join('');
    // Click tracking
    featuredGrid.querySelectorAll('a').forEach(a => {
      a.addEventListener('click', () => {
        track('ClickAffiliate', { position: 'featured', product_id: a.dataset.id });
      });
    });
  }

  // ----- Filter chips -----
  const categories = ['all', ...Array.from(new Set(data.map(p => p.category))).sort()];
  const chipLabel = c => c === 'all' ? 'Semua' : catLabel(c);
  if (chipsEl) {
    chipsEl.innerHTML = categories.map((c, i) =>
      `<button class="chip ${i===0?'active':''}" data-cat="${escapeHtml(c)}" role="tab" aria-selected="${i===0}">${escapeHtml(chipLabel(c))}</button>`
    ).join('');
  }

  // ----- State -----
  let activeCat = 'all';
  let searchQ = '';
  let sortBy = 'price_desc';
  let priceMin = null;
  let priceMax = null;

  // ----- Render grid -----
  function render() {
    let rows = data.slice();
    if (activeCat !== 'all') rows = rows.filter(p => p.category === activeCat);
    if (searchQ) {
      const q = searchQ.toLowerCase();
      rows = rows.filter(p =>
        p.name.toLowerCase().includes(q) ||
        p.store.toLowerCase().includes(q) ||
        catLabel(p.category).toLowerCase().includes(q) ||
        (p.editorial_note || '').toLowerCase().includes(q)
      );
    }
    if (priceMin !== null) rows = rows.filter(p => p.price >= priceMin);
    if (priceMax !== null) rows = rows.filter(p => p.price <= priceMax);

    if (sortBy === 'price_desc') rows.sort((a,b) => b.price - a.price);
    else if (sortBy === 'price_asc') rows.sort((a,b) => a.price - b.price);
    else if (sortBy === 'name') rows.sort((a,b) => a.name.localeCompare(b.name));
    else if (sortBy === 'sold_desc') rows.sort((a,b) => (b.sold || 0) - (a.sold || 0));

    if (rows.length === 0) {
      grid.innerHTML = '';
      empty.hidden = false;
    } else {
      empty.hidden = true;
      grid.innerHTML = rows.map((p, idx) => {
        const img = p.image_webp
          ? `<picture><source type="image/webp" srcset="${escapeHtml(p.image_srcset)}" sizes="(max-width: 560px) 100vw, (max-width: 900px) 50vw, 33vw"><img class="card-img" src="${escapeHtml(p.image_webp)}" alt="${escapeHtml(p.name)}" loading="lazy" decoding="async" width="800" height="800" onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'card-monogram',textContent:'${escapeHtml(monogram(p.store || p.name))}'}))"></picture>`
          : `<div class="card-monogram">${escapeHtml(monogram(p.store || p.name))}</div>`;
        const rank = String(idx + 1).padStart(3, '0');
        const soldTxt = p.sold_label || (p.sold ? p.sold.toLocaleString('id-ID') + ' terjual' : '0 terjual');
        return `
        <article class="card reveal" data-id="${escapeHtml(p.id)}">
          <a href="${escapeHtml(p.url)}" target="_blank" rel="noopener sponsored nofollow" class="card-link" data-id="${escapeHtml(p.id)}">
            <div class="card-thumb">
              <div class="card-rank">No. ${rank}</div>
              <div class="card-cat">${escapeHtml(catLabel(p.category))}</div>
              ${img}
            </div>
            <div class="card-body">
              <div class="card-store">${escapeHtml(p.store || '')}</div>
              <h3 class="card-name">${escapeHtml(p.name)}</h3>
              ${p.editorial_note ? `<p class="card-note">${escapeHtml(p.editorial_note)}</p>` : ''}
              <div class="card-footer">
                <div class="card-price-block">
                  <div class="card-price">${escapeHtml(p.price_label)}</div>
                </div>
                <div class="card-sold">${escapeHtml(soldTxt)}</div>
              </div>
            </div>
          </a>
          <button class="card-share" type="button" aria-label="Bagikan ${escapeHtml(p.name)}" data-id="${escapeHtml(p.id)}">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>
          </button>
        </article>
      `;}).join('');

      // Inject MGID in-feed widgets every 8 products (after the 8th, 16th, 24th card)
      // Skip injection if MGID publisher ID is still placeholder (not configured)
      const MGID_WIDGET_ID = 'WIDGET_ID_INFEED';  // swap with real widget ID from mgid.com
      const MGID_PLACEHOLDER = 'WIDGET_ID_INFEED';
      if (MGID_WIDGET_ID !== MGID_PLACEHOLDER && typeof window.mgid !== 'undefined') {
        const cards = grid.querySelectorAll('.card');
        const insertPositions = [];
        for (let i = 7; i < cards.length; i += 8) insertPositions.push(i);
        insertPositions.reverse().forEach(idx => {
          const targetCard = cards[idx];
          if (!targetCard) return;
          const ins = document.createElement('ins');
          ins.className = 'mgid-widget mgid-infeed';
          ins.setAttribute('data-widget-id', MGID_WIDGET_ID);
          ins.style.display = 'block';
          ins.style.gridColumn = '1 / -1';
          ins.style.minHeight = '240px';
          ins.style.margin = '0.75rem 0';
          targetCard.parentNode.insertBefore(ins, targetCard.nextSibling);
          if (window.mgid) {
            window.mgid.push({ widget: MGID_WIDGET_ID, renderer: 'default', size: 'default' });
          }
        });
        // Show footer widget too (below grid)
        const footer = document.getElementById('mgid-widget-footer');
        if (footer) {
          footer.style.display = 'block';
          footer.style.gridColumn = '1 / -1';
          footer.style.minHeight = '90px';
          footer.style.margin = '2rem auto 1rem';
        }
      }

      // Bind affiliate click tracking
      grid.querySelectorAll('.card-link').forEach(a => {
        a.addEventListener('click', () => {
          track('ClickAffiliate', { position: 'grid', product_id: a.dataset.id });
        });
      });
      // Bind share button
      grid.querySelectorAll('.card-share').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          const p = data.find(x => x.id === btn.dataset.id);
          if (p) shareProduct(p);
        });
      });
    }

    if (countLabel) countLabel.textContent = `${rows.length} barang`;

    observeReveals();
  }

  // ----- Events -----
  if (chipsEl) {
    chipsEl.addEventListener('click', e => {
      const btn = e.target.closest('.chip');
      if (!btn) return;
      chipsEl.querySelectorAll('.chip').forEach(c => { c.classList.remove('active'); c.setAttribute('aria-selected', 'false'); });
      btn.classList.add('active');
      btn.setAttribute('aria-selected', 'true');
      activeCat = btn.dataset.cat;
      track('FilterCategory', { category: activeCat });
      render();
    });
  }

  if (searchEl) {
    let debounce;
    searchEl.addEventListener('input', e => {
      clearTimeout(debounce);
      debounce = setTimeout(() => {
        searchQ = e.target.value.trim();
        if (searchQ) track('Search', { query: searchQ });
        render();
      }, 200);
    });
  }

  if (sortEl) {
    sortEl.addEventListener('change', e => {
      sortBy = e.target.value;
      track('Sort', { method: sortBy });
      render();
    });
  }

  if (priceMinEl) {
    let debounce;
    priceMinEl.addEventListener('input', e => {
      clearTimeout(debounce);
      debounce = setTimeout(() => {
        priceMin = parseInt(e.target.value) || null;
        render();
      }, 200);
    });
  }
  if (priceMaxEl) {
    let debounce;
    priceMaxEl.addEventListener('input', e => {
      clearTimeout(debounce);
      debounce = setTimeout(() => {
        priceMax = parseInt(e.target.value) || null;
        render();
      }, 200);
    });
  }

  // ----- Sticky mobile CTA visibility -----
  if (stickyCta) {
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.target.id === 'koleksi') {
          stickyCta.classList.toggle('sticky-cta-show', entry.isIntersecting);
        }
      });
    }, { threshold: 0.1 });
    const koleksiEl = document.getElementById('koleksi');
    if (koleksiEl) observer.observe(koleksiEl);
  }

  // ----- Reveal on scroll -----
  let revealObserver;
  function observeReveals() {
    if (!('IntersectionObserver' in window)) {
      document.querySelectorAll('.reveal').forEach(el => el.classList.add('in'));
      return;
    }
    if (revealObserver) revealObserver.disconnect();
    revealObserver = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('in');
          revealObserver.unobserve(entry.target);
        }
      });
    }, { threshold: 0.05, rootMargin: '0px 0px -30px 0px' });
    document.querySelectorAll('.reveal:not(.in)').forEach(el => revealObserver.observe(el));
  }

  // ----- Newsletter form -----
  const newsletterForm = document.getElementById('newsletterForm');
  const newsletterEmail = document.getElementById('newsletterEmail');
  const newsletterMsg = document.getElementById('newsletterMsg');
  if (newsletterForm) {
    newsletterForm.addEventListener('submit', e => {
      e.preventDefault();
      const email = newsletterEmail.value.trim();
      if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        newsletterMsg.hidden = false;
        newsletterMsg.textContent = 'Email tidak valid';
        newsletterMsg.className = 'newsletter-msg newsletter-msg-err';
        return;
      }
      // Save to localStorage
      try {
        const subs = JSON.parse(localStorage.getItem('curated_subs') || '[]');
        if (!subs.includes(email)) subs.push(email);
        localStorage.setItem('curated_subs', JSON.stringify(subs));
      } catch (e) {}
      track('NewsletterSignup', { email_domain: email.split('@')[1] });
      newsletterMsg.hidden = false;
      newsletterMsg.textContent = '✓ Terdaftar. Cek inbox Anda.';
      newsletterMsg.className = 'newsletter-msg newsletter-msg-ok';
      newsletterEmail.value = '';
    });
  }

  // ----- Service worker registration (PWA) -----
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js').catch(() => {});
    });
  }

  // Initial render
  render();
  observeReveals();
})();
