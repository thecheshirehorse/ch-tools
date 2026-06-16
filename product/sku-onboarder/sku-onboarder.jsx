import { useState, useEffect, useCallback, useRef } from "react";
import * as XLSX from "xlsx";

// ── Storage helpers ────────────────────────────────────────────────────────
async function loadRules() {
  try {
    const res = await window.storage.get("rph-rules");
    return res ? JSON.parse(res.value) : { items: {}, classes: {}, vendors: {} };
  } catch { return { items: {}, classes: {}, vendors: {} }; }
}
async function saveRules(rules) {
  try { await window.storage.set("rph-rules", JSON.stringify(rules)); } catch (e) { console.error("Save failed:", e); }
}
async function loadHistory() {
  try {
    const res = await window.storage.get("rph-history");
    return res ? JSON.parse(res.value) : [];
  } catch { return []; }
}
async function saveHistory(history) {
  try { await window.storage.set("rph-history", JSON.stringify(history.slice(-20))); } catch (e) { console.error(e); }
}

// ── Cascade logic ──────────────────────────────────────────────────────────
function classifyCascade(rows, rules) {
  const approved = [], dropped = [], review = [];
  const dropReasons = {};
  rows.forEach(r => {
    const sku = (r["Item Number"] || r["SKU"] || "").toString().trim();
    const vendor = (r["Vendor Name"] || r["Vendor"] || "").toString().trim();
    const retail = parseFloat(r["Retail Price"] || r["Price"] || 0);
    const closeout = (r["Store Closeout?"] || r["Closeout"] || "").toString().trim().toUpperCase();
    const dept = (r["Department Code"] || r["Dept"] || r["Department"] || "").toString().trim().toUpperCase();
    const cls = (r["Class Code"] || r["Class"] || "").toString().trim().toUpperCase();
    const desc = (r["Description"] || r["Item Description"] || "").toString().trim();
    const qoh = parseInt(r["Quantity on Hand"] || r["QOH"] || 0);
    const qoo = parseInt(r["Quantity on Order"] || r["QOO"] || 0);
    const upc = (r["UPC"] || "").toString().trim();
    const mfg = (r["MFG Part"] || r["Mfg Part Number"] || "").toString().trim();
    const wt = parseFloat(r["Weight"] || 0);
    const list = parseFloat(r["List Price"] || 0);
    const item = { sku, vendor, retail, closeout, dept, cls, desc, qoh, qoo, upc, mfg, weight: wt, list, selected: false, _raw: r };

    // Check item-level overrides first
    if (rules.items[sku]) {
      const rule = rules.items[sku];
      if (rule.action === "approve") { item.selected = true; item._ruleSource = "Item rule: always approve"; approved.push(item); return; }
      if (rule.action === "drop") { dropReasons[sku] = "Item rule: always drop"; dropped.push(item); return; }
      if (rule.action === "review") { item._ruleSource = "Item rule: always review"; review.push(item); return; }
    }

    // Auto-drop checks
    if (!vendor) { dropReasons[sku] = "Blank vendor"; dropped.push(item); return; }
    if (retail <= 0) { dropReasons[sku] = "$0 retail"; dropped.push(item); return; }
    if (closeout === "Y") { dropReasons[sku] = "Closeout"; dropped.push(item); return; }
    if (sku.startsWith("ZZ")) { dropReasons[sku] = "ZZ special order"; dropped.push(item); return; }
    if (sku.startsWith("DP") || sku.startsWith("IS")) { dropReasons[sku] = "Display/promo item"; dropped.push(item); return; }
    if (dept === "H1" || dept === "H2") { dropReasons[sku] = `Coupon (dept ${dept})`; dropped.push(item); return; }
    if (dept === "80") { dropReasons[sku] = "Delivery (dept 80)"; dropped.push(item); return; }

    // Check vendor rules
    if (rules.vendors[vendor]) {
      const vr = rules.vendors[vendor];
      if (vr.action === "approve") { item.selected = true; item._ruleSource = `Vendor rule: ${vendor}`; approved.push(item); return; }
      if (vr.action === "drop") { dropReasons[sku] = `Vendor rule: ${vendor}`; dropped.push(item); return; }
      if (vr.action === "review") { item._ruleSource = `Vendor rule: ${vendor}`; review.push(item); return; }
    }

    // Check class rules (saved)
    if (cls && rules.classes[cls]) {
      const cr = rules.classes[cls];
      if (cr.action === "approve") { item.selected = true; item._ruleSource = `Class rule: ${cls}`; approved.push(item); return; }
      if (cr.action === "drop") { dropReasons[sku] = `Class rule: ${cls}`; dropped.push(item); return; }
      if (cr.action === "review") { item._ruleSource = `Class rule: ${cls}`; review.push(item); return; }
    }

    // Built-in class auto-approve
    const autoClasses = ["C03","C07","C12","C20","C50","C55","C58"];
    if (cls && autoClasses.includes(cls)) { item.selected = true; item._ruleSource = `Auto-approve: class ${cls}`; approved.push(item); return; }

    review.push(item);
  });
  return { approved, dropped, review, dropReasons };
}

// ── Styles ─────────────────────────────────────────────────────────────────
const STYLES = `
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg: #0f1117; --surface: #1a1d27; --surface2: #242836; --surface3: #2e3348;
    --border: #353a4f; --text: #e8eaf0; --text2: #9ca3b8; --text3: #6b7394;
    --accent: #6c8cff; --accent2: #4a6aee; --green: #4ade80; --green-bg: #0f2a1a;
    --red: #f87171; --red-bg: #2a0f0f; --amber: #fbbf24; --amber-bg: #2a220f;
    --blue-bg: #0f1a2a;
  }
  body { font-family: 'DM Sans', sans-serif; background: var(--bg); color: var(--text); }
  .app { max-width: 1200px; margin: 0 auto; padding: 20px; min-height: 100vh; }
  .app-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--border); }
  .app-title { font-size: 20px; font-weight: 700; color: var(--text); letter-spacing: -0.3px; }
  .app-title span { color: var(--accent); }
  .header-actions { display: flex; gap: 8px; }
  .btn { font-family: inherit; font-size: 13px; font-weight: 600; padding: 8px 16px; border-radius: 8px; border: 1px solid var(--border); background: var(--surface2); color: var(--text); cursor: pointer; transition: all 0.15s; display: inline-flex; align-items: center; gap: 6px; }
  .btn:hover { background: var(--surface3); border-color: var(--accent); }
  .btn-primary { background: var(--accent); border-color: var(--accent); color: #fff; }
  .btn-primary:hover { background: var(--accent2); }
  .btn-sm { padding: 5px 10px; font-size: 12px; }
  .btn-danger { border-color: var(--red); color: var(--red); }
  .btn-danger:hover { background: var(--red-bg); }

  .stepper { display: flex; gap: 4px; margin-bottom: 24px; }
  .step-item { flex: 1; }
  .step-bar { height: 3px; border-radius: 2px; background: var(--surface3); margin-bottom: 6px; transition: background 0.3s; }
  .step-item.active .step-bar { background: var(--accent); }
  .step-item.done .step-bar { background: var(--green); }
  .step-label { font-size: 11px; color: var(--text3); font-weight: 500; cursor: default; }
  .step-item.active .step-label { color: var(--accent); }
  .step-item.done .step-label { color: var(--green); cursor: pointer; }

  .card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin-bottom: 16px; }
  .card-title { font-size: 15px; font-weight: 600; margin-bottom: 12px; }

  .drop-zone { border: 2px dashed var(--border); border-radius: 12px; padding: 48px; text-align: center; cursor: pointer; transition: all 0.2s; background: var(--surface); }
  .drop-zone:hover, .drop-zone.drag-over { border-color: var(--accent); background: var(--blue-bg); }
  .drop-zone h3 { font-size: 16px; margin-bottom: 8px; }
  .drop-zone p { color: var(--text2); font-size: 13px; }

  .stat-row { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
  .stat-box { flex: 1; min-width: 120px; padding: 12px 16px; border-radius: 10px; border: 1px solid var(--border); background: var(--surface2); }
  .stat-val { font-size: 22px; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
  .stat-label { font-size: 11px; color: var(--text2); margin-top: 2px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px; }
  .stat-box.green { border-color: #2d6b45; background: var(--green-bg); }
  .stat-box.green .stat-val { color: var(--green); }
  .stat-box.red { border-color: #6b2d2d; background: var(--red-bg); }
  .stat-box.red .stat-val { color: var(--red); }
  .stat-box.amber { border-color: #6b5a2d; background: var(--amber-bg); }
  .stat-box.amber .stat-val { color: var(--amber); }

  .section-toggle { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; background: var(--surface2); border-radius: 8px; cursor: pointer; margin-bottom: 8px; border: 1px solid var(--border); }
  .section-toggle:hover { border-color: var(--accent); }
  .section-toggle .label { font-size: 13px; font-weight: 600; }
  .section-toggle .count { font-size: 12px; color: var(--text2); font-family: 'JetBrains Mono', monospace; }

  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { text-align: left; padding: 8px 10px; font-size: 11px; font-weight: 600; color: var(--text3); text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid var(--border); position: sticky; top: 0; background: var(--surface); z-index: 1; }
  td { padding: 7px 10px; border-bottom: 1px solid var(--border); vertical-align: middle; }
  tr:hover td { background: var(--surface2); }
  .mono { font-family: 'JetBrains Mono', monospace; font-size: 12px; }
  .text-muted { color: var(--text2); }
  .text-green { color: var(--green); }
  .text-red { color: var(--red); }
  .text-amber { color: var(--amber); }

  .chip { display: inline-flex; align-items: center; gap: 4px; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; border: 1px solid; }
  .chip-green { color: var(--green); border-color: #2d6b45; background: var(--green-bg); }
  .chip-red { color: var(--red); border-color: #6b2d2d; background: var(--red-bg); }
  .chip-amber { color: var(--amber); border-color: #6b5a2d; background: var(--amber-bg); }
  .chip-blue { color: var(--accent); border-color: #2d456b; background: var(--blue-bg); }

  .filter-bar { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; align-items: center; }
  .filter-input { font-family: inherit; font-size: 13px; padding: 7px 12px; border-radius: 8px; border: 1px solid var(--border); background: var(--surface2); color: var(--text); flex: 1; min-width: 180px; outline: none; }
  .filter-input:focus { border-color: var(--accent); }
  select.filter-input { flex: 0 0 auto; min-width: 160px; cursor: pointer; }

  .table-wrap { max-height: 420px; overflow-y: auto; border: 1px solid var(--border); border-radius: 8px; }
  .table-wrap::-webkit-scrollbar { width: 6px; }
  .table-wrap::-webkit-scrollbar-track { background: var(--surface); }
  .table-wrap::-webkit-scrollbar-thumb { background: var(--surface3); border-radius: 3px; }

  .action-bar { display: flex; justify-content: space-between; align-items: center; margin-top: 16px; }

  .modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.6); display: flex; align-items: center; justify-content: center; z-index: 100; }
  .modal { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 24px; width: 420px; max-width: 95vw; max-height: 80vh; overflow-y: auto; }
  .modal h3 { font-size: 16px; margin-bottom: 16px; }
  .modal-actions { display: flex; gap: 8px; margin-top: 16px; justify-content: flex-end; }

  .rule-row { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; border: 1px solid var(--border); border-radius: 8px; margin-bottom: 6px; background: var(--surface2); }
  .rule-row .rule-info { font-size: 13px; }
  .rule-row .rule-type { font-size: 11px; color: var(--text3); text-transform: uppercase; font-weight: 600; margin-right: 8px; }

  .radio-group { display: flex; flex-direction: column; gap: 8px; margin: 12px 0; }
  .radio-opt { display: flex; align-items: center; gap: 10px; padding: 10px 14px; border-radius: 8px; border: 1px solid var(--border); cursor: pointer; transition: all 0.15s; }
  .radio-opt:hover { border-color: var(--accent); background: var(--blue-bg); }
  .radio-opt.selected { border-color: var(--accent); background: var(--blue-bg); }
  .radio-opt input { accent-color: var(--accent); }
  .radio-label { font-size: 13px; font-weight: 500; }
  .radio-desc { font-size: 11px; color: var(--text2); }

  .vendor-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
  .vendor-chip { padding: 5px 12px; border-radius: 20px; font-size: 12px; font-weight: 500; border: 1px solid var(--border); background: var(--surface2); cursor: pointer; transition: all 0.15s; }
  .vendor-chip:hover { border-color: var(--accent); background: var(--blue-bg); }
  .vendor-chip .vc-count { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--text3); margin-left: 4px; }

  .history-item { font-size: 12px; color: var(--text2); padding: 4px 0; border-bottom: 1px solid var(--border); }
  .empty-state { text-align: center; padding: 32px; color: var(--text3); }
  .empty-state p { margin-top: 8px; font-size: 13px; }

  .loading-bar { height: 3px; background: var(--surface3); border-radius: 2px; overflow: hidden; margin-bottom: 12px; }
  .loading-bar-inner { height: 100%; width: 30%; background: var(--accent); border-radius: 2px; animation: loadSlide 1.2s ease-in-out infinite; }
  @keyframes loadSlide { 0% { transform: translateX(-100%); } 100% { transform: translateX(400%); } }

  input[type="checkbox"] { accent-color: var(--accent); width: 15px; height: 15px; cursor: pointer; }
  .cb-cell { width: 36px; text-align: center; }
`;

// ── Upload Step ────────────────────────────────────────────────────────────
function UploadStep({ onData, rulesLoaded, rulesSummary }) {
  const [drag, setDrag] = useState(false);
  const fileRef = useRef();
  const handleFile = (file) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      const wb = XLSX.read(e.target.result, { type: "array" });
      const ws = wb.Sheets[wb.SheetNames[0]];
      const rows = XLSX.utils.sheet_to_json(ws);
      onData(rows);
    };
    reader.readAsArrayBuffer(file);
  };
  return (
    <div>
      <div className="card">
        <div className="card-title">Upload RPH Export</div>
        {rulesSummary && (
          <div style={{ marginBottom: 16, padding: "10px 14px", borderRadius: 8, background: "var(--blue-bg)", border: "1px solid #2d456b", fontSize: 13 }}>
            <span style={{ color: "var(--accent)", fontWeight: 600 }}>Rules loaded:</span>{" "}
            <span className="text-muted">{rulesSummary}</span>
          </div>
        )}
        <div
          className={`drop-zone ${drag ? "drag-over" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); handleFile(e.dataTransfer.files[0]); }}
          onClick={() => fileRef.current?.click()}
        >
          <h3>Drop your RPH v2 file here</h3>
          <p>.xls or .xlsx — Thursday export with dept/class columns</p>
          <input ref={fileRef} type="file" accept=".xls,.xlsx,.csv" hidden onChange={(e) => handleFile(e.target.files[0])} />
        </div>
      </div>
    </div>
  );
}

// ── Cascade Step ───────────────────────────────────────────────────────────
function CascadeStep({ products, drops, dropReasons, stats, onNext, onRescue, rules, onSaveRule }) {
  const [showDrops, setShowDrops] = useState(false);
  const [showApproved, setShowApproved] = useState(false);
  const [rescueModal, setRescueModal] = useState(null);
  const [rescueAction, setRescueAction] = useState("review");

  const handleRescue = (item) => {
    setRescueModal(item);
    setRescueAction("review");
  };
  const confirmRescue = () => {
    if (!rescueModal) return;
    onRescue(rescueModal.sku, rescueAction);
    setRescueModal(null);
  };

  return (
    <div>
      <div className="stat-row">
        <div className="stat-box green"><div className="stat-val">{stats.approved}</div><div className="stat-label">Auto-Approved</div></div>
        <div className="stat-box red"><div className="stat-val">{stats.dropped}</div><div className="stat-label">Auto-Dropped</div></div>
        <div className="stat-box amber"><div className="stat-val">{stats.review}</div><div className="stat-label">Needs Review</div></div>
        <div className="stat-box"><div className="stat-val">{stats.total}</div><div className="stat-label">Total Items</div></div>
      </div>

      <div className="section-toggle" onClick={() => setShowApproved(!showApproved)}>
        <span className="label"><span className="chip chip-green">✓</span> Auto-Approved Items</span>
        <span className="count">{stats.approved} items {showApproved ? "▲" : "▼"}</span>
      </div>
      {showApproved && (
        <div className="card" style={{ maxHeight: 300, overflowY: "auto" }}>
          <table><thead><tr><th>SKU</th><th>Description</th><th>Vendor</th><th>Class</th><th>Rule</th></tr></thead>
            <tbody>{products.filter(p => p.selected).map(p => (
              <tr key={p.sku}><td className="mono">{p.sku}</td><td>{p.desc}</td><td className="text-muted">{p.vendor}</td><td className="mono">{p.cls}</td><td><span className="chip chip-green">{p._ruleSource || "Auto"}</span></td></tr>
            ))}</tbody>
          </table>
        </div>
      )}

      <div className="section-toggle" onClick={() => setShowDrops(!showDrops)}>
        <span className="label"><span className="chip chip-red">✕</span> Dropped Items</span>
        <span className="count">{stats.dropped} items {showDrops ? "▲" : "▼"}</span>
      </div>
      {showDrops && (
        <div className="card" style={{ maxHeight: 300, overflowY: "auto" }}>
          <table><thead><tr><th>SKU</th><th>Description</th><th>Vendor</th><th>Reason</th><th></th></tr></thead>
            <tbody>{drops.map(d => (
              <tr key={d.sku}><td className="mono">{d.sku}</td><td>{d.desc}</td><td className="text-muted">{d.vendor}</td>
                <td><span className="chip chip-red">{dropReasons[d.sku]}</span></td>
                <td><button className="btn btn-sm" onClick={() => handleRescue(d)}>Rescue</button></td></tr>
            ))}</tbody>
          </table>
        </div>
      )}

      <div className="action-bar">
        <div></div>
        <button className="btn btn-primary" onClick={onNext}>Review {stats.review} Items →</button>
      </div>

      {rescueModal && (
        <div className="modal-overlay" onClick={() => setRescueModal(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3>Rescue: {rescueModal.sku}</h3>
            <p style={{ fontSize: 13, color: "var(--text2)", marginBottom: 8 }}>{rescueModal.desc}</p>
            <p style={{ fontSize: 12, color: "var(--text3)" }}>Dropped because: {dropReasons[rescueModal.sku]}</p>
            <div className="radio-group">
              <label className={`radio-opt ${rescueAction === "review" ? "selected" : ""}`} onClick={() => setRescueAction("review")}>
                <input type="radio" checked={rescueAction === "review"} readOnly />
                <div><div className="radio-label">Move to Review (this time only)</div><div className="radio-desc">You'll decide in the review step. No rule saved.</div></div>
              </label>
              <label className={`radio-opt ${rescueAction === "review-always" ? "selected" : ""}`} onClick={() => setRescueAction("review-always")}>
                <input type="radio" checked={rescueAction === "review-always"} readOnly />
                <div><div className="radio-label">Always send to Review</div><div className="radio-desc">Saves a rule: this item skips auto-drop and goes to review every week.</div></div>
              </label>
              <label className={`radio-opt ${rescueAction === "approve" ? "selected" : ""}`} onClick={() => setRescueAction("approve")}>
                <input type="radio" checked={rescueAction === "approve"} readOnly />
                <div><div className="radio-label">Approve (this time only)</div><div className="radio-desc">Auto-approve it this run. No rule saved.</div></div>
              </label>
              <label className={`radio-opt ${rescueAction === "approve-always" ? "selected" : ""}`} onClick={() => setRescueAction("approve-always")}>
                <input type="radio" checked={rescueAction === "approve-always"} readOnly />
                <div><div className="radio-label">Always Approve</div><div className="radio-desc">Saves a rule: this item is always auto-approved going forward.</div></div>
              </label>
            </div>
            <div className="modal-actions">
              <button className="btn" onClick={() => setRescueModal(null)}>Cancel</button>
              <button className="btn btn-primary" onClick={confirmRescue}>Confirm</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Review Step ────────────────────────────────────────────────────────────
function ReviewStep({ products, onUpdate, onNext, onBack, stats, onSaveRule }) {
  const [search, setSearch] = useState("");
  const [vendorFilter, setVendorFilter] = useState("all");
  const [vendorModal, setVendorModal] = useState(null);
  const [vendorAction, setVendorAction] = useState("select");

  const reviewItems = products.filter(p => !p.selected && !p._dropped);
  const vendors = {};
  reviewItems.forEach(p => { vendors[p.vendor] = (vendors[p.vendor] || 0) + 1; });
  const sortedVendors = Object.entries(vendors).sort((a, b) => b[1] - a[1]);

  const filtered = reviewItems.filter(p => {
    if (vendorFilter !== "all" && p.vendor !== vendorFilter) return false;
    if (search && !p.sku.toLowerCase().includes(search.toLowerCase()) && !p.desc.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const toggleItem = (sku) => {
    onUpdate(products.map(p => p.sku === sku ? { ...p, selected: !p.selected } : p));
  };
  const selectShown = () => {
    const skus = new Set(filtered.map(p => p.sku));
    onUpdate(products.map(p => skus.has(p.sku) ? { ...p, selected: true } : p));
  };
  const deselectShown = () => {
    const skus = new Set(filtered.map(p => p.sku));
    onUpdate(products.map(p => skus.has(p.sku) ? { ...p, selected: false } : p));
  };

  const handleVendorAction = () => {
    if (!vendorModal) return;
    const vName = vendorModal;
    if (vendorAction === "select" || vendorAction === "select-save") {
      onUpdate(products.map(p => p.vendor === vName && !p._dropped ? { ...p, selected: true } : p));
      if (vendorAction === "select-save") onSaveRule("vendor", vName, "approve");
    } else if (vendorAction === "skip" || vendorAction === "skip-save") {
      onUpdate(products.map(p => p.vendor === vName && !p._dropped ? { ...p, _dropped: true } : p));
      if (vendorAction === "skip-save") onSaveRule("vendor", vName, "drop");
    }
    setVendorModal(null);
  };

  const selectedCount = products.filter(p => p.selected).length;

  return (
    <div>
      <div className="card-title" style={{ marginBottom: 12 }}>Review Items — {selectedCount} selected of {stats.total} total</div>

      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 12, color: "var(--text3)", marginBottom: 6, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.5px" }}>Quick Actions by Vendor</div>
        <div className="vendor-chips">
          {sortedVendors.slice(0, 20).map(([v, c]) => (
            <div key={v} className="vendor-chip" onClick={() => { setVendorModal(v); setVendorAction("select"); }}>
              {v} <span className="vc-count">{c}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="filter-bar">
        <input className="filter-input" placeholder="Search SKU or description..." value={search} onChange={e => setSearch(e.target.value)} />
        <select className="filter-input" value={vendorFilter} onChange={e => setVendorFilter(e.target.value)}>
          <option value="all">All Vendors ({reviewItems.length})</option>
          {sortedVendors.map(([v, c]) => <option key={v} value={v}>{v} ({c})</option>)}
        </select>
        <button className="btn btn-sm" onClick={selectShown}>Select Shown</button>
        <button className="btn btn-sm" onClick={deselectShown}>Deselect Shown</button>
      </div>

      <div className="table-wrap">
        <table>
          <thead><tr><th className="cb-cell"><input type="checkbox" onChange={e => e.target.checked ? selectShown() : deselectShown()} /></th><th>SKU</th><th>Description</th><th>Vendor</th><th>Dept</th><th>Class</th><th>QOH</th><th>Retail</th></tr></thead>
          <tbody>
            {filtered.map(p => (
              <tr key={p.sku}>
                <td className="cb-cell"><input type="checkbox" checked={p.selected || false} onChange={() => toggleItem(p.sku)} /></td>
                <td className="mono">{p.sku}</td><td>{p.desc}</td><td className="text-muted">{p.vendor}</td>
                <td className="mono">{p.dept}</td><td className="mono">{p.cls}</td>
                <td className="mono">{p.qoh}</td><td className="mono">${p.retail.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && <div className="empty-state"><p>No items match your filters</p></div>}
      </div>

      <div className="action-bar">
        <button className="btn" onClick={onBack}>← Cascade</button>
        <button className="btn btn-primary" onClick={onNext}>Group Variations →</button>
      </div>

      {vendorModal && (
        <div className="modal-overlay" onClick={() => setVendorModal(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3>{vendorModal}</h3>
            <p style={{ fontSize: 13, color: "var(--text2)" }}>{vendors[vendorModal]} items in review</p>
            <div className="radio-group">
              <label className={`radio-opt ${vendorAction === "select" ? "selected" : ""}`} onClick={() => setVendorAction("select")}>
                <input type="radio" checked={vendorAction === "select"} readOnly />
                <div><div className="radio-label">Select all (this time)</div></div>
              </label>
              <label className={`radio-opt ${vendorAction === "select-save" ? "selected" : ""}`} onClick={() => setVendorAction("select-save")}>
                <input type="radio" checked={vendorAction === "select-save"} readOnly />
                <div><div className="radio-label">Select all + save rule</div><div className="radio-desc">Always auto-approve this vendor going forward</div></div>
              </label>
              <label className={`radio-opt ${vendorAction === "skip" ? "selected" : ""}`} onClick={() => setVendorAction("skip")}>
                <input type="radio" checked={vendorAction === "skip"} readOnly />
                <div><div className="radio-label">Skip all (this time)</div></div>
              </label>
              <label className={`radio-opt ${vendorAction === "skip-save" ? "selected" : ""}`} onClick={() => setVendorAction("skip-save")}>
                <input type="radio" checked={vendorAction === "skip-save"} readOnly />
                <div><div className="radio-label">Skip all + save rule</div><div className="radio-desc">Always auto-drop this vendor going forward</div></div>
              </label>
            </div>
            <div className="modal-actions">
              <button className="btn" onClick={() => setVendorModal(null)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleVendorAction}>Apply</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Group Step ─────────────────────────────────────────────────────────────
function GroupStep({ products, onUpdate, groups, setGroups, onNext, onBack }) {
  const selected = products.filter(p => p.selected);
  const ungrouped = selected.filter(p => !groups.some(g => g.skus.includes(p.sku)));
  const [multiSelect, setMultiSelect] = useState([]);

  // Auto-detect potential groups by shared prefix + same vendor
  const suggestions = [];
  const seen = new Set();
  ungrouped.forEach(p => {
    if (seen.has(p.sku) || p.sku.length < 6) return;
    const prefix = p.sku.slice(0, Math.max(4, p.sku.length - 3));
    const matches = ungrouped.filter(q => q.sku.startsWith(prefix) && q.vendor === p.vendor && q.sku !== p.sku);
    if (matches.length >= 1) {
      const all = [p, ...matches];
      all.forEach(a => seen.add(a.sku));
      suggestions.push({ prefix, vendor: p.vendor, items: all });
    }
  });

  const createGroup = (skus, name) => {
    setGroups([...groups, { id: Date.now(), name: name || `Group ${groups.length + 1}`, skus, variationType: "color" }]);
    setMultiSelect([]);
  };
  const removeGroup = (id) => setGroups(groups.filter(g => g.id !== id));
  const toggleMulti = (sku) => setMultiSelect(prev => prev.includes(sku) ? prev.filter(s => s !== sku) : [...prev, sku]);

  return (
    <div>
      <div className="card-title" style={{ marginBottom: 12 }}>Group Variations — {selected.length} products, {groups.length} groups</div>

      {suggestions.length > 0 && (
        <div className="card">
          <div style={{ fontSize: 12, color: "var(--text3)", marginBottom: 8, fontWeight: 600, textTransform: "uppercase" }}>Suggested Groups</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {suggestions.slice(0, 15).map(s => (
              <button key={s.prefix} className="btn btn-sm" onClick={() => createGroup(s.items.map(i => i.sku), `${s.vendor} ${s.prefix}*`)}>
                {s.prefix}* <span style={{ color: "var(--text3)" }}>({s.items.length})</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {groups.length > 0 && (
        <div className="card">
          <div style={{ fontSize: 12, color: "var(--text3)", marginBottom: 8, fontWeight: 600, textTransform: "uppercase" }}>Created Groups</div>
          {groups.map(g => (
            <div key={g.id} className="rule-row">
              <div className="rule-info">
                <span style={{ fontWeight: 600 }}>{g.name}</span>
                <span className="text-muted" style={{ marginLeft: 8, fontSize: 12 }}>{g.skus.length} variants</span>
              </div>
              <button className="btn btn-sm btn-danger" onClick={() => removeGroup(g.id)}>Remove</button>
            </div>
          ))}
        </div>
      )}

      <div className="card">
        <div style={{ fontSize: 12, color: "var(--text3)", marginBottom: 8, fontWeight: 600, textTransform: "uppercase" }}>
          Ungrouped Items ({ungrouped.length})
          {multiSelect.length >= 2 && (
            <button className="btn btn-sm btn-primary" style={{ marginLeft: 12 }} onClick={() => createGroup(multiSelect)}>
              Group {multiSelect.length} Selected
            </button>
          )}
        </div>
        <div className="table-wrap" style={{ maxHeight: 320 }}>
          <table>
            <thead><tr><th className="cb-cell"></th><th>SKU</th><th>Description</th><th>Vendor</th></tr></thead>
            <tbody>
              {ungrouped.map(p => (
                <tr key={p.sku} style={{ background: multiSelect.includes(p.sku) ? "var(--blue-bg)" : undefined }}>
                  <td className="cb-cell"><input type="checkbox" checked={multiSelect.includes(p.sku)} onChange={() => toggleMulti(p.sku)} /></td>
                  <td className="mono">{p.sku}</td><td>{p.desc}</td><td className="text-muted">{p.vendor}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="action-bar">
        <button className="btn" onClick={onBack}>← Review</button>
        <button className="btn btn-primary" onClick={onNext}>Edit & Categorize →</button>
      </div>
    </div>
  );
}

// ── Edit Step ──────────────────────────────────────────────────────────────
function EditStep({ products, onUpdate, groups, setGroups, onNext, onBack }) {
  const selected = products.filter(p => p.selected);
  const [editSku, setEditSku] = useState(null);

  const updateProduct = (sku, field, value) => {
    onUpdate(products.map(p => p.sku === sku ? { ...p, [field]: value } : p));
  };

  return (
    <div>
      <div className="card-title" style={{ marginBottom: 12 }}>Edit & Categorize — {selected.length} products</div>
      <div className="table-wrap" style={{ maxHeight: 500 }}>
        <table>
          <thead><tr><th>SKU</th><th>Name</th><th>Category</th><th>Retail</th><th>Group</th></tr></thead>
          <tbody>
            {selected.map(p => {
              const group = groups.find(g => g.skus.includes(p.sku));
              return (
                <tr key={p.sku}>
                  <td className="mono">{p.sku}</td>
                  <td><input className="filter-input" style={{ width: "100%", padding: "4px 8px", minWidth: 0 }} value={p.displayName || p.desc} onChange={e => updateProduct(p.sku, "displayName", e.target.value)} /></td>
                  <td><input className="filter-input" style={{ width: 140, padding: "4px 8px", minWidth: 0 }} value={p.category || ""} onChange={e => updateProduct(p.sku, "category", e.target.value)} placeholder="Category ID" /></td>
                  <td className="mono">${p.retail.toFixed(2)}</td>
                  <td>{group ? <span className="chip chip-blue">{group.name}</span> : <span className="text-muted">—</span>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="action-bar">
        <button className="btn" onClick={onBack}>← Group</button>
        <button className="btn btn-primary" onClick={onNext}>Export XML →</button>
      </div>
    </div>
  );
}

// ── Export Step ─────────────────────────────────────────────────────────────
function ExportStep({ products, groups, onBack }) {
  const selected = products.filter(p => p.selected);
  const NS = "http://www.demandware.com/xml/impex/catalog/2006-10-31";

  const generateCatalogXML = () => {
    const lines = [`<?xml version="1.0" encoding="UTF-8"?>`, `<catalog xmlns="${NS}" catalog-id="master-cheshirehorse">`];
    const grouped = new Set(groups.flatMap(g => g.skus));

    // Standalone products
    selected.filter(p => !grouped.has(p.sku)).forEach(p => {
      lines.push(`  <product product-id="${esc(p.sku)}">`);
      lines.push(`    <display-name xml:lang="x-default">${esc(p.displayName || p.desc)}</display-name>`);
      if (p.upc) lines.push(`    <upc>${esc(p.upc)}</upc>`);
      if (p.mfg) lines.push(`    <manufacturer-sku>${esc(p.mfg)}</manufacturer-sku>`);
      lines.push(`    <online-flag>true</online-flag>`);
      lines.push(`    <searchable-flag>true</searchable-flag>`);
      lines.push(`  </product>`);
    });

    // Grouped products (master + variants)
    groups.forEach(g => {
      const variants = selected.filter(p => g.skus.includes(p.sku));
      if (variants.length === 0) return;
      const masterId = g.name.replace(/[^a-zA-Z0-9_-]/g, "-");
      lines.push(`  <product product-id="${esc(masterId)}">`);
      lines.push(`    <display-name xml:lang="x-default">${esc(g.name)}</display-name>`);
      lines.push(`    <online-flag>true</online-flag>`);
      lines.push(`    <searchable-flag>true</searchable-flag>`);
      lines.push(`    <variations>`);
      lines.push(`      <attributes><shared-variation-attribute attribute-id="${g.variationType || "color"}" /></attributes>`);
      lines.push(`      <variants>`);
      variants.forEach(v => lines.push(`        <variant product-id="${esc(v.sku)}" />`));
      lines.push(`      </variants>`);
      lines.push(`    </variations>`);
      lines.push(`  </product>`);
      variants.forEach(v => {
        lines.push(`  <product product-id="${esc(v.sku)}">`);
        lines.push(`    <display-name xml:lang="x-default">${esc(v.displayName || v.desc)}</display-name>`);
        if (v.upc) lines.push(`    <upc>${esc(v.upc)}</upc>`);
        if (v.mfg) lines.push(`    <manufacturer-sku>${esc(v.mfg)}</manufacturer-sku>`);
        lines.push(`    <online-flag>true</online-flag>`);
        lines.push(`  </product>`);
      });
    });

    lines.push(`</catalog>`);
    return lines.join("\n");
  };

  const generatePricebookXML = () => {
    const lines = [`<?xml version="1.0" encoding="UTF-8"?>`,
      `<pricebooks xmlns="http://www.demandware.com/xml/impex/pricebook/2006-10-31">`,
      `  <pricebook>`,
      `    <header pricebook-id="usd-list-prices"><currency>USD</currency></header>`,
      `    <price-tables>`];
    selected.forEach(p => {
      lines.push(`      <price-table product-id="${esc(p.sku)}"><amount quantity="1">${p.retail.toFixed(2)}</amount></price-table>`);
    });
    lines.push(`    </price-tables>`, `  </pricebook>`, `</pricebooks>`);
    return lines.join("\n");
  };

  const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

  const download = (content, filename) => {
    const blob = new Blob([content], { type: "application/xml" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
  };

  return (
    <div>
      <div className="card">
        <div className="card-title">Export Ready</div>
        <div className="stat-row">
          <div className="stat-box green"><div className="stat-val">{selected.length}</div><div className="stat-label">Products</div></div>
          <div className="stat-box"><div className="stat-val">{groups.length}</div><div className="stat-label">Variation Groups</div></div>
          <div className="stat-box"><div className="stat-val">{selected.filter(p => !groups.some(g => g.skus.includes(p.sku))).length}</div><div className="stat-label">Standalone</div></div>
        </div>
        <div style={{ display: "flex", gap: 12, marginTop: 16 }}>
          <button className="btn btn-primary" onClick={() => download(generateCatalogXML(), "catalog-import.xml")}>Download Catalog XML</button>
          <button className="btn btn-primary" onClick={() => download(generatePricebookXML(), "pricebook-import.xml")}>Download Pricebook XML</button>
        </div>
      </div>
      <div className="action-bar">
        <button className="btn" onClick={onBack}>← Edit</button>
        <div></div>
      </div>
    </div>
  );
}

// ── Rules Panel ────────────────────────────────────────────────────────────
function RulesPanel({ rules, onDeleteRule, onClearAll }) {
  const itemRules = Object.entries(rules.items || {});
  const classRules = Object.entries(rules.classes || {});
  const vendorRules = Object.entries(rules.vendors || {});
  const total = itemRules.length + classRules.length + vendorRules.length;

  const actionChip = (action) => {
    if (action === "approve") return <span className="chip chip-green">Approve</span>;
    if (action === "drop") return <span className="chip chip-red">Drop</span>;
    return <span className="chip chip-amber">Review</span>;
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div className="card-title" style={{ margin: 0 }}>Saved Rules ({total})</div>
        {total > 0 && <button className="btn btn-sm btn-danger" onClick={onClearAll}>Clear All Rules</button>}
      </div>

      {total === 0 && <div className="empty-state"><p>No saved rules yet. Rules are created when you rescue items or use vendor quick-actions with "save rule".</p></div>}

      {itemRules.length > 0 && (
        <div className="card">
          <div style={{ fontSize: 12, color: "var(--text3)", marginBottom: 8, fontWeight: 600, textTransform: "uppercase" }}>Item Rules ({itemRules.length})</div>
          {itemRules.map(([sku, r]) => (
            <div key={sku} className="rule-row">
              <div className="rule-info"><span className="mono" style={{ marginRight: 10 }}>{sku}</span>{actionChip(r.action)}</div>
              <button className="btn btn-sm btn-danger" onClick={() => onDeleteRule("item", sku)}>×</button>
            </div>
          ))}
        </div>
      )}

      {classRules.length > 0 && (
        <div className="card">
          <div style={{ fontSize: 12, color: "var(--text3)", marginBottom: 8, fontWeight: 600, textTransform: "uppercase" }}>Class Rules ({classRules.length})</div>
          {classRules.map(([cls, r]) => (
            <div key={cls} className="rule-row">
              <div className="rule-info"><span className="mono" style={{ marginRight: 10 }}>{cls}</span>{actionChip(r.action)}</div>
              <button className="btn btn-sm btn-danger" onClick={() => onDeleteRule("class", cls)}>×</button>
            </div>
          ))}
        </div>
      )}

      {vendorRules.length > 0 && (
        <div className="card">
          <div style={{ fontSize: 12, color: "var(--text3)", marginBottom: 8, fontWeight: 600, textTransform: "uppercase" }}>Vendor Rules ({vendorRules.length})</div>
          {vendorRules.map(([v, r]) => (
            <div key={v} className="rule-row">
              <div className="rule-info"><span style={{ marginRight: 10 }}>{v}</span>{actionChip(r.action)}</div>
              <button className="btn btn-sm btn-danger" onClick={() => onDeleteRule("vendor", v)}>×</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Run History Panel ──────────────────────────────────────────────────────
function HistoryPanel({ history }) {
  if (!history.length) return <div className="empty-state"><p>No run history yet.</p></div>;
  return (
    <div className="card">
      <div className="card-title">Run History (last 20)</div>
      {history.map((h, i) => (
        <div key={i} className="history-item">
          <span style={{ fontWeight: 600 }}>{h.date}</span> — {h.total} items → {h.approved} approved, {h.dropped} dropped, {h.exported} exported
        </div>
      ))}
    </div>
  );
}

// ── Main App ───────────────────────────────────────────────────────────────
export default function App() {
  const [rules, setRules] = useState({ items: {}, classes: {}, vendors: {} });
  const [rulesLoaded, setRulesLoaded] = useState(false);
  const [history, setHistory] = useState([]);
  const [products, setProducts] = useState([]);
  const [drops, setDrops] = useState([]);
  const [dropReasons, setDropReasons] = useState({});
  const [stats, setStats] = useState({ total: 0, approved: 0, dropped: 0, review: 0 });
  const [groups, setGroups] = useState([]);
  const [step, setStep] = useState(0);
  const [showRules, setShowRules] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  // Load persisted rules and history on mount
  useEffect(() => {
    (async () => {
      const r = await loadRules();
      setRules(r);
      setRulesLoaded(true);
      const h = await loadHistory();
      setHistory(h);
    })();
  }, []);

  const rulesSummary = rulesLoaded ? (() => {
    const ic = Object.keys(rules.items).length;
    const cc = Object.keys(rules.classes).length;
    const vc = Object.keys(rules.vendors).length;
    const parts = [];
    if (ic) parts.push(`${ic} item${ic > 1 ? "s" : ""}`);
    if (cc) parts.push(`${cc} class${cc > 1 ? "es" : ""}`);
    if (vc) parts.push(`${vc} vendor${vc > 1 ? "s" : ""}`);
    return parts.length ? parts.join(", ") : null;
  })() : null;

  const handleUpload = (rows) => {
    const result = classifyCascade(rows, rules);
    setProducts([...result.approved, ...result.review]);
    setDrops(result.dropped);
    setDropReasons(result.dropReasons);
    setStats({ total: rows.length, approved: result.approved.length, dropped: result.dropped.length, review: result.review.length });
    setStep(1);
  };

  const handleSaveRule = useCallback(async (type, key, action) => {
    setRules(prev => {
      const next = { ...prev };
      if (type === "item") next.items = { ...next.items, [key]: { action } };
      else if (type === "class") next.classes = { ...next.classes, [key]: { action } };
      else if (type === "vendor") next.vendors = { ...next.vendors, [key]: { action } };
      saveRules(next);
      return next;
    });
  }, []);

  const handleDeleteRule = useCallback(async (type, key) => {
    setRules(prev => {
      const next = { ...prev };
      if (type === "item") { next.items = { ...next.items }; delete next.items[key]; }
      else if (type === "class") { next.classes = { ...next.classes }; delete next.classes[key]; }
      else if (type === "vendor") { next.vendors = { ...next.vendors }; delete next.vendors[key]; }
      saveRules(next);
      return next;
    });
  }, []);

  const handleClearAll = useCallback(async () => {
    const next = { items: {}, classes: {}, vendors: {} };
    setRules(next);
    await saveRules(next);
  }, []);

  const handleRescue = useCallback((sku, action) => {
    const item = drops.find(d => d.sku === sku);
    if (!item) return;

    if (action === "review" || action === "review-always") {
      item.selected = false;
      item._ruleSource = action === "review-always" ? "Item rule: always review" : undefined;
      setProducts(prev => [...prev, item]);
      setDrops(prev => prev.filter(d => d.sku !== sku));
      setStats(prev => ({ ...prev, dropped: prev.dropped - 1, review: prev.review + 1 }));
      if (action === "review-always") handleSaveRule("item", sku, "review");
    } else if (action === "approve" || action === "approve-always") {
      item.selected = true;
      item._ruleSource = action === "approve-always" ? "Item rule: always approve" : "Rescued";
      setProducts(prev => [...prev, item]);
      setDrops(prev => prev.filter(d => d.sku !== sku));
      setStats(prev => ({ ...prev, dropped: prev.dropped - 1, approved: prev.approved + 1 }));
      if (action === "approve-always") handleSaveRule("item", sku, "approve");
    }
  }, [drops, handleSaveRule]);

  const stepLabels = ["Upload", "Cascade", "Review", "Group", "Edit", "Export"];

  return (
    <div className="app">
      <style>{STYLES}</style>
      <div className="app-header">
        <div className="app-title">SKU <span>Onboarder</span></div>
        <div className="header-actions">
          <button className={`btn btn-sm ${showHistory ? "btn-primary" : ""}`} onClick={() => { setShowHistory(!showHistory); setShowRules(false); }}>History</button>
          <button className={`btn btn-sm ${showRules ? "btn-primary" : ""}`} onClick={() => { setShowRules(!showRules); setShowHistory(false); }}>
            Rules {rulesSummary && <span style={{ opacity: 0.7 }}>({Object.keys(rules.items).length + Object.keys(rules.classes).length + Object.keys(rules.vendors).length})</span>}
          </button>
        </div>
      </div>

      {!showRules && !showHistory && step > 0 && (
        <div className="stepper">
          {stepLabels.map((label, i) => (
            <div key={label} className={`step-item ${i === step ? "active" : i < step ? "done" : ""}`}>
              <div className="step-bar"></div>
              <div className="step-label" onClick={() => { if (i < step) setStep(i); }}>{label}</div>
            </div>
          ))}
        </div>
      )}

      <div className="app-content">
        {showRules ? (
          <RulesPanel rules={rules} onDeleteRule={handleDeleteRule} onClearAll={handleClearAll} />
        ) : showHistory ? (
          <HistoryPanel history={history} />
        ) : (
          <>
            {step === 0 && <UploadStep onData={handleUpload} rulesLoaded={rulesLoaded} rulesSummary={rulesSummary} />}
            {step === 1 && <CascadeStep products={products} drops={drops} dropReasons={dropReasons} stats={stats} onNext={() => setStep(2)} rules={rules} onSaveRule={handleSaveRule} onRescue={handleRescue} />}
            {step === 2 && <ReviewStep products={products} onUpdate={setProducts} onNext={() => setStep(3)} onBack={() => setStep(1)} stats={stats} onSaveRule={handleSaveRule} />}
            {step === 3 && <GroupStep products={products} onUpdate={setProducts} groups={groups} setGroups={setGroups} onNext={() => setStep(4)} onBack={() => setStep(2)} />}
            {step === 4 && <EditStep products={products} onUpdate={setProducts} groups={groups} setGroups={setGroups} onNext={() => setStep(5)} onBack={() => setStep(3)} />}
            {step === 5 && <ExportStep products={products} groups={groups} onBack={() => setStep(4)} />}
          </>
        )}
      </div>
    </div>
  );
}
