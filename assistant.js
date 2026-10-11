(() => {
  const panel = document.getElementById('assistant-panel');
  const launcher = document.getElementById('assistant-launcher');
  const close = document.getElementById('assistant-close');
  const language = document.getElementById('assistant-language');
  const launcherLabel = document.querySelector('.assistant-launcher-label');
  const launcherButton = document.getElementById('assistant-launcher');
  const form = document.getElementById('assistant-form');
  const input = document.getElementById('assistant-input');
  const messages = document.getElementById('assistant-messages');
  if (!panel || !launcher || !form || !input || !messages) return;

  const greetings = [...messages.querySelectorAll('[data-greeting-ta]')];
  const addMessage = (text, role) => {
    const bubble = document.createElement('div');
    bubble.className = `assistant-bubble ${role === 'user' ? 'assistant-user' : 'assistant-reply'}`;
    bubble.textContent = text;
    messages.append(bubble);
    messages.scrollTop = messages.scrollHeight;
    return bubble;
  };

  const setLanguage = () => {
    const tamil = language.value === 'ta';
    input.placeholder = tamil ? 'உங்கள் கேள்வியை எழுதுங்கள்...' : 'Type your question...';
    input.setAttribute('aria-label', tamil ? 'கடல் உதவியாளருக்கு செய்தி அனுப்பவும்' : 'Message the marine assistant');
    document.getElementById('assistant-title').textContent = tamil ? 'கடல் உதவியாளர்' : 'Marine assistant';
    document.getElementById('assistant-subtitle').textContent = tamil ? 'உள்ளூர் app உதவி · தமிழ் / English' : 'Local app guide · Tamil / English';
    document.getElementById('assistant-disclaimer').textContent = tamil
      ? 'உள்ளூர் உதவியாளர் · அவசர அல்லது வழிசெலுத்தல் முடிவுகளுக்கல்ல'
      : 'Local assistant · Not for emergency or navigation decisions';
    launcherLabel.textContent = tamil ? 'கடல் உதவியாளர்' : 'Marine assistant';
    launcherButton.setAttribute('aria-label', tamil ? 'தமிழ் / English கடல் உதவியாளரை திற' : 'Open Tamil and English marine assistant');
    greetings.forEach((greeting) => {
      greeting.textContent = tamil ? greeting.dataset.greetingTa : greeting.dataset.greetingEn;
    });
    document.querySelectorAll('[data-prompt-ta]').forEach((button) => {
      button.querySelector('span').textContent = tamil
        ? ({ Weather: 'வானிலை', Fleet: 'கப்பல்கள்', Harbour: 'துறைமுகம்' })[button.querySelector('span').textContent]
        : ({ வானிலை: 'Weather', கப்பல்கள்: 'Fleet', துறைமுகம்: 'Harbour' })[button.querySelector('span').textContent];
    });
  };

  const setOpen = (isOpen) => {
    panel.hidden = !isOpen;
    launcher.setAttribute('aria-expanded', String(isOpen));
    if (isOpen) input.focus();
  };
  launcher.addEventListener('click', () => setOpen(panel.hidden));
  close.addEventListener('click', () => setOpen(false));
  language.addEventListener('change', setLanguage);
  setLanguage();

  document.querySelectorAll('[data-prompt-ta]').forEach((button) => {
    button.addEventListener('click', () => {
      input.value = language.value === 'ta' ? button.dataset.promptTa : button.dataset.promptEn;
      input.focus();
    });
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const message = input.value.trim();
    if (!message) return;
    addMessage(message, 'user');
    input.value = '';
    const pending = addMessage(language.value === 'ta' ? 'பதில் தேடுகிறது…' : 'Checking local information…', 'assistant-reply assistant-pending');
    form.querySelector('button').disabled = true;
    try {
      const response = await fetch('/api/assistant', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ message, language: language.value })
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || `Request failed (${response.status})`);
      pending.textContent = result.reply;
      pending.classList.remove('assistant-pending');
    } catch (error) {
      pending.textContent = language.value === 'ta'
        ? `உதவியாளர் பதிலளிக்க முடியவில்லை: ${error.message}`
        : `The assistant could not reply: ${error.message}`;
      pending.classList.remove('assistant-pending');
      pending.classList.add('assistant-error');
    } finally {
      form.querySelector('button').disabled = false;
      messages.scrollTop = messages.scrollHeight;
      input.focus();
    }
  });
})();
