let config = null;
let sessions = {};
let state = {tasks: [], results: {}, outcomes: {}, products: {}, reviews: [], running: false, total: 0, done: 0};
let allReviews = [];
let mode = 'quick';
let selectedCountries = new Set(['us']);
let selectedStars = new Set(['全部']);
let showAllMarkets = false;
let selectedProduct = '';
let currentView = 'reviews';
let currentPage = 1;
let revision = -1;
let instanceId = null;
let connected = false;
let submitBusy = false;
let lastRun = null;
let draftTimer;
let toastTimer;
let llmTestBusy=false, llmTestSource='';
const requestedMetadata = new Set();
const PAGE_SIZE = 12;
const $ = id => document.getElementById(id);
const icon = name => `<svg aria-hidden="true"><use href="#i-${name}"/></svg>`;
const loginBusy = () => ['opening', 'waiting', 'saving'].includes(state.login_phase);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const taskKey = task => task.id || task.asin;
const countryName = code => language === 'en' ? (COUNTRY_EN[code] || String(code || '').toUpperCase()) : config?.marketplaces.find(item => item.code === code)?.name || String(code || '').toUpperCase();
const statusSources = {success:'已完成', empty:'暂无评论', failed:'采集失败', blocked:'访问受限',
  login_required:'需要登录', review_auth_required:'需再次认证', http_error:'页面异常',
  network_error:'网络异常', parse_error:'读取失败', pagination_error:'翻页未完成', cancelled:'已停止', pending:'待采集',running:'正在采集',interrupted:'意外中断'};
const goodStatuses = new Set(['success', 'empty', 'cancelled']);
const sessionSources = {missing:'未登录', saved:'已保存，待验证', verified:'已验证',
  expired:'需要重新登录', invalid:'会话不可用'};

const statusNames = new Proxy(statusSources,{get:(source,key)=>t(source[key] || key)});
const sessionLabels = new Proxy(sessionSources,{get:(source,key)=>t(source[key] || key)});
let connectionMessage='正在连接', noticeSource='', toastSource='', setupExpanded=true;
const expandedReviews=new Set();

async function request(url, body) {
  const response = await fetch(url, body === undefined ? {} : {
    method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)
  });
  let data;
  try { data = await response.json(); }
  catch (_) { throw new Error('服务暂时没有响应，请确认本地服务正在运行'); }
  if (!response.ok || data.ok === false) throw new Error(data.message || '请求未完成，请稍后重试');
  return data;
}

function saveDraft() {
  clearTimeout(draftTimer);
  draftTimer = setTimeout(() => {
    try {
      localStorage.setItem('reviewStudio.settings', JSON.stringify({
        asins:$('asins').value, mode, countries:[...selectedCountries],
        stars:[...selectedStars], cap:$('cap').value, localOnly:$('localOnly').checked, translation:translationDraft()
      }));
    } catch (_) {}
  }, 150);
}

function readAsins() {
  return [...new Set($('asins').value.split(/[\s,，;；]+/).map(s => s.trim().toUpperCase()).filter(Boolean))];
}

async function init() {
  try {
    config = await request('/api/init');
    sessions = config.sessions || {};
    const initial = await request('/api/status');
    let draft = null;
    try { draft = JSON.parse(localStorage.getItem('reviewStudio.settings')); } catch (_) {}
    if (draft && !initial.running) {
      $('asins').value = String(draft.asins || '');
      mode = draft.mode === 'deep' ? 'deep' : 'quick';
      selectedCountries = new Set((draft.countries || ['us']).filter(code => config.marketplaces.some(m => m.code === code)));
      selectedStars = new Set((draft.stars || ['全部']).filter(star => config.star_filters.includes(star)));
      $('cap').value = Number(draft.cap) || 100;
      $('localOnly').checked = draft.localOnly === true;
      restoreTranslationDraft(draft.translation);
    } else if (initial.tasks?.length) {
      $('asins').value = [...new Set(initial.tasks.map(t => t.asin))].join('\n');
      mode = initial.tasks[0].mode;
      selectedCountries = new Set(initial.tasks.map(t => t.country));
      selectedStars = new Set(initial.tasks.map(t => t.star_key || '全部'));
      $('cap').value = initial.tasks[0].cap || 100;
      $('localOnly').checked = initial.tasks[0].local_only === true;
    }
    if (!selectedCountries.size) selectedCountries.add('us');
    if (!selectedStars.size) selectedStars.add('全部');
    setMode(mode, false);
    renderCountryOptions();
    renderStarOptions();
    applySnapshot(initial);
    setSetup(!initial.tasks?.length);
    activateNav(initial.tasks?.length ? "navResults" : "navSetup");
    connectSSE();
  } catch (error) {
    notice(error.message);
    setConnection(false, '连接失败，请启动服务后刷新');
  }
}

function setConnection(live, message) {
  connected=live;
  connectionMessage=message;
  $('connectionStatus').innerHTML='<i></i>'+esc(t(message));
  $('connectionStatus').title=t(message);
  $('connectionStatus').setAttribute('aria-label',t(message));
  $('connectionStatus').className='connection '+(live ? 'live' : 'error');
  renderControls();
}

function connectSSE() {
  const source = new EventSource('/api/events');
  source.onopen = () => {setConnection(true, '已连接');maybeFetchProduct();};
  source.onmessage = event => {
    let data;
    try { data = JSON.parse(event.data); } catch (_) { return; }
    if (data.type === 'snapshot') applySnapshot(data);
    else if (data.type === 'progress' && acceptVersion(data)) {
      Object.assign(state, {status:data.status, done:data.done, total:data.total, active_task:data.active_task});
      renderProgress();
      renderStats();
      if (currentView === 'tasks') renderTasks();
    }
  };
  source.onerror = () => setConnection(false, '正在重连并恢复任务…');
}

function acceptVersion(event) {
  if (event.instance_id !== instanceId) {
    instanceId = event.instance_id;
    revision = -1;
  }
  if (event.revision <= revision) return false;
  revision = event.revision;
  return true;
}

function deduplicateReviews(snapshot) {
  if (Array.isArray(snapshot.reviews)) return snapshot.reviews;
  const merged = new Map();
  (snapshot.tasks || []).forEach(task => (snapshot.results?.[taskKey(task)] || []).forEach(raw => {
    const identity = [task.asin, task.country, raw.review_id || JSON.stringify([raw.title,raw.body,raw.author,raw.date,raw.rating])].join('|');
    if (!merged.has(identity)) merged.set(identity, {...raw, asin:task.asin, country:task.country});
  }));
  return [...merged.values()];
}

function applySnapshot(snapshot) {
  if (!acceptVersion(snapshot)) return;
  if (snapshot.run_id !== lastRun) {
    lastRun = snapshot.run_id;
    currentPage = 1;
    selectedProduct = '';
    if (snapshot.running) currentView = 'reviews';
  }
  state = snapshot;
  state.tasks ||= [];
  state.outcomes ||= {};
  state.products ||= {};
  sessions = snapshot.sessions || sessions;
  allReviews = deduplicateReviews(snapshot);
  const asins = [...new Set(state.tasks.map(task => task.asin))];
  if (!asins.includes(selectedProduct)) selectedProduct = asins[0] || '';
  if (state.phase === 'failed' && !allReviews.length) currentView = 'tasks';
  renderStats();
  renderProgress();
  renderCapture();
  renderSessions();
  renderLogin();
  renderControls();
  renderTranslation();
  renderResults();
  maybeFetchProduct();
}

function renderCountryOptions() {
  if (!config) return;
  const preferred = ['us','uk','de','jp','ca','fr','it','es'];
  const rank = code => preferred.includes(code) ? preferred.indexOf(code) : 99;
  const ordered = [...config.marketplaces].sort((a,b) => rank(a.code)-rank(b.code));
  const visible = showAllMarkets ? ordered : ordered.filter((m,i) => i<8 || selectedCountries.has(m.code));
  $('countryOptions').innerHTML = visible.map(m => `<label class="country-chip ${selectedCountries.has(m.code) ? 'selected' : ''}" title="${esc(countryName(m.code)+' · '+m.domain)}"><input type="checkbox" name="countries" value="${m.code}" ${selectedCountries.has(m.code) ? 'checked' : ''}><span>${esc(countryName(m.code))}</span><span class="country-code">${m.code.toUpperCase()}</span></label>`).join('');
  $('toggleMarkets').innerHTML = esc(showAllMarkets ? t('收起更多站点') : t('查看全部 {count} 个站点',{count:ordered.length})) + icon('chevron');
  renderControls();
}

function renderStarOptions() {
  const options = ['全部','5 星','4 星','3 星','2 星','1 星'];
  $('starOptions').innerHTML = options.map(star => `<label class="star-chip ${selectedStars.has(star) ? 'selected' : ''}"><input type="checkbox" name="star_keys" value="${star}" ${selectedStars.has(star) ? 'checked' : ''}>${star === '全部' ? esc(t('全部')) : star[0]+'<span class="star-mini">★</span>'}</label>`).join('');
  renderControls();
}

function setMode(value, persist=true) {
  mode = value === 'deep' ? 'deep' : 'quick';
  document.querySelectorAll('#modeGroup label').forEach(label => {
    label.classList.toggle('active', label.dataset.mode === mode);
    label.querySelector('input').checked = label.dataset.mode === mode;
  });
  $('starField').hidden = mode !== 'deep';
  $('quickModeNote').hidden = mode === 'deep';
  renderEstimate();
  if (persist) saveDraft();
}

function renderEstimate() {
  const asins = readAsins();
  const invalid = asins.filter(asin => !/^[A-Z0-9]{10}$/.test(asin));
  $('asinCount').textContent = invalid.length ? t('{count} 个格式有误',{count:invalid.length}) : t('{count} 个 ASIN',{count:asins.length});
  $('asins').setAttribute('aria-invalid', invalid.length ? 'true' : 'false');
  const stars = mode === 'deep' ? selectedStars.size : 1;
  const count = asins.length*selectedCountries.size*stars;
  $('taskEstimate').textContent = asins.length ? t('{products} 商品 × {markets} 市场 × {stars} 星级',{products:asins.length,markets:selectedCountries.size,stars}) : t('添加商品，准备开始');
  $('estimatedCount').textContent = count ? t('{count} 个任务',{count}) : '';
  renderControls();
}

function renderControls() {
  const busy = state.running || loginBusy() || submitBusy || llmTestBusy;
  const asins = readAsins();
  const count = asins.length * selectedCountries.size * (mode === 'deep' ? selectedStars.size : 1);
  const valid = asins.length && asins.every(a => /^[A-Z0-9]{10}$/.test(a)) &&
    selectedCountries.size && (mode !== 'deep' || selectedStars.size) && count <= 500;
  $('startBtn').disabled = busy || !connected || !valid;
  $('startBtn').innerHTML = esc(t(state.phase==='translating' ? '正在翻译评论' : state.running ? '正在采集用户反馈' : '开始采集')) + icon('arrow');
  $('stopBtn').hidden = !state.running;
  $('stopBtn').disabled = !connected || submitBusy;
  $('captureStopBtn').hidden = !state.running || state.phase==='translating';
  $('captureStopBtn').disabled = !connected || submitBusy;
  document.querySelectorAll('[data-retry]').forEach(button=>button.disabled=busy||!connected);
  $('asins').disabled = busy;
  $('cap').disabled = busy;
  $('localOnly').disabled = busy;
  document.querySelectorAll('#translationFields input,#translationFields select,#enableTranslation').forEach(input=>input.disabled=busy||llmTestBusy);
  $('testLlmBtn').disabled=busy||llmTestBusy||!connected;
  $('translateExistingBtn').disabled=busy||llmTestBusy||!connected||!allReviews.length;
  $('stopTranslationBtn').disabled=submitBusy||!connected;
  document.querySelectorAll('#countryOptions input, #starOptions input, #modeGroup input').forEach(input => input.disabled = busy);
  document.querySelectorAll('[data-login]').forEach(button => button.disabled = busy || !connected);
  const hasResults = state.tasks?.length > 0;
  $('downloadBtn').classList.toggle('disabled', !hasResults);
  $('downloadBtn').setAttribute('aria-disabled', String(!hasResults));
  $('loginSaveBtn').disabled = state.login_phase !== 'waiting' || submitBusy || !connected;
  $('loginCancelBtn').disabled = submitBusy || !connected;
}

function renderSessions() {
  const countries = [...new Set([...selectedCountries,...(loginBusy() && state.login_code ? [state.login_code] : [])])];
  $('sessionList').innerHTML = countries.length ? countries.map(code => {
    const status = sessions[code] || 'missing';
    const ready = status === 'verified' || status === 'saved';
    return `<div class="session-row"><span class="market-avatar">${code.toUpperCase()}</span><span class="session-name">${esc(countryName(code))}<small>Amazon ${code.toUpperCase()}</small></span><span class="session-state ${ready ? 'ready' : ''}"><i class="tiny-dot ${ready ? 'green' : ''}"></i>${esc(sessionLabels[status])}</span><button class="session-login" data-login="${code}">${esc(t(ready ? '验证' : '登录'))}</button></div>`;
  }).join('') : '<div class="session-note">'+esc(t('选择一个目标市场后，可在这里登录。'))+'</div>';
  $('loginBadge').textContent = countries.map(code => sessionLabels[sessions[code] || 'missing']).join(language==='en' ? ', ' : '、');
}

function renderLogin() {
  const phase = state.login_phase;
  const messages = {
    opening:t('正在打开评论页认证窗口，请稍候。'),
    waiting:state.login_error ? localizeServer(state.login_error)+t('（认证页面已保留）') : t('在浏览器中完成评论页要求的认证，然后回到这里验证并保存。'),
    saving:t('正在确认评论页可读取，并保存这次会话。'),
    saved:t('会话已保存。请保留浏览器窗口，开始你的评论采集。'),
    error:t('登录未完成：{message}',{message:localizeServer(state.login_error) || t('请重新打开认证窗口')}),
    cancelled:t('本次登录已取消，可随时重新开始。')
  };
  $('loginBanner').hidden = !messages[phase];
  $('loginBannerText').textContent = messages[phase] || '';
  $('loginBannerTitle').textContent = (state.login_code ? countryName(state.login_code)+' · ' : '') + t(phase==='saved' ? '会话已就绪' : '站点认证');
  $('loginSaveBtn').hidden = !['waiting','saving'].includes(phase);
  $('loginSaveBtn').textContent = t(phase==='saving' ? '正在验证…' : '验证并保存');
  $('loginCancelBtn').hidden = !loginBusy();
}

function renderStats() {
  const rated = allReviews.filter(r => Number(r.rating)>0);
  const average = rated.length ? rated.reduce((n,r) => n+Number(r.rating),0)/rated.length : 0;
  const countries = new Set(state.tasks.map(t => t.country));
  const issues = Object.values(state.outcomes).filter(o => !goodStatuses.has(o.status) && !['pending','running'].includes(o.status)).length;
  $('statReviews').innerHTML = allReviews.length.toLocaleString()+'<span>'+esc(t('条'))+'</span>';
  $('statProducts').innerHTML = new Set(state.tasks.map(t => t.asin)).size+'<span>'+esc(t('件'))+'</span>';
  $('statRating').innerHTML = (rated.length ? average.toFixed(1) : '—')+'<span>/ 5</span>';
  $('statTasks').innerHTML = (state.done || 0)+'<span>/ '+(state.total || 0)+'</span>';
  $('statMarkets').textContent = countries.size ? t('覆盖 {count} 个国家 / 地区',{count:countries.size}) : t('等待第一轮采集');
  $('statPositive').textContent = rated.length ? t('{percent}% 的样本评分为 4–5 星',{percent:Math.round(rated.filter(r => Number(r.rating)>=4).length/rated.length*100)}) : t('随评论结果实时更新');
  $('statTaskStatus').textContent = state.phase==='translating' ? t('正在翻译评论') : state.running ? t('正在收集真实反馈…') : issues ? t('{count} 个任务需要关注',{count:issues}) : t(state.phase==='completed' ? '本轮采集已完成' : state.phase==='cancelled' ? '已停止，结果已保留' : '准备就绪，随时开始');
  $('navCount').textContent = allReviews.length>999 ? '999+' : allReviews.length;
  $('taskIssueCount').hidden = !issues;
  $('taskIssueCount').textContent = issues;
}

function renderProgress() {
  $('progressCard').hidden = !state.total;
  const done = state.done || 0, total = state.total || 0;
  $('countLabel').textContent = t('{done} / {total} 个任务',{done,total});
  $('progressBar').style.width = (total ? Math.round(done/total*100) : 0)+'%';
  $('progressTitle').textContent = t(state.phase==='translating' ? '正在翻译评论' : state.running ? '正在收集用户声音' : state.phase==='failed' ? '本轮采集需要关注' : state.phase==='cancelled' ? '已停止，保留已有评论' : '本轮采集已结束');
  $('statusLine').textContent = localizeServer(state.status || '');
}

function renderResults() {
  const hasTasks = state.tasks.length > 0;
  $('emptyState').hidden = hasTasks;
  $('resultsContent').hidden = !hasTasks;
  $('resultSummary').textContent = hasTasks ? t('{products} 个商品 · {reviews} 条评论',{products:new Set(state.tasks.map(t => t.asin)).size,reviews:allReviews.length}) : t('等待你的第一轮采集');
  if (!hasTasks) return;
  const products = [...new Set(state.tasks.map(t => t.asin))];
  $('productTabs').innerHTML = products.length > 1 ? products.map(asin =>
    `<button class="product-tab ${asin === selectedProduct ? 'active' : ''}" data-product="${asin}">${icon('box')}${asin}<small>${allReviews.filter(r => r.asin === asin).length}</small></button>`).join('') : '';
  renderMarketFilter();
  renderHero();
  renderReviews();
  renderTasks();
  setView(currentView);
}

function renderMarketFilter() {
  const previous = $('resultCountry').value;
  const countries = [...new Set(state.tasks.filter(t => t.asin===selectedProduct).map(t => t.country))];
  $('resultCountry').innerHTML = '<option value="">'+esc(t('全部市场'))+'</option>'+countries.map(code => `<option value="${code}">${esc(countryName(code))}</option>`).join('');
  if (countries.includes(previous)) $('resultCountry').value=previous;
}

function safeImage(url) {
  try {
    const parsed = new URL(url);
    const host = parsed.hostname.toLowerCase();
    return parsed.protocol === 'https:' && (host === 'm.media-amazon.com' || host.endsWith('.media-amazon.com') || host.endsWith('.images-amazon.com') || host.endsWith('.ssl-images-amazon.com')) ? parsed.href : '';
  } catch (_) { return ''; }
}

function currentMetadata() {
  const country = $('resultCountry').value;
  const candidates = Object.values(state.products || {}).filter(p => p.asin === selectedProduct && (!country || p.country === country));
  return candidates.find(p => p.image && p.title) || candidates.find(p => p.title) || candidates[0] || {};
}

function renderHero() {
  const metadata = currentMetadata();
  const market = $('resultCountry').value;
  const reviews = allReviews.filter(r => r.asin === selectedProduct && (!market || r.country === market));
  const rated = reviews.filter(r => Number(r.rating)>0);
  const average = rated.length ? rated.reduce((sum,r) => sum+Number(r.rating),0)/rated.length : 0;
  const countries = [...new Set(state.tasks.filter(t => t.asin === selectedProduct).map(t => t.country))];
  const code = market || metadata.country || countries[0] || 'us';
  const domain = config?.marketplaces.find(m => m.code === code)?.domain || 'www.amazon.com';
  const image = safeImage(metadata.image);
  const distribution = [5,4,3,2,1].map(star => {
    const amount = rated.filter(r => Math.round(Number(r.rating)) === star).length;
    const percentage = rated.length ? Math.round(amount/rated.length*100) : 0;
    return `<div class="rating-row"><span>${star}</span><i><b style="width:${percentage}%"></b></i><span>${percentage}%</span></div>`;
  }).join('');
  $('productHero').innerHTML = `<article class="product-hero"><div class="product-art"><span class="fallback">${icon('box')}<small>${esc(t('商品'))}</small></span>${image ? '<img src="'+esc(image)+'" alt="'+esc(metadata.title || selectedProduct)+'" loading="lazy" referrerpolicy="no-referrer">' : ''}</div>
    <div class="product-info"><div class="product-kicker"><span class="collection-label">${esc(t('商品研究'))}</span><span>${esc(metadata.brand || t(metadata.title ? 'Amazon 商品' : '商品资料暂未返回'))}</span></div>
    <h3 class="product-title ${metadata.title ? '' : 'placeholder'}">${esc(metadata.title || selectedProduct)}</h3>
    <div class="product-subline"><button class="asin-copy" data-copy="${selectedProduct}" title="${esc(t('复制 ASIN'))}">${selectedProduct}${icon('copy')}</button>${countries.map(c => '<span class="market-pill">'+esc(countryName(c))+'</span>').join('')}<a class="source-link" href="https://${esc(domain)}/dp/${selectedProduct}" target="_blank" rel="noopener noreferrer">${esc(t('查看商品'))}${icon('link')}</a>${!image ? '<button class="metadata-refresh" data-refresh-product>'+esc(t('重新读取资料'))+'</button>' : ''}</div></div>
    <div class="rating-summary"><div class="rating-number">${rated.length ? average.toFixed(1) : '—'}<span>/ 5</span></div><div class="rating-stars">${'★'.repeat(Math.round(average))}${'☆'.repeat(5-Math.round(average))}</div><div class="rating-distribution">${distribution}</div></div></article>`;
}

function filteredReviews() {
  const query = $('reviewSearch').value.trim().toLowerCase();
  const country = $('resultCountry').value;
  const rating = Number($('resultStar').value);
  let reviews = allReviews.filter(r => r.asin === selectedProduct &&
    (!country || r.country === country) && (!rating || Math.round(Number(r.rating)) === rating) &&
    (!query || [r.body,r.title,r.author,r.translation?.title,r.translation?.body].join(' ').toLowerCase().includes(query)));
  const sort = $('reviewSort').value;
  if (sort === 'lowest') reviews = [...reviews].sort((a,b) => Number(a.rating)-Number(b.rating));
  else if (sort === 'highest') reviews = [...reviews].sort((a,b) => Number(b.rating)-Number(a.rating));
  else if (sort === 'helpful') {
    const votes = r => Number((String(r.helpful || '').replace(/,/g,'').match(/\d+/) || [0])[0]);
    reviews = [...reviews].sort((a,b) => votes(b)-votes(a));
  }
  return reviews;
}

function renderReviews() {
  const reviews = filteredReviews();
  const pages = Math.max(1, Math.ceil(reviews.length/PAGE_SIZE));
  currentPage = Math.max(1, Math.min(pages, currentPage));
  const offset = (currentPage-1)*PAGE_SIZE;
  $('filteredCount').textContent = t('{count} 条匹配评论',{count:reviews.length});
  $('resultBody').innerHTML = reviews.slice(offset,offset+PAGE_SIZE).map(review => {
    const rating = Math.max(0, Math.min(5, Number(review.rating)||0));
    const author = review.author || t('Amazon 用户');
    const initial = Array.from(author.trim())[0] || 'A';
    const long = [review.body,review.translation?.body].some(text=>String(text||'').length>160||String(text||'').includes('\n'));
    return `<article class="review-row" data-review-key="${esc(reviewIdentity(review))}"><span class="review-avatar">${esc(initial)}</span><div><div class="review-meta"><span class="review-author">${esc(author)}</span><span class="market-pill">${esc(t('{market} 站点',{market:countryName(review.country)}))}</span><span class="origin-pill">${esc(t('评价地区：{region}',{region:review.review_country ? countryName(review.review_country) : review.review_country_name || t('未识别')}))}</span>${review.verified ? '<span class="verified">'+icon('check')+esc(t('已验证购买'))+'</span>' : ''}<span class="review-date" title="${esc(review.date)}">${esc(reviewDate(review.date))}</span></div><div class="review-rating"><span>${'★'.repeat(Math.round(rating))}${'☆'.repeat(5-Math.round(rating))}</span><span class="rating-caption">${rating.toFixed(1)} / 5</span></div>${reviewContent(review)}<div class="review-bottom">${long ? '<button class="expand-review" aria-expanded="'+String(expandedReviews.has(reviewIdentity(review)))+'">'+esc(t(expandedReviews.has(reviewIdentity(review)) ? '收起内容' : '展开全文'))+icon('chevron')+'</button>' : '<span></span>'}<span class="review-helpful">${esc(helpfulText(review.helpful))}</span></div></div></article>`;
  }).join('') || '<div class="no-matches">'+icon('search')+esc(t(allReviews.length ? '没有找到匹配的评论，试试其他关键词或筛选条件。' : '尚未取得评论，可在“任务明细”中查看当前进展。'))+'</div>';
  const numbers = new Set([1,pages,currentPage-1,currentPage,currentPage+1].filter(n => n>0 && n<=pages));
  let last = 0;
  const buttons = [...numbers].sort((a,b)=>a-b).map(number => {
    const gap = last && number-last>1 ? '<span>…</span>' : '';
    last = number;
    return gap+`<button class="page-button ${number === currentPage ? 'active' : ''}" data-page="${number}" ${number === currentPage ? 'aria-current="page"' : ''}>${number}</button>`;
  }).join('');
  $('pagination').innerHTML = '<span>'+(reviews.length ? (offset+1)+'–'+Math.min(offset+PAGE_SIZE,reviews.length)+' / '+reviews.length : t('0 条评论'))+'</span><div class="page-buttons"><button class="page-button previous" data-page="'+(currentPage-1)+'" '+(currentPage===1?'disabled':'')+' aria-label="'+esc(t('上一页'))+'">'+icon('chevron')+'</button>'+buttons+'<button class="page-button" data-page="'+(currentPage+1)+'" '+(currentPage===pages?'disabled':'')+' aria-label="'+esc(t('下一页'))+'">'+icon('chevron')+'</button></div>';
}

function renderTasks() {
  $('outcomeBody').innerHTML = state.tasks.map(task => {
    const outcome = state.outcomes[taskKey(task)] || {status:'pending',count:0,message:''};
    const active = state.running && state.active_task===taskKey(task) && ['pending','running'].includes(outcome.status);
    const css = active ? 'running' : outcome.status==='success' ? 'success' : goodStatuses.has(outcome.status) || outcome.status==='pending' ? '' : 'issue';
    const retry = !state.running && !['success','empty'].includes(outcome.status);
    const reason = ['running','pending'].includes(outcome.status) ? t(active?'正在读取页面…':'等待执行') : t(config?.stop_reasons?.[outcome.stop_reason] || '未记录结束原因');
    return `<tr><td>${esc(task.asin)}<small>${esc(countryName(task.country))} · ${task.country.toUpperCase()}</small></td><td>${esc(t(task.star_key || '全部'))}</td><td>${esc(t(task.local_only ? '仅本站国家/地区' : '全部地区'))}</td><td><span class="status-badge ${css}">${active ? esc(t('正在采集')) : esc(statusNames[outcome.status] || outcome.status)}</span></td><td>${outcome.count || 0}</td><td><strong class="task-reason">${esc(reason)}</strong><p>${esc(outcome.message ? localizeServer(outcome.message,outcome.status) : '')}</p><details class="task-numbers"><summary>${esc(t('查看本轮数量明细'))}</summary>${outcome.stats_known ? statsMarkup(outcome.stats) : '<p>'+esc(t('旧任务未记录数量明细；后续采集时会记录。'))+'</p>'}</details>${retry ? `<button class="button secondary small" data-retry="${esc(taskKey(task))}" ${!connected||submitBusy||loginBusy()||llmTestBusy?'disabled':''}>${esc(t('重试此组合'))}</button>` : ''}</td></tr>`;
  }).join('');
}

function setView(view) {
  currentView = view;
  $('reviewsView').hidden = view !== 'reviews';
  $('tasksView').hidden = view !== 'tasks';
  ['reviews','tasks'].forEach(name => {
    $(name+'Tab').classList.toggle('active', name === view);
    $(name+'Tab').setAttribute('aria-selected', String(name === view));
  });
}

function maybeFetchProduct() {
  if (!selectedProduct || state.running || loginBusy() || !connected) return;
  const country = $('resultCountry').value || state.tasks.find(t => t.asin === selectedProduct)?.country;
  if (!country) return;
  const key = selectedProduct+':'+country;
  if (state.products[key]?.image || requestedMetadata.has(key)) return;
  requestedMetadata.add(key);
  request('/api/products/refresh', {asin:selectedProduct,country}).catch(() => {});
}

async function action(url, body) {
  submitBusy = true;
  notice('');
  renderControls();
  try {
    await request(url, body);
    if (url === '/api/start' || url === '/api/retry') {setSetup(false);activateNav('navResults');}
    applySnapshot(await request('/api/status'));
  } catch (error) { notice(error.message); }
  finally { submitBusy = false; renderControls(); renderLogin(); }
}

function notice(message) {
  noticeSource=message;
  $('notice').textContent=localizeServer(message);
  $('notice').hidden=!message;
}

function toast(message) {
  clearTimeout(toastTimer);
  toastSource=message;
  $('toast').textContent=localizeServer(message);
  $('toast').hidden=false;
  toastTimer=setTimeout(() => $('toast').hidden=true,2200);
}

function setSetup(expanded) {
  setupExpanded=Boolean(expanded);
  $('setupContent').hidden=!setupExpanded;
  $('toggleSetup').setAttribute('aria-expanded',String(setupExpanded));
  $('toggleSetup').innerHTML=esc(t(setupExpanded ? '收起设置' : '展开设置'))+icon('chevron');
}

function activateNav(id) {
  document.querySelectorAll('.topnav .nav-item').forEach(button => {
    button.classList.toggle('active',button.id===id);
    button.setAttribute('aria-pressed',String(button.id===id));
  });
}

function setLanguage(next) {
  language=next==='en' ? 'en' : 'zh';
  try {localStorage.setItem('reviewStudio.language',language);} catch (_) {}
  translateDOM();
  setConnection(connected,connectionMessage);
  renderCountryOptions();
  renderStarOptions();
  renderEstimate();
  renderSessions();
  renderLogin();
  renderStats();
  renderProgress();
  renderCapture();
  renderTranslation();
  renderTranslationSettings();
  renderResults();
  setSetup(setupExpanded);
  if (noticeSource) notice(noticeSource);
  if (!$('toast').hidden) $('toast').textContent=localizeServer(toastSource);
  renderControls();
  $('llmTestResult').textContent=localizeServer(llmTestSource);
}

function reviewIdentity(review) {
  return [review.asin,review.country,review.review_id || JSON.stringify([review.author,review.date,review.title,review.body])].join('|');
}

function translationDraft() {
  return {enabled:$('enableTranslation').checked,provider:$('llmProvider').value,base_url:$('llmUrl').value,model:$('llmModel').value,
    target_language:$('llmLanguage').value,batch_size:$('llmBatchSize').value,timeout:$('llmTimeout').value,max_tokens:$('llmMaxTokens').value};
}

function restoreTranslationDraft(draft) {
  if (!draft) return;
  $('enableTranslation').checked=draft.enabled === true;
  $('llmProvider').value=draft.provider==='anthropic'?'anthropic':'openai';
  for (const [id,key] of [['llmUrl','base_url'],['llmModel','model'],['llmLanguage','target_language'],['llmBatchSize','batch_size'],['llmTimeout','timeout'],['llmMaxTokens','max_tokens']]) {
    if (draft[key] !== undefined) $(id).value=draft[key];
  }
  renderTranslationSettings();
}

function translationSettings() {
  const draft=translationDraft();
  if (!draft.base_url.trim() || !draft.model.trim()) throw new Error('请填写 LLM 接口地址和模型名称');
  const batch=Number(draft.batch_size),timeout=Number(draft.timeout);
  if (!Number.isInteger(batch)||batch<1||batch>20||!Number.isInteger(timeout)||timeout<5||timeout>180) throw new Error('翻译批量须为 1–20，超时须为 5–180 秒的整数');
  const settings={provider:draft.provider,base_url:draft.base_url.trim(),model:draft.model.trim(),api_key:$('llmKey').value,target_language:draft.target_language,batch_size:batch,timeout};
  if (draft.provider==='anthropic') {
    const maxTokens=Number(draft.max_tokens);
    if (!Number.isInteger(maxTokens)||maxTokens<128||maxTokens>65536) throw new Error('Anthropic 输出上限须为 128–65536 的整数');
    settings.max_tokens=maxTokens;
  }
  return settings;
}

function renderTranslationSettings() {
  $('translationFields').hidden=!$('enableTranslation').checked;
  const anthropic=$('llmProvider').value==='anthropic';
  $('llmProvider').dataset.current=$('llmProvider').value;
  $('llmAnthropicField').hidden=!anthropic;
  $('llmProtocolBadge').textContent=t(anthropic?'Anthropic 原生接口':'OpenAI 兼容接口');
  $('llmUrl').placeholder=anthropic?'https://api.anthropic.com':'https://your-provider.example/v1';
  $('llmProtocolHint').textContent=t(anthropic?'Anthropic 可填写域名、含 /v1 的地址或完整 /v1/messages 地址；输出上限须在模型支持范围内。':'OpenAI 兼容接口请填写含版本路径的 Base URL，或完整 /chat/completions 地址。');
}

function renderTranslation() {
  const info=state.translation||{phase:'idle'};
  $('translationCard').hidden=info.phase==='idle';
  $('stopTranslationBtn').hidden=info.phase!=='running';
  if (info.phase==='idle') return;
  const labels={running:'正在翻译评论',completed:'评论翻译已完成',partial:'部分评论翻译失败，可重试',failed:'评论翻译失败',cancelled:'翻译已停止，已有译文已保留',interrupted:'翻译曾中断，可继续翻译剩余评论'};
  $('translationTitle').textContent=t(labels[info.phase]||'评论翻译');
  $('translationCount').textContent=t('{done} / {total} 条',{done:info.done||0,total:info.total||0});
  $('translationBar').style.width=(info.total?Math.min(100,Math.round(info.done/info.total*100)):0)+'%';
  $('translationDetail').textContent=t('成功 {success} 条 · 失败 {failed} 条 · 目标语言 {language} · 模型 {model}',{success:info.succeeded||0,failed:info.failed||0,language:info.target_language||'',model:info.model||''})+(info.error?' · '+localizeServer(info.error):'');
}

function reviewContent(review) {
  const entry=review.translation;
  const expanded=expandedReviews.has(reviewIdentity(review));
  const original='<div class="review-original">'+(entry?'<div class="comparison-label">'+esc(t('原文'))+'</div>':'')+'<h4 class="review-title">'+esc(review.title||t('用户评价'))+'</h4><p class="review-text '+(expanded?'expanded':'')+'">'+esc(review.body)+'</p></div>';
  if (!entry) return original;
  if (entry.status!=='success') return original+'<div class="translation-error">'+esc(t('翻译失败，原文已保留'))+(entry.error?' · '+esc(localizeServer(entry.error)):'')+'</div>';
  return '<div class="review-comparison">'+original+'<div class="review-translated"><div class="comparison-label">'+esc(t('译文'))+' · '+esc(entry.target_language)+'</div><h4 class="review-translated-title">'+esc(entry.title)+'</h4><p class="review-translation-text '+(expanded?'expanded':'')+'">'+esc(entry.body)+'</p></div></div>';
}

$('enableTranslation').addEventListener('change',()=>{renderTranslationSettings();saveDraft();});
$('stopTranslationBtn').addEventListener('click',()=>action('/api/stop',{}));
$('llmProvider').addEventListener('change',()=>{
  if ($('llmProvider').dataset.current!==$('llmProvider').value) {
    const url=$('llmUrl').value.trim();
    if (!url||/^https:\/\/api\.(?:openai|anthropic)\.com(?:\/v1)?(?:\/(?:chat\/completions|messages))?\/?$/.test(url)) $('llmUrl').value=$('llmProvider').value==='anthropic'?'https://api.anthropic.com':'https://api.openai.com/v1';
    $('llmKey').value='';llmTestSource='';$('llmTestResult').textContent='';
  }
  renderTranslationSettings();saveDraft();
});
['llmUrl','llmModel','llmLanguage','llmBatchSize','llmTimeout','llmMaxTokens'].forEach(id=>$(id).addEventListener('input',saveDraft));
$('testLlmBtn').addEventListener('click',async()=>{
  let settings;
  try {settings=translationSettings();} catch(error) {notice(error.message);return;}
  llmTestBusy=true;llmTestSource='正在测试翻译连接…';$('llmTestResult').textContent=t(llmTestSource);renderControls();
  try {
    await request('/api/llm/test',settings);
    llmTestSource='翻译连接测试成功';
  } catch(error) {llmTestSource=error.message;}
  finally {llmTestBusy=false;$('llmTestResult').textContent=localizeServer(llmTestSource);renderControls();}
});
$('translateExistingBtn').addEventListener('click',()=>{
  try {action('/api/translate',translationSettings());} catch(error) {notice(error.message);}
});

$('languageSelect').addEventListener('change',event=>setLanguage(event.target.value));
$('toggleSetup').addEventListener('click',()=>setSetup(!setupExpanded));
$('navSetup').addEventListener('click',()=>{activateNav('navSetup');setSetup(true);$('setupPanel').scrollIntoView({behavior:'smooth',block:'start'});});

$('asins').addEventListener('input', () => {renderEstimate();saveDraft();});
$('cap').addEventListener('input', saveDraft);
$('localOnly').addEventListener('change', saveDraft);
$('modeGroup').addEventListener('change', event => {
  if (event.target.name === 'mode') setMode(event.target.value);
});
$('countryOptions').addEventListener('change', event => {
  if (event.target.name !== 'countries') return;
  if (event.target.checked) selectedCountries.add(event.target.value);
  else selectedCountries.delete(event.target.value);
  event.target.closest('label').classList.toggle('selected', event.target.checked);
  renderEstimate(); renderSessions(); renderControls(); saveDraft();
});
$('starOptions').addEventListener('change', event => {
  const input = event.target;
  if (input.name !== 'star_keys') return;
  if (input.value === '全部') {
    selectedStars = input.checked ? new Set(['全部']) : new Set();
  } else {
    selectedStars.delete('全部');
    if (input.checked) selectedStars.add(input.value); else selectedStars.delete(input.value);
  }
  renderStarOptions(); renderEstimate(); saveDraft();
});
$('toggleMarkets').addEventListener('click', () => {showAllMarkets=!showAllMarkets;renderCountryOptions();});
$('startBtn').addEventListener('click', async () => {
  const asins = readAsins();
  const cap = mode === 'deep' ? Number($('cap').value) : null;
  if (mode === 'deep' && (!Number.isInteger(cap) || cap<1 || cap>10000)) {
    notice('每个组合的采集上限需要是 1 到 10000 之间的整数');return;
  }
  let translation=null;
  try {if ($('enableTranslation').checked) translation=translationSettings();} catch(error) {notice(error.message);return;}
  await action('/api/start', {asins,countries:[...selectedCountries],mode,
    star_keys:mode === 'deep' ? [...selectedStars] : ['全部'],cap,local_only:$('localOnly').checked,translation});
});
$('stopBtn').addEventListener('click', () => action('/api/stop',{}));
$('sessionList').addEventListener('click', event => {
  const button = event.target.closest('[data-login]');
  if (!button) return;
  const asin = readAsins().find(a => /^[A-Z0-9]{10}$/.test(a)) || selectedProduct;
  action('/api/login',{country:button.dataset.login,asin:asin || null});
});
$('loginSaveBtn').addEventListener('click', () => action('/api/login/save',{}));
$('loginCancelBtn').addEventListener('click', () => action('/api/login/cancel',{}));
$('reviewsTab').addEventListener('click', () => setView('reviews'));
$('tasksTab').addEventListener('click', () => setView('tasks'));
$('navResults').addEventListener('click', () => {activateNav('navResults');$('resultCard').scrollIntoView({behavior:'smooth',block:'start'});});
$('navSessions').addEventListener('click', () => {activateNav('navSessions');$('sessionsPanel').open=true;$('sessionsPanel').scrollIntoView({behavior:'smooth',block:'start'});});
$('productTabs').addEventListener('click', event => {
  const button = event.target.closest('[data-product]');
  if (!button) return;
  selectedProduct=button.dataset.product;currentPage=1;
  renderResults();maybeFetchProduct();
});
$('reviewSearch').addEventListener('input', () => {currentPage=1;renderReviews();});
['resultCountry','resultStar','reviewSort'].forEach(id => $(id).addEventListener('change', () => {
  currentPage=1;renderHero();renderReviews();maybeFetchProduct();
}));
$('resultBody').addEventListener('click', event => {
  const button = event.target.closest('.expand-review');
  if (!button) return;
  const expanded = button.getAttribute('aria-expanded') !== 'true';
  button.setAttribute('aria-expanded', String(expanded));
  button.closest('.review-row').querySelectorAll('.review-text,.review-translation-text').forEach(text=>text.classList.toggle('expanded',expanded));
  const key=button.closest('.review-row').dataset.reviewKey;
  if(expanded) expandedReviews.add(key); else expandedReviews.delete(key);
  button.innerHTML = esc(t(expanded ? '收起内容' : '展开全文'))+icon('chevron');
});
$('productHero').addEventListener('click', async event => {
  if (event.target.closest('[data-refresh-product]')) {
    const country = $('resultCountry').value || state.tasks.find(t => t.asin === selectedProduct)?.country;
    if (!country) return;
    try {
      await request('/api/products/refresh', {asin:selectedProduct, country});
      toast('已请求重新读取商品资料，评论数据会继续保留');
    } catch (error) {toast(error.message);}
    return;
  }
  const button=event.target.closest('[data-copy]');
  if (!button) return;
  try {await navigator.clipboard.writeText(button.dataset.copy);toast('ASIN 已复制');}
  catch (_) {toast('ASIN：'+button.dataset.copy);}
});
$('pagination').addEventListener('click', event => {
  const button=event.target.closest('[data-page]');
  if (!button || button.disabled) return;
  currentPage=Number(button.dataset.page);renderReviews();
  $('productHero').scrollIntoView({behavior:'smooth',block:'start'});
});
document.addEventListener('error', event => {
  if (event.target instanceof HTMLImageElement && event.target.closest('.product-art')) event.target.hidden=true;
},true);
document.addEventListener('keydown', event => {
  if (event.key === '/' && !$('helpDialog').open && !['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)) {
    event.preventDefault();$('reviewSearch').focus();
  }
});
const captureFields={read:'读取条目',duplicates:'重复条目',foreign:'非本站剔除',unknown:'地区未知剔除',over_limit:'超上限条目',new:'本轮新增',recovered:'沿用已有',kept:'组合保留'};
function statsMarkup(stats={}) {
  return '<dl class="capture-numbers">'+Object.entries(captureFields).map(([key,label])=>`<div><dt>${esc(t(label))}</dt><dd>${Number(stats[key]||0).toLocaleString()}</dd></div>`).join('')+'</dl>';
}
function renderCapture() {
  $('captureCard').hidden=!state.tasks.length;
  const summary=state.capture_summary;
  $('captureNumbers').innerHTML=summary?.recorded_tasks ? statsMarkup(summary) : '<p class="capture-hint">'+esc(t('旧任务未记录数量明细；后续采集时会记录。'))+'</p>';
  $('captureCoverage').textContent=summary?.recorded_tasks ? t('已记录 {recorded} / {total} 个组合；各组合取最近一轮统计。',{recorded:summary.recorded_tasks,total:state.total}) : '';
  $('captureUnique').textContent=t('去重后共 {count} 条评论',{count:allReviews.length});
  $('savedStatus').textContent=state.last_saved_at ? t('已保存至本机 · {time}',{time:new Date(state.last_saved_at).toLocaleString(language==='en'?'en-US':'zh-CN')}) : t('完成的结果已保留；新任务将按页保存。');
  $('persistenceError').hidden=!state.persistence_error;
  $('persistenceError').textContent=localizeServer(state.persistence_error||'');
  const count=state.tasks.filter(task=>!['success','empty'].includes(state.outcomes[taskKey(task)]?.status)).length;
  $('retryAllBtn').hidden=state.running||!count;
  $('retryAllBtn').textContent=t('重试未完成组合（{count}）',{count});
}
async function retryCapture(key) {
  let translation=null;
  try {if ($('enableTranslation').checked) translation=translationSettings();} catch(error) {notice(error.message);return;}
  await action('/api/retry',{run_id:state.run_id,task_ids:key?[key]:null,translation});
}
$('retryAllBtn').addEventListener('click',()=>retryCapture());
$('outcomeBody').addEventListener('click',event=>{
  const button=event.target.closest('[data-retry]');
  if (button&&!button.disabled) retryCapture(button.dataset.retry);
});
$('captureStopBtn').addEventListener('click',()=>action('/api/stop',{}));
$('helpBtn').addEventListener('click',()=>{$('helpDialog').showModal();document.body.classList.add('help-open');});
$('helpCloseBtn').addEventListener('click',()=>$('helpDialog').close());
$('helpDialog').addEventListener('close',()=>{document.body.classList.remove('help-open');$('helpBtn').focus();});
$('helpDialog').addEventListener('click',event=>{
  if (event.target!==$('helpDialog')) return;
  const rect=$('helpDialog').getBoundingClientRect();
  if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom) $('helpDialog').close();
});
renderTranslationSettings();
renderEstimate();
init();
