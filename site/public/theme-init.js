// Applies the stored theme before first paint so there is no flash of the
// wrong palette. Kept tiny on purpose. Moved out of index.html's own
// inline <script> (package 22) so script-src can stay 'self' with no
// 'unsafe-inline' exception -- the CSP the CV-reading feature needs for
// real (blocking model output from ever executing as script), not
// weakened for this one pre-existing, content-free script's sake.
(function () {
  try {
    var t = localStorage.getItem('compass:theme') || 'compass';
    var m = localStorage.getItem('compass:mode');
    if (!m) m = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    document.documentElement.dataset.theme = t;
    document.documentElement.dataset.mode = m;
    document.documentElement.style.colorScheme = m;
  } catch (e) {}
})();
