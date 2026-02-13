import { useState } from "react";
import { Star } from "lucide-react";
import Card from "./ui/Card";
import Input from "./ui/Input";
import Button from "./ui/Button";

/**
 * Neo-Brutalist review form with star rating selector.
 *
 * @param {object} props
 * @param {function} props.onSubmit - Called with { title, body, rating }.
 */
export default function ReviewForm({ onSubmit }) {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [rating, setRating] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    if (rating === 0) return;
    setIsSubmitting(true);
    try {
      await onSubmit({ title, body, rating });
      setTitle("");
      setBody("");
      setRating(0);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Card header="LEAVE A REVIEW" headerColor="bg-neo-secondary">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4 p-6">
        {/* Star rating */}
        <div>
          <label className="mb-1 block text-sm font-bold uppercase tracking-widest">
            Rating
          </label>
          <div className="flex gap-1">
            {Array.from({ length: 5 }, (_, i) => (
              <button
                key={i}
                type="button"
                onClick={() => setRating(i + 1)}
                className="focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2"
                aria-label={`Rate ${i + 1} stars`}
              >
                <Star
                  className={`h-8 w-8 transition-colors duration-100 ${
                    i < rating
                      ? "fill-neo-secondary text-black"
                      : "text-black/20 hover:text-black/40"
                  }`}
                  strokeWidth={2}
                />
              </button>
            ))}
          </div>
        </div>

        <Input
          label="Title"
          placeholder="Great product!"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />

        <Input
          label="Review"
          type="textarea"
          placeholder="Tell us what you think..."
          value={body}
          onChange={(e) => setBody(e.target.value)}
          required
        />

        <Button
          type="submit"
          variant="secondary"
          disabled={isSubmitting || rating === 0}
        >
          {isSubmitting ? "SUBMITTING..." : "SUBMIT REVIEW"}
        </Button>
      </form>
    </Card>
  );
}
