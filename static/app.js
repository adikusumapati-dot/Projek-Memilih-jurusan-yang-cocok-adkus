async function call(url, method, body) {
  const res = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "Terjadi kesalahan");
  return data;
}

// Bookmark jurusan (tombol dengan atribut data-bookmark)
document.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-bookmark]");
  if (btn) {
    try {
      const d = await call(`/api/bookmark/${btn.dataset.bookmark}`, "POST");
      if (btn.hasAttribute("data-reload")) return location.reload();
      document.querySelectorAll(`[data-bookmark="${btn.dataset.bookmark}"]`).forEach((b) => {
        b.classList.toggle("btn-warning", d.saved);
        b.classList.toggle("btn-outline-warning", !d.saved);
        b.textContent = d.saved ? "★ Tersimpan" : "☆ Simpan";
      });
    } catch (err) {
      alert(err.message);
    }
    return;
  }

  // Hapus kampus target
  const del = e.target.closest("[data-del-target]");
  if (del && confirm("Hapus kampus target ini?")) {
    try {
      await call(`/api/targets/${del.dataset.delTarget}`, "DELETE");
      location.reload();
    } catch (err) {
      alert(err.message);
    }
  }
});

// Tambah kampus target
const tf = document.getElementById("targetForm");
if (tf) {
  tf.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await call("/api/targets", "POST", Object.fromEntries(new FormData(tf)));
      location.reload();
    } catch (err) {
      alert(err.message);
    }
  });
}
