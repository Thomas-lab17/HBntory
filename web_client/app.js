/* Client web HBntory
   Page publique : les visiteurs posent des questions en langage naturel
   sur les produits et le stock. Pas de connexion, pas d'historique.

   État actuel : interface seule, sans backend. L'envoi d'une question
   affiche une réponse d'attente locale ; le branchement au futur service
   de réponses se fera plus tard (intégration). */

const form = document.getElementById("question-form");
const input = document.getElementById("question-input");
const messages = document.getElementById("messages");
const error = document.getElementById("error");

// Message affiché tant qu'aucun service de réponses n'est branché.
const PENDING_MESSAGE =
  "Le service de réponses n'est pas encore connecté. Cette page est pour " +
  "l'instant une interface seule.";

function appendMessage(text, who) {
  const p = document.createElement("p");
  p.className = `msg ${who}`;
  p.textContent = text;
  messages.appendChild(p);
  messages.scrollTop = messages.scrollHeight;
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const question = input.value.trim();
  if (!question) return;

  error.classList.add("hidden");
  appendMessage(question, "user");
  input.value = "";

  // Plus tard : envoyer `question` au service de réponses et afficher sa
  // réponse. Pour l'instant, réponse d'attente locale.
  appendMessage(PENDING_MESSAGE, "bot");
  input.focus();
});

input.focus();
