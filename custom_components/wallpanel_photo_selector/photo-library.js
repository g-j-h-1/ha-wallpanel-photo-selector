class WallpanelPhotoLibrary extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._data = { photos: [], errors: [] };
    this._filter = "all";
    this._search = "";
    this._loaded = false;
  }

  set hass(value) {
    this._hass = value;
    if (!this._loaded && value) {
      this._loaded = true;
      this.load();
    }
  }

  connectedCallback() { this.render(); }

  async load() {
    if (!this._hass) return;
    try {
      this._data = await this._hass.connection.sendMessagePromise({
        type: "wallpanel_photo_selector/library"
      });
      this._error = null;
    } catch (error) {
      this._error = String(error.message || error);
    }
    this.render();
  }

  render() {
    const root = this.shadowRoot;
    root.replaceChildren();
    const style = document.createElement("style");
    style.textContent = `
      :host { display:block; color:var(--primary-text-color); background:var(--primary-background-color); min-height:100%; font-family:var(--paper-font-body1_-_font-family, sans-serif) }
      main { max-width:1100px; margin:auto; padding:20px }
      header { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap }
      h1 { font-size:24px; margin:0 }
      .muted { color:var(--secondary-text-color); font-size:13px }
      .controls { display:flex; flex-wrap:wrap; gap:8px; margin:20px 0 }
      button,input { font:inherit; border:1px solid var(--divider-color); border-radius:9px; padding:10px; background:var(--card-background-color); color:var(--primary-text-color) }
      button { cursor:pointer } button[aria-pressed=true] { background:var(--primary-color); color:var(--text-primary-color, white) }
      input { min-width:220px; flex:1 }
      table { border-collapse:collapse; width:100%; background:var(--card-background-color) }
      th,td { text-align:left; padding:12px; border-bottom:1px solid var(--divider-color); overflow-wrap:anywhere }
      th:last-child,td:last-child { text-align:right; white-space:nowrap }
      .error { color:var(--error-color, #d32f2f); font-size:12px; margin-top:4px }
      .empty { padding:24px; text-align:center }
      @media(max-width:600px) { main { padding:12px } td,th { padding:8px } }
    `;
    root.append(style);
    const main = document.createElement("main");
    root.append(main);
    const header = document.createElement("header");
    const title = document.createElement("h1");
    title.textContent = "Photo Library";
    const reload = document.createElement("button");
    reload.textContent = "Refresh list";
    reload.addEventListener("click", () => this.load());
    header.append(title, reload);
    main.append(header);
    const status = document.createElement("p");
    status.className = "muted";
    const d = this._data;
    status.textContent = this._error ? "Unable to load library: " + this._error :
      `${d.photos.length} indexed photos · ${d.errors.length} metadata errors · ${d.unreadable || 0} unreadable · Scan: ${d.scan_status || "unknown"}` +
      (d.last_scan ? ` · Last scan: ${new Date(d.last_scan).toLocaleString()}` : "");
    main.append(status);
    if (d.scan_error) {
      const error = document.createElement("p");
      error.className = "error";
      error.textContent = d.scan_error;
      main.append(error);
    }
    const controls = document.createElement("div");
    controls.className = "controls";
    const filters = [{key:"all",label:"All"},...Array.from({length:6},(_,i)=>({key:String(i),label:`${i} ★`})) ,{key:"errors",label:"Errors"}];
    for (const filter of filters) {
      const button = document.createElement("button");
      button.textContent = filter.label;
      button.setAttribute("aria-pressed", String(this._filter === filter.key));
      button.addEventListener("click", () => { this._filter = filter.key; this.render(); });
      controls.append(button);
    }
    const input = document.createElement("input");
    input.placeholder = "Search filenames or error messages";
    input.setAttribute("aria-label", "Search photo library");
    input.value = this._search;
    input.addEventListener("input", event => {
      const start = event.target.selectionStart;
      this._search = event.target.value;
      this.render();
      const next = this.shadowRoot.querySelector("input");
      next.focus();
      next.setSelectionRange(start, start);
    });
    controls.append(input);
    main.append(controls);
    const errors = new Map();
    for (const item of d.errors) {
      if (!errors.has(item.path)) errors.set(item.path, []);
      errors.get(item.path).push(item.reason);
    }
    const photos = d.photos.map(p => ({...p, reasons:errors.get(p.path)||[]}));
    if (this._filter === "errors") {
      for (const [path,reasons] of errors) {
        if (!photos.some(p => p.path === path)) photos.push({path,rating:null,reasons});
      }
    }
    const rows = photos.filter(p => {
      if (this._filter === "errors" && !p.reasons.length) return false;
      if (this._filter !== "all" && this._filter !== "errors" && String(p.rating) !== this._filter) return false;
      return (p.path + " " + p.reasons.join(" ")).toLowerCase().includes(this._search.toLowerCase());
    });
    const count = document.createElement("p");
    count.className = "muted";
    count.textContent = `${rows.length} matching files`;
    main.append(count);
    const table = document.createElement("table");
    const thead = document.createElement("thead");
    const headrow = document.createElement("tr");
    for (const text of ["Filename / path", "Rating"]) {
      const th = document.createElement("th"); th.textContent = text; headrow.append(th);
    }
    thead.append(headrow); table.append(thead);
    const tbody = document.createElement("tbody");
    for (const photo of rows) {
      const tr = document.createElement("tr");
      const filename = document.createElement("td");
      filename.textContent = photo.path;
      for (const reason of photo.reasons) {
        const detail = document.createElement("div");
        detail.className = "error"; detail.textContent = reason;
        filename.append(detail);
      }
      const rating = document.createElement("td");
      rating.textContent = photo.rating === null ? "—" : `${photo.rating} ★`;
      tr.append(filename,rating); tbody.append(tr);
    }
    table.append(tbody); main.append(table);
    if (!rows.length) {
      const empty = document.createElement("p");
      empty.className = "empty"; empty.textContent = "No matching photographs.";
      main.append(empty);
    }
  }
}
customElements.define("wallpanel-photo-library", WallpanelPhotoLibrary);
