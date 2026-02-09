import { motion, AnimatePresence } from 'motion/react';
import { useEffect, useRef, useState } from 'react';
import { X, Volume2, Bell, Eye, Lock, Palette, Gauge, Waves, Mic } from 'lucide-react';
import alertInfo from '../assets/alert_info.wav';
import alertWarning from '../assets/alert_warning.wav';
import alertError from '../assets/alert_error.wav';
import alertSuccess from '../assets/alert_success.wav';

export type SettingsState = {
  volume: number;
  chimeVolume: number;
  replyChime: boolean;
  voiceMode: boolean;
  systemSounds: boolean;
  systemAlerts: boolean;
  processWarnings: boolean;
  updateNotices: boolean;
  animations: boolean;
  grid: boolean;
  opacity: number;
  processingMode: 'BALANCED' | 'PERFORMANCE' | 'POWER SAVER';
  hardwareAccel: boolean;
  backgroundProc: boolean;
  notifications: boolean;
  devEnabled: boolean;
  debugOverlay: boolean;
  preferredInputId?: string;
  themeBg: string;
  themePanel: string;
  themeBorder: string;
  themeText: string;
  themeAccent: string;
  themeAccent2: string;
};

interface SettingsPanelProps {
  onClose: () => void;
  settings: SettingsState;
  onChange: (next: Partial<SettingsState>) => void;
  audioDevices: MediaDeviceInfo[];
  audioError: string | null;
  onOpenHub?: () => void;
  onDevUnlock: (password: string) => void;
  devEnabled: boolean;
  ollamaReady: boolean | null;
  onOllamaStart: () => void;
  onImportChatGPT: (file: File) => Promise<void>;
  onOpenDebugModal: () => void;
  focusSection?: 'theme';
  onFocusHandled?: () => void;
}

export function SettingsPanel({ onClose, settings, onChange, audioDevices, audioError, onOpenHub, onDevUnlock, devEnabled, ollamaReady, onOllamaStart, onImportChatGPT, onOpenDebugModal, focusSection, onFocusHandled }: SettingsPanelProps) {
  const [devPassword, setDevPassword] = useState('');
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const themeRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (focusSection === 'theme' && themeRef.current) {
      requestAnimationFrame(() => {
        themeRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        onFocusHandled?.();
      });
    }
  }, [focusSection, onFocusHandled]);
  const playTone = (url: string) => {
    try {
      const audio = new Audio(url);
      audio.volume = Math.max(0, Math.min(1, settings.chimeVolume / 100));
      audio.play().catch(() => {});
    } catch {
      // ignore
    }
  };
  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 overflow-y-auto"
        onClick={onClose}
      >
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.9, opacity: 0 }}
          className="bg-black border-2 border-cyan-500/50 max-w-4xl w-full max-h-[80vh] overflow-y-auto relative"
          onClick={(e) => e.stopPropagation()}
        >
          <motion.div
            className="absolute inset-0 pointer-events-none"
            style={{
              background: 'linear-gradient(90deg, transparent, rgba(0, 255, 255, 0.3), transparent)',
            }}
            animate={{ x: ['-100%', '100%'] }}
            transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
          />

          <div className="border-b border-cyan-500/30 p-4 flex items-center justify-between sticky top-0 bg-black z-10">
            <div>
              <h2 className="text-cyan-400">SYSTEM CONFIGURATION</h2>
              <p className="text-xs text-cyan-600 mt-1">Audio, visual, performance, and frequency modules.</p>
            </div>
            <div className="flex items-center gap-2">
              {onOpenHub && (
                <button
                  onClick={onOpenHub}
                  className="p-2 border border-cyan-500/40 hover:bg-cyan-500/10 transition-colors flex items-center gap-1 text-xs"
                >
                  <Waves className="w-4 h-4" /> Open Frequency Hub
                </button>
              )}
              <button
                onClick={onClose}
                className="p-2 border border-cyan-500/30 hover:bg-cyan-500/10 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>

          <div className="p-6 space-y-6">
            {/* Audio Settings */}
            <Section title="AUDIO INTERFACE" icon={<Volume2 className="w-5 h-5" />}>
              <div className="space-y-3 pl-7">
                <SettingItem
                  label="System Sounds"
                  checked={settings.systemSounds}
                  onToggle={(v) => onChange({ systemSounds: v })}
                  onTest={() => playTone(alertSuccess)}
                />
                <SettingItem
                  label="Voice Feedback"
                  checked={settings.voiceMode}
                  onToggle={(v) => onChange({ voiceMode: v })}
                  onTest={() => playTone(alertInfo)}
                />
                <SettingItem
                  label="Reply chime when text-only"
                  checked={settings.replyChime}
                  onToggle={(v) => onChange({ replyChime: v })}
                  onTest={() => playTone(alertInfo)}
                />
                <div className="space-y-1">
                  <label className="text-xs text-cyan-600">VOLUME LEVEL</label>
                  <input
                    type="range"
                    min={0}
                    max={100}
                    value={settings.volume}
                    onChange={(e) => onChange({ volume: Number(e.target.value) })}
                    className="w-full h-1 bg-black border border-cyan-500/30 appearance-none cursor-pointer"
                    style={{
                      background: `linear-gradient(to right, rgba(0, 255, 255, 0.3) 0%, rgba(0, 255, 255, 0.3) ${settings.volume}%, rgba(0, 0, 0, 0.5) ${settings.volume}%, rgba(0, 0, 0, 0.5) 100%)`,
                    }}
                  />
                  <div className="text-xs text-cyan-400">{settings.volume}%</div>
                </div>

                <div className="space-y-1">
                  <label className="text-xs text-cyan-600">CHIME VOLUME</label>
                  <input
                    type="range"
                    min={0}
                    max={100}
                    value={settings.chimeVolume}
                    onChange={(e) => onChange({ chimeVolume: Number(e.target.value) })}
                    className="w-full h-1 bg-black border border-cyan-500/30 appearance-none cursor-pointer"
                  />
                  <div className="text-xs text-cyan-400">{settings.chimeVolume}%</div>
                </div>

                <div className="space-y-1">
                  <label className="text-xs text-cyan-600 flex items-center gap-2">
                    <Mic className="w-4 h-4" /> Input source
                  </label>
                  <select
                    className="w-full bg-black border border-cyan-500/30 px-3 py-2 text-sm focus:outline-none focus:border-cyan-500"
                    value={settings.preferredInputId || ''}
                    onChange={(e) => onChange({ preferredInputId: e.target.value || undefined })}
                  >
                    <option value="">Default (system)</option>
                    {audioDevices.map((d) => (
                      <option key={d.deviceId} value={d.deviceId}>
                        {d.label || d.deviceId}
                      </option>
                    ))}
                  </select>
                  {audioError && <div className="text-[11px] text-rose-300">{audioError}</div>}
                </div>
              </div>
            </Section>

            {/* Notifications */}
            <Section title="NOTIFICATIONS" icon={<Bell className="w-5 h-5" />}>
              <div className="space-y-3 pl-7">
                <SettingItem
                  label="Notifications (master)"
                  checked={settings.notifications}
                  onToggle={(v) => onChange({ notifications: v })}
                  onTest={() => playTone(alertInfo)}
                />
                <SettingItem
                  label="System Alerts"
                  checked={settings.systemAlerts}
                  onToggle={(v) => onChange({ systemAlerts: v })}
                  onTest={() => playTone(alertWarning)}
                />
                <SettingItem
                  label="Process Warnings"
                  checked={settings.processWarnings}
                  onToggle={(v) => onChange({ processWarnings: v })}
                  onTest={() => playTone(alertWarning)}
                />
                <SettingItem
                  label="Update Notifications"
                  checked={settings.updateNotices}
                  onToggle={(v) => onChange({ updateNotices: v })}
                  onTest={() => playTone(alertInfo)}
                />
              </div>
            </Section>

            {/* Display Settings */}
            <Section title="VISUAL INTERFACE" icon={<Eye className="w-5 h-5" />}>
              <div className="space-y-3 pl-7">
                <SettingItem
                  label="Animation Effects"
                  checked={settings.animations}
                  onToggle={(v) => onChange({ animations: v })}
                />
                <SettingItem
                  label="Grid Overlay"
                  checked={settings.grid}
                  onToggle={(v) => onChange({ grid: v })}
                />
                <div className="space-y-1">
                  <label className="text-xs text-cyan-600">OPACITY</label>
                  <input
                    type="range"
                    min={0}
                    max={100}
                    value={settings.opacity}
                    onChange={(e) => onChange({ opacity: Number(e.target.value) })}
                    className="w-full h-1 bg-black border border-cyan-500/30"
                  />
                  <div className="text-xs text-cyan-400">{settings.opacity}%</div>
                </div>
              </div>
            </Section>

            {/* Performance */}
            <Section title="PERFORMANCE" icon={<Gauge className="w-5 h-5" />}>
              <div className="space-y-3 pl-7">
                <div className="space-y-1">
                  <label className="text-xs text-cyan-600">PROCESSING MODE</label>
                  <select
                    className="w-full bg-black border border-cyan-500/30 px-3 py-2 text-sm focus:outline-none focus:border-cyan-500"
                    value={settings.processingMode}
                    onChange={(e) => onChange({ processingMode: e.target.value as SettingsState['processingMode'] })}
                  >
                    <option value="BALANCED">BALANCED</option>
                    <option value="PERFORMANCE">PERFORMANCE</option>
                    <option value="POWER SAVER">POWER SAVER</option>
                  </select>
                </div>
                <SettingItem
                  label="Hardware Acceleration"
                  checked={settings.hardwareAccel}
                  onToggle={(v) => onChange({ hardwareAccel: v })}
                />
                <SettingItem
                  label="Background Processing"
                  checked={settings.backgroundProc}
                  onToggle={(v) => onChange({ backgroundProc: v })}
                />
              </div>
            </Section>

            {/* Dev & Debug */}
            <Section title="DEVELOPER / DEBUG" icon={<Lock className="w-5 h-5" />}>
              <div className="pl-7 space-y-3">
                <div className="flex items-center gap-2">
                  <input
                    type="password"
                    placeholder="Dev password"
                    value={devPassword}
                    onChange={(e) => setDevPassword(e.target.value)}
                    className="bg-black border border-cyan-500/30 px-3 py-2 text-sm focus:outline-none focus:border-cyan-500 w-64"
                  />
                  <button
                    onClick={() => onDevUnlock(devPassword)}
                    className="px-3 py-2 border border-cyan-500/50 text-sm hover:bg-cyan-500/10"
                  >
                    Enable Dev
                  </button>
                  <span className="text-xs text-cyan-400">{devEnabled ? 'Unlocked' : 'Locked'}</span>
                </div>
                <SettingItem
                  label="Debug overlay"
                  checked={settings.debugOverlay}
                  onToggle={(v) => onChange({ debugOverlay: v })}
                />
                <button
                  onClick={onOpenDebugModal}
                  className="px-3 py-2 border border-cyan-500/50 text-sm hover:bg-cyan-500/10"
                >
                  Open debug console
                </button>
                <div className="space-y-2 text-xs text-cyan-200">
                  <div className="text-cyan-400">Import ChatGPT export</div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      className="px-3 py-2 border border-cyan-500/50 text-sm hover:bg-cyan-500/10"
                    >
                      Choose file
                    </button>
                    <span className="text-[11px] text-cyan-500/80">Select your ChatGPT export zip or conversations.json.</span>
                  </div>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".zip,.json"
                    className="hidden"
                    onChange={async (e) => {
                      const f = e.target.files?.[0];
                      if (!f) return;
                      await onImportChatGPT(f);
                      e.target.value = '';
                    }}
                  />
                  <div className="text-[11px] text-cyan-500/80">Select your ChatGPT export zip or conversations.json.</div>
                </div>
              </div>
            </Section>

            {/* Ollama */}
            <Section title="LOCAL AI (OLLAMA)" icon={<Waves className="w-5 h-5" />}>
              <div className="pl-7 space-y-2 text-xs text-cyan-200">
                <div>Status: {ollamaReady === null ? 'Checking...' : ollamaReady ? 'Ready' : 'Offline'}</div>
                <button
                  onClick={onOllamaStart}
                  className="px-4 py-2 border border-cyan-500/50 bg-cyan-500/10 hover:bg-cyan-500/20 transition-colors text-sm"
                >
                  Start Ollama
                </button>
              </div>
            </Section>

            {/* Security */}
            <Section title="SECURITY PROTOCOLS" icon={<Lock className="w-5 h-5" />}>
              <div className="space-y-3 pl-7">
                <SettingItem label="Encryption Enabled" checked />
                <SettingItem label="Auto-Lock" checked />
                <SettingItem label="Audit Logging" />
              </div>
            </Section>

            {/* Theme */}
            <div ref={themeRef}>
              <Section title="THEME CONFIGURATION" icon={<Palette className="w-5 h-5" />}>
              <div className="pl-7 space-y-3">
                <ColorItem label="Background" value={settings.themeBg} onChange={(v) => onChange({ themeBg: v })} />
                <ColorItem label="Panels" value={settings.themePanel} onChange={(v) => onChange({ themePanel: v })} />
                <ColorItem label="Borders" value={settings.themeBorder} onChange={(v) => onChange({ themeBorder: v })} />
                <ColorItem label="Text" value={settings.themeText} onChange={(v) => onChange({ themeText: v })} />
                <ColorItem label="Accent" value={settings.themeAccent} onChange={(v) => onChange({ themeAccent: v })} />
                <ColorItem label="Accent 2" value={settings.themeAccent2} onChange={(v) => onChange({ themeAccent2: v })} />
              </div>
            </Section>
            </div>

            {/* Frequency Hub */}
            {onOpenHub && (
              <Section title="FREQUENCY LAB / CYMATICS" icon={<Waves className="w-5 h-5" />}>
                <div className="pl-7 space-y-2 text-xs text-cyan-200">
                  <p>Open the self-hosted Frequency Hub to run analyzers, generators, and cymatic visual tests without AI.</p>
                  <button
                    onClick={onOpenHub}
                    className="px-4 py-2 border border-cyan-500/50 bg-cyan-500/10 hover:bg-cyan-500/20 transition-colors text-sm"
                  >
                    Launch Frequency Hub
                  </button>
                </div>
              </Section>
            )}
          </div>

          <div className="border-t border-cyan-500/30 p-4 flex gap-3 justify-end bg-black sticky bottom-0">
            <button
              onClick={onClose}
              className="px-6 py-2 border border-cyan-500/30 hover:bg-cyan-500/10 transition-colors text-xs"
            >
              CLOSE
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

function Section({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="space-y-3 border-t border-cyan-500/20 pt-6 first:border-0 first:pt-0">
      <div className="flex items-center gap-2 text-cyan-400">
        {icon}
        <h3 className="text-sm">{title}</h3>
      </div>
      {children}
    </div>
  );
}

function SettingItem({ label, checked = false, onToggle, onTest }: { label: string; checked?: boolean; onToggle?: (v: boolean) => void; onTest?: () => void }) {
  return (
    <div className="flex items-center gap-3">
      <label className="flex items-center gap-3 cursor-pointer group">
        <div className="relative w-10 h-5 border border-cyan-500/30 bg-black group-hover:border-cyan-500/50 transition-colors">
          <input
            type="checkbox"
            className="sr-only peer"
            checked={checked}
            onChange={(e) => onToggle?.(e.target.checked)}
          />
          <div className="absolute inset-0 bg-cyan-500/20 peer-checked:bg-cyan-500/30 transition-colors"></div>
          <div className="absolute top-0.5 left-0.5 w-4 h-4 bg-cyan-500 peer-checked:translate-x-5 transition-transform"></div>
        </div>
        <span className="text-xs">{label}</span>
      </label>
      {onTest && (
        <button
          onClick={onTest}
          className="px-2 py-1 border border-cyan-500/40 text-[11px] hover:bg-cyan-500/10 transition-colors"
        >
          Test
        </button>
      )}
    </div>
  );
}

function ColorItem({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div className="flex items-center gap-3 text-xs">
      <label className="w-28 text-cyan-600">{label}</label>
      <input
        type="color"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-8 w-12 border border-cyan-500/30 bg-black"
      />
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="flex-1 bg-black border border-cyan-500/30 px-2 py-1"
      />
    </div>
  );
}
