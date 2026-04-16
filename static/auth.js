const loginForm = document.getElementById("login-form");
const loginMessage = document.getElementById("login-message");

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(loginForm);
  const response = await fetch("/api/login", {
    method: "POST",
    body: formData,
    credentials: "same-origin",
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    loginMessage.textContent = payload.detail || "Ошибка входа";
    return;
  }
  window.location.href = "/";
});
