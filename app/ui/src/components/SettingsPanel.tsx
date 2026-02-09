import { useEffect, useState } from 'react';
import { motion } from 'motion/react';
import { X, Volume2, Bell, Eye, Lock, Palette, Gauge } from 'lucide-react';
import { apiSettingsGet, apiSettingsSet } from '../lib/api';

interface SettingsPanelProps {
  onClose: () => void;
}

interface ToggleProps {
  label: string;
  checked?: boolean;
  onChange?: (val: boolean) => void;
}

function SettingItem({ label, checked = false, onChange }: ToggleProps) {
  return (
    <label className="flex items-center gap-3 cursor-pointer group select-none">
      <div className="relative w-10 h-5 border border-cyan-500/30 bg-black group-hover:border-cyan-500/50 transition-colors">
        <input
          type="checkbox"
          className="sr-only peer"
          checked={checked}
          onChange={(e) => onChange?.(e.target.checked)}
        />
        <div className="absolute inset-0 bg-cyan-500/20 peer-checked:bg-cyan-500/30 transition-colors"></div>
        <div className="absolute top-0.5 left-0.5 w-4 h-4 bg-cyan-500 peer-checked:translate-x-5 transition-transform"></div>
      </div>
      <span className="text-xs text-cyan-200">{label}</span>
    </label>
  );
}

export function SettingsPanel({ onClose }: SettingsPanelProps) {
  const [audioSettings, setAudioSettings] = useState({
    systemSounds: true,
    voiceFeedback: true,
    volume: 75,
  });

  const [notificationSettings, setNotificationSettings] = useState({
    systemAlerts: true,
    processWarnings: true,
    updateNotifications: false,
  });

  const [visualSettings, setVisualSettings] = useState({
    animationEffects: true,
    gridOverlay: false,
    opacity: 90,
  });

  const [performanceSettings, setPerformanceSettings] = useState({
    processingMode: 'BALANCED',
    hardwareAcceleration: true,
    backgroundProcessing: true,
  });

  const [securitySettings, setSecuritySettings] = useState({
    encryptionEnabled: true,
    autoLock: true,
    auditLogging: false,
  });

  useEffect(() => {
    apiSettingsGet().then((res) => {
      const s = res.settings || {};
      if (s.audio) setAudioSettings((prev) => ({ ...prev, ...s.audio }));
      if (s.notifications) setNotificationSettings((prev) => ({ ...prev, ...s.notifications }));
      if (s.visual) setVisualSettings((prev) => ({ ...prev, ...s.visual }));
      if (s.performance) setPerformanceSettings((prev) => ({ ...prev, ...s.performance }));
      if (s.security) setSecuritySettings((prev) => ({ ...prev, ...s.security }));
    });
  }, []);

  const saveSettings = async () => {
    await apiSettingsSet({
      audio: audioSettings,
      notifications: notificationSettings,
      visual: visualSettings,
      performance: performanceSettings,
      security: securitySettings,
    });
    onClose();
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        className="bg-black border-2 border-cyan-500/50 w-full max-w-4xl mx-auto max-h-[80vh] overflow-y-auto overflow-x-hidden relative"
        style={{ scrollbarGutter: 'stable both-edges' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Animated border effect */}
        <motion.div
          className="absolute inset-0 pointer-events-none"
          style={{
            background: 'linear-gradient(90deg, transparent, rgba(0, 255, 255, 0.3), transparent)',
          }}
          animate={{ x: ['-100%', '100%'] }}
          transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
        />

        {/* Header */}
        <div className="border-b border-cyan-500/30 p-4 flex items-center justify-between sticky top-0 bg-black z-10">
          <div>
            <h2 className="text-cyan-400">SYSTEM CONFIGURATION</h2>
            <p className="text-xs text-cyan-600 mt-1">Adjust AI parameters and interface settings</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 border border-cyan-500/30 hover:bg-cyan-500/10 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Settings Content */}
        <div className="p-6 space-y-6 w-full max-w-4xl mx-auto overflow-x-hidden">
          {/* Audio Settings */}
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-cyan-400">
              <Volume2 className="w-5 h-5" />
              <h3 className="text-sm">AUDIO INTERFACE</h3>
            </div>
            <div className="pl-7 space-y-3">
              <SettingItem
                label="System Sounds"
                checked={audioSettings.systemSounds}
                onChange={(v) => setAudioSettings((p) => ({ ...p, systemSounds: v }))}
              />
              <SettingItem
                label="Voice Feedback"
                checked={audioSettings.voiceFeedback}
                onChange={(v) => setAudioSettings((p) => ({ ...p, voiceFeedback: v }))}
              />
              <div className="space-y-1">
                <label className="text-xs text-cyan-600">VOLUME LEVEL</label>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={audioSettings.volume}
                  onChange={(e) => setAudioSettings((p) => ({ ...p, volume: Number(e.target.value) }))}
                  className="w-full h-1 bg-black border border-cyan-500/30 appearance-none cursor-pointer"
                  style={{
                    background: `linear-gradient(to right, rgba(0, 255, 255, 0.3) 0%, rgba(0, 255, 255, 0.3) ${audioSettings.volume}%, rgba(0, 0, 0, 0.5) ${audioSettings.volume}%, rgba(0, 0, 0, 0.5) 100%)`
                  }}
                />
              </div>
            </div>
          </div>

          {/* Notifications */}
          <div className="space-y-3 border-top border-cyan-500/20 pt-6">
            <div className="flex items-center gap-2 text-cyan-400">
              <Bell className="w-5 h-5" />
              <h3 className="text-sm">NOTIFICATIONS</h3>
            </div>
            <div className="pl-7 space-y-3">
              <SettingItem label="System Alerts" checked={notificationSettings.systemAlerts} onChange={(v) => setNotificationSettings((p) => ({ ...p, systemAlerts: v }))} />
              <SettingItem label="Process Warnings" checked={notificationSettings.processWarnings} onChange={(v) => setNotificationSettings((p) => ({ ...p, processWarnings: v }))} />
              <SettingItem label="Update Notifications" checked={notificationSettings.updateNotifications} onChange={(v) => setNotificationSettings((p) => ({ ...p, updateNotifications: v }))} />
            </div>
          </div>

          {/* Display Settings */}
          <div className="space-y-3 border-t border-cyan-500/20 pt-6">
            <div className="flex items-center gap-2 text-cyan-400">
              <Eye className="w-5 h-5" />
              <h3 className="text-sm">VISUAL INTERFACE</h3>
            </div>
            <div className="pl-7 space-y-3">
              <SettingItem label="Animation Effects" checked={visualSettings.animationEffects} onChange={(v) => setVisualSettings((p) => ({ ...p, animationEffects: v }))} />
              <SettingItem label="Grid Overlay" checked={visualSettings.gridOverlay} onChange={(v) => setVisualSettings((p) => ({ ...p, gridOverlay: v }))} />
              <div className="space-y-1">
                <label className="text-xs text-cyan-600">OPACITY</label>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={visualSettings.opacity}
                  onChange={(e) => setVisualSettings((p) => ({ ...p, opacity: Number(e.target.value) }))}
                  className="w-full h-1 bg-black border border-cyan-500/30"
                />
              </div>
            </div>
          </div>

          {/* Performance */}
          <div className="space-y-3 border-t border-cyan-500/20 pt-6">
            <div className="flex items-center gap-2 text-cyan-400">
              <Gauge className="w-5 h-5" />
              <h3 className="text-sm">PERFORMANCE</h3>
            </div>
            <div className="pl-7 space-y-3">
              <div className="space-y-1">
                <label className="text-xs text-cyan-600">PROCESSING MODE</label>
                <select
                  className="w-full bg-black border border-cyan-500/30 px-3 py-2 text-sm focus:outline-none focus:border-cyan-500"
                  value={performanceSettings.processingMode}
                  onChange={(e) => setPerformanceSettings((p) => ({ ...p, processingMode: e.target.value }))}
                >
                  <option value="BALANCED">BALANCED</option>
                  <option value="PERFORMANCE">PERFORMANCE</option>
                  <option value="POWER SAVER">POWER SAVER</option>
                </select>
              </div>
              <SettingItem
                label="Hardware Acceleration"
                checked={performanceSettings.hardwareAcceleration}
                onChange={(v) => setPerformanceSettings((p) => ({ ...p, hardwareAcceleration: v }))}
              />
              <SettingItem
                label="Background Processing"
                checked={performanceSettings.backgroundProcessing}
                onChange={(v) => setPerformanceSettings((p) => ({ ...p, backgroundProcessing: v }))}
              />
            </div>
          </div>

          {/* Security */}
          <div className="space-y-3 border-t border-cyan-500/20 pt-6">
            <div className="flex items-center gap-2 text-cyan-400">
              <Lock className="w-5 h-5" />
              <h3 className="text-sm">SECURITY PROTOCOLS</h3>
            </div>
            <div className="pl-7 space-y-3">
              <SettingItem
                label="Encryption Enabled"
                checked={securitySettings.encryptionEnabled}
                onChange={(v) => setSecuritySettings((p) => ({ ...p, encryptionEnabled: v }))}
              />
              <SettingItem
                label="Auto-Lock"
                checked={securitySettings.autoLock}
                onChange={(v) => setSecuritySettings((p) => ({ ...p, autoLock: v }))}
              />
              <SettingItem
                label="Audit Logging"
                checked={securitySettings.auditLogging}
                onChange={(v) => setSecuritySettings((p) => ({ ...p, auditLogging: v }))}
              />
            </div>
          </div>

          {/* Theme */}
          <div className="space-y-3 border-t border-cyan-500/20 pt-6">
            <div className="flex items-center gap-2 text-cyan-400">
              <Palette className="w-5 h-5" />
              <h3 className="text-sm">THEME CONFIGURATION</h3>
            </div>
            <div className="pl-7 space-y-3">
              <div className="space-y-1">
                <label className="text-xs text-cyan-600">COLOR SCHEME</label>
                <div className="flex gap-2">
                  <button className="w-12 h-12 border-2 border-cyan-500 bg-black"></button>
                  <button className="w-12 h-12 border border-cyan-500/30 bg-black hover:border-cyan-500 transition-colors"></button>
                  <button className="w-12 h-12 border border-cyan-500/30 bg-black hover:border-cyan-500 transition-colors"></button>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-cyan-500/30 p-4 flex gap-3 justify-end bg-black">
          <button
            onClick={onClose}
            className="px-6 py-2 border border-cyan-500/30 hover:bg-cyan-500/10 transition-colors text-xs"
          >
            CANCEL
          </button>
          <button
            onClick={saveSettings}
            className="px-6 py-2 bg-cyan-500/20 border border-cyan-500/50 hover:bg-cyan-500/30 transition-colors text-xs"
          >
            APPLY CHANGES
          </button>
          <button
            onClick={saveSettings}
            className="px-6 py-2 border border-cyan-500/50 bg-cyan-500/10 hover:bg-cyan-500/20 transition-colors text-xs"
          >
            APPLY & SAVE
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}
