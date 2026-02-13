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
 * Neo-Brutalist Register page.
 * Similar layout to Login with form for new account creation.
 */
export default function Register() {
  const [formData, setFormData] = useState({
    username: "",
    email: "",
    password: "",
    confirmPassword: "",
  });
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  function handleChange(e) {
    setFormData((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");

    if (formData.password !== formData.confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    setIsLoading(true);
    try {
      const response = await apiClient.post("/auth/register", {
        username: formData.username,
        email: formData.email,
        password: formData.password,
      });
      setToken(response.data.token);
      navigate("/");
    } catch (err) {
      setError(extractApiError(err, "Registration failed"));
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
            className="absolute -right-8 -top-8 h-12 w-12 animate-spin-slow text-neo-muted"
            strokeWidth={3}
          />
          <Badge
            variant="accent"
            rotation="-rotate-2"
            className="absolute -left-4 -top-6"
          >
            JOIN US
          </Badge>

          <Card shadow="shadow-neo-xl">
            <div className="border-b-4 border-black bg-black px-6 py-6">
              <h1 className="font-black text-4xl uppercase tracking-tight text-white">
                SIGN UP
              </h1>
            </div>

            <form onSubmit={handleSubmit} className="flex flex-col gap-4 p-6">
              {error && (
                <div className="border-4 border-black bg-neo-accent p-3 font-bold">
                  {error}
                </div>
              )}

              <Input
                label="Username"
                name="username"
                placeholder="hackerman42"
                value={formData.username}
                onChange={handleChange}
                required
              />

              <Input
                label="Email"
                type="email"
                name="email"
                placeholder="your@email.com"
                value={formData.email}
                onChange={handleChange}
                required
              />

              <Input
                label="Password"
                type="password"
                name="password"
                placeholder="********"
                value={formData.password}
                onChange={handleChange}
                required
              />

              <Input
                label="Confirm Password"
                type="password"
                name="confirmPassword"
                placeholder="********"
                value={formData.confirmPassword}
                onChange={handleChange}
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
                {isLoading ? "CREATING ACCOUNT..." : "SIGN UP"}
              </Button>

              <p className="text-center text-lg font-bold">
                Already have an account?{" "}
                <Link
                  to="/login"
                  className="border-b-4 border-neo-accent transition-all duration-100 hover:bg-neo-accent hover:px-1"
                >
                  LOGIN
                </Link>
              </p>
            </form>
          </Card>
        </div>
      </Container>
    </main>
  );
}
