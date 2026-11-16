/* 求是·考点 — 首页交互：搜索 + 筛选 + 考点云 */
(function () {
  var q = document.getElementById('q');
  var grid = document.getElementById('grid');
  var empty = document.getElementById('empty');
  if (!grid) return;

  var cards = Array.prototype.slice.call(grid.querySelectorAll('.card'));
  var filter = 'all';
  var latest = 0;
  cards.forEach(function (c) {
    var m = (c.getAttribute('href') || '').match(/(\d{2})\.html/);
    var no = m ? parseInt(m[1], 10) : 0;
    c.dataset.no = no;
    if (no > latest) latest = no;
  });

  function apply() {
    var kw = (q && q.value ? q.value : '').trim().toLowerCase();
    var shown = 0;
    cards.forEach(function (c) {
      var no = parseInt(c.dataset.no, 10);
      var heat = parseInt(c.dataset.heat || '0', 10);
      var blob = (c.dataset.q || '').toLowerCase() + ' 第' + no + '期';
      var okKw = !kw || blob.indexOf(kw) > -1;
      var okF = true;
      if (filter === 'hot') okF = heat >= 4;
      if (filter === 'new') okF = no > latest - 3;
      var ok = okKw && okF;
      c.style.display = ok ? '' : 'none';
      if (ok) shown++;
    });
    if (empty) empty.style.display = shown ? 'none' : '';
  }

  if (q) q.addEventListener('input', apply);

  var chips = document.getElementById('chips');
  if (chips) {
    chips.addEventListener('click', function (e) {
      var b = e.target.closest('.chip');
      if (!b) return;
      chips.querySelectorAll('.chip').forEach(function (x) { x.classList.remove('on'); });
      b.classList.add('on');
      filter = b.dataset.f;
      apply();
    });
  }

  /* 考点云：点一下即用它搜索 */
  document.querySelectorAll('.kchip').forEach(function (k) {
    k.addEventListener('click', function () {
      var on = k.classList.contains('on');
      document.querySelectorAll('.kchip').forEach(function (x) { x.classList.remove('on'); });
      if (on) {
        if (q) q.value = '';
      } else {
        k.classList.add('on');
        if (q) q.value = k.dataset.kw;
      }
      apply();
    });
  });

  /* / 聚焦搜索 */
  document.addEventListener('keydown', function (e) {
    if (e.key === '/' && document.activeElement !== q && q) {
      e.preventDefault();
      q.focus();
    }
  });
})();
