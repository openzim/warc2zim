async function main() {
  if (!navigator.serviceWorker) {
    document.querySelector("h2").innerText = "{{ _("Sorry, service workers are not supported in your browser. (If using Firefox in Private Mode, try regular mode instead.)") }}";
    return;
  }

  var worker = new Worker("./sw.js");

  var prefix = window.location.href.slice(0, window.location.href.indexOf("/A/"));

  const name = prefix.slice(prefix.lastIndexOf("/") + 1).replace(/[\W]+/, "");

  console.log("prefix: " + prefix);
  console.log("name: " + name);

  prefix += "/A/";

  await navigator.serviceWorker.register("./sw.js?replayPrefix=&root=" + name, {scope: prefix});

  worker.addEventListener("message", (event) => {
    if (event.data.msg_type === "collAdded" && event.data.name === name) {
      if (window.location.hash && window.location.hash.startsWith("#redirect=")) {
        prefix += decodeURIComponent(window.location.hash.slice("#redirect=".length));
      } else {
        prefix += window.mainUrl;
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

main();

