// Links leaving the documentation site (GitHub pages, the model repositories,
// the licence, the data) open in a new tab, so that the reader keeps their
// place in the documentation.
document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll("a[href]").forEach(function (link) {
    if (link.hostname && link.hostname !== window.location.hostname) {
      link.target = "_blank";
      link.rel = "noopener";
    }
  });
});
