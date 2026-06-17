document.getElementById('common-modal').addEventListener('click',function(e){
  if(e.target===this)this.style.display='none';
});
document.addEventListener('keydown',function(e){
  if(e.key==='Escape')document.getElementById('common-modal').style.display='none';
});
function showCommonModal(uriA,uriB,nameA,nameB){
  const modal=document.getElementById('common-modal');
  document.getElementById('modal-title').textContent=nameA+' × '+nameB;
  document.getElementById('modal-content').innerHTML='<p style="color:#aaa;padding:2rem;text-align:center">⏳ Chargement…</p>';
  modal.style.display='flex';
  fetch('/api/common?a='+encodeURIComponent(uriA)+'&b='+encodeURIComponent(uriB))
    .then(r=>r.json()).then(pubs=>{
      if(!pubs.length){
        document.getElementById('modal-content').innerHTML='<p style="color:#888;text-align:center;padding:2rem">Aucune publication commune.</p>';
        return;
      }
      document.getElementById('modal-content').innerHTML=
        '<p style="color:#aaa;font-size:12px;margin-bottom:12px">'+pubs.length+' publication(s)</p>'+
        pubs.map(p=>{
          const t=p.url?'<a class="pub-title-link" href="'+p.url+'" target="_blank">'+p.title+'</a>'
                       :'<span class="pub-title">'+p.title+'</span>';
          return '<div class="pub-item">'+t+
            '<div class="pub-meta">'+(p.venue?p.venue+' &nbsp;·&nbsp; ':'')+
            '<span class="pub-year">'+p.year+'</span></div></div>';
        }).join('');
    });
}
(function waitNetwork(n){
  if(typeof network!=='undefined'&&typeof nodes!=='undefined'&&typeof edges!=='undefined'){
    network.on('click',function(p){
      if(p.edges.length>0&&p.nodes.length===0){
        const e=edges.get(p.edges[0]);if(!e)return;
        const na=nodes.get(e.from),nb=nodes.get(e.to);
        showCommonModal(e.from,e.to,na?na.label:e.from,nb?nb.label:e.to);
      }
    });
  }else if(n<80)setTimeout(()=>waitNetwork(n+1),100);
})(0);

initAutocomplete('ac-focus', 'ac-focus-drop');
