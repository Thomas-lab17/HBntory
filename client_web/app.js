/* Client web HBntory
   Page publique : les visiteurs posent des questions en langage naturel
   sur les produits et le stock. Pas de connexion, pas d'historique.

   Chaque question est envoyée au service de réponses (ai_service) via
   POST /query ; la réponse est affichée dans le fil de discussion. */

const AI_API_URL = "http://localhost:8100";

const form = document.getElementById("question-form");
const input = document.getElementById("question-input");
const messages = document.getElementById("messages");
const error = document.getElementById("error");

function appendMessage(text, who) {
  const p = document.createElement("p");
  p.className = `msg ${who}`;
  p.textContent = text;
  messages.appendChild(p);
  messages.scrollTop = messages.scrollHeight;
}

// Envoie la question au service de réponses et retourne la réponse texte.
async function ask(question) {
  const res = await fetch(`${AI_API_URL}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || `Erreur du service (${res.status})`);
  }
  return data.answer;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = input.value.trim();
  if (!question) return;

  error.classList.add("hidden");
  appendMessage(question, "user");
  input.value = "";
  input.disabled = true;
  form.querySelector("button").disabled = true;
  appendMessage("…", "bot");

  try {
    const answer = await ask(question);
    messages.lastChild.textContent = answer || "Pas de réponse.";
  } catch (err) {
    messages.lastChild.textContent = err.message;
  } finally {
    input.disabled = false;
    form.querySelector("button").disabled = false;
    input.focus();
  }
});

input.focus();
