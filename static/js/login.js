/* login.js – login / registro en un único formulario */
document.addEventListener("DOMContentLoaded", () => {
  let mode = "login";                      // 'login'  |  'signup'
  const form     = document.getElementById("auth-form");
  const title    = document.getElementById("form-title");
  const submitBtn= document.getElementById("submit-btn");
  const toggle   = document.getElementById("toggle");
  const switcher = document.getElementById("switch-to-signup");

  function updateUI() {
    if (mode === "login") {
      title.textContent   = "Iniciar sesión";
      submitBtn.textContent = "Entrar";
      toggle.innerHTML    = '¿No tienes cuenta? <a href="#" id="switch-to-signup">Regístrate</a>';
    } else {
      title.textContent   = "Crear cuenta";
      submitBtn.textContent = "Registrar";
      toggle.innerHTML    = '¿Ya tienes cuenta? <a href="#" id="switch-to-login">Inicia sesión</a>';
      // en registro no hace falta el checkbox recordar
      document.getElementById("remember-wrapper").style.display = "none";
    }
  }

  document.addEventListener("click", (e) => {
    if (e.target.id === "switch-to-signup") {
      e.preventDefault();
      mode = "signup";
      updateUI();
    }
    if (e.target.id === "switch-to-login") {
      e.preventDefault();
      mode = "login";
      document.getElementById("remember-wrapper").style.display = "flex";
      updateUI();
    }
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const payload = {
      email:    document.getElementById("email").value.trim(),
      password: document.getElementById("password").value,
      remember: document.getElementById("remember").checked
    };

    const url = (mode === "login") ? "/api/login" : "/api/signup";

    const res = await fetch(url, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      // login / signup ok → a la página principal
      location.href = "/";
    } else {
      const {error} = await res.json();
      alert(error || "Se produjo un error");
    }
  });

  document.getElementById("google-btn")
          .addEventListener("click", () => location.href = "/login/google");

  // pinta estado inicial
  updateUI();
});
