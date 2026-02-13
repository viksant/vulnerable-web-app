import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { ShoppingCart } from "lucide-react";
import apiClient from "../api/client";
import Container from "../components/ui/Container";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Divider from "../components/ui/Divider";
import ReviewList from "../components/ReviewList";
import ReviewForm from "../components/ReviewForm";
import { generatePlaceholderSvg } from "../utils/placeholderImage";

/**
 * Neo-Brutalist product detail page.
 * Two-column layout: image | info. Reviews section below.
 */
export default function ProductDetail() {
  const { id } = useParams();
  const [product, setProduct] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchProduct();
    fetchReviews();
  }, [id]);

  async function fetchProduct() {
    setIsLoading(true);
    try {
      const response = await apiClient.get(`/products/${id}`);
      setProduct(response.data);
    } catch {
      setProduct(null);
    } finally {
      setIsLoading(false);
    }
  }

  async function fetchReviews() {
    try {
      const response = await apiClient.get(`/products/${id}/reviews`);
      setReviews(response.data || []);
    } catch {
      setReviews([]);
    }
  }

  async function handleAddToCart() {
    try {
      await apiClient.post("/cart/items", {
        product_id: Number(id),
        quantity: 1,
      });
    } catch {
      // Error logged by axios interceptor
    }
  }

  async function handleSubmitReview(reviewData) {
    await apiClient.post(`/products/${id}/reviews`, reviewData);
    fetchReviews();
  }

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

  if (!product) {
    return (
      <main className="min-h-screen bg-neo-bg py-16">
        <Container>
          <p className="text-center font-black text-3xl uppercase">
            PRODUCT NOT FOUND
          </p>
        </Container>
      </main>
    );
  }

  /** Badge color based on stock level */
  function stockBadge() {
    const stock = product.stock ?? 0;
    if (stock === 0) return <Badge variant="accent">OUT OF STOCK</Badge>;
    if (stock < 10) return <Badge variant="secondary">LOW STOCK: {stock}</Badge>;
    return <Badge variant="muted">IN STOCK: {stock}</Badge>;
  }

  return (
    <main className="min-h-screen bg-neo-bg">
      <Container className="py-16">
        <div className="grid grid-cols-1 gap-12 lg:grid-cols-2">
          {/* Image */}
          <div className="border-4 border-black shadow-neo-lg">
            <img
              src={product.image_url || generatePlaceholderSvg(product.id, product.name)}
              alt={product.name}
              className="aspect-square w-full object-cover"
              onError={(e) => {
                e.target.onerror = null;
                e.target.src = generatePlaceholderSvg(product.id, product.name);
              }}
            />
          </div>

          {/* Info */}
          <div className="flex flex-col gap-4">
            <h1 className="font-black text-4xl uppercase tracking-tight sm:text-5xl">
              {product.name}
            </h1>

            {product.category && (
              <Badge variant="muted" className="self-start">
                {product.category}
              </Badge>
            )}

            <div>
              <span className="inline-block border-2 border-black bg-neo-secondary px-3 py-1 font-black text-4xl">
                ${Number(product.price).toFixed(2)}
              </span>
            </div>

            {stockBadge()}

            <p className="text-lg font-bold leading-relaxed">
              {product.description}
            </p>

            <Button
              variant="primary"
              size="lg"
              className="mt-4 shadow-neo-md"
              onClick={handleAddToCart}
              disabled={product.stock === 0}
            >
              <ShoppingCart className="mr-2 inline h-5 w-5" strokeWidth={3} />
              ADD TO CART
            </Button>
          </div>
        </div>
      </Container>

      {/* Reviews divider */}
      <div className="relative border-t-8 border-black">
        <div className="absolute left-1/2 -translate-x-1/2 -translate-y-1/2">
          <Badge variant="accent" className="text-lg">
            REVIEWS
          </Badge>
        </div>
      </div>

      {/* Reviews section */}
      <section className="bg-neo-bg py-16">
        <Container>
          <div className="grid grid-cols-1 gap-12 lg:grid-cols-5">
            <div className="lg:col-span-3">
              <ReviewList reviews={reviews} />
            </div>
            <div className="lg:col-span-2">
              <ReviewForm onSubmit={handleSubmitReview} />
            </div>
          </div>
        </Container>
      </section>
    </main>
  );
}
