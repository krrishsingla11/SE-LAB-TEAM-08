// MINI-PROJECT/frontend/js/api.js
// One place for all API calls. Flip USE_MOCK to false on Sat 31 to use the real backend.
const USE_MOCK = true;
const BASE_URL = "/api";

function getToken() {
  return localStorage.getItem("token");
}

async function apiCall(method, path, body) {
  if (USE_MOCK) return mockCall(method, path, body);

  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers["Authorization"] = "Bearer " + token;

  const res = await fetch(BASE_URL + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  // Backend errors look like {error, message, status_code, timestamp}
  if (!res.ok) throw new Error(data.message || "Something went wrong. Please try again.");
  return data;
}

// ---------- Mock backend (delete once the real API is ready) ----------
function mockCall(method, path, body) {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (path === "/auth/login") {
        if (body.email === "test@x.com" && body.password === "Test@1234") {
          resolve({ token: "mock-token", expires_in: 86400 });
        } else {
          reject(new Error("Invalid email or password."));
        }
      } else if (path === "/auth/register") {
        if (body.email === "taken@x.com") {
          reject(new Error("This email is already registered."));
        } else {
          resolve({ user_id: 1, email: body.email });
        }
      } else {
        reject(new Error("No mock data for " + path));
      }
    }, 400);
  });
}

// ---------- Functions the pages call ----------
const api = {
  login: (email, password) => apiCall("POST", "/auth/login", { email, password }),
  register: (data) => apiCall("POST", "/auth/register", data), // {email, password, full_name, role}
  products: (q = "", category = "", page = 1) =>
    apiCall("GET", `/products?q=${encodeURIComponent(q)}&category=${category}&page=${page}`),
  createProduct: (data) => apiCall("POST", "/products", data),
  cartGet: () => apiCall("GET", "/cart/items"),
  cartAdd: (product_id, quantity) => apiCall("POST", "/cart/items", { product_id, quantity }),
  cartUpdate: (product_id, quantity) => apiCall("PUT", "/cart/items", { product_id, quantity }),
  cartRemove: (product_id) => apiCall("DELETE", "/cart/items", { product_id }),
  checkout: (shipping_address, payment_token) =>
    apiCall("POST", "/checkout", { shipping_address, payment_token }),
};
