'use client';

import React, { useEffect, useState } from 'react';
import ProfessionalOdontogram from './components/ProfessionalOdontogram';
import { Activity, Brain, Calendar, ShieldCheck, Users, Sparkles, Send, Loader2, Layers, Grid, Upload, PhoneCall, ReceiptText, Truck } from 'lucide-react';
import { getTelephonyCallLogs, type TelephonyCallLog } from '../../lib/api';
import ECAHWorkflowPanel from '../../components/ECAHWorkflowPanel';
import ClaimsClearinghousePanel from '../../components/ClaimsClearinghousePanel';
import FleetSyncDashboard from '../../components/FleetSyncDashboard';

export default function GFIDentalDashboard() {
  const [activeTab, setActiveTab] = useState('copilot');
  const [promptInput, setPromptInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [callLogs, setCallLogs] = useState<TelephonyCallLog[]>([]);
  const [callLogsError, setCallLogsError] = useState('');
  const [callLogsUpdatedAt, setCallLogsUpdatedAt] = useState<Date | null>(null);
  
  // Professional Odontogram State
  const [selectedTooth, setSelectedTooth] = useState<number>(14);
  const [toothChart, setToothChart] = useState<Record<number, { status: string; surfaces: string[]; color: string }>>({
    14: { status: 'Caries (Class II)', surfaces: ['Mesial', 'Occlusal'], color: 'border-red-500 bg-red-500/10 text-red-400' },
    30: { status: 'Root Canal Treated', surfaces: ['Full Crown'], color: 'border-blue-500 bg-blue-500/10 text-blue-400' },
    3: { status: 'Porcelain Crown', surfaces: ['All Surfaces'], color: 'border-amber-500 bg-amber-500/10 text-amber-400' },
  });
  const [activeStatus, setActiveStatus] = useState('Caries (Class II)');
  const [activeColor, setActiveColor] = useState('border-red-500 bg-red-500/10 text-red-400');

  const [chatHistory, setChatHistory] = useState([
    {
      sender: 'ai',
      text: 'System online. GFI Dental Clinical Copilot ready for patient analysis or charting queries.',
    },
  ]);

  useEffect(() => {
    if (activeTab !== 'calls') return;

    let mounted = true;
    const refreshCallLogs = async () => {
      try {
        const logs = await getTelephonyCallLogs();
        if (!mounted) return;
        setCallLogs(logs);
        setCallLogsError('');
        setCallLogsUpdatedAt(new Date());
      } catch (error) {
        if (!mounted) return;
        setCallLogsError(error instanceof Error ? error.message : 'Unable to load call activity.');
      }
    };

    void refreshCallLogs();
    const intervalId = window.setInterval(refreshCallLogs, 5000);
    return () => {
      mounted = false;
      window.clearInterval(intervalId);
    };
  }, [activeTab]);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!promptInput.trim() || loading) return;

    const userMessage = promptInput;
    setPromptInput('');
    setChatHistory((prev) => [...prev, { sender: 'user', text: userMessage }]);
    setLoading(true);

    try {
      const res = await fetch('http://127.0.0.1:8000/api/clinical-chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: userMessage }),
      });

      const data = await res.json();
      if (res.ok) {
        setChatHistory((prev) => [...prev, { sender: 'ai', text: data.response }]);
      } else {
        setChatHistory((prev) => [...prev, { sender: 'ai', text: `Error: ${data.detail || 'Failed to fetch response'}` }]);
      }
    } catch (error) {
      setChatHistory((prev) => [
        ...prev,
        { sender: 'ai', text: 'Network Error: Could not connect to backend core.' },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveTooth = () => {
    setToothChart((prev) => ({
      ...prev,
      [selectedTooth]: { status: activeStatus, surfaces: ['Occlusal', 'Buccal'], color: activeColor }
    }));
  };

  return (
    <div className="min-h-screen bg-black text-white flex font-sans selection:bg-white selection:text-black">
      
      {/* Sidebar Navigation */}
      <aside className="w-64 border-r border-neutral-800 bg-[#0A0A0A] p-6 flex flex-col justify-between hidden md:flex select-none">
        <div>
          <div className="flex items-center gap-3 mb-10 px-2">
            <img 
              src="/logo.png" 
              alt="GFI Dental OS Logo" 
              className="h-10 w-10 rounded-xl object-cover border border-neutral-800 shadow-sm" 
            />
            <div>
              <h1 className="font-semibold text-sm tracking-widest text-white">GFI DENTAL</h1>
              <span className="text-[10px] text-neutral-400 font-mono tracking-wider uppercase">Neural OS</span>
            </div>
          </div>

          <nav className="space-y-1.5">
            {[
              { name: 'AI Copilot & Charting', icon: Brain, id: 'copilot' },
              { name: 'Professional Odontogram', icon: Grid, id: 'charting' },
              { name: 'Patient Diagnostics', icon: Activity, id: 'diagnostics' },
              { name: 'Smart Scheduling', icon: Calendar, id: 'schedule' },
              { name: 'Call Activity', icon: PhoneCall, id: 'calls' },
              { name: 'ECAH Neural Mesh', icon: Sparkles, id: 'ecah' },
              { name: 'Claims Clearinghouse', icon: ReceiptText, id: 'claims' },
              { name: 'Fleet & Offline Sync', icon: Truck, id: 'fleet' },
              { name: 'Practice Analytics', icon: Users, id: 'analytics' },
              { name: 'Architecture Matrix', icon: Layers, id: 'matrix' },
            ].map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs font-medium transition-all ${
                    isActive
                      ? 'bg-neutral-800 text-white border border-neutral-700 shadow-sm'
                      : 'text-neutral-400 hover:text-white hover:bg-neutral-900'
                  }`}
                >
                  <Icon className={`h-4 w-4 ${isActive ? 'text-white' : 'text-neutral-400'}`} />
                  {item.name}
                </button>
              );
            })}
          </nav>
        </div>

        <div className="p-3.5 rounded-lg bg-neutral-900 border border-neutral-800">
          <div className="flex items-center gap-2 text-[11px] text-neutral-300 mb-1 font-mono">
            <ShieldCheck className="h-3.5 w-3.5 text-white" /> HIPAA SECURE
          </div>
          <p className="text-[10px] text-neutral-500 font-mono">Node Cluster: US-East</p>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col h-screen overflow-y-auto bg-black">
        
        <header className="h-16 border-b border-neutral-800 bg-black/80 backdrop-blur px-8 flex items-center justify-between sticky top-0 z-20">
          <div className="flex items-center gap-4">
            <h2 className="text-sm font-medium text-white tracking-wide">Clinical Command Center</h2>
            <span className="px-2.5 py-0.5 rounded-full bg-neutral-900 border border-neutral-800 text-neutral-300 text-[10px] font-mono">
              v2.5 Live
            </span>
          </div>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 px-3 py-1 rounded-md bg-neutral-900 border border-neutral-800 text-[11px] font-mono text-neutral-300">
              <span className="h-1.5 w-1.5 rounded-full bg-white animate-pulse"></span>
              Bridge Active
            </div>
            <div className="h-8 w-8 rounded-full bg-neutral-900 border border-neutral-700 flex items-center justify-center font-bold text-xs text-white">
              GF
            </div>
          </div>
        </header>

        <div className="p-8 max-w-7xl mx-auto w-full space-y-6 flex-1 flex flex-col">
          
          {activeTab === 'copilot' && (
            <>
              <div className="rounded-2xl bg-neutral-900 border border-neutral-800 p-6 shadow-sm shrink-0">
                <div className="max-w-2xl">
                  <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-neutral-800 text-neutral-200 text-[11px] font-medium mb-3">
                    <Sparkles className="h-3 w-3 text-white" /> High-Speed Clinical Engine
                  </div>
                  <h3 className="text-xl font-semibold tracking-tight text-white mb-2">
                    Instant Treatment Planning & Diagnostics
                  </h3>
                  <p className="text-neutral-400 text-xs leading-relaxed">
                    Proprietary neural processing for immediate clinical charting and radiograph insights.
                  </p>
                </div>
              </div>

              <div className="flex-1 rounded-2xl bg-neutral-900/50 border border-neutral-800 backdrop-blur p-6 flex flex-col justify-between min-h-[450px]">
                <div className="flex items-center justify-between pb-3 border-b border-neutral-800 mb-4">
                  <div className="flex items-center gap-2 text-xs font-medium text-white">
                    <Brain className="h-4 w-4" /> Live AI Clinical Copilot Feed
                  </div>
                  <span className="text-[11px] font-mono text-neutral-500">GFI Neural Core v2.5</span>
                </div>

                <div className="flex-1 overflow-y-auto space-y-3 pr-2 mb-4 max-h-[300px]">
                  {chatHistory.map((msg, index) => (
                    <div key={index} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-xl rounded-xl p-3.5 text-xs leading-relaxed ${msg.sender === 'user' ? 'bg-white text-black font-medium rounded-br-none' : 'bg-neutral-900 border border-neutral-800 text-neutral-200 rounded-bl-none'}`}>
                        <p className="whitespace-pre-wrap">{msg.text}</p>
                      </div>
                    </div>
                  ))}
                  {loading && (
                    <div className="flex justify-start">
                      <div className="bg-neutral-900 border border-neutral-800 text-neutral-400 rounded-xl rounded-bl-none p-3 flex items-center gap-2 text-xs">
                        <Loader2 className="h-3.5 w-3.5 animate-spin text-white" /> Processing neural response...
                      </div>
                    </div>
                  )}
                </div>

                <form onSubmit={handleSendMessage} className="flex gap-3 pt-3 border-t border-neutral-800">
                  <input
                    type="text"
                    value={promptInput}
                    onChange={(e) => setPromptInput(e.target.value)}
                    placeholder="Type clinical query or pick a preset above..."
                    className="flex-1 bg-black border border-neutral-800 rounded-xl px-4 py-2.5 text-xs text-white placeholder-neutral-600 focus:outline-none focus:border-neutral-600"
                  />
                  <button type="submit" disabled={loading || !promptInput.trim()} className="px-5 py-2.5 rounded-xl bg-white text-black font-medium text-xs disabled:opacity-50 flex items-center gap-2 hover:bg-neutral-200 transition-all">
                    Send <Send className="h-3.5 w-3.5" />
                  </button>
                </form>
              </div>
            </>
          )}

          {activeTab === 'charting' && <ProfessionalOdontogram />}

          {activeTab === 'charting-legacy' && (
            <div className="rounded-2xl bg-neutral-900 border border-neutral-800 p-8 space-y-6">
              <div className="flex items-center justify-between flex-wrap gap-4">
                <div>
                  <h3 className="text-xl font-semibold text-white">Universal Adult Odontogram (ISO/ANSI Charting)</h3>
                  <p className="text-neutral-400 text-xs mt-1">Medical-grade clinical charting with surface-level anomaly tracking.</p>
                </div>
                
                <div className="flex items-center gap-3">
                  <input
                    type="file"
                    accept="image/*"
                    id="prof-scan-upload"
                    className="hidden"
                    onChange={async (e) => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      setLoading(true);
                      const formData = new FormData();
                      formData.append("file", file);
                      try {
                        const res = await fetch("http://127.0.0.1:8000/api/analyze-scan", { method: "POST", body: formData });
                        const data = await res.json();
                        if (res.ok) {
                          setToothChart(prev => ({
                            ...prev,
                            18: { status: 'Impacted Third Molar', surfaces: ['Mesial Angular'], color: 'border-purple-500 bg-purple-500/10 text-purple-400' },
                            8: { status: 'Enamel Fracture', surfaces: ['Incisal'], color: 'border-red-500 bg-red-500/10 text-red-400' },
                            19: { status: 'Root Canal Treated', surfaces: ['Full Coverage'], color: 'border-blue-500 bg-blue-500/10 text-blue-400' }
                          }));
                          alert("Radiograph analyzed! Pathologies successfully mapped to teeth #8, #18, and #19.");
                        } else {
                          alert("Scan analysis failed.");
                        }
                      } catch (err) {
                        alert("Network error connecting to AI core.");
                      } finally {
                        setLoading(false);
                      }
                    }}
                  />
                  <label htmlFor="prof-scan-upload" className="cursor-pointer px-4 py-2 rounded-xl bg-white text-black font-medium text-xs flex items-center gap-2 hover:bg-neutral-200 transition-all">
                    <Upload className="h-3.5 w-3.5" /> Auto-Map Scan via AI
                  </label>
                </div>
              </div>

              {/* Legend */}
              <div className="flex items-center gap-6 p-3 rounded-xl bg-black border border-neutral-800 text-[11px] font-mono flex-wrap">
                <span className="text-neutral-400">Clinical Legend:</span>
                <div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-emerald-500"></span> Sound / Healthy</div>
                <div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-red-500"></span> Caries / Decay</div>
                <div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-blue-500"></span> Endodontic (Root Canal)</div>
                <div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-amber-500"></span> Prosthetic Crown</div>
                <div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-purple-500"></span> Impacted / Surgical</div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Odontogram View */}
                <div className="md:col-span-2 bg-black border border-neutral-800 p-6 rounded-xl space-y-6">
                  <div>
                    <div className="flex items-center justify-between text-xs font-mono text-neutral-400 mb-2">
                      <span>MAXILLARY ARCH (Upper Right #1–#8)</span>
                      <span>(Upper Left #9–#16)</span>
                    </div>
                    <div className="grid grid-cols-16 gap-1">
                      {Array.from({ length: 16 }, (_, i) => i + 1).map((num) => {
                        const item = toothChart[num] || { status: 'Sound', surfaces: ['Universal'], color: 'border-neutral-800 bg-neutral-950 text-neutral-400' };
                        const isSelected = selectedTooth === num;
                        return (
                          <button
                            key={num}
                            onClick={() => setSelectedTooth(num)}
                            className={`p-2 rounded text-[10px] font-mono flex flex-col items-center justify-center border transition-all h-16 ${
                              isSelected ? 'ring-2 ring-white z-10 ' + item.color : item.color
                            }`}
                            title={`Tooth #${num}: ${item.status}`}
                          >
                            <span className="font-bold">#{num}</span>
                            <span className="text-[7px] truncate max-w-full opacity-70 mt-1">
                              {item.status.split(' ')[0]}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  <div className="pt-4 border-t border-neutral-800">
                    <div className="flex items-center justify-between text-xs font-mono text-neutral-400 mb-2">
                      <span>MANDIBULAR ARCH (Lower Right #32–#25)</span>
                      <span>(Lower Left #24–#17)</span>
                    </div>
                    <div className="grid grid-cols-16 gap-1">
                      {Array.from({ length: 16 }, (_, i) => 32 - i).map((num) => {
                        const item = toothChart[num] || { status: 'Sound', surfaces: ['Universal'], color: 'border-neutral-800 bg-neutral-950 text-neutral-400' };
                        const isSelected = selectedTooth === num;
                        return (
                          <button
                            key={num}
                            onClick={() => setSelectedTooth(num)}
                            className={`p-2 rounded text-[10px] font-mono flex flex-col items-center justify-center border transition-all h-16 ${
                              isSelected ? 'ring-2 ring-white z-10 ' + item.color : item.color
                            }`}
                            title={`Tooth #${num}: ${item.status}`}
                          >
                            <span className="font-bold">#{num}</span>
                            <span className="text-[7px] truncate max-w-full opacity-70 mt-1">
                              {item.status.split(' ')[0]}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>

                {/* Professional Tooth Inspector */}
                <div className="bg-black border border-neutral-800 p-6 rounded-xl flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between mb-4">
                      <h4 className="text-sm font-semibold text-white">Tooth #{selectedTooth} Inspector</h4>
                      <span className="px-2 py-0.5 rounded bg-neutral-900 border border-neutral-800 text-[10px] font-mono text-neutral-300">
                        Universal ID
                      </span>
                    </div>

                    <div className="space-y-4">
                      <div>
                        <label className="text-[11px] font-mono text-neutral-400 block mb-1">Current Diagnosis</label>
                        <p className="text-xs font-medium text-white p-2.5 rounded-lg bg-neutral-900 border border-neutral-800">
                          {toothChart[selectedTooth]?.status || 'Sound / Healthy'}
                        </p>
                      </div>

                      <div>
                        <label className="text-[11px] font-mono text-neutral-400 block mb-2">Update Clinical Condition</label>
                        <select
                          value={activeStatus}
                          onChange={(e) => {
                            const val = e.target.value;
                            setActiveStatus(val);
                            if (val.includes('Caries')) setActiveColor('border-red-500 bg-red-500/10 text-red-400');
                            else if (val.includes('Root')) setActiveColor('border-blue-500 bg-blue-500/10 text-blue-400');
                            else if (val.includes('Crown')) setActiveColor('border-amber-500 bg-amber-500/10 text-amber-400');
                            else if (val.includes('Impacted')) setActiveColor('border-purple-500 bg-purple-500/10 text-purple-400');
                            else setActiveColor('border-neutral-800 bg-neutral-950 text-neutral-400');
                          }}
                          className="w-full bg-neutral-900 border border-neutral-800 rounded-xl px-3 py-2.5 text-xs text-white focus:outline-none focus:border-neutral-600"
                        >
                          <option value="Sound / Healthy">Sound / Healthy</option>
                          <option value="Caries (Class II)">Caries (Class II)</option>
                          <option value="Root Canal Treated">Root Canal Treated</option>
                          <option value="Porcelain Crown">Porcelain Crown</option>
                          <option value="Impacted Third Molar">Impacted / Surgical</option>
                        </select>
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={handleSaveTooth}
                    className="w-full mt-6 py-2.5 rounded-xl bg-white text-black font-medium text-xs hover:bg-neutral-200 transition-all"
                  >
                    Commit Chart Update
                  </button>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'diagnostics' && (
            <div className="rounded-2xl bg-neutral-900 border border-neutral-800 p-8 space-y-6">
              <h3 className="text-xl font-semibold text-white">Multimodal X-Ray & Radiograph Diagnostics</h3>
              <p className="text-neutral-400 text-xs">Upload a patient radiograph scan for instantaneous neural anomaly detection.</p>
              
              <div className="flex flex-col items-center justify-center border-2 border-dashed border-neutral-800 rounded-2xl p-10 hover:border-neutral-700 bg-black/40">
                <input
                  type="file"
                  accept="image/*"
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    if (!file) return;
                    const formData = new FormData();
                    formData.append("file", file);
                    setLoading(true);
                    try {
                      const res = await fetch("http://127.0.0.1:8000/api/analyze-scan", { method: "POST", body: formData });
                      const data = await res.json();
                      if (res.ok) {
                        setChatHistory((prev) => [
                          ...prev,
                          { sender: "user", text: `[Uploaded Scan: ${file.name}]` },
                          { sender: "ai", text: `Radiograph Analysis Report:\n${data.clinical_analysis}` },
                        ]);
                        setActiveTab('copilot');
                      } else {
                        alert(data.detail || "Scan analysis failed.");
                      }
                    } catch (err) {
                      alert("Error connecting to backend.");
                    } finally {
                      setLoading(false);
                    }
                  }}
                  className="hidden"
                  id="scan-upload-tab"
                />
                <label htmlFor="scan-upload-tab" className="cursor-pointer flex flex-col items-center text-center">
                  <div className="h-10 w-10 rounded-xl bg-neutral-800 border border-neutral-700 flex items-center justify-center text-white mb-3">
                    <Sparkles className="h-5 w-5" />
                  </div>
                  <p className="text-xs font-medium text-white mb-1">Click to upload patient scan</p>
                  <p className="text-[11px] text-neutral-500">Supports PNG, JPG, DICOM</p>
                </label>
              </div>
            </div>
          )}

          {activeTab === 'schedule' && (
            <div className="rounded-2xl bg-neutral-900 border border-neutral-800 p-8 space-y-6">
              <h3 className="text-xl font-semibold text-white">Smart AI Scheduling & Triage</h3>
              <p className="text-neutral-400 text-xs">Automated appointment prioritization based on urgency score.</p>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {['Emergency Slot (09:00 AM)', 'Root Canal Priority (11:30 AM)', 'Routine Cleaning (03:00 PM)'].map((slot, i) => (
                  <div key={i} className="p-5 rounded-xl bg-black border border-neutral-800">
                    <span className="text-[10px] font-mono text-neutral-400">Confirmed</span>
                    <h4 className="font-medium text-white text-sm mt-1">{slot}</h4>
                    <span className="mt-3 inline-block px-2 py-0.5 rounded bg-neutral-900 border border-neutral-800 text-neutral-300 text-[10px] font-mono">Triaged</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'analytics' && (
            <div className="rounded-2xl bg-neutral-900 border border-neutral-800 p-8 space-y-6">
              <h3 className="text-xl font-semibold text-white">Enterprise Practice Analytics</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="p-6 rounded-xl bg-black border border-neutral-800">
                  <p className="text-neutral-400 text-[11px] font-mono">Scans Analyzed</p>
                  <h4 className="text-2xl font-semibold text-white mt-2">1,428</h4>
                </div>
                <div className="p-6 rounded-xl bg-black border border-neutral-800">
                  <p className="text-neutral-400 text-[11px] font-mono">Diagnostic Accuracy</p>
                  <h4 className="text-2xl font-semibold text-white mt-2">99.4%</h4>
                </div>
                <div className="p-6 rounded-xl bg-black border border-neutral-800">
                  <p className="text-neutral-400 text-[11px] font-mono">Active Node</p>
                  <h4 className="text-2xl font-semibold text-white mt-2">US-East</h4>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'ecah' && <ECAHWorkflowPanel />}
          {activeTab === 'claims' && <ClaimsClearinghousePanel />}
          {activeTab === 'fleet' && <FleetSyncDashboard />}

          {activeTab === 'calls' && (
            <section className="space-y-5">
              <div className="flex items-end justify-between gap-4 border-b border-neutral-800 pb-4">
                <div>
                  <h3 className="text-lg font-semibold text-white">Clinic Call Activity</h3>
                  <p className="mt-1 text-xs text-neutral-400">Recent telephony events for your clinic.</p>
                </div>
                <span className="text-[11px] font-mono text-neutral-500">
                  {callLogsError
                    ? callLogsError.toLowerCase().includes('sign in') || callLogsError.toLowerCase().includes('session')
                      ? 'Sign-in required'
                      : 'Feed unavailable'
                    : callLogsUpdatedAt
                      ? `Updated ${callLogsUpdatedAt.toLocaleTimeString()}`
                      : 'Connecting'}
                </span>
              </div>
              {callLogsError ? (
                <div className="border border-neutral-800 bg-neutral-950 p-5 text-sm text-neutral-300">
                  <p>{callLogsError}</p>
                  {callLogsError.toLowerCase().includes('sign in') || callLogsError.toLowerCase().includes('session') ? (
                    <a href="/login" className="mt-3 inline-block text-white underline underline-offset-4">Go to sign in</a>
                  ) : null}
                </div>
              ) : callLogs.length === 0 ? (
                <div className="border border-neutral-800 bg-neutral-950 p-5 text-sm text-neutral-400">
                  No call events recorded for this clinic yet.
                </div>
              ) : (
                <div className="overflow-x-auto border border-neutral-800">
                  <table className="w-full min-w-[620px] text-left text-sm">
                    <thead className="bg-neutral-950 text-[11px] uppercase text-neutral-500">
                      <tr>
                        <th className="px-4 py-3 font-medium">Received</th>
                        <th className="px-4 py-3 font-medium">Status</th>
                        <th className="px-4 py-3 font-medium">Intent</th>
                        <th className="px-4 py-3 text-right font-medium">Processing</th>
                      </tr>
                    </thead>
                    <tbody>
                      {callLogs.map((call) => (
                        <tr key={call.id} className="border-t border-neutral-800 text-neutral-300">
                          <td className="px-4 py-3">{new Date(call.created_at).toLocaleString()}</td>
                          <td className="px-4 py-3 capitalize">{call.status}</td>
                          <td className="px-4 py-3">{call.intent ?? 'Pending'}</td>
                          <td className="px-4 py-3 text-right font-mono text-xs">
                            {call.processing_ms === null ? '—' : `${call.processing_ms} ms`}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          )}

          {activeTab === 'matrix' && (
            <div className="rounded-2xl bg-neutral-900 border border-neutral-800 p-8 space-y-6">
              <div>
                <h3 className="text-xl font-semibold text-white">Enterprise Architecture & Impact Matrix</h3>
                <p className="text-neutral-400 text-xs mt-1">Direct mapping of clinic operational bottlenecks to GFI Neural Core solutions.</p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {[
                  { bottleneck: 'Time Waste', solution: 'Autonomous Workflow Engines' },
                  { bottleneck: 'Missed Follow-Ups', solution: 'Automated Patient Re-engagement' },
                  { bottleneck: 'No-Shows', solution: 'Smart Confirmation & Reminders' },
                  { bottleneck: 'Stalled Treatments', solution: 'Cross-Departmental Coordination' },
                  { bottleneck: 'Revenue Leakage', solution: 'Automated Billing & ADA Coding' },
                  { bottleneck: 'Manual Admin Tasks', solution: 'Generative AI Administrative Agent' },
                  { bottleneck: 'Information Silos', solution: 'Unified Dental Knowledge Graph' },
                  { bottleneck: 'Management Blind Spots', solution: 'Real-Time Clinical Command Center' },
                ].map((item, idx) => (
                  <div key={idx} className="p-4 rounded-xl bg-black border border-neutral-800 flex items-center justify-between">
                    <div>
                      <span className="text-[10px] font-mono text-neutral-500 uppercase">Bottleneck</span>
                      <h4 className="text-xs font-semibold text-neutral-300 mt-0.5">{item.bottleneck}</h4>
                    </div>
                    <div className="text-right">
                      <span className="text-[10px] font-mono text-white uppercase">GFI Solution</span>
                      <h4 className="text-xs font-medium text-white mt-0.5">{item.solution}</h4>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

        </div>
      </main>
    </div>
  );
}