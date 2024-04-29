const img10 = document.getElementById('img10');
const origSrc = img10.getAttribute('src')
const newSrc = origSrc.replace('not_working', 'working')
console.debug('Replacing ' + origSrc + ' with ' + newSrc)
img10.src = newSrc;