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
// Shapes copied from the real backend (app/search/service.py, app/cart/routes.py)
const MOCK_CATEGORIES = [
  { category_id: 1, name: "Pottery", slug: "pottery" },
  { category_id: 2, name: "Textiles", slug: "textiles" },
  { category_id: 3, name: "Woodwork", slug: "woodwork" },
  { category_id: 4, name: "Metalwork", slug: "metalwork" },
];
const mp = (id, title, description, price, category_id, artisan_id, stock) => ({
  product_id: id, title, description, price, category_id, artisan_id,
  image_url: null, stock_quantity: stock, in_stock: stock > 0,
});
const MOCK_PRODUCTS = [
  mp(108, "Brass Diya Lamp", "Cast brass oil lamp with a hand-finished surface.", 720, 4, 4, 15),
  mp(107, "Painted Clay Vase", "Hand-painted clay vase, sealed for dry flowers.", 560, 1, 1, 6),
  mp(106, "Block-Printed Table Runner", "Cotton table runner printed with hand-carved wooden blocks.", 980, 2, 2, 8),
  mp(105, "Terracotta Planter", "Unglazed terracotta planter with a hand-pressed pattern and drainage hole.", 450, 1, 1, 25),
  mp(104, "Carved Teak Coaster Set", "Set of four teak coasters, carved by hand and finished with food-safe oil.", 640, 3, 3, 0),
  mp(103, "Handwoven Cotton Scarf", "Soft cotton scarf woven on a pit loom with natural indigo dye.", 1200, 2, 2, 3),
  mp(102, "Blue Glaze Ceramic Bowl", "Wheel-thrown stoneware bowl with a hand-poured blue glaze.", 850, 1, 1, 12),
  mp(101, "Wooden Spice Box", "Seven-compartment spice box in rosewood.", 1500, 3, 3, 9),
];

function mockCall(method, path, body) {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      const url = new URL(path, "http://mock");
      if (path === "/auth/login") {
        if (body.email === "test@x.com" && body.password === "Test@1234") {
          resolve({ token: "mock-token", expires_in: 86400 });
        } else {
          reject(new Error("Invalid email or password."));
        }
      } else if (path === "/auth/register") {
        if (body.email === "taken@x.com") {
          reject(new Error("Email already registered"));
        } else {
          resolve({ user_id: 1, email: body.email });
        }
      } else if (url.pathname === "/categories") {
        resolve({ categories: MOCK_CATEGORIES });
      } else if (url.pathname === "/products" && method === "GET") {
        const q = (url.searchParams.get("q") || "").toLowerCase();
        const cat = url.searchParams.get("category");
        const page = parseInt(url.searchParams.get("page") || "1", 10);
        const per_page = parseInt(url.searchParams.get("per_page") || "12", 10);
        const filtered = MOCK_PRODUCTS.filter(
          (p) =>
            (!q || p.title.toLowerCase().includes(q) || p.description.toLowerCase().includes(q)) &&
            (!cat || p.category_id === parseInt(cat, 10))
        );
        resolve({
          products: filtered.slice((page - 1) * per_page, page * per_page),
          total: filtered.length, page, per_page,
        });
      } else if (/^\/products\/\d+$/.test(url.pathname) && method === "GET") {
        const id = parseInt(url.pathname.split("/")[2], 10);
        const p = MOCK_PRODUCTS.find((x) => x.product_id === id);
        p ? resolve({ ...p, images: [] }) : reject(new Error("Product not found"));
      } else if (path === "/cart/items" && method === "POST") {
        resolve({ message: "Added to cart" });
      } else {
        reject(new Error("No mock data for " + method + " " + path));
      }
    }, 400);
  });
}

// ---------- Functions the pages call ----------
const api = {
  login: (email, password) => apiCall("POST", "/auth/login", { email, password }),
  register: (data) => apiCall("POST", "/auth/register", data), // {email, password, full_name, role: "buyer"|"artisan"}
  categories: () => apiCall("GET", "/categories"), // {categories: [{category_id, name, slug}]}
  products: (q = "", categoryId = "", page = 1, perPage = 6) =>
    apiCall("GET", `/products?q=${encodeURIComponent(q)}&category=${categoryId}&page=${page}&per_page=${perPage}`),
  product: (id) => apiCall("GET", `/products/${id}`),
  createProduct: (data) => apiCall("POST", "/products", data),
  cartGet: () => apiCall("GET", "/cart"),
  cartAdd: (product_id, quantity) => apiCall("POST", "/cart/items", { product_id, quantity }),
  cartUpdate: (product_id, quantity) => apiCall("PUT", `/cart/items/${product_id}`, { quantity }),
  cartRemove: (product_id) => apiCall("DELETE", `/cart/items/${product_id}`),
  checkout: (shipping_address, payment_token) =>
    apiCall("POST", "/checkout", { shipping_address, payment_token }),
};
