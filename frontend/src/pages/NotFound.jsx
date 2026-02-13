import { useNavigate } from "react-router-dom";
import Button from "../components/ui/Button";

/**
 * Neo-Brutalist 404 page.
 * Full-screen red background with massive "404" in text-stroke.
 */
export default function NotFound() {
  const navigate = useNavigate();

  return (
    <main className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-neo-accent">
      {/* Decorative floating shapes */}
      <div className="absolute left-[10%] top-[20%] h-16 w-16 rotate-12 border-4 border-black bg-neo-secondary" />
      <div className="absolute bottom-[25%] right-[15%] h-20 w-20 rounded-full border-4 border-black bg-neo-muted" />
      <div className="absolute left-[60%] top-[10%] h-12 w-12 -rotate-6 border-4 border-black bg-white" />
      <div className="absolute bottom-[15%] left-[20%] h-14 w-14 rotate-45 rounded-full border-4 border-black bg-neo-secondary" />

      {/* 404 */}
      <h1 className="-rotate-3 text-stroke-3 font-black text-[120px] leading-none sm:text-[200px]">
        404
      </h1>

      <p className="mt-4 font-black text-3xl uppercase tracking-tight sm:text-4xl">
        PAGE NOT FOUND
      </p>

      <Button
        variant="dark"
        size="lg"
        className="mt-8 shadow-neo-lg"
        onClick={() => navigate("/")}
      >
        GO HOME
      </Button>
    </main>
  );
}
