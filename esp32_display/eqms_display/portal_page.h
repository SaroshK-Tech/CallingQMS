// Configuration portal served by the ESP32 (AP mode: http://192.168.4.1/).
#pragma once

const char PORTAL_HTML[] PROGMEM = R"HTML(<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EQMS Display Setup</title>
<style>
  :root{
    --bg:#0b1220; --card:#111c30; --card2:#0e1728; --line:#22314a;
    --text:#e8eef8; --muted:#8da2c0; --accent:#38bdf8; --accent2:#22d3ee;
    --ok:#34d399; --err:#fb7185;
  }
  *{box-sizing:border-box}
  body{margin:0;min-height:100vh;font-family:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;
       background:radial-gradient(1200px 700px at 15% -10%,#12294a 0%,var(--bg) 55%);color:var(--text)}
  .wrap{max-width:760px;margin:0 auto;padding:28px 18px 60px}
  header{display:flex;align-items:center;gap:14px;margin-bottom:20px}
  .logo{width:48px;height:48px;border-radius:14px;display:grid;place-items:center;
        background:linear-gradient(135deg,var(--accent),var(--accent2));color:#06202e;font-weight:800;font-size:18px}
  h1{font-size:20px;margin:0}
  header p{margin:3px 0 0;color:var(--muted);font-size:13px}
  .card{background:linear-gradient(180deg,var(--card),var(--card2));border:1px solid var(--line);
        border-radius:18px;padding:20px;margin-bottom:16px;box-shadow:0 18px 40px rgba(0,0,0,.25)}
  h2{font-size:13px;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);margin:0 0 14px}
  .status{padding:12px 14px;border-radius:12px;background:#0a2a2f;border:1px solid #155e63;
          color:#a7f3d0;font-size:13px;line-height:1.5;word-break:break-word}
  .status code{color:#fff}
  label{display:block;font-size:13px;color:var(--muted);margin:14px 0 6px}
  input[type=text],input[type=password],input[type=number],select{
    width:100%;padding:12px 13px;border-radius:11px;border:1px solid var(--line);
    background:#081120;color:var(--text);font-size:15px;outline:none}
  input:focus,select:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(56,189,248,.15)}
  .row{display:grid;grid-template-columns:1fr 1fr;gap:14px}
  @media(max-width:560px){.row{grid-template-columns:1fr}}
  .hint{font-size:12px;color:var(--muted);margin-top:6px;line-height:1.4}
  .check{display:flex;gap:9px;align-items:center;margin-top:12px;font-size:13px;color:var(--muted)}
  .check input{width:17px;height:17px;accent-color:var(--accent)}
  .slider{display:flex;align-items:center;gap:14px}
  input[type=range]{flex:1;accent-color:var(--accent);height:4px}
  output{min-width:64px;text-align:right;font-variant-numeric:tabular-nums;color:var(--text);font-weight:600}
  .buttons{display:flex;flex-wrap:wrap;gap:10px;margin-top:22px}
  button{border:0;border-radius:11px;padding:12px 16px;font-size:14px;font-weight:600;cursor:pointer}
  .primary{background:linear-gradient(135deg,var(--accent),var(--accent2));color:#06202e}
  .ghost{background:#152238;color:var(--text);border:1px solid var(--line)}
  .danger{background:#2a1420;color:#fecdd3;border:1px solid #6b2238}
  button:active{transform:translateY(1px)}
  .msg{min-height:20px;font-size:13px;margin-top:14px}
  .msg.ok{color:var(--ok)} .msg.err{color:var(--err)}
  footer{text-align:center;color:var(--muted);font-size:12px;margin-top:26px;line-height:1.6}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="logo">Q</div>
    <div>
      <h1>EQMS Display Setup</h1>
      <p>ESP32 + P10 HUB12 counter display</p>
    </div>
  </header>

  <div class="card">
    <h2>Device</h2>
    <div class="status">%%STATUS%%</div>
  </div>

  <form id="cfg" autocomplete="off">
    <div class="card">
      <h2>Wi-Fi network</h2>
      <label for="ssid">Network name (SSID)</label>
      <input type="text" id="ssid" name="ssid" list="networks" value="%%SSID%%" placeholder="Scanning..." required>
      <datalist id="networks"></datalist>
      <div class="hint">Tap the field to choose a detected network, or type the name manually.</div>

      <label for="pass">Wi-Fi password</label>
      <input type="password" id="pass" name="pass" placeholder="%%PASS_PLACEHOLDER%%">
      <div class="check"><input type="checkbox" id="show"><span>Show password</span></div>
      <div class="check"><input type="checkbox" id="open" name="open" value="1"><span>Open network (no password)</span></div>
    </div>

    <div class="card">
      <h2>EQMS server</h2>
      <div class="row">
        <div>
          <label for="host">Server IP or hostname</label>
          <input type="text" id="host" name="host" value="%%HOST%%" placeholder="192.168.1.10" required>
        </div>
        <div>
          <label for="port">Port</label>
          <input type="number" id="port" name="port" value="%%PORT%%" min="1" max="65535" required>
        </div>
      </div>
      <div class="row">
        <div>
          <label for="counter">Counter ID</label>
          <input type="number" id="counter" name="counter" value="%%COUNTER%%" min="1" max="65535" required>
          <div class="hint">The numeric ID from Django admin / counter URL.</div>
        </div>
        <div>
          <label for="scale">Font size</label>
          <div class="slider">
            <input type="range" id="scale" name="scale" min="1" max="%%MAXSCALE%%" step="1" value="%%FONTSCALE%%">
            <output id="scaleOut">2x</output>
          </div>
          <div class="hint">2x fills the panel height. Text is shrunk automatically if a ticket is too wide.</div>
        </div>
      </div>
    </div>

    <div class="card">
      <h2>Panel</h2>
      <label for="bright">Brightness</label>
      <div class="slider">
        <input type="range" id="bright" name="bright" min="0" max="100" step="1" value="%%BRIGHTNESS%%">
        <output id="brightOut">%%BRIGHTNESS%%%</output>
      </div>
      <div class="hint">Changes are applied immediately when you press "Apply display settings".</div>
    </div>

    <div class="buttons">
      <button type="submit" class="primary">Save &amp; restart</button>
      <button type="button" class="ghost" id="apply">Apply display settings</button>
      <button type="button" class="ghost" id="reboot">Restart</button>
      <button type="button" class="danger" id="reset">Factory reset</button>
    </div>
    <div class="msg" id="msg"></div>
  </form>

  <footer>
    Configuration AP: <strong>%%APSSID%%</strong> &middot; password <strong>%%AP_PASSWORD%%</strong><br>
    Open <code>http://192.168.4.1/</code> while connected to that AP.
  </footer>
</div>

<script>
  const $ = (id) => document.getElementById(id);
  const msg = (text, ok) => { const el = $('msg'); el.textContent = text; el.className = 'msg ' + (ok ? 'ok' : 'err'); };
  const scaleNames = {1:'1x small', 2:'2x normal', 3:'3x large', 4:'4x extra large'};

  function paintScale(){ $('scaleOut').textContent = scaleNames[$('scale').value] || ($('scale').value + 'x'); }
  function paintBright(){ $('brightOut').textContent = $('bright').value + '%'; }

  $('scale').addEventListener('input', paintScale);
  $('bright').addEventListener('input', paintBright);
  $('show').addEventListener('change', () => { $('pass').type = $('show').checked ? 'text' : 'password'; });
  $('open').addEventListener('change', () => { $('pass').disabled = $('open').checked; });
  paintScale(); paintBright();

  // Populate the SSID suggestions from the ESP32 Wi-Fi scan.
  fetch('/scan').then(r => r.json()).then(list => {
    const dl = $('networks');
    dl.innerHTML = '';
    (list || []).forEach(net => {
      if (!net.ssid) return;
      const opt = document.createElement('option');
      opt.value = net.ssid;
      opt.label = net.ssid + (typeof net.rssi === 'number' ? '  (' + net.rssi + ' dBm)' : '');
      dl.appendChild(opt);
    });
    if (!$('ssid').value && list && list.length) $('ssid').value = list[0].ssid;
  }).catch(() => {});

  async function saveAll() {
    const data = new URLSearchParams();
    data.set('ssid', $('ssid').value.trim());
    data.set('pass', $('pass').disabled ? '' : $('pass').value);
    data.set('host', $('host').value.trim());
    data.set('port', $('port').value);
    data.set('counter', $('counter').value);
    data.set('bright', $('bright').value);
    data.set('scale', $('scale').value);
    data.set('open', $('open').checked ? '1' : '0');
    msg('Saving...', true);
    try {
      const r = await fetch('/save', {method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded'}, body:data});
      const j = await r.json();
      if (!j.ok) throw new Error(j.error || 'save failed');
      msg('Saved. Restarting...', true);
      setTimeout(() => fetch('/reboot').catch(() => {}), 1200);
    } catch (e) { msg('Could not save: ' + e.message, false); }
  }

  async function applyDisplay() {
    const data = new URLSearchParams();
    data.set('bright', $('bright').value);
    data.set('scale', $('scale').value);
    msg('Applying...', true);
    try {
      const r = await fetch('/apply', {method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded'}, body:data});
      const j = await r.json();
      if (!j.ok) throw new Error(j.error || 'apply failed');
      msg('Display settings applied.', true);
    } catch (e) { msg('Could not apply: ' + e.message, false); }
  }

  $('cfg').addEventListener('submit', (e) => { e.preventDefault(); saveAll(); });
  $('apply').addEventListener('click', applyDisplay);
  $('reboot').addEventListener('click', () => { if (confirm('Restart the display?')) { msg('Restarting...', true); fetch('/reboot').catch(() => {}); } });
  $('reset').addEventListener('click', () => {
    if (!confirm('Erase Wi-Fi and display settings and reboot?')) return;
    msg('Resetting...', true);
    fetch('/reset', {method:'POST'}).catch(() => {});
  });
</script>
</body>
</html>)HTML";
