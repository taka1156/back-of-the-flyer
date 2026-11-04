// 確認クイズの表示（各メモの <!-- memo:quiz --> ブロックから読み込む）。
// 問題データは各メモの <script type="application/json" id="memo-quiz">。
// 問題データ（#memo-quiz）がこのブロックより後ろにあってもよいよう、読み込み後に実行する
(function (run) {
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run);
  else run();
})(function () {
  var data = document.getElementById('memo-quiz');
  var ui = document.getElementById('memo-quiz-ui');
  if (!data || !ui) return;
  var qs;
  try { qs = JSON.parse(data.textContent); } catch (e) { return; }
  if (!Array.isArray(qs)) return;
  qs = qs.filter(function (q) {
    return q && typeof q.q === 'string' && Array.isArray(q.choices) &&
      typeof q.answer === 'number' && q.choices[q.answer] !== undefined;
  });
  if (!qs.length) return;
  var list = ui.querySelector('.mq-list');
  var score = ui.querySelector('h2 small');
  var result = ui.querySelector('.mq-result');
  var picks = [];
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  // ---- 本文の該当箇所へ移動する。飛び先が閉じたタブや <details> の中なら先に開く
  function isShown(e) { return !!(e.offsetParent || e.getClientRects().length); }
  function controlFor(id) {
    var esc = window.CSS && CSS.escape ? CSS.escape(id) : id;
    var c = document.querySelector('[data-panel="' + esc + '"],[aria-controls="' + esc + '"],[data-target="#' + esc + '"],[href="#' + esc + '"]:not(.mq-ref)');
    if (c) return c;
    // onclick="switchTab('layers')" のように id の一部を渡すタブにも対応
    var keys = [id, id.replace(/^(panel|tab)[-_]/, '')];
    var all = document.querySelectorAll('[onclick]');
    for (var i = 0; i < all.length; i++) {
      var code = all[i].getAttribute('onclick');
      for (var k = 0; k < keys.length; k++) {
        if (code.indexOf("'" + keys[k] + "'") >= 0 || code.indexOf('"' + keys[k] + '"') >= 0) return all[i];
      }
    }
    return null;
  }
  function reveal(target) {
    var chain = [];
    for (var e = target; e && e !== document.body; e = e.parentElement) chain.unshift(e);
    chain.forEach(function (e) {
      if (e.tagName === 'DETAILS' && !e.open && e !== target) e.open = true;
      if (isShown(e)) return;
      var c = e.id && controlFor(e.id);
      if (c) c.click();
      if (!isShown(e) && e.hidden) e.hidden = false;
    });
  }
  function jump(id, smooth) {
    var target = document.getElementById(id);
    if (!target) return false;
    reveal(target);
    // 遠い飛び先までゆっくりスクロールすると待たされるので、画面 2 枚分より遠ければ一気に移動する
    var far = Math.abs(target.getBoundingClientRect().top) > innerHeight * 2;
    target.scrollIntoView({ behavior: smooth && !far ? 'smooth' : 'auto', block: 'start' });
    target.classList.add('mq-flash');
    setTimeout(function () { target.classList.remove('mq-flash'); }, 1800);
    return true;
  }
  // 本文の該当箇所（ref = "#id"）へのリンク
  function refLink(q, label) {
    if (typeof q.ref !== 'string' || !/^#[\w-]+$/.test(q.ref)) return null;
    var id = q.ref.slice(1);
    if (!document.getElementById(id)) return null;
    var a = el('a', 'mq-ref', label);
    a.href = q.ref;
    a.addEventListener('click', function (ev) {
      ev.preventDefault();
      if (history.replaceState) history.replaceState(null, '', q.ref);
      jump(id, true);
    });
    return a;
  }
  // クイズページなど他のページから page.html#id で来たとき
  if (/^#[\w-]+$/.test(location.hash) && location.hash !== '#memo-quiz-ui') {
    var initial = location.hash.slice(1);
    setTimeout(function () { jump(initial, false); }, 0);
  }
  function count() {
    var done = 0, ok = 0;
    picks.forEach(function (p, i) { if (p != null) { done++; if (p === qs[i].answer) ok++; } });
    return { done: done, ok: ok };
  }
  function showResult() {
    var c = count();
    result.textContent = '';
    var head = el('p', 'mq-score');
    head.appendChild(el('b', null, c.ok + ' / ' + qs.length));
    head.appendChild(document.createTextNode(' 問正解' +
      (c.ok === qs.length ? ' 🎉 全問正解！' : '（間違えた問題は本文で確認できます）')));
    result.appendChild(head);
    var ol = el('ol', 'mq-review');
    qs.forEach(function (q, i) {
      var ok = picks[i] === q.answer;
      var li = el('li', ok ? 'ok' : 'ng');
      var top = el('div', 'mq-rv-q');
      top.appendChild(el('b', ok ? 'ok' : 'ng', ok ? '⭕' : '❌'));
      top.appendChild(document.createTextNode(' Q' + (i + 1) + '. ' + q.q));
      li.appendChild(top);
      var ans = el('div', 'mq-rv-a');
      ans.appendChild(document.createTextNode('正解: ' + q.choices[q.answer]));
      if (!ok) ans.appendChild(document.createTextNode(' ／ あなたの答え: ' + q.choices[picks[i]]));
      li.appendChild(ans);
      if (!ok) {
        var link = refLink(q, '本文で確認する →');
        if (link) li.appendChild(link);
      }
      ol.appendChild(li);
    });
    result.appendChild(ol);
    result.hidden = false;
  }
  function update() {
    var c = count();
    score.textContent = c.done ? c.ok + ' / ' + c.done + ' 問正解' + (c.done < qs.length ? '（残り ' + (qs.length - c.done) + ' 問）' : '') : '全 ' + qs.length + ' 問';
    if (c.done === qs.length) showResult();
  }
  function render() {
    list.textContent = '';
    result.hidden = true;
    picks = qs.map(function () { return null; });
    qs.forEach(function (q, i) {
      var box = el('div', 'mq-q');
      box.appendChild(el('p', 'mq-prompt', 'Q' + (i + 1) + '. ' + q.q));
      var ch = el('div', 'mq-choices');
      var fb = el('p', 'mq-fb');
      fb.hidden = true;
      q.choices.forEach(function (c, j) {
        var b = el('button', 'mq-c', c);
        b.type = 'button';
        b.addEventListener('click', function () {
          var ok = j === q.answer;
          Array.prototype.forEach.call(ch.children, function (x, k) {
            x.disabled = true;
            if (k === q.answer) x.classList.add('mq-ok');
          });
          if (!ok) b.classList.add('mq-ng');
          fb.textContent = '';
          fb.appendChild(el('b', ok ? 'ok' : 'ng', ok ? '⭕ 正解' : '❌ 不正解'));
          fb.appendChild(document.createTextNode(
            (ok ? '' : '（正解: ' + q.choices[q.answer] + '）') + (q.explain ? ' ' + q.explain : '')));
          if (!ok) {
            var link = refLink(q, '本文で確認する →');
            if (link) { fb.appendChild(document.createTextNode(' ')); fb.appendChild(link); }
          }
          fb.hidden = false;
          picks[i] = j;
          update();
        });
        ch.appendChild(b);
      });
      box.appendChild(ch);
      box.appendChild(fb);
      list.appendChild(box);
    });
    update();
  }
  ui.querySelector('.mq-reset').addEventListener('click', function () {
    render();
    ui.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
  render();
  ui.hidden = false;
});
