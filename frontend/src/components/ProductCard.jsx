import { Link } from "react-router-dom";
import { Star, ShoppingCart } from "lucide-react";
import Card from "./ui/Card";
import Badge from "./ui/Badge";
import Button from "./ui/Button";
import { generatePlaceholderSvg } from "../utils/placeholderImage";

/**
 * Neo-Brutalist product card for grids.
 * Lift effect on hover, price sticker, rating stars.
 *
 * @param {object} props
 * @param {object} props.product - Product data.
 * @param {function} props.onAddToCart - Called when Add to Cart is clicked.
 */
export default function ProductCard({ product, onAddToCart }) {
  const rating = product.average_rating || 0;

  return (
    <div className="group relative">
      {/* Sale/Hot badge */}
      {product.discount_percent > 0 && (
        <Badge
          variant="accent"
          rotation="rotate-6"
          className="absolute -right-3 -top-3 z-10"
        >
          SALE
        </Badge>
      )}

      <Card
        hoverable
        shadow="shadow-neo-md"
        className="flex h-full flex-col overflow-hidden"
      >
        <Link to={`/products/${product.id}`}>
          {/* Image */}
          <div className="relative aspect-square border-b-4 border-black bg-neo-bg">
            <img
              src={product.image_url || generatePlaceholderSvg(product.id, product.name)}
              alt={product.name}
              className="h-full w-full object-cover"
              onError={(e) => {
                e.target.onerror = null;
                e.target.src = generatePlaceholderSvg(product.id, product.name);
              }}
            />
          </div>
        </Link>

        {/* Body */}
        <div className="flex flex-1 flex-col p-4">
          <Link to={`/products/${product.id}`}>
            <h3 className="truncate font-black text-xl uppercase">
              {product.name}
            </h3>
          </Link>

          {product.category && (
            <Badge variant="muted" className="mt-1 self-start border-2 text-xs">
              {product.category}
            </Badge>
          )}

          {/* Rating */}
          <div className="mt-2 flex items-center gap-1">
            {Array.from({ length: 5 }, (_, i) => (
              <Star
                key={i}
                className={`h-5 w-5 ${i < Math.round(rating) ? "fill-neo-secondary text-black" : "text-black/20"}`}
                strokeWidth={2}
              />
            ))}
          </div>

          {/* Price sticker */}
          <div className="mt-3">
            <span className="inline-block border-2 border-black bg-neo-secondary px-2 font-black text-3xl">
              ${Number(product.price).toFixed(2)}
            </span>
          </div>

          {/* Add to cart */}
          <Button
            variant="primary"
            size="sm"
            fullWidth
            className="mt-4"
            onClick={(e) => {
              e.preventDefault();
              onAddToCart?.(product.id);
            }}
          >
            <ShoppingCart className="mr-2 inline h-4 w-4" strokeWidth={3} />
            ADD TO CART
          </Button>
        </div>
      </Card>
    </div>
  );
}
