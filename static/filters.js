(function () {
  const q = document.getElementById("q");
  const colore = document.getElementById("colore");
  const tipologia = document.getElementById("tipologia");
  const regione = document.getElementById("regione");
  const results = document.getElementById("results");
  const reset = document.getElementById("reset");

  const rows = Array.from(document.querySelectorAll(".wine-row"));
  const categoryBlocks = Array.from(document.querySelectorAll(".category-block"));

  function norm(s){ return (s||"").toString().trim().toLowerCase(); }

  function apply(){
    const qv = norm(q.value);
    const cv = (colore.value||"").toString();
    const tv = (tipologia.value||"").toString();
    const rv = (regione.value||"").toString();

    let visible = 0;

    rows.forEach((r)=>{
      const name = r.dataset.nome || "";
      const prod = r.dataset.prod || "";
      const c = r.dataset.colore || "";
      const t = r.dataset.tipologia || "";
      const reg = r.dataset.regione || "";

      const textOk = !qv || name.includes(qv) || prod.includes(qv);
      const coloreOk = !cv || c === cv;
      const tipoOk = !tv || t === tv;
      const regOk = !rv || reg === rv;

      const ok = textOk && coloreOk && tipoOk && regOk;
      r.classList.toggle("d-none", !ok);
      if(ok) visible += 1;
    });

    categoryBlocks.forEach((block)=>{
      const catRows = Array.from(block.querySelectorAll(".wine-row"));
      const visibleInCat = catRows.filter((r)=>!r.classList.contains("d-none")).length;
      const badge = block.querySelector(".cat-count");
      const emptyNote = block.querySelector(".empty-note");
      if(badge) badge.textContent = visibleInCat.toString();
      if(emptyNote) emptyNote.classList.toggle("d-none", visibleInCat !== 0);
      block.classList.toggle("d-none", visibleInCat === 0);
    });

    results.textContent = visible ? `${visible} vini trovati` : "Nessun vino trovato";
  }

  function resetAll(){
    q.value=""; colore.value=""; tipologia.value=""; regione.value="";
    apply();
  }

  [q,colore,tipologia,regione].forEach((el)=>{
    el?.addEventListener("input", apply);
    el?.addEventListener("change", apply);
  });
  reset?.addEventListener("click", resetAll);

  apply();
})();