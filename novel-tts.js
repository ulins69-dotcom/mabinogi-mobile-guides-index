/*
 * 小說頁的中文朗讀（2026-10-01 新增）。
 *
 * 用瀏覽器內建的語音合成（Web Speech API），不經過任何伺服器、不需要金鑰、不花錢（本站成本原則）。
 * 聲音來自讀者自己的裝置：電腦用 Edge 的「自然」語音最像真人；手機用系統內建的中文語音。
 *
 * 2026-10-01 起，同一套程式也直接內建在小說原稿（claude.ai artifact）裡；
 * 網站這支檔案改當備援：原稿已經有朗讀時（window.__erinnTTS），這支什麼都不做。
 * 萬一日後原稿改版時把內建的朗讀弄掉了，這支會自動補上。
 */
(function () {
  "use strict";

  // 小說原稿（claude.ai artifact）現在也內建同一套朗讀；已經裝過就不要再裝第二次
  if (window.__erinnTTS) return;
  window.__erinnTTS = true;

  var app = document.getElementById("app");
  if (!app) return;
  var synth = window.speechSynthesis;
  var supported = !!(synth && window.SpeechSynthesisUtterance);
  var MAX_CHUNK = 60; // 每次唸的字數上限：Chrome 的部分語音單句太長會中途斷掉

  var KEY = { rate: "erinn-tts-rate", voice: "erinn-tts-voice", auto: "erinn-tts-autonext" };
  function load(k) { try { return window.localStorage.getItem(k); } catch (e) { return null; } }
  function save(k, v) { try { window.localStorage.setItem(k, v); } catch (e) { /* 只是記住偏好，失敗也沒關係 */ } }

  var settings = {
    rate: parseFloat(load(KEY.rate)) || 1,
    voice: load(KEY.voice) || "",
    auto: load(KEY.auto) === "1"
  };
  // status: idle（沒在唸）／playing／paused
  var state = { status: "idle", chunks: [], idx: 0, gen: 0, paras: [], route: "", pendingAuto: false };
  var ui = { bar: null, play: null, stop: null, voiceSel: null, status: null, mini: null, miniPlay: null, miniText: null };

  // 跟原稿同一套「不用 innerHTML」的建元素方式
  function h(tag, attrs, kids) {
    var el = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      var v = attrs[k];
      if (v === null || v === undefined || v === false) return;
      if (k === "class") el.className = v;
      else if (k === "text") el.textContent = v;
      else el.setAttribute(k, v === true ? "" : String(v));
    });
    (kids || []).forEach(function (kid) {
      if (kid) el.appendChild(typeof kid === "string" ? document.createTextNode(kid) : kid);
    });
    return el;
  }

  // ---------- 樣式（沿用原稿的顏色變數，亮暗色自動跟著變） ----------
  var style = document.createElement("style");
  style.textContent = [
    ".tts-bar{font-family:var(--sans);display:flex;flex-wrap:wrap;gap:.45rem .7rem;align-items:center;margin:.9rem 0 0;padding:.65rem .75rem;background:var(--paper-2);border-radius:4px;font-size:.85rem;color:var(--ink-2)}",
    ".tts-bar button{font:inherit;background:var(--ink);color:var(--paper);border:0;border-radius:3px;padding:.35rem .85rem;cursor:pointer}",
    ".tts-bar button.ghost{background:none;color:var(--ink);border:1px solid var(--rule)}",
    ".tts-bar button[disabled]{opacity:.45;cursor:default}",
    ".tts-bar select{font:inherit;background:var(--paper);color:var(--ink);border:1px solid var(--rule);border-radius:3px;padding:.2rem .3rem;max-width:13rem}",
    ".tts-bar label{display:inline-flex;align-items:center;gap:.3rem;white-space:nowrap}",
    ".tts-bar .tts-status{color:var(--river);min-width:5.5em}",
    ".tts-hint{flex-basis:100%;margin:0;font-size:.75rem;line-height:1.6;color:var(--ink-2)}",
    ".prose p.tts-on{background:var(--paper-2);box-shadow:inset 3px 0 0 var(--lantern);padding:0 .45rem;margin-left:-.45rem;margin-right:-.45rem;border-radius:2px}",
    ".tts-reading .prose p{cursor:pointer}",
    ".tts-bar details{flex-basis:100%;margin:0;font-size:.75rem;line-height:1.6;color:var(--ink-2)}",
    ".tts-bar summary{cursor:pointer;width:max-content}",
    ".tts-mini{position:fixed;right:max(.75rem,env(safe-area-inset-right,0px));bottom:calc(env(safe-area-inset-bottom,0px) + .75rem);z-index:20;display:flex;gap:.1rem;align-items:center;background:var(--ink);color:var(--paper);border-radius:999px;padding:.2rem;font-family:var(--sans);font-size:.72rem;line-height:1;box-shadow:0 2px 10px rgba(0,0,0,.22);opacity:.9}",
    ".tts-mini[hidden],.tts-mini button[hidden]{display:none}",
    ".tts-mini button{font:inherit;font-size:.85rem;width:2.1rem;height:2.1rem;display:inline-flex;align-items:center;justify-content:center;background:none;color:var(--paper);border:0;border-radius:50%;cursor:pointer;padding:0}",
    ".tts-mini button:hover,.tts-mini button:focus-visible{background:rgba(255,255,255,.14)}",
    ".tts-mini .tts-n{padding:0 .15rem 0 .5rem;font-variant-numeric:tabular-nums;white-space:nowrap}",
    ".tts-mini .tts-n:empty{display:none}"
  ].join("\n");
  document.head.appendChild(style);

  // ---------- 語音 ----------
  function langOf(v) { return String(v.lang || "").replace("_", "-").toLowerCase(); }
  function zhVoices() {
    if (!supported) return [];
    return synth.getVoices().filter(function (v) { return /^(zh|cmn|yue)/.test(langOf(v)); });
  }
  // 台灣中文優先、「自然／線上」語音（較像真人）優先
  function rank(v) {
    var l = langOf(v), s = /tw|hant/.test(l) ? 4 : (/hk|yue/.test(l) ? 2 : 1);
    if (/natural|online|neural/i.test(v.name)) s += 3;
    return s;
  }
  function sortedVoices() { return zhVoices().sort(function (a, b) { return rank(b) - rank(a); }); }
  function pickVoice() {
    var list = sortedVoices();
    if (settings.voice) {
      for (var i = 0; i < list.length; i++) if (list[i].name === settings.voice) return list[i];
    }
    return list[0] || null;
  }

  // ---------- 把章節切成要唸的小段 ----------
  function speakable(t) {
    return t.replace(/[—─]+/g, "，").replace(/\s+/g, " ").trim(); // 「咚——」的破折號唸成停頓
  }
  function splitText(text) {
    var sentences = text.match(/[^。！？!?；;]+[。！？!?；;]*[」』）)]*/g) || [text];
    var out = [], buf = "";
    sentences.forEach(function (s) {
      s = s.trim();
      while (s.length > MAX_CHUNK) { // 太長的句子在逗號處再切
        var cut = s.lastIndexOf("，", MAX_CHUNK);
        if (cut < MAX_CHUNK * 0.4) cut = MAX_CHUNK - 1;
        if (buf) { out.push(buf); buf = ""; }
        out.push(s.slice(0, cut + 1));
        s = s.slice(cut + 1).trim();
      }
      if (!s) return;
      if ((buf + s).length <= MAX_CHUNK) buf += s; // 短句合併，唸起來比較順
      else { if (buf) out.push(buf); buf = s; }
    });
    if (buf) out.push(buf);
    return out.filter(function (c) { return /[㐀-鿿\w]/.test(c); });
  }
  function buildChunks(head, prose) {
    state.paras = Array.prototype.slice.call(prose.querySelectorAll("p"));
    var chunks = [];
    var title = head.querySelector("h1");
    if (title) chunks.push({ p: -1, text: speakable(title.textContent) }); // 先唸章名
    state.paras.forEach(function (p, i) {
      splitText(speakable(p.textContent)).forEach(function (t) { chunks.push({ p: i, text: t }); });
    });
    state.chunks = chunks;
  }

  // ---------- 播放控制 ----------
  function highlight(pi) {
    state.paras.forEach(function (p, i) { p.classList.toggle("tts-on", i === pi); });
    var el = state.paras[pi];
    if (!el) return;
    var r = el.getBoundingClientRect();
    if (r.top < 70 || r.bottom > window.innerHeight - 80) {
      var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      el.scrollIntoView({ block: "center", behavior: reduce ? "auto" : "smooth" });
    }
  }
  function speakNext() {
    var g = state.gen;
    if (state.idx >= state.chunks.length) { finish(); return; }
    var c = state.chunks[state.idx];
    highlight(c.p);
    var u = new SpeechSynthesisUtterance(c.text);
    u.lang = "zh-TW";
    var v = pickVoice();
    if (v) { u.voice = v; u.lang = v.lang; }
    u.rate = settings.rate;
    u.onend = function () {
      if (g !== state.gen || state.status !== "playing") return; // 已經暫停／停止／換段，舊的結束事件不理
      state.idx++;
      speakNext();
    };
    u.onerror = function (e) {
      if (g !== state.gen || e.error === "interrupted" || e.error === "canceled") return;
      state.idx++; // 這一小段唸不出來就跳下一段，不卡住
      speakNext();
    };
    synth.speak(u);
    render();
  }
  function play(from) {
    if (!supported) return;
    var head = app.querySelector(".chapter-head"), prose = app.querySelector(".prose");
    if (!head || !prose) return;
    if (!state.chunks.length) buildChunks(head, prose);
    if (typeof from === "number") state.idx = from;
    if (state.idx >= state.chunks.length) state.idx = 0;
    state.gen++;
    synth.cancel();
    state.status = "playing";
    app.classList.add("tts-reading");
    speakNext();
  }
  function pause() {
    state.gen++;
    synth.cancel(); // 用「取消後從同一小段重唸」代替 pause()／resume()，各家瀏覽器行為比較一致
    state.status = "paused";
    render();
  }
  function stop(message) {
    state.gen++;
    if (supported) synth.cancel();
    state.status = "idle";
    state.idx = 0;
    state.pendingAuto = false;
    state.paras.forEach(function (p) { p.classList.remove("tts-on"); });
    app.classList.remove("tts-reading");
    render(message);
  }
  function nextChapterLink() {
    var links = app.querySelectorAll(".pager a");
    for (var i = 0; i < links.length; i++) if (links[i].textContent === "下一章") return links[i];
    return null;
  }
  function finish() {
    var next = settings.auto ? nextChapterLink() : null;
    if (next) {
      state.pendingAuto = true; // 換頁後由 onRoute 接著唸
      location.hash = next.getAttribute("href");
    } else {
      stop(settings.auto ? "這是目前最新的一章。" : "這一章唸完了。");
    }
  }

  // ---------- 介面 ----------
  function render(message) {
    var total = state.chunks.length, n = Math.min(state.idx + 1, total);
    var text = state.status === "playing" ? "朗讀中 " + n + "／" + total
      : state.status === "paused" ? "已暫停 " + n + "／" + total
      : (message || "");
    if (ui.play) {
      ui.play.textContent = state.status === "playing" ? "❚❚ 暫停" : (state.status === "paused" ? "▶ 繼續" : "🔊 中文朗讀");
      ui.play.setAttribute("aria-label", state.status === "playing" ? "暫停朗讀" : "開始朗讀");
      ui.stop.disabled = state.status === "idle";
      ui.status.textContent = text;
    }
    if (ui.mini) {
      ui.mini.hidden = !app.querySelector(".prose");
      ui.miniText.textContent = state.status === "idle" ? "" : n + "／" + total;
      ui.miniStop.hidden = state.status === "idle";
      ui.miniPlay.textContent = state.status === "playing" ? "❚❚" : (state.status === "paused" ? "▶" : "🔊");
      var lbl = state.status === "playing" ? "暫停朗讀" : (state.status === "paused" ? "繼續朗讀" : "從畫面上這一段開始朗讀");
      ui.miniPlay.setAttribute("aria-label", lbl);
      ui.miniPlay.setAttribute("title", lbl);
    }
  }
  function toggle() { if (state.status === "playing") pause(); else play(); }
  // 讀到一半才想聽：從畫面上看得到的第一段開始唸
  function playFromView() {
    var head = app.querySelector(".chapter-head"), prose = app.querySelector(".prose");
    if (!head || !prose) return;
    if (!state.chunks.length) buildChunks(head, prose);
    if (head.getBoundingClientRect().bottom > 0) { play(0); return; }
    for (var i = 0; i < state.paras.length; i++) {
      if (state.paras[i].getBoundingClientRect().bottom > 80) {
        for (var j = 0; j < state.chunks.length; j++) if (state.chunks[j].p === i) { play(j); return; }
      }
    }
    play(0);
  }

  function fillVoices() {
    if (!ui.voiceSel) return;
    var sel = ui.voiceSel, list = sortedVoices();
    sel.textContent = "";
    sel.appendChild(h("option", { value: "", text: list.length ? "自動（中文）" : "裝置預設" }));
    list.forEach(function (v) {
      var natural = /natural|online|neural/i.test(v.name) ? "・自然" : "";
      sel.appendChild(h("option", { value: v.name, text: v.name.replace(/^Microsoft\s+/, "").replace(/\s*-\s*Chinese.*$/i, "") + "（" + langOf(v) + natural + "）" }));
    });
    sel.value = list.some(function (v) { return v.name === settings.voice; }) ? settings.voice : "";
  }

  function mountBar(head, prose) {
    if (!supported) {
      head.appendChild(h("p", { class: "tts-hint", text: "這個瀏覽器不支援語音朗讀，建議改用 Chrome、Edge 或 Safari。" }));
      return;
    }
    ui.play = h("button", { type: "button" });
    ui.stop = h("button", { type: "button", class: "ghost", text: "■ 停止", "aria-label": "停止朗讀" });
    ui.status = h("span", { class: "tts-status", role: "status", "aria-live": "polite" });
    var rateSel = h("select", { "aria-label": "語速" }, [0.8, 1, 1.2, 1.4].map(function (r) {
      return h("option", { value: String(r), text: r + "×" });
    }));
    rateSel.value = String(settings.rate);
    ui.voiceSel = h("select", { "aria-label": "聲音" });
    fillVoices();
    var auto = h("input", { type: "checkbox" });
    auto.checked = settings.auto;

    ui.play.addEventListener("click", toggle);
    ui.stop.addEventListener("click", function () { stop(); });
    rateSel.addEventListener("change", function () {
      settings.rate = parseFloat(rateSel.value) || 1;
      save(KEY.rate, String(settings.rate));
      if (state.status === "playing") play(state.idx); // 從目前這一小段用新語速重唸
    });
    ui.voiceSel.addEventListener("change", function () {
      settings.voice = ui.voiceSel.value;
      save(KEY.voice, settings.voice);
      if (state.status === "playing") play(state.idx);
    });
    auto.addEventListener("change", function () {
      settings.auto = auto.checked;
      save(KEY.auto, auto.checked ? "1" : "0");
    });

    ui.bar = h("div", { class: "tts-bar" }, [
      ui.play, ui.stop, ui.status,
      h("label", null, ["語速", rateSel]),
      h("label", null, ["聲音", ui.voiceSel]),
      h("label", null, [auto, "讀完自動下一章"]),
      h("details", null, [h("summary", { text: "說明" }), "用你裝置內建的語音，免費。讀到一半想聽，按右下角的 🔊，會從畫面上這一段開始；朗讀時點任何一段，就從那段開始。電腦建議用 Edge，選標「自然」的聲音最像真人；手機請保持螢幕開著，鎖屏可能會停。"])
    ]);
    head.appendChild(ui.bar);

    // 朗讀中（或暫停中）點段落：從那一段開始
    prose.addEventListener("click", function (e) {
      if (state.status === "idle") return;
      var p = e.target.closest ? e.target.closest("p") : null;
      var pi = p ? state.paras.indexOf(p) : -1;
      if (pi < 0) return;
      for (var i = 0; i < state.chunks.length; i++) if (state.chunks[i].p === pi) { play(i); return; }
    });
    render();
  }

  function mountMini() {
    if (!supported || ui.mini) return;
    ui.miniText = h("span", { class: "tts-n", role: "status", "aria-live": "off" });
    ui.miniPlay = h("button", { type: "button" });
    ui.miniStop = h("button", { type: "button", text: "■", "aria-label": "停止朗讀", title: "停止朗讀" });
    ui.miniPlay.addEventListener("click", function () { if (state.status === "idle") playFromView(); else toggle(); });
    ui.miniStop.addEventListener("click", function () { stop(); });
    ui.mini = h("div", { class: "tts-mini", hidden: true }, [ui.miniText, ui.miniPlay, ui.miniStop]);
    document.body.appendChild(ui.mini);
  }

  // ---------- 跟著原稿換頁 ----------
  function onRoute() {
    var head = app.querySelector(".chapter-head"), prose = app.querySelector(".prose");
    var route = location.hash || "#/";
    if (!head || !prose) { // 離開章節頁（目錄、人物、改名…）就停止
      if (state.status !== "idle") stop();
      state.route = route;
      render();
      return;
    }
    if (route !== state.route) {
      if (!state.pendingAuto && state.status !== "idle") stop();
      state.route = route;
      state.chunks = [];
      state.idx = 0;
    }
    if (!head.querySelector(".tts-bar") && !head.querySelector(".tts-hint")) mountBar(head, prose);
    if (state.pendingAuto) {
      state.pendingAuto = false;
      window.setTimeout(function () { play(0); }, 400);
    }
    render();
  }

  mountMini();
  if (supported) {
    if (typeof synth.addEventListener === "function") synth.addEventListener("voiceschanged", fillVoices);
    else synth.onvoiceschanged = fillVoices;
    window.addEventListener("pagehide", function () { synth.cancel(); }); // 關掉頁面時不要繼續唸
  }
  new MutationObserver(onRoute).observe(app, { childList: true });
  onRoute(); // 直接打開某一章的網址時，原稿已經畫好了
})();
