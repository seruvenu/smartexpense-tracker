// Count-up for money numbers (.count). The server-rendered text is the final value, so
// the page is correct even if JS is off; the animation only decorates it.
(function () {
  if (window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  document.querySelectorAll('.count').forEach(function (el) {
    var final = el.textContent.trim();
    var m = final.match(/^(\D*?)([\d,]+(?:\.\d+)?)(.*)$/);
    if (!m) return;
    var pre = m[1], target = parseFloat(m[2].replace(/,/g, '')), post = m[3];
    var dec = (m[2].split('.')[1] || '').length, t0 = null, dur = 1200;
    function fmt(v) { return v.toLocaleString('en-IN', { minimumFractionDigits: dec, maximumFractionDigits: dec }); }
    el.textContent = pre + fmt(0) + post;
    requestAnimationFrame(function step(ts) {
      if (t0 === null) t0 = ts;
      var p = Math.min((ts - t0) / dur, 1), e = 1 - Math.pow(1 - p, 3);
      el.textContent = p < 1 ? pre + fmt(target * e) + post : final;
      if (p < 1) requestAnimationFrame(step);
    });
  });
  // Show / hide password buttons
  document.querySelectorAll('.pw-toggle').forEach(function (b) {
    b.addEventListener('click', function () {
      var input = document.getElementById(b.getAttribute('data-target'));
      var show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      b.querySelector('i').className = 'bi ' + (show ? 'bi-eye-slash' : 'bi-eye');
    });
  });
})();
