"use client";

import React, { useState } from "react";
import { ShieldAlert, Users, PackageSearch, ShieldCheck, PlayCircle, CheckCircle2, Loader2, AlertCircle } from "lucide-react";
import { agentApi } from "@/lib/api";

type AgentType = "insurance" | "retention" | "inventory" | "audit";

interface AgentStatus {
  status: "idle" | "running" | "success" | "error";
  response?: any;
  error?: string;
}

export default function AgentControlPanel({ clinicId, defaultTreatmentPlanId }: { clinicId: number, defaultTreatmentPlanId: number }) {
  const [agents, setAgents] = useState<Record<AgentType, AgentStatus>>({
    insurance: { status: "idle" },
    retention: { status: "idle" },
    inventory: { status: "idle" },
    audit: { status: "idle" }
  });

  const handleRunAgent = async (type: AgentType, apiCall: () => Promise<any>) => {
    setAgents(prev => ({ ...prev, [type]: { status: "running" } }));
    try {
      const res = await apiCall();
      setAgents(prev => ({ ...prev, [type]: { status: "success", response: res } }));
    } catch (err: any) {
      setAgents(prev => ({ ...prev, [type]: { status: "error", error: err.message || "Failed to execute" } }));
    }
  };

  const getLoadingText = (type: AgentType) => {
    switch (type) {
      case "insurance": return "Adjudicating ADA Code...";
      case "retention": return "Analyzing Decay Window...";
      case "inventory": return "Generating Purchase Order...";
      case "audit": return "Cross-Referencing Medical History...";
      default: return "Executing Agent...";
    }
  };

  const cards = [
    {
      id: "insurance" as AgentType,
      title: "Insurance Pre-Auth",
      subtitle: "Revenue Moat",
      description: "Auto-generates compliant claims with zero human touch.",
      icon: <ShieldAlert className="w-8 h-8 text-blue-400 drop-shadow-md" />,
      theme: "from-blue-900/20 to-slate-900/40 border-blue-500/30",
      buttonColor: "bg-blue-600/80 hover:bg-blue-500",
      action: () => handleRunAgent("insurance", () => agentApi.triggerInsuranceAgent(clinicId, defaultTreatmentPlanId))
    },
    {
      id: "retention" as AgentType,
      title: "Patient Retention",
      subtitle: "LTV Moat",
      description: "Scans decay windows & triggers personalized reactivation sequences.",
      icon: <Users className="w-8 h-8 text-emerald-400 drop-shadow-md" />,
      theme: "from-emerald-900/20 to-slate-900/40 border-emerald-500/30",
      buttonColor: "bg-emerald-600/80 hover:bg-emerald-500",
      action: () => handleRunAgent("retention", () => agentApi.triggerRetentionAgent(clinicId))
    },
    {
      id: "inventory" as AgentType,
      title: "Supply Auto-Pilot",
      subtitle: "Cost Moat",
      description: "Drafts POs with suppliers before composite stock hits zero.",
      icon: <PackageSearch className="w-8 h-8 text-amber-400 drop-shadow-md" />,
      theme: "from-amber-900/20 to-slate-900/40 border-amber-500/30",
      buttonColor: "bg-amber-600/80 hover:bg-amber-500",
      action: () => handleRunAgent("inventory", () => agentApi.triggerInventoryAgent(clinicId))
    },
    {
      id: "audit" as AgentType,
      title: "Clinical Audit Guardrail",
      subtitle: "Risk Moat",
      description: "Real-time safety checks against patient medical history.",
      icon: <ShieldCheck className="w-8 h-8 text-purple-400 drop-shadow-md" />,
      theme: "from-purple-900/20 to-slate-900/40 border-purple-500/30",
      buttonColor: "bg-purple-600/80 hover:bg-purple-500",
      action: () => handleRunAgent("audit", () => agentApi.triggerAuditAgent(clinicId, defaultTreatmentPlanId))
    }
  ];

  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
      {cards.map(card => (
        <div 
          key={card.id} 
          className={`relative p-8 rounded-2xl border backdrop-blur-xl bg-gradient-to-br shadow-2xl transition-all duration-300 hover:shadow-3xl flex flex-col justify-between overflow-hidden ${card.theme}`}
        >
          {/* Glassmorphism accent layer */}
          <div className="absolute top-0 right-0 -mt-10 -mr-10 w-40 h-40 bg-white/5 rounded-full blur-3xl pointer-events-none" />
          
          <div className="relative z-10">
            <div className="flex justify-between items-start mb-6">
              <div className="p-3 bg-slate-950/50 rounded-xl border border-white/5 backdrop-blur-md">
                {card.icon}
              </div>
              <div className="flex space-x-2 items-center">
                {agents[card.id].status === "running" && <Loader2 className="w-6 h-6 animate-spin text-slate-400" />}
                {agents[card.id].status === "success" && <CheckCircle2 className="w-6 h-6 text-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.5)]" />}
                {agents[card.id].status === "error" && <AlertCircle className="w-6 h-6 text-red-400 drop-shadow-[0_0_8px_rgba(248,113,113,0.5)]" />}
              </div>
            </div>
            
            <div className="flex items-baseline gap-3 mb-2">
              <h3 className="text-2xl font-bold text-white tracking-tight">{card.title}</h3>
              <span className="text-xs font-mono uppercase tracking-widest text-slate-400 bg-slate-950/50 px-2 py-1 rounded-md border border-white/5">
                {card.subtitle}
              </span>
            </div>
            <p className="text-slate-300 text-sm mb-8 font-light leading-relaxed">{card.description}</p>
          </div>
          
          <div className="relative z-10 mt-auto">
            <button
              onClick={card.action}
              disabled={agents[card.id].status === "running"}
              className={`w-full py-3.5 px-6 ${card.buttonColor} text-white rounded-xl font-semibold flex items-center justify-center gap-3 shadow-lg disabled:opacity-50 disabled:cursor-not-allowed transition-all border border-white/10`}
            >
              <PlayCircle className="w-5 h-5" />
              {agents[card.id].status === "running" ? getLoadingText(card.id) : "Trigger Agent"}
            </button>
            
            {(agents[card.id].status === "success" || agents[card.id].status === "error") && (
              <div className="mt-6 p-4 bg-slate-950/80 border border-slate-700/50 backdrop-blur-md font-mono text-[13px] rounded-xl overflow-x-auto max-h-60 overflow-y-auto shadow-inner custom-scrollbar">
                {agents[card.id].status === "error" ? (
                  <span className="text-red-400">{agents[card.id].error}</span>
                ) : (
                  <pre className="text-emerald-400/90 leading-relaxed">
                    {typeof agents[card.id].response === 'object' 
                      ? JSON.stringify(agents[card.id].response, null, 2) 
                      : agents[card.id].response}
                  </pre>
                )}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
