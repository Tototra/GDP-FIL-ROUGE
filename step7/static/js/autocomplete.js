function initAutocomplete(inputId, dropdownId) {
  let researchers = [];
  let activeIdx = -1;
  fetch('/api/researchers').then(r => r.json()).then(d => { researchers = d; });
  const input = document.getElementById(inputId);
  const dropdown = document.getElementById(dropdownId);
  function renderDropdown(matches) {
    activeIdx = -1;
    if (!matches.length) { dropdown.style.display='none'; return; }
    dropdown.innerHTML = matches.map((n,i) => `<div class="ac-item" data-idx="${i}">${n}</div>`).join('');
    dropdown.style.display = 'block';
    dropdown.querySelectorAll('.ac-item').forEach(item => {
      item.addEventListener('mousedown', e => {
        e.preventDefault(); input.value = item.textContent;
        dropdown.style.display='none'; input.form.submit();
      });
    });
  }
  input.addEventListener('input', () => {
    const q = input.value.toLowerCase().trim();
    if (!q) { dropdown.style.display='none'; return; }
    renderDropdown(researchers.filter(n => n.toLowerCase().includes(q)).slice(0,8));
  });
  input.addEventListener('keydown', e => {
    const items = dropdown.querySelectorAll('.ac-item');
    if (!items.length) return;
    if (e.key==='ArrowDown') { e.preventDefault(); activeIdx=Math.min(activeIdx+1,items.length-1); }
    else if (e.key==='ArrowUp') { e.preventDefault(); activeIdx=Math.max(activeIdx-1,0); }
    else if (e.key==='Enter' && activeIdx>=0) {
      e.preventDefault(); input.value=items[activeIdx].textContent;
      dropdown.style.display='none'; input.form.submit(); return;
    } else if (e.key==='Escape') { dropdown.style.display='none'; return; }
    else return;
    items.forEach(el => el.classList.remove('active'));
    items[activeIdx].classList.add('active');
    input.value = items[activeIdx].textContent;
  });
  document.addEventListener('click', e => { if (!e.target.closest('.ac-wrapper')) dropdown.style.display='none'; });
}
