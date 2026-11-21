/* Consent and Google Analytics. Nothing is requested from Google until the visitor accepts, and
   only on the host named in data-host. The page reads the same without this file. */
(() => {
  const me = document.querySelector("script[data-ga]");
  if (!me) return;
  const id = me.dataset.ga, hosts = me.dataset.host.split(","), KEY = "scry-consent-v1",
    LIFE = 183 * 24 * 3600 * 1000;
  if (!id || !hosts.includes(location.hostname)) return;

  // A browser can deny storage for the origin: the choice then lives in memory for the visit.
  const memory = {};
  const store = {
    get() { try { const v = localStorage.getItem(KEY); if (v !== null) return v; } catch {} return memory[KEY] ?? null; },
    set(v) { try { localStorage.setItem(KEY, v); } catch { memory[KEY] = v; } },
    del() { try { localStorage.removeItem(KEY); } catch {} delete memory[KEY]; },
  };
  const read = () => {
    try {
      const r = JSON.parse(store.get());
      if ((r.decision === "granted" || r.decision === "denied") && Number.isFinite(r.at)
          && r.at <= Date.now() && Date.now() - r.at <= LIFE) return r.decision;
    } catch {}
    return null;
  };

  let loaded = false;
  const load = () => {
    if (loaded) return gtag("consent", "update", { analytics_storage: "granted" });
    loaded = true;
    const layer = window.dataLayer = window.dataLayer || [];
    // gtag.js reads the arguments object and ignores an array.
    window.gtag = function () { layer.push(arguments); };
    gtag("consent", "default", { ad_storage: "denied", ad_user_data: "denied",
      ad_personalization: "denied", analytics_storage: "denied" });
    gtag("consent", "update", { analytics_storage: "granted" });
    gtag("js", new Date());
    gtag("config", id);
    const s = document.createElement("script");
    s.async = true;
    s.src = "https://www.googletagmanager.com/gtag/js?id=" + encodeURIComponent(id);
    document.head.append(s);
  };

  const banner = document.getElementById("consent");
  const decide = choice => {
    store.set(JSON.stringify({ decision: choice, at: Date.now() }));
    if (banner) banner.hidden = true;
    if (choice === "granted") load();
    else if (loaded) gtag("consent", "update", { analytics_storage: "denied" });
  };
  for (const b of document.querySelectorAll("[data-consent]")) {
    b.hidden = false;
    b.addEventListener("click", () => {
      if (b.dataset.consent !== "reset") return decide(b.dataset.consent);
      store.del();
      if (banner) { banner.hidden = false; banner.querySelector("button").focus(); }
    });
  }
  // Only the buttons inside the banner were shown above; the banner opens when no choice stands.
  if (banner) for (const b of banner.querySelectorAll("button")) b.hidden = false;
  const now = read();
  if (now === "granted") load();
  else if (now === null && banner) banner.hidden = false;
})();
