import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Send, Terminal, Eye, EyeOff, Ear, EarOff, Brain, CheckSquare } from 'lucide-react';

interface Message {
  id: string;
  type: 'user' | 'ai';
  text: string;
  timestamp: string;
}

interface ChatBoxProps {
  isAwake: boolean;
  onStatusChange: (status: 'idle' | 'speaking' | 'listening') => void;
  onSend: (msg: string) => Promise<string>;
}

export function ChatBox({ isAwake, onStatusChange, onSend }: ChatBoxProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [activeTab, setActiveTab] = useState<'chat' | 'commands'>('chat');
  const [toggles, setToggles] = useState({
    listen: true,
    vision: false,
    awareness: true,
    tasks: false
  });
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    // Keep scroll near bottom when new messages arrive but avoid jumping the whole page
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [messages]);

  // Only post the initialization line once, after wake
  useEffect(() => {
    if (isAwake && messages.length === 0) {
      setMessages([
        {
          id: 'init',
          type: 'ai',
          text: 'Bjorgsun-26 initialized. All systems nominal. How may I assist you?',
          timestamp: new Date().toLocaleTimeString()
        }
      ]);
    }
    if (!isAwake) {
      // Clear chat and show dormant hint when going offline
      setMessages([]);
    }
  }, [isAwake, messages.length]);

  const handleSend = async () => {
    if (!input.trim() || !isAwake) return;

    onStatusChange('listening');
    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      text: input,
      timestamp: new Date().toLocaleTimeString()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    try {
      onStatusChange('speaking');
      const reply = await onSend(userMessage.text);
      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: 'ai',
        text: reply || 'Online.',
        timestamp: new Date().toLocaleTimeString()
      };
      setMessages(prev => [...prev, aiMessage]);
    } finally {
      onStatusChange('idle');
    }
  };

  const quickCommands = [
    { label: 'Status Report', command: '/status' },
    { label: 'Run Diagnostics', command: '/diagnostics' },
    { label: 'Memory Scan', command: '/memory' },
    { label: 'Network Check', command: '/network' },
    { label: 'Clear Cache', command: '/clear-cache' },
    { label: 'Restart Core', command: '/restart' }
  ];

  return (
    <div className="border border-cyan-500/30 bg-slate-900/50 backdrop-blur-sm h-[calc(100vh-280px)] flex flex-col relative overflow-hidden shadow-lg shadow-cyan-500/10">
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
            onClick={() => setToggles(prev => ({ ...prev, listen: !prev.listen }))}
            disabled={!isAwake}
          />
          <ToggleButton
            icon={toggles.vision ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
            label="VISION"
            active={toggles.vision}
            onClick={() => setToggles(prev => ({ ...prev, vision: !prev.vision }))}
            disabled={!isAwake}
          />
          <ToggleButton
            icon={<Brain className="w-3 h-3" />}
            label="AWARE"
            active={toggles.awareness}
            onClick={() => setToggles(prev => ({ ...prev, awareness: !prev.awareness }))}
            disabled={!isAwake}
          />
          <ToggleButton
            icon={<CheckSquare className="w-3 h-3" />}
            label="TASKS"
            active={toggles.tasks}
            onClick={() => setToggles(prev => ({ ...prev, tasks: !prev.tasks }))}
            disabled={!isAwake}
          />
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto p-4">
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
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              handleSend();
            }
          }}
          placeholder={isAwake ? "Enter command..." : "System dormant..."}
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
  disabled 
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
