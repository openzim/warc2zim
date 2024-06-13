async function fetchContent1() {
    const response = await fetch('./content1.json')
    const json = await response.json();
    const span = document.getElementById("span01");
    span.innerHTML=json.property;
    span.classList.add('green');
}
fetchContent1()
