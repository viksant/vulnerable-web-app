import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { X, Plus, Minus, ArrowRight } from "lucide-react";
import apiClient from "../api/client";
import Container from "../components/ui/Container";
import Card from "../components/ui/Card";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import CouponInput from "../components/CouponInput";
import { generatePlaceholderSvg } from "../utils/placeholderImage";

/**
 * Neo-Brutalist cart page with item list, quantity controls, and coupon.
 */
export default function Cart() {
  const [cart, setCart] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    fetchCart();
  }, []);

  async function fetchCart() {
    setIsLoading(true);
    try {
      const response = await apiClient.get("/cart");
      setCart(response.data);
    } catch {
      setCart(null);
    } finally {
      setIsLoading(false);
    }
  }

  async function updateQuantity(itemId, quantity) {
    if (quantity < 1) return;
    try {
      await apiClient.put(`/cart/items/${itemId}`, { quantity });
      fetchCart();
    } catch {
      // Error logged by interceptor
    }
  }

  async function removeItem(itemId) {
    try {
      await apiClient.delete(`/cart/items/${itemId}`);
      fetchCart();
    } catch {
      // Error logged by interceptor
    }
  }

  async function applyCoupon(code) {
    try {
      await apiClient.post("/cart/coupon", { code });
      fetchCart();
    } catch {
      // Error logged by interceptor
    }
  }

  const items = cart?.items || [];
  const subtotal = cart?.subtotal || 0;
  const discount = cart?.discount || 0;
  const total = cart?.total || subtotal - discount;

  if (isLoading) {
    return (
      <main className="min-h-screen bg-neo-bg py-16">
        <Container>
          <p className="animate-bounce-slow text-center font-black text-3xl uppercase">
            LOADING CART...
          </p>
        </Container>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-neo-bg py-16">
      <Container>
        <div className="mb-8 flex items-center gap-4">
          <h1 className="font-black text-5xl uppercase tracking-tight">
            YOUR CART
          </h1>
          <Badge variant="dark">{items.length} ITEMS</Badge>
        </div>

        {items.length === 0 ? (
          /* Empty cart */
          <div className="py-24 text-center">
            <p className="text-stroke font-black text-8xl uppercase">EMPTY</p>
            <p className="mt-4 text-xl font-bold">
              Your cart is lonely. Go add some products!
            </p>
            <Button
              variant="primary"
              size="lg"
              className="mt-6"
              onClick={() => navigate("/")}
            >
              GO SHOPPING
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
            {/* Items list */}
            <div className="flex flex-col gap-4 lg:col-span-2">
              {items.map((item) => (
                <Card key={item.id} shadow="shadow-neo-sm">
                  <div className="flex items-center gap-4 p-4">
                    {/* Thumbnail */}
                    <div className="h-24 w-24 flex-shrink-0 border-4 border-black bg-neo-bg">
                      <img
                        src={item.image_url || generatePlaceholderSvg(item.product_id, item.product_name)}
                        alt={item.product_name}
                        className="h-full w-full object-cover"
                        onError={(e) => {
                          e.target.onerror = null;
                          e.target.src = generatePlaceholderSvg(item.product_id, item.product_name);
                        }}
                      />
                    </div>

                    {/* Info */}
                    <div className="flex-1">
                      <h3 className="font-black text-lg uppercase">
                        {item.product_name || `Product #${item.product_id}`}
                      </h3>
                      <p className="font-bold text-lg">
                        ${Number(item.price || 0).toFixed(2)}
                      </p>
                    </div>

                    {/* Quantity controls */}
                    <div className="flex items-center gap-0">
                      <button
                        onClick={() => updateQuantity(item.id, item.quantity - 1)}
                        className="flex h-10 w-10 items-center justify-center border-4 border-black bg-white font-black transition-all duration-100 active:translate-x-[1px] active:translate-y-[1px]"
                        aria-label="Decrease quantity"
                      >
                        <Minus className="h-4 w-4" strokeWidth={3} />
                      </button>
                      <span className="flex h-10 w-12 items-center justify-center border-y-4 border-black bg-white font-black text-lg">
                        {item.quantity}
                      </span>
                      <button
                        onClick={() => updateQuantity(item.id, item.quantity + 1)}
                        className="flex h-10 w-10 items-center justify-center border-4 border-black bg-white font-black transition-all duration-100 active:translate-x-[1px] active:translate-y-[1px]"
                        aria-label="Increase quantity"
                      >
                        <Plus className="h-4 w-4" strokeWidth={3} />
                      </button>
                    </div>

                    {/* Subtotal */}
                    <span className="font-black text-xl">
                      ${(Number(item.price || 0) * item.quantity).toFixed(2)}
                    </span>

                    {/* Remove */}
                    <button
                      onClick={() => removeItem(item.id)}
                      className="flex h-10 w-10 items-center justify-center border-4 border-black bg-neo-accent transition-all duration-100 active:translate-x-[1px] active:translate-y-[1px] active:shadow-none"
                      aria-label="Remove item"
                    >
                      <X className="h-5 w-5" strokeWidth={3} />
                    </button>
                  </div>
                </Card>
              ))}
            </div>

            {/* Summary */}
            <div className="flex flex-col gap-4">
              <CouponInput onApply={applyCoupon} />

              <Card shadow="shadow-neo-lg" className="bg-neo-secondary">
                <div className="flex flex-col gap-3 p-6">
                  <div className="flex justify-between font-bold text-lg">
                    <span>SUBTOTAL</span>
                    <span>${Number(subtotal).toFixed(2)}</span>
                  </div>
                  {discount > 0 && (
                    <div className="flex justify-between font-bold text-lg text-neo-accent">
                      <span>DISCOUNT</span>
                      <span>-${Number(discount).toFixed(2)}</span>
                    </div>
                  )}
                  <hr className="border-t-4 border-black" />
                  <div className="flex justify-between font-black text-2xl">
                    <span>TOTAL</span>
                    <span>${Number(total).toFixed(2)}</span>
                  </div>

                  <Button
                    variant="dark"
                    size="lg"
                    fullWidth
                    className="mt-4 shadow-neo-lg"
                    onClick={() => navigate("/checkout")}
                  >
                    CHECKOUT <ArrowRight className="ml-2 inline h-5 w-5" strokeWidth={3} />
                  </Button>
                </div>
              </Card>
            </div>
          </div>
        )}
      </Container>
    </main>
  );
}
