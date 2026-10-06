'use client';

import { FormEvent, useState } from 'react';
import { registerUser } from '../../lib/api';

export default function RegisterPage() {
  const [clinicName, setClinicName] = useState('');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [mobile, setMobile] = useState('');
  const [licenseNumber, setLicenseNumber] = useState('');
  const [issuingCouncil, setIssuingCouncil] = useState('');
  const [certificate, setCertificate] = useState<File | null>(null);
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      if (!certificate) throw new Error('Upload your dental license certificate to continue.');
      await registerUser({
        email,
        full_name: fullName,
        password,
        clinic_name: clinicName,
        dental_license_number: licenseNumber,
        issuing_council: issuingCouncil,
        license_certificate: certificate,
        ...(mobile ? { clinic_mobile: mobile } : {}),
      });
      setSubmitted(true);
    } catch (registrationError) {
      setError(registrationError instanceof Error ? registrationError.message : 'Unable to register.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen bg-black px-5 py-10 text-white flex items-center justify-center">
      <section className="w-full max-w-md border border-neutral-800 bg-neutral-950 p-8">
        <p className="text-xs font-mono tracking-widest text-neutral-400">GFI DENTAL OS</p>
        <h1 className="mt-3 text-2xl font-semibold">Create clinic account</h1>
        <p className="mt-2 text-sm text-neutral-400">Register your clinic workspace to continue.</p>
        {submitted ? (
          <div role="status" className="mt-7 space-y-4 border border-amber-900/70 bg-amber-950/30 p-4">
            <h2 className="text-sm font-semibold text-amber-200">Verification pending</h2>
            <p className="text-sm leading-relaxed text-neutral-300">
              Your license documents were submitted for Dental Council verification. You can sign in after review is complete.
            </p>
            <a href="/login" className="inline-block text-sm text-white underline underline-offset-4">Return to sign in</a>
          </div>
        ) : (
        <>
        <form onSubmit={handleSubmit} className="mt-7 space-y-4">
          <label className="block text-sm text-neutral-300">
            Clinic name
            <input
              required
              autoComplete="organization"
              value={clinicName}
              onChange={(event) => setClinicName(event.target.value)}
              className="mt-2 w-full border border-neutral-700 bg-black px-3 py-2.5 text-white outline-none focus:border-neutral-400"
            />
          </label>
          <label className="block text-sm text-neutral-300">
            Your name
            <input
              required
              autoComplete="name"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              className="mt-2 w-full border border-neutral-700 bg-black px-3 py-2.5 text-white outline-none focus:border-neutral-400"
            />
          </label>
          <label className="block text-sm text-neutral-300">
            Email
            <input
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="mt-2 w-full border border-neutral-700 bg-black px-3 py-2.5 text-white outline-none focus:border-neutral-400"
            />
          </label>
          <label className="block text-sm text-neutral-300">
            Dental council license number
            <input
              required
              minLength={4}
              maxLength={32}
              pattern="[A-Za-z0-9][A-Za-z0-9/-]{3,31}"
              value={licenseNumber}
              onChange={(event) => setLicenseNumber(event.target.value)}
              className="mt-2 w-full border border-neutral-700 bg-black px-3 py-2.5 text-white outline-none focus:border-neutral-400"
            />
          </label>
          <label className="block text-sm text-neutral-300">
            Issuing dental council
            <input
              required
              minLength={2}
              maxLength={120}
              value={issuingCouncil}
              onChange={(event) => setIssuingCouncil(event.target.value)}
              className="mt-2 w-full border border-neutral-700 bg-black px-3 py-2.5 text-white outline-none focus:border-neutral-400"
            />
          </label>
          <label className="block text-sm text-neutral-300">
            License certificate <span className="text-neutral-500">(PDF, PNG, or JPEG, up to 5 MB)</span>
            <input
              type="file"
              accept="application/pdf,image/png,image/jpeg"
              required
              onChange={(event) => setCertificate(event.target.files?.[0] ?? null)}
              className="mt-2 block w-full text-xs text-neutral-300 file:mr-3 file:border-0 file:bg-neutral-800 file:px-3 file:py-2 file:text-white"
            />
          </label>
          <label className="block text-sm text-neutral-300">
            Clinic mobile <span className="text-neutral-500">(optional, E.164)</span>
            <input
              type="tel"
              autoComplete="tel"
              pattern="\+[1-9][0-9]{7,14}"
              placeholder="+14155552671"
              value={mobile}
              onChange={(event) => setMobile(event.target.value)}
              className="mt-2 w-full border border-neutral-700 bg-black px-3 py-2.5 text-white outline-none focus:border-neutral-400"
            />
          </label>
          <label className="block text-sm text-neutral-300">
            Password
            <input
              type="password"
              autoComplete="new-password"
              minLength={8}
              maxLength={128}
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
            {submitting ? 'Creating account...' : 'Register clinic'}
          </button>
        </form>
        <p className="mt-6 text-sm text-neutral-400">
          Already registered? <a href="/login" className="text-white underline underline-offset-4">Sign in</a>
        </p>
        </>
        )}
      </section>
    </main>
  );
}