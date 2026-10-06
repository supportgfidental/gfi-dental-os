'use client';

import React, { useState } from 'react';
import { Sparkles, History, Mic, MicOff } from 'lucide-react';

interface SurfaceCondition {
  M?: string;
  O?: string;
  D?: string;
  B?: string;
  L?: string;
}

interface ToothRecord {
  status: string;
  surfaces: SurfaceCondition;
  history: { date: string; event: string; author: string }[];
  color: string;
}

export default function ProfessionalOdontogram() {
  const [selectedTooth, setSelectedTooth] = useState<number>(16);
  const [currentTab, setCurrentTab] = useState<'chart' | 'history' | 'ai'>('chart');
  
  const [isRecording, setIsRecording] = useState(false);
  const [dictationNotes, setDictationNotes] = useState('');
  
  const [dentition, setDentition] = useState<Record<number, ToothRecord>>({
    16: {
      status: 'Caries (Class II)',
      surfaces: { M: 'Caries', O: 'Caries' },
      history: [
        { date: '2026-09-15', event: 'Initial Examination - Caries diagnosed on M & O surfaces', author: 'Dr. Sarah Jenkins' },
        { date: '2026-09-29', event: 'AI Neural Core Flagged 92% Caries Confidence', author: 'GFI AI Engine' }
      ],
      color: 'fill-red-500/20 stroke-red-500'
    },
    30: {
      status: 'Root Canal Treated',
      surfaces: { O: 'Restored', B: 'Sound', L: 'Sound', M: 'Sound', D: 'Sound' },
      history: [
        { date: '2025-04-10', event: 'Endodontic therapy completed & post placed', author: 'Dr. Robert Vance' }
      ],
      color: 'fill-blue-500/20 stroke-blue-500'
    },
    3: {
      status: 'Porcelain Crown',
      surfaces: { O: 'Crown', M: 'Crown', D: 'Crown', B: 'Crown', L: 'Crown' },
      history: [
        { date: '2024-11-02', event: 'Full coverage porcelain crown seated', author: 'Dr. Sarah Jenkins' }
      ],
      color: 'fill-amber-500/20 stroke-amber-500'
    }
  });

  const [activeCondition, setActiveCondition] = useState('Caries');
  const [aiPendingFindings, setAiPendingFindings] = useState([
    { tooth: 14, finding: 'Possible interproximal caries', confidence: '94%' },
    { tooth: 21, finding: 'Existing class III restoration', confidence: '98%' },
    { tooth: 36, finding: 'Mild periapical radiolucency', confidence: '82%' }
  ]);

  const handleApplyCondition = (surfaceKey: keyof SurfaceCondition) => {
    setDentition(prev => {
      const current = prev[selectedTooth] || { status: 'Sound', surfaces: {}, history: [], color: 'fill-neutral-900 stroke-neutral-700' };
      const updatedSurfaces = { ...current.surfaces, [surfaceKey]: activeCondition };
      return {
        ...prev,
        [selectedTooth]: {
          ...current,
          status: activeCondition,
          surfaces: updatedSurfaces,
          color: activeCondition === 'Caries' ? 'fill-red-500/20 stroke-red-500' : 'fill-blue-500/20 stroke-blue-500'
        }
      };
    });
  };

  const renderAnatomicalTooth = (toothNum: number) => {
    const data = dentition[toothNum] || { status: 'Sound', surfaces: {}, history: [], color: 'fill-neutral-900 stroke-neutral-700' };
    const isSelected = selectedTooth === toothNum;

    return (
      <div 
        key={toothNum}
        onClick={() => setSelectedTooth(toothNum)}
        className={`flex flex-col items-center cursor-pointer p-1.5 rounded-xl transition-all ${
          isSelected ? 'bg-neutral-800 ring-2 ring-white' : 'hover:bg-neutral-900/60'
        }`}
      >
        <span className="text-[10px] font-mono text-neutral-400 mb-1">#{toothNum}</span>
        
        <svg width="36" height="42" viewBox="0 0 100 120">
          <path
            d="M 20 20 Q 50 5 80 20 Q 95 50 85 90 Q 75 115 50 115 Q 25 115 15 90 Q 5 50 20 20 Z"
            className={`${data.color} stroke-[3] transition-all`}
          />
          <polygon
            points="35,35 65,35 70,65 50,85 30,65"
            className="fill-black/40 stroke-neutral-600 stroke-[1.5]"
          />
          {data.surfaces.M && <circle cx="20" cy="50" r="5" className="fill-red-500" />}
          {data.surfaces.O && <circle cx="50" cy="50" r="6" className="fill-white" />}
          {data.surfaces.D && <circle cx="80" cy="50" r="5" className="fill-red-500" />}
        </svg>

        <span className="text-[8px] font-mono text-neutral-500 mt-1 truncate max-w-[42px]">
          {data.status.split(' ')[0]}
        </span>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between p-4 rounded-2xl bg-neutral-900 border border-neutral-800 flex-wrap gap-4">
        <div className="flex items-center gap-4">
          <div className="h-10 w-10 rounded-xl bg-black border border-neutral-800 flex items-center justify-center font-bold text-white">
            JD
          </div>
          <div>
            <div className="flex items-center gap-3">
              <h3 className="text-sm font-semibold text-white">Patient: John Doe</h3>
              <span className="text-[10px] font-mono text-neutral-400">MRN: GFI-000184</span>
            </div>
            <p className="text-[11px] text-neutral-400 mt-0.5">Adult Dentition • Universal Numbering System (1–32)</p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <button onClick={() => setCurrentTab('chart')} className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${currentTab === 'chart' ? 'bg-white text-black' : 'bg-neutral-800 text-neutral-300'}`}>Odontogram</button>
          <button onClick={() => setCurrentTab('history')} className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${currentTab === 'history' ? 'bg-white text-black' : 'bg-neutral-800 text-neutral-300'}`}>Clinical History</button>
          <button onClick={() => setCurrentTab('ai')} className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${currentTab === 'ai' ? 'bg-white text-black' : 'bg-neutral-800 text-neutral-300'}`}><Sparkles className="h-3 w-3" /> AI Review Queue</button>
          <button 
            onClick={() => {
              alert("GFI Clinical Executive Summary compiled successfully. Opening secure print dialog...");
              window.print();
            }}
            className="px-3 py-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-white text-xs font-medium border border-neutral-700 transition-all"
          >
            Export PDF Report
          </button>
        </div>
      </div>

      {currentTab === 'chart' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 bg-neutral-900 border border-neutral-800 p-6 rounded-2xl space-y-8">
            <div className="flex items-center gap-6 p-3 rounded-xl bg-black border border-neutral-800 text-[11px] font-mono flex-wrap">
              <span className="text-neutral-400">Legend:</span>
              <div className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-neutral-700"></span> Sound</div>
              <div className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-red-500"></span> Caries</div>
              <div className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-blue-500"></span> Root Canal</div>
              <div className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-amber-500"></span> Crown</div>
            </div>

            <div>
              <div className="text-xs font-mono text-neutral-400 mb-3 tracking-wider">MAXILLARY ARCH (UPPER)</div>
              <div className="grid grid-cols-8 sm:grid-cols-16 gap-1 bg-black p-4 rounded-xl border border-neutral-800">
                {Array.from({ length: 16 }, (_, i) => i + 1).map((num) => renderAnatomicalTooth(num))}
              </div>
            </div>

            <div>
              <div className="text-xs font-mono text-neutral-400 mb-3 tracking-wider">MANDIBULAR ARCH (LOWER)</div>
              <div className="grid grid-cols-8 sm:grid-cols-16 gap-1 bg-black p-4 rounded-xl border border-neutral-800">
                {Array.from({ length: 16 }, (_, i) => 32 - i).map((num) => renderAnatomicalTooth(num))}
              </div>
            </div>
          </div>

          <div className="bg-neutral-900 border border-neutral-800 p-6 rounded-2xl flex flex-col justify-between space-y-6">
            <div>
              <div className="flex items-center justify-between pb-4 border-b border-neutral-800 mb-4">
                <h4 className="text-sm font-semibold text-white">Tooth #{selectedTooth} Inspector</h4>
                <span className="px-2 py-0.5 rounded bg-black border border-neutral-800 text-[10px] font-mono text-cyan-400">Active Focus</span>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="text-[11px] font-mono text-neutral-400 block mb-1">Primary Diagnosis</label>
                  <p className="text-xs font-medium text-white p-2.5 rounded-lg bg-black border border-neutral-800">
                    {dentition[selectedTooth]?.status || 'Sound / Healthy'}
                  </p>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="text-[11px] font-mono text-neutral-400">Clinical Voice Dictation</label>
                    <button
                      type="button"
                      onClick={() => {
                        setIsRecording(!isRecording);
                        if (!isRecording) {
                          setDictationNotes("Patient exhibits mild sensitivity to thermal changes. Recommend composite restoration on mesial surface.");
                        }
                      }}
                      className={`px-2.5 py-1 rounded-md text-[10px] font-mono flex items-center gap-1.5 transition-all ${
                        isRecording ? 'bg-red-500/20 text-red-400 border border-red-500/50 animate-pulse' : 'bg-neutral-800 text-neutral-300 hover:bg-neutral-700'
                      }`}
                    >
                      {isRecording ? <MicOff className="h-3 w-3" /> : <Mic className="h-3 w-3" />}
                      {isRecording ? 'Listening...' : 'Dictate'}
                    </button>
                  </div>
                  <textarea
                    value={dictationNotes}
                    onChange={(e) => setDictationNotes(e.target.value)}
                    placeholder="Click 'Dictate' for neural audio-to-text transcription..."
                    className="w-full h-20 bg-black border border-neutral-800 rounded-xl p-3 text-xs text-white placeholder-neutral-600 focus:outline-none focus:border-neutral-600 font-mono resize-none"
                  />
                </div>

                <div>
                  <label className="text-[11px] font-mono text-neutral-400 block mb-2">Assign Condition</label>
                  <select
                    value={activeCondition}
                    onChange={(e) => setActiveCondition(e.target.value)}
                    className="w-full bg-black border border-neutral-800 rounded-xl px-3 py-2.5 text-xs text-white focus:outline-none focus:border-neutral-600 font-mono"
                  >
                    <option value="Caries">Caries (Decay)</option>
                    <option value="Root Canal Treated">Root Canal Treated</option>
                    <option value="Porcelain Crown">Porcelain Crown</option>
                    <option value="Missing">Missing Tooth</option>
                  </select>
                </div>
              </div>
            </div>

            <button
              onClick={() => {
                handleApplyCondition('O');
                alert(`Clinical notes and condition committed to Tooth #${selectedTooth} record.`);
              }}
              className="w-full py-3 rounded-xl bg-white text-black font-medium text-xs hover:bg-neutral-200 transition-all shadow-sm"
            >
              Commit Surface & Notes
            </button>
          </div>
        </div>
      )}

      {currentTab === 'history' && (
        <div className="bg-neutral-900 border border-neutral-800 p-8 rounded-2xl space-y-6">
          <div>
            <h3 className="text-lg font-semibold text-white">Clinical Audit Trail & History</h3>
            <p className="text-xs text-neutral-400 mt-1">Immutable historical record of treatments and diagnoses for Tooth #{selectedTooth}.</p>
          </div>

          <div className="space-y-4">
            {(dentition[selectedTooth]?.history || [{ date: '2026-01-01', event: 'No prior clinical events recorded.', author: 'System' }]).map((item, idx) => (
              <div key={idx} className="p-4 rounded-xl bg-black border border-neutral-800 flex items-center justify-between">
                <div className="flex items-start gap-3">
                  <div className="h-8 w-8 rounded-lg bg-neutral-900 border border-neutral-800 flex items-center justify-center text-white shrink-0 mt-0.5">
                    <History className="h-4 w-4" />
                  </div>
                  <div>
                    <h4 className="text-xs font-medium text-white">{item.event}</h4>
                    <span className="text-[10px] font-mono text-neutral-500 mt-1 block">Clinician: {item.author}</span>
                  </div>
                </div>
                <span className="text-[11px] font-mono text-neutral-400 px-3 py-1 rounded bg-neutral-900 border border-neutral-800">{item.date}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {currentTab === 'ai' && (
        <div className="bg-neutral-900 border border-neutral-800 p-8 rounded-2xl space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-white">AI Clinical Assist & Verification Queue</h3>
              <p className="text-xs text-neutral-400 mt-1">Neural core findings extracted from recent radiograph scans. Requires clinician confirmation.</p>
            </div>
            <span className="px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 text-xs font-mono">3 Pending Reviews</span>
          </div>

          <div className="space-y-3">
            {aiPendingFindings.map((finding, idx) => (
              <div key={idx} className="p-4 rounded-xl bg-black border border-neutral-800 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="h-8 w-8 rounded-lg bg-neutral-900 border border-neutral-800 flex items-center justify-center text-white font-mono text-xs">#{finding.tooth}</div>
                  <div>
                    <h4 className="text-xs font-medium text-white">{finding.finding}</h4>
                    <span className="text-[10px] font-mono text-emerald-400 mt-0.5 block">AI Confidence: {finding.confidence}</span>
                  </div>
                </div>
                <button 
                  onClick={() => {
                    setAiPendingFindings(prev => prev.filter((_, i) => i !== idx));
                    alert(`Tooth #${finding.tooth} finding confirmed and committed.`);
                  }}
                  className="px-4 py-2 rounded-lg bg-white text-black text-xs font-medium hover:bg-neutral-200 transition-all"
                >
                  Confirm Finding
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}