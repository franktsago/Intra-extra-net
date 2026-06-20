/* Temps réel LPM — messages, appels et notifications « poussés » sans rafraîchir.

   Architecture : chaque navigateur s'abonne à son topic MQTT et reçoit de petits
   « pings » (identifiants uniquement, jamais de contenu) publiés par les autres
   navigateurs. À réception → on récupère la donnée réelle depuis Django (authentifié),
   on joue un son, on affiche une notification in-app + une notification système.
   Un sondage léger sert de repli si MQTT est indisponible. */
(function () {
  var CFG = window.LPM_RT || {};
  if (!CFG.uid) return;
  var UID = String(CFG.uid);
  var PREFIX = CFG.prefix || 'lpm';
  var topicFor = function (uid) { return PREFIX + '/u/' + uid; };

  // ---------------------------------------------------------------- son
  var actx = null;
  function unlockAudio() { try { if (!actx) actx = new (window.AudioContext || window.webkitAudioContext)(); if (actx.state === 'suspended') actx.resume(); } catch (e) {} }
  function ding(kind) {
    try {
      if (!actx) return;
      var seq = kind === 'call' ? [[880, 0], [660, 0.18], [880, 0.36]] : [[740, 0], [988, 0.12]];
      seq.forEach(function (p) {
        var o = actx.createOscillator(), g = actx.createGain(), t = actx.currentTime + p[1];
        o.frequency.value = p[0]; o.type = 'sine'; o.connect(g); g.connect(actx.destination);
        g.gain.setValueAtTime(0.0001, t);
        g.gain.exponentialRampToValueAtTime(0.22, t + 0.02);
        g.gain.exponentialRampToValueAtTime(0.0001, t + 0.22);
        o.start(t); o.stop(t + 0.24);
      });
    } catch (e) {}
  }

  // ---------------------------------------------------------------- toast in-app
  var host = null;
  function toastHost() {
    if (host) return host;
    host = document.createElement('div');
    host.style.cssText = 'position:fixed;right:14px;bottom:14px;z-index:10000;display:flex;flex-direction:column;gap:8px;max-width:330px';
    document.body.appendChild(host);
    return host;
  }
  function toast(title, body, url, color) {
    var el = document.createElement('div');
    el.style.cssText = 'background:#fff;border:1px solid #e2e8f0;border-left:4px solid ' + (color || '#0073DE') +
      ';border-radius:12px;box-shadow:0 10px 28px rgba(0,0,0,.16);padding:11px 13px;font-family:Inter,system-ui,sans-serif;cursor:pointer;opacity:0;transform:translateY(8px);transition:.18s';
    el.innerHTML = '<div style="font-weight:600;color:#0f172a;font-size:13px">' + esc(title) + '</div>' +
      (body ? '<div style="color:#475569;font-size:12px;margin-top:2px">' + esc(body) + '</div>' : '');
    el.onclick = function () { if (url) location.href = url; el.remove(); };
    toastHost().appendChild(el);
    requestAnimationFrame(function () { el.style.opacity = '1'; el.style.transform = 'none'; });
    setTimeout(function () { el.style.opacity = '0'; setTimeout(function () { el.remove(); }, 200); }, 6000);
  }
  function esc(s) { var d = document.createElement('div'); d.textContent = s == null ? '' : s; return d.innerHTML; }

  // ---------------------------------------------------------------- notification système (tél + PC)
  function sysNotify(title, body, url, tag) {
    try {
      if (!('Notification' in window) || Notification.permission !== 'granted') return;
      if (!document.hidden) return;          // si l'onglet est visible, le toast suffit
      var n = new Notification(title, { body: body || '', tag: tag || 'lpm', icon: '/static/img/favicon.png', renotify: true });
      n.onclick = function () { window.focus(); if (url) location.href = url; n.close(); };
    } catch (e) {}
  }
  function askPermission() {
    try { if ('Notification' in window && Notification.permission === 'default') Notification.requestPermission(); } catch (e) {}
  }
  document.addEventListener('click', function () { unlockAudio(); askPermission(); }, { once: true });
  document.addEventListener('keydown', function () { unlockAudio(); }, { once: true });

  // ---------------------------------------------------------------- badges
  function setBadge(id, n) {
    var el = document.getElementById(id);
    if (!el) return;
    if (n > 0) { el.textContent = n > 99 ? '99+' : n; el.style.display = ''; }
    else { el.style.display = 'none'; }
  }
  function bump(id) {
    var el = document.getElementById(id);
    if (!el) return;
    var n = parseInt(el.textContent || '0', 10) || 0;
    setBadge(id, n + 1);
  }

  // ---------------------------------------------------------------- gestion des pings
  function onPing(p) {
    if (!p || !p.k) return;
    if (p.k === 'msg') {
      ding('msg');
      bump('msg-badge');
      var poll = window.__chatPoll;
      if (typeof poll === 'function') poll();                 // affiche le message tout de suite si le fil est ouvert
      if (!isThreadOpen(p.c)) {
        toast('Nouveau message', 'Ouvrir la messagerie', '/messagerie/', '#0073DE');
        sysNotify('Nouveau message LPM', '', '/messagerie/', 'msg');
      }
    } else if (p.k === 'call') {
      ding('call');
      if (window.__incomingCallPoll) window.__incomingCallPoll();  // bannière « Répondre » immédiate
      toast('Appel entrant', 'Ouvrir la messagerie', '/messagerie/', '#16a34a');
      sysNotify('Appel entrant LPM', '', '/messagerie/', 'call');
    } else if (p.k === 'notif') {
      pollNotifs();                                            // récupère le contenu réel (son/toast gérés là)
    }
  }
  function isThreadOpen(conv) {
    var t = document.getElementById('thread');
    return t && conv && t.dataset && (t.dataset.pollKind + t.dataset.pollPk) === String(conv);
  }

  // ---------------------------------------------------------------- MQTT
  var client = null;
  function connectMqtt() {
    if (!CFG.mqtt || !window.mqtt) return;
    try {
      client = window.mqtt.connect(CFG.mqtt, {
        clientId: 'lpm_' + UID + '_' + Math.random().toString(16).slice(2, 8),
        keepalive: 45, reconnectPeriod: 4000, connectTimeout: 8000, clean: true,
      });
      client.on('connect', function () { client.subscribe(topicFor(UID)); });
      client.on('message', function (_t, payload) {
        try { onPing(JSON.parse(payload.toString())); } catch (e) {}
      });
      client.on('error', function () { try { client.end(true); } catch (e) {} });
    } catch (e) { client = null; }
  }
  // Publication d'un ping vers un (ou des) destinataire(s).
  window.lpmPublish = function (uid, data) {
    if (!client || !uid) return;
    try { client.publish(topicFor(uid), JSON.stringify(data), { qos: 0 }); } catch (e) {}
  };
  window.lpmPublishMany = function (uids, data) {
    (uids || []).forEach(function (u) { window.lpmPublish(u, data); });
  };

  // ---------------------------------------------------------------- notifications (repli + contenu réel)
  var lastNotifId = parseInt(CFG.lastNotifId || '0', 10);
  function pollNotifs() {
    fetch('/notifications/flux/?after=' + lastNotifId, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        setBadge('notif-badge', d.unread || 0);
        if (d.new && d.new.length) {
          ding('notif');
          d.new.forEach(function (n) {
            if (n.id > lastNotifId) lastNotifId = n.id;
            var color = n.level === 'WARNING' || n.level === 'ERROR' ? '#e11d48' : (n.level === 'SUCCESS' ? '#16a34a' : '#0073DE');
            toast(n.title, n.message, n.url || '/notifications/', color);
            sysNotify(n.title, n.message, n.url || '/notifications/', 'notif-' + n.id);
          });
        } else if (typeof d.last_id === 'number' && d.last_id > lastNotifId) {
          lastNotifId = d.last_id;  // synchronise sans alerter (au 1er chargement)
        }
      }).catch(function () {});
  }

  // ---------------------------------------------------------------- démarrage
  connectMqtt();
  // 1er passage silencieux pour caler lastNotifId, puis sondage de repli toutes les 12 s.
  if (!lastNotifId) lastNotifId = 0;
  setInterval(function () { if (!document.hidden) pollNotifs(); }, 12000);
  document.addEventListener('visibilitychange', function () { if (!document.hidden) pollNotifs(); });
})();
