'use client';

import React, { useState } from 'react';
import { Activity, Brain, Calendar, FileText, ShieldCheck, Users, Sparkles, ArrowUpRight } from 'lucide-react';

export default function GFIDentalDashboard() {
  const [activeTab, setActiveTab] = useState('copilot');

  return (
    <div className="min-h-screen bg-[#090A0F] text-slate-100 flex font-sans selection:bg-cyan-500 selection:text-black">
      
      {/* Sidebar Navigation */}
      <aside className="w-64 border-r border-slate-800/60 bg-[#0C0E15]/80 backdrop-blur-xl p-6 flex flex-col justify-between hidden md:flex">
        <div>
          <div className="flex items-center gap-3 mb-10">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
              <Brain className="h-6 w-6 text-white" />
            </div>
            <div>
              <h1 className="font-bold text-lg tracking-wider text-white">GFI DENTAL</h1>
              <span className="text-xs text-cyan-400 font-mono tracking-widest uppercase">AI Enterprise OS</span>
            </div>
          </div>

          <nav className="space-y-2">
            {[
              { name: 'AI Copilot & Charting', icon: Brain, id: 'copilot' },
              { name: 'Patient Diagnostics', icon: Activity, id: 'diagnostics' },
              { name: 'Smart Scheduling', icon: Calendar, id: 'schedule' },
              { name: 'Practice Analytics', icon: Users, id: 'analytics' },
            ].map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 text-sm font-medium ${
                    isActive
                      ? 'bg-gradient-to-r from-cyan-500/20 to-blue-500/10 text-cyan-400 border border-cyan-500/30 shadow-inner'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                  }`}
                >
                  <Icon className={`h-5 w-5 ${isActive ? 'text-cyan-400' : 'text-slate-400'}`} />
                  {item.name}
                </button>
              );
            })}
          </nav>
        </div>

        <div className="p-4 rounded-xl bg-gradient-to-b from-white/5 to-transparent border border-white/10">
          <div className="flex items-center gap-2 text-xs text-emerald-400 mb-1 font-mono">
            <ShieldCheck className="h-4 w-4" /> HIPAA & SECURE
          </div>
          <p className="text-xs text-slate-400">Node Cluster: Active (US-East)</p>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col h-screen overflow-y-auto">
        
        {/* Top Header */}
        <header className="h-20 border-b border-slate-800/60 bg-[#090A0F]/50 backdrop-blur-md px-8 flex items-center justify-between sticky top-0 z-20">
          <div className="flex items-center gap-4">
            <h2 className="text-xl font-semibold text-white tracking-wide">Clinical Command Center</h2>
            <span className="px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 text-xs font-mono">
              v2.5 Enterprise Live
            </span>
          </div>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs font-mono text-slate-300">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
              Gemini API Connected
            </div>
            <div className="h-10 w-10 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center font-bold text-cyan-400">
              GF
            </div>
          </div>
        </header>

        {/* Dashboard Content Grid */}
        <div className="p-8 max-w-7xl mx-auto w-full space-y-8">
          
          {/* Hero Banner Card */}
          <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-blue-900/40 via-slate-900 to-cyan-950/40 border border-slate-800 p-8 shadow-2xl">
            <div className="absolute right-0 top-0 translate-x-10 -translate-y-10 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none"></div>
            <div className="relative z-10 max-w-2xl">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-500/20 text-cyan-300 text-xs font-semibold mb-4">
                <Sparkles className="h-3.5 w-3.5" /> Next-Gen Dental Intelligence
              </div>
              <h3 className="text-3xl font-bold tracking-tight text-white mb-3">
                Automate Clinical Workflows & Patient Insights
              </h3>
              <p className="text-slate-400 text-sm leading-relaxed mb-6">
                Harness multimodal AI models to instantly parse dental scans, auto-transcribe clinical notes, and manage enterprise appointments with zero friction.
              </p>
              <button className="px-6 py-3 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-medium text-sm shadow-lg shadow-cyan-500/25 hover:shadow-cyan-500/40 transition-all flex items-center gap-2">
                Launch AI Consultation <ArrowUpRight className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Quick Metrics Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              { title: 'Processed Records Today', value: '1,428', change: '+18.2%', color: 'text-cyan-400' },
              { title: 'AI Accuracy Rating', value: '99.8%', change: '+0.4%', color: 'text-emerald-400' },
              { title: 'Active Clinic Nodes', value: '42', change: 'Online', color: 'text-blue-400' },
            ].map((stat, i) => (
              <div key={i} className="rounded-2xl bg-white/5 border border-white/10 p-6 backdrop-blur-md">
                <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">{stat.title}</p>
                <div className="flex items-baseline justify-between">
                  <h4 className="text-3xl font-extrabold text-white">{stat.value}</h4>
                  <span className={`text-xs font-mono font-semibold ${stat.color}`}>{stat.change}</span>
                </div>
              </div>
            ))}
          </div>

        </div>
      </main>
    </div>
  );
}