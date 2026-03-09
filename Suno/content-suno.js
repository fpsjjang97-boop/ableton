(() => {
  'use strict';

  // ─── State ───
  var selectedSongs = new Map();
  var panelInjected = false;

  // ═══════════════════════════════════════
  //  FIELD DETECTION (label-based)
  //  Finds inputs by looking at nearby label text
  // ═══════════════════════════════════════

  function findAllPageFields() {
    var fields = {
      lyrics: null,       // textarea for lyrics
      style: null,        // input for Style of Music
      title: null,        // input for Title
      exclude: null,      // input for Exclude Styles
      sliders: {}         // weirdness, styleInfluence, audioInfluence
    };

    // Find textareas - the lyrics field is the main/largest textarea
    var textareas = document.querySelectorAll('textarea');
    for (var i = 0; i < textareas.length; i++) {
      var ta = textareas[i];
      var taLabel = getLabelText(ta);
      if (taLabel.includes('lyric') || taLabel.includes('가사') ||
          ta.placeholder.toLowerCase().includes('lyric') ||
          ta.placeholder.toLowerCase().includes('write')) {
        fields.lyrics = ta;
        break;
      }
    }
    // Fallback: first visible textarea
    if (!fields.lyrics && textareas.length > 0) {
      for (var t = 0; t < textareas.length; t++) {
        if (textareas[t].offsetParent !== null) {
          fields.lyrics = textareas[t];
          break;
        }
      }
    }

    // Find text inputs
    var inputs = document.querySelectorAll('input[type="text"], input:not([type])');
    for (var j = 0; j < inputs.length; j++) {
      var inp = inputs[j];
      if (inp.offsetParent === null) continue; // skip hidden
      var label = getLabelText(inp);
      var ph = (inp.placeholder || '').toLowerCase();

      // Exclude Styles field
      if (label.includes('exclude') || label.includes('제외') ||
          ph.includes('exclude') || ph.includes('제외')) {
        fields.exclude = inp;
        continue;
      }

      // Style of Music field (NOT exclude)
      if (label.includes('style') || label.includes('스타일') ||
          ph.includes('style') || ph.includes('genre') ||
          label.includes('genre') || label.includes('장르')) {
        if (!fields.style) fields.style = inp;
        continue;
      }

      // Title field
      if (label.includes('title') || label.includes('제목') ||
          ph.includes('title') || ph.includes('제목')) {
        fields.title = inp;
        continue;
      }
    }

    // Find sliders
    var sliders = document.querySelectorAll('input[type="range"]');
    for (var k = 0; k < sliders.length; k++) {
      var slider = sliders[k];
      var sLabel = getLabelText(slider);
      if (sLabel.includes('weird')) {
        fields.sliders.weirdness = slider;
      } else if (sLabel.includes('style') && sLabel.includes('influ')) {
        fields.sliders.styleInfluence = slider;
      } else if (sLabel.includes('audio') && sLabel.includes('influ')) {
        fields.sliders.audioInfluence = slider;
      }
    }
    // Fallback: assign by position
    if (sliders.length >= 3 && !fields.sliders.weirdness) {
      fields.sliders.weirdness = sliders[0];
      fields.sliders.styleInfluence = sliders[1];
      fields.sliders.audioInfluence = sliders[2];
    }

    return fields;
  }

  function getLabelText(el) {
    var text = '';

    // 1) aria-label
    text = (el.getAttribute('aria-label') || '').toLowerCase();
    if (text.length > 2) return text;

    // 2) Associated <label>
    var id = el.id;
    if (id) {
      var labelFor = document.querySelector('label[for="' + id + '"]');
      if (labelFor) return (labelFor.textContent || '').toLowerCase();
    }

    // 3) Walk up parents and check for label/span/div text
    var parent = el.parentElement;
    for (var i = 0; i < 4 && parent; i++) {
      var labels = parent.querySelectorAll('label, span, div, p, h3, h4');
      for (var j = 0; j < labels.length; j++) {
        // Don't pick up the element itself or its children
        if (labels[j].contains(el)) continue;
        var t = (labels[j].textContent || '').trim().toLowerCase();
        if (t.length > 1 && t.length < 60) return t;
      }
      parent = parent.parentElement;
    }

    return '';
  }

  // ═══════════════════════════════════════
  //  READ current values from Suno page
  // ═══════════════════════════════════════

  function readCurrentPageData() {
    var fields = findAllPageFields();
    return {
      lyrics: fields.lyrics ? (fields.lyrics.value || '').trim() : '',
      style: fields.style ? (fields.style.value || '').trim() : '',
      title: fields.title ? (fields.title.value || '').trim() : '',
      exclude: fields.exclude ? (fields.exclude.value || '').trim() : '',
      weirdness: fields.sliders.weirdness ? fields.sliders.weirdness.value : '',
      styleInfluence: fields.sliders.styleInfluence ? fields.sliders.styleInfluence.value : '',
      audioInfluence: fields.sliders.audioInfluence ? fields.sliders.audioInfluence.value : '',
    };
  }

  // ═══════════════════════════════════════
  //  INIT
  // ═══════════════════════════════════════

  init();

  function init() {
    injectPanel();
    injectCheckboxes();

    var observer = new MutationObserver(function() {
      if (!document.getElementById('suno-git-panel')) {
        panelInjected = false;
        injectPanel();
      }
      injectCheckboxes();
    });
    observer.observe(document.body, { childList: true, subtree: true });

    // SPA navigation detection
    var lastUrl = location.href;
    setInterval(function() {
      if (location.href !== lastUrl) {
        lastUrl = location.href;
        panelInjected = false;
        injectPanel();
        injectCheckboxes();
      }
    }, 1000);

    // Auto-fill listener
    chrome.runtime.onMessage.addListener(function(msg) {
      if (msg.action === 'fillFromStorage') {
        checkAndFill();
      }
    });
    setTimeout(checkAndFill, 2000);
  }

  // ═══════════════════════════════════════
  //  PANEL
  // ═══════════════════════════════════════

  function injectPanel() {
    if (panelInjected || document.getElementById('suno-git-panel')) return;
    panelInjected = true;

    var panel = document.createElement('div');
    panel.id = 'suno-git-panel';
    panel.innerHTML = [
      '<div class="suno-git-header">',
      '  <svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor">',
      '    <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38',
      '      0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13',
      '      -.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66',
      '      .07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15',
      '      -.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0',
      '      1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82',
      '      1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01',
      '      1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>',
      '  </svg>',
      '  <span>Suno to Git</span>',
      '</div>',
      '<div id="suno-git-count">Selected: 0</div>',
      '<div id="suno-git-score-wrap">',
      '  <label for="suno-git-score">Score</label>',
      '  <input type="number" id="suno-git-score" min="0" max="100" value="" placeholder="0-100" />',
      '</div>',
      '<button id="suno-git-save" disabled>Save to Git</button>',
      '<div id="suno-git-status"></div>',
      '<button id="suno-git-toggle" title="Minimize">_</button>',
    ].join('\n');

    document.body.appendChild(panel);

    document.getElementById('suno-git-toggle').addEventListener('click', function() {
      panel.classList.toggle('minimized');
      document.getElementById('suno-git-toggle').textContent =
        panel.classList.contains('minimized') ? '+' : '_';
    });

    document.getElementById('suno-git-save').addEventListener('click', handleSave);
  }

  // ═══════════════════════════════════════
  //  CHECKBOXES
  // ═══════════════════════════════════════

  function injectCheckboxes() {
    var songLinks = document.querySelectorAll('a[href*="/song/"]');

    for (var i = 0; i < songLinks.length; i++) {
      var link = songLinks[i];
      var container = findSongContainer(link);
      if (!container || container.hasAttribute('data-suno-git')) continue;
      container.setAttribute('data-suno-git', 'true');

      var songId = extractSongId(link.href);
      if (!songId) continue;

      var checkbox = document.createElement('div');
      checkbox.className = 'suno-git-checkbox';
      checkbox.setAttribute('data-song-id', songId);
      checkbox.setAttribute('data-song-url', link.href);
      checkbox.setAttribute('data-song-title', (link.textContent || '').trim());
      checkbox.innerHTML =
        '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="3">' +
        '<polyline points="20 6 9 17 4 12"/>' +
        '</svg>';

      checkbox.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        var cb = e.currentTarget;
        var cont = cb.closest('[data-suno-git]');
        var id = cb.getAttribute('data-song-id');
        var isSelected = cb.classList.toggle('selected');
        cont.classList.toggle('suno-git-selected', isSelected);

        if (isSelected) {
          selectedSongs.set(id, {
            id: id,
            title: cb.getAttribute('data-song-title') || 'Untitled',
            url: cb.getAttribute('data-song-url') || ''
          });
        } else {
          selectedSongs.delete(id);
        }
        updateCount();
      });

      container.style.position = 'relative';
      container.appendChild(checkbox);
    }
  }

  function findSongContainer(link) {
    var selectors = ['.clip-row', 'div[class*="clip"]', 'div[style*="grid-template-columns"]'];
    for (var i = 0; i < selectors.length; i++) {
      var match = link.closest(selectors[i]);
      if (match) return match;
    }
    var el = link.parentElement;
    for (var j = 0; j < 5 && el; j++) {
      var s = el.getAttribute('style') || '';
      var c = (typeof el.className === 'string') ? el.className : '';
      if (s.includes('grid') || c.includes('clip') || c.includes('row') || c.includes('card')) {
        return el;
      }
      el = el.parentElement;
    }
    return link.parentElement;
  }

  function extractSongId(href) {
    var m = href.match(/\/song\/([a-f0-9-]+)/);
    return m ? m[1] : null;
  }

  function updateCount() {
    var countEl = document.getElementById('suno-git-count');
    var saveBtn = document.getElementById('suno-git-save');
    if (countEl) countEl.textContent = 'Selected: ' + selectedSongs.size;
    if (saveBtn) saveBtn.disabled = selectedSongs.size === 0;
  }

  // ═══════════════════════════════════════
  //  AUTO-FILL from suhbway.kr
  // ═══════════════════════════════════════

  async function checkAndFill() {
    var data = await new Promise(function(r) {
      chrome.storage.local.get(['suno_pending_fill'], r);
    });
    if (!data.suno_pending_fill) return;

    var fill = data.suno_pending_fill;
    showFillNotification(fill);

    var attempts = 0;
    var tryFill = setInterval(function() {
      attempts++;
      var filled = doFill(fill);
      if (filled || attempts > 30) {
        clearInterval(tryFill);
        if (filled) {
          chrome.storage.local.remove('suno_pending_fill');
        }
      }
    }, 500);
  }

  function doFill(fill) {
    var fields = findAllPageFields();
    var filledAny = false;

    // LYRICS → lyrics textarea
    if (fill.lyrics && fields.lyrics) {
      setReactValue(fields.lyrics, fill.lyrics);
      filledAny = true;
    }

    // PROMPT (from suhbway = Suno Prompt) → Style of Music input
    if (fill.prompt && fields.style) {
      setReactValue(fields.style, fill.prompt);
      filledAny = true;
    }

    // EXCLUDE STYLES → Exclude Styles input
    if (fill.excludeStyles && fields.exclude) {
      setReactValue(fields.exclude, fill.excludeStyles);
      filledAny = true;
    }

    // TITLE → Title input
    if (fill.title && fields.title) {
      setReactValue(fields.title, fill.title);
      filledAny = true;
    }

    // PARAMETERS → sliders
    if (fill.params) {
      if (fill.params.weirdness != null && fields.sliders.weirdness) {
        setReactValue(fields.sliders.weirdness, String(fill.params.weirdness));
        filledAny = true;
      }
      if (fill.params.styleInfluence != null && fields.sliders.styleInfluence) {
        setReactValue(fields.sliders.styleInfluence, String(fill.params.styleInfluence));
        filledAny = true;
      }
      if (fill.params.audioInfluence != null && fields.sliders.audioInfluence) {
        setReactValue(fields.sliders.audioInfluence, String(fill.params.audioInfluence));
        filledAny = true;
      }
    }

    return filledAny;
  }

  function setReactValue(el, value) {
    // React uses internal value tracker - must bypass it
    var proto = (el.tagName === 'TEXTAREA') ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    var nativeSetter = Object.getOwnPropertyDescriptor(proto, 'value');

    if (nativeSetter && nativeSetter.set) {
      nativeSetter.set.call(el, value);
    } else {
      el.value = value;
    }

    // Reset React's value tracker so it sees the change
    var tracker = el._valueTracker;
    if (tracker) tracker.setValue('');

    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    el.dispatchEvent(new Event('blur', { bubbles: true }));
  }

  function showFillNotification(fill) {
    var existing = document.getElementById('suno-fill-toast');
    if (existing) existing.remove();

    var toast = document.createElement('div');
    toast.id = 'suno-fill-toast';
    toast.innerHTML =
      '<div style="font-weight:700;margin-bottom:4px;">Auto-filled from suhbway.kr</div>' +
      '<div style="font-size:11px;color:#aaa;">' + (fill.title || 'Prompt loaded') + '</div>';
    toast.style.cssText =
      'position:fixed;top:20px;right:20px;z-index:999999;' +
      'padding:14px 20px;background:#1a1a2e;color:#fff;' +
      'border:1px solid #6c63ff;border-radius:10px;' +
      'box-shadow:0 8px 30px rgba(0,0,0,0.5);' +
      'font-family:-apple-system,BlinkMacSystemFont,sans-serif;' +
      'font-size:13px;transition:opacity 0.3s;';
    document.body.appendChild(toast);
    setTimeout(function() {
      toast.style.opacity = '0';
      setTimeout(function() { toast.remove(); }, 300);
    }, 3000);
  }

  // ═══════════════════════════════════════
  //  SAVE TO GITHUB
  //  Reads ALL current field values at save time
  // ═══════════════════════════════════════

  async function handleSave() {
    var saveBtn = document.getElementById('suno-git-save');
    var statusEl = document.getElementById('suno-git-status');
    if (!saveBtn || !statusEl) return;

    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';
    statusEl.textContent = '';
    statusEl.className = '';

    try {
      var settings = await new Promise(function(r) {
        chrome.storage.local.get(['github_token', 'github_owner', 'github_repo'], r);
      });
      if (!settings.github_token) {
        throw new Error('Set up GitHub in extension popup first');
      }

      var scoreEl = document.getElementById('suno-git-score');
      var score = scoreEl ? scoreEl.value.trim() : '-';

      // READ all current page field values NOW (at save time)
      var pageData = readCurrentPageData();

      var saved = 0;
      var total = selectedSongs.size;

      for (var entry of selectedSongs) {
        var songData = entry[1];
        // Merge page data into song data
        songData.score = score || '-';
        songData.lyrics = pageData.lyrics;
        songData.style = pageData.style;
        songData.exclude = pageData.exclude;
        songData.weirdness = pageData.weirdness;
        songData.styleInfluence = pageData.styleInfluence;
        songData.audioInfluence = pageData.audioInfluence;
        songData.savedAt = new Date().toISOString();

        saved++;
        statusEl.textContent = 'Saving ' + saved + '/' + total + '...';
        var markdown = buildMarkdown(songData);
        await saveToGitHub(settings, songData, markdown);
      }

      // Clear selection state (buttons stay)
      selectedSongs.clear();
      var cbs = document.querySelectorAll('.suno-git-checkbox.selected');
      for (var i = 0; i < cbs.length; i++) {
        cbs[i].classList.remove('selected');
        var p = cbs[i].closest('[data-suno-git]');
        if (p) p.classList.remove('suno-git-selected');
      }
      updateCount();

      statusEl.className = 'suno-git-status success';
      statusEl.textContent = total + ' song(s) saved!';
      setTimeout(function() { statusEl.textContent = ''; statusEl.className = ''; }, 3000);
    } catch (err) {
      statusEl.className = 'suno-git-status error';
      statusEl.textContent = err.message;
      setTimeout(function() { statusEl.textContent = ''; statusEl.className = ''; }, 4000);
    } finally {
      saveBtn.textContent = 'Save to Git';
      saveBtn.disabled = selectedSongs.size === 0;
    }
  }

  function buildMarkdown(data) {
    var lines = [
      '# ' + data.title,
      '',
      '- **Date**: ' + data.savedAt,
      '- **URL**: [' + data.url + '](' + data.url + ')',
      '- **Song ID**: `' + data.id + '`',
      '- **Score**: ' + (data.score || '-') + ' / 100',
      ''
    ];

    // Lyrics
    lines.push('## Lyrics');
    lines.push('');
    if (data.lyrics) {
      lines.push('```');
      lines.push(data.lyrics);
      lines.push('```');
    } else {
      lines.push('(no lyrics)');
    }
    lines.push('');

    // Style of Music (Prompt)
    lines.push('## Style of Music (Prompt)');
    lines.push('');
    lines.push(data.style || '(no style)');
    lines.push('');

    // Exclude Styles
    if (data.exclude) {
      lines.push('## Exclude Styles');
      lines.push('');
      lines.push(data.exclude);
      lines.push('');
    }

    // Parameters
    if (data.weirdness || data.styleInfluence || data.audioInfluence) {
      lines.push('## Parameters');
      lines.push('');
      lines.push('| Parameter | Value |');
      lines.push('|-----------|-------|');
      if (data.weirdness) lines.push('| Weirdness | ' + data.weirdness + '% |');
      if (data.styleInfluence) lines.push('| Style Influence | ' + data.styleInfluence + '% |');
      if (data.audioInfluence) lines.push('| Audio Influence | ' + data.audioInfluence + '% |');
      lines.push('');
    }

    return lines.join('\n');
  }

  async function saveToGitHub(settings, songData, markdown) {
    var date = new Date().toISOString().split('T')[0];
    var safeName = songData.title.replace(/[^a-zA-Z0-9\uAC00-\uD7A3\s-]/g, '').trim().replace(/\s+/g, '-') || 'untitled';
    var path = 'songs/' + date + '_' + safeName + '_' + songData.id.slice(0, 8) + '.md';

    var content = btoa(unescape(encodeURIComponent(markdown)));

    var res = await fetch(
      'https://api.github.com/repos/' + settings.github_owner + '/' + settings.github_repo + '/contents/' + path,
      {
        method: 'PUT',
        headers: {
          'Authorization': 'Bearer ' + settings.github_token,
          'Content-Type': 'application/json',
          'Accept': 'application/vnd.github+json'
        },
        body: JSON.stringify({
          message: 'Add: ' + songData.title + ' (' + date + ')',
          content: content
        })
      }
    );

    if (!res.ok) {
      var err = await res.json();
      throw new Error(err.message || 'GitHub error: ' + res.status);
    }

    await updateIndex(settings, songData, date);
  }

  async function updateIndex(settings, songData, date) {
    var indexPath = 'README.md';
    var existingSha = null;
    var existingContent = '# Suno Music History\n\n| Date | Title | Score | URL |\n|------|-------|-------|-----|\n';

    try {
      var res = await fetch(
        'https://api.github.com/repos/' + settings.github_owner + '/' + settings.github_repo + '/contents/' + indexPath,
        {
          headers: {
            'Authorization': 'Bearer ' + settings.github_token,
            'Accept': 'application/vnd.github+json'
          }
        }
      );
      if (res.ok) {
        var data = await res.json();
        existingSha = data.sha;
        existingContent = decodeURIComponent(escape(atob(data.content.replace(/\n/g, ''))));
      }
    } catch (e) {}

    var newRow = '| ' + date + ' | ' + songData.title + ' | ' + (songData.score || '-') + ' | [Listen](' + songData.url + ') |';
    var updatedContent = existingContent.trimEnd() + '\n' + newRow + '\n';
    var content = btoa(unescape(encodeURIComponent(updatedContent)));

    var body = { message: 'Update index: ' + songData.title, content: content };
    if (existingSha) body.sha = existingSha;

    await fetch(
      'https://api.github.com/repos/' + settings.github_owner + '/' + settings.github_repo + '/contents/' + indexPath,
      {
        method: 'PUT',
        headers: {
          'Authorization': 'Bearer ' + settings.github_token,
          'Content-Type': 'application/json',
          'Accept': 'application/vnd.github+json'
        },
        body: JSON.stringify(body)
      }
    );
  }
})();
