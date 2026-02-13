import { Star } from "lucide-react";
import Card from "./ui/Card";
import Badge from "./ui/Badge";

/**
 * Neo-Brutalist review list.
 * INTENTIONALLY renders review body and title without sanitization.
 *
 * @param {object} props
 * @param {Array} props.reviews - Array of review objects.
 */
export default function ReviewList({ reviews = [] }) {
  if (reviews.length === 0) {
    return (
      <p className="py-8 text-center font-bold text-lg text-black/40">
        NO REVIEWS YET. BE THE FIRST!
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {reviews.map((review) => (
        <Card key={review.id} shadow="shadow-neo-sm">
          {/* Review header */}
          <div className="flex items-center gap-3 border-b-4 border-black bg-neo-muted/20 px-4 py-3">
            <Badge variant="dark">{review.username || "Anonymous"}</Badge>

            <div className="flex items-center gap-1">
              {Array.from({ length: 5 }, (_, i) => (
                <Star
                  key={i}
                  className={`h-4 w-4 ${i < (review.rating || 0) ? "fill-neo-secondary text-black" : "text-black/20"}`}
                  strokeWidth={2}
                />
              ))}
            </div>

            <span className="ml-auto text-sm font-bold text-black/60">
              {review.created_at
                ? new Date(review.created_at).toLocaleDateString()
                : ""}
            </span>
          </div>

          {/* Review body */}
          <div className="p-4">
            {/* VULN: Stored XSS - Review title rendered without sanitization - Ref: https://hackerone.com/reports/485748 */}
            {review.title && (
              <h4
                className="mb-2 font-black text-lg uppercase"
                dangerouslySetInnerHTML={{ __html: review.title }}
              />
            )}

            {/* VULN: Stored XSS - Review body rendered as raw HTML - Ref: https://hackerone.com/reports/485748 */}
            <div
              className="font-bold text-lg leading-relaxed"
              dangerouslySetInnerHTML={{ __html: review.body }}
            />
          </div>
        </Card>
      ))}
    </div>
  );
}
