'use client';

import { useState } from 'react';
import { Check, Download, Loader2, RefreshCw, ShieldAlert, X } from 'lucide-react';
import {
  decideLicenseReview,
  downloadLicenseCertificate,
  getLicenseReviewAudit,
  getPendingLicenseReviews,
  getVerifiedLicenseAccounts,
  type LicenseReviewAuditEntry,
  type LicenseReviewEntry,
} from '../../lib/api';

type ReviewView = 'pending' | 'verified' | 'audit';

export default function LicenseReviewPage() {
  const [reviewerKey, setReviewerKey] = useState('');
  const [view, setView] = useState<ReviewView>('pending');
  const [pendingAccounts, setPendingAccounts] = useState<LicenseReviewEntry[]>([]);
  const [verifiedAccounts, setVerifiedAccounts] = useState<LicenseReviewEntry[]>([]);
  const [auditHistory, setAuditHistory] = useState<LicenseReviewAuditEntry[]>([]);
  const [reviewReason, setReviewReason] = useState('');
  const [error, setError] = useState('');
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);

  async function loadView(nextView: ReviewView = view) {
    if (!reviewerKey) {
      setError('Enter the configured reviewer key to continue.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      if (nextView === 'pending') setPendingAccounts(await getPendingLicenseReviews(reviewerKey));
      if (nextView === 'verified') setVerifiedAccounts(await getVerifiedLicenseAccounts(reviewerKey));
      if (nextView === 'audit') setAuditHistory(await getLicenseReviewAudit(reviewerKey));
      setView(nextView);
      setLoaded(true);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load review data.');
      setLoaded(false);
    } finally {
      setBusy(false);
    }
  }

  async function handleDecision(userId: number, decision: 'VERIFIED' | 'REJECTED' | 'REVOKED') {
    if (reviewReason.trim().length < 5) {
      setError('Enter a review reason of at least five characters.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      await decideLicenseReview(reviewerKey, userId, decision, reviewReason.trim());
      setReviewReason('');
      await loadView(view);
    } catch (decisionError) {
      setError(decisionError instanceof Error ? decisionError.message : 'Unable to save the review decision.');
    } finally {
      setBusy(false);
    }
  }

  async function handleCertificateDownload(userId: number) {
    setError('');
    try {
      const certificate = await downloadLicenseCertificate(reviewerKey, userId);
      const objectUrl = URL.createObjectURL(certificate);
      const anchor = document.createElement('a');
      anchor.href = objectUrl;
      anchor.download = `license-certificate-${userId}`;
      anchor.click();
      URL.revokeObjectURL(objectUrl);
    } catch (downloadError) {
      setError(downloadError instanceof Error ? downloadError.message : 'Unable to download certificate.');
    }
  }

  const accounts = view === 'pending' ? pendingAccounts : verifiedAccounts;

  return (
    <main className="min-h-screen bg-black px-5 py-10 text-white">
      <div className="mx-auto max-w-6xl space-y-7">
        <header className="flex flex-wrap items-end justify-between gap-4 border-b border-neutral-800 pb-5">
          <div>
            <p className="text-xs font-mono uppercase tracking-widest text-neutral-400">Restricted operations</p>
            <h1 className="mt-2 text-2xl font-semibold">Dental License Review</h1>
            <p className="mt-2 text-sm text-neutral-400">Review submitted credentials and record approval, rejection, or revocation.</p>
          </div>
          <a href="/dashboard" className="text-sm text-neutral-300 underline underline-offset-4">Clinical dashboard</a>
        </header>

        <p className="border border-amber-900/70 bg-amber-950/20 p-4 text-sm leading-relaxed text-amber-100">
          Verify the license with the issuing council and inspect the original certificate before approval. Format checks alone do not establish authenticity.
        </p>

        <section className="grid grid-cols-1 gap-4 border border-neutral-800 bg-neutral-950 p-5 md:grid-cols-[1fr_auto]">
          <label className="text-xs text-neutral-300">
            Reviewer key
            <input
              type="password"
              autoComplete="off"
              value={reviewerKey}
              onChange={(event) => setReviewerKey(event.target.value)}
              className="mt-2 w-full border border-neutral-700 bg-black px-3 py-2.5 text-sm text-white outline-none focus:border-neutral-400"
            />
          </label>
          <button
            type="button"
            onClick={() => void loadView(view)}
            disabled={busy || !reviewerKey}
            className="self-end inline-flex min-h-10 items-center justify-center gap-2 bg-white px-4 py-2.5 text-sm font-medium text-black disabled:opacity-50"
          >
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Load review data
          </button>
        </section>

        <nav className="flex flex-wrap gap-2" aria-label="License review views">
          {([['pending', 'Pending applicants'], ['verified', 'Verified accounts'], ['audit', 'Decision history']] as const).map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => void loadView(id)}
              disabled={busy || !reviewerKey}
              aria-pressed={view === id}
              className={`border px-3 py-2 text-xs ${view === id ? 'border-white bg-white text-black' : 'border-neutral-800 text-neutral-300 hover:border-neutral-600'}`}
            >
              {label}
            </button>
          ))}
        </nav>

        {error && <p role="alert" className="border border-red-900 bg-red-950/30 p-4 text-sm text-red-200">{error}</p>}

        {!loaded ? (
          <div className="border border-neutral-800 bg-neutral-950 p-6 text-sm text-neutral-400">
            Reviewer authentication is required to view license records.
          </div>
        ) : view === 'audit' ? (
          auditHistory.length === 0 ? (
            <div className="border border-neutral-800 bg-neutral-950 p-6 text-sm text-neutral-400">No review decisions recorded.</div>
          ) : (
            <div className="overflow-x-auto border border-neutral-800">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead className="bg-neutral-950 text-[11px] uppercase text-neutral-500">
                  <tr>
                    <th className="px-4 py-3">Reviewed</th><th className="px-4 py-3">Reviewer</th>
                    <th className="px-4 py-3">Account</th><th className="px-4 py-3">Decision</th>
                    <th className="px-4 py-3">Reason</th><th className="px-4 py-3">Source IP</th>
                  </tr>
                </thead>
                <tbody>
                  {auditHistory.map((entry) => (
                    <tr key={entry.id} className="border-t border-neutral-800 text-neutral-300">
                      <td className="px-4 py-3">{new Date(entry.created_at).toLocaleString()}</td>
                      <td className="px-4 py-3">{entry.reviewer_id}</td>
                      <td className="px-4 py-3">#{entry.user_id}</td>
                      <td className="px-4 py-3">{entry.new_status}</td>
                      <td className="px-4 py-3">{entry.review_reason}</td>
                      <td className="px-4 py-3 font-mono text-xs">{entry.ip_address}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : accounts.length === 0 ? (
          <div className="border border-neutral-800 bg-neutral-950 p-6 text-sm text-neutral-400">
            {view === 'pending' ? 'No pending applicants.' : 'No verified accounts found.'}
          </div>
        ) : (
          <div className="space-y-4">
            {view !== 'audit' && (
              <label className="block max-w-3xl text-xs text-neutral-300">
                Reviewer rationale (required for every decision)
                <textarea
                  required
                  minLength={5}
                  maxLength={2000}
                  rows={2}
                  value={reviewReason}
                  onChange={(event) => setReviewReason(event.target.value)}
                  className="mt-2 w-full border border-neutral-700 bg-black px-3 py-2.5 text-sm text-white outline-none focus:border-neutral-400"
                />
              </label>
            )}
            {accounts.map((account) => (
              <article key={account.user_id} className="border border-neutral-800 bg-neutral-950 p-5">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="space-y-1 text-sm">
                    <h2 className="font-semibold text-white">{account.clinic_name}</h2>
                    <p className="text-neutral-300">{account.full_name} · {account.email}</p>
                    <p className="font-mono text-xs text-neutral-400">License {account.license_number} · {account.issuing_council}</p>
                    <p className="text-xs text-neutral-500">User: {account.user_status} · Clinic: {account.clinic_status}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => void handleCertificateDownload(account.user_id)}
                    disabled={!account.certificate_available || busy}
                    className="inline-flex items-center gap-2 border border-neutral-700 px-3 py-2 text-xs text-neutral-200 disabled:opacity-40"
                  >
                    <Download className="h-4 w-4" /> View certificate
                  </button>
                </div>
                <div className="mt-5 flex flex-wrap gap-2">
                  {view === 'pending' ? (
                    <>
                      <button type="button" onClick={() => void handleDecision(account.user_id, 'VERIFIED')} disabled={busy || !reviewReason.trim()} className="inline-flex items-center gap-2 bg-emerald-300 px-3 py-2 text-xs font-semibold text-black disabled:opacity-40">
                        <Check className="h-4 w-4" /> Approve and verify
                      </button>
                      <button type="button" onClick={() => void handleDecision(account.user_id, 'REJECTED')} disabled={busy || !reviewReason.trim()} className="inline-flex items-center gap-2 border border-rose-800 px-3 py-2 text-xs text-rose-200 disabled:opacity-40">
                        <X className="h-4 w-4" /> Reject
                      </button>
                    </>
                  ) : (
                    <button type="button" onClick={() => void handleDecision(account.user_id, 'REVOKED')} disabled={busy || !reviewReason.trim()} className="inline-flex items-center gap-2 border border-rose-800 px-3 py-2 text-xs text-rose-200 disabled:opacity-40">
                      <ShieldAlert className="h-4 w-4" /> Revoke license access
                    </button>
                  )}
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}