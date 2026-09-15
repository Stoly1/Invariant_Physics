#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Собирает сайт-справочник по физике из файлов темы/**/*.md в папку docs/.

Запуск из корня проекта:   python3 скрипты/собрать.py

Ничего не требует, кроме стандартного Python 3.8+.
"""

import os
import re
import io
import json
import html
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'темы')
OUT = os.path.join(ROOT, 'docs')

# ---------------------------------------------------------------- транслитерация

_TRANS = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
}


def slug(text):
    out = []
    for ch in text.lower().strip():
        if ch in _TRANS:
            out.append(_TRANS[ch])
        elif ch.isalnum():
            out.append(ch)
        elif ch in ' _-/':
            out.append('-')
    s = re.sub(r'-+', '-', ''.join(out)).strip('-')
    return s or 'tema'


# ---------------------------------------------------------------- формулы
# Поддерживаем подмножество LaTeX, которого хватает школьной физике:
# \frac{a}{b}  \sqrt{x}  \vec{v}  x^{2}  v_{ср}  \cdot  \text{...}  греческие буквы

_SYMBOLS = {
    r'\cdot': '·', r'\times': '×', r'\pm': '±', r'\mp': '∓',
    r'\approx': '≈', r'\neq': '≠', r'\leq': '⩽', r'\geq': '⩾',
    r'\ldots': '…', r'\dots': '…', r'\infty': '∞',
    r'\Delta': 'Δ', r'\delta': 'δ', r'\alpha': 'α', r'\beta': 'β',
    r'\gamma': 'γ', r'\theta': 'θ', r'\lambda': 'λ', r'\mu': 'μ',
    r'\nu': 'ν', r'\pi': 'π', r'\rho': 'ρ', r'\sigma': 'σ', r'\tau': 'τ',
    r'\phi': 'φ', r'\omega': 'ω', r'\Omega': 'Ω', r'\varepsilon': 'ε',
    r'\to': '→', r'\rightarrow': '→', r'\Rightarrow': '⇒',
    r'\sin': 'sin<span class="m-thin"></span>',
    r'\cos': 'cos<span class="m-thin"></span>',
    r'\tan': 'tg<span class="m-thin"></span>', r'\tg': 'tg<span class="m-thin"></span>',
    r'\qquad': '<span class="m-gap"></span>',
    r'\quad': '<span class="m-gap-s"></span>',
    r'\,': '<span class="m-thin"></span>',
    r'\ ': ' ',
}


def _read_group(s, i):
    """Читает {...} начиная с позиции i (s[i] == '{'). Возвращает (содержимое, новый i)."""
    depth = 0
    start = i + 1
    while i < len(s):
        if s[i] == '{':
            depth += 1
        elif s[i] == '}':
            depth -= 1
            if depth == 0:
                return s[start:i], i + 1
        i += 1
    return s[start:], len(s)


def _read_arg(s, i):
    """Читает аргумент: либо {группу}, либо один следующий символ."""
    while i < len(s) and s[i] == ' ':
        i += 1
    if i < len(s) and s[i] == '{':
        return _read_group(s, i)
    if i < len(s):
        return s[i], i + 1
    return '', i


def math(src):
    """Переводит LaTeX-подмножество в HTML."""
    out = []
    i = 0
    n = len(src)
    while i < n:
        ch = src[i]

        if ch == '\\':
            m = re.match(r'\\[a-zA-Z]+|\\[,\ ]', src[i:])
            cmd = m.group(0) if m else src[i:i + 2]

            if cmd == r'\frac' or cmd == r'\dfrac':
                num, i = _read_arg(src, i + len(cmd))
                den, i = _read_arg(src, i)
                out.append('<span class="m-frac"><span class="m-num">%s</span>'
                           '<span class="m-den">%s</span></span>' % (math(num), math(den)))
                continue
            if cmd == r'\sqrt':
                arg, i = _read_arg(src, i + len(cmd))
                out.append('<span class="m-sqrt"><span class="m-radic">√</span>'
                           '<span class="m-rad">%s</span></span>' % math(arg))
                continue
            if cmd == r'\vec':
                arg, i = _read_arg(src, i + len(cmd))
                out.append('<span class="m-vec">%s</span>' % math(arg))
                continue
            if cmd == r'\text' or cmd == r'\mathrm':
                arg, i = _read_arg(src, i + len(cmd))
                out.append('<span class="m-text">%s</span>' % html.escape(arg))
                continue
            if cmd in _SYMBOLS:
                out.append(_SYMBOLS[cmd])
                i += len(cmd)
                continue
            i += len(cmd)
            continue

        if ch == '^' or ch == '_':
            arg, i = _read_arg(src, i + 1)
            tag = 'sup' if ch == '^' else 'sub'
            out.append('<%s>%s</%s>' % (tag, math(arg), tag))
            continue

        if ch == '{' or ch == '}':
            i += 1
            continue

        if ch == ' ':
            out.append(' ')
            i += 1
            continue

        out.append(html.escape(ch))
        i += 1

    return ''.join(out)


# ---------------------------------------------------------------- markdown

def inline(text):
    """Инлайновая разметка: формулы $..$, **жирный**, *курсив*, `код`, [ссылки]."""
    parts = []
    pos = 0
    # формулы вырезаем первыми, чтобы разметка их не портила
    for m in re.finditer(r'\$([^$]+)\$', text):
        parts.append(('t', text[pos:m.start()]))
        parts.append(('m', m.group(1)))
        pos = m.end()
    parts.append(('t', text[pos:]))

    out = []
    for kind, chunk in parts:
        if kind == 'm':
            out.append('<span class="math">%s</span>' % math(chunk))
            continue
        s = html.escape(chunk)
        s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
        s = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)
        s = re.sub(r'(?<![\w*])\*([^*\n]+)\*(?![\w*])', r'<em>\1</em>', s)
        s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)',
                   r'<a href="\2" rel="noopener">\1</a>', s)
        s = s.replace(' -- ', ' — ')
        out.append(s)
    return ''.join(out)


def render_blocks(lines):
    """Рендерит список строк markdown в HTML. Возвращает строку."""
    out = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # готовый HTML (рисунки, схемы) — пропускаем как есть
        m = re.match(r'^<([a-zA-Z][\w-]*)[\s>]', stripped)
        if m:
            tag = m.group(1)
            close = '</%s>' % tag
            buf = [line]
            i += 1
            while i < n and close not in buf[-1]:
                buf.append(lines[i])
                i += 1
            out.append('\n'.join(buf))
            continue

        # блочная формула $$...$$
        if stripped.startswith('$$'):
            body = stripped[2:]
            if body.endswith('$$') and len(stripped) > 4:
                body = body[:-2]
                i += 1
            else:
                i += 1
                buf = [body]
                while i < n and not lines[i].strip().endswith('$$'):
                    buf.append(lines[i])
                    i += 1
                if i < n:
                    buf.append(lines[i].strip()[:-2])
                    i += 1
                body = ' '.join(buf)
            out.append('<div class="math-block">%s</div>' % math(body.strip()))
            continue

        # таблица: строка с | и следующая строка-разделитель |---|---|
        if (stripped.startswith('|') and i + 1 < n
                and re.match(r'^\|[\s:|-]+\|$', lines[i + 1].strip())):
            def cells(row):
                return [c.strip() for c in row.strip().strip('|').split('|')]

            head = cells(stripped)
            i += 2
            body = []
            while i < n and lines[i].strip().startswith('|'):
                body.append(cells(lines[i]))
                i += 1
            thead = ''.join('<th>%s</th>' % inline(c) for c in head)
            rows = ''.join(
                '<tr>%s</tr>' % ''.join('<td>%s</td>' % inline(c) for c in row)
                for row in body)
            out.append('<div class="table-wrap"><table>'
                       '<thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>'
                       % (thead, rows))
            continue

        # заголовки
        m = re.match(r'^(#{2,4})\s+(.*)$', stripped)
        if m:
            level = len(m.group(1))
            out.append('<h%d id="%s">%s</h%d>' % (
                level, slug(m.group(2)), inline(m.group(2)), level))
            i += 1
            continue

        # цитата-вынос
        if stripped.startswith('>'):
            buf = []
            while i < n and lines[i].strip().startswith('>'):
                buf.append(lines[i].strip()[1:].strip())
                i += 1
            out.append('<aside class="note">%s</aside>' % render_blocks(buf))
            continue

        # маркированный список
        if re.match(r'^[-*]\s+', stripped):
            items = []
            while i < n and re.match(r'^[-*]\s+', lines[i].strip()):
                items.append(re.sub(r'^[-*]\s+', '', lines[i].strip()))
                i += 1
            out.append('<ul>%s</ul>' % ''.join(
                '<li>%s</li>' % inline(x) for x in items))
            continue

        # нумерованный список
        if re.match(r'^\d+[.)]\s+', stripped):
            items = []
            while i < n and re.match(r'^\d+[.)]\s+', lines[i].strip()):
                items.append(re.sub(r'^\d+[.)]\s+', '', lines[i].strip()))
                i += 1
            out.append('<ol>%s</ol>' % ''.join(
                '<li>%s</li>' % inline(x) for x in items))
            continue

        # абзац
        buf = [stripped]
        i += 1
        while i < n and lines[i].strip() and not re.match(
                r'^(#{2,4}\s|>|[-*]\s|\d+[.)]\s|\$\$|<[a-zA-Z])', lines[i].strip()):
            buf.append(lines[i].strip())
            i += 1
        out.append('<p>%s</p>' % inline(' '.join(buf)))

    return ''.join(out)


# ---------------------------------------------------------------- разбор темы

def parse_frontmatter(text):
    meta = {}
    if not text.startswith('---'):
        return meta, text
    end = text.find('\n---', 3)
    if end == -1:
        return meta, text
    for line in text[3:end].strip().splitlines():
        if ':' in line:
            k, v = line.split(':', 1)
            meta[k.strip()] = v.strip()
    return meta, text[end + 4:]


def parse_topic(path):
    with io.open(path, encoding='utf-8') as f:
        meta, body = parse_frontmatter(f.read())

    lines = body.splitlines()

    # делим на секции верхнего уровня (## Теория / ## Задачи)
    sections = {}
    current = None
    for line in lines:
        m = re.match(r'^##\s+(?!#)(.*)$', line.strip())
        if m:
            current = m.group(1).strip().lower()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)

    theory = render_blocks(sections.get('теория', []))

    # задачи: **N.** условие ... затем строки "> ответ"
    tasks = []
    group = None
    task_lines = sections.get('задачи', [])
    j = 0
    while j < len(task_lines):
        raw = task_lines[j].strip()

        m = re.match(r'^###\s+(.*)$', raw)
        if m:
            group = m.group(1).strip()
            j += 1
            continue

        m = re.match(r'^\*\*(\d+)\.\*\*\s*(.*)$', raw)
        if m:
            num = int(m.group(1))
            # условие: текст плюс, возможно, готовый HTML-блок (рисунок к задаче)
            parts = []          # куски условия по порядку, уже как HTML
            text = [m.group(2)]

            def flush(text=text, parts=parts):
                s = ' '.join(x for x in text if x).strip()
                if s:
                    parts.append(inline(s))
                del text[:]

            j += 1
            while j < len(task_lines):
                nxt = task_lines[j].strip()
                if nxt.startswith('>') or nxt.startswith('**') or nxt.startswith('###'):
                    break
                if not nxt:
                    # пустая строка условие не обрывает: дальше может идти рисунок
                    j += 1
                    if j < len(task_lines):
                        after = task_lines[j].strip()
                        if not (after.startswith('<') or after.startswith('>')
                                or after.startswith('**') or after.startswith('###')
                                or not after):
                            break
                    continue
                mh = re.match(r'^<([a-zA-Z][\w-]*)[\s>]', nxt)
                if mh:
                    flush()
                    close = '</%s>' % mh.group(1)
                    buf = [task_lines[j]]
                    j += 1
                    while j < len(task_lines) and close not in buf[-1]:
                        buf.append(task_lines[j])
                        j += 1
                    parts.append('\n'.join(buf))
                    continue
                text.append(nxt)
                j += 1
            flush()
            answer = []
            while j < len(task_lines) and task_lines[j].strip().startswith('>'):
                answer.append(task_lines[j].strip()[1:].strip())
                j += 1
            tasks.append({
                'num': num,
                'group': group,
                'cond': ''.join(parts),
                'answer': inline(' '.join(x for x in answer if x)),
            })
            continue

        j += 1

    rel = os.path.relpath(path, SRC)
    section = meta.get('раздел') or os.path.dirname(rel).replace(os.sep, ' / ') or 'Без раздела'

    # текст для поиска — без разметки
    plain = re.sub(r'<[^>]+>', ' ', theory + ' ' + ' '.join(t['cond'] for t in tasks))
    plain = re.sub(r'\s+', ' ', html.unescape(plain)).strip().lower()

    return {
        'title': meta.get('тема') or os.path.splitext(os.path.basename(path))[0],
        'section': section,
        'grade': meta.get('класс', ''),
        'order': int(meta.get('порядок', 999) or 999),
        'date': meta.get('дата', ''),
        'summary': meta.get('кратко', ''),
        'viz': meta.get('визуализация', ''),
        'theory': theory,
        'tasks': tasks,
        'slug': slug(section) + '/' + slug(os.path.splitext(os.path.basename(path))[0]),
        'plain': plain[:1200],
    }


def collect():
    topics = []
    for dirpath, _dirnames, filenames in os.walk(SRC):
        for fn in sorted(filenames):
            if fn.endswith('.md') and not fn.startswith('.'):
                topics.append(parse_topic(os.path.join(dirpath, fn)))
    topics.sort(key=lambda t: (t['section'], t['order'], t['title']))
    return topics


# ---------------------------------------------------------------- шаблоны

def page(title, base, body, cls=''):
    return u'''<!doctype html>
<html lang="ru" class="%(cls)s">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<link rel="stylesheet" href="%(base)sassets/fonts.css">
<link rel="stylesheet" href="%(base)sassets/style.css">
<link rel="icon" href="%(base)sassets/img/logo-mark.png">
<link rel="apple-touch-icon" href="%(base)sassets/img/logo-mark.png">
<meta name="theme-color" content="#0d1330">
</head>
<body>
%(body)s
<script src="%(base)sassets/app.js"></script>
</body>
</html>''' % {'title': html.escape(title), 'base': base, 'body': body, 'cls': cls}


def nav_html(topics, base, active=None):
    by_section = []
    for t in topics:
        if not by_section or by_section[-1][0] != t['section']:
            by_section.append((t['section'], []))
        by_section[-1][1].append(t)

    parts = []
    for section, items in by_section:
        links = []
        for t in items:
            is_active = ' class="active"' if t['slug'] == active else ''
            links.append(u'<li><a href="%st/%s.html"%s>%s</a></li>' % (
                base, t['slug'], is_active, html.escape(t['title'])))
        parts.append(u'<div class="nav-group"><h3>%s</h3><ul>%s</ul></div>' % (
            html.escape(section), ''.join(links)))

    return u'''<nav class="sidebar" id="sidebar" aria-label="Разделы">
<div class="nav-inner">
<label class="search-box">
  <span class="search-icon" aria-hidden="true">⌕</span>
  <input type="search" id="nav-search" placeholder="Поиск по темам" autocomplete="off" aria-label="Поиск по темам">
</label>
<div id="nav-list">%s</div>
<p class="nav-empty" id="nav-empty" hidden>Ничего не нашлось</p>
</div>
</nav>''' % ''.join(parts)


def topbar(base, extra=''):
    return u'''<header class="topbar">
<button class="icon-btn menu-btn" id="menu-btn" aria-label="Открыть список тем" aria-expanded="false">☰</button>
<a class="brand" href="%(base)sindex.html">
  <img class="brand-logo" src="%(base)sassets/img/logo-mark.png" alt="" width="34" height="34">
  <span class="brand-text">INVARIANT<span class="brand-sub">Физика</span></span>
</a>
<div class="topbar-right">%(extra)s
<button class="icon-btn" id="theme-btn" aria-label="Сменить оформление">◐</button>
</div>
</header>''' % {'base': base, 'extra': extra}


def signature(base):
    """Подпись автора сборника — внизу каждой страницы."""
    return u'''<aside class="signature">
<img class="sig-logo" src="%sassets/img/logo-mark.png" alt="" width="46" height="46">
<div class="sig-text">
  <span class="sig-name">INVARIANT</span>
  <span class="sig-sub">Физика · материалы к занятиям</span>
</div>
</aside>''' % base


def render_topic(t, topics):
    base = '../../'

    groups = []
    for task in t['tasks']:
        if not groups or groups[-1][0] != task['group']:
            groups.append((task['group'], []))
        groups[-1][1].append(task)

    task_html = []
    for group, items in groups:
        if group:
            task_html.append(u'<h3 class="task-group">%s</h3>' % html.escape(group))
        for task in items:
            task_html.append(
                u'<article class="task"><div class="task-num">%d</div>'
                u'<div class="task-body">%s</div></article>' % (task['num'], task['cond']))

    answers = u''.join(
        u'<li><span class="ans-num">%d</span><span class="ans-body">%s</span></li>' % (
            task['num'], task['answer'] or '—')
        for task in t['tasks'] if task['answer'])

    answers_block = u''
    if answers:
        answers_block = u'''<section class="answers" id="otvety">
<button class="answers-toggle" id="answers-toggle" aria-expanded="false" aria-controls="answers-body">
  <span class="answers-label">Ответы</span>
  <span class="answers-hint">Сначала реши сам — потом проверь</span>
  <span class="chev" aria-hidden="true">▾</span>
</button>
<ol class="answers-list" id="answers-body" hidden>%s</ol>
</section>''' % answers

    tasks_section = u''
    if task_html:
        tasks_section = u'''<section class="tasks">
<h2 class="section-head"><span class="section-kicker">Домашнее задание</span>
<span class="task-count">%d задач</span></h2>
%s
</section>''' % (len(t['tasks']), ''.join(task_html))

    body = u'''%(topbar)s
<div class="shell">
%(nav)s
<main class="content">
<article class="topic">
<p class="eyebrow">%(meta)s</p>
<h1>%(title)s</h1>
%(summary)s
<section class="theory">%(theory)s</section>
%(tasks)s
%(answers)s
</article>
<footer class="page-foot">
<a href="%(base)sindex.html">← Все темы</a>
<button class="link-btn" id="print-btn">Распечатать</button>
</footer>
%(signature)s
</main>
</div>
<div class="scrim" id="scrim" hidden></div>''' % {
        'topbar': topbar(base),
        'nav': nav_html(topics, base, t['slug']),
        'meta': html.escape(t['section']),
        'title': html.escape(t['title']),
        'signature': signature(base),
        'summary': u'<p class="lede">%s</p>' % inline(t['summary']) if t['summary'] else '',
        'theory': t['theory'],
        'tasks': tasks_section,
        'answers': answers_block,
        'base': base,
    }
    return page(t['title'] + ' — INVARIANT', base, body)


def render_index(topics):
    by_section = []
    for t in topics:
        if not by_section or by_section[-1][0] != t['section']:
            by_section.append((t['section'], []))
        by_section[-1][1].append(t)

    cards = []
    for section, items in by_section:
        rows = []
        for t in items:
            count = (u'<span class="card-meta"><span class="chip">%d задач</span></span>'
                     % len(t['tasks'])) if t['tasks'] else ''
            rows.append(
                u'<a class="card" href="t/%s.html">'
                u'<span class="card-title">%s</span>'
                u'<span class="card-sum">%s</span>'
                u'%s</a>' % (
                    t['slug'], html.escape(t['title']),
                    inline(t['summary']) if t['summary'] else '', count))
        cards.append(u'<section class="index-group"><h2>%s</h2><div class="cards">%s</div></section>'
                     % (html.escape(section), ''.join(rows)))

    total_tasks = sum(len(t['tasks']) for t in topics)

    body = u'''%(topbar)s
<div class="shell">
%(nav)s
<main class="content">
<div class="cover">
  <img class="cover-logo" src="assets/img/logo-mark.png" alt="" width="72" height="72">
  <div class="cover-text">
    <span class="cover-name">INVARIANT</span>
    <span class="cover-sub">Физика</span>
  </div>
</div>
<div class="hero">
<h1>Справочник по физике</h1>
<p class="lede">Теория, разборы и домашние задания по пройденным темам.
Выбери тему — внутри конспект, задачи и ответы для самопроверки.</p>
<p class="stats"><span><b>%(ntopics)d</b> тем</span><span><b>%(ntasks)d</b> задач</span></p>
</div>
%(cards)s
%(signature)s
</main>
</div>
<div class="scrim" id="scrim" hidden></div>''' % {
        'topbar': topbar(''),
        'nav': nav_html(topics, ''),
        'cards': ''.join(cards),
        'ntopics': len(topics),
        'ntasks': total_tasks,
        'signature': signature(''),
    }
    return page('INVARIANT — справочник по физике', '', body, cls='is-index')


# ---------------------------------------------------------------- сборка

def main():
    if not os.path.isdir(SRC):
        raise SystemExit('Нет папки «темы» — положи туда .md файлы с темами.')

    topics = collect()
    if not topics:
        raise SystemExit('В папке «темы» не найдено ни одного .md файла.')

    tdir = os.path.join(OUT, 't')
    if os.path.isdir(tdir):
        shutil.rmtree(tdir)

    for t in topics:
        dst = os.path.join(tdir, t['slug'] + '.html')
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with io.open(dst, 'w', encoding='utf-8') as f:
            f.write(render_topic(t, topics))

    with io.open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(render_index(topics))

    index = [{'t': t['title'], 's': t['section'], 'u': t['slug'], 'p': t['plain']}
             for t in topics]
    with io.open(os.path.join(OUT, 'search.json'), 'w', encoding='utf-8') as f:
        f.write(json.dumps(index, ensure_ascii=False))

    with io.open(os.path.join(OUT, '.nojekyll'), 'w', encoding='utf-8') as f:
        f.write('')

    print('Собрано: %d тем, %d задач → %s' % (
        len(topics), sum(len(t['tasks']) for t in topics), OUT))
    for t in topics:
        print('  · %-45s %2d задач' % (t['title'][:45], len(t['tasks'])))


if __name__ == '__main__':
    main()
