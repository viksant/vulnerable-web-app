import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ShoppingCart, Menu, X } from "lucide-react";
import { getCurrentUser, removeToken } from "../utils/auth";
import Container from "./ui/Container";

/**
 * Neo-Brutalist navigation bar.
 * Shows different links based on user role.
 * Mobile: hamburger menu with full-screen overlay.
 */
export default function Navbar({ cartCount = 0 }) {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const user = getCurrentUser();
  const navigate = useNavigate();

  function handleLogout() {
    removeToken();
    navigate("/login");
  }

  /** @type {{label: string, to: string}[]} */
  const links = [];

  links.push({ label: "Shop", to: "/" });

  if (!user) {
    links.push({ label: "Login", to: "/login" });
    links.push({ label: "Register", to: "/register" });
  } else {
    links.push({ label: "Cart", to: "/cart" });
    links.push({ label: "Orders", to: "/orders" });
    links.push({ label: "Profile", to: "/profile" });

    if (user.role === "seller" || user.role === "admin") {
      links.push({ label: "Seller Dashboard", to: "/seller" });
    }
    if (user.role === "support" || user.role === "admin") {
      links.push({ label: "Support Panel", to: "/support" });
    }
    if (user.role === "admin") {
      links.push({ label: "Admin Panel", to: "/admin" });
    }
  }

  return (
    <nav className="border-b-4 border-black bg-neo-bg">
      <Container className="flex h-16 items-center justify-between">
        {/* Logo */}
        <Link
          to="/"
          className="-rotate-1 border-4 border-black bg-neo-accent px-3 py-1 font-black uppercase tracking-tight shadow-neo-sm transition-all duration-100 hover:rotate-0"
        >
          VULNSHOP
        </Link>

        {/* Desktop links */}
        <div className="hidden items-center gap-2 md:flex">
          {links.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              className="relative px-2 py-1 text-sm font-bold uppercase tracking-wide transition-all duration-100 hover:border-4 hover:border-black hover:bg-neo-accent hover:shadow-neo-sm"
            >
              {link.label}
              {link.label === "Cart" && cartCount > 0 && (
                <span className="absolute -right-2 -top-2 flex h-5 w-5 items-center justify-center rounded-full border-2 border-black bg-neo-accent text-xs font-black">
                  {cartCount}
                </span>
              )}
            </Link>
          ))}

          {user && (
            <button
              onClick={handleLogout}
              className="px-2 py-1 text-sm font-bold uppercase tracking-wide transition-all duration-100 hover:border-4 hover:border-black hover:bg-neo-accent hover:shadow-neo-sm"
            >
              Logout
            </button>
          )}

          {/* Cart icon for authenticated users */}
          {user && (
            <Link
              to="/cart"
              className="relative ml-2 border-4 border-black p-2 shadow-neo-sm transition-all duration-100 active:translate-x-[2px] active:translate-y-[2px] active:shadow-none"
              aria-label="Shopping cart"
            >
              <ShoppingCart className="h-6 w-6" strokeWidth={3} />
              {cartCount > 0 && (
                <span className="absolute -right-2 -top-2 flex h-6 w-6 items-center justify-center rounded-full border-2 border-black bg-neo-accent text-xs font-black">
                  {cartCount}
                </span>
              )}
            </Link>
          )}
        </div>

        {/* Mobile hamburger */}
        <button
          onClick={() => setIsMenuOpen(!isMenuOpen)}
          className="border-4 border-black p-2 shadow-neo-sm transition-all duration-100 active:translate-x-[2px] active:translate-y-[2px] active:shadow-none md:hidden"
          aria-label="Toggle menu"
        >
          {isMenuOpen ? (
            <X className="h-6 w-6" strokeWidth={3} />
          ) : (
            <Menu className="h-6 w-6" strokeWidth={3} />
          )}
        </button>
      </Container>

      {/* Mobile menu overlay */}
      {isMenuOpen && (
        <div className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-4 bg-neo-secondary md:hidden">
          <button
            onClick={() => setIsMenuOpen(false)}
            className="absolute right-4 top-4 border-4 border-black p-2 shadow-neo-sm"
            aria-label="Close menu"
          >
            <X className="h-8 w-8" strokeWidth={3} />
          </button>

          {links.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              onClick={() => setIsMenuOpen(false)}
              className="w-64 border-4 border-black bg-white px-6 py-4 text-center font-black text-xl uppercase tracking-wide shadow-neo-md transition-all duration-100 active:translate-x-[2px] active:translate-y-[2px] active:shadow-none"
            >
              {link.label}
            </Link>
          ))}

          {user && (
            <button
              onClick={() => {
                handleLogout();
                setIsMenuOpen(false);
              }}
              className="w-64 border-4 border-black bg-neo-accent px-6 py-4 text-center font-black text-xl uppercase tracking-wide shadow-neo-md transition-all duration-100 active:translate-x-[2px] active:translate-y-[2px] active:shadow-none"
            >
              Logout
            </button>
          )}
        </div>
      )}
    </nav>
  );
}
