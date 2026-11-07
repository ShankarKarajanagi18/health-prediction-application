const API = "/api/patients";
const FIELDS = ["full_name", "date_of_birth", "email", "glucose", "haemoglobin", "cholesterol"];

const form = document.getElementById("record-form");
const formAlert = document.getElementById("form-alert");
const saveBtn = document.getElementById("save-btn");
const tableBody = document.getElementById("records-body");
const emptyState = document.getElementById("empty-state");
const emptyTitle = document.getElementById("empty-title");
const emptyMessage = document.getElementById("empty-message");
const loadingState = document.getElementById("loading-state");
const searchInput = document.getElementById("search-input");

const recordModal = new bootstrap.Modal(document.getElementById("record-modal"));
const deleteModal = new bootstrap.Modal(document.getElementById("delete-modal"));

let records = [];
let editingId = null;
let deletingId = null;
let sortKey = null;
let sortDirection = "asc";
const expandedRemarks = new Set();

async function request(url, options = {}) {
  const response = await fetch(url, { headers: { "Content-Type": "application/json" }, ...options });
  const data = response.status === 204 ? null : await response.json().catch(() => null);
  return { ok: response.ok, status: response.status, data };
}

function showToast(message, type = "success") {
  const el = document.createElement("div");
  el.className = `toast align-items-center text-bg-${type} border-0`;
  el.setAttribute("role", "alert");
  const row = document.createElement("div");
  row.className = "d-flex";
  const body = document.createElement("div");
  body.className = "toast-body";
  body.textContent = message;
  const close = document.createElement("button");
  close.type = "button";
  close.className = "btn-close btn-close-white me-2 m-auto";
  close.setAttribute("data-bs-dismiss", "toast");
  close.setAttribute("aria-label", "Close");
  row.append(body, close);
  el.appendChild(row);
  document.getElementById("toasts").appendChild(el);
  const toast = new bootstrap.Toast(el, { delay: type === "success" ? 3000 : 7000 });
  el.addEventListener("hidden.bs.toast", () => el.remove());
  toast.show();
}

function createButton(label, className, onClick, ariaLabel = label) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = `btn btn-sm ${className}`;
  btn.textContent = label;
  btn.setAttribute("aria-label", ariaLabel);
  btn.addEventListener("click", onClick);
  return btn;
}

function initials(name) {
  return name.trim().split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
}

function classifyValue(type, value) {
  if (type === "glucose") return value < 70 ? ["Low", "value-high"] : value < 100 ? ["Normal", "value-normal"] : value < 126 ? ["Borderline / prediabetes range", "value-borderline"] : ["High / diabetes range", "value-high"];
  if (type === "haemoglobin") return value < 12 ? ["Low / anaemia range", "value-high"] : value <= 17.5 ? ["Normal", "value-normal"] : ["High", "value-high"];
  return value < 200 ? ["Normal / desirable", "value-normal"] : value < 240 ? ["Borderline high", "value-borderline"] : ["High", "value-high"];
}

function valueBadge(type, value) {
  const [label, className] = classifyValue(type, Number(value));
  const badge = document.createElement("span");
  badge.className = `value-badge ${className}`;
  badge.textContent = value;
  badge.title = label;
  badge.setAttribute("aria-label", `${value}: ${label}`);
  return badge;
}

function hasAbnormal(record) {
  return ["glucose", "haemoglobin", "cholesterol"].some((field) => classifyValue(field, Number(record[field]))[1] !== "value-normal");
}

function remarksCell(record) {
  const td = document.createElement("td");
  td.className = "remarks-cell";
  if (!record.remarks) {
    const note = document.createElement("div");
    note.className = "text-secondary fst-italic mb-2";
    note.textContent = "No remarks yet";
    td.append(note, createButton("Generate", "btn-outline-primary", () => regenerate(record.id)));
    return td;
  }
  const badge = document.createElement("span");
  badge.className = "badge ai-badge";
  badge.textContent = "AI";
  const text = document.createElement("span");
  text.className = "remark-text";
  text.textContent = record.remarks;
  if (expandedRemarks.has(record.id)) text.classList.add("expanded");
  const toggle = createButton(expandedRemarks.has(record.id) ? "Show less" : "Show more", "btn-link btn-sm p-0 ms-1", () => {
    if (expandedRemarks.has(record.id)) expandedRemarks.delete(record.id);
    else expandedRemarks.add(record.id);
    render();
  });
  toggle.classList.add("remark-toggle");
  td.append(badge, text, toggle);
  return td;
}

function matchesSearch(record) {
  const query = searchInput.value.trim().toLowerCase();
  return !query || record.full_name.toLowerCase().includes(query) || record.email.toLowerCase().includes(query);
}

function parseDate(value) {
  const [day, month, year] = value.split("/").map(Number);
  return new Date(year, month - 1, day).getTime();
}

function visibleRecords() {
  const filtered = records.filter(matchesSearch);
  if (!sortKey) return filtered;
  return filtered.sort((a, b) => {
    const left = sortKey === "date_of_birth" ? parseDate(a[sortKey]) : sortKey === "id" ? Number(a[sortKey]) : a[sortKey].toLowerCase();
    const right = sortKey === "date_of_birth" ? parseDate(b[sortKey]) : sortKey === "id" ? Number(b[sortKey]) : b[sortKey].toLowerCase();
    return (left < right ? -1 : left > right ? 1 : 0) * (sortDirection === "asc" ? 1 : -1);
  });
}

function updateSummary() {
  document.getElementById("total-records").textContent = records.length;
  document.getElementById("abnormal-records").textContent = records.filter(hasAbnormal).length;
  document.getElementById("remark-records").textContent = records.filter((record) => Boolean(record.remarks)).length;
  document.getElementById("record-count").textContent = visibleRecords().length;
}

function renderEmptyState() {
  const isSearch = Boolean(searchInput.value.trim());
  emptyTitle.textContent = isSearch ? "No matching records" : "No records yet";
  emptyMessage.textContent = isSearch ? "Try a different name or email search." : "Add a patient record to begin your care overview.";
  document.getElementById("empty-add-btn").classList.toggle("d-none", isSearch);
  emptyState.classList.remove("d-none");
}

function render() {
  const visible = visibleRecords();
  tableBody.replaceChildren();
  updateSummary();
  for (const record of visible) {
    const row = document.createElement("tr");
    const name = document.createElement("div");
    name.className = "name-cell";
    const avatar = document.createElement("span");
    avatar.className = "initials";
    avatar.textContent = initials(record.full_name);
    const nameText = document.createElement("span");
    nameText.textContent = record.full_name;
    name.append(avatar, nameText);
    const nameCell = document.createElement("td");
    nameCell.appendChild(name);
    const actions = document.createElement("td");
    actions.className = "text-end text-nowrap";
    actions.append(createButton("Edit", "btn-outline-secondary me-1", () => openForm(record)), createButton("Delete", "btn-outline-danger", () => openDelete(record)));
    const rowCells = [
      String(record.id), nameCell, record.date_of_birth, record.email,
      valueBadge("glucose", record.glucose), valueBadge("haemoglobin", record.haemoglobin), valueBadge("cholesterol", record.cholesterol),
    ];
    rowCells.forEach((value, index) => {
      if (value instanceof Node) {
        const td = document.createElement("td");
        td.className = index > 3 ? "text-end" : "";
        td.appendChild(value);
        row.appendChild(td);
      } else row.appendChild(Object.assign(document.createElement("td"), { textContent: value }));
    });
    row.append(remarksCell(record), actions);
    tableBody.appendChild(row);
  }
  emptyState.classList.toggle("d-none", visible.length > 0);
  if (visible.length === 0) renderEmptyState();
}

function updateSortButtons() {
  document.querySelectorAll(".sort-button").forEach((button) => {
    const active = button.dataset.sort === sortKey;
    button.classList.toggle("active", active);
    button.classList.toggle("asc", active && sortDirection === "asc");
    button.classList.toggle("desc", active && sortDirection === "desc");
    button.setAttribute("aria-label", `Sort by ${button.dataset.sort.replace("_", " ")}${active ? `, ${sortDirection === "asc" ? "ascending" : "descending"}` : ""}`);
  });
}

async function loadRecords() {
  loadingState.classList.remove("d-none");
  tableBody.replaceChildren();
  try {
    const { ok, data } = await request(API);
    if (!ok) throw new Error();
    records = Array.isArray(data) ? data : [];
    render();
  } catch {
    showToast("Could not load records.", "danger");
    records = [];
    render();
  } finally {
    loadingState.classList.add("d-none");
  }
}

function clearErrors() {
  formAlert.classList.add("d-none");
  FIELDS.forEach((name) => {
    form.elements[name].classList.remove("is-invalid");
    form.elements[name].closest(".field-wrap").querySelector(".invalid-feedback").textContent = "";
  });
}

function showErrors(data) {
  const errors = (data && data.errors) || {};
  Object.entries(errors).forEach(([name, message]) => {
    const input = form.elements[name];
    if (!input) return;
    input.classList.add("is-invalid");
    input.closest(".field-wrap").querySelector(".invalid-feedback").textContent = message;
  });
  formAlert.textContent = (data && data.message) || "Something went wrong.";
  formAlert.classList.remove("d-none");
}

function openForm(record = null) {
  editingId = record ? record.id : null;
  document.getElementById("record-modal-title").textContent = record ? "Edit record" : "Add record";
  form.reset();
  clearErrors();
  if (record) FIELDS.forEach((name) => { form.elements[name].value = record[name]; });
  recordModal.show();
}

function setSaving(saving) {
  saveBtn.disabled = saving;
  saveBtn.querySelector(".spinner-border").classList.toggle("d-none", !saving);
  saveBtn.querySelector(".label").textContent = saving ? "Saving and generating remarks..." : "Save";
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearErrors();
  const payload = Object.fromEntries(FIELDS.map((name) => [name, form.elements[name].value]));
  const url = editingId ? `${API}/${editingId}` : API;
  setSaving(true);
  let result;
  try {
    result = await request(url, { method: editingId ? "PUT" : "POST", body: JSON.stringify(payload) });
  } catch {
    result = { ok: false, data: { message: "Could not reach the server." } };
  }
  setSaving(false);
  if (!result.ok) { showErrors(result.data); return; }
  recordModal.hide();
  showToast(editingId ? "Record updated." : "Record created.");
  if (result.data.warning) showToast(result.data.warning, "warning");
  await loadRecords();
});

async function regenerate(id) {
  showToast("Generating remarks...", "secondary");
  try {
    const { ok, data } = await request(`${API}/${id}/remarks`, { method: "POST" });
    if (!ok) showToast((data && data.message) || "Could not generate remarks.", "warning");
  } catch { showToast("Could not reach the server.", "danger"); }
  await loadRecords();
}

function openDelete(record) {
  deletingId = record.id;
  document.getElementById("delete-name").textContent = record.full_name;
  deleteModal.show();
}

document.getElementById("confirm-delete-btn").addEventListener("click", async () => {
  try {
    const { ok, data } = await request(`${API}/${deletingId}`, { method: "DELETE" });
    deleteModal.hide();
    showToast(ok ? "Record deleted." : (data && data.message) || "Could not delete the record.", ok ? "success" : "danger");
  } catch { showToast("Could not reach the server.", "danger"); }
  await loadRecords();
});

document.querySelectorAll(".sort-button").forEach((button) => button.addEventListener("click", () => {
  if (sortKey === button.dataset.sort) sortDirection = sortDirection === "asc" ? "desc" : "asc";
  else { sortKey = button.dataset.sort; sortDirection = "asc"; }
  updateSortButtons();
  render();
}));
searchInput.addEventListener("input", render);
document.getElementById("add-btn").addEventListener("click", () => openForm());
document.getElementById("empty-add-btn").addEventListener("click", () => openForm());
updateSortButtons();
loadRecords();
