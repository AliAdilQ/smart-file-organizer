(() => {
  if (!window.Chart) return;
  const data = JSON.parse(document.getElementById('chartData').textContent);
  const colors = ['#7860db','#50b9c9','#e7b15e','#db82af','#79b998','#9d9cdb','#85a8e0','#b3bacb'];
  Chart.defaults.font.family = 'Inter, Segoe UI, sans-serif';
  Chart.defaults.color = '#8890a2';
  Chart.defaults.animation = false;
  const category = document.getElementById('categoryChart');
  if (category) new Chart(category, {type:'doughnut',data:{labels:data.category_labels,datasets:[{data:data.category_values,backgroundColor:colors,borderWidth:0,hoverOffset:6}]},options:{maintainAspectRatio:false,cutout:'73%',plugins:{legend:{position:'bottom',labels:{usePointStyle:true,pointStyle:'circle',padding:12,boxWidth:8,font:{size:10}}}}}});
  const activity = document.getElementById('activityChart');
  if (activity) new Chart(activity, {type:'line',data:{labels:data.date_labels,datasets:[{label:'Files organized',data:data.date_values,borderColor:colors[0],backgroundColor:'rgba(120,96,219,.08)',fill:true,tension:.35,pointRadius:3,pointBackgroundColor:colors[0],borderWidth:2}]},options:{maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{grid:{display:false},ticks:{maxTicksLimit:6}},y:{beginAtZero:true,ticks:{precision:0},grid:{color:'rgba(130,130,150,.1)'},border:{display:false}}}}});
  const extensions = document.getElementById('extensionChart');
  if (extensions) new Chart(extensions,{type:'bar',data:{labels:data.extension_labels,datasets:[{label:'Files',data:data.extension_values,backgroundColor:colors,borderRadius:6}]},options:{maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{y:{beginAtZero:true,ticks:{precision:0}},x:{grid:{display:false}}}}});
})();
