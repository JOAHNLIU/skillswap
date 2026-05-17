/* filepath: skillswap/static/js/chat.js
   Real-time chat via Socket.IO */

(function () {
  const chatMessages = document.getElementById('chatMessages');
  const msgInput    = document.getElementById('msgInput');
  const chatForm    = document.getElementById('chatForm');
  const exchangeId  = window.EXCHANGE_ID;
  const currentUserId = window.CURRENT_USER_ID;
  const currentUserName = window.CURRENT_USER_NAME;
  const currentUserAvatar = window.CURRENT_USER_AVATAR;

  if (!chatMessages || !exchangeId) return;

  // Scroll to bottom
  function scrollBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }
  scrollBottom();

  // Try Socket.IO connection
  let socket = null;
  try {
    socket = io({ transports: ['websocket', 'polling'] });

    socket.on('connect', function () {
      socket.emit('join_exchange', { exchange_id: exchangeId });
    });

    socket.on('new_message', function (data) {
      appendMessage(data);
      scrollBottom();
    });

    socket.on('disconnect', function () {
      console.log('Socket disconnected — fallback to HTTP');
    });
  } catch (e) {
    console.log('Socket.IO not available, using HTTP fallback');
  }

  // Form submit
  if (chatForm) {
    chatForm.addEventListener('submit', function (e) {
      const body = msgInput ? msgInput.value.trim() : '';
      if (!body) { e.preventDefault(); return; }

      if (socket && socket.connected) {
        e.preventDefault();
        socket.emit('send_message', {
          exchange_id: exchangeId,
          body: body,
          csrf_token: document.querySelector('input[name="csrf_token"]')?.value || ''
        });
        msgInput.value = '';
      }
      // else: normal form submit (HTTP fallback)
    });
  }

  function appendMessage(data) {
    const isMine = data.sender_id == currentUserId;
    const wrapper = document.createElement('div');
    wrapper.className = `d-flex mb-3 ${isMine ? 'justify-content-end' : ''}`;

    const avatar = `<img src="${data.avatar || ''}" class="rounded-circle ${isMine ? 'ms-2' : 'me-2'} flex-shrink-0"
                         width="32" height="32" style="object-fit:cover;"/>`;
    const bubble = `<div class="chat-bubble ${isMine ? 'chat-bubble-mine' : 'chat-bubble-other'}">
      <div class="small">${escHtml(data.body)}</div>
      <div class="text-muted" style="font-size:.65rem;">${data.time}</div>
    </div>`;

    wrapper.innerHTML = isMine
      ? `${bubble}${avatar}`
      : `${avatar}${bubble}`;

    chatMessages.appendChild(wrapper);
  }

  function escHtml(str) {
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;')
              .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }
})();
