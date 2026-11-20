(function(){var t=null;try{t=localStorage.getItem('tema')}catch(e){}
if(!t)t=matchMedia('(prefers-color-scheme: light)').matches?'light':'dark';
document.documentElement.dataset.theme=t;})();
