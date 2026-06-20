/* Détection d'appel entrant (polling global) — bannière « Répondre / Refuser ». */
(function () {
  if (!document.body) return;
  var banner = document.createElement('div');
  banner.id = 'incoming-call';
  banner.style.cssText = 'position:fixed;right:16px;bottom:16px;z-index:9999;display:none';
  document.body.appendChild(banner);
  var current = null;

  function csrf() { var c = document.cookie.match(/csrftoken=([^;]+)/); return c ? c[1] : ''; }

  // --- Sonnerie (WebAudio) ---
  var actx = null, ringTimer = null;
  function tone(freq, start, dur) {
    var o = actx.createOscillator(), g = actx.createGain();
    o.frequency.value = freq; o.type = 'sine'; o.connect(g); g.connect(actx.destination);
    var t = actx.currentTime + start;
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(0.25, t + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.start(t); o.stop(t + dur + 0.02);
  }
  function startRing() {
    try { if (!actx) actx = new (window.AudioContext || window.webkitAudioContext)(); if (actx.state === 'suspended') actx.resume(); } catch (e) { return; }
    function cycle() { try { tone(880, 0, 0.25); tone(660, 0.32, 0.25); } catch (e) {} }
    cycle(); ringTimer = setInterval(cycle, 1800);
  }
  function stopRing() { if (ringTimer) { clearInterval(ringTimer); ringTimer = null; } }
  // Débloque l'audio au premier clic de l'utilisateur (politique navigateur).
  document.addEventListener('click', function () {
    try { if (!actx) actx = new (window.AudioContext || window.webkitAudioContext)(); if (actx.state === 'suspended') actx.resume(); } catch (e) {}
  }, { once: true });

  function show(call) {
    current = call.id;
    banner.innerHTML =
      '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:14px;box-shadow:0 12px 32px rgba(0,0,0,.2);padding:14px 16px;width:290px;font-family:Inter,system-ui,sans-serif">'
      + '<div style="font-size:12px;color:#64748b">📞 Appel ' + (call.mode === 'video' ? 'vidéo' : 'audio') + ' entrant</div>'
      + '<div style="font-weight:700;color:#0f172a;margin:3px 0 12px">' + call.from + (call.is_group ? ' · groupe « ' + call.title + ' »' : '') + '</div>'
      + '<div style="display:flex;gap:8px">'
      + '<a href="' + call.join + '" style="flex:1;text-align:center;background:#16a34a;color:#fff;text-decoration:none;padding:9px;border-radius:9px;font-weight:600">Répondre</a>'
      + '<button data-decline style="flex:1;background:#e11d48;color:#fff;border:0;padding:9px;border-radius:9px;cursor:pointer;font-weight:600">Refuser</button>'
      + '</div></div>';
    banner.style.display = 'block';
    startRing();
  }
  function hide() { banner.style.display = 'none'; current = null; stopRing(); }

  banner.addEventListener('click', function (e) {
    if (e.target.closest('[data-decline]') && current) {
      fetch('/messagerie/appel/' + current + '/refuser/', { method: 'POST', headers: { 'X-CSRFToken': csrf() } }).catch(function () {});
      hide();
    }
  });

  function poll() {
    // Ne sonde pas quand l'onglet est en arrière-plan (économise le serveur).
    if (document.hidden) return;
    fetch('/messagerie/appel/entrant/', { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { return r.json(); })
      .then(function (d) { if (d.call) { if (d.call.id !== current) show(d.call); } else hide(); })
      .catch(function () {});
  }
  // Permet à realtime.js (ping MQTT) de déclencher la vérification immédiatement.
  window.__incomingCallPoll = poll;
  // Sonde toutes les 5 s (un appel sonne ~45 s) : assez réactif pour ne pas rater
  // un appel entrant, tout en restant léger.
  setInterval(poll, 5000);
  // Vérifie aussi dès que l'utilisateur revient sur l'onglet / la fenêtre.
  document.addEventListener('visibilitychange', function () { if (!document.hidden) poll(); });
  window.addEventListener('focus', poll);
  poll();
})();
