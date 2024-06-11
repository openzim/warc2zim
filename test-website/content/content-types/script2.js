async function fetchContent2() {
    const response = await fetch('./content2.json')
    const json = await response.json();
    const span = document.getElementById("span02");
    span.innerHTML=json.property;
    span.classList.add('green');
}
fetchContent2()
