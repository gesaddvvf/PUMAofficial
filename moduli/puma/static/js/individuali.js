(function(){
var liv=document.getElementById('liv'); if(!liv)return;
liv.onchange=async function(){
  document.getElementById('tipo').value=liv.selectedOptions[0].dataset.s||'';
  var m=document.getElementById('man'); m.innerHTML='<legend>Manovre</legend>'; if(!liv.value)return;
  var r=await (await fetch(liv.dataset.url.replace(/0$/,liv.value))).json();
  if(!r.length)m.insertAdjacentHTML('beforeend','<small>Nessuna manovra definita per questo livello (Impostazioni).</small>');
  r.forEach(function(x){var l=document.createElement('label');l.className='puma-chk';var i=document.createElement('input');i.type='checkbox';i.name='manovre';i.value=x.nome;l.append(i,' '+x.nome);m.append(l)});
};})();
