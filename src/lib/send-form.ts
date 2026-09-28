/**
 * Submit a contact form to the site inbox via FormSubmit (https://formsubmit.co).
 * The site is static, so there is no server to send mail from; FormSubmit relays
 * the submission to the address below. The first submission triggers a one-time
 * activation email to that inbox — until "Activate" is clicked there, messages
 * are held rather than delivered.
 */
export const CONTACT_EMAIL = 'impactcollectiv0625@gmail.com';

const ENDPOINT = `https://formsubmit.co/ajax/${CONTACT_EMAIL}`;

export async function sendForm(form: HTMLFormElement, subject: string): Promise<void> {
  const data = new FormData(form);
  const payload: Record<string, string> = {
    _subject: subject,
    _template: 'table',
    _captcha: 'false',
  };
  data.forEach((value, key) => {
    payload[key] = String(value);
  });
  const res = await fetch(ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(payload),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok || body.success === 'false' || body.success === false) {
    throw new Error(body.message || `Request failed (${res.status})`);
  }
}

/** Wire a form: disable the button while sending, then show `success` (or an inline error). */
export function wireForm(form: HTMLFormElement | null, subject: string, success: HTMLElement | null) {
  if (!form) return;
  const button = form.querySelector<HTMLButtonElement>('button[type="submit"]');
  const label = button?.textContent ?? 'Send';
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (button) {
      button.disabled = true;
      button.textContent = 'Sending…';
    }
    try {
      await sendForm(form, subject);
      form.reset();
      form.hidden = true;
      if (success) success.hidden = false;
    } catch (err) {
      if (button) {
        button.disabled = false;
        button.textContent = label;
      }
      let note = form.querySelector<HTMLElement>('.form-error');
      if (!note) {
        note = document.createElement('p');
        note.className = 'form-error';
        note.style.cssText = 'font-family: var(--font-primary); font-size: 14px; color: #b00020; margin-top: 8px;';
        form.appendChild(note);
      }
      note.textContent = `Sorry, your message could not be sent. Please email ${CONTACT_EMAIL} directly.`;
      console.error(err);
    }
  });
}
