/* Справочник по физике — поведение страницы */
(function () {
  'use strict';

  var root = document.documentElement;

  /* ---- оформление: светлое / тёмное ---------------------- */

  var saved = null;
  try { saved = localStorage.getItem('fizika-theme'); } catch (e) {}
  if (saved === 'dark' || saved === 'light') root.setAttribute('data-theme', saved);

  var themeBtn = document.getElementById('theme-btn');
  if (themeBtn) {
    themeBtn.addEventListener('click', function () {
      var isDark = root.getAttribute('data-theme') === 'dark' ||
        (!root.getAttribute('data-theme') &&
          window.matchMedia('(prefers-color-scheme: dark)').matches);
      var next = isDark ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      try { localStorage.setItem('fizika-theme', next); } catch (e) {}
    });
  }

  /* ---- боковая панель на телефоне ------------------------ */

  var sidebar = document.getElementById('sidebar');
  var menuBtn = document.getElementById('menu-btn');
  var scrim = document.getElementById('scrim');

  function closeNav() {
    if (!sidebar) return;
    sidebar.classList.remove('open');
    if (scrim) scrim.hidden = true;
    if (menuBtn) menuBtn.setAttribute('aria-expanded', 'false');
  }

  if (menuBtn && sidebar) {
    menuBtn.addEventListener('click', function () {
      var open = sidebar.classList.toggle('open');
      if (scrim) scrim.hidden = !open;
      menuBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
      if (open) {
        var input = document.getElementById('nav-search');
        if (input) input.focus();
      }
    });
  }
  if (scrim) scrim.addEventListener('click', closeNav);

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeNav();
    if (e.key === '/' && document.activeElement.tagName !== 'INPUT') {
      var input = document.getElementById('nav-search');
      if (input) { e.preventDefault(); input.focus(); }
    }
  });

  /* ---- поиск по темам ------------------------------------ */

  var search = document.getElementById('nav-search');
  var navList = document.getElementById('nav-list');
  var navEmpty = document.getElementById('nav-empty');
  var fulltext = null;

  function base() {
    return root.classList.contains('is-index') ? '' : '../../';
  }

  function loadFulltext() {
    if (fulltext !== null) return;
    fulltext = {};
    fetch(base() + 'search.json')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        data.forEach(function (item) { fulltext[item.u] = item.p || ''; });
        if (search && search.value) filter();
      })
      .catch(function () {});
  }

  function filter() {
    if (!navList) return;
    var q = search.value.trim().toLowerCase();
    var groups = navList.querySelectorAll('.nav-group');
    var shown = 0;

    groups.forEach(function (group) {
      var visible = 0;
      group.querySelectorAll('li').forEach(function (li) {
        var link = li.querySelector('a');
        if (!link) return;
        var title = link.textContent.toLowerCase();
        var sect = (group.querySelector('h3') || {}).textContent || '';
        var href = link.getAttribute('href') || '';
        var url = href.replace(base() + 't/', '').replace('.html', '');
        var body = (fulltext && fulltext[url]) || '';
        var hit = !q || title.indexOf(q) > -1 ||
          sect.toLowerCase().indexOf(q) > -1 || body.indexOf(q) > -1;
        li.hidden = !hit;
        if (hit) visible++;
      });
      group.hidden = visible === 0;
      shown += visible;
    });

    if (navEmpty) navEmpty.hidden = shown !== 0;
  }

  if (search) {
    search.addEventListener('focus', loadFulltext, { once: true });
    search.addEventListener('input', filter);
  }

  /* ---- ответы -------------------------------------------- */

  var toggle = document.getElementById('answers-toggle');
  var answers = document.getElementById('answers-body');

  if (toggle && answers) {
    toggle.addEventListener('click', function () {
      var open = toggle.getAttribute('aria-expanded') === 'true';
      toggle.setAttribute('aria-expanded', open ? 'false' : 'true');
      answers.hidden = open;
      if (!open) {
        answers.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      }
    });
  }

  /* ---- печать -------------------------------------------- */

  var printBtn = document.getElementById('print-btn');
  if (printBtn) {
    printBtn.addEventListener('click', function () { window.print(); });
  }
})();
