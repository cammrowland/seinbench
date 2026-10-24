// Shared bits for every SeinBench page.
const SB = (() => {
  const OWNER = 'cammrowland';
  const REPO = 'seinbench';

  // Best (1) to worst (5). A verdict is a 0–100 SeinScore; the tier is the band it falls in.
  // To move a band, change its `min` (each band runs up to the next one's min - 1).
  const TIERS = [
    { n: 1, min: 90, name: 'Gold, Jerry! Gold!', icon: '🏆', desc: 'Indistinguishable from a lost season-five script. Statistically significant. Would interrupt a dinner party to describe it.' },
    { n: 2, min: 75, name: 'Real and Spectacular', icon: '✨', desc: 'Strong performance across all four storylines. The threads tie together. Would watch in syndication.' },
    { n: 3, min: 60, name: 'Giddyup!', icon: '🐎', desc: 'Competent and enthusiastic. Kramer-level energy, Kramer-level plotting. Some jokes land through the door.' },
    { n: 4, min: 40, name: "That's a Shame", icon: '😔', desc: 'Jokes were detected, but not enough to fill twenty-two minutes. The characters are wearing their names like a costume.' },
    { n: 5, min: 0, name: 'It Stinks!', icon: '🦨', desc: 'Hugging occurred. Lessons were learned. Automatic disqualification under the original rules of the show.' },
  ];
  TIERS.forEach((t, i) => { t.max = i ? TIERS[i - 1].min - 1 : 100; t.mid = Math.round((t.min + t.max) / 2); });

  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const tier = (n) => TIERS.find((t) => t.n === n);
  const trackGradient = () => `linear-gradient(to right, ${TIERS.slice().reverse().map((t) => `var(--tier-${t.n}) ${t.min}% ${t.max + 1}%`).join(', ')})`;
  const tierFor = (score) => TIERS.find((t) => score >= t.min).n;
  // Verdicts from before scores existed only have a tier; count them at the middle of their band.
  const scoreOf = (e) => (e.score != null ? e.score : e.rating ? tier(e.rating).mid : null);
  const fmtScore = (s) => (s == null ? '—' : Number.isInteger(s) ? String(s) : s.toFixed(1));

  function badge(n, large = false) {
    const lg = large ? ' lg' : '';
    if (!n) return `<span class="tier pending${lg}">Verdict pending</span>`;
    const t = tier(n);
    return `<span class="tier${lg}" style="--tc:var(--tier-${n})"><i aria-hidden="true">${t.icon}</i>${esc(t.name)}</span>`;
  }

  async function getJSON(path) {
    const res = await fetch(`${path}?v=${Date.now()}`, { cache: 'no-store' });
    if (!res.ok) throw new Error(`${path}: ${res.status}`);
    return res.json();
  }
  async function getText(path) {
    const res = await fetch(`${path}?v=${Date.now()}`, { cache: 'no-store' });
    return res.ok ? res.text() : '';
  }

  const modelUrl = (id) => `model.html?m=${encodeURIComponent(id)}`;
  const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—');
  const fmtCost = (c) => (c == null ? '—' : c < 0.01 ? `$${c.toFixed(4)}` : `$${c.toFixed(2)}`);
  const lab = (id) => ({ openai: 'OpenAI', anthropic: 'Anthropic', google: 'Google', 'meta-llama': 'Meta', meta: 'Meta', 'x-ai': 'xAI', mistralai: 'Mistral', deepseek: 'DeepSeek', qwen: 'Qwen', moonshotai: 'Moonshot', 'z-ai': 'Z.ai' }[id.split('/')[0]] || id.split('/')[0]);

  // One leaderboard row per model; a model with several judged episodes gets its average score.
  function aggregate(episodes) {
    const byModel = new Map();
    for (const e of episodes.filter((e) => scoreOf(e) != null)) {
      if (!byModel.has(e.model)) byModel.set(e.model, []);
      byModel.get(e.model).push(e);
    }
    const rows = [...byModel.entries()].map(([model, eps]) => {
      eps.sort((a, b) => (b.ratedAt || '').localeCompare(a.ratedAt || ''));
      const score = Math.round((eps.reduce((s, e) => s + scoreOf(e), 0) / eps.length) * 10) / 10;
      return { model, name: eps[0].modelName || model, lab: lab(model), score, tier: tierFor(score), latest: eps[0], count: eps.length };
    });
    rows.sort((a, b) => b.score - a.score || (b.latest.ratedAt || '').localeCompare(a.latest.ratedAt || ''));
    rows.forEach((r, i) => { r.rank = i > 0 && rows[i - 1].score === r.score ? rows[i - 1].rank : i + 1; });
    return rows;
  }

  // Turn whatever script format a model produced into screenplay-ish HTML.
  function renderScene(text) {
    const out = [];
    let inDialogue = false;
    const cueRe = /^[A-Z][A-Z0-9 .'’\-]{0,24}(\s*\((V\.O\.|O\.S\.|O\.C\.|CONT'D|CONT’D|[^)]{1,20})\))?$/;
    for (const raw of String(text || '').replace(/\r/g, '').split('\n')) {
      const line = raw.trim().replace(/^#+\s*/, '').replace(/\*\*|__/g, '').replace(/^\*(.+)\*$/, '$1').trim();
      if (!line) { inDialogue = false; out.push('<div class="sp-gap"></div>'); continue; }
      if (/^(INT\.|EXT\.|INT\/EXT|I\/E\.|COLD OPEN|FADE (IN|OUT)|CUT TO|SMASH CUT|DISSOLVE|END OF|THE END)/i.test(line)) {
        inDialogue = false; out.push(`<p class="sp-slug">${esc(line)}</p>`); continue;
      }
      const inline = line.match(/^([A-Z][A-Za-z0-9 .'’\-]{0,24}?)(\s*\([^)]{1,30}\))?\s*:\s*(.+)$/);
      if (inline && inline[1].trim().split(/\s+/).length <= 3) {
        out.push(`<p class="sp-cue">${esc(inline[1].trim())}${inline[2] ? ' ' + esc(inline[2].trim()) : ''}</p>`);
        let rest = inline[3];
        const paren = rest.match(/^(\([^)]*\))\s*(.*)$/);
        if (paren) { out.push(`<p class="sp-paren">${esc(paren[1])}</p>`); rest = paren[2]; }
        if (rest) out.push(`<p class="sp-dialogue">${esc(rest)}</p>`);
        inDialogue = false;
        continue;
      }
      if (cueRe.test(line) && line === line.toUpperCase() && /[A-Z]/.test(line)) {
        inDialogue = true; out.push(`<p class="sp-cue">${esc(line)}</p>`); continue;
      }
      if (/^\(.*\)$/.test(line)) { out.push(`<p class="${inDialogue ? 'sp-paren' : 'sp-action'}">${esc(line)}</p>`); continue; }
      out.push(`<p class="${inDialogue ? 'sp-dialogue' : 'sp-action'}">${esc(line)}</p>`);
    }
    return out.join('');
  }

  function chrome(active) {
    const letters = [['S', -6, 2], ['e', 5, -3], ['i', -3, 1], ['n', 6, -2], ['B', -5, 3, 'b'], ['e', 4, -2, 'b'], ['n', -4, 2, 'b'], ['c', 3, -3, 'b'], ['h', -2, 1, 'b']];
    const logo = letters.map(([ch, r, y, c]) => `<span${c ? ` class="${c}"` : ''} style="--r:${r}deg;--y:${y}px">${ch}</span>`).join('');
    const nav = [['index.html', 'Leaderboard', 'board'], ['index.html#scale', 'The Scale', 'scale'], ['index.html#methodology', 'Methodology', 'method']]
      .map(([href, label, key]) => `<a href="${href}"${key === active ? ' aria-current="page"' : ''}>${label}</a>`).join('');
    document.querySelector('#site-header').innerHTML = `
      <div class="wrap">
        <a class="logo" href="index.html" aria-label="SeinBench home">${logo}<span class="ver">v1.0</span></a>
        <nav class="site-nav" aria-label="Main">${nav}</nav>
      </div>`;
    document.querySelector('#site-footer').innerHTML = `
      <div class="wrap">
        <p>SeinBench is a fan-made parody. Not affiliated with Seinfeld, its creators, Castle Rock, Sony, NBC, OpenRouter, or any AI lab.</p>
        <p>No models were harmed in the making of this benchmark. Several were embarrassed. · <a href="writers-room.html">Writers' Room</a> (staff only. That means you, Jerry.)</p>
      </div>`;
  }

  return { OWNER, REPO, TIERS, esc, tier, tierFor, scoreOf, fmtScore, trackGradient, badge, getJSON, getText, modelUrl, fmtDate, fmtCost, lab, aggregate, renderScene, chrome };
})();
