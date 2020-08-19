async function main() {
  if (!navigator.serviceWorker) {

    let msg;
    // check if service worker doesn't work due to http loading
    if (window.location.protocol === "http:" && window.location.hostname !== "localhost") {
      const httpsUrl = window.location.href.replace("http:", "https:");
      document.querySelector("#error").innerHTML = "<p>{{ _("This page must be loaded via an HTTPS URL to support service workers.") }}</p>" +
          `<a href="${httpsUrl}">{{ _("Try Loading HTTPS URL?") }}</a>`;
    // otherwise, assume service worker not available at all
    } else {
      document.querySelector("#error").innerText = "{{ _("Sorry, service workers are not supported in your browser. (If using Firefox in Private Mode, try regular mode instead.)") }}";
    }

    document.querySelector("#loading").style.display = "none";
    return;
  }

  var worker = new Worker("./sw.js");

  // finds  '/A/' followed by a domain name with a .
  var prefix = window.location.href.slice(0, window.location.href.search(/[/]A[/][^/]+[.]/));

  const name = prefix.slice(prefix.lastIndexOf("/") + 1).replace(/[\W]+/, "");

  prefix += "/A/";

  await navigator.serviceWorker.register("./sw.js?replayPrefix=&root=" + name, {scope: prefix});

  worker.addEventListener("message", (event) => {
    if (event.data.msg_type === "collAdded" && event.data.name === name) {
      if (window.location.hash && window.location.hash.startsWith("#redirect=")) {
        prefix += decodeURIComponent(window.location.hash.slice("#redirect=".length));
      } else {
        const inx = window.mainUrl.indexOf("//");
        prefix += inx >= 0 ? window.mainUrl.slice(inx + 2) : window.mainUrl;
      }

      console.log("final: " + prefix);
      window.location.href = prefix;
    }
  });

  worker.postMessage({
    msg_type: "addColl",
    name: name,
    file: {"sourceUrl": "proxy:../"},
    root: true,
    skipExisting: false,
    extraConfig: {"sourceType": "kiwix", notFoundPageUrl: "./404.html"},
    topTemplateUrl: "./topFrame.html"
  });
}

window.addEventListener("load", main);

