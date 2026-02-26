/* ============================================================
   KARTU PINTAR - Main JavaScript
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {
    initSidebar();
    initFlashMessages();
});

// ============================================================
// SIDEBAR TOGGLE
// ============================================================

function initSidebar() {
    const hamburger = document.getElementById('hamburger');
    const sidebar = document.getElementById('sidebar');
    const sidebarClose = document.getElementById('sidebarClose');
    const mainContent = document.getElementById('mainContent');

    if (hamburger && sidebar) {
        hamburger.addEventListener('click', () => {
            sidebar.classList.toggle('open');
        });
    }

    if (sidebarClose && sidebar) {
        sidebarClose.addEventListener('click', () => {
            sidebar.classList.remove('open');
        });
    }

    // Close sidebar when clicking outside on mobile
    if (mainContent && sidebar) {
        mainContent.addEventListener('click', () => {
            if (window.innerWidth <= 768 && sidebar.classList.contains('open')) {
                sidebar.classList.remove('open');
            }
        });
    }
}

// ============================================================
// FLASH MESSAGES AUTO DISMISS
// ============================================================

function initFlashMessages() {
    const flashes = document.querySelectorAll('.flash-message');
    flashes.forEach((flash, i) => {
        setTimeout(() => {
            flash.style.opacity = '0';
            flash.style.transform = 'translateY(-10px)';
            setTimeout(() => flash.remove(), 300);
        }, 4000 + (i * 500));
    });
}

// ============================================================
// NUMPAD PAYMENT
// ============================================================

function initNumpad() {
    const display = document.getElementById('amountValue');
    if (!display) return;

    let amount = '';

    window.numpadPress = function(val) {
        if (val === 'C') {
            amount = '';
        } else if (val === 'DEL') {
            amount = amount.slice(0, -1);
        } else {
            if (amount.length < 9) {
                amount += val;
            }
        }
        display.textContent = amount ? parseInt(amount).toLocaleString('id-ID') : '0';
        const hiddenInput = document.getElementById('amountInput');
        if (hiddenInput) hiddenInput.value = amount;
    };
}

// ============================================================
// SIMULATE NFC SCAN
// ============================================================

function simulateNFCScan() {
    const resultArea = document.getElementById('scanResult');
    if (!resultArea) return;

    resultArea.innerHTML = `
        <div class="scan-card" style="border-style: solid; border-color: var(--gold-500);">
            <div class="scan-card-icon" style="animation: scanPulse 1s ease-in-out infinite;">
                <i class="bi bi-broadcast"></i>
            </div>
            <h3>Mendekatkan Kartu NFC...</h3>
            <p>Tahan kartu di dekat perangkat</p>
        </div>
    `;

    // Simulate scan delay
    setTimeout(() => {
        // Simulate finding a card
        const demoUID = 'A1B2C3D4';
        window.location.href = `/scan/result/${demoUID}`;
    }, 2500);
}

// ============================================================
// SIMULATE QR SCAN
// ============================================================

function simulateQRScan() {
    const resultArea = document.getElementById('scanResult');
    if (!resultArea) return;

    resultArea.innerHTML = `
        <div class="scanner-area">
            <div class="scanner-line"></div>
            <div style="z-index: 1; text-align: center;">
                <i class="bi bi-qr-code-scan" style="font-size: 48px; color: var(--gold-400);"></i>
                <p style="color: var(--text-muted); margin-top: 8px; font-size: 13px;">Arahkan kamera ke QR Code</p>
            </div>
        </div>
    `;

    // Simulate scan delay
    setTimeout(() => {
        const demoQR = 'KP-2025-001';
        window.location.href = `/scan/result/${demoQR}`;
    }, 3000);
}

// ============================================================
// FORMAT CURRENCY
// ============================================================

function formatRupiah(num) {
    return 'Rp ' + num.toLocaleString('id-ID');
}
