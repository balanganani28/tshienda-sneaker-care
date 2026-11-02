// Real-time Order Tracking Enhancements
document.addEventListener('DOMContentLoaded', () => {
  const trackerCard = document.querySelector('.sneaker-tracker-card');
  if (!trackerCard) return;

  // Sound feedback on stage change if tab is open
  const orderCode = trackerCard.dataset.orderCode;
  const initialStage = trackerCard.dataset.currentStage;

  if (orderCode && initialStage && initialStage !== 'collected') {
    // Optional periodic refresh every 45s for customers waiting on campus
    setInterval(() => {
      fetch(`/api/orders/${orderCode}`)
        .then(r => r.ok ? r.json() : null)
        .then(data => {
          if (data && data.stage && data.stage !== initialStage) {
            window.location.reload();
          }
        })
        .catch(() => {});
    }, 45000);
  }
});
