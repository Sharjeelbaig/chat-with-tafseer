(function () {
  function getFormState() {
    var resourceId = parseInt(document.getElementById("chapter_resource_id").value, 10);
    var chapterNumber = parseInt(document.getElementById("chapter_number").value, 10);

    return {
      resource_id: Number.isFinite(resourceId) && resourceId > 0 ? resourceId : 169,
      chapter_number: Number.isFinite(chapterNumber) && chapterNumber > 0 ? chapterNumber : 1,
    };
  }

  function updateUrlPreview() {
    var payload = getFormState();
    var url = window.docsSite.buildApiUrl("/tafseer/" + payload.resource_id + "/chapter/" + payload.chapter_number);
    document.getElementById("chapter-url-preview").textContent = url;
    document.getElementById("chapter-curl-preview").textContent = "curl " + url;
  }

  function setStatus(kind, label) {
    var node = document.getElementById("chapter-sandbox-status");
    node.className = kind;
    node.innerHTML = '<span class="status-dot"></span>' + label;
  }

  function setResponsePreview(payload) {
    document.getElementById("chapter-response-preview").textContent = JSON.stringify(payload, null, 2);
  }

  async function sendRequest() {
    var button = document.getElementById("fetch-tafseer-btn");
    var payload = getFormState();
    var endpoint = "/tafseer/" + payload.resource_id + "/chapter/" + payload.chapter_number;

    button.disabled = true;
    button.innerHTML = "Fetching...";
    setStatus("status-warn", "Awaiting response");

    try {
      var response = await fetch(window.docsSite.buildApiUrl(endpoint));
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
        detail: error instanceof Error ? error.message : "Unexpected error while calling /tafseer",
      });
    } finally {
      button.disabled = false;
      button.innerHTML = "Fetch Tafseer";
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    ["chapter_resource_id", "chapter_number"].forEach(function (id) {
      document.getElementById(id).addEventListener("input", updateUrlPreview);
    });

    document.getElementById("fetch-tafseer-btn").addEventListener("click", sendRequest);
    document.getElementById("copy-chapter-url-btn").addEventListener("click", function (event) {
      window.docsSite.copyText(document.getElementById("chapter-url-preview").textContent, event.currentTarget, "Copied");
    });
    document.getElementById("copy-chapter-curl-btn").addEventListener("click", function (event) {
      window.docsSite.copyText(document.getElementById("chapter-curl-preview").textContent, event.currentTarget, "Copied");
    });
    document.getElementById("copy-chapter-response-btn").addEventListener("click", function (event) {
      window.docsSite.copyText(document.getElementById("chapter-response-preview").textContent, event.currentTarget, "Copied");
    });

    setStatus("status-ok", "Ready");
    setResponsePreview({
      tafsirs: [
        {
          verse_key: "1:1",
          text: "Chapter tafseer preview appears here after you call the endpoint.",
        },
      ],
    });
    updateUrlPreview();
  });
})();
