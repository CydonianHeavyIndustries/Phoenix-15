import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Send, Terminal, Eye, EyeOff, Ear, EarOff, Brain, CheckSquare } from 'lucide-react';
import { addMemory, getCoach, chatLocal, ttsEdge } from '../api/client';
import alertSuccess from '../assets/alert_success.wav';
import alertInfo from '../assets/alert_info.wav';

interface Message {
  id: string;
  type: 'user' | 'ai';
  text: string;
  timestamp: string;
}

interface ChatBoxProps {
  isAwake: boolean;
  onStatusChange: (status: 'idle' | 'speaking' | 'listening' | 'thinking') => void;
  replyChime: boolean;
  chimeVolume: number;
  voiceMode: boolean;
  systemSounds: boolean;
  isHushed: boolean;
}

let activeTimeouts: number[] = [];

// simple cached WAV loader for chimes/alerts
const audioCache: Record<string, AudioBuffer | null> = {};
const loadBuffer = async (ctx: AudioContext, url: string) => {
  if (audioCache[url] !== undefined) return audioCache[url];
  try {
    const res = await fetch(url);
    const arr = await res.arrayBuffer();
    const buf = await ctx.decodeAudioData(arr);
    audioCache[url] = buf;
    return buf;
  } catch {
    audioCache[url] = null;
    return null;
  }
};

const playChime = (volume: number, url: string = alertSuccess) => {
  try {
    const audio = new Audio(url);
    audio.volume = Math.max(0, Math.min(1, volume / 100));
    audio.play().catch(() => {});
  } catch {
    // ignore
  }
};

export function ChatBox({ isAwake, onStatusChange, replyChime, chimeVolume, voiceMode, systemSounds, isHushed }: ChatBoxProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [activeTab, setActiveTab] = useState<'chat' | 'commands'>('chat');
  const [toggles, setToggles] = useState({
    listen: true,
    vision: false,
    awareness: true,
    tasks: false,
  });
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    const container = scrollRef.current;
    if (!container) return;
    const threshold = 80; // px from bottom to auto-scroll
    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    if (distanceFromBottom <= threshold) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (!isAwake) {
      setMessages([]);
    }
  }, [isAwake]);

  // Add greeting only after wake
  useEffect(() => {
    if (isAwake && messages.length === 0) {
      setMessages([{
        id: Date.now().toString(),
        type: 'ai',
        text: 'Bjorgsun-26 initialized. All systems nominal. Ready to assist!',
        timestamp: new Date().toLocaleTimeString(),
      }]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAwake]);

  const handleSend = () => {
    if (!input.trim() || !isAwake) return;

    onStatusChange('thinking');
    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      text: input,
      timestamp: new Date().toLocaleTimeString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');

    addMemory(userMessage.text).catch(() => {});

    (async () => {
      try {
        const history = messages.slice(-6).map((m) => ({
          role: m.type === 'user' ? 'user' : 'assistant',
          content: m.text,
        }));
        const data = await chatLocal(userMessage.text, history);
        const tip = data.reply || 'Acknowledged.';
        onStatusChange('speaking');
        setMessages((prev) => [
          ...prev,
          {
            id: (Date.now() + 1).toString(),
            type: 'ai',
            text: tip,
            timestamp: new Date().toLocaleTimeString(),
          },
        ]);
        const res = voiceMode && !isHushed ? await speakText(tip, chimeVolume) : { dur: 0, tts: false };
        if (!voiceMode && replyChime && systemSounds && !isHushed) {
          playChime(chimeVolume, alertInfo);
        }
        if (!res.tts) {
          const fallback = Math.max(1.2, res.dur + 0.5);
          setTimeout(() => onStatusChange('listening'), fallback * 1000);
        }
      } catch (err: any) {
        try {
          const data = await getCoach();
          const tip = Array.isArray(data?.coach?.advice) ? data.coach.advice[0] : 'Acknowledged.';
          onStatusChange('speaking');
          setMessages((prev) => [
            ...prev,
            {
              id: (Date.now() + 1).toString(),
              type: 'ai',
            text: tip || 'Acknowledged.',
            timestamp: new Date().toLocaleTimeString(),
          },
        ]);
        const res = voiceMode && !isHushed ? await speakText(tip || 'Acknowledged.', chimeVolume) : { dur: 0, tts: false };
        if (!voiceMode && replyChime && systemSounds && !isHushed) {
          playChime(chimeVolume, alertInfo);
        }
        if (!res.tts) {
          const fallback = Math.max(1.2, res.dur + 0.5);
          setTimeout(() => onStatusChange('listening'), fallback * 1000);
        }
        } catch {
          onStatusChange('speaking');
          setMessages((prev) => [
            ...prev,
            {
              id: (Date.now() + 1).toString(),
              type: 'ai',
              text: 'Local AI unavailable. Ensure Ollama is running and reachable. Message logged.',
              timestamp: new Date().toLocaleTimeString(),
            },
          ]);
          setTimeout(() => onStatusChange('listening'), 1500);
        }
      }
    })();
  };

  const stopVoice = () => {
    activeTimeouts.forEach((t) => clearTimeout(t));
    activeTimeouts = [];
  };

type SpeakResult = { dur: number; tts: boolean };

const speakText = async (text: string, chimeVolume: number): Promise<SpeakResult> => {
  // Use edge-tts backend. If it fails, remain silent.
  stopVoice();
  try {
    const blob = await ttsEdge(text);
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.volume = Math.max(0, Math.min(1, chimeVolume / 100));
    audio.onended = () => onStatusChange('listening');
    audio.play().catch(() => onStatusChange('listening'));
    const dur = Math.max(1.5, Math.min(12, text.split(/\s+/).filter(Boolean).length * 0.5));
    return { dur, tts: true };
  } catch {
    onStatusChange('listening');
    return { dur: 0, tts: false };
  }
};

type PhonemeFrame = { f0: number; f1: number; f2: number; f3: number; dur: number; noise?: boolean };

const PHONEMES: Record<string, PhonemeFrame> = {
  a: { f0: 165, f1: 800, f2: 1700, f3: 2700, dur: 0.18 },
  e: { f0: 168, f1: 500, f2: 1900, f3: 2500, dur: 0.16 },
  i: { f0: 170, f1: 320, f2: 2400, f3: 3200, dur: 0.16 },
  o: { f0: 160, f1: 500, f2: 900, f3: 2600, dur: 0.18 },
  u: { f0: 158, f1: 350, f2: 1100, f3: 2500, dur: 0.18 },
  y: { f0: 165, f1: 420, f2: 1800, f3: 2600, dur: 0.16 },
  s: { f0: 0, f1: 0, f2: 4500, f3: 0, dur: 0.12, noise: true },
  f: { f0: 0, f1: 0, f2: 2500, f3: 0, dur: 0.1, noise: true },
  h: { f0: 0, f1: 0, f2: 1800, f3: 0, dur: 0.1, noise: true },
  sh: { f0: 0, f1: 0, f2: 2500, f3: 0, dur: 0.14, noise: true },
  z: { f0: 165, f1: 0, f2: 4000, f3: 0, dur: 0.12, noise: true },
  r: { f0: 165, f1: 450, f2: 1100, f3: 2500, dur: 0.12 },
  l: { f0: 165, f1: 400, f2: 1700, f3: 2600, dur: 0.12 },
  m: { f0: 150, f1: 250, f2: 1200, f3: 2600, dur: 0.14 },
  n: { f0: 155, f1: 300, f2: 1450, f3: 2600, dur: 0.14 },
  g: { f0: 165, f1: 300, f2: 1500, f3: 2500, dur: 0.12 },
  k: { f0: 0, f1: 0, f2: 0, f3: 0, dur: 0.09, noise: true },
  t: { f0: 0, f1: 0, f2: 0, f3: 0, dur: 0.09, noise: true },
  p: { f0: 0, f1: 0, f2: 0, f3: 0, dur: 0.09, noise: true },
  b: { f0: 155, f1: 300, f2: 1200, f3: 2500, dur: 0.12 },
  d: { f0: 160, f1: 400, f2: 1600, f3: 2600, dur: 0.12 },
  v: { f0: 160, f1: 0, f2: 2200, f3: 0, dur: 0.12, noise: true },
};

const buildPhonemeFrames = (text: string): PhonemeFrame[] => {
  const cleaned = text.toLowerCase().replace(/[^a-z\\s]/g, ' ');
  const tokens = cleaned.split(/\\s+/).filter(Boolean);
  const frames: PhonemeFrame[] = [];

  tokens.forEach((tok) => {
    const syllables = tok.match(/sh|ch|th|[aeiouy]|[bcdfghjklmnpqrstvwxyz]/g) || [];
    syllables.forEach((sy) => {
      const key = PHONEMES[sy] ? sy : sy[0];
      const base = PHONEMES[key] || PHONEMES['a'];
      frames.push({
        f0: base.f0 || 165,
        f1: base.f1 || 500,
        f2: base.f2 || 1800,
        f3: base.f3 || 2600,
        dur: base.dur || 0.12,
        noise: base.noise,
      });
    });
    // add a tiny pause between words
    frames.push({ f0: 0, f1: 0, f2: 0, f3: 0, dur: 0.04, noise: false });
  });

  if (frames.length === 0) {
    frames.push({ f0: 165, f1: 500, f2: 1800, f3: 2600, dur: 0.16 });
  }
  return frames;
};

  const quickCommands = [
    { label: 'Status Report', command: '/status' },
    { label: 'Run Diagnostics', command: '/diagnostics' },
    { label: 'Memory Scan', command: '/memory' },
    { label: 'Network Check', command: '/network' },
    { label: 'Clear Cache', command: '/clear-cache' },
    { label: 'Restart Core', command: '/restart' },
  ];

  return (
    <div
      className="border border-cyan-500/30 bg-slate-900/50 backdrop-blur-sm h-full min-h-[400px] flex flex-col relative overflow-hidden shadow-lg shadow-cyan-500/10"
    >
      {/* Header with Tabs */}
      <div className="border-b border-cyan-500/30">
        <div className="flex items-center border-b border-cyan-500/30">
          <button
            onClick={() => setActiveTab('chat')}
            className={`flex-1 p-3 text-xs transition-colors ${
              activeTab === 'chat'
                ? 'bg-cyan-500/10 border-b-2 border-cyan-500'
                : 'hover:bg-cyan-500/5'
            }`}
          >
            <Terminal className="w-4 h-4 inline mr-2" />
            CHAT INTERFACE
          </button>
          <button
            onClick={() => setActiveTab('commands')}
            className={`flex-1 p-3 text-xs transition-colors ${
              activeTab === 'commands'
                ? 'bg-cyan-500/10 border-b-2 border-cyan-500'
                : 'hover:bg-cyan-500/5'
            }`}
          >
            <CheckSquare className="w-4 h-4 inline mr-2" />
            QUICK COMMANDS
          </button>
        </div>

        {/* Module Toggles */}
        <div className="p-3 flex items-center gap-4 text-xs">
          <span className="text-cyan-600">MODULES:</span>
          <ToggleButton
            icon={toggles.listen ? <Ear className="w-3 h-3" /> : <EarOff className="w-3 h-3" />}
            label="LISTEN"
            active={toggles.listen}
            onClick={() => setToggles((prev) => ({ ...prev, listen: !prev.listen }))}
            disabled={!isAwake}
          />
          <ToggleButton
            icon={toggles.vision ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
            label="VISION"
            active={toggles.vision}
            onClick={() => setToggles((prev) => ({ ...prev, vision: !prev.vision }))}
            disabled={!isAwake}
          />
          <ToggleButton
            icon={<Brain className="w-3 h-3" />}
            label="AWARE"
            active={toggles.awareness}
            onClick={() => setToggles((prev) => ({ ...prev, awareness: !prev.awareness }))}
            disabled={!isAwake}
          />
          <ToggleButton
            icon={<CheckSquare className="w-3 h-3" />}
            label="TASKS"
            active={toggles.tasks}
            onClick={() => setToggles((prev) => ({ ...prev, tasks: !prev.tasks }))}
            disabled={!isAwake}
          />
        </div>
      </div>

      {/* Content Area */}
      <div
        className="flex-1 overflow-y-auto p-4"
        ref={scrollRef}
      >
        {activeTab === 'chat' ? (
          <div className="space-y-4">
            <AnimatePresence>
              {messages.map((message) => (
                <motion.div
                  key={message.id}
                  initial={{ opacity: 0, x: message.type === 'user' ? 20 : -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div className={`max-w-[80%] ${message.type === 'user' ? 'order-2' : 'order-1'}`}>
                    <div className="text-xs text-cyan-600 mb-1 flex items-center gap-2">
                      <span>{message.type === 'user' ? 'USER' : 'BJORGSUN-26'}</span>
                      <span>{message.timestamp}</span>
                    </div>
                    <div
                      className={`p-3 border ${
                        message.type === 'user'
                          ? 'bg-cyan-500/10 border-cyan-500/30'
                          : 'bg-black/70 border-cyan-500/20'
                      }`}
                    >
                      <p className="text-sm">{message.text}</p>
                    </div>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
            <div ref={messagesEndRef} />
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-2">
            {quickCommands.map((cmd, index) => (
              <motion.button
                key={cmd.command}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.05 }}
                onClick={() => {
                  if (isAwake) {
                    setInput(cmd.command);
                    setActiveTab('chat');
                  }
                }}
                disabled={!isAwake}
                className={`p-3 border text-left transition-colors ${
                  isAwake
                    ? 'border-cyan-500/30 hover:bg-cyan-500/10'
                    : 'border-gray-700 text-gray-600 cursor-not-allowed'
                }`}
              >
                <div className="text-xs text-cyan-400">{cmd.label}</div>
                <div className="text-xs text-cyan-600 mt-1 font-mono">{cmd.command}</div>
              </motion.button>
            ))}
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="border-t border-cyan-500/30 p-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder={isAwake ? 'Enter command...' : 'System dormant...'}
            disabled={!isAwake}
            className="flex-1 bg-black border border-cyan-500/30 px-4 py-2 text-sm focus:outline-none focus:border-cyan-500 placeholder-cyan-800 disabled:opacity-50 disabled:cursor-not-allowed"
          />
          <button
            onClick={handleSend}
            disabled={!isAwake}
            className="px-6 py-2 bg-cyan-500/20 border border-cyan-500/50 hover:bg-cyan-500/30 transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send className="w-4 h-4" />
            <span className="text-xs">SEND</span>
          </button>
        </div>
      </div>
    </div>
  );
}

function ToggleButton({
  icon,
  label,
  active,
  onClick,
  disabled,
}: {
  icon: React.ReactNode;
  label: string;
  active: boolean;
  onClick: () => void;
  disabled: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`px-2 py-1 border text-xs flex items-center gap-1 transition-colors ${
        disabled
          ? 'border-gray-700 text-gray-600 cursor-not-allowed'
          : active
          ? 'border-cyan-500 bg-cyan-500/20 text-cyan-400'
          : 'border-cyan-500/30 text-cyan-600 hover:bg-cyan-500/10'
      }`}
    >
      {icon}
      <span>{label}</span>
    </button>
  );
}
