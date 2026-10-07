"use client";

import React, { useState, useEffect } from "react";
import { agentApi } from "@/lib/api";
import { CheckCircle2, AlertCircle, Undo2, ShieldAlert } from "lucide-react";

type ToothState = "Healthy" | "Caries" | "Crown" | "Root Canal" | "Missing";

interface OdontogramProps {
  clinicId: number;
  patientId: number;
}

const toothColors: Record<ToothState, string> = {
  Healthy: "bg-neutral-950 border-neutral-700 text-neutral-400",
  Caries: "bg-red-500/20 border-red-500 text-red-400",
  Crown: "bg-amber-500/20 border-amber-500 text-amber-400",
  "Root Canal": "bg-purple-500/20 border-purple-500 text-purple-400",
  Missing: "bg-neutral-800 border-neutral-600 text-neutral-600",
};

const STORAGE_KEY = "gfi_odontogram_state";

export default function Odontogram({ clinicId, patientId }: OdontogramProps) {
  const upperRight = [18, 17, 16, 15, 14, 13, 12, 11];
  const upperLeft = [21, 22, 23, 24, 25, 26, 27, 28];
  const lowerRight = [48, 47, 46, 45, 44, 43, 42, 41];
  const lowerLeft = [31, 32, 33, 34, 35, 36, 37, 38];
  const allTeeth = [...upperRight, ...upperLeft, ...lowerRight, ...lowerLeft];

  const loadCached = (): Record<number, ToothState> => {
    if (typeof window === "undefined") return {};
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) return JSON.parse(raw);
    } catch {}
    return Object.fromEntries(allTeeth.map((t) => [t, "Healthy" as ToothState]));
  };

  const [teeth, setTeeth] = useState<Record<number, ToothState>>(loadCached);
  const [selectedState, setSelectedState] = useState<ToothState>("Caries");
  const [syncStatus, setSyncStatus] = useState<Record<number, "syncing" | "synced" | "error">>({});
  const [history, setHistory] = useState<{ toothId: number; prev: ToothState }[]>([]);
  
  // Real-time Audit Toast State
  const [activeAudit, setActiveAudit] = useState<{ status: string; notes: string; isFlagged: boolean } | null>(null);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(teeth));
  }, [teeth]);

  const handleToothClick = async (toothId: number) => {
    const prevState = teeth[toothId];
    const newState = selectedState;
    if (prevState === newState) return;

    setTeeth((prev) => ({ ...prev, [toothId]: newState }));
    setHistory((prev) => [...prev.slice(-20), { toothId, prev: prevState }]);
    setSyncStatus((prev) => ({ ...prev, [toothId]: "syncing" }));
    setActiveAudit(null);

    try {
      // 1. Sync tooth state (Creates Treatment Plan)
      const res = await agentApi.updateToothState(clinicId, patientId, toothId.toString(), newState) as any;
      setSyncStatus((prev) => ({ ...prev, [toothId]: "synced" }));
      setTimeout(() => setSyncStatus((prev) => ({ ...prev, [toothId]: undefined as any })), 2000);
      
      // 2. Automatically trigger real-time Clinical Audit Guardrail
      if (res && res.id) {
        const auditRes = await agentApi.triggerAuditAgent(clinicId, res.id);
        if (auditRes) {
          setActiveAudit({
            status: auditRes.safety_status || "Passed",
            notes: auditRes.notes || "Audit complete",
            isFlagged: auditRes.safety_status === "Flagged"
          });
          // Auto-hide passed audits after 4 seconds
          if (auditRes.safety_status !== "Flagged") {
            setTimeout(() => setActiveAudit(null), 4000);
          }
        }
      }
    } catch (error) {
      console.error("Failed to sync or audit tooth state", error);
      setSyncStatus((prev) => ({ ...prev, [toothId]: "error" }));
    }
  };

  const handleUndo = () => {
    if (history.length === 0) return;
    const last = history[history.length - 1];
    setTeeth((prev) => ({ ...prev, [last.toothId]: last.prev }));
    setHistory((prev) => prev.slice(0, -1));
    setActiveAudit(null);
  };

  const renderRow = (teethIds: number[], label: string) => (
    <div className="flex flex-col items-center gap-1">
      <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">{label}</span>
      <div className="flex gap-1.5">
        {teethIds.map((id) => {
          const state = teeth[id];
          const sync = syncStatus[id];
          return (
            <button
              key={id}
              onClick={() => handleToothClick(id)}
              className={`w-10 h-14 border-2 rounded-lg flex flex-col items-center justify-center font-mono transition-all duration-200 hover:scale-110 hover:z-10 relative ${toothColors[state]}`}
              title={`Tooth ${id} — ${state}`}
            >
              <span className="text-[11px] font-bold">{id}</span>
              <span className="text-[7px] opacity-80 truncate max-w-full mt-0.5">
                {state === "Healthy" ? "—" : state.split(" ")[0]}
              </span>
              {sync === "syncing" && (
                <span className="absolute -top-1.5 -right-1.5 w-3 h-3 rounded-full bg-blue-500 animate-pulse border border-slate-900" />
              )}
              {sync === "synced" && (
                <span className="absolute -top-1.5 -right-1.5 bg-slate-900 rounded-full">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                </span>
              )}
              {sync === "error" && (
                <span className="absolute -top-1.5 -right-1.5 bg-slate-900 rounded-full">
                  <AlertCircle className="w-3.5 h-3.5 text-red-500" />
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );

  return (
    <div className="p-8 bg-slate-950/50 backdrop-blur-xl rounded-2xl border border-slate-800 shadow-2xl relative overflow-hidden">
      {/* Real-time Audit Toast */}
      {activeAudit && (
        <div className={`absolute top-4 left-1/2 -translate-x-1/2 z-20 px-4 py-2 rounded-full border shadow-xl flex items-center gap-2 text-sm font-medium animate-in slide-in-from-top-4 fade-in duration-300 ${activeAudit.isFlagged ? 'bg-red-950/90 border-red-500/50 text-red-200' : 'bg-emerald-950/90 border-emerald-500/50 text-emerald-200'}`}>
          <ShieldAlert className={`w-4 h-4 ${activeAudit.isFlagged ? 'text-red-400' : 'text-emerald-400'}`} />
          {activeAudit.notes}
        </div>
      )}

      {/* Header */}
      <div className="flex justify-between items-center mb-8 flex-wrap gap-4 relative z-10">
        <div>
          <h3 className="text-xl font-bold text-white tracking-tight">32-Tooth FDI Odontogram</h3>
          <p className="text-[12px] text-slate-400 font-medium mt-1">
            Clinical findings auto-trigger real-time AI Safety Guardrails.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleUndo}
            disabled={history.length === 0}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-300 text-xs font-semibold disabled:opacity-30 hover:bg-slate-800 transition-all shadow-sm"
          >
            <Undo2 className="w-4 h-4" /> Undo Action
          </button>
        </div>
      </div>

      {/* Condition Palette */}
      <div className="flex gap-2.5 mb-8 flex-wrap relative z-10">
        {(Object.keys(toothColors) as ToothState[]).map((state) => (
          <button
            key={state}
            onClick={() => setSelectedState(state)}
            className={`px-4 py-2 text-xs font-bold rounded-lg border transition-all duration-200 ${
              selectedState === state
                ? "ring-2 ring-white/50 shadow-lg scale-105"
                : "opacity-60 hover:opacity-100 bg-slate-900/50"
            } ${toothColors[state]}`}
          >
            {state}
          </button>
        ))}
      </div>

      {/* Odontogram Grid */}
      <div className="flex flex-col gap-6 relative z-10">
        <div className="flex items-center justify-between text-[11px] font-mono font-semibold text-slate-500 px-2">
          <span className="tracking-widest">MAXILLARY (Upper)</span>
          <span className="tracking-widest">RIGHT ← → LEFT</span>
        </div>
        <div className="flex gap-8 justify-center items-center bg-slate-900/30 p-4 rounded-xl border border-slate-800/50">
          {renderRow(upperRight, "Q1")}
          <div className="w-px h-24 bg-gradient-to-b from-transparent via-slate-600 to-transparent" />
          {renderRow(upperLeft, "Q2")}
        </div>
        
        <div className="flex gap-8 justify-center items-center bg-slate-900/30 p-4 rounded-xl border border-slate-800/50">
          {renderRow(lowerRight, "Q4")}
          <div className="w-px h-24 bg-gradient-to-b from-transparent via-slate-600 to-transparent" />
          {renderRow(lowerLeft, "Q3")}
        </div>
        <div className="flex items-center justify-between text-[11px] font-mono font-semibold text-slate-500 px-2">
          <span className="tracking-widest">MANDIBULAR (Lower)</span>
          <span className="bg-slate-800 px-2 py-1 rounded text-slate-300">
            {allTeeth.filter((t) => teeth[t] !== "Healthy").length} findings charted
          </span>
        </div>
      </div>
    </div>
  );
}
