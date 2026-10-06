'use client';

import { FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ApiError, loginUser } from '../../lib/api';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [pendingVerification, setPendingVerification] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await loginUser(email, password);
      router.replace('/dashboard');
    } catch (loginError) {
      if (
        loginError instanceof ApiError
        && loginError.status === 403
        && loginError.message.includes('Pending Dental Council Verification')
      ) {
        setPendingVerification(true);
      } else {
        setError(loginError instanceof Error ? loginError.message : 'Unable to sign in.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen bg-black text-white flex items-center justify-center px-5">
      <section className="w-full max-w-sm border border-neutral-800 bg-neutral-950 p-8">
        <p className="text-xs font-mono tracking-widest text-neutral-400">GFI DENTAL OS</p>
        <h1 className="mt-3 text-2xl font-semibold">Sign in</h1>
        <p className="mt-2 text-sm text-neutral-400">Access your clinic workspace.</p>
        <form onSubmit={handleSubmit} className="mt-8 space-y-5">
          <label className="block text-sm text-neutral-300">
            Email
            <input
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="mt-2 w-full border border-neutral-700 bg-black px-3 py-2.5 text-white outline-none focus:border-neutral-400"
            />
          </label>
          <label className="block text-sm text-neutral-300">
            Password
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="mt-2 w-full border border-neutral-700 bg-black px-3 py-2.5 text-white outline-none focus:border-neutral-400"
            />
          </label>
          {error && <p role="alert" className="text-sm text-red-400">{error}</p>}
          <button
            type="submit"
            disabled={submitting}
            className="w-full bg-white px-4 py-2.5 text-sm font-medium text-black disabled:opacity-50"
          >
            {submitting ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
        <p className="mt-6 text-sm text-neutral-400">
          New to GFI? <a href="/register" className="text-white underline underline-offset-4">Create a clinic account</a>
        </p>
      </section>
      {pendingVerification && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 px-5" role="presentation">
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="verification-required-title"
            className="w-full max-w-md border border-amber-800 bg-neutral-950 p-6 shadow-2xl"
          >
            <h2 id="verification-required-title" className="text-lg font-semibold text-amber-200">
              Verification required
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-neutral-200">
              Account Pending Dental Council Verification. Unauthorized access is restricted.
            </p>
            <button
              type="button"
              onClick={() => setPendingVerification(false)}
              className="mt-6 bg-white px-4 py-2 text-sm font-medium text-black"
            >
              Close
            </button>
          </section>
        </div>
      )}
    </main>
  );
}