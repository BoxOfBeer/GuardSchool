const setupForm = document.getElementById("setup-form");
const setupMessage = document.getElementById("setup-message");

setupForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(setupForm);
  const response = await fetch("/api/setup", { method: "POST", body: formData });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    setupMessage.textContent = payload.detail || "Ошибка создания";
    return;
  }
  window.location.href = "/login";
});
