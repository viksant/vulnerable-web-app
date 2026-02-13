import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "../api/client";
import { extractApiError } from "../utils/extractApiError";
import Container from "../components/ui/Container";
import Card from "../components/ui/Card";
import Input from "../components/ui/Input";
import Button from "../components/ui/Button";

/**
 * Neo-Brutalist checkout page.
 * Two-column layout: shipping form | order summary.
 */
export default function Checkout() {
  const [cart, setCart] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    address: "",
    city: "",
    zip_code: "",
    country: "",
    payment_method: "credit_card",
  });

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

  function handleChange(e) {
    setFormData((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setIsSubmitting(true);
    setError("");
    try {
      const response = await apiClient.post("/orders", {
        shipping_address: `${formData.address}, ${formData.city}, ${formData.zip_code}, ${formData.country}`,
        payment_method: formData.payment_method,
      });
      const orderId = response.data.id || response.data.order_id;
      navigate(`/orders/${orderId}`);
    } catch (err) {
      setError(extractApiError(err, "Checkout failed"));
    } finally {
      setIsSubmitting(false);
    }
  }

  const items = cart?.items || [];
  const total = cart?.total || cart?.subtotal || 0;

  if (isLoading) {
    return (
      <main className="min-h-screen bg-neo-bg py-16">
        <Container>
          <p className="animate-bounce-slow text-center font-black text-3xl uppercase">
            LOADING...
          </p>
        </Container>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-neo-bg py-16">
      <Container>
        <h1 className="mb-8 font-black text-5xl uppercase tracking-tight">
          CHECKOUT
        </h1>

        {error && (
          <div className="mb-6 border-4 border-black bg-neo-accent p-4 font-bold">
            {error}
          </div>
        )}

        <form
          onSubmit={handleSubmit}
          className="grid grid-cols-1 gap-8 lg:grid-cols-5"
        >
          {/* Shipping form */}
          <div className="lg:col-span-3">
            <Card header="SHIPPING ADDRESS" headerColor="bg-neo-muted">
              <div className="flex flex-col gap-4 p-6">
                <Input
                  label="Address"
                  name="address"
                  placeholder="123 Hack Street"
                  value={formData.address}
                  onChange={handleChange}
                  required
                />
                <div className="grid grid-cols-2 gap-4">
                  <Input
                    label="City"
                    name="city"
                    placeholder="Hacktown"
                    value={formData.city}
                    onChange={handleChange}
                    required
                  />
                  <Input
                    label="ZIP Code"
                    name="zip_code"
                    placeholder="00000"
                    value={formData.zip_code}
                    onChange={handleChange}
                    required
                  />
                </div>
                <Input
                  label="Country"
                  name="country"
                  placeholder="Hackistan"
                  value={formData.country}
                  onChange={handleChange}
                  required
                />
                <div>
                  <label className="mb-1 block text-sm font-bold uppercase tracking-widest">
                    Payment Method
                  </label>
                  <select
                    name="payment_method"
                    value={formData.payment_method}
                    onChange={handleChange}
                    className="h-14 w-full border-4 border-black bg-white px-4 font-bold text-lg focus:bg-neo-secondary focus:outline-none"
                  >
                    <option value="credit_card">Credit Card</option>
                    <option value="debit_card">Debit Card</option>
                    <option value="paypal">PayPal</option>
                    <option value="crypto">Crypto</option>
                  </select>
                </div>
              </div>
            </Card>
          </div>

          {/* Order summary */}
          <div className="lg:col-span-2">
            <Card shadow="shadow-neo-lg" className="bg-neo-muted/30">
              <div className="border-b-4 border-black bg-black px-4 py-3">
                <h2 className="font-black text-lg uppercase tracking-widest text-white">
                  ORDER SUMMARY
                </h2>
              </div>
              <div className="p-6">
                <div className="flex flex-col gap-3">
                  {items.map((item) => (
                    <div
                      key={item.id}
                      className="flex justify-between font-bold"
                    >
                      <span className="truncate">
                        {item.product_name || `Item #${item.product_id}`} x{item.quantity}
                      </span>
                      <span>
                        ${(Number(item.price || 0) * item.quantity).toFixed(2)}
                      </span>
                    </div>
                  ))}
                </div>
                <hr className="my-4 border-t-4 border-black" />
                <div className="flex justify-between font-black text-2xl">
                  <span>TOTAL</span>
                  <span>${Number(total).toFixed(2)}</span>
                </div>

                <Button
                  type="submit"
                  variant="primary"
                  size="lg"
                  fullWidth
                  disabled={isSubmitting || items.length === 0}
                  className="mt-6 h-16 text-xl shadow-neo-lg"
                >
                  {isSubmitting ? "PLACING ORDER..." : "PLACE ORDER"}
                </Button>
              </div>
            </Card>
          </div>
        </form>
      </Container>
    </main>
  );
}
