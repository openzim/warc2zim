import okValue from './resources.js?query=value';
import { okClass } from './resources.js?query=value';

const span = document.getElementById("span06f");
span.innerHTML=okValue;
span.classList.add(okClass);
