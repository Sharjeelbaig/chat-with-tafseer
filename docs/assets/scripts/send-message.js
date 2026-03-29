(function () {
  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderHighlightedJson(payload) {
    return escapeHtml(JSON.stringify(payload, null, 2))
      .replace(/&quot;([^&]+)&quot;:/g, '<span class="bk">"$1"</span>:')
      .replace(/: &quot;([^&]*)&quot;/g, ': <span class="bv">"$1"</span>')
      .replace(/: (\d+)/g, ': <span class="bn">$1</span>')
      .replace(/: (true|false|null)/g, ': <span class="bn">$1</span>');
  }

  function getFormState() {
    var resourceId = parseInt(document.getElementById("resource_id").value, 10);
    var verseKey = document.getElementById("verse_key").value.trim();
    var message = document.getElementById("message").value.trim();
    var threadId = document.getElementById("thread_id").value.trim();

    return {
      resource_id: Number.isFinite(resourceId) && resourceId > 0 ? resourceId : 169,
      verse_key: verseKey || "1:1",
      message: message || "What does it say?",
      thread_id: threadId || "session-1",
    };
  }

  function updateBodyPreview() {
    var payload = getFormState();
    document.getElementById("request-body-preview").innerHTML = renderHighlightedJson(payload);
    document.getElementById("curl-preview").textContent =
      "curl -X POST " +
      window.docsSite.buildApiUrl("/chat") +
      " \\\n  -H \"Content-Type: application/json\" \\\n  -d '" +
      JSON.stringify(payload, null, 2) +
      "'";
  }

  function setStatus(kind, label) {
    var node = document.getElementById("sandbox-status");
    node.className = kind;
    node.innerHTML = '<span class="status-dot"></span>' + label;
  }

  function setResponsePreview(payload) {
    document.getElementById("response-preview").textContent = JSON.stringify(payload, null, 2);
  }

  function copyCurrentBody(button) {
    window.docsSite.copyText(JSON.stringify(getFormState(), null, 2), button, "Copied");
  }

  async function sendRequest() {
    var button = document.getElementById("send-request-btn");
    var payload = getFormState();

    button.disabled = true;
    button.innerHTML = "Sending...";
    setStatus("status-warn", "Awaiting response");

    try {
      var response = await fetch(window.docsSite.buildApiUrl("/chat"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      var contentType = response.headers.get("content-type") || "";
      var data = contentType.includes("application/json") ? await response.json() : await response.text();

      if (!response.ok) {
        setStatus("status-error", "HTTP " + response.status);
        setResponsePreview(data);
        return;
      }

      setStatus("status-ok", "HTTP " + response.status);
      setResponsePreview(data);
    } catch (error) {
      setStatus("status-error", "Request failed");
      setResponsePreview({
        detail: error instanceof Error ? error.message : "Unexpected error while calling /chat",
      });
    } finally {
      button.disabled = false;
      button.innerHTML = "Send Request";
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    ["resource_id", "verse_key", "message", "thread_id"].forEach(function (id) {
      document.getElementById(id).addEventListener("input", updateBodyPreview);
    });

    document.getElementById("copy-body-btn").addEventListener("click", function (event) {
      copyCurrentBody(event.currentTarget);
    });

    document.getElementById("send-request-btn").addEventListener("click", sendRequest);
    document.getElementById("copy-curl-btn").addEventListener("click", function (event) {
      window.docsSite.copyText(document.getElementById("curl-preview").textContent, event.currentTarget, "Copied");
    });
    document.getElementById("copy-response-btn").addEventListener("click", function (event) {
      window.docsSite.copyText(document.getElementById("response-preview").textContent, event.currentTarget, "Copied");
    });

    setStatus("status-ok", "Ready");
    setResponsePreview({
      answer: "Response preview appears here after you call /chat.",
      resource_id: 169,
      verse_key: "1:1",
      chapter_number: 1,
    });
    updateBodyPreview();
  });
})();
