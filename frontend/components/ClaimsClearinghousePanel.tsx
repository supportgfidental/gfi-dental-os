'use client';

import { FormEvent, useState } from 'react';
import { Loader2, ReceiptText } from 'lucide-react';
import { auditClaim, type ClaimsAuditResponse } from '../lib/api';

const statusStyles: Record<ClaimsAuditResponse['claim_validity_status'], string> = {
  APPROVED: 'border-emerald-800 bg-emerald-950/30 text-emerald-200',
  PENDING_DOCS: 'border-amber-800 bg-amber-950/30 text-amber-200',
  REJECTED_POLICY_MISMATCH: 'border-rose-800 bg-rose-950/30 text-rose-200',
};

export default function ClaimsClearinghousePanel() {
  const [patientId, setPatientId] = useState('');
  const [treatmentDescription, setTreatmentDescription] = useState('');
  const [procedureCodesText, setProcedureCodesText] = useState('');
  const [providerRules, setProviderRules] = useState('');
  const [regionalTariffsText, setRegionalTariffsText] = useState('');
  const [result, setResult] = useState<ClaimsAuditResponse | null>(null);
  const [error, setError] = useState('');
  const [running, setRunning] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (running) return;
    setError('');
    setResult(null);

    const procedureCodes = procedureCodesText
      .split(/[\s,]+/)
      .map((code) => code.trim().toUpperCase())
      .filter(Boolean);
    if (!procedureCodes.length || procedureCodes.some((code) => !/^D\d{4}$/.test(code))) {
      setError('Enter one or more CDT codes in the format D0120.');
      return;
    }

    let regionalTariffs: Record<string, number>;
    try {
      const parsed: unknown = JSON.parse(regionalTariffsText);
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error('Tariffs must be a JSON object.');
      }
      regionalTariffs = parsed as Record<string, number>;
      if (Object.values(regionalTariffs).some((amount) => typeof amount !== 'number' || !Number.isFinite(amount) || amount < 0)) {
        throw new Error('Tariff values must be non-negative numbers.');
      }
    } catch (parseError) {
      setError(parseError instanceof Error ? parseError.message : 'Enter valid regional tariff JSON.');
      return;
    }

    setRunning(true);
    try {
      const audit = await auditClaim({
        ...(patientId ? { patient_id: Number(patientId) } : {}),
        patient_treatment_description: treatmentDescription,
        procedure_codes: procedureCodes,
        insurance_provider_rules: providerRules,
        regional_tariffs: regionalTariffs,
      });
      setResult(audit);
    } catch (auditError) {
      setError(auditError instanceof Error ? auditError.message : 'Unable to audit this claim.');
    } finally {
      setRunning(false);
    }
  }

  return (
    <section className="space-y-6">
      <header className="border-b border-neutral-800 pb-4">
        <div className="flex items-center gap-2 text-xs font-mono uppercase text-cyan-300">
          <ReceiptText className="h-4 w-4" /> Claims Clearinghouse
        </div>
        <h2 className="mt-2 text-lg font-semibold text-white">Pre-submission compliance review</h2>
        <p className="mt-1 text-xs text-neutral-400">
          Projections use only supplied tariff amounts. This does not submit a claim or guarantee insurer payment.
        </p>
      </header>

      <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4 border border-neutral-800 bg-neutral-950 p-5 md:grid-cols-2">
        <label className="text-xs text-neutral-300">
          Patient record ID <span className="text-neutral-500">(optional, clinic-scoped)</span>
          <input
            type="number"
            min="1"
            value={patientId}
            onChange={(event) => setPatientId(event.target.value)}
            className="mt-2 w-full border border-neutral-700 bg-black px-3 py-2.5 text-sm text-white outline-none focus:border-neutral-400"
          />
        </label>
        <label className="text-xs text-neutral-300">
          CDT procedure codes
          <input
            required
            value={procedureCodesText}
            onChange={(event) => setProcedureCodesText(event.target.value)}
            placeholder="D0120, D1110"
            className="mt-2 w-full border border-neutral-700 bg-black px-3 py-2.5 text-sm text-white outline-none focus:border-neutral-400"
          />
        </label>
        <label className="text-xs text-neutral-300 md:col-span-2">
          Treatment description and clinical notes
          <textarea
            required
            maxLength={6000}
            rows={4}
            value={treatmentDescription}
            onChange={(event) => setTreatmentDescription(event.target.value)}
            className="mt-2 w-full resize-y border border-neutral-700 bg-black px-3 py-2.5 text-sm text-white outline-none focus:border-neutral-400"
          />
        </label>
        <label className="text-xs text-neutral-300">
          Insurance provider rules
          <textarea
            required
            maxLength={6000}
            rows={4}
            value={providerRules}
            onChange={(event) => setProviderRules(event.target.value)}
            className="mt-2 w-full resize-y border border-neutral-700 bg-black px-3 py-2.5 text-sm text-white outline-none focus:border-neutral-400"
          />
        </label>
        <label className="text-xs text-neutral-300">
          Regional CDT tariff amounts (JSON)
          <textarea
            required
            rows={4}
            value={regionalTariffsText}
            onChange={(event) => setRegionalTariffsText(event.target.value)}
            placeholder={'{ "D0120": 45.00, "D1110": 82.50 }'}
            className="mt-2 w-full resize-y border border-neutral-700 bg-black px-3 py-2.5 font-mono text-sm text-white outline-none focus:border-neutral-400"
          />
        </label>
        <div className="md:col-span-2">
          <button
            type="submit"
            disabled={running}
            className="inline-flex min-h-10 items-center gap-2 bg-white px-4 py-2.5 text-sm font-medium text-black disabled:cursor-not-allowed disabled:opacity-50"
          >
            {running && <Loader2 className="h-4 w-4 animate-spin" />}
            {running ? 'Reviewing claim...' : 'Audit and project reimbursement'}
          </button>
        </div>
      </form>

      {error && <p role="alert" className="border border-red-900 bg-red-950/30 p-4 text-sm text-red-200">{error}</p>}

      {result && (
        <section aria-live="polite" className="space-y-4">
          <div className={`border p-5 ${statusStyles[result.claim_validity_status]}`}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-[11px] font-mono uppercase">Audit result · #{result.audit_id}</p>
                <h3 className="mt-1 text-lg font-semibold">{result.claim_validity_status.replaceAll('_', ' ')}</h3>
              </div>
              <div className="text-right">
                <p className="text-[11px] uppercase">Projected payout</p>
                <p className="mt-1 font-mono text-xl">{result.estimated_payout.toFixed(2)}</p>
                <p className="text-[10px]">tariff currency · estimate only</p>
              </div>
            </div>
            <p className="mt-3 text-xs">Confidence: {result.confidence_score}%</p>
            <p className="mt-1 text-xs">Billable code projection: {result.billable_codes.join(', ') || 'None identified'}</p>
          </div>
          <div className="border border-neutral-800 bg-neutral-950 p-5">
            <h3 className="text-sm font-semibold text-white">Compliance notes</h3>
            {result.compliance_notes.length ? (
              <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-neutral-300">
                {result.compliance_notes.map((note, index) => <li key={`${index}-${note}`}>{note}</li>)}
              </ul>
            ) : (
              <p className="mt-3 text-sm text-neutral-400">No anomalies were identified against the supplied rules.</p>
            )}
          </div>
        </section>
      )}
    </section>
  );
}