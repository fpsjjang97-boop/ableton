// Background service worker - handles tab communication & API proxy

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === 'openSunoCreate') {
    // Find existing Suno create tab or open new one
    chrome.tabs.query({ url: 'https://suno.com/*' }, (tabs) => {
      const createTab = tabs.find(t => t.url?.includes('/create'));
      if (createTab) {
        chrome.tabs.update(createTab.id, { active: true });
        chrome.tabs.sendMessage(createTab.id, { action: 'fillFromStorage' });
      } else {
        chrome.tabs.create({ url: 'https://suno.com/create' });
      }
    });
  }

  // Proxy API call from content script (avoids CORS/CSP issues)
  if (msg.action === 'fetchClipData') {
    fetchClipFromBackground(msg.clipId)
      .then(data => sendResponse({ success: true, data: data }))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true; // keep channel open for async response
  }
});

async function fetchClipFromBackground(clipId) {
  // Get cookies for suno.com to build auth
  const cookies = await chrome.cookies.getAll({ domain: 'suno.com' });
  const cookieHeader = cookies.map(c => c.name + '=' + c.value).join('; ');

  const res = await fetch('https://suno.com/api/clip/' + clipId, {
    headers: {
      'Accept': 'application/json',
      'Cookie': cookieHeader
    }
  });

  if (!res.ok) throw new Error('API error: ' + res.status);
  return await res.json();
}
