let currentPage = 1;


// ============================================================
// MODALES
// ============================================================

function resetModalPosition(modal) {
    const content = modal.querySelector(".modal-content");
    content.style.left = "50%";
    content.style.top = "50%";
    content.style.transform = "translate(-50%, -50%)";
}

function openAddBatchModal() {
    const modal = document.getElementById("addBatchModal");
    resetModalPosition(modal);
    modal.style.display = "block";
    makeDraggable(modal);
}

function closeAddBatchModal() {
    document.getElementById("addBatchModal").style.display = "none";
    document.getElementById("addBatchForm").reset();
}

function openPreviewModal(imageUrl) {
    const modal = document.getElementById("previewModal");
    document.getElementById("previewImage").src = imageUrl;
    resetModalPosition(modal);
    modal.style.display = "block";
    makeDraggable(modal);
}

function closePreviewModal() {
    document.getElementById("previewModal").style.display = "none";
}


// ============================================================
// CARGA DE BATCHES
// ============================================================

async function loadBatches(page = 1) {
    currentPage = page;

    const response = await fetch(`/api/batches?page=${page}`);
    const data = await response.json();

    const tbody = document.getElementById("batchesTable");
    tbody.innerHTML = "";

    data.batches.forEach(batch => {
        const row = document.createElement("tr");

        const statusIcon = batch.status === "correct"
            ? '<span class="status-icon status-correct">✓</span>'
            : '<span class="status-icon status-incorrect">✗</span>';

        row.innerHTML = `
            <td>${batch.batch_number}</td>
            <td>${batch.hole_id}</td>
            <td>${batch.from}</td>
            <td>${batch.to}</td>
            <td>${batch.machine}</td>
            <td>${statusIcon}</td>
            <td>${batch.comentarios}</td>
            <td><button class="btn btn-small" onclick="showPreview(${batch.batch_number})">Ver</button></td>
            <td><button class="btn btn-danger btn-small" onclick="confirmDelete(${batch.batch_number})">Eliminar</button></td>
        `;

        tbody.appendChild(row);
    });

    renderPagination(data.total_pages, data.current_page);
    updateMetrosEscaneados();
}


// ============================================================
// ELIMINAR
// ============================================================

function confirmDelete(batchNumber) {
    if (confirm("¿Seguro que deseas eliminar este batch?")) {
        deleteBatch(batchNumber);
    }
}

async function deleteBatch(batchNumber) {
    const res = await fetch(`/api/batches/${batchNumber}`, { method: "DELETE" });
    const data = await res.json();

    if (data.success) {
        alert("Batch eliminado correctamente.");
        loadBatches(1);
    } else {
        alert("Error al eliminar: " + data.error);
    }
}


// ============================================================
// PREVIEW
// ============================================================

async function showPreview(batchNumber) {
    const response = await fetch(`/api/preview/${batchNumber}`);
    const data = await response.json();

    if (data.image_path) {
        openPreviewModal(data.image_path);
    } else {
        alert("No hay imagen disponible para este batch.");
    }
}


// ============================================================
// AGREGAR BATCH
// ============================================================

document.getElementById("addBatchForm").addEventListener("submit", async (e) => {
    e.preventDefault();

    const formData = {
        machine: document.getElementById("machine").value,
        hole_id: document.getElementById("holeId").value,
        from: document.getElementById("from").value,
        to: document.getElementById("to").value,
        comentarios: document.getElementById("comentarios").value
    };

    const response = await fetch("/api/batches", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData)
    });

    const data = await response.json();

    if (data.success) {
        closeAddBatchModal();
        loadBatches(1);
    }
});
// ============================================================
//  EDITAR BATCK DE STATUS CHECKER
// ============================================================
async function editBatch(batchNumber) {
    const response = await fetch(`/api/status_checker_data?page=${currentPage}`);
    const data = await response.json();
    const batch = data.batches.find(b => b.batch_number === batchNumber);

    if (!batch) {
        alert("Batch no encontrado");
        return;
    }

    // Llenar modal
    document.getElementById("editBatchNumber").value = batch.batch_number;
    document.getElementById("editHoleId").value = batch.hole_id;
    document.getElementById("editFrom").value = batch.from;
    document.getElementById("editTo").value = batch.to;
    document.getElementById("editMachine").value = batch.machine;
    document.getElementById("editComentarios").value = batch.comentarios || "";

    // Mostrar modal
    document.getElementById("editModal").style.display = "block";
}
function closeEditModal() {
    document.getElementById("editModal").style.display = "none";
}


// ============================================================
// PAGINACIÓN
// ============================================================

function renderPagination(total, current) {
    const container = document.getElementById("pagination");
    container.innerHTML = "";

    for (let i = 1; i <= total; i++) {
        const btn = document.createElement("button");
        btn.innerText = i;
        btn.className = (i === current) ? "btn btn-primary" : "btn btn-secondary";
        btn.onclick = () => loadBatches(i);
        container.appendChild(btn);
    }
}


// ============================================================
// METROS ESCANEADOS
// ============================================================

async function updateMetrosEscaneados() {
    const response = await fetch("/api/metros_escaneados");
    const data = await response.json();
    document.getElementById("metrosEscaneados").textContent = data.metros;
}


// ============================================================
// INICIO
// ============================================================

document.addEventListener("DOMContentLoaded", () => {
    if (document.getElementById("batchesTable")) {
        loadBatches(1);
    }
});


// ================= STATUS CHECKER =================
async function loadStatusData(page = 1) {
    const res = await fetch(`/api/status_checker_data?page=${page}`);
    const data = await res.json();

    const tbody = document.getElementById("statusTable");
    if (!tbody) return;
    tbody.innerHTML = "";

    (data.batches || []).forEach(batch => {
        const mv = batch.machine_values || {};

        const row = document.createElement("tr");
        row.innerHTML = `
            <td>${batch.batch_number ?? ""}</td>
            <td>${batch.hole_id ?? "-"}</td>
            <td>${batch.from ?? "-"}</td>
            <td>${batch.to ?? "-"}</td>
            <td>${batch.machine ?? "-"}</td>

            <td>${mv.hole_id ?? "-"}</td>
            <td>${mv.from ?? "-"}</td>
            <td>${mv.to ?? "-"}</td>
            <td>${mv.machine ?? "-"}</td>

            <td>
                <button onclick="editBatch(${batch.batch_number})">✏️</button>
            </td>
        `;
        tbody.appendChild(row);
    });
}
