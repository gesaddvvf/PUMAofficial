document.addEventListener('DOMContentLoaded',function(){
var b=document.getElementById('tema-toggle');if(!b)return;
function agg(){var s=document.documentElement.dataset.theme==='dark';b.textContent=s?'☀️':'🌙';b.title=s?'Passa al tema chiaro':'Passa al tema scuro';}
b.addEventListener('click',function(){var n=document.documentElement.dataset.theme==='dark'?'light':'dark';
document.documentElement.dataset.theme=n;try{localStorage.setItem('tema',n)}catch(e){}agg();});agg();});
