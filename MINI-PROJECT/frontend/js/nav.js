// Shared top navigation. Every page has <nav id="site-nav"></nav> in its header and loads this file.
(function () {
  const nav = document.getElementById("site-nav");
  if (!nav) return;

  const here = location.pathname.split("/").pop() || "index.html";
  const loggedIn = !!localStorage.getItem("token");
  const role = localStorage.getItem("role");
  const cls = "text-indigo-800 underline hover:text-indigo-600 focus:outline-none focus:ring-2 focus:ring-indigo-700 rounded";

  const items = [["catalog.html", "Browse"], ["cart.html", "Cart"]];
  if (role === "artisan") items.push(["artisan-listings.html", "Sell"]);
  if (!loggedIn) items.push(["login.html", "Log in"], ["register.html", "Create account"]);

  nav.className = "flex flex-wrap items-center gap-x-4 gap-y-1 text-sm font-medium";
  nav.setAttribute("aria-label", "Main");
  nav.innerHTML = items
    .map(([href, label]) => `<a href="${href}" class="${cls}"${here === href ? ' aria-current="page"' : ""}>${label}</a>`)
    .join("");

  if (loggedIn) {
    const out = document.createElement("button");
    out.type = "button";
    out.textContent = "Log out";
    out.className = cls;
    out.addEventListener("click", () => {
      localStorage.removeItem("token");
      localStorage.removeItem("role");
      window.location.href = "index.html";
    });
    nav.appendChild(out);
  }
})();
