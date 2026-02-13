import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
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
 * Neo-Brutalist order detail page by UUID/ID.
 */
export default function OrderDetail() {
  const { id } = useParams();
  const [order, setOrder] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchOrder();
  }, [id]);

  async function fetchOrder() {
    setIsLoading(true);
    try {
      const response = await apiClient.get(`/orders/${id}`);
      setOrder(response.data);
    } catch {
      setOrder(null);
    } finally {
      setIsLoading(false);
    }
  }

  if (isLoading) {
    return (
      <main className="min-h-screen bg-neo-bg py-16">
        <Container>
          <p className="animate-bounce-slow text-center font-black text-3xl uppercase">
            LOADING ORDER...
          </p>
        </Container>
      </main>
    );
  }

  if (!order) {
    return (
      <main className="min-h-screen bg-neo-bg py-16">
        <Container>
          <p className="text-center font-black text-3xl uppercase">
            ORDER NOT FOUND
          </p>
        </Container>
      </main>
    );
  }

  const items = order.items || [];

  return (
    <main className="min-h-screen bg-neo-bg py-16">
      <Container>
        <Link
          to="/orders"
          className="mb-6 inline-flex items-center gap-2 font-bold uppercase transition-all duration-100 hover:border-4 hover:border-black hover:bg-neo-accent hover:px-2 hover:shadow-neo-sm"
        >
          <ArrowLeft className="h-5 w-5" strokeWidth={3} />
          BACK TO ORDERS
        </Link>

        <div className="mb-6 flex flex-wrap items-center gap-4">
          <h1 className="font-black text-4xl uppercase tracking-tight">
            ORDER
          </h1>
          <Badge variant="dark" className="font-mono">
            {String(order.id || order.uuid || "")}
          </Badge>
          <Badge variant={STATUS_VARIANT[order.status] || "muted"}>
            {(order.status || "pending").toUpperCase()}
          </Badge>
        </div>

        <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
          {/* Items */}
          <div className="lg:col-span-2">
            <Card header="ITEMS" headerColor="bg-neo-secondary">
              <div className="divide-y-4 divide-black">
                {items.map((item, index) => (
                  <div
                    key={item.id || index}
                    className="flex items-center justify-between p-4"
                  >
                    <div>
                      <p className="font-black text-lg uppercase">
                        {item.product_name || `Product #${item.product_id}`}
                      </p>
                      <p className="font-bold">Qty: {item.quantity}</p>
                    </div>
                    <span className="font-black text-xl">
                      ${(Number(item.price || 0) * item.quantity).toFixed(2)}
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          </div>

          {/* Summary */}
          <div>
            <Card shadow="shadow-neo-lg" className="bg-neo-secondary">
              <div className="flex flex-col gap-4 p-6">
                <div className="flex justify-between font-black text-2xl">
                  <span>TOTAL</span>
                  <span>${Number(order.total || 0).toFixed(2)}</span>
                </div>
                {order.shipping_address && (
                  <div>
                    <p className="text-sm font-bold uppercase tracking-widest">
                      SHIPPING TO
                    </p>
                    <p className="mt-1 font-bold text-lg">
                      {order.shipping_address}
                    </p>
                  </div>
                )}
                {order.created_at && (
                  <p className="text-sm font-bold text-black/60">
                    Placed: {new Date(order.created_at).toLocaleString()}
                  </p>
                )}
              </div>
            </Card>
          </div>
        </div>
      </Container>
    </main>
  );
}
