import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Star } from "lucide-react";
import apiClient from "../api/client";
import { setToken } from "../utils/auth";
import { extractApiError } from "../utils/extractApiError";
import Button from "../components/ui/Button";
import Input from "../components/ui/Input";
import Card from "../components/ui/Card";
import Badge from "../components/ui/Badge";
import Container from "../components/ui/Container";

/**
 * Neo-Brutalist Login page.
 * Black header, dots background, decorative elements.
 */
export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      const response = await apiClient.post("/auth/login", { email, password });
      setToken(response.data.access_token);
      navigate("/");
    } catch (err) {
      setError(extractApiError(err, "Login failed"));
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="relative min-h-screen bg-neo-bg bg-dots py-16">
      <Container className="flex justify-center">
        <div className="relative w-full max-w-md">
          {/* Decorative elements */}
          <Star
            className="absolute -left-8 -top-8 h-12 w-12 animate-spin-slow text-neo-accent"
            strokeWidth={3}
          />
          <Badge
            variant="secondary"
            rotation="rotate-3"
            className="absolute -right-4 -top-6"
          >
            MEMBERS ONLY
          </Badge>

          <Card shadow="shadow-neo-xl">
            {/* Black header */}
            <div className="border-b-4 border-black bg-black px-6 py-6">
              <h1 className="font-black text-4xl uppercase tracking-tight text-white">
                LOGIN
              </h1>
            </div>

            <form onSubmit={handleSubmit} className="flex flex-col gap-4 p-6">
              {error && (
                <div className="border-4 border-black bg-neo-accent p-3 font-bold">
                  {error}
                </div>
              )}

              <Input
                label="Email"
                type="email"
                placeholder="your@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />

              <Input
                label="Password"
                type="password"
                placeholder="********"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />

              <Button
                type="submit"
                variant="primary"
                size="lg"
                fullWidth
                disabled={isLoading}
                className="mt-2 shadow-neo-md"
              >
                {isLoading ? "LOGGING IN..." : "LOGIN"}
              </Button>

              <p className="text-center text-lg font-bold">
                Don&apos;t have an account?{" "}
                <Link
                  to="/register"
                  className="border-b-4 border-neo-accent transition-all duration-100 hover:bg-neo-accent hover:px-1"
                >
                  SIGN UP
                </Link>
              </p>
            </form>
          </Card>
        </div>
      </Container>
    </main>
  );
}
