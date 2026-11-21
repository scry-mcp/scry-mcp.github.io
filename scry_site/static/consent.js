/* Consent and Google Analytics. Nothing is requested from Google until the visitor accepts, and
   only on the host named in data-host. The page reads the same without this file. */
(() => {
  const me = document.querySelector("script[data-ga]");
  if (!me) return;
  const id = me.dataset.ga, hosts = me.dataset.host.split(","), KEY = "scry-consent-v1",
    LIFE = 183 * 24 * 3600 * 1000;
  if (!id || !hosts.includes(location.hostname)) return;

  // A browser can deny storage for the origin: nothing is remembered and every page asks again.
  const store = {
    get() { try { return localStorage.getItem(KEY); } catch { return null; } },
    set(v) { try { localStorage.setItem(KEY, v); } catch {} },
    del() { try { localStorage.removeItem(KEY); } catch {} },
  };
  const read = () => {
    try {
      const r = JSON.parse(store.get());
      if ((r.decision === "granted" || r.decision === "denied") && Number.isFinite(r.at)
          && r.at <= Date.now() && Date.now() - r.at <= LIFE) return r.decision;
    } catch {}
    return null;
  };

  // Without a granted choice the tag sends nothing and the cookies of an earlier visit go too.
  const off = "ga-disable-" + id;
  const withdraw = () => {
    window[off] = true;
    if (loaded) gtag("consent", "update", { analytics_storage: "denied" });
    for (const part of document.cookie.split(";")) {
      const name = part.split("=")[0].trim();
      if (!/^_ga(_|$)/.test(name)) continue;
      for (const scope of ["", "; domain=" + location.hostname, "; domain=." + location.hostname])
        document.cookie = name + "=; Max-Age=0; path=/" + scope;
    }
  };

  let loaded = false;
  const load = () => {
    window[off] = false;
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
    else withdraw();
  };
  for (const b of document.querySelectorAll("[data-consent]")) {
    b.hidden = false;
    b.addEventListener("click", () => {
      if (b.dataset.consent !== "reset") return decide(b.dataset.consent);
      store.del();
      withdraw();
      if (banner) { banner.hidden = false; banner.querySelector("button").focus(); }
    });
  }
  // Another tab's choice reaches this one: a tab already measuring stops when it is rejected.
  addEventListener("storage", e => {
    if (e.key !== null && e.key !== KEY) return;
    const choice = read();
    if (banner) banner.hidden = choice !== null;
    if (choice === "granted") load();
    else withdraw();
  });
  const now = read();
  if (now === "granted") load();
  else if (now === null && banner) banner.hidden = false;
})();
