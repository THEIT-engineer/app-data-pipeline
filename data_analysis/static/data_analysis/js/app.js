/* App Data — interactions communes à toutes les pages */
(function () {
  "use strict";

  var root = document.documentElement;

  // Thème clair / sombre (mémorisé dans le navigateur)
  function storedTheme() {
    try { return localStorage.getItem("appdata-theme"); } catch (e) { return null; }
  }
  function applyTheme(theme) {
    root.setAttribute("data-theme", theme);
    try { localStorage.setItem("appdata-theme", theme); } catch (e) { /* stockage indisponible */ }
  }

  document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      applyTheme(root.getAttribute("data-theme") === "dark" ? "light" : "dark");
    });
  });

  if (!storedTheme() && window.matchMedia("(prefers-color-scheme: dark)").matches) {
    root.setAttribute("data-theme", "dark");
  }

  // Menu latéral sur mobile
  document.querySelectorAll("[data-sidebar-toggle]").forEach(function (el) {
    el.addEventListener("click", function () {
      document.body.classList.toggle("sidebar-open");
    });
  });

  // Zones de dépôt de fichiers : affichent le nom du fichier choisi
  document.querySelectorAll(".dropzone").forEach(function (zone) {
    var input = zone.querySelector("input[type=file]");
    var label = zone.querySelector(".file-name");
    if (!input) return;

    function showName() {
      if (label && input.files.length) label.textContent = input.files[0].name;
    }
    input.addEventListener("change", showName);

    ["dragenter", "dragover"].forEach(function (evt) {
      zone.addEventListener(evt, function (e) { e.preventDefault(); zone.classList.add("is-dragover"); });
    });
    ["dragleave", "drop"].forEach(function (evt) {
      zone.addEventListener(evt, function () { zone.classList.remove("is-dragover"); });
    });
    zone.addEventListener("drop", function (e) {
      e.preventDefault();
      if (e.dataTransfer.files.length) {
        input.files = e.dataTransfer.files;
        showName();
      }
    });
  });

  // Onglets : <div data-tabs> avec boutons [data-tab="id"] et panneaux #id
  document.querySelectorAll("[data-tabs]").forEach(function (group) {
    var tabs = group.querySelectorAll("[data-tab]");
    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        tabs.forEach(function (t) {
          var active = t === tab;
          t.classList.toggle("is-active", active);
          t.setAttribute("aria-selected", active);
          var panel = document.getElementById(t.dataset.tab);
          if (panel) panel.hidden = !active;
        });
        // Les graphiques Plotly d'un onglet caché ont été dessinés sans largeur : on les redimensionne
        window.dispatchEvent(new Event("resize"));
      });
    });
  });

  // Bouton désactivé + libellé pendant l'envoi d'un formulaire long
  document.querySelectorAll("form[data-loading]").forEach(function (form) {
    form.addEventListener("submit", function () {
      var btn = form.querySelector("[type=submit]");
      if (btn) {
        btn.disabled = true;
        btn.textContent = form.dataset.loading || "Traitement…";
      }
    });
  });
})();
