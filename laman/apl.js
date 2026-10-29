// MintRadar datt.my — teks dari bahasa.json, nombor dari /data/stats.json (dijana radar setiap 10 min). Tiada pustaka luar.
(function () {
  "use strict";
  var KUNCI_BAHASA = "mintradar-bahasa";
  var teks = null, data = null, bahasa = "en";

  try { bahasa = localStorage.getItem(KUNCI_BAHASA) || ""; } catch (e) { bahasa = ""; }
  if (bahasa !== "en" && bahasa !== "ms") bahasa = (navigator.language || "").toLowerCase().indexOf("ms") === 0 ? "ms" : "en";

  function t(k, ganti) {
    var s = (teks && teks[bahasa] && teks[bahasa][k]) || "";
    if (ganti) Object.keys(ganti).forEach(function (n) { s = s.split("{" + n + "}").join(String(ganti[n])); });
    return s;
  }
  function el(tag, kelas, isi) {
    var e = document.createElement(tag);
    if (kelas) e.className = kelas;
    if (isi != null) e.textContent = isi;
    return e;
  }
  function bnb(x) {
    var s = (x >= 0 ? "+" : "−") + Math.abs(x).toFixed(4) + " BNB";
    return s;
  }
  function lalu(ts) {
    var m = Math.max(0, Math.round((Date.now() / 1000 - ts) / 60));
    return m < 90 ? t("minit_lalu", { n: m }) : t("jam_lalu", { n: Math.round(m / 60) });
  }
  function pendek(a) { return a.slice(0, 6) + "…" + a.slice(-4); }

  function lukisTeks() {
    document.documentElement.lang = bahasa === "ms" ? "ms" : "en";
    document.title = t("tajuk_laman");
    Array.prototype.forEach.call(document.querySelectorAll("[data-t]"), function (n) {
      var v = t(n.getAttribute("data-t"));
      if (v) n.textContent = v;
    });
  }

  function lukisData() {
    var kaki = document.getElementById("kaki-data");
    if (!data) { kaki.textContent = t("kaki_gagal"); return; }
    var tb = document.getElementById("senarai-sentuhan");
    tb.textContent = "";
    data.terbaru.forEach(function (s) {
      var tr = el("tr");
      var td = el("td");
      td.appendChild(el("span", "nama-koleksi", s.nama || t("tanpa_nama")));
      td.appendChild(el("span", "alamat", pendek(s.alamat)));
      tr.appendChild(td);
      var tj = el("td");
      tj.appendChild(el("span", "jenis jenis-" + s.kelas, t("jenis_" + s.kelas)));
      tr.appendChild(tj);
      tr.appendChild(selTd(s.keselamatan));
      tr.appendChild(el("td", "nombor", s.mint.toLocaleString(bahasa)));
      tr.appendChild(el("td", "nombor", lalu(s.ts_panas)));
      tb.appendChild(tr);
    });

    var dl = document.getElementById("senarai-kertas");
    dl.textContent = "";
    data.kertas.forEach(function (k) {
      var d = el("div");
      d.appendChild(el("dt", null, t("kertas_jual", { jam: k.jam })));
      var b = el("dd", "bersih " + (k.mint ? (k.bersih_bnb >= 0 ? "positif" : "negatif") : ""), k.mint ? bnb(k.bersih_bnb) : "—");
      d.appendChild(b);
      d.appendChild(el("dd", "butir", k.mint ? t("kertas_baris", { mint: k.mint, untung: k.untung, pembeli: k.ada_pembeli }) : t("kertas_belum")));
      dl.appendChild(d);
    });

    var ol = document.getElementById("senarai-teratas");
    ol.textContent = "";
    data.teratas_24j.forEach(function (w) {
      var li = el("li");
      li.appendChild(el("span", "nama-koleksi", w.nama || pendek(w.alamat)));
      li.appendChild(el("span", "bersih positif", bnb(w.bersih_bnb)));
      li.appendChild(el("span", "butir", t("teratas_jualan", { n: w.jualan })));
      ol.appendChild(li);
    });

    var ul = document.getElementById("senarai-amaran");
    ul.textContent = "";
    if (!data.amaran || !data.amaran.length) ul.appendChild(el("li", "kosong", t("amaran_kosong")));
    (data.amaran || []).forEach(function (a) {
      var li = el("li");
      li.appendChild(el("span", "nama-koleksi", a.nama || pendek(a.alamat)));
      li.appendChild(el("span", "alamat", a.alamat));
      a.temuan.filter(function (x) { return x.kod === "KEKAL_DANA" || x.kod === "PROKSI"; })
        .forEach(function (x) { li.appendChild(el("span", "temuan", teksTemuan(x))); });
      ul.appendChild(li);
    });
    if (data.semakan_24j) document.getElementById("semakan-baris").textContent = t("semakan_baris", data.semakan_24j);

    var tp = data.tumpuan_24j;
    if (tp && tp.bil_kedudukan) {
      var lain = tp.bersih_semua_bnb - tp.untung_teratas_bnb;
      document.getElementById("tumpuan").textContent = t("tumpuan_baris", {
        n: tp.n_teratas, teratas: tp.untung_teratas_bnb.toFixed(4), semua: tp.bersih_semua_bnb.toFixed(4),
        baki: tp.bil_kedudukan - tp.n_teratas, lain: (lain >= 0 ? "+" : "\u2212") + Math.abs(lain).toFixed(4)
      });
    }
    var masa = new Date(data.dijana * 1000).toLocaleString(bahasa === "ms" ? "ms-MY" : "en-GB", { dateStyle: "medium", timeStyle: "short" });
    kaki.textContent = t("kaki_dijana", { masa: masa, blok: data.blok.toLocaleString(bahasa) });
  }

  function teksTemuan(x) {
    return t("temuan_" + x.kod, { fungsi: x.fungsi ? x.fungsi + "()" : "" });
  }
  function selTd(k) {
    var td = el("td", "selamat");
    var label = k ? k.label : "belum";
    var lencana = el("span", "lencana lencana-" + label, t("label_" + label));
    td.appendChild(lencana);
    if (k && k.temuan.length) {
      var unik = [], dilihat = {};
      k.temuan.forEach(function (x) { if (!dilihat[x.kod]) { dilihat[x.kod] = 1; unik.push(x); } });
      td.appendChild(el("span", "temuan", unik.slice(0, 2).map(teksTemuan).join(" ")));
    }
    return td;
  }

  function ambil(url) {
    return fetch(url, { cache: "no-store" }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); });
  }

  function muatData() {
    return ambil("/data/stats.json").then(function (d) { data = d; }, function () { data = null; }).then(lukisData);
  }

  document.getElementById("tukar-bahasa").addEventListener("click", function () {
    bahasa = bahasa === "en" ? "ms" : "en";
    try { localStorage.setItem(KUNCI_BAHASA, bahasa); } catch (e) { /* pelayar peribadi: abaikan */ }
    lukisTeks();
    lukisData();
  });

  ambil("/bahasa.json").then(function (b) { teks = b; lukisTeks(); return muatData(); }).then(function () {
    document.body.classList.add("sedia");
  });
  setInterval(muatData, 60000);
})();
