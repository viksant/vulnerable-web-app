import { useState, useEffect, useRef } from "react";
import axios from "axios";
import Container from "../components/ui/Container";
import Card from "../components/ui/Card";
import Input from "../components/ui/Input";
import Button from "../components/ui/Button";

const STEPS = [
  "Validating API key...",
  "Dropping database schema...",
  "Rebuilding tables & seed data...",
  "Clearing uploaded files...",
  "Flushing Redis cache...",
  "Waiting for backend to come back up...",
];

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function waitForHealth(maxAttempts = 30) {
  for (let i = 0; i < maxAttempts; i++) {
    try {
      const res = await axios.get("/api/products?page=1&per_page=1", {
        timeout: 2000,
      });
      if (res.status === 200) return true;
    } catch {
      /* not ready yet */
    }
    await sleep(2000);
  }
  return false;
}

/**
 * Full-screen neo-brutalist loader overlay.
 */
function FullScreenLoader({ step, progress }) {
  return (
    <div className="fixed inset-0 z-[9999] flex flex-col items-center justify-center bg-black">
      {/* Spinning square */}
      <div className="mb-10 h-20 w-20 animate-spin border-8 border-neo-accent border-t-transparent" />

      {/* Title */}
      <h2 className="mb-6 text-center font-black text-4xl uppercase tracking-tight text-white">
        RESETTING APPLICATION
      </h2>

      {/* Progress bar */}
      <div className="mx-4 mb-6 w-full max-w-md border-4 border-white bg-neutral-900">
        <div
          className="h-6 bg-neo-accent transition-all duration-500 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Current step */}
      <p className="mb-2 text-center font-bold text-lg uppercase tracking-wide text-neo-accent">
        {step}
      </p>
      <p className="text-center font-bold text-sm text-neutral-400">
        Do not close this page
      </p>
    </div>
  );
}

/**
 * Factory-reset page.
 * Sends POST /api/reset with X-API-Key header to restore the app to seed state.
 * Shows a full-screen loader during the reset process.
 */
export default function ResetApp() {
  const [apiKey, setApiKey] = useState("");
  const [status, setStatus] = useState(null); // null | "loading" | "success" | "error"
  const [message, setMessage] = useState("");
  const [loaderStep, setLoaderStep] = useState(0);
  const [progress, setProgress] = useState(0);
  const abortRef = useRef(false);

  // Animate through steps during loading
  useEffect(() => {
    if (status !== "loading") return;
    abortRef.current = false;

    let cancelled = false;

    async function animate() {
      // Steps 0-4: simulated progress while the POST is in flight
      for (let i = 0; i <= 4; i++) {
        if (cancelled) return;
        setLoaderStep(i);
        setProgress(Math.round(((i + 1) / STEPS.length) * 80));
        await sleep(800 + Math.random() * 600);
      }
    }

    animate();
    return () => { cancelled = true; };
  }, [status]);

  async function handleReset(e) {
    e.preventDefault();
    if (!apiKey.trim()) {
      setStatus("error");
      setMessage("API key is required");
      return;
    }

    setStatus("loading");
    setLoaderStep(0);
    setProgress(0);
    setMessage("");

    try {
      const response = await axios.post(
        "/api/reset",
        {},
        { headers: { "X-API-Key": apiKey }, timeout: 60000 },
      );

      // POST succeeded — now wait for backend health
      setLoaderStep(5);
      setProgress(85);

      const healthy = await waitForHealth();

      if (healthy) {
        setProgress(100);
        await sleep(600);
        setStatus("success");
        setMessage(response.data?.message || "Application reset successfully");
      } else {
        setStatus("error");
        setMessage("Reset completed but backend did not recover in time. Reload the page.");
      }
    } catch (err) {
      setStatus("error");
      setMessage(
        err.response?.data?.detail || "Reset failed. Check your API key.",
      );
    }
  }

  return (
    <>
      {status === "loading" && (
        <FullScreenLoader step={STEPS[loaderStep]} progress={progress} />
      )}

      <main className="min-h-screen bg-neo-bg py-16">
        <Container className="max-w-xl">
          <h1 className="mb-2 font-black text-5xl uppercase tracking-tight">
            FACTORY RESET
          </h1>
          <p className="mb-8 text-lg font-bold">
            Restore the application to its original seed state. This will erase
            all data, uploads, and cache.
          </p>

          <Card
            header="RESET APPLICATION"
            headerColor="bg-neo-accent"
            shadow="shadow-neo-lg"
          >
            <form onSubmit={handleReset} className="flex flex-col gap-6 p-6">
              <Input
                label="API Key"
                type="password"
                placeholder="Enter your reset API key"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                autoComplete="off"
              />

              <Button
                type="submit"
                variant="dark"
                size="lg"
                fullWidth
                disabled={status === "loading"}
              >
                {status === "loading" ? "RESETTING..." : "RESET APPLICATION"}
              </Button>

              {status === "success" && (
                <div className="border-4 border-black bg-green-200 p-4 font-bold">
                  {message}
                </div>
              )}

              {status === "error" && (
                <div className="border-4 border-black bg-neo-accent p-4 font-bold">
                  {message}
                </div>
              )}
            </form>
          </Card>

          <div className="mt-6 border-4 border-black bg-neo-secondary p-4 shadow-neo-sm">
            <p className="font-bold uppercase">Warning</p>
            <p className="text-sm font-bold">
              This action is irreversible. All users, orders, reviews, tickets,
              and uploaded files will be deleted and replaced with the original
              seed data.
            </p>
          </div>
        </Container>
      </main>
    </>
  );
}
