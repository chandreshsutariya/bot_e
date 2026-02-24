const chatWindow = document.getElementById('chatWindow');
const chatBody = document.getElementById('chatBody');
const userInput = document.getElementById('userInput');

const sessionId = `session_${Math.random().toString(36).substring(2, 15)}`;
const username = window.userId || "User"; 

let greeted = false;

function toggleChat() {
  const isOpen = chatWindow.style.display === 'flex';
  chatWindow.style.display = isOpen ? 'none' : 'flex';

  if (!isOpen) {
    userInput.focus();
    if (!greeted) {
      appendMessage("👋 Hi! I’m Ginni. How I can help you.", 'bot');
      greeted = true;
    }
  }
}

function appendMessage(content, sender = 'bot') {
  console.log("Appending message:", content);
  
  if (typeof content !== 'string') {
    try {
      content = content?.output || JSON.stringify(content);
    } catch (err) {
      content = String(content);
    }
  }

  const messageDiv = document.createElement('div');
  messageDiv.className = `message ${sender}`;
  messageDiv.innerHTML = sender === 'bot'
    ? content.replace(/\n/g, '<br>')
    : content;

  chatBody.appendChild(messageDiv);
  chatBody.scrollTop = chatBody.scrollHeight;
}

// function sendMessage() {
//   const userMessage = userInput.value.trim();
//   if (!userMessage) return;

//   appendMessage(userMessage, 'user');
//   userInput.value = "";

//   fetch('/chat', {
//     method: 'POST',
//     headers: { "Content-Type": "application/json" },
//     body: JSON.stringify({
//       session_id: sessionId,
//       message: userMessage,
//       username: username
//     })
//   })
//     .then(res => res.json())
//     .then(data => {
//       if (data.response) {
//         console.log("Bot response:", data.response);
//         appendMessage(data.response, 'bot');
//       } else {
//         appendMessage("⚠️ I couldn't understand that. Try again.", 'bot');
//       }
//     })
//     .catch(err => {
//       console.error("Error:", err);
//       appendMessage("⚠️ Something went wrong. Try again later.", 'bot');
//     });
// }

// userInput.addEventListener("keydown", function (event) {
//   if (event.key === "Enter") {
//     event.preventDefault();  // Prevents default newline behavior
//     sendMessage();
//   }
// });
let isRequestInProgress = false;
const MAX_RETRIES = 1;
const TIMEOUT_MS = 5000; // 5 seconds

function sendMessage() {
  const userMessage = userInput.value.trim();
  if (!userMessage || isRequestInProgress) return;

  appendMessage(userMessage, 'user');
  userInput.value = "";
  userInput.disabled = true;
  isRequestInProgress = true;

  let retryAttempt = 0;
  let responseReceived = false;
  let typingDiv = null;

  const requestPayload = {
    session_id: sessionId,
    message: userMessage,
    username: username
  };

  function attemptSend() {
    console.log(`Sending request, attempt ${retryAttempt + 1}`);

    // Show typing message and keep a reference
    if (!typingDiv) {
      typingDiv = document.createElement('div');
      typingDiv.className = 'message bot';
      typingDiv.textContent = '🤖 Typing...';
      chatBody.appendChild(typingDiv);
      chatBody.scrollTop = chatBody.scrollHeight;
    }

    fetch('/chat', {
      method: 'POST',
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestPayload)
    })
      .then(res => res.json())
      .then(data => {
        if (data.response) {
          responseReceived = true;
          typingDiv.remove(); // Remove "Typing..." before appending real response
          appendMessage(data.response, 'bot');
        } else {
          responseReceived = true;
          typingDiv.textContent = "⚠️ I couldn't understand that. Try again.";
        }
      })
      .catch(err => {
        console.error("Fetch error:", err);
        typingDiv.textContent = "⚠️ Something went wrong. Try again later.";
      })
      .finally(() => {
        if (responseReceived || retryAttempt >= MAX_RETRIES) {
          isRequestInProgress = false;
          userInput.disabled = false;
          userInput.focus();
        }
      });

    // Retry if no response after timeout
    setTimeout(() => {
      if (!responseReceived && retryAttempt < MAX_RETRIES) {
        retryAttempt++;
        console.warn("No response yet. Retrying...");
        typingDiv.textContent = "⏳ Still waiting... retrying...";
        attemptSend();
      }
    }, TIMEOUT_MS);
  }

  attemptSend();
}
