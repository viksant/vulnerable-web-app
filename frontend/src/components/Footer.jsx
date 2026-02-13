import { Star } from "lucide-react";

/**
 * Neo-Brutalist Footer.
 * Black background, white text, decorative star row.
 */
export default function Footer() {
  return (
    <footer className="border-t-8 border-black bg-black py-8">
      <div className="mx-auto max-w-7xl px-4 text-center sm:px-6 lg:px-8">
        <div className="mb-4 flex items-center justify-center gap-2">
          {Array.from({ length: 5 }, (_, i) => (
            <Star
              key={i}
              className="h-6 w-6 text-neo-secondary"
              strokeWidth={3}
              fill="currentColor"
            />
          ))}
        </div>
        <p className="text-sm font-bold uppercase tracking-widest text-white">
          VULNSHOP &copy; 2024 &mdash; DELIBERATELY VULNERABLE
        </p>
      </div>
    </footer>
  );
}
