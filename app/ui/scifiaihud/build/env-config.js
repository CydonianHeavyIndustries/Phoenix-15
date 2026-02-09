window.__BJ_CFG = {"user": "Father", "pass": "NeverKnowsBest", "apiBase": "/"};
window.addEventListener('error', function(e){
  try {
    fetch('/log/client', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({message:'window.onerror', detail:(e.message||'') + ' @' + (e.filename||'') + ':' + (e.lineno||'')})});
  } catch(_) {}
});
window.addEventListener('unhandledrejection', function(e){
  try {
    fetch('/log/client', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({message:'unhandledrejection', detail:(e.reason&&e.reason.toString())||''})});
  } catch(_) {}
});
