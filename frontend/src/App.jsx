import { useState, useEffect } from "react";
import { Routes, Route, useLocation } from "react-router-dom";
import apiClient from "./api/client";
import { isAuthenticated } from "./utils/auth";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer";
import ProtectedRoute from "./components/ProtectedRoute";
import Home from "./pages/Home";
import Login from "./pages/Login";
import Register from "./pages/Register";
import ProductDetail from "./pages/ProductDetail";
import Cart from "./pages/Cart";
import Checkout from "./pages/Checkout";
import OrderHistory from "./pages/OrderHistory";
import OrderDetail from "./pages/OrderDetail";
import Profile from "./pages/Profile";
import SellerDashboard from "./pages/SellerDashboard";
import SupportPanel from "./pages/SupportPanel";
import AdminPanel from "./pages/AdminPanel";
import NotFound from "./pages/NotFound";

/**
 * Root application component with routing and layout.
 */
export default function App() {
  const [cartCount, setCartCount] = useState(0);
  const location = useLocation();

  // Refetch cart count on every navigation so badge stays current
  useEffect(() => {
    if (isAuthenticated()) {
      fetchCartCount();
    }
  }, [location.pathname]);

  async function fetchCartCount() {
    try {
      const response = await apiClient.get("/cart");
      const items = response.data?.items || [];
      setCartCount(items.reduce((sum, item) => sum + item.quantity, 0));
    } catch {
      setCartCount(0);
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Navbar cartCount={cartCount} />

      <div className="flex-1">
        <Routes>
          {/* Public routes */}
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/products/:id" element={<ProductDetail />} />

          {/* Protected: any authenticated user */}
          <Route
            path="/cart"
            element={
              <ProtectedRoute>
                <Cart />
              </ProtectedRoute>
            }
          />
          <Route
            path="/checkout"
            element={
              <ProtectedRoute>
                <Checkout />
              </ProtectedRoute>
            }
          />
          <Route
            path="/orders"
            element={
              <ProtectedRoute>
                <OrderHistory />
              </ProtectedRoute>
            }
          />
          <Route
            path="/orders/:id"
            element={
              <ProtectedRoute>
                <OrderDetail />
              </ProtectedRoute>
            }
          />
          <Route
            path="/profile"
            element={
              <ProtectedRoute>
                <Profile />
              </ProtectedRoute>
            }
          />

          {/* Protected: seller or admin */}
          <Route
            path="/seller"
            element={
              <ProtectedRoute roles={["seller", "admin"]}>
                <SellerDashboard />
              </ProtectedRoute>
            }
          />

          {/* Protected: support or admin */}
          <Route
            path="/support"
            element={
              <ProtectedRoute roles={["support", "admin"]}>
                <SupportPanel />
              </ProtectedRoute>
            }
          />

          {/* Protected: admin only */}
          <Route
            path="/admin"
            element={
              <ProtectedRoute roles={["admin"]}>
                <AdminPanel />
              </ProtectedRoute>
            }
          />

          {/* 404 */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </div>

      <Footer />
    </div>
  );
}
