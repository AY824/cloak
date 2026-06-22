const mockAssets = [
    {
        id: 'asset-001',
        name: 'Data Compliance Dataset',
        type: 'data_compliance',
        typeName: 'Data Compliance',
        samples: 5000,
        price: 150,
        owner: '0x1234...abcd',
        quality: 4.5
    },
    {
        id: 'asset-002',
        name: 'Patent Risk Assessment Data',
        type: 'patent_infringement',
        typeName: 'Patent Risk',
        samples: 3200,
        price: 200,
        owner: '0x5678...efgh',
        quality: 4.8
    },
    {
        id: 'asset-003',
        name: 'Algorithm Security Vulnerability Dataset',
        type: 'algorithm_security',
        typeName: 'Algorithm Security',
        samples: 2800,
        price: 180,
        owner: '0x9abc...ijkl',
        quality: 4.2
    },
    {
        id: 'asset-004',
        name: 'R&D Failure Risk Case Library',
        type: 'rd_failure',
        typeName: 'R&D Failure',
        samples: 1500,
        price: 120,
        owner: '0xdef0...mnop',
        quality: 4.0
    },
    {
        id: 'asset-005',
        name: 'Geopolitical Risk Data',
        type: 'geopolitical',
        typeName: 'Geopolitical',
        samples: 800,
        price: 250,
        owner: '0x1234...abcd',
        quality: 4.7
    }
];

let isTraining = false;
let currentRound = 0;
const maxRounds = 20;
let trainingInterval = null;

document.addEventListener('DOMContentLoaded', function() {
    initWallet();
    initAssets();
    initCompute();
});

function initWallet() {
    const connectBtn = document.getElementById('connectBtn');
    if (!connectBtn) return;
    
    let connected = false;
    
    connectBtn.addEventListener('click', function() {
        if (!connected) {
            connected = true;
            connectBtn.textContent = '0x1234...5678';
            showToast('Wallet connected', 'success');
        } else {
            connected = false;
            connectBtn.textContent = 'Connect';
            showToast('Wallet disconnected', 'info');
        }
    });
}

function initAssets() {
    const assetsList = document.getElementById('assetsList');
    const filter = document.getElementById('riskTypeFilter');
    
    if (!assetsList) return;
    
    renderAssets('all');
    
    if (filter) {
        filter.addEventListener('change', function() {
            renderAssets(this.value);
        });
    }
}

function renderAssets(filterType) {
    const assetsList = document.getElementById('assetsList');
    if (!assetsList) return;
    
    const filtered = filterType === 'all' 
        ? mockAssets 
        : mockAssets.filter(a => a.type === filterType);
    
    if (filtered.length === 0) {
        assetsList.innerHTML = '<p>No assets found.</p>';
        return;
    }
    
    let html = '';
    filtered.forEach(asset => {
        html += `
            <div class="asset-item">
                <h4>${asset.name}</h4>
                <div class="meta">
                    ${asset.typeName} · ${asset.samples.toLocaleString()} samples · ${asset.price} USDT
                </div>
            </div>
        `;
    });
    
    assetsList.innerHTML = html;
}

function initCompute() {
    const startBtn = document.getElementById('startBtn');
    const resetBtn = document.getElementById('resetBtn');
    
    if (startBtn) {
        startBtn.addEventListener('click', startTraining);
    }
    
    if (resetBtn) {
        resetBtn.addEventListener('click', resetTraining);
    }
}

function startTraining() {
    if (isTraining) return;
    
    isTraining = true;
    currentRound = 0;
    
    const startBtn = document.getElementById('startBtn');
    if (startBtn) startBtn.disabled = true;
    
    showToast('Training started', 'info');
    
    trainingInterval = setInterval(function() {
        currentRound++;
        
        const accuracy = 0.5 + (currentRound / maxRounds) * 0.35 + Math.random() * 0.02;
        const loss = 0.8 - (currentRound / maxRounds) * 0.6 + Math.random() * 0.02;
        
        updateMetrics(accuracy, loss);
        updateRoundDisplay();
        updateNodeStatuses();
        
        if (currentRound >= maxRounds) {
            clearInterval(trainingInterval);
            isTraining = false;
            
            const startBtn = document.getElementById('startBtn');
            if (startBtn) startBtn.disabled = false;
            
            showToast('Training completed', 'success');
        }
    }, 500);
}

function resetTraining() {
    if (trainingInterval) {
        clearInterval(trainingInterval);
    }
    
    isTraining = false;
    currentRound = 0;
    
    const startBtn = document.getElementById('startBtn');
    if (startBtn) startBtn.disabled = false;
    
    updateMetrics(0, 0);
    updateRoundDisplay();
    resetNodeStatuses();
    
    showToast('Training reset', 'info');
}

function updateMetrics(accuracy, loss) {
    const accEl = document.getElementById('accuracy');
    const lossEl = document.getElementById('loss');
    
    if (accEl) accEl.textContent = (accuracy * 100).toFixed(2) + '%';
    if (lossEl) lossEl.textContent = loss.toFixed(3);
}

function updateRoundDisplay() {
    const roundEl = document.getElementById('roundNum');
    if (roundEl) roundEl.textContent = currentRound;
}

function updateNodeStatuses() {
    const nodes = document.querySelectorAll('.node .status');
    const statuses = ['Training', 'Training', 'Training'];
    
    nodes.forEach((node, index) => {
        if (node && statuses[index]) {
            node.textContent = statuses[index];
        }
    });
}

function resetNodeStatuses() {
    const nodes = document.querySelectorAll('.node .status');
    nodes.forEach(node => {
        if (node) node.textContent = 'Idle';
    });
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = 'toast ' + type;
    toast.textContent = message;
    
    document.body.appendChild(toast);
    
    setTimeout(function() {
        toast.remove();
    }, 3000);
}
