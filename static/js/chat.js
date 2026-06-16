/* Messagerie LPM — interactions façon WhatsApp : bascule micro/envoi, Entrée pour
   envoyer, zone de saisie auto-extensible, émojis, et messages vocaux. */
(function () {
  var EMOJIS = ['😀','😁','😂','🤣','😊','😍','😘','😎','🤔','😅','🙂','😉','😢','😭','😡','👍','👎','🙏','👏','💪','🔥','🎉','✅','❌','❤️','💙','💯','😴','🤝','👌','🙌','😬','😱','🥳','🤩','😇','😋','🤗','😐','🫡'];

  function initComposer(form) {
    var fileInput = form.querySelector('input[type=file]');
    var input = form.querySelector('[data-input]');
    var mic = form.querySelector('[data-mic]');
    var send = form.querySelector('[data-send]');
    var label = form.querySelector('[data-mic-label]');
    var emojiBtn = form.querySelector('[data-emoji]');
    var pop = form.querySelector('[data-emoji-pop]');

    // --- bascule micro / envoi selon le contenu ---
    function refresh() {
      if (!mic || !send || !input) return;
      var has = input.value.trim().length > 0;
      send.classList.toggle('hidden', !has);
      send.classList.toggle('flex', has);
      mic.classList.toggle('hidden', has);
      mic.classList.toggle('flex', !has);
    }
    if (input) {
      input.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        refresh();
      });
      // Entrée = envoyer, Maj+Entrée = nouvelle ligne
      input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
          if (this.value.trim().length) { e.preventDefault(); form.submit(); }
        }
      });
    }
    refresh();

    // --- émojis ---
    if (emojiBtn && pop && input) {
      pop.innerHTML = '<div style="display:grid;grid-template-columns:repeat(8,1fr)">' +
        EMOJIS.map(function (e) { return '<button type="button" data-e="' + e + '">' + e + '</button>'; }).join('') + '</div>';
      emojiBtn.addEventListener('click', function (ev) { ev.stopPropagation(); pop.classList.toggle('show'); });
      pop.addEventListener('click', function (ev) {
        var b = ev.target.closest('[data-e]'); if (!b) return;
        var s = input.selectionStart || input.value.length, en = input.selectionEnd || input.value.length;
        input.value = input.value.slice(0, s) + b.getAttribute('data-e') + input.value.slice(en);
        input.focus(); refresh();
      });
      document.addEventListener('click', function (ev) {
        if (!pop.contains(ev.target) && ev.target !== emojiBtn && !emojiBtn.contains(ev.target)) pop.classList.remove('show');
      });
    }

    // --- message vocal ---
    if (!mic || !fileInput) return;
    var voiceBar = form.querySelector('[data-voice-bar]');
    var voiceAudio = form.querySelector('[data-voice-audio]');
    var voiceCancel = form.querySelector('[data-voice-cancel]');
    var rec = null, chunks = [], stream = null, timer = null, t0 = 0, blobUrl = null;

    function clearVoice() {
      var dt = new DataTransfer(); fileInput.files = dt.files;
      if (voiceBar) { voiceBar.classList.add('hidden'); voiceBar.classList.remove('flex'); }
      if (blobUrl) { URL.revokeObjectURL(blobUrl); blobUrl = null; }
      if (voiceAudio) voiceAudio.removeAttribute('src');
    }
    if (voiceCancel) voiceCancel.addEventListener('click', clearVoice);
    function reset() {
      mic.classList.remove('bg-red-600', 'animate-pulse');
      mic.classList.add('bg-lpm');
      mic.innerHTML = '<i class="fa-solid fa-microphone"></i>';
      if (label) label.textContent = '';
      if (timer) { clearInterval(timer); timer = null; }
    }
    mic.addEventListener('click', async function () {
      if (rec && rec.state === 'recording') { rec.stop(); return; }
      if (!navigator.mediaDevices || !window.MediaRecorder) { alert("Enregistrement vocal non supporté par ce navigateur."); return; }
      if (!window.isSecureContext && location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') {
        alert("Le micro nécessite une connexion sécurisée (HTTPS)."); return;
      }
      try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
      catch (e) { alert("Accès au micro refusé ou indisponible."); return; }
      chunks = [];
      rec = new MediaRecorder(stream);
      rec.ondataavailable = function (e) { if (e.data && e.data.size) chunks.push(e.data); };
      rec.onstop = function () {
        try {
          var blob = new Blob(chunks, { type: 'audio/webm' });
          var file = new File([blob], 'voix-' + Date.now() + '.webm', { type: 'audio/webm' });
          var dt = new DataTransfer(); dt.items.add(file); fileInput.files = dt.files;
          // Aperçu : l'utilisateur écoute puis décide d'envoyer ou d'annuler.
          blobUrl = URL.createObjectURL(blob);
          if (voiceAudio) voiceAudio.src = blobUrl;
          if (voiceBar) { voiceBar.classList.remove('hidden'); voiceBar.classList.add('flex'); }
        } catch (e) {}
        if (stream) stream.getTracks().forEach(function (t) { t.stop(); });
        reset();
      };
      rec.start(); t0 = Date.now();
      mic.classList.remove('bg-lpm'); mic.classList.add('bg-red-600', 'animate-pulse');
      mic.innerHTML = '<i class="fa-solid fa-stop"></i>';
      if (label) timer = setInterval(function () {
        var s = Math.floor((Date.now() - t0) / 1000);
        label.textContent = '● ' + Math.floor(s / 60) + ':' + ('0' + (s % 60)).slice(-2) + ' — appuyez pour envoyer';
      }, 200);
    });
  }
  document.querySelectorAll('form[data-composer]').forEach(initComposer);

  // --- Menu par message / Répondre / Copier (délégation globale) ---
  function closeMenus() { document.querySelectorAll('[data-menu]').forEach(function (m) { m.classList.add('hidden'); }); }
  document.addEventListener('click', function (ev) {
    var btn = ev.target.closest('[data-menu-btn]');
    if (btn) {
      ev.stopPropagation();
      var menu = btn.parentElement.querySelector('[data-menu]');
      var wasOpen = menu && !menu.classList.contains('hidden');
      closeMenus();
      if (menu && !wasOpen) {
        menu.classList.remove('hidden');
        // Position fixe calculée pour échapper au rognage du conteneur scrollable.
        var r = btn.getBoundingClientRect();
        var mh = menu.offsetHeight, mw = menu.offsetWidth;
        var top = r.top - mh - 4; if (top < 8) top = r.bottom + 4;
        var left = r.left; if (left + mw > window.innerWidth - 8) left = window.innerWidth - mw - 8;
        menu.style.position = 'fixed';
        menu.style.top = top + 'px';
        menu.style.left = left + 'px';
        menu.style.right = 'auto';
        menu.style.bottom = 'auto';
      }
      return;
    }
    var reply = ev.target.closest('[data-reply]');
    if (reply) {
      ev.preventDefault();
      var form = document.querySelector('form[data-composer]'); if (!form) return;
      form.querySelector('[data-reply-input]').value = reply.getAttribute('data-id');
      form.querySelector('[data-reply-name]').textContent = reply.getAttribute('data-name');
      form.querySelector('[data-reply-text]').textContent = reply.getAttribute('data-text');
      var bar = form.querySelector('[data-reply-bar]');
      bar.classList.remove('hidden'); bar.classList.add('flex');
      var inp = form.querySelector('[data-input]'); if (inp) inp.focus();
      closeMenus();
      return;
    }
    var jump = ev.target.closest('[data-jump]');
    if (jump) {
      ev.preventDefault();
      var el = document.getElementById(jump.getAttribute('data-jump'));
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        el.style.backgroundColor = 'rgba(1,150,242,.18)';
        setTimeout(function () { el.style.backgroundColor = ''; }, 1600);
      }
      return;
    }
    var cp = ev.target.closest('[data-copy]');
    if (cp) {
      ev.preventDefault();
      var txt = cp.getAttribute('data-copy');
      if (navigator.clipboard) navigator.clipboard.writeText(txt);
      closeMenus();
      return;
    }
    closeMenus();
  });
  document.addEventListener('click', function (ev) {
    var c = ev.target.closest('[data-reply-cancel]');
    if (!c) return;
    var form = c.closest('form[data-composer]');
    form.querySelector('[data-reply-input]').value = '';
    var bar = form.querySelector('[data-reply-bar]');
    bar.classList.add('hidden'); bar.classList.remove('flex');
  });

  // --- Temps réel par polling (messages instantanés + saisie + présence) ---
  var thread = document.getElementById('thread');
  if (thread && thread.dataset.pollKind) {
    var kind = thread.dataset.pollKind, pk = thread.dataset.pollPk;
    var lastId = parseInt(thread.dataset.lastId || '0', 10);
    var form = document.querySelector('form[data-composer]');
    var csrf = form ? form.querySelector('[name=csrfmiddlewaretoken]').value : '';
    var typingEl = document.querySelector('[data-typing]');
    var presenceEl = document.querySelector('[data-presence]');
    var esc = function (s) { var d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; };
    var atBottom = function () { return thread.scrollHeight - thread.scrollTop - thread.clientHeight < 90; };

    function bubble(m) {
      var w = document.createElement('div');
      if (m.is_system) {
        w.className = 'flex justify-center my-2';
        w.innerHTML = '<span class="bg-white/85 text-slate-500 text-[11px] font-medium px-3 py-1 rounded-lg shadow-sm inline-flex items-center gap-1.5">' +
          '<i class="fa-solid fa-user-plus text-slate-400"></i> ' + esc(m.body) + '</span>';
        return w;
      }
      if (m.is_call) {
        w.className = 'flex justify-center my-2';
        var red = /manqu|refus/.test(m.body), term = /termin/.test(m.body);
        var color = red ? 'text-red-600' : (term ? 'text-lpm' : 'text-emerald-600');
        var icon = /vid[ée]o/.test(m.body) ? 'fa-video' : 'fa-phone';
        var txt = esc(m.body.replace(/^📞\s*/, ''));
        w.innerHTML = '<span class="bg-white border border-slate-200 rounded-full px-3 py-1 text-xs shadow-sm inline-flex items-center gap-1.5 ' +
          color + '"><i class="fa-solid ' + icon + '"></i> ' + txt + ' · ' + m.time + '</span>';
        return w;
      }
      w.className = 'flex items-end gap-1.5 ' + (m.mine ? 'justify-end' : '');
      var html = '';
      if (!m.mine && m.is_group) {
        html += m.avatar ? '<img src="' + m.avatar + '" class="h-7 w-7 rounded-full object-cover">'
          : '<span class="h-7 w-7 rounded-full lpm-gradient text-white text-[10px] font-bold flex items-center justify-center">' + esc(m.initials) + '</span>';
      }
      var b = '<div class="rounded-lg px-2.5 py-1.5 shadow-sm max-w-[78%] ' + (m.mine ? 'wa-out rounded-tr-none' : 'wa-in rounded-tl-none') + '">';
      if (m.is_group && !m.mine) b += '<div class="text-[12px] font-semibold text-lpm mb-0.5">' + esc(m.name) + '</div>';
      if (m.is_forwarded) b += '<div class="text-[11px] italic text-slate-400 mb-0.5"><i class="fa-solid fa-share"></i> Transféré' + (m.is_group ? ' par ' + esc(m.name) : '') + '</div>';
      if (m.att && m.att.url) {
        if (m.att.is_audio) b += '<audio src="' + m.att.url + '" controls preload="metadata" class="mt-1 w-60 max-w-full"></audio>';
        else if (m.att.is_image) b += '<a href="' + m.att.url + '" target="_blank"><img src="' + m.att.url + '" class="rounded-md max-h-60 max-w-full"></a>';
        else b += '<a href="' + m.att.url + '" download class="text-lpm hover:underline text-sm"><i class="fa-solid fa-paperclip"></i> ' + esc(m.att.ext) + '</a>';
      }
      if (m.body) b += '<span class="text-sm whitespace-pre-line text-slate-800">' + esc(m.body) + '</span>';
      b += '<span class="float-right ml-2 mt-1 text-[10px] text-slate-400">' + m.time + '</span><div class="clear-both"></div></div>';
      w.innerHTML = html + b;
      return w;
    }

    function poll() {
      fetch('/messagerie/flux/' + kind + '/' + pk + '/?after=' + lastId, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d.messages && d.messages.length) {
            var stick = atBottom();
            d.messages.forEach(function (m) { if (m.id > lastId) { thread.appendChild(bubble(m)); lastId = m.id; } });
            if (stick) thread.scrollTop = thread.scrollHeight;
          }
          // « Supprimé pour tout le monde » → remplace la bulle par une trace, en direct.
          if (d.deleted_all) {
            d.deleted_all.forEach(function (id) {
              var el = document.getElementById('msg-' + id);
              if (el && !el.dataset.tomb) {
                el.dataset.tomb = '1';
                el.innerHTML = '<span class="rounded-lg px-3 py-1.5 text-xs italic text-slate-400 bg-white/70 border border-slate-200 inline-flex items-center gap-1.5"><i class="fa-solid fa-ban"></i> Ce message a été supprimé</span>';
              }
            });
          }
          if (typingEl) {
            if (d.typing && d.typing.length) {
              typingEl.textContent = d.typing.join(', ') + (d.typing.length > 1 ? ' écrivent…' : ' écrit…');
              typingEl.classList.remove('hidden');
            } else typingEl.classList.add('hidden');
          }
          if (presenceEl) {
            presenceEl.innerHTML = d.online
              ? '<span class="text-emerald-500 font-medium">● en ligne</span>'
              : '<span class="text-slate-400">● hors ligne</span>';
          }
        }).catch(function () {});
    }
    poll();                  // 1er rafraîchissement immédiat
    setInterval(poll, 1500); // puis toutes les 1,5 s → quasi temps réel

    if (form) {
      var input = form.querySelector('[data-input]'), lastPing = 0;
      if (input) input.addEventListener('input', function () {
        // Signale la saisie sans attendre : ping immédiat puis limité à ~1,2 s.
        var now = Date.now(); if (now - lastPing < 1200) return; lastPing = now;
        fetch('/messagerie/ecrit/' + kind + '/' + pk + '/', { method: 'POST', headers: { 'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest' } }).catch(function () {});
      });
    }
  }
})();
