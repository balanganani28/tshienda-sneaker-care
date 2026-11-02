// Camera QR Scanner with BarcodeDetector & HTML5 Video Stream
document.addEventListener('DOMContentLoaded', () => {
  const videoElem = document.getElementById('scannerVideo');
  const startBtn = document.getElementById('startCameraBtn');
  const stopBtn = document.getElementById('stopCameraBtn');
  const statusMsg = document.getElementById('cameraStatus');
  const manualInput = document.getElementById('order_number');
  let stream = null;
  let detector = null;
  let scanningActive = false;

  // Initialize BarcodeDetector if available
  if ('BarcodeDetector' in window) {
    try {
      detector = new BarcodeDetector({ formats: ['qr_code'] });
    } catch (e) {
      console.warn('BarcodeDetector format qr_code not supported directly', e);
    }
  }

  // Play audio synth beep on scan
  function playBeep() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(880, ctx.currentTime); // 880Hz A5
      gain.gain.setValueAtTime(0.2, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.15);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.15);
      if (navigator.vibrate) navigator.vibrate(100);
    } catch (e) {}
  }

  async function startCamera() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      if (statusMsg) statusMsg.textContent = 'Camera not supported in this browser. Please type order number below.';
      return;
    }
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: 'environment' } }
      });
      videoElem.srcObject = stream;
      videoElem.setAttribute('playsinline', true);
      await videoElem.play();
      scanningActive = true;
      if (startBtn) startBtn.style.display = 'none';
      if (stopBtn) stopBtn.style.display = 'inline-flex';
      if (statusMsg) statusMsg.textContent = 'Camera active. Point at QR tag.';
      scanFrame();
    } catch (err) {
      if (statusMsg) statusMsg.textContent = 'Camera access denied. Please use the manual input.';
    }
  }

  function stopCamera() {
    scanningActive = false;
    if (stream) {
      stream.getTracks().forEach(t => t.stop());
      stream = null;
    }
    if (startBtn) startBtn.style.display = 'inline-flex';
    if (stopBtn) stopBtn.style.display = 'none';
    if (statusMsg) statusMsg.textContent = 'Camera stopped.';
  }

  async function scanFrame() {
    if (!scanningActive) return;
    if (detector && videoElem.readyState >= 2) {
      try {
        const barcodes = await detector.detect(videoElem);
        if (barcodes.length > 0) {
          const raw = barcodes[0].rawValue;
          playBeep();
          handleScannedData(raw);
          stopCamera();
          return;
        }
      } catch (err) {}
    }
    requestAnimationFrame(scanFrame);
  }

  function handleScannedData(raw) {
    let code = raw.trim().toUpperCase();
    if (code.includes('/track/')) {
      code = code.split('/track/')[1].split('?')[0].split('#')[0].trim().toUpperCase();
    }
    if (manualInput) manualInput.value = code;
    // Auto lookup order
    window.location.href = `/staff/scan?code=${encodeURIComponent(code)}`;
  }

  if (startBtn) startBtn.addEventListener('click', startCamera);
  if (stopBtn) stopBtn.addEventListener('click', stopCamera);
});
