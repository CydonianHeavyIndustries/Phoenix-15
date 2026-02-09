import { motion } from 'motion/react';
import { Lock, User, Key, Cpu } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

interface LoginOverlayProps {
  onLogin: () => void;
}

export function LoginOverlay({ onLogin }: LoginOverlayProps) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isBooting, setIsBooting] = useState(false);
   const [rememberUser, setRememberUser] = useState(false);
   const [rememberMe, setRememberMe] = useState(false);
   const [error, setError] = useState<string | null>(null);
   const autoLoginTriggered = useRef(false);

   // Load saved creds/preferences
   useEffect(() => {
     const ru = localStorage.getItem('BJ_REMEMBER_USER') === '1';
     const rm = localStorage.getItem('BJ_REMEMBER_ME') === '1';
     const savedUser = localStorage.getItem('BJ_REM_USER') || '';
     const savedPass = localStorage.getItem('BJ_REM_PASS') || '';
     setRememberUser(ru);
     setRememberMe(rm);
     if (ru) setUsername(savedUser);
     if (rm) setPassword(savedPass);
     // Auto-login if remember me has both fields
     if (rm && savedUser && savedPass && !autoLoginTriggered.current) {
       autoLoginTriggered.current = true;
       setTimeout(() => handleLogin(true), 200);
     }
   }, []);

   const persistPrefs = () => {
     if (rememberUser) {
       localStorage.setItem('BJ_REM_USER', username);
       localStorage.setItem('BJ_REMEMBER_USER', '1');
     } else {
       localStorage.removeItem('BJ_REM_USER');
       localStorage.removeItem('BJ_REMEMBER_USER');
     }
     if (rememberMe) {
       localStorage.setItem('BJ_REMEMBER_ME', '1');
       localStorage.setItem('BJ_REM_USER', username);
       localStorage.setItem('BJ_REM_PASS', password);
     } else {
       localStorage.removeItem('BJ_REMEMBER_ME');
       localStorage.removeItem('BJ_REM_PASS');
     }
   };

   const handleLogin = (auto = false) => {
     if (!username) {
       setError('Enter username.');
       return;
     }
     if (!password && !rememberMe) {
       setError('Enter password or enable Remember Me.');
       return;
     }
     setError(null);
     setIsBooting(true);
     persistPrefs();
     setTimeout(() => {
       onLogin();
       setIsBooting(false);
     }, auto ? 600 : 1200);
   };

  if (isBooting) {
    return (
      <motion.div
        initial={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black z-50 flex items-center justify-center"
      >
        <div className="text-center">
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
            className="w-16 h-16 border-4 border-cyan-500 border-t-transparent rounded-full mx-auto mb-4"
          />
          <div className="text-cyan-400 mb-2">BOOTING BJORGSUN-26 SYSTEM</div>
          <div className="text-xs text-cyan-600">Initializing core modules...</div>
          <motion.div
            className="w-64 h-1 bg-black border border-cyan-500/30 mt-4 mx-auto overflow-hidden"
          >
            <motion.div
              className="h-full bg-gradient-to-r from-cyan-500 to-blue-500"
              animate={{ x: ['-100%', '100%'] }}
              transition={{ duration: 1.5, repeat: Infinity, ease: 'linear' }}
              style={{ width: '50%' }}
            />
          </motion.div>
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="fixed inset-0 bg-black/95 backdrop-blur-sm z-50 flex items-center justify-center p-4"
    >
      {/* Background effects */}
      <div className="absolute inset-0 opacity-10">
        <div className="absolute inset-0" style={{
          backgroundImage: `linear-gradient(rgba(0, 255, 255, 0.1) 1px, transparent 1px),
                           linear-gradient(90deg, rgba(0, 255, 255, 0.1) 1px, transparent 1px)`,
          backgroundSize: '50px 50px'
        }}></div>
      </div>

      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        className="relative bg-black border-2 border-cyan-500/50 p-8 max-w-md w-full"
      >
        {/* Animated border */}
        <motion.div
          className="absolute inset-0 pointer-events-none"
          style={{
            background: 'linear-gradient(90deg, transparent, rgba(0, 255, 255, 0.3), transparent)',
          }}
          animate={{ x: ['-100%', '100%'] }}
          transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
        />

        <div className="relative">
          {/* Header */}
          <div className="text-center mb-8">
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ delay: 0.2 }}
              className="w-20 h-20 mx-auto mb-4 border-2 border-cyan-500 flex items-center justify-center"
            >
              <Cpu className="w-10 h-10 text-cyan-400" />
            </motion.div>
            <h1 className="text-2xl text-cyan-400 mb-2">BJORGSUN-26</h1>
            <p className="text-sm text-cyan-600">Queer-coded AI System // Authentication Required</p>
          </div>

          {/* Login Form */}
          <div className="space-y-4">
            <div>
              <label className="text-xs text-cyan-600 mb-2 block flex items-center gap-2">
                <User className="w-3 h-3" />
                USERNAME
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter username..."
                className="w-full bg-black border border-cyan-500/30 px-4 py-2 text-sm focus:outline-none focus:border-cyan-500 placeholder-cyan-800"
              />
            </div>

            <div>
              <label className="text-xs text-cyan-600 mb-2 block flex items-center gap-2">
                <Key className="w-3 h-3" />
                PASSWORD
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password..."
                onKeyPress={(e) => e.key === 'Enter' && handleLogin()}
                className="w-full bg-black border border-cyan-500/30 px-4 py-2 text-sm focus:outline-none focus:border-cyan-500 placeholder-cyan-800"
              />
            </div>

            <div className="flex items-center justify-between text-xs text-cyan-200 mt-2 mb-1 gap-4">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={rememberUser}
                  onChange={(e) => setRememberUser(e.target.checked)}
                  className="accent-cyan-500"
                />
                <span className="text-cyan-300 font-semibold tracking-wide">Remember user</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  className="accent-cyan-500"
                />
                <span className="text-cyan-300 font-semibold tracking-wide">Remember me</span>
              </label>
            </div>
            <div className="text-[11px] text-cyan-600 mb-2">
              Remember user stores just the username; Remember me stores username + password and auto-logins next time.
            </div>

            {error && (
              <div className="text-pink-400 text-xs">
                {error}
              </div>
            )}

            <button
              onClick={() => handleLogin(false)}
              className="w-full py-3 bg-cyan-500/20 border border-cyan-500/50 hover:bg-cyan-500/30 transition-colors text-sm relative overflow-hidden group"
            >
              <motion.div
                className="absolute inset-0 bg-gradient-to-r from-transparent via-cyan-400/20 to-transparent"
                initial={{ x: '-100%' }}
                whileHover={{ x: '100%' }}
                transition={{ duration: 0.5 }}
              />
              <span className="relative">INITIALIZE SYSTEM</span>
            </button>
          </div>

          {/* Footer */}
          <div className="mt-6 pt-4 border-t border-cyan-500/20 text-center">
            <p className="text-xs text-cyan-600">
              AUTHORIZED PERSONNEL ONLY
            </p>
            <p className="text-xs text-cyan-800 mt-1">
              All access attempts are logged and monitored
            </p>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}
