(function () {
  var DEFAULT_API_BASE = "https://chat-with-tafseer.vercel.app";
  var THEME_STORAGE_KEY = "docs-theme";
  var DARK_ICON =
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 0 1 11.21 3c0 0 0 0 0 0A9 9 0 1 0 21 12.79Z"></path></svg>';
  var LIGHT_ICON =
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2"></path><path d="M12 20v2"></path><path d="m4.93 4.93 1.41 1.41"></path><path d="m17.66 17.66 1.41 1.41"></path><path d="M2 12h2"></path><path d="M20 12h2"></path><path d="m6.34 17.66-1.41 1.41"></path><path d="m19.07 4.93-1.41 1.41"></path></svg>';

  function trimTrailingSlash(value) {
    return value.replace(/\/+$/, "");
  }

  function getStoredTheme() {
    try {
      return localStorage.getItem(THEME_STORAGE_KEY);
    } catch (error) {
      return null;
    }
  }

  function getPreferredTheme() {
    var stored = getStoredTheme();
    if (stored === "light" || stored === "dark") {
      return stored;
    }

    if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
      return "dark";
    }

    return "light";
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);

    document.querySelectorAll("[data-theme-toggle]").forEach(function (button) {
      var isDark = theme === "dark";
      button.setAttribute("aria-pressed", isDark ? "true" : "false");
      button.setAttribute("aria-label", isDark ? "Switch to light theme" : "Switch to dark theme");

      var label = button.querySelector("[data-theme-label]");
      if (label) {
        label.textContent = isDark ? "Light theme" : "Dark theme";
      }

      var icon = button.querySelector("[data-theme-icon]");
      if (icon) {
        icon.innerHTML = isDark ? LIGHT_ICON : DARK_ICON;
      }
    });
  }

  function setTheme(theme) {
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch (error) {
      // Ignore storage failures and still update the current view.
    }
    applyTheme(theme);
  }

  function attachThemeToggle() {
    applyTheme(getPreferredTheme());

    document.querySelectorAll("[data-theme-toggle]").forEach(function (button) {
      button.addEventListener("click", function () {
        var nextTheme = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
        setTheme(nextTheme);
      });
    });
  }

  function getApiBaseUrl() {
    var params = new URLSearchParams(window.location.search);
    var explicitBase = params.get("api_base");
    if (explicitBase) {
      return trimTrailingSlash(explicitBase);
    }

    return DEFAULT_API_BASE;
  }

  function buildApiUrl(pathname) {
    var normalizedPath = pathname.startsWith("/") ? pathname : "/" + pathname;
    return getApiBaseUrl() + normalizedPath;
  }

  function setButtonCopiedState(button, message) {
    var original = button.dataset.originalLabel;
    if (!original) {
      original = button.innerHTML;
      button.dataset.originalLabel = original;
    }

    button.innerHTML = message;
    button.disabled = true;

    window.setTimeout(function () {
      button.innerHTML = original;
      button.disabled = false;
    }, 1800);
  }

  function copyText(value, button, label) {
    navigator.clipboard.writeText(value).then(function () {
      if (button) {
        setButtonCopiedState(button, label || "Copied");
      }
    });
  }

  function attachCopyButtons() {
    document.querySelectorAll("[data-copy-target]").forEach(function (button) {
      button.addEventListener("click", function () {
        var selector = button.getAttribute("data-copy-target");
        var target = document.querySelector(selector);
        if (!target) {
          return;
        }

        var value = target.textContent || target.innerText || "";
        copyText(value.trim(), button, button.getAttribute("data-copy-label") || "Copied");
      });
    });

    document.querySelectorAll("[data-copy-value]").forEach(function (button) {
      button.addEventListener("click", function () {
        copyText(button.getAttribute("data-copy-value") || "", button, button.getAttribute("data-copy-label") || "Copied");
      });
    });
  }

  function populateEndpointLinks() {
    document.querySelectorAll("[data-endpoint-path]").forEach(function (node) {
      node.textContent = buildApiUrl(node.getAttribute("data-endpoint-path") || "/");
    });
  }

  function attachLlmsPreview() {
    var preview = document.querySelector("[data-llms-preview]");
    if (!preview) {
      return;
    }

    fetch("./llms.txt")
      .then(function (response) {
        if (!response.ok) {
          throw new Error("Unable to load llms.txt");
        }
        return response.text();
      })
      .then(function (text) {
        preview.textContent = text.trim();
        document.querySelectorAll("[data-copy-llms]").forEach(function (button) {
          button.setAttribute("data-copy-value", text.trim());
          button.addEventListener("click", function () {
            copyText(text.trim(), button, "Copied");
          });
        });
      })
      .catch(function () {
        preview.textContent = "Unable to load llms.txt from this docs build.";
      });
  }

  function attachExternalLinkSafety() {
    document.querySelectorAll("a[target=\"_blank\"]").forEach(function (link) {
      if (!link.rel.includes("noopener")) {
        link.rel = (link.rel + " noopener noreferrer").trim();
      }
    });
  }

  function attachMobileMenu() {
    var overlay = document.createElement("div");
    overlay.className = "mobile-overlay";
    document.body.appendChild(overlay);

    document.querySelectorAll("[data-menu-toggle]").forEach(function (button) {
      button.addEventListener("click", function () {
        document.body.classList.toggle("sidebar-open");
      });
    });

    overlay.addEventListener("click", function () {
      document.body.classList.remove("sidebar-open");
    });

    document.querySelectorAll(".sidebar-item").forEach(function (item) {
      item.addEventListener("click", function () {
        document.body.classList.remove("sidebar-open");
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    attachThemeToggle();
    attachMobileMenu();
    populateEndpointLinks();
    attachCopyButtons();
    attachLlmsPreview();
    attachExternalLinkSafety();
  });

  window.docsSite = {
    buildApiUrl: buildApiUrl,
    copyText: copyText,
    setButtonCopiedState: setButtonCopiedState,
  };
})();
