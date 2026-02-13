import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "../api/client";
import Container from "../components/ui/Container";
import Card from "../components/ui/Card";
import Badge from "../components/ui/Badge";

const STATUS_VARIANT = {
  pending: "secondary",
  completed: "muted",
  cancelled: "accent",
  processing: "secondary",
};

/**
 * Neo-Brutalist order history page.
 * List of orders as clickable cards with status badges.
 */
export default function OrderHistory() {
  const [orders, setOrders] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    fetchOrders();
  }, []);

  async function fetchOrders() {
    setIsLoading(true);
    try {
      const response = await apiClient.get("/orders");
      setOrders(response.data || []);
    } catch {
      setOrders([]);
    } finally {
      setIsLoading(false);
    }
  }

  if (isLoading) {
    return (
      <main className="min-h-screen bg-neo-bg py-16">
        <Container>
          <p className="animate-bounce-slow text-center font-black text-3xl uppercase">
            LOADING ORDERS...
          </p>
        </Container>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-neo-bg py-16">
      <Container>
        <h1 className="mb-8 font-black text-5xl uppercase tracking-tight">
          YOUR ORDERS
        </h1>

        {orders.length === 0 ? (
          <p className="py-16 text-center font-black text-2xl uppercase text-black/30">
            NO ORDERS YET
          </p>
        ) : (
          <div className="flex flex-col gap-4">
            {orders.map((order) => (
              <Card
                key={order.id}
                hoverable
                shadow="shadow-neo-sm"
                onClick={() => navigate(`/orders/${order.id}`)}
              >
                <div className="flex flex-wrap items-center gap-4 p-4">
                  <Badge variant="dark" className="font-mono text-xs">
                    {String(order.id || order.uuid || "").slice(0, 8)}...
                  </Badge>

                  <Badge variant={STATUS_VARIANT[order.status] || "muted"}>
                    {(order.status || "pending").toUpperCase()}
                  </Badge>

                  <span className="font-black text-2xl">
                    ${Number(order.total || 0).toFixed(2)}
                  </span>

                  <span className="ml-auto text-sm font-bold text-black/60">
                    {order.created_at
                      ? new Date(order.created_at).toLocaleDateString()
                      : ""}
                  </span>
                </div>
              </Card>
            ))}
          </div>
        )}
      </Container>
    </main>
  );
}
