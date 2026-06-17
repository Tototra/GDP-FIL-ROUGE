const PAL=['#4363D8','#3CB44B','#E6194B','#F58231','#911EB4','#42D4F4','#F032E6',
           '#469990','#BFEF45','#FFE119','#9A6324','#800000','#aaffc3','#808000',
           '#ffd8b1','#000075','#a9a9a9'];
const COPT={responsive:true,plugins:{legend:{labels:{color:'#eee'}}}};
const SC={color:'#888',grid:{color:'#ffffff15'}};

fetch('/api/stats').then(r=>r.json()).then(d=>{
  document.getElementById('loading').style.display='none';
  document.getElementById('grid').style.display='grid';

  const years=Object.keys(d.yearly).sort();
  new Chart(document.getElementById('c-yearly'),{
    type:'line',
    data:{labels:years,datasets:[{label:'Publications',
      data:years.map(y=>d.yearly[y]),borderColor:'#42D4F4',
      backgroundColor:'#42D4F415',fill:true,tension:.35,
      pointRadius:3,pointBackgroundColor:'#42D4F4'}]},
    options:{...COPT,scales:{x:SC,y:{...SC,beginAtZero:true}}}
  });

  new Chart(document.getElementById('c-teams'),{
    type:'doughnut',
    data:{labels:d.teams.map(t=>t.team),
      datasets:[{data:d.teams.map(t=>t.count),backgroundColor:PAL,
        borderColor:'#1a1a2e',borderWidth:2}]},
    options:{...COPT,plugins:{legend:{position:'right',
      labels:{color:'#eee',font:{size:11}}}}}
  });

  new Chart(document.getElementById('c-top'),{
    type:'bar',
    data:{labels:d.top_researchers.map(r=>r.name),
      datasets:[{label:'Publications',data:d.top_researchers.map(r=>r.count),
        backgroundColor:d.top_researchers.map((_,i)=>PAL[i%PAL.length]),
        borderRadius:4}]},
    options:{...COPT,indexAxis:'y',scales:{x:{...SC,beginAtZero:true},y:SC}}
  });

  new Chart(document.getElementById('c-venues'),{
    type:'bar',
    data:{labels:d.venues.map(v=>v.venue.length>38?v.venue.slice(0,38)+'…':v.venue),
      datasets:[{label:'Publications',data:d.venues.map(v=>v.count),
        backgroundColor:'#911EB4',borderRadius:4}]},
    options:{...COPT,indexAxis:'y',
      scales:{x:{...SC,beginAtZero:true},y:{...SC,ticks:{font:{size:10}}}}}
  });

  if(Object.keys(d.topics).length>0){
    document.getElementById('topics-card').style.display='block';
    const tms=Object.keys(d.topics);
    const allT=[...new Set(tms.flatMap(t=>Object.keys(d.topics[t])))];
    new Chart(document.getElementById('c-topics'),{
      type:'bar',
      data:{labels:tms,datasets:allT.map((topic,i)=>({
        label:topic,
        data:tms.map(t=>d.topics[t][topic]||0),
        backgroundColor:PAL[i%PAL.length],borderRadius:2,
        stack:'s'
      }))},
      options:{...COPT,scales:{x:{...SC,stacked:true},y:{...SC,stacked:true,beginAtZero:true}},
        plugins:{...COPT.plugins,legend:{position:'right',
          labels:{color:'#eee',font:{size:10},boxWidth:12}}}}
    });
  }
});
