(() => {
  const container = document.getElementById("chat-container");
  const messagesEl = document.getElementById("messages");
  const input = document.getElementById("message-input");
  const sendBtn = document.getElementById("send-btn");

  let conversationId = container?.dataset.conversationId || "";

  // Render any existing markdown messages on load
  document.querySelectorAll(".markdown-body[data-raw]").forEach(renderMarkdown);

  // Auto-resize textarea
  input?.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 160) + "px";
  });

  // Send on Enter (Shift+Enter = newline)
  input?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  });

  sendBtn?.addEventListener("click", handleSend);

  // Example prompt buttons
  document.querySelectorAll(".example-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (input) {
        input.value = btn.textContent.trim();
        input.dispatchEvent(new Event("input"));
        handleSend();
      }
    });
  });

  // Delete conversation buttons
  document.querySelectorAll(".convo-delete").forEach(attachDeleteHandler);

  async function ensureConversation() {
    if (conversationId) return true;
    try {
      const resp = await fetch("/conversations/new", { method: "POST", redirect: "follow" });
      const id = new URL(resp.url).pathname.split("/").pop();
      if (!id || isNaN(Number(id))) {
        console.error("Could not parse conversation id from redirect");
        return false;
      }
      conversationId = id;
      window.history.replaceState({}, "", `/conversations/${id}`);
      messagesEl.innerHTML = "";
      return true;
    } catch (err) {
      console.error("Failed to create conversation:", err);
      return false;
    }
  }

  async function handleSend() {
    const text = input?.value.trim();
    if (!text || sendBtn?.disabled) return;

    setLoading(true);

    if (!(await ensureConversation())) {
      setLoading(false);
      return;
    }

    const userText = text;
    input.value = "";
    input.style.height = "auto";

    appendMessage("user", userText);
    const typingEl = appendTyping();
    scrollToBottom();

    try {
      const resp = await fetch(`/conversations/${conversationId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: userText }),
      });

      typingEl.remove();

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        appendMessage("assistant", `Error: ${err.detail || resp.statusText}`);
      } else {
        const data = await resp.json();
        appendMessage("assistant", data.message.content, true);
        // Update sidebar title for the active item if it was "New Conversation"
        updateSidebarTitle(conversationId, userText);
      }
    } catch (err) {
      typingEl.remove();
      appendMessage("assistant", `Network error: ${err.message}`);
    } finally {
      setLoading(false);
      scrollToBottom();
    }
  }

  function appendMessage(role, content, isMarkdown = false) {
    const msgEl = document.createElement("div");
    msgEl.className = `message ${role}`;
    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    const contentEl = document.createElement("div");
    contentEl.className = isMarkdown ? "message-content markdown-body" : "message-content";

    if (isMarkdown) {
      contentEl.dataset.raw = content;
      renderMarkdown(contentEl);
    } else {
      contentEl.textContent = content;
    }

    bubble.appendChild(contentEl);
    msgEl.appendChild(bubble);
    messagesEl.appendChild(msgEl);
    return msgEl;
  }

  function appendTyping() {
    const msgEl = document.createElement("div");
    msgEl.className = "message assistant typing-indicator";
    msgEl.innerHTML = `<div class="message-bubble"><div class="message-content"><div class="dots"><span></span><span></span><span></span></div></div></div>`;
    messagesEl.appendChild(msgEl);
    return msgEl;
  }

  function renderMarkdown(el) {
    const raw = el.dataset.raw || el.textContent;
    if (typeof marked !== "undefined") {
      el.innerHTML = marked.parse(raw, { breaks: true, gfm: true });
    } else {
      el.textContent = raw;
    }
  }

  function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function setLoading(loading) {
    if (sendBtn) sendBtn.disabled = loading;
    if (input) input.disabled = loading;
  }

  function updateSidebarTitle(id, firstMessage) {
    const link = document.querySelector(`.convo-item[data-id="${id}"] .convo-title`);
    if (link && link.textContent.trim() === "New Conversation") {
      link.textContent = firstMessage.slice(0, 60) + (firstMessage.length > 60 ? "…" : "");
    }
  }

  function attachDeleteHandler(btn) {
    btn.addEventListener("click", async (e) => {
      e.preventDefault();
      e.stopPropagation();
      const id = btn.dataset.id;
      try {
        await fetch(`/conversations/${id}`, { method: "DELETE" });
        window.location.href = "/";
      } catch (err) {
        console.error("Delete failed:", err);
      }
    });
  }
})();
