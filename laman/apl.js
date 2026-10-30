// MintRadar datt.my — teks dari bahasa.json, nombor dari /data/stats.json (dijana radar setiap 10 min). Tiada pustaka luar.
(function () {
  "use strict";
  var KUNCI_BAHASA = "mintradar-bahasa";
  var teks = null, data = null, bahasa = "en";

  // D43: bahasa = URL (/ = EN, /ms/ = BM; teks sudah dipapar pelayan). Pautan lama ?lang=ms dialih ke /ms/.
  if (/[?&]lang=ms\b/.test(location.search) && location.pathname.indexOf("/ms/") !== 0) { location.replace("/ms/" + location.hash); return; }
  bahasa = location.pathname.indexOf("/ms/") === 0 ? "ms" : "en";
  try { localStorage.setItem(KUNCI_BAHASA, bahasa); } catch (e) { /* pelayar peribadi: abaikan */ }

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
    lukisScouts();

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
    window.MR_DATA = data;
    document.dispatchEvent(new CustomEvent("mr-data", { detail: data }));
    lukisToken(data.token);
    lukisUtama();
    lukisSkop();
    lukisPeta();
    hadJadual();
    lukisCukai();
    lukisSebenar();
    lukisSegar();
  }

  // Pembuka (D39): tiga angka dari stats.json
  function lukisUtama() {
    var k24 = (data.kertas || []).filter(function (k) { return k.jam === 24; })[0];
    document.getElementById("u-percuma").textContent = data.hari ? data.hari.percuma.toLocaleString(bahasa) : "\u2014";
    document.getElementById("u-pembeli").textContent = k24 ? t("utama_daripada", { a: k24.ada_pembeli, b: k24.mint }) : "\u2014";
    document.getElementById("u-merah").textContent = data.semakan_24j ? data.semakan_24j.merah.toLocaleString(bahasa) : "\u2014";
  }

  // Skop (D39): seperti radar sebenar — garis sapuan = sekarang; sudut di belakangnya = berapa lama dahulu ditanda (kontrak paling
  // 2 jam = 300°), jarak dari tengah = log mint. Versi pertama (jejari = umur) mengumpul semua titik di tengah.
  var NS = "http://www.w3.org/2000/svg", SAPU = -52 * Math.PI / 180;
  function lukisSkop() {
    var g = document.getElementById("skop-titik");
    g.textContent = "";
    var senarai = (data.terbaru || []).slice(0, 15), kini = Date.now() / 1000;
    if (!senarai.length) return;
    var tertua = 7200;  // tetingkap TETAP: 300° = 2 jam (relatif kepada senarai = semua titik di hadapan sapuan bila umur hampir sama)
    var mints = senarai.map(function (s) { return Math.log(Math.max(2, s.mint)); });
    var lo = Math.min.apply(null, mints), hi = Math.max.apply(null, mints);
    senarai.forEach(function (s, i) {
      var sud = SAPU - Math.min(1, (kini - s.ts_panas) / tertua) * (300 * Math.PI / 180);
      var r = 40 + (hi > lo ? (mints[i] - lo) / (hi - lo) : 0.5) * 108;
      var c = document.createElementNS(NS, "circle");
      c.setAttribute("cx", (170 + r * Math.cos(sud)).toFixed(1));
      c.setAttribute("cy", (170 + r * Math.sin(sud)).toFixed(1));
      c.setAttribute("r", "6");
      c.setAttribute("class", "titik-" + (s.keselamatan ? s.keselamatan.label : "belum"));
      var tt = document.createElementNS(NS, "title");
      tt.textContent = (s.nama || t("tanpa_nama")) + ": " + t("label_" + (s.keselamatan ? s.keselamatan.label : "belum")) + ", " + s.mint.toLocaleString(bahasa) + " mints, " + lalu(s.ts_panas);
      c.appendChild(tt);
      g.appendChild(c);
    });
  }

  // D41: kesegaran (blok + umur data, berdetik), ke mana cukai pergi, rekod sebenar sebelum/selepas peraturan jualan
  function tarikh(ts) {
    return new Date(ts * 1000).toLocaleString(bahasa === "ms" ? "ms-MY" : "en-GB", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit", timeZoneName: "short" });
  }
  function lukisSegar() {
    var e = document.getElementById("segar");
    if (!data || !data.blok) { e.textContent = ""; return; }
    var n = Math.max(0, Math.round(Date.now() / 1000 - data.dijana));
    var umur = n < 120 ? t("saat_lalu", { n: n }) : lalu(data.dijana);
    e.textContent = t("segar", { blok: data.blok.toLocaleString(bahasa), saat: umur });
  }
  setInterval(lukisSegar, 1000);

  function baris(dl, label, nilai) {
    var d = el("div");
    d.appendChild(el("dt", null, label));
    d.appendChild(el("dd", null, nilai));
    dl.appendChild(d);
  }
  function angka(x, digit) { return x === null || x === undefined ? "\u2014" : Number(x).toLocaleString(bahasa, { maximumFractionDigits: digit }); }

  function lukisCukai() {
    var w = data.dompet || {}, tk = data.token || {};
    var dl = document.getElementById("cukai-angka");
    dl.textContent = "";
    baris(dl, t("cukai_diterima"), tk.alamat ? (tk.cukai_bnb === null || tk.cukai_bnb === undefined ? "\u2014" : angka(tk.cukai_bnb, 6) + " BNB") : "0 BNB");
    baris(dl, t("cukai_bnb"), w.bnb === null || w.bnb === undefined ? "\u2014" : angka(w.bnb, 5) + " BNB");
    baris(dl, t("cukai_usdt"), w.usdt === null || w.usdt === undefined ? "\u2014" : angka(w.usdt, 2) + " USDT");
    baris(dl, t("cukai_tx"), angka(w.nonce, 0));
    var a = document.getElementById("cukai-wallet");
    if (w.alamat) { a.textContent = w.alamat; a.href = "https://bscscan.com/address/" + w.alamat; }
    var ul = document.getElementById("cukai-belanja");
    ul.textContent = "";
    var b = data.belanja || [];
    if (!b.length) ul.appendChild(el("li", "kosong", t("cukai_belanja_kosong")));
    b.forEach(function (x) {
      var li = el("li");
      li.appendChild(el("span", null, x.perkara + " \u2014 " + angka(x.bnb, 6) + " BNB"));
      var l = el("a", "alamat", pendek(x.tx)); l.href = "https://bscscan.com/tx/" + x.tx; l.rel = "noopener";
      li.appendChild(l);
      ul.appendChild(li);
    });
  }

  function lukisSebenar() {
    var sb = data.sebenar, isi = document.getElementById("sebenar-isi");
    isi.textContent = "";
    if (!sb) return;
    var ket = document.querySelector("[data-t=sebenar_ket]");
    ket.textContent = t("sebenar_ket", { mula: sb.mula ? tarikh(sb.mula) : "\u2014" });
    [["sebelum", "sebenar_sebelum_ket"], ["selepas", "sebenar_selepas_ket"]].forEach(function (b) {
      var x = sb[b[0]], kad = el("div", "sebenar-kad");
      kad.appendChild(el("h3", null, t("sebenar_" + b[0])));
      kad.appendChild(el("p", "ket", t(b[1], { sejak: tarikh(sb.sejak) })));
      var dl = el("dl", "sebenar-angka");
      baris(dl, t("sebenar_mint"), angka(x.mint, 0));
      baris(dl, t("sebenar_nft"), angka(x.disenarai + x.terjual + x.dipegang, 0));
      baris(dl, t("sebenar_terjual"), angka(x.terjual, 0));
      baris(dl, t("sebenar_gas"), angka(x.gas_bnb, 5) + " BNB");
      var dd = (x.bersih_bnb >= 0 ? "+" : "\u2212") + Math.abs(x.bersih_bnb).toFixed(5) + " BNB";
      baris(dl, t("sebenar_bersih"), dd);
      dl.lastChild.lastChild.className = x.bersih_bnb >= 0 ? "positif" : "negatif";
      kad.appendChild(dl);
      isi.appendChild(kad);
    });
  }

  // Jadual: 8 baris dahulu (SSR memapar semua; JS menyorok baki + butang)
  var SEMUA = false, HAD = 8;
  function hadJadual() {
    var tr = document.querySelectorAll("#senarai-sentuhan tr"), b = document.getElementById("tunjuk-semua");
    Array.prototype.forEach.call(tr, function (r, i) { r.hidden = !SEMUA && i >= HAD; });
    b.hidden = tr.length <= HAD;
    b.textContent = SEMUA ? t("tunjuk_kurang") : t("tunjuk_semua", { n: tr.length });
    b.setAttribute("aria-expanded", SEMUA ? "true" : "false");
  }
  document.getElementById("tunjuk-semua").addEventListener("click", function () { SEMUA = !SEMUA; hadJadual(); });

  // Peta haba: baris = kontrak, petak = minit; kecerahan ikut log mint (kaca laut)
  function lukisPeta() {
    var isi = document.getElementById("peta-isi");
    isi.textContent = "";
    var p = data.peta && data.peta.kontrak || [];
    if (!p.length) { isi.appendChild(el("p", "peta-kosong", t("peta_kosong"))); return; }
    var mx = 1;
    p.forEach(function (k) { k.minit.forEach(function (v) { if (v > mx) mx = v; }); });
    p.forEach(function (k) {
      var baris = el("div", "peta-baris");
      var nama = el("div", "peta-nama");
      nama.appendChild(el("b", null, k.nama || t("tanpa_nama")));
      var lab = k.label || "belum";
      nama.appendChild(el("span", "lencana lencana-" + lab, t("label_" + lab)));
      nama.appendChild(el("span", null, k.jualan ? t("peta_jualan", { n: k.jualan }) : t("peta_tiada_jualan")));
      baris.appendChild(nama);
      var petak = el("div", "petak");
      k.minit.forEach(function (v) {
        var i = el("i");
        if (v > 0) i.style.background = "rgba(159,227,212," + (0.22 + 0.78 * Math.log(1 + v) / Math.log(1 + mx)).toFixed(2) + ")";
        petak.appendChild(i);
      });
      baris.appendChild(petak);
      baris.appendChild(el("div", "peta-jumlah", k.jumlah.toLocaleString(bahasa)));
      isi.appendChild(baris);
    });
  }

  // Token $MRADAR (D37): tersorok tanpa data; sebelum lancar = masa lancar; selepas = alamat + angka (sengkang = tiada angka)
  function wang(x, digit) {
    if (x === null || x === undefined) return "\u2014";
    if (digit) return "$" + Number(x).toPrecision(digit);
    return "$" + Math.round(x).toLocaleString(bahasa);
  }
  function lukisToken(k) {
    var sek = document.getElementById("token");
    if (!k || k.status === "rejected" || k.status === "failed") { sek.hidden = true; return; }
    sek.hidden = false;
    var tunggu = document.getElementById("token-menunggu"), hidup = document.getElementById("token-hidup");
    if (!k.alamat) {
      hidup.hidden = true;
      tunggu.hidden = false;
      var bila = k.lancar_pada ? new Date(k.lancar_pada) : null;
      tunggu.textContent = bila && bila > new Date()
        ? t(k.status === "review" ? "token_semakan" : "token_menunggu", { masa: bila.toLocaleString(bahasa === "ms" ? "ms-MY" : "en-GB", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short" }) })
        : t("token_menunggu_lalu");
      return;
    }
    tunggu.hidden = true;
    hidup.hidden = false;
    document.getElementById("token-alamat").textContent = k.alamat;
    document.getElementById("token-flap").href = k.flap_url || ("https://flap.sh/bnb/" + k.alamat);
    document.getElementById("token-bscscan").href = "https://bscscan.com/token/" + k.alamat;
    document.getElementById("token-dex").href = "https://dexscreener.com/bsc/" + k.alamat;
    var dl = document.getElementById("token-angka");
    dl.textContent = "";
    [["token_harga", wang(k.harga_usd, 3)], ["token_mcap", wang(k.mcap_usd)], ["token_likuiditi", wang(k.likuiditi_usd)],
     ["token_volume", wang(k.volume_24j_usd)], ["token_pemegang", k.pemegang ? k.pemegang.toLocaleString(bahasa) : "\u2014"],
     ["token_cukai", k.cukai_bnb === null || k.cukai_bnb === undefined ? "\u2014" : bnb(k.cukai_bnb)]].forEach(function (r) {
      var d = el("div");
      d.appendChild(el("dt", null, t(r[0])));
      d.appendChild(el("dd", null, r[1]));
      dl.appendChild(d);
    });
  }

  document.getElementById("token-salin").addEventListener("click", function () {
    var b = this, a = document.getElementById("token-alamat").textContent;
    function siap() { b.textContent = t("token_disalin"); setTimeout(function () { b.textContent = t("token_salin"); }, 1600); }
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(a).then(siap, function () {});
    else { var r = document.createRange(); r.selectNodeContents(document.getElementById("token-alamat")); var s = getSelection(); s.removeAllRanges(); s.addRange(r); }
  });

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

  // D47: papan pendahulu Scouts (pelapor pertama kontrak berisiko yang disahkan automatik)
  function lukisScouts() {
    var sc = data && data.scouts;
    if (!sc) return;
    document.getElementById("scouts-ket").textContent = t("scouts_ket", { had: sc.daily_limit });
    var ol = document.getElementById("senarai-scouts");
    ol.textContent = "";
    if (!sc.leaderboard.length) ol.appendChild(el("li", "kosong", t("scouts_kosong")));
    sc.leaderboard.forEach(function (x) {
      var li = el("li");
      li.appendChild(el("span", "nama-koleksi", x.agent));
      li.appendChild(el("span", "bersih positif", t("scouts_mata", { n: x.points })));
      li.appendChild(el("span", "butir", t("scouts_butir", { disahkan: x.confirmed, laporan: x.reports })));
      ol.appendChild(li);
    });
    document.getElementById("scouts-baris").textContent = t("scouts_baris", { laporan: sc.reports, disahkan: sc.confirmed });
  }

  function muatData() {
    return ambil("/data/stats.json").then(function (d) { data = d; }, function () { data = null; }).then(lukisData);
  }

  // Menu telefon: tutup selepas memilih pautan atau Escape
  var menu = document.getElementById("menu");
  menu.addEventListener("click", function (ev) { if (ev.target.closest("a")) menu.open = false; });
  document.addEventListener("keydown", function (ev) { if (ev.key === "Escape" && menu.open) { menu.open = false; menu.querySelector("summary").focus(); } });

  // D43: penyemak kontrak — /data/kontrak/<alamat>.json (ditulis radar setiap semakan); tiada = arahan @sasaoff
  var ALAMAT = new RegExp("^0x[0-9a-fA-F]{40}$");
  function salinButang(teksSalin) {
    var b = el("button", "salin", t("periksa_salin"));
    b.type = "button";
    b.addEventListener("click", function () {
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(teksSalin).then(function () {
        b.textContent = t("periksa_disalin"); setTimeout(function () { b.textContent = t("periksa_salin"); }, 1600);
      }, function () {});
    });
    return b;
  }
  function senaraiTemuan(tajuk, label, temuan) {
    var kad = el("div", "periksa-kad");
    var h = el("h3"); h.appendChild(document.createTextNode(tajuk + " "));
    h.appendChild(el("span", "lencana lencana-" + label, t("umum_" + label)));  // label umum: kuning pasaran ≠ "kuasa owner"
    kad.appendChild(h);
    var ul = el("ul");
    temuan.forEach(function (x) { ul.appendChild(el("li", null, x)); });
    kad.appendChild(ul);
    return kad;
  }
  var disemak = null, disemakPada = 0;
  function senaraiDisemak() {
    if (disemak && Date.now() - disemakPada < 300000) return Promise.resolve(disemak);
    return fetch("/data/kontrak/index.json", { cache: "no-store" }).then(function (r) { return r.ok ? r.json() : { contracts: [] }; }).then(function (j) {
      disemak = {}; disemakPada = Date.now();
      (j.contracts || []).forEach(function (c) { disemak[c.address.toLowerCase()] = 1; });
      return disemak;
    });
  }
  document.getElementById("periksa-borang").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var a = document.getElementById("periksa-alamat").value.trim(), hasil = document.getElementById("periksa-hasil");
    hasil.textContent = "";
    if (!ALAMAT.test(a)) { hasil.appendChild(el("p", "periksa-salah", t("periksa_salah"))); return; }
    a = a.toLowerCase();
    hasil.appendChild(el("p", "ket", t("periksa_memuat")));
    // index.json dahulu: alamat belum disemak dijawab tanpa permintaan 404 (pelayar mencatat setiap 404 sebagai ralat konsol)
    senaraiDisemak().then(function (ada) {
      return ada[a] ? fetch("/data/kontrak/" + a + ".json", { cache: "no-store" }) : { status: 404 };
    }).then(function (r) {
      hasil.textContent = "";
      if (r.status === 404) {
        hasil.appendChild(el("p", null, t("periksa_tiada")));
        var baris = el("div", "periksa-sebut");
        var kod = "@sasaoff " + a;
        baris.appendChild(el("code", "alamat", kod));
        baris.appendChild(salinButang(kod));
        hasil.appendChild(baris);
        return null;
      }
      if (!r.ok) throw new Error(r.status);
      return r.json();
    }).then(function (d) {
      if (!d) return;
      var kepala = el("div", "periksa-kepala");
      kepala.appendChild(el("b", null, d.name || pendek(d.address)));
      kepala.appendChild(el("span", "lencana lencana-" + d.label, t("umum_" + d.label)));
      kepala.appendChild(el("span", "ket", t("periksa_disemak", { masa: lalu(d.checked_at) })));
      hasil.appendChild(kepala);
      // teks dari KOD temuan dalam bahasa halaman (JSON kontrak ditulis EN untuk ejen); kod tidak dikenali = teks JSON
      var kod = (d.findings || []).filter(function (x) { return x.code !== "DILEPASKAN"; }).map(function (x) {
        return t("temuan_" + x.code, { fungsi: x["function"] ? x["function"] + "()" : "" }) || x.text;
      });
      hasil.appendChild(senaraiTemuan(t("periksa_kod"), d.label, kod.length ? kod : [t("periksa_bersih")]));
      if (d.market) hasil.appendChild(senaraiTemuan(t("periksa_pasaran"), d.market.label, (d.market.findings || []).map(function (x) {
        return t("pasaran_" + x.code, { nilai: x.value }) || x.text;
      })));
      var p = el("p", "periksa-pautan");
      var l = el("a", null, t("periksa_json")); l.href = "/data/kontrak/" + a + ".json";
      p.appendChild(l);
      var bs = el("a", null, "BscScan"); bs.href = "https://bscscan.com/address/" + a; bs.rel = "noopener";
      p.appendChild(bs);
      hasil.appendChild(p);
    }).catch(function () { hasil.textContent = ""; hasil.appendChild(el("p", "periksa-salah", t("periksa_gagal"))); });
  });

  // D43: medan 3D — dimuat HANYA bila WebGL ada, tiada "kurangkan data", selepas data sedia; gagal = skop SVG kekal
  function muat3D() {
    if (window.MR_3D || navigator.connection && navigator.connection.saveData) return;
    var c = document.createElement("canvas");
    if (!(c.getContext("webgl2") || c.getContext("webgl"))) return;
    window.MR_3D = true;
    var sc = document.createElement("script");
    sc.type = "module"; sc.src = "/medan3d.js?v=1";
    document.body.appendChild(sc);
  }

  ambil("/bahasa.json").then(function (b) { teks = b; lukisTeks(); return muatData(); }).then(function () {
    document.body.classList.add("sedia");
    muat3D();
  });
  setInterval(muatData, 60000);
})();
