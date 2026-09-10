// ShopShare web app — a functional, hash-routed single-page client for the
// same FastAPI backend the Flutter app talks to. Vanilla JS, no build step,
// consistent with the rest of this repo's "no framework" approach.

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

// Change this once your backend is deployed publicly. Until then this
// assumes `uvicorn main:app --reload` running locally on its default port.
const API_BASE = window.SHOPSHARE_API_BASE || 'http://localhost:8000';

// ---------------------------------------------------------------------------
// API client — thin fetch wrapper. Cookies are httponly, so the browser
// manages them automatically via `credentials: 'include'`; unlike the
// Flutter client, there's no manual Set-Cookie parsing needed here.
// ---------------------------------------------------------------------------

async function request(method, path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    credentials: 'include',
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : {},
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  let data = null;
  const text = await res.text();
  if (text) {
    try { data = JSON.parse(text); } catch (_) { data = text; }
  }
  return { ok: res.ok, status: res.status, data };
}

const api = {
  // Auth
  register: (body) => request('POST', '/login/register', body),
  login: (body) => request('POST', '/login/login', body),
  me: () => request('GET', '/login/me'),
  logout: () => request('POST', '/login/logout', {}),
  updateProfile: (body) => request('PATCH', '/login/me', body),
  deleteProfile: () => request('DELETE', '/login/me'),

  // Rides
  listRides: (params = {}) => {
    const qs = new URLSearchParams();
    if (params.pickup) qs.set('pickup', params.pickup);
    if (params.destination) qs.set('destination', params.destination);
    if (params.date) qs.set('date', params.date);
    const q = qs.toString();
    return request('GET', `/rides/${q ? `?${q}` : ''}`);
  },
  getRide: (id) => request('GET', `/rides/${id}`),
  createRide: (body) => request('POST', '/rides/', body),
  updateRide: (id, body) => request('PATCH', `/rides/${id}`, body),
  deleteRide: (id) => request('DELETE', `/rides/${id}`),
  joinRide: (id) => request('POST', `/rides/${id}/join`, {}),

  // Ride requests
  myRideRequests: () => request('GET', '/rides/me/requests'),
  rideRequests: (rideId) => request('GET', `/rides/${rideId}/requests`),
  acceptRequest: (rideId, reqId) => request('POST', `/rides/${rideId}/requests/${reqId}/accept`, {}),
  rejectRequest: (rideId, reqId) => request('POST', `/rides/${rideId}/requests/${reqId}/reject`, {}),

  // Conversations
  listConversations: () => request('GET', '/conversations/'),
  listMessages: (conversationId) => request('GET', `/conversations/${conversationId}`),
  sendMessage: (conversationId, body) => request('POST', `/conversations/${conversationId}/messages`, body),

  // Notifications
  listNotifications: () => request('GET', '/notifications/'),
  markRead: (id) => request('POST', `/notifications/${id}/read`, {}),

  // Ratings
  submitRating: (rideId, body) => request('POST', `/rides/${rideId}/ratings`, body),
  getRatingsForUser: (userId) => request('GET', `/users/${userId}/ratings`),

  // Trips
  myTrips: () => request('GET', '/trips/'),

  // Payments
  createCheckoutSession: (rideRequestId) => request('POST', '/payments/checkout', { ride_request_id: rideRequestId }),
  getPaymentStatus: (rideRequestId) => request('GET', `/payments/ride-requests/${rideRequestId}`),

  // Driver verification
  startDriverVerification: (vehicle) => request('POST', '/driver-verification/start', vehicle),
  getDriverVerificationStatus: () => request('GET', '/driver-verification/status'),
};

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

const state = { me: null };

// Every async view/loader function bumps this at the start (before its
// first await) and checks it after each await before writing to the DOM.
// Without this, navigating away while a fetch is still in flight lets that
// stale response clobber whatever view the user has since navigated to —
// e.g. leaving the ride-detail page mid-load, then landing on Trips, only
// for the ride-detail fetch to resolve late and overwrite the Trips page.
let renderToken = 0;
function beginRender() { return ++renderToken; }
function isStaleRender(token) { return token !== renderToken; }

function escapeHtml(str) {
  return String(str ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

function formatDateTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
  });
}

function money(n) {
  return `$${Number(n).toFixed(2)}`;
}

function errorMessage(data, fallback = 'Something went wrong') {
  if (!data) return fallback;
  if (typeof data === 'string') return data;
  const detail = data.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail[0] && detail[0].msg) return detail[0].msg;
  return fallback;
}

let toastTimer = null;
function toast(message, kind = 'info') {
  const el = document.getElementById('toast');
  el.textContent = message;
  el.className = `toast toast--${kind} is-visible`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('is-visible'), 3200);
}

function openModal(innerHtml) {
  const root = document.getElementById('modalRoot');
  root.innerHTML = `
    <div class="modal-backdrop" id="modalBackdrop">
      <div class="modal-card" role="dialog" aria-modal="true">${innerHtml}</div>
    </div>`;
  root.querySelector('#modalBackdrop').addEventListener('click', (e) => {
    if (e.target.id === 'modalBackdrop') closeModal();
  });
}
function closeModal() {
  document.getElementById('modalRoot').innerHTML = '';
}

// ---------------------------------------------------------------------------
// Router
// ---------------------------------------------------------------------------

const PUBLIC_ROUTES = new Set(['/login', '/register', '/terms', '/privacy']);

const routes = [
  { pattern: '/login', view: viewLogin },
  { pattern: '/register', view: viewRegister },
  { pattern: '/terms', view: viewTerms },
  { pattern: '/privacy', view: viewPrivacy },
  { pattern: '/', view: viewRides },
  { pattern: '/rides', view: viewRides },
  { pattern: '/rides/new', view: viewCreateRide },
  { pattern: '/rides/:id/requests', view: viewRideRequests },
  { pattern: '/rides/:id', view: viewRideDetail },
  { pattern: '/trips', view: viewTrips },
  { pattern: '/conversations', view: viewConversations },
  { pattern: '/conversations/:id', view: viewMessages },
  { pattern: '/notifications', view: viewNotifications },
  { pattern: '/profile', view: viewProfile },
  { pattern: '/profile/edit', view: viewEditProfile },
  { pattern: '/host', view: viewDriverVerification },
  { pattern: '/pay/:id', view: viewPayment },
];

function matchRoute(path) {
  for (const route of routes) {
    const patternParts = route.pattern.split('/').filter(Boolean);
    const pathParts = path.split('/').filter(Boolean);
    if (patternParts.length !== pathParts.length) continue;
    const params = {};
    let matched = true;
    for (let i = 0; i < patternParts.length; i++) {
      if (patternParts[i].startsWith(':')) {
        params[patternParts[i].slice(1)] = decodeURIComponent(pathParts[i]);
      } else if (patternParts[i] !== pathParts[i]) {
        matched = false;
        break;
      }
    }
    if (matched) return { view: route.view, params };
  }
  return null;
}

function currentPath() {
  const hash = window.location.hash.replace(/^#/, '');
  return hash || '/';
}

function navigate(path) {
  window.location.hash = path;
}

async function router() {
  const path = currentPath();
  closeModal();

  if (!PUBLIC_ROUTES.has(path)) {
    const res = await api.me();
    if (res.ok) {
      state.me = res.data;
    } else {
      state.me = null;
      if (path !== '/login') {
        navigate('/login');
        return;
      }
    }
  } else if (path === '/login' || path === '/register') {
    // If already logged in, skip straight past the auth screens.
    const res = await api.me();
    if (res.ok) {
      state.me = res.data;
      navigate('/');
      return;
    }
  }

  renderShell();
  const match = matchRoute(path);
  const view = document.getElementById('view');
  if (!match) {
    view.innerHTML = `<div class="empty-state"><h2>Page not found</h2><a href="#/">Go home</a></div>`;
    return;
  }
  try {
    await match.view(match.params);
  } catch (err) {
    console.error(err);
    view.innerHTML = `<div class="empty-state"><h2>Something broke</h2><p>${escapeHtml(err.message || String(err))}</p></div>`;
  }
}

window.addEventListener('hashchange', router);
window.addEventListener('DOMContentLoaded', router);

// ---------------------------------------------------------------------------
// Shell (top nav)
// ---------------------------------------------------------------------------

function renderShell() {
  const shell = document.getElementById('shell');
  const path = currentPath();
  if (PUBLIC_ROUTES.has(path)) {
    shell.innerHTML = '';
    shell.classList.add('shell--hidden');
    return;
  }
  shell.classList.remove('shell--hidden');

  const tabs = [
    { href: '#/rides', label: 'Rides', match: (p) => p === '/' || p.startsWith('/rides') },
    { href: '#/trips', label: 'Trips', match: (p) => p.startsWith('/trips') },
    { href: '#/conversations', label: 'Messages', match: (p) => p.startsWith('/conversations') },
    { href: '#/notifications', label: 'Alerts', match: (p) => p.startsWith('/notifications') },
    { href: '#/profile', label: 'Profile', match: (p) => p.startsWith('/profile') || p === '/host' },
  ];

  shell.innerHTML = `
    <div class="appnav">
      <a href="#/rides" class="appnav__brand">
        <img src="../assets/logos/mark-only-green.svg" width="26" height="26" alt="" />
        <span>shop<span class="accent">share</span></span>
      </a>
      <nav class="appnav__tabs">
        ${tabs.map((t) => `<a href="${t.href}" class="${t.match(path) ? 'is-active' : ''}">${t.label}</a>`).join('')}
      </nav>
      <button class="btn btn--primary btn--sm" id="postRideBtn">Post a ride</button>
    </div>`;
  shell.querySelector('#postRideBtn').addEventListener('click', () => navigate('/rides/new'));
}

// ---------------------------------------------------------------------------
// Views: Auth
// ---------------------------------------------------------------------------

function viewLogin() {
  document.getElementById('view').innerHTML = `
    <div class="auth-shell">
      <div class="auth-card">
        <img src="../assets/logos/mark-only-green.svg" width="40" height="40" alt="" />
        <h1>Welcome back</h1>
        <p class="muted">Log in to find or post a ride.</p>
        <form id="loginForm">
          <label>Email<input type="email" name="email" required autocomplete="email" /></label>
          <label>Password<input type="password" name="password" required autocomplete="current-password" /></label>
          <p class="form-error" id="loginError"></p>
          <button class="btn btn--primary" type="submit" style="width:100%">Log In</button>
        </form>
        <p class="muted center">No account? <a href="#/register">Create one</a></p>
      </div>
    </div>`;

  document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = new FormData(e.target);
    const res = await api.login({ email: form.get('email'), password: form.get('password') });
    if (res.ok) {
      navigate('/rides');
    } else {
      document.getElementById('loginError').textContent = errorMessage(res.data, 'Login failed');
    }
  });
}

function viewRegister() {
  document.getElementById('view').innerHTML = `
    <div class="auth-shell">
      <div class="auth-card auth-card--wide">
        <img src="../assets/logos/mark-only-green.svg" width="40" height="40" alt="" />
        <h1>Create your account</h1>
        <p class="muted">Split rides to the grocery store with other students.</p>
        <form id="registerForm">
          <div class="grid-2">
            <label>Email<input type="email" name="email" required /></label>
            <label>Username (min 6 chars)<input type="text" name="username" minlength="6" required /></label>
          </div>
          <label>Password (min 6 chars)<input type="password" name="password" minlength="6" required /></label>
          <div class="grid-2">
            <label>First name<input type="text" name="first_name" /></label>
            <label>Last name<input type="text" name="last_name" /></label>
          </div>
          <div class="grid-2">
            <label>University<input type="text" name="university" placeholder="e.g. UBC Okanagan" /></label>
            <label>Phone number<input type="tel" name="phone_number" /></label>
          </div>
          <label class="checkbox-row">
            <input type="checkbox" name="terms_accepted" required />
            <span>I agree to the <a href="#/terms" target="_blank">Terms of Service</a> and <a href="#/privacy" target="_blank">Privacy Policy</a></span>
          </label>
          <p class="form-error" id="registerError"></p>
          <button class="btn btn--primary" type="submit" style="width:100%">Create Account</button>
        </form>
        <p class="muted center">Already have an account? <a href="#/login">Log in</a></p>
      </div>
    </div>`;

  document.getElementById('registerForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = new FormData(e.target);
    const body = {
      email: form.get('email'),
      username: form.get('username'),
      password: form.get('password'),
      first_name: form.get('first_name') || '',
      last_name: form.get('last_name') || '',
      university: form.get('university') || '',
      phone_number: form.get('phone_number') || '',
      terms_accepted: form.get('terms_accepted') === 'on',
    };
    const res = await api.register(body);
    if (res.ok) {
      toast('Account created — log in to continue', 'success');
      navigate('/login');
    } else {
      document.getElementById('registerError').textContent = errorMessage(res.data, 'Registration failed');
    }
  });
}

// ---------------------------------------------------------------------------
// Views: Rides
// ---------------------------------------------------------------------------

async function viewRides() {
  const view = document.getElementById('view');
  view.innerHTML = `
    <div class="page">
      <div class="page__header">
        <h1>Find a ride</h1>
        <button class="btn btn--primary" id="newRideBtn">Post a ride</button>
      </div>
      <form class="search-bar" id="searchForm">
        <input type="text" name="pickup" placeholder="Pickup location" />
        <input type="text" name="destination" placeholder="Destination" />
        <input type="date" name="date" />
        <button class="btn btn--ghost" type="submit">Search</button>
        <button class="btn btn--ghost" type="button" id="clearSearch">Clear</button>
      </form>
      <div id="ridesList" class="card-list"><p class="muted">Loading rides…</p></div>
    </div>`;

  document.getElementById('newRideBtn').addEventListener('click', () => navigate('/rides/new'));
  document.getElementById('searchForm').addEventListener('submit', (e) => {
    e.preventDefault();
    const form = new FormData(e.target);
    loadRides({
      pickup: form.get('pickup') || undefined,
      destination: form.get('destination') || undefined,
      date: form.get('date') || undefined,
    });
  });
  document.getElementById('clearSearch').addEventListener('click', () => {
    document.getElementById('searchForm').reset();
    loadRides({});
  });

  await loadRides({});
}

async function loadRides(params) {
  const myToken = beginRender();
  const list = document.getElementById('ridesList');
  const res = await api.listRides(params);
  if (isStaleRender(myToken)) return;
  if (!res.ok) {
    list.innerHTML = `<p class="muted">Could not load rides.</p>`;
    return;
  }
  const rides = res.data;
  if (!rides.length) {
    list.innerHTML = `<div class="empty-state"><h3>No rides found</h3><p class="muted">Try different filters, or be the first to post one.</p></div>`;
    return;
  }
  list.innerHTML = rides.map((r) => `
    <a class="card ride-card" href="#/rides/${r.id}">
      <div>
        <h3>${escapeHtml(r.pickup_location)} → ${escapeHtml(r.destination)}</h3>
        <p class="muted">${formatDateTime(r.departure_time)}</p>
        <p class="muted">Host: ${escapeHtml(r.host_username || 'unknown')} · ${r.available_seats} seat(s) · ${money(r.price_per_person)}</p>
      </div>
      <span class="chevron">›</span>
    </a>`).join('');
}

function viewCreateRide() {
  document.getElementById('view').innerHTML = `
    <div class="page page--narrow">
      <div class="page__header"><h1>Post a ride</h1></div>
      <form id="createRideForm" class="form-card">
        <label>Pickup location<input type="text" name="pickup_location" minlength="2" required /></label>
        <label>Destination store<input type="text" name="destination" minlength="2" required /></label>
        <label>Departure date &amp; time<input type="datetime-local" name="departure_time" required /></label>
        <div class="grid-2">
          <label>Available seats<input type="number" name="available_seats" min="1" value="3" required /></label>
          <label>Price per person ($)<input type="number" name="price_per_person" min="0" step="0.01" value="5.00" required /></label>
        </div>
        <p class="form-error" id="createRideError"></p>
        <button class="btn btn--primary" type="submit">Post Ride</button>
      </form>
    </div>`;

  document.getElementById('createRideForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = new FormData(e.target);
    const departureLocal = form.get('departure_time');
    const body = {
      pickup_location: form.get('pickup_location'),
      destination: form.get('destination'),
      departure_time: new Date(departureLocal).toISOString(),
      available_seats: Number(form.get('available_seats')),
      price_per_person: Number(form.get('price_per_person')),
    };
    const res = await api.createRide(body);
    if (res.ok) {
      toast('Ride posted!', 'success');
      navigate(`/rides/${res.data.id}`);
    } else {
      document.getElementById('createRideError').textContent = errorMessage(res.data, 'Could not post ride');
    }
  });
}

async function viewRideDetail(params) {
  const myToken = beginRender();
  const view = document.getElementById('view');
  view.innerHTML = `<div class="page"><p class="muted">Loading ride…</p></div>`;

  const rideId = Number(params.id);
  const [rideRes, myReqsRes] = await Promise.all([api.getRide(rideId), api.myRideRequests()]);
  if (isStaleRender(myToken)) return;
  if (!rideRes.ok) {
    view.innerHTML = `<div class="page"><div class="empty-state"><h2>Ride not found</h2><a href="#/rides">Back to rides</a></div></div>`;
    return;
  }
  const ride = rideRes.data;
  const isHost = state.me && ride.host_id === state.me.id;
  const myRequest = myReqsRes.ok ? myReqsRes.data.find((r) => r.ride && r.ride.id === rideId) : null;

  view.innerHTML = `
    <div class="page page--narrow">
      <a href="#/rides" class="back-link">‹ Back to rides</a>
      <h1>${escapeHtml(ride.pickup_location)} → ${escapeHtml(ride.destination)}</h1>
      <p class="muted">${formatDateTime(ride.departure_time)}</p>
      <div class="card info-card">
        <div class="info-row"><span>Host</span><strong>${escapeHtml(ride.host_username || 'Unknown')}</strong></div>
        <div class="info-row"><span>Seats available</span><strong>${ride.available_seats}</strong></div>
        <div class="info-row"><span>Price per person</span><strong>${money(ride.price_per_person)}</strong></div>
        <div class="info-row"><span>Status</span><strong>${escapeHtml(ride.status)}</strong></div>
      </div>
      <div id="rideActions"></div>
    </div>`;

  const actions = document.getElementById('rideActions');

  if (isHost) {
    actions.innerHTML = `
      <span class="chip chip--brand">You are hosting this ride</span>
      <div class="action-stack">
        <button class="btn btn--ghost" id="manageRequestsBtn">Manage Requests</button>
        ${ride.status === 'open' ? `
          <button class="btn btn--ghost" id="completeBtn">Mark Completed</button>
          <button class="btn btn--ghost btn--warn" id="cancelBtn">Cancel Ride</button>` : ''}
        <button class="btn btn--ghost btn--danger" id="deleteBtn">Delete Ride</button>
      </div>`;
    document.getElementById('manageRequestsBtn').addEventListener('click', () => navigate(`/rides/${rideId}/requests`));
    document.getElementById('completeBtn')?.addEventListener('click', () => setRideStatus(rideId, 'completed'));
    document.getElementById('cancelBtn')?.addEventListener('click', () => setRideStatus(rideId, 'cancelled'));
    document.getElementById('deleteBtn').addEventListener('click', async () => {
      if (!confirm('Delete this ride? This cancels it for everyone.')) return;
      const res = await api.deleteRide(rideId);
      if (res.ok) { toast('Ride deleted'); navigate('/rides'); }
      else toast(errorMessage(res.data, 'Could not delete ride'), 'error');
    });
  } else if (myRequest?.status === 'accepted') {
    actions.innerHTML = `
      <span class="chip chip--success">You're confirmed on this ride</span>
      <div class="action-stack">
        <a class="btn btn--primary" href="#/pay/${myRequest.id}">Pay Host</a>
        <button class="btn btn--ghost" id="messageBtn">Message Host</button>
      </div>`;
    document.getElementById('messageBtn').addEventListener('click', () => openConversationForRide(rideId));
  } else if (myRequest?.status === 'pending') {
    actions.innerHTML = `<span class="chip chip--pending">Request pending host approval</span>`;
  } else if (myRequest?.status === 'rejected') {
    actions.innerHTML = `
      <span class="chip chip--danger">Your request was declined</span>
      <div class="action-stack"><button class="btn btn--primary" id="joinBtn">Request Again</button></div>`;
    document.getElementById('joinBtn').addEventListener('click', () => joinRide(rideId));
  } else {
    actions.innerHTML = `<div class="action-stack"><button class="btn btn--primary" id="joinBtn">Join Ride</button></div>`;
    document.getElementById('joinBtn').addEventListener('click', () => joinRide(rideId));
  }
}

async function joinRide(rideId) {
  const res = await api.joinRide(rideId);
  if (res.ok) {
    toast('Request sent to host', 'success');
    viewRideDetail({ id: String(rideId) });
  } else {
    toast(errorMessage(res.data, 'Could not join ride'), 'error');
  }
}

async function setRideStatus(rideId, status) {
  const res = await api.updateRide(rideId, { status });
  if (res.ok) { toast('Ride updated', 'success'); viewRideDetail({ id: String(rideId) }); }
  else toast(errorMessage(res.data, 'Could not update ride'), 'error');
}

async function openConversationForRide(rideId) {
  const res = await api.listConversations();
  if (!res.ok) return;
  const match = res.data.find((c) => c.ride_id === rideId);
  if (match) navigate(`/conversations/${match.id}`);
}

// ---------------------------------------------------------------------------
// Views: Ride requests (host)
// ---------------------------------------------------------------------------

async function viewRideRequests(params) {
  const view = document.getElementById('view');
  const rideId = Number(params.id);
  view.innerHTML = `
    <div class="page page--narrow">
      <a href="#/rides/${rideId}" class="back-link">‹ Back to ride</a>
      <h1>Ride Requests</h1>
      <div id="requestsList" class="card-list"><p class="muted">Loading…</p></div>
    </div>`;
  await loadRideRequests(rideId);
}

async function loadRideRequests(rideId) {
  const myToken = beginRender();
  const list = document.getElementById('requestsList');
  const res = await api.rideRequests(rideId);
  if (isStaleRender(myToken)) return;
  if (!res.ok) {
    list.innerHTML = `<p class="muted">${escapeHtml(errorMessage(res.data, 'Could not load requests'))}</p>`;
    return;
  }
  if (!res.data.length) {
    list.innerHTML = `<div class="empty-state"><p class="muted">No one has requested this ride yet.</p></div>`;
    return;
  }
  list.innerHTML = res.data.map((r) => `
    <div class="card request-card">
      <div class="avatar-circle">#${r.passenger_id}</div>
      <div class="request-card__body">
        <strong>Passenger #${r.passenger_id}</strong>
        <span class="chip chip--${r.status === 'accepted' ? 'success' : r.status === 'rejected' ? 'danger' : 'pending'}">${escapeHtml(r.status)}</span>
      </div>
      ${r.status === 'pending' ? `
        <div class="request-card__actions">
          <button class="icon-btn icon-btn--accept" data-accept="${r.id}" title="Accept">✓</button>
          <button class="icon-btn icon-btn--reject" data-reject="${r.id}" title="Reject">✕</button>
        </div>` : ''}
    </div>`).join('');

  list.querySelectorAll('[data-accept]').forEach((btn) => btn.addEventListener('click', async () => {
    const res2 = await api.acceptRequest(rideId, Number(btn.dataset.accept));
    if (res2.ok) { toast('Accepted', 'success'); loadRideRequests(rideId); }
    else toast(errorMessage(res2.data, 'Could not accept'), 'error');
  }));
  list.querySelectorAll('[data-reject]').forEach((btn) => btn.addEventListener('click', async () => {
    const res2 = await api.rejectRequest(rideId, Number(btn.dataset.reject));
    if (res2.ok) { toast('Declined'); loadRideRequests(rideId); }
    else toast(errorMessage(res2.data, 'Could not reject'), 'error');
  }));
}

// ---------------------------------------------------------------------------
// Views: Trips
// ---------------------------------------------------------------------------

async function viewTrips() {
  const myToken = beginRender();
  const view = document.getElementById('view');
  view.innerHTML = `
    <div class="page">
      <div class="page__header"><h1>My Trips</h1></div>
      <div class="tabs" id="tripTabs">
        <button class="tab is-active" data-tab="open">Active</button>
        <button class="tab" data-tab="completed">Completed</button>
        <button class="tab" data-tab="cancelled">Cancelled</button>
      </div>
      <div id="tripsList" class="card-list"><p class="muted">Loading…</p></div>
    </div>`;

  // Wire up the tabs' click listeners *before* awaiting the trips fetch,
  // not after — attaching them only once data arrives leaves a window
  // where the tab buttons are visible but inert, silently dropping a
  // click that lands before the fetch resolves. `trips`/`activeStatus`
  // are captured by reference, so render() always uses whatever's
  // current at click time.
  const tabsEl = document.getElementById('tripTabs');
  const listEl = document.getElementById('tripsList');
  let trips = [];
  let activeStatus = 'open';

  function render(status) {
    activeStatus = status;
    const items = trips.filter((t) => t.ride_status === status);
    if (!items.length) {
      listEl.innerHTML = `<div class="empty-state"><p class="muted">No ${status === 'open' ? 'active' : status} trips.</p></div>`;
      return;
    }
    listEl.innerHTML = items.map((t) => `
      <div class="card trip-card">
        <div class="trip-card__top">
          <span class="chip chip--${t.role === 'host' ? 'brand' : 'success'}">${t.role === 'host' ? 'Hosting' : 'Riding'}</span>
          ${t.role === 'passenger' && t.request_status ? `<span class="muted">${escapeHtml(t.request_status)}</span>` : ''}
        </div>
        <h3>${escapeHtml(t.pickup_location)} → ${escapeHtml(t.destination)}</h3>
        <p class="muted">${formatDateTime(t.departure_time)} · ${money(t.price_per_person)} per person</p>
        ${t.ride_status === 'completed' ? `<button class="btn btn--ghost" data-rate='${escapeHtml(JSON.stringify(t))}'>Rate</button>` : ''}
      </div>`).join('');

    listEl.querySelectorAll('[data-rate]').forEach((btn) => btn.addEventListener('click', () => {
      openRatingFlow(JSON.parse(btn.dataset.rate));
    }));
  }

  tabsEl.querySelectorAll('.tab').forEach((tab) => tab.addEventListener('click', () => {
    tabsEl.querySelectorAll('.tab').forEach((t) => t.classList.remove('is-active'));
    tab.classList.add('is-active');
    render(tab.dataset.tab);
  }));

  const res = await api.myTrips();
  if (isStaleRender(myToken)) return;
  trips = res.ok ? res.data : [];
  render(activeStatus);
}

async function openRatingFlow(trip) {
  if (trip.role === 'passenger') {
    openRatingDialog(trip.ride_id, trip.host_id, 'your host');
    return;
  }
  const res = await api.rideRequests(trip.ride_id);
  if (!res.ok) return;
  const accepted = res.data.filter((r) => r.status === 'accepted');
  if (!accepted.length) {
    toast('No confirmed passengers to rate yet.');
    return;
  }
  openModal(`
    <h3>Who are you rating?</h3>
    <div class="modal-list">
      ${accepted.map((r) => `<button class="modal-list__item" data-passenger="${r.passenger_id}">Passenger #${r.passenger_id}</button>`).join('')}
    </div>
    <button class="btn btn--ghost" id="modalCancel">Cancel</button>`);
  document.getElementById('modalCancel').addEventListener('click', closeModal);
  document.querySelectorAll('[data-passenger]').forEach((btn) => btn.addEventListener('click', () => {
    openRatingDialog(trip.ride_id, Number(btn.dataset.passenger), `passenger #${btn.dataset.passenger}`);
  }));
}

function openRatingDialog(rideId, toUserId, label) {
  let score = 5;
  const render = () => `
    <h3>Rate ${escapeHtml(label)}</h3>
    <div class="star-row">
      ${[1, 2, 3, 4, 5].map((n) => `<button class="star ${n <= score ? 'is-filled' : ''}" data-star="${n}">★</button>`).join('')}
    </div>
    <textarea id="ratingComment" placeholder="Comment (optional)" rows="3"></textarea>
    <div class="modal-actions">
      <button class="btn btn--ghost" id="modalCancel">Cancel</button>
      <button class="btn btn--primary" id="modalSubmit">Submit</button>
    </div>`;
  openModal(render());

  function wire() {
    document.querySelectorAll('[data-star]').forEach((btn) => btn.addEventListener('click', () => {
      score = Number(btn.dataset.star);
      const comment = document.getElementById('ratingComment').value;
      openModal(render());
      document.getElementById('ratingComment').value = comment;
      wire();
    }));
    document.getElementById('modalCancel').addEventListener('click', closeModal);
    document.getElementById('modalSubmit').addEventListener('click', async () => {
      const comment = document.getElementById('ratingComment').value.trim();
      const res = await api.submitRating(rideId, { to_user_id: toUserId, rating_score: score, comment: comment || null });
      closeModal();
      toast(res.ok ? 'Thanks for rating!' : errorMessage(res.data, 'Could not submit rating'), res.ok ? 'success' : 'error');
    });
  }
  wire();
}

// ---------------------------------------------------------------------------
// Views: Conversations / Messages
// ---------------------------------------------------------------------------

async function viewConversations() {
  const myToken = beginRender();
  const view = document.getElementById('view');
  view.innerHTML = `<div class="page"><div class="page__header"><h1>Messages</h1></div><div id="convoList" class="card-list"><p class="muted">Loading…</p></div></div>`;
  const res = await api.listConversations();
  if (isStaleRender(myToken)) return;
  const list = document.getElementById('convoList');
  if (!res.ok || !res.data.length) {
    list.innerHTML = `<div class="empty-state"><p class="muted">No conversations yet.</p></div>`;
    return;
  }
  list.innerHTML = res.data.map((c) => `
    <a class="card ride-card" href="#/conversations/${c.id}">
      <div><h3>Ride #${c.ride_id}</h3><p class="muted">Tap to view messages</p></div>
      <span class="chevron">›</span>
    </a>`).join('');
}

async function viewMessages(params) {
  const myToken = beginRender();
  const view = document.getElementById('view');
  const conversationId = Number(params.id);
  view.innerHTML = `
    <div class="page page--narrow page--chat">
      <a href="#/conversations" class="back-link">‹ Back to messages</a>
      <div id="messagesList" class="messages-list"><p class="muted">Loading…</p></div>
      <form id="messageForm" class="message-form">
        <input type="text" name="content" placeholder="Message…" autocomplete="off" required />
        <button class="btn btn--primary" type="submit">Send</button>
      </form>
    </div>`;

  async function load() {
    const res = await api.listMessages(conversationId);
    if (isStaleRender(myToken)) return;
    const list = document.getElementById('messagesList');
    if (!res.ok) {
      list.innerHTML = `<p class="muted">${escapeHtml(errorMessage(res.data, 'Could not load messages'))}</p>`;
      return;
    }
    list.innerHTML = res.data.map((m) => `
      <div class="bubble ${state.me && m.sender_id === state.me.id ? 'bubble--mine' : ''}">${escapeHtml(m.content)}</div>
    `).join('') || `<p class="muted">Say hello 👋</p>`;
    list.scrollTop = list.scrollHeight;
  }

  document.getElementById('messageForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = new FormData(e.target);
    const content = form.get('content').trim();
    if (!content) return;
    e.target.reset();
    const res = await api.sendMessage(conversationId, { content });
    if (res.ok) load();
    else toast(errorMessage(res.data, 'Message failed to send'), 'error');
  });

  await load();
}

// ---------------------------------------------------------------------------
// Views: Notifications
// ---------------------------------------------------------------------------

async function viewNotifications() {
  const view = document.getElementById('view');
  view.innerHTML = `<div class="page"><div class="page__header"><h1>Notifications</h1></div><div id="notifList" class="card-list"><p class="muted">Loading…</p></div></div>`;
  await loadNotifications();
}

async function loadNotifications() {
  const myToken = beginRender();
  const res = await api.listNotifications();
  if (isStaleRender(myToken)) return;
  const list = document.getElementById('notifList');
  if (!res.ok || !res.data.length) {
    list.innerHTML = `<div class="empty-state"><p class="muted">No notifications yet.</p></div>`;
    return;
  }
  list.innerHTML = res.data.map((n) => `
    <div class="card notif-card ${n.is_read ? '' : 'notif-card--unread'}">
      <p>${escapeHtml(n.message)}</p>
      ${n.is_read ? '' : `<button class="btn btn--ghost btn--sm" data-mark="${n.id}">Mark read</button>`}
    </div>`).join('');
  list.querySelectorAll('[data-mark]').forEach((btn) => btn.addEventListener('click', async () => {
    await api.markRead(Number(btn.dataset.mark));
    loadNotifications();
  }));
}

// ---------------------------------------------------------------------------
// Views: Profile
// ---------------------------------------------------------------------------

async function viewProfile() {
  const myToken = beginRender();
  const view = document.getElementById('view');
  const res = await api.me();
  if (isStaleRender(myToken)) return;
  if (!res.ok) { navigate('/login'); return; }
  const me = res.data;
  state.me = me;
  const initials = (me.username || '?').slice(0, 1).toUpperCase();

  view.innerHTML = `
    <div class="page page--narrow">
      <div class="profile-header">
        <div class="avatar-circle avatar-circle--lg">${escapeHtml(initials)}</div>
        <h1>${escapeHtml(me.username)}</h1>
        ${me.university ? `<p class="muted">${escapeHtml(me.university)}</p>` : ''}
        ${me.rating != null ? `<p class="muted">★ ${Number(me.rating).toFixed(1)}</p>` : ''}
      </div>
      <div class="card info-card">
        <div class="info-row"><span>Email</span><strong>${escapeHtml(me.email)}</strong></div>
        <div class="info-row"><span>Name</span><strong>${escapeHtml(`${me.first_name || ''} ${me.last_name || ''}`.trim() || '—')}</strong></div>
        <div class="info-row"><span>Phone</span><strong>${escapeHtml(me.phone_number || '—')}</strong></div>
      </div>
      <div class="menu-list">
        <a class="card menu-item" href="#/profile/edit">Edit Profile <span class="chevron">›</span></a>
        <a class="card menu-item" href="#/host">Become a Host <span class="chevron">›</span></a>
        <a class="card menu-item" href="#/terms" target="_blank">Terms of Service <span class="chevron">›</span></a>
        <a class="card menu-item" href="#/privacy" target="_blank">Privacy Policy <span class="chevron">›</span></a>
      </div>
      <div class="action-stack">
        <button class="btn btn--ghost" id="logoutBtn">Log Out</button>
        <button class="btn btn--ghost btn--danger" id="deleteAccountBtn">Delete Account</button>
      </div>
    </div>`;

  document.getElementById('logoutBtn').addEventListener('click', async () => {
    await api.logout();
    state.me = null;
    navigate('/login');
  });
  document.getElementById('deleteAccountBtn').addEventListener('click', async () => {
    if (!confirm('This permanently deletes your profile, rides, requests, messages, and ratings. Continue?')) return;
    const res2 = await api.deleteProfile();
    if (res2.ok) { state.me = null; navigate('/login'); }
    else toast(errorMessage(res2.data, 'Could not delete account'), 'error');
  });
}

async function viewEditProfile() {
  const myToken = beginRender();
  const view = document.getElementById('view');
  const res = await api.me();
  if (isStaleRender(myToken)) return;
  if (!res.ok) { navigate('/login'); return; }
  const me = res.data;

  view.innerHTML = `
    <div class="page page--narrow">
      <a href="#/profile" class="back-link">‹ Back to profile</a>
      <h1>Edit Profile</h1>
      <form id="editForm" class="form-card">
        <label>Username<input type="text" name="username" minlength="6" value="${escapeHtml(me.username)}" required /></label>
        <div class="grid-2">
          <label>First name<input type="text" name="first_name" value="${escapeHtml(me.first_name || '')}" /></label>
          <label>Last name<input type="text" name="last_name" value="${escapeHtml(me.last_name || '')}" /></label>
        </div>
        <label>University<input type="text" name="university" value="${escapeHtml(me.university || '')}" /></label>
        <label>Phone number<input type="tel" name="phone_number" value="${escapeHtml(me.phone_number || '')}" /></label>
        <label>New password (leave blank to keep current)<input type="password" name="password" minlength="6" /></label>
        <p class="form-error" id="editError"></p>
        <button class="btn btn--primary" type="submit">Save Changes</button>
      </form>
    </div>`;

  document.getElementById('editForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = new FormData(e.target);
    const body = {
      username: form.get('username'),
      first_name: form.get('first_name'),
      last_name: form.get('last_name'),
      university: form.get('university'),
      phone_number: form.get('phone_number'),
    };
    if (form.get('password')) body.password = form.get('password');
    const res2 = await api.updateProfile(body);
    if (res2.ok) { toast('Profile updated', 'success'); navigate('/profile'); }
    else document.getElementById('editError').textContent = errorMessage(res2.data, 'Update failed');
  });
}

// ---------------------------------------------------------------------------
// Views: Driver verification
// ---------------------------------------------------------------------------

async function viewDriverVerification() {
  const myToken = beginRender();
  const view = document.getElementById('view');
  view.innerHTML = `<div class="page page--narrow"><a href="#/profile" class="back-link">‹ Back to profile</a><h1>Become a Host</h1><p class="muted">Loading…</p></div>`;

  const res = await api.getDriverVerificationStatus();
  if (isStaleRender(myToken)) return;
  const status = res.ok ? res.data.status : 'unverified';
  const v = res.ok ? res.data : {};

  const badge = {
    unverified: ['Not started', 'chip--pending'],
    pending: ['Pending review', 'chip--pending'],
    verified: ['Verified', 'chip--success'],
    rejected: ['Needs resubmission', 'chip--danger'],
  }[status] || ['Not started', 'chip--pending'];

  document.getElementById('view').innerHTML = `
    <div class="page page--narrow">
      <a href="#/profile" class="back-link">‹ Back to profile</a>
      <h1>Become a Host</h1>
      <span class="chip ${badge[1]}">${badge[0]}</span>
      <p class="muted" style="margin-top:16px">Riders trust that a verified host has a real license and vehicle. Enter your vehicle details, then complete a quick ID check hosted by Stripe Identity.</p>
      <form id="verifyForm" class="form-card">
        <label>Vehicle make<input type="text" name="vehicle_make" value="${escapeHtml(v.vehicle_make || '')}" /></label>
        <label>Vehicle model<input type="text" name="vehicle_model" value="${escapeHtml(v.vehicle_model || '')}" /></label>
        <label>Vehicle color<input type="text" name="vehicle_color" value="${escapeHtml(v.vehicle_color || '')}" /></label>
        <label>License plate<input type="text" name="vehicle_plate" value="${escapeHtml(v.vehicle_plate || '')}" /></label>
        ${status !== 'verified' ? `<button class="btn btn--primary" type="submit">${status === 'pending' ? 'Restart Verification' : 'Start Verification'}</button>` : ''}
      </form>
    </div>`;

  document.getElementById('verifyForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = new FormData(e.target);
    const res2 = await api.startDriverVerification({
      vehicle_make: form.get('vehicle_make'),
      vehicle_model: form.get('vehicle_model'),
      vehicle_color: form.get('vehicle_color'),
      vehicle_plate: form.get('vehicle_plate'),
    });
    if (res2.status === 503) {
      toast('Driver verification isn\'t configured on this server yet.', 'error');
      return;
    }
    if (!res2.ok) {
      toast(errorMessage(res2.data, 'Could not start verification'), 'error');
      return;
    }
    if (res2.data.verification_url) {
      window.open(res2.data.verification_url, '_blank');
      toast('Complete verification in the new tab, then come back and refresh.');
    } else {
      toast('Already verified!', 'success');
    }
    viewDriverVerification();
  });
}

// ---------------------------------------------------------------------------
// Views: Payment
// ---------------------------------------------------------------------------

async function viewPayment(params) {
  const myToken = beginRender();
  const rideRequestId = Number(params.id);
  const view = document.getElementById('view');
  view.innerHTML = `
    <div class="page page--narrow">
      <h1>Pay for Ride</h1>
      <div id="paymentStatus"><p class="muted">Checking status…</p></div>
    </div>`;

  const statusRes = await api.getPaymentStatus(rideRequestId);
  if (isStaleRender(myToken)) return;
  const box = document.getElementById('paymentStatus');

  if (statusRes.ok && statusRes.data.status === 'succeeded') {
    box.innerHTML = `<div class="card"><p>✅ Payment complete.</p></div>`;
    return;
  }

  box.innerHTML = `
    <div class="card">
      <p class="muted">You'll be taken to a secure Stripe checkout page in a new tab.</p>
      <button class="btn btn--primary" id="payBtn" style="margin-top:12px">Pay Now</button>
      <button class="btn btn--ghost" id="refreshPayBtn" style="margin-top:12px">I've Paid — Check Status</button>
    </div>`;

  document.getElementById('payBtn').addEventListener('click', async () => {
    const res = await api.createCheckoutSession(rideRequestId);
    if (res.status === 503) { toast('Payments aren\'t configured on this server yet.', 'error'); return; }
    if (!res.ok) { toast(errorMessage(res.data, 'Could not start checkout'), 'error'); return; }
    window.open(res.data.checkout_url, '_blank');
  });
  document.getElementById('refreshPayBtn').addEventListener('click', async () => {
    const res = await api.getPaymentStatus(rideRequestId);
    if (res.ok && res.data.status === 'succeeded') {
      toast('Payment confirmed!', 'success');
      viewPayment(params);
    } else {
      toast('Still waiting on payment confirmation.');
    }
  });
}

// ---------------------------------------------------------------------------
// Views: Legal (static)
// ---------------------------------------------------------------------------

function viewTerms() {
  document.getElementById('view').innerHTML = `<div class="page page--narrow legal">${TERMS_HTML}</div>`;
}
function viewPrivacy() {
  document.getElementById('view').innerHTML = `<div class="page page--narrow legal">${PRIVACY_HTML}</div>`;
}
