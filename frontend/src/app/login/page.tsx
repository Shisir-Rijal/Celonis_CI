"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import Button from "../../../components/ui/Button";
import { useAuthStore } from "@/store/authStore";

export default function LoginPage() {
  const router = useRouter();
  const { login, isAuthenticated, hydrate } = useAuthStore();

  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    if (isAuthenticated) {
      router.replace("/");
    }
  }, [isAuthenticated, router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    if (!password.trim()) {
      setError("Please enter your password.");
      return;
    }

    setError(null);
    setLoading(true);

    try {
      await login(password);
      router.replace("/");
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Something went wrong.";
      if (message.includes("401") || message.includes("Unauthorized")) {
        setError("Incorrect password. Please try again.");
      } else if (
        message.includes("fetch") ||
        message.includes("NetworkError") ||
        message.includes("Failed to fetch")
      ) {
        setError("Cannot reach the server. Check your connection.");
      } else {
        setError("Login failed. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-neutral-grey-00 px-4">
      <div className="w-full max-w-sm">

        {/* Card */}
        <div className="bg-primary-white rounded-2xl shadow-sm border border-neutral-grey-10 px-8 py-10 flex flex-col gap-8">

          {/* Logo */}
          <div className="flex flex-col items-center gap-3">
            <div className="w-32">
              <Image
                src="/celonis_logo.png"
                alt="Celonis"
                width={128}
                height={128}
                className="w-full h-auto object-contain"
                priority
              />
            </div>
            <p className="text-neutral-grey-20 text-center text-sm leading-relaxed">
              Internal Competitor Intelligence Dashboard
            </p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="flex flex-col gap-5">
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="password"
                className="text-sm font-medium text-primary-black"
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  if (error) setError(null);
                }}
                placeholder="Enter your password"
                autoComplete="current-password"
                autoFocus
                className="w-full px-4 py-2.5 rounded-lg border border-neutral-grey-10 bg-primary-white text-primary-black text-sm placeholder:text-neutral-grey-10 focus:outline-none focus:ring-2 focus:ring-primary-black focus:border-transparent transition"
              />
            </div>

            {/* Error */}
            {error && (
              <p className="text-error text-sm -mt-1" role="alert">
                {error}
              </p>
            )}

            <Button
              type="submit"
              size="md"
              disabled={loading}
              onClick={undefined}
            >
              <span className="w-full text-center">
                {loading ? "Signing in…" : "Sign in"}
              </span>
            </Button>
          </form>
        </div>

      </div>
    </div>
  );
}
