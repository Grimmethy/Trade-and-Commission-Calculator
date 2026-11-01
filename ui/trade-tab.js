'use strict';

// Trade & Commission tab (manifest-driven, docs/PLUGIN_API.md in agent-manager).
// Lazy-starts the PRIVATE instance (TRADE_MODE=private, :7462) and embeds it. The public instance is a separate systemd service.
registerPluginTabRenderer('trade-calculator', async function renderTradeTab() {
  const main = document.getElementById('main');
  const url = 'http://' + location.hostname + ':7462/';
  if (main.querySelector('iframe.trade-frame') || main.querySelector('[data-trade-starting]')) return;
  main.innerHTML = '<div data-trade-starting style="padding:16px;color:var(--muted,#9a9aa2)">Starting the trade calculator...</div>';
  let ok = false, why = '';
  try {
    const r = await fetch('/api/plugins/trade-calculator/ensure-started', { method: 'POST' });
    const j = await r.json().catch(() => ({}));
    ok = r.ok && j.healthy !== false; why = r.ok ? 'the server did not become healthy in time' : (j.error || r.status);
  } catch (e) { why = String(e); }
  if (!ok) {
    main.innerHTML = `<div style="padding:16px"><strong>Trade calculator did not start</strong><p>${escapeAttr(String(why))}</p><p>Start it by hand: <code>cd /media/model-cache/github/trade-calculator &amp;&amp; ./run.sh</code></p></div>`;
    return;
  }
  main.innerHTML = `<iframe class="viz trade-frame" src="${escapeAttr(url)}" style="width:100%;height:calc(100vh - 120px);border:2px solid var(--border);border-radius:8px"></iframe>`;
});
