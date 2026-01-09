(function(){
  document.querySelectorAll(".attivo-toggle").forEach((chk)=>{
    chk.addEventListener("change", async ()=>{
      const id = chk.dataset.id;
      const form = new FormData();
      form.set("attivo", chk.checked ? "1" : "0");
      try{
        const res = await fetch(`/admin/toggle/${id}`, {method:"POST", body: form});
        if(!res.ok) throw new Error("HTTP " + res.status);
      }catch(err){
        alert("Errore nel salvataggio. Riprova.");
        chk.checked = !chk.checked;
      }
    });
  });
})();