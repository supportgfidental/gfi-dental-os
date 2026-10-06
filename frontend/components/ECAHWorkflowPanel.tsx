'use client';

import { FormEvent, useState } from 'react';
import { Loader2, Sparkles } from 'lucide-react';
import {
  ECAHAgentResult,
  ECAHWorkflowResponse,
  executeECAHWorkflow,
} from '../lib/api';

const agents = [
  { id: 'emergency', name: 'Emergency Triage', color: 'border-rose-800 bg-rose-950/30' },
  { id: 'consult', name: 'Clinical Consultation', color: 'border-sky-800 bg-sky-950/30' },
  { id: 'audit', name: 'Billing & Compliance Audit', color: 'border-amber-800 bg-amber-950/30' },
  { id: 'handover', name: 'Shift Handover', color: 'border-emerald-800 bg-emerald-950/30' },
] as const;

function AgentCard({ agent }: { agent: ECAHAgentResult }) {
  const details = agents.find((item) => item.id === agent.agent_type);
  return (
    <article className={`min-w-0 border p-5 ${details?.color ?? 'border-neutral-800 bg-neutral-950'}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-white">{details?.name ?? agent.agent_type}</h3>
          <p className="mt-1 text-[11px] uppercase text-neutral-400">{agent.status}</p>
        </div>
        <span className="shrink-0 font-mono text-xs text-neutral-300">{agent.execution_time_ms} ms</span>
      </div>
      {agent.output ? (
        <pre className="mt-4 max-h-80 overflow-auto whitespace-pre-wrap break-words text-xs leading-relaxed text-neutral-200">
          {JSON.stringify(agent.output, null, 2)}
        </pre>
      ) : (
        <p className="mt-4 text-xs text-neutral-400">{agent.error ?? 'No result returned.'}</p>
      )}
    </article>
  );
}

export default function ECAHWorkflowPanel() {
  const [patientId, setPatientId] = useState('');
  const [patientContext, setPatientContext] = useState('');
  const [region, setRegion] = useState('');
  const [tariffContext, setTariffContext] = useState('');
  const [complianceRules, setComplianceRules] = useState('');
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<ECAHWorkflowResponse | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (running) return;
    setRunning(true);
    setError('');
    setResult(null);
    try {
      const response = await executeECAHWorkflow({
        operation_type: 'ECAH_FULL_SWEEP',
        ...(patientId ? { patient_id: Number(patientId) } : {}),
        patient_context: patientContext,
        clinic_parameters: {
          ...(region ? { region } : {}),
          ...(tariffContext ? { insurance_tariff_context: tariffContext } : {}),
          ...(complianceRules ? { compliance_rules: complianceRules } : {}),
        },
      });
      setResult(response);
    } catch (workflowError) {
      setError(workflowError instanceof Error ? workflowError.message : 'Unable to execute the workflow.');
    } finally {
      setRunning(false);
    }
  }

  return (
    <section className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-neutral-800 pb-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono uppercase text-cyan-300">
            <Sparkles className="h-4 w-4" /> ECAH Neural Mesh
          </div>
          <h2 className="mt-2 text-lg font-semibold text-white">Emergency · Consult · Audit · Handover</h2>
          <p className="mt-1 text-xs text-neutral-400">Four independent agents run concurrently. Outputs require clinician review.</p>
        </div>
        {result && (
          <span className="font-mono text-xs text-neutral-400">
            {result.status} · {result.execution_time_ms} ms total
          </span>
        )}
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
          Region for audit context
          <input
            maxLength={120}
            value={region}
            onChange={(event) => setRegion(event.target.value)}
            className="mt-2 w-full border border-neutral-700 bg-black px-3 py-2.5 text-sm text-white outline-none focus:border-neutral-400"
          />
        </label>
        <label className="text-xs text-neutral-300 md:col-span-2">
          Patient context
          <textarea
            required
            maxLength={4000}
            rows={4}
            value={patientContext}
            onChange={(event) => setPatientContext(event.target.value)}
            placeholder="Describe reported symptoms or the workflow context. Avoid unnecessary identifying details."
            className="mt-2 w-full resize-y border border-neutral-700 bg-black px-3 py-2.5 text-sm text-white outline-none focus:border-neutral-400"
          />
        </label>
        <label className="text-xs text-neutral-300">
          Insurance tariff context
          <textarea
            maxLength={4000}
            rows={3}
            value={tariffContext}
            onChange={(event) => setTariffContext(event.target.value)}
            className="mt-2 w-full resize-y border border-neutral-700 bg-black px-3 py-2.5 text-sm text-white outline-none focus:border-neutral-400"
          />
        </label>
        <label className="text-xs text-neutral-300">
          Compliance rules
          <textarea
            maxLength={4000}
            rows={3}
            value={complianceRules}
            onChange={(event) => setComplianceRules(event.target.value)}
            className="mt-2 w-full resize-y border border-neutral-700 bg-black px-3 py-2.5 text-sm text-white outline-none focus:border-neutral-400"
          />
        </label>
        <div className="md:col-span-2">
          <button
            type="submit"
            disabled={running || !patientContext.trim()}
            className="inline-flex min-h-10 items-center gap-2 bg-white px-4 py-2.5 text-sm font-medium text-black disabled:cursor-not-allowed disabled:opacity-50"
          >
            {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            {running ? 'Running four agents...' : 'Execute Full ECAH Sweep'}
          </button>
        </div>
      </form>

      {running && (
        <div role="status" aria-live="polite" className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {agents.map((agent) => (
            <div key={agent.id} className={`flex items-center gap-3 border p-4 text-sm text-neutral-200 ${agent.color}`}>
              <Loader2 className="h-4 w-4 animate-spin" /> {agent.name} running
            </div>
          ))}
        </div>
      )}

      {error && <p role="alert" className="border border-red-900 bg-red-950/30 p-4 text-sm text-red-200">{error}</p>}

      {result && (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {result.agents.map((agent) => <AgentCard key={agent.agent_type} agent={agent} />)}
        </div>
      )}
    </section>
  );
}