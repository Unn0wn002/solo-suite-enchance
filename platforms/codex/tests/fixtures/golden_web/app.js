document.querySelector('#signup').addEventListener('submit', async (event) => {
  event.preventDefault();
  const status = document.querySelector('#status');
  const email = document.querySelector('#email').value;
  const response = await fetch('/api/signup', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({email})
  });
  const payload = await response.json();
  status.textContent = payload.message;
});
