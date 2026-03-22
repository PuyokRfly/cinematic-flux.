
// ── Track active EventSource connections ──
const activeSources = {};
let activeCount = 0;

// ── Toast helper ──────────────────────────────────────────────────────────
function showToast(msg, type = 'info') {
    const toast   = document.getElementById('toast');
    const icon    = document.getElementById('toast-icon');
    const msgEl   = document.getElementById('toast-msg');
    const colors  = { info: 'text-primary', error: 'text-error', success: 'text-tertiary' };
    const icons   = { info: 'info', error: 'error', success: 'check_circle' };
    icon.className    = `material-symbols-outlined text-sm ${colors[type] || colors.info}`;
    icon.textContent  = icons[type] || icons.info;
    msgEl.textContent = msg;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 4000);
}

// ── Vault Status ──────────────────────────────────────────────────────────
async function refreshVaultStatus() {
    try {
        const res  = await fetch('/vault-status');
        const data = await res.json();
        if (data.error) {
            document.getElementById('vault-percent').textContent   = 'N/A';
            document.getElementById('vault-used').textContent      = 'Drive offline';
            document.getElementById('vault-available').textContent = '—';
            document.getElementById('vault-total').textContent     = '—';
            return;
        }
        const pct = parseFloat(data.percent);
        document.getElementById('vault-percent').textContent   = pct + '%';
        document.getElementById('vault-used').textContent      = data.used;
        document.getElementById('vault-available').textContent = data.available;
        document.getElementById('vault-total').textContent     = data.total;

        // Animate SVG ring: circumference = 2π×88 ≈ 553
        const CIRC   = 553;
        const offset = CIRC - (pct / 100) * CIRC;
        document.getElementById('vault-ring-progress').setAttribute('stroke-dashoffset', offset.toFixed(1));
    } catch (e) {
        console.warn('Vault status fetch failed:', e);
    }
}

// ── Build a download card DOM node ────────────────────────────────────────
function createDownloadCard(dlId, title, fmt) {
    const fmtLabel = fmt === 'mp3' ? 'MP3' : 'MP4';
    const fmtIcon  = fmt === 'mp3' ? 'music_note' : 'videocam';

    const card = document.createElement('div');
    card.id    = `card-${dlId}`;
    card.className = 'download-card bg-surface-container rounded-xl p-6 flex flex-col md:flex-row gap-6 items-center';
    card.innerHTML = `
        <!-- Thumbnail placeholder -->
        <div class="w-full md:w-40 h-24 rounded-md overflow-hidden bg-surface-container-lowest flex-shrink-0 flex items-center justify-center">
            <span class="material-symbols-outlined text-4xl text-on-surface-variant opacity-30">${fmtIcon}</span>
        </div>
        <!-- Info -->
        <div class="flex-1 w-full space-y-3">
            <div class="flex justify-between items-start">
                <div class="flex-1 min-w-0 pr-4">
                    <h3 id="title-${dlId}" class="font-headline font-bold text-on-surface leading-tight truncate">${escHtml(title)}</h3>
                    <div class="flex items-center gap-3 mt-1">
                        <span class="flex items-center gap-1 text-[10px] text-tertiary-container font-bold uppercase tracking-widest px-2 py-0.5 rounded bg-surface-container-highest">
                            <span class="material-symbols-outlined text-xs">${fmtIcon}</span> ${fmtLabel}
                        </span>
                        <span id="size-${dlId}" class="text-xs text-on-surface-variant">Memulai…</span>
                    </div>
                </div>
                <div class="flex gap-2 flex-shrink-0">
                    <button onclick="cancelDownload('${dlId}')" class="p-2 rounded-full hover:bg-surface-container-lowest text-error transition-colors" title="Cancel">
                        <span class="material-symbols-outlined text-sm">close</span>
                    </button>
                </div>
            </div>
            <!-- Progress bar -->
            <div class="space-y-2">
                <div class="h-1.5 w-full bg-surface-variant/40 rounded-full overflow-hidden">
                    <div id="bar-${dlId}" class="progress-fill h-full bg-secondary rounded-full shadow-[0_0_10px_rgba(255,113,106,0.5)]" style="width:0%"></div>
                </div>
                <div class="flex justify-between text-[10px] font-bold text-on-surface-variant uppercase tracking-tighter">
                    <span id="pct-${dlId}">0% Complete</span>
                    <span id="speed-${dlId}">—</span>
                </div>
                <div class="text-[10px] text-on-surface-variant/70">
                    ETA: <span id="eta-${dlId}">—</span>
                </div>
            </div>
        </div>
    `;
    return card;
}

// ── Escape HTML ───────────────────────────────────────────────────────────
function escHtml(str) {
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Update active count label ─────────────────────────────────────────────
function updateActiveCount() {
    const el = document.getElementById('active-count');
    el.textContent = activeCount === 0
        ? '0 files currently in transit'
        : `${activeCount} file${activeCount > 1 ? 's' : ''} currently in transit`;
    document.getElementById('empty-state').style.display = activeCount === 0 ? '' : 'none';
}

// ── Start download ────────────────────────────────────────────────────────
async function startDownload() {
    const url    = document.getElementById('url-input').value.trim();
    const fmtRaw = document.getElementById('format-select').value;  // mp4 | mp4_720 | mp3 | mp3_320
    const fmt    = fmtRaw.startsWith('mp3') ? 'mp3' : 'mp4';

    if (!url) {
        showToast('Tempel URL YouTube terlebih dahulu.', 'error');
        return;
    }

    const btn = document.getElementById('download-btn');
    btn.disabled = true;
    btn.classList.add('opacity-60', 'cursor-not-allowed');

    let data;
    try {
        const res = await fetch('/download', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ url, format: fmt }),
        });
        data = await res.json();
        if (!res.ok) {
            showToast(data.error || 'Gagal memulai download.', 'error');
            btn.disabled = false;
            btn.classList.remove('opacity-60', 'cursor-not-allowed');
            return;
        }
    } catch (e) {
        showToast('Tidak dapat terhubung ke server. Pastikan app.py berjalan.', 'error');
        btn.disabled = false;
        btn.classList.remove('opacity-60', 'cursor-not-allowed');
        return;
    }

    const dlId = data.id;

    // Inject download card
    const container = document.getElementById('active-downloads');
    const card      = createDownloadCard(dlId, 'Fetching info…', fmt);
    container.appendChild(card);
    activeCount++;
    updateActiveCount();

    // Re-enable button
    btn.disabled = false;
    btn.classList.remove('opacity-60', 'cursor-not-allowed');
    document.getElementById('url-input').value = '';
    showToast('Download dimulai!', 'success');

    // Open SSE stream
    const evtSource = new EventSource(`/progress/${dlId}`);
    activeSources[dlId] = evtSource;

    evtSource.onmessage = function(event) {
        const d = JSON.parse(event.data);

        // Update title if available
        if (d.title && d.title !== 'Fetching info…') {
            const titleEl = document.getElementById(`title-${dlId}`);
            if (titleEl) titleEl.textContent = d.title;
        }

        if (d.status === 'downloading') {
            const pct   = Math.min(parseFloat(d.percent) || 0, 100).toFixed(1);
            const bar   = document.getElementById(`bar-${dlId}`);
            const pctEl = document.getElementById(`pct-${dlId}`);
            const spEl  = document.getElementById(`speed-${dlId}`);
            const szEl  = document.getElementById(`size-${dlId}`);
            const etaEl = document.getElementById(`eta-${dlId}`);
            if (bar)   bar.style.width   = pct + '%';
            if (pctEl) pctEl.textContent = pct + '% Complete';
            if (spEl)  spEl.textContent  = d.speed  || '—';
            if (szEl)  szEl.textContent  = (d.downloaded && d.total) ? `${d.downloaded} / ${d.total}` : '';
            if (etaEl) etaEl.textContent = d.eta    || '—';

        } else if (d.status === 'finished') {
            evtSource.close();
            delete activeSources[dlId];
            onDownloadFinished(dlId, d.title || 'Unknown', d.format || fmt);

        } else if (d.status === 'error') {
            evtSource.close();
            delete activeSources[dlId];
            onDownloadError(dlId, d.message || 'Unknown error');
        }
    };

    evtSource.onerror = function() {
        // Only close if not already finished
        if (activeSources[dlId]) {
            evtSource.close();
            delete activeSources[dlId];
            onDownloadError(dlId, 'Koneksi SSE terputus.');
        }
    };
}

// ── Download finished handler ─────────────────────────────────────────────
function onDownloadFinished(dlId, title, fmt) {
    const card = document.getElementById(`card-${dlId}`);
    if (!card) return;

    // Ooze glow animation
    card.classList.add('ooze-anim');

    // Fill bar to 100%
    const bar   = document.getElementById(`bar-${dlId}`);
    const pctEl = document.getElementById(`pct-${dlId}`);
    const spEl  = document.getElementById(`speed-${dlId}`);
    const etaEl = document.getElementById(`eta-${dlId}`);
    if (bar)   bar.style.width   = '100%';
    if (pctEl) pctEl.textContent = '100% Complete';
    if (spEl)  spEl.textContent  = 'Done ✓';
    if (etaEl) etaEl.textContent = '—';

    showToast(`"${title}" selesai diunduh!`, 'success');

    // After animation, move to archive
    setTimeout(() => {
        card.remove();
        activeCount--;
        updateActiveCount();
        addToArchive(title, fmt);
        refreshVaultStatus();
    }, 2600);
}

// ── Download error handler ────────────────────────────────────────────────
function onDownloadError(dlId, msg) {
    const card = document.getElementById(`card-${dlId}`);
    if (card) {
        const pctEl = document.getElementById(`pct-${dlId}`);
        const spEl  = document.getElementById(`speed-${dlId}`);
        if (pctEl) pctEl.textContent = 'Error';
        if (spEl)  spEl.textContent  = '—';
        // Turn bar red
        const bar = document.getElementById(`bar-${dlId}`);
        if (bar) bar.classList.replace('bg-secondary', 'bg-error');
        setTimeout(() => {
            card.remove();
            activeCount--;
            updateActiveCount();
        }, 4000);
    }
    showToast('Download error: ' + msg, 'error');
}

// ── Cancel single download ────────────────────────────────────────────────
function cancelDownload(dlId) {
    if (activeSources[dlId]) {
        activeSources[dlId].close();
        delete activeSources[dlId];
    }
    const card = document.getElementById(`card-${dlId}`);
    if (card) { card.remove(); activeCount--; updateActiveCount(); }
    showToast('Download dibatalkan.', 'info');
}

// ── Cancel all downloads ──────────────────────────────────────────────────
function cancelAllDownloads() {
    Object.keys(activeSources).forEach(id => cancelDownload(id));
}

// ── Add entry to Archive section ──────────────────────────────────────────
function addToArchive(title, fmt) {
    // Re-fetch the live filesystem to keep Archive perfectly in sync
    loadArchive();
}

// ── Load real files into Archive ──────────────────────────────────────────
async function loadArchive() {
    try {
        const res   = await fetch('/files');
        const files = await res.json();
        const container = document.getElementById('archive-list');
        container.innerHTML = ''; 

        if (files.length === 0) {
            container.innerHTML = '<div class="col-span-full py-8 text-center text-on-surface-variant text-sm border border-dashed border-outline-variant/30 rounded-xl">No files found on PERANGKAT U.</div>';
            return;
        }

        files.forEach(file => {
            const isAudio = ['mp3', 'wav', 'm4a'].includes(file.format);
            const fmtIcon = isAudio ? 'music_note' : 'videocam';
            const html = `
                <div class="bg-surface-container-low rounded-xl p-4 flex gap-4 items-center group border border-transparent hover:border-outline-variant/20 transition-all">
                    <div class="w-20 h-20 rounded-lg overflow-hidden flex-shrink-0 bg-surface-container-highest flex items-center justify-center">
                        <span class="material-symbols-outlined text-3xl text-tertiary" style="font-variation-settings:'FILL' 1">${fmtIcon}</span>
                    </div>
                    <div class="overflow-hidden flex-1">
                        <h4 class="font-headline font-semibold text-sm text-on-surface truncate" title="${escHtml(file.name)}">${escHtml(file.name)}</h4>
                        <p class="text-[10px] text-on-surface-variant mt-1">${file.size} &bull; ${file.date}</p>
                        <div class="flex gap-4 mt-3">
                            <span class="text-[10px] font-bold text-tertiary flex items-center gap-1 uppercase tracking-widest"><span class="material-symbols-outlined text-[10px]" style="font-variation-settings:'FILL' 1">check_circle</span> Saved</span>
                            <button onclick="deleteFile('${escHtml(file.name)}')" class="text-[10px] font-bold text-error hover:text-error-container flex items-center gap-1 uppercase tracking-widest transition-colors"><span class="material-symbols-outlined text-[12px]">delete</span> Delete</button>
                        </div>
                    </div>
                </div>
            `;
            container.insertAdjacentHTML('beforeend', html);
        });
    } catch (e) {
        console.error('Failed to load archive:', e);
    }
}

// ── Delete File ───────────────────────────────────────────────────────────
async function deleteFile(filename) {
    if (!confirm(\`Are you sure you want to delete "\${filename}"?\`)) return;
    
    try {
        const res = await fetch(\`/files/\${encodeURIComponent(filename)}\`, { method: 'DELETE' });
        const data = await res.json();
        
        if (res.ok && data.status === 'deleted') {
            showToast('File deleted successfully', 'info');
            loadArchive();
            refreshVaultStatus();
        } else {
            showToast(data.error || 'Failed to delete file', 'error');
        }
    } catch (e) {
        showToast('Connection error while deleting', 'error');
    }
}

// ── Initialise on page load ───────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    updateActiveCount();
    refreshVaultStatus();
    loadArchive();
});

