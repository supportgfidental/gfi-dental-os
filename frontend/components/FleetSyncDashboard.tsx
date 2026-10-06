'use client';

import { FormEvent, useEffect, useState } from 'react';
import { Cloud, CloudOff, Loader2, RefreshCw, Smartphone, Trash2 } from 'lucide-react';
import { getFleetBranches, type FleetBranch, type FleetEntityType } from '../lib/api';
import {
  discardFleetQueueItem,
  getFleetIdentitySummary,
  getFleetQueueSummary,
  queueFleetDiff,
  registerFleetDevice,
  syncFleetQueue,
  type FleetQueueSummary,
} from '../lib/fleetSync';

export default function FleetSyncDashboard() {
  const [online, setOnline] = useState(true);
  const [identity, setIdentity] = useState<Awaited<ReturnType<typeof getFleetIdentitySummary>>>(null);
  const [branches, setBranches] = useState<FleetBranch[]>([]);
  const [queue, setQueue] = useState<FleetQueueSummary[]>([]);
  const [locationName, setLocationName] = useState('');
  const [entityType, setEntityType] = useState<FleetEntityType>('appointment');
  const [recordId, setRecordId] = useState('');
  const [changes, setChanges] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    const refresh = async () => {
      try {
        const [savedIdentity, savedQueue] = await Promise.all([
          getFleetIdentitySummary(),
          getFleetQueueSummary(),
        ]);
        if (!active) return;
        setIdentity(savedIdentity);
        setQueue(savedQueue);
        if (window.localStorage.getItem('access_token')) {
          setBranches(await getFleetBranches());
        }
      } catch (loadError) {
        if (active) setError(loadError instanceof Error ? loadError.message : 'Unable to load fleet state.');
      }
    };
    const onOnline = async () => {
      setOnline(true);
      setMessage('Connection restored. Attempting to sync queued changes...');
      try {
        const queued = await getFleetQueueSummary();
        if (queued.some((item) => item.state === 'queued')) await syncFleetQueue();
        await refresh();
        if (active) setMessage('Connection restored. Sync queue refreshed.');
      } catch (syncError) {
        if (active) setError(syncError instanceof Error ? syncError.message : 'Automatic sync failed.');
      }
    };
    const onOffline = () => {
      setOnline(false);
      setMessage('Offline mode. New diffs will be encrypted and queued on this device.');
    };

    setOnline(navigator.onLine);
    void refresh();
    window.addEventListener('online', onOnline);
    window.addEventListener('offline', onOffline);
    return () => {
      active = false;
      window.removeEventListener('online', onOnline);
      window.removeEventListener('offline', onOffline);
    };
  }, []);

  async function refreshFleetState() {
    const [savedIdentity, savedQueue, branchList] = await Promise.all([
      getFleetIdentitySummary(),
      getFleetQueueSummary(),
      getFleetBranches(),
    ]);
    setIdentity(savedIdentity);
    setQueue(savedQueue);
    setBranches(branchList);
  }

  async function handleRegisterBranch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || !online) return;
    setBusy(true);
    setError('');
    setMessage('Registering this device signing key with the clinic...');
    try {
      const registered = await registerFleetDevice(locationName.trim());
      setIdentity(registered);
      setLocationName(registered.locationName);
      await refreshFleetState();
      setMessage('Branch device registered. Its signing key remains on this device.');
    } catch (registerError) {
      setError(registerError instanceof Error ? registerError.message : 'Unable to register branch device.');
    } finally {
      setBusy(false);
    }
  }

  async function handleQueueDiff(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!identity) {
      setError('Register this branch device before queuing clinical diffs.');
      return;
    }
    setError('');
    try {
      const parsed: unknown = JSON.parse(changes);
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error('Changes must be a JSON object.');
      }
      await queueFleetDiff(entityType, recordId.trim(), parsed as Record<string, unknown>);
      setQueue(await getFleetQueueSummary());
      setRecordId('');
      setChanges('');
      setMessage('Change encrypted and queued locally.');
    } catch (queueError) {
      setError(queueError instanceof Error ? queueError.message : 'Unable to queue this change.');
    }
  }

  async function handleSync() {
    if (!online || busy) return;
    setBusy(true);
    setError('');
    setMessage('Signing and sending queued delta batch...');
    try {
      const result = await syncFleetQueue();
      await refreshFleetState();
      setMessage(result
        ? `Sync ${result.sync_status}: ${result.applied_count} applied, ${result.conflict_count} need review.`
        : 'No queued changes are ready to sync.');
    } catch (syncError) {
      setError(syncError instanceof Error ? syncError.message : 'Fleet sync failed.');
    } finally {
      setBusy(false);
    }
  }

  async function handleDiscardConflict(transactionId: string) {
    await discardFleetQueueItem(transactionId);
    setQueue(await getFleetQueueSummary());
  }

  const queuedCount = queue.filter((item) => item.state === 'queued').length;
  const conflictCount = queue.filter((item) => item.state === 'conflict').length;
  const connectivityLabel = !online
    ? 'Offline'
    : queuedCount > 0
      ? 'Pending Sync Queue'
      : 'Online';

  return (
    <section className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-neutral-800 pb-4">
        <div>
          <p className="text-xs font-mono uppercase tracking-widest text-cyan-300">Fleet & Offline Sync</p>
          <h2 className="mt-2 text-lg font-semibold text-white">Branch device command</h2>
          <p className="mt-1 text-xs text-neutral-400">Local changes are encrypted in this browser and signed before upload.</p>
        </div>
        <div className={`inline-flex items-center gap-2 border px-3 py-2 text-xs ${online ? 'border-emerald-900 bg-emerald-950/30 text-emerald-200' : 'border-amber-900 bg-amber-950/30 text-amber-200'}`}>
          {online ? <Cloud className="h-4 w-4" /> : <CloudOff className="h-4 w-4" />}
          {connectivityLabel}
          {conflictCount > 0 && <span>· {conflictCount} conflicts</span>}
        </div>
      </header>

      {!identity && (
        <form onSubmit={handleRegisterBranch} className="flex flex-col gap-3 border border-neutral-800 bg-neutral-950 p-5 sm:flex-row sm:items-end">
          <label className="flex-1 text-xs text-neutral-300">
            Branch or mobile unit name
            <input
              required
              maxLength={200}
              value={locationName}
              onChange={(event) => setLocationName(event.target.value)}
              placeholder="Mobile Unit 04"
              className="mt-2 w-full border border-neutral-700 bg-black px-3 py-2.5 text-sm text-white outline-none focus:border-neutral-400"
            />
          </label>
          <button type="submit" disabled={busy || !online} className="inline-flex min-h-10 items-center gap-2 bg-white px-4 py-2.5 text-sm font-medium text-black disabled:opacity-50">
            {busy && <Loader2 className="h-4 w-4 animate-spin" />} Register this device
          </button>
        </form>
      )}

      {identity && (
        <div className="border border-neutral-800 bg-neutral-950 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <Smartphone className="h-5 w-5 text-neutral-300" />
              <div>
                <h3 className="text-sm font-semibold text-white">This device · {identity.locationName}</h3>
                <p className="mt-1 font-mono text-[10px] text-neutral-500">Branch {identity.branchId} · key {identity.deviceFingerprint.slice(0, 20)}...</p>
              </div>
            </div>
            <span className="text-xs text-neutral-400">{queuedCount} queued · {conflictCount} conflicts</span>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(280px,0.75fr)]">
        <form onSubmit={handleQueueDiff} className="space-y-4 border border-neutral-800 bg-neutral-950 p-5">
          <div>
            <h3 className="text-sm font-semibold text-white">Queue offline transaction diff</h3>
            <p className="mt-1 text-xs text-neutral-500">Only appointment/treatment updates and inventory quantity deltas are accepted.</p>
          </div>
          <label className="block text-xs text-neutral-300">
            Record type
            <select value={entityType} onChange={(event) => setEntityType(event.target.value as FleetEntityType)} className="mt-2 w-full border border-neutral-700 bg-black px-3 py-2.5 text-sm text-white">
              <option value="appointment">Appointment</option>
              <option value="treatment">Treatment plan</option>
              <option value="inventory">Inventory item</option>
            </select>
          </label>
          <label className="block text-xs text-neutral-300">
            {entityType === 'inventory' ? 'Inventory SKU' : 'Server record ID'}
            <input required value={recordId} onChange={(event) => setRecordId(event.target.value)} className="mt-2 w-full border border-neutral-700 bg-black px-3 py-2.5 text-sm text-white" />
          </label>
          <label className="block text-xs text-neutral-300">
            Change diff (JSON)
            <textarea
              required
              rows={5}
              value={changes}
              onChange={(event) => setChanges(event.target.value)}
              placeholder={entityType === 'inventory' ? '{ "quantity_delta": -1 }' : '{ "status": "Confirmed" }'}
              className="mt-2 w-full resize-y border border-neutral-700 bg-black px-3 py-2.5 font-mono text-sm text-white"
            />
          </label>
          <button type="submit" disabled={!identity} className="min-h-10 bg-neutral-100 px-4 py-2.5 text-sm font-medium text-black disabled:opacity-50">
            Encrypt and queue locally
          </button>
        </form>

        <section className="space-y-4 border border-neutral-800 bg-neutral-950 p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-white">Registered branches</h3>
              <p className="mt-1 text-xs text-neutral-500">Clinic-owned devices and latest successful batch time.</p>
            </div>
            <button type="button" title="Refresh branches" onClick={() => void refreshFleetState().catch((e) => setError(e.message))} disabled={busy} className="p-2 text-neutral-300 hover:bg-neutral-800 disabled:opacity-50">
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>
          {branches.length === 0 ? (
            <p className="text-sm text-neutral-500">No registered mobile units or branches.</p>
          ) : (
            <ul className="space-y-3">
              {branches.map((branch) => (
                <li key={branch.branch_id} className="border-t border-neutral-800 pt-3">
                  <p className="text-sm text-neutral-200">{branch.location_name} {!branch.is_active && <span className="text-rose-300">· Disabled</span>}</p>
                  <p className="mt-1 font-mono text-[10px] text-neutral-500">{branch.last_sync_timestamp ? new Date(branch.last_sync_timestamp).toLocaleString() : 'Never synced'}</p>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-white">Local sync queue</h3>
            <p className="mt-1 text-xs text-neutral-500">Server-wins conflicts remain local for review and are not retried automatically.</p>
          </div>
          <button type="button" onClick={() => void handleSync()} disabled={!online || busy || queuedCount === 0} className="inline-flex min-h-10 items-center gap-2 bg-white px-4 py-2.5 text-sm font-medium text-black disabled:opacity-50">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Force Sync Delta
          </button>
        </div>
        {message && <p role="status" className="text-sm text-emerald-200">{message}</p>}
        {error && <p role="alert" className="border border-red-900 bg-red-950/30 p-3 text-sm text-red-200">{error}</p>}
        {queue.length === 0 ? (
          <div className="border border-neutral-800 bg-neutral-950 p-4 text-sm text-neutral-500">Queue is empty.</div>
        ) : (
          <ul className="divide-y divide-neutral-800 border border-neutral-800 bg-neutral-950">
            {queue.map((item) => (
              <li key={item.transaction_id} className="flex flex-wrap items-center justify-between gap-3 p-4">
                <div>
                  <p className="text-sm text-neutral-200">{item.entity_type} · {item.record_id}</p>
                  <p className="mt-1 font-mono text-[10px] text-neutral-500">{item.client_updated_at} · {item.state}</p>
                  {item.conflict_detail && <p className="mt-1 text-xs text-amber-200">{item.conflict_detail}</p>}
                </div>
                {item.state === 'conflict' && (
                  <button type="button" onClick={() => void handleDiscardConflict(item.transaction_id).catch((e) => setError(e.message))} title="Discard local conflict" className="p-2 text-neutral-400 hover:bg-neutral-800 hover:text-white">
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </section>
  );
}