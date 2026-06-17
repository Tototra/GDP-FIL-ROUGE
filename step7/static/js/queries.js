const STYLES = `
  .qblock{background:#16213e;border:1px solid #0f3460;border-radius:12px;margin-bottom:1.5rem;overflow:hidden}
  .qblock summary{padding:1rem 1.25rem;cursor:pointer;font-weight:600;color:#fff;
    display:flex;align-items:center;gap:.75rem;list-style:none}
  .qblock summary::-webkit-details-marker{display:none}
  .qblock[open] summary{border-bottom:1px solid #0f3460}
  .badge{background:#0f3460;color:#42D4F4;border-radius:6px;padding:.15rem .6rem;font-size:.75rem;font-weight:700;flex-shrink:0}
  .sparql-code{background:#0d0d1a;padding:1rem 1.25rem;font-family:monospace;font-size:.8rem;
    color:#aaccff;overflow-x:auto;border-bottom:1px solid #0f3460;white-space:pre;line-height:1.6}
  .results-wrap{overflow-x:auto}
  table{border-collapse:collapse;width:100%;font-size:.82rem}
  th{background:#0f3460;color:#42D4F4;padding:.5rem .9rem;text-align:left;white-space:nowrap}
  td{padding:.45rem .9rem;border-bottom:1px solid #0f346060;vertical-align:top;word-break:break-word}
  tr:last-child td{border-bottom:none}
  tr:nth-child(even) td{background:#16213e08}
  .empty{padding:1rem 1.25rem;color:#888;font-size:.85rem}
  .err{padding:1rem 1.25rem;color:#E6194B;font-size:.82rem;font-family:monospace}
  .row-count{color:#888;font-size:.75rem;padding:.5rem 1.25rem;border-top:1px solid #0f3460}
`;
const style = document.createElement('style');
style.textContent = STYLES;
document.head.appendChild(style);

function esc(s){ return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function renderBlock(q, idx) {
  const open = idx < 3 ? 'open' : '';
  let body = '';
  if (q.error) {
    body = `<div class="err">Erreur : ${esc(q.error)}</div>`;
  } else if (q.rows.length) {
    const thead = q.headers.map(h=>`<th>${esc(h)}</th>`).join('');
    const tbody = q.rows.map(r=>`<tr>${r.map(c=>`<td>${esc(c)}</td>`).join('')}</tr>`).join('');
    body = `<div class="results-wrap"><table><thead><tr>${thead}</tr></thead><tbody>${tbody}</tbody></table></div>
            <div class="row-count">${q.rows.length} résultat(s)</div>`;
  } else {
    body = `<div class="empty">Aucun résultat.</div>`;
  }
  return `<details class="qblock" ${open}>
    <summary><span class="badge">Q${idx+1}</span>${esc(q.name)}</summary>
    <div class="sparql-code">${esc(q.sparql)}</div>
    ${body}
  </details>`;
}

fetch('/api/queries')
  .then(r => r.json())
  .then(data => {
    document.getElementById('spinner').style.display = 'none';
    document.getElementById('loading-msg').textContent =
      `${data.length} requêtes exécutées — résultats mis en cache.`;
    setTimeout(() => {
      document.getElementById('loading-banner').style.display = 'none';
    }, 2500);
    document.getElementById('results-container').innerHTML =
      data.map((q, i) => renderBlock(q, i)).join('');
  })
  .catch(e => {
    document.getElementById('loading-msg').textContent = 'Erreur : ' + e;
  });
