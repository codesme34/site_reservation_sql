function switchTab(tab) {
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
      document.getElementById('panel-' + tab).classList.add('active');
      document.querySelectorAll('.tab-pill').forEach(b => {
        b.classList.toggle('active', b.dataset.tab === tab);
      });
    }
const choiceEl = document.getElementById("choice")
if (choiceEl) {
    choiceEl.addEventListener("change", function() {
        if (this.value === "hotel") {
            document.getElementById("dest-hotel").style.display = "block"
            document.getElementById("dest-vol").style.display = "none"
        } else {
            document.getElementById("dest-vol").style.display = "block"
            document.getElementById("dest-hotel").style.display = "none"
        }
    })
}


