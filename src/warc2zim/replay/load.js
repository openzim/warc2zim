async function main() {
  if (!navigator.serviceWorker) {
    document.querySelector("h2").innerText = "Sorry, service workers are not supported in your browser. (If using Firefox in Private Mode, try regular mode instead.)";
    return;
  }

  var worker = new Worker("./sw.js");

  const parts = window.location.href.split("/");
  const inx = parts.indexOf("A");
  const name = parts[inx - 1];

  await navigator.serviceWorker.register("./sw.js?replayPrefix=&root=" + name, {scope: "./"});

  worker.addEventListener("message", (event) => {
    if (event.data.msg_type === "collAdded" && event.data.name === name) {
      window.location.href = "./" + window.mainUrl;
    }
  });

  worker.postMessage({
    msg_type: "addColl",
    name: name,
    file: {"sourceUrl": "proxy:../"},
    root: true,
    skipExisting: true,
    extraConfig: {"sourceType": "kiwix", notFoundPageUrl: "./notFoundPage.html"},
    topTemplateUrl: "./topFrame.html"
  });
}

main();

