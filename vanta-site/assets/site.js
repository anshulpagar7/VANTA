/* Shared: scroll reveals and bar growth. No dependencies. */
(function () {
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (!e.isIntersecting) return;
      e.target.classList.add('on');
      e.target.querySelectorAll('.arm').forEach(function (arm, i) {
        var bar = arm.querySelector('.fill');
        if (bar) setTimeout(function () {
          bar.style.width = arm.getAttribute('data-pct') + '%';
        }, reduce ? 0 : i * 130);
      });
      io.unobserve(e.target);
    });
  }, { threshold: 0.2 });
  document.querySelectorAll('.reveal').forEach(function (el) { io.observe(el); });
})();
