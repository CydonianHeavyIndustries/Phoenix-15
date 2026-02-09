import { motion } from 'motion/react';
import { Lock, User, Key } from 'lucide-react';
import { useEffect, useState } from 'react';

interface LoginOverlayProps {
  onLogin: (username: string, password: string) => Promise<void> | void;
}

export function LoginOverlay({ onLogin }: LoginOverlayProps) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isBooting, setIsBooting] = useState(false);
  const [error, setError] = useState('');
  // Runtime-injected credentials (from env-config.js via start_ui server)
  const runtimeConfig = (window as any).__BJ_CFG || {};
  const requiredUser =
    (runtimeConfig.user as string)?.trim() ||
    import.meta.env.VITE_BJORGSUN_USER?.trim() ||
    'Father';
  const requiredPass =
    (runtimeConfig.pass as string)?.trim() ||
    import.meta.env.VITE_BJORGSUN_PASS?.trim() ||
    'Father';

  useEffect(() => {
    const lastUser = localStorage.getItem('bjorgsun:lastUser');
    if (lastUser) {
      setUsername(lastUser);
    }
  }, []);

  const handleLogin = () => {
    const userOk = username.trim() === requiredUser;
    const passOk = password.trim() === requiredPass;
    if (!userOk || !passOk) {
      setError(
        `Invalid credentials. Username must be "${requiredUser}" and password must match the configured secret.`
      );
      return;
    }
    setError('');
    setIsBooting(true);
    Promise.resolve(onLogin(username, password))
      .then(() => {
        localStorage.setItem('bjorgsun:lastUser', username);
      })
      .catch(() => {
        setError("Login failed");
        setIsBooting(false);
      });
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
          <div className="text-cyan-400 mb-2">BOOTING BJORGSUN-26</div>
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
          {/* Logo */}
          <div className="text-center mb-8">
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 8, repeat: Infinity, ease: 'linear' }}
              className="w-16 h-16 mx-auto mb-4"
            >
              <Lock className="w-full h-full text-cyan-400" />
            </motion.div>
            <h1 className="text-2xl text-cyan-400 mb-2">BJORGSUN-26</h1>
            <p className="text-xs text-cyan-600">SECURE ACCESS REQUIRED</p>
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

            <button
              onClick={handleLogin}
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
            {error && (
              <div className="text-xs text-red-400 mt-2">{error}</div>
            )}
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
