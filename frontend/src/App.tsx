import { useState, useEffect, useRef } from 'react';
import {
  Send, Home, Volume2, VolumeX,
  Sun, Cloud, CloudRain, CloudSnow, CloudLightning, CloudFog, Moon,
  Droplets, Wind, Thermometer, ArrowUp, ArrowDown,
  Power, ChevronUp, ChevronDown, ChevronLeft, ChevronRight,
  Play, SkipBack, SkipForward, Menu, ArrowLeft
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import * as api from './api';

// Utility
const cn = (...classes: (string | boolean | undefined)[]) => classes.filter(Boolean).join(' ');

// ==================== WEATHER CARD ====================
const WeatherCard = ({ data }: { data: any }) => {
  if (!data?.weather) {
    return (
      <div className="bg-gradient-to-br from-blue-900/40 to-purple-900/40 backdrop-blur-xl rounded-3xl p-6 border border-white/10">
        <div className="animate-pulse text-white/50 text-center py-8">Loading weather...</div>
      </div>
    );
  }

  const w = data.weather;

  const getWeatherIcon = (code: number, isDay: number = 1) => {
    const iconClass = "w-16 h-16 drop-shadow-lg";

    // Night Mode Check
    if (isDay === 0) {
      if (code === 0) return <Moon className={`${iconClass} text-blue-100/80`} />;
      if (code >= 1 && code <= 3) return <Cloud className={`${iconClass} text-gray-400`} />;
    }

    if (code === 0) return <Sun className={`${iconClass} text-yellow-400`} />;
    if (code >= 1 && code <= 3) return <Cloud className={`${iconClass} text-gray-300`} />;
    if (code >= 45 && code <= 48) return <CloudFog className={`${iconClass} text-gray-400`} />;
    if (code >= 51 && code <= 67) return <CloudRain className={`${iconClass} text-blue-400`} />;
    if (code >= 71 && code <= 77) return <CloudSnow className={`${iconClass} text-blue-200`} />;
    if (code >= 95) return <CloudLightning className={`${iconClass} text-yellow-300`} />;
    return <Thermometer className={`${iconClass} text-cyan-400`} />;
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-gradient-to-br from-blue-900/40 to-purple-900/40 backdrop-blur-xl rounded-3xl p-6 border border-white/10 shadow-2xl"
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="text-white/60 text-sm font-medium">{w.location?.split(',')[0] || 'Bangalore'}</p>
          <div className="flex items-baseline gap-1">
            <span className="text-6xl font-light text-white">{w.temperature}</span>
            <span className="text-2xl text-white/60">°C</span>
          </div>
          <p className="text-white/80 font-medium mt-1">{w.condition}</p>
          <div className="flex gap-4 mt-2 text-sm">
            <span className="flex items-center gap-1 text-blue-300">
              <ArrowDown size={14} /> {w.temp_min}°
            </span>
            <span className="flex items-center gap-1 text-orange-300">
              <ArrowUp size={14} /> {w.temp_max}°
            </span>
          </div>
        </div>
        <div>
          {getWeatherIcon(w.weather_code, w.is_day)}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4 mt-6 pt-4 border-t border-white/10">
        <div className="text-center">
          <Droplets className="w-5 h-5 mx-auto text-blue-400 mb-1" />
          <p className="text-white font-medium">{w.humidity}%</p>
          <p className="text-white/50 text-xs">Humidity</p>
        </div>
        <div className="text-center">
          <Wind className="w-5 h-5 mx-auto text-cyan-400 mb-1" />
          <p className="text-white font-medium">{w.wind_speed}</p>
          <p className="text-white/50 text-xs">km/h</p>
        </div>
        <div className="text-center">
          <Thermometer className="w-5 h-5 mx-auto text-purple-400 mb-1" />
          <p className="text-white font-medium">{w.pressure}</p>
          <p className="text-white/50 text-xs">hPa</p>
        </div>
      </div>
    </motion.div>
  );
};

// ==================== LIGHT CONTROLS ====================
const LightControls = ({ status, refresh }: { status: any; refresh: () => void }) => {
  const [brightness, setBrightness] = useState(50);

  const colors = [
    { name: 'White', hex: '#FFFFFF', hue: -1 },
    { name: 'Warm', hex: '#FFD580', hue: 30 },
    { name: 'Red', hex: '#FF4444', hue: 0 },
    { name: 'Orange', hex: '#FF9500', hue: 30 },
    { name: 'Green', hex: '#34C759', hue: 120 },
    { name: 'Cyan', hex: '#5AC8FA', hue: 180 },
    { name: 'Blue', hex: '#007AFF', hue: 220 },
    { name: 'Purple', hex: '#AF52DE', hue: 280 },
  ];

  useEffect(() => {
    if (status?.brightness !== undefined) setBrightness(status.brightness);
  }, [status]);

  const isOn = status?.on === true;

  // Get current color from status - backend now returns actual color name in 'mode'
  const detectCurrentColor = () => {
    if (!status?.mode) return 'White';
    // Capitalize first letter to match button labels
    const mode = status.mode.toLowerCase();
    return mode.charAt(0).toUpperCase() + mode.slice(1);
  };

  const currentColor = detectCurrentColor();

  const togglePower = () => {
    console.log('[UI] Toggle power, current isOn:', isOn);
    api.controlLight(isOn ? 'off' : 'on')
      .then(() => { console.log('[UI] Light command success'); refresh(); })
      .catch(err => console.error('[UI] Light command error:', err));
  };
  const setColor = (name: string) => {
    console.log('[UI] Set color:', name);
    api.controlLight('color', name)
      .then(() => refresh())
      .catch(err => console.error('[UI] Color error:', err));
  };
  const commitBrightness = () => {
    console.log('[UI] Set brightness:', brightness);
    api.controlLight('brightness', brightness)
      .then(() => refresh())
      .catch(err => console.error('[UI] Brightness error:', err));
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 }}
      className="bg-gradient-to-br from-amber-900/30 to-orange-900/30 backdrop-blur-xl rounded-3xl p-6 border border-white/10 shadow-2xl"
    >
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-white font-semibold text-lg">Room Light</h3>
          <p className="text-white/50 text-sm">{isOn ? `${currentColor} • ${brightness}%` : 'Off'}</p>
        </div>
        <motion.button
          whileTap={{ scale: 0.9 }}
          onClick={togglePower}
          className={cn(
            "w-14 h-14 rounded-full flex items-center justify-center transition-all",
            isOn
              ? "bg-gradient-to-br from-yellow-400 to-orange-500 shadow-lg shadow-orange-500/30"
              : "bg-white/10 border border-white/20"
          )}
        >
          <Power className={cn("w-6 h-6", isOn ? "text-white" : "text-white/50")} />
        </motion.button>
      </div>

      {/* Brightness */}
      <div className="mb-6">
        <div className="flex justify-between text-sm mb-2">
          <span className="text-white/60">Brightness</span>
          <span className="text-white font-medium">{brightness}%</span>
        </div>
        <input
          type="range"
          min="0" max="100"
          value={brightness}
          onChange={(e) => setBrightness(parseInt(e.target.value))}
          onMouseUp={commitBrightness}
          onTouchEnd={commitBrightness}
          className="w-full h-2 bg-white/10 rounded-full appearance-none cursor-pointer 
            [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 
            [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:shadow-lg"
        />
      </div>

      {/* Colors */}
      <div className="grid grid-cols-4 gap-3">
        {colors.map((c) => (
          <motion.button
            key={c.name}
            whileTap={{ scale: 0.9 }}
            onClick={() => setColor(c.name)}
            className={cn(
              "h-10 rounded-xl transition-all relative",
              currentColor === c.name ? "ring-2 ring-white ring-offset-2 ring-offset-transparent scale-105" : ""
            )}
            style={{ backgroundColor: c.hex }}
          >
            {currentColor === c.name && (
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="w-3 h-3 bg-black/30 rounded-full" />
              </div>
            )}
          </motion.button>
        ))}
      </div>
    </motion.div>
  );
};

// ==================== TV REMOTE ====================
const TVRemote = ({ refresh }: { refresh: () => void }) => {
  const press = (cmd: string) => api.controlFirestick(cmd).then(refresh);

  const RemoteBtn = ({ onClick, children, variant = 'default' }: any) => (
    <motion.button
      whileTap={{ scale: 0.9 }}
      onClick={onClick}
      className={cn(
        "w-12 h-12 rounded-2xl flex items-center justify-center transition-all",
        variant === 'primary' && "bg-gradient-to-br from-blue-500 to-blue-600 text-white shadow-lg shadow-blue-500/30",
        variant === 'default' && "bg-white/10 text-white/80 hover:bg-white/20",
        variant === 'accent' && "bg-gradient-to-br from-purple-500 to-pink-500 text-white"
      )}
    >
      {children}
    </motion.button>
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2 }}
      className="bg-gradient-to-br from-slate-900/60 to-slate-800/60 backdrop-blur-xl rounded-3xl p-6 border border-white/10 shadow-2xl"
    >
      <h3 className="text-white font-semibold text-lg mb-4 text-center">Fire TV</h3>

      {/* Top Row */}
      <div className="flex justify-center gap-4 mb-4">
        <RemoteBtn onClick={() => press('back')}><ArrowLeft size={20} /></RemoteBtn>
        <RemoteBtn onClick={() => press('home')} variant="primary"><Home size={20} /></RemoteBtn>
        <RemoteBtn onClick={() => press('menu')}><Menu size={20} /></RemoteBtn>
      </div>

      {/* D-Pad */}
      <div className="relative w-40 h-40 mx-auto mb-4">
        <motion.button
          whileTap={{ scale: 0.9 }}
          onClick={() => press('up')}
          className="absolute top-0 left-1/2 -translate-x-1/2 w-12 h-12 bg-white/10 rounded-full flex items-center justify-center"
        >
          <ChevronUp className="text-white" />
        </motion.button>
        <motion.button
          whileTap={{ scale: 0.9 }}
          onClick={() => press('down')}
          className="absolute bottom-0 left-1/2 -translate-x-1/2 w-12 h-12 bg-white/10 rounded-full flex items-center justify-center"
        >
          <ChevronDown className="text-white" />
        </motion.button>
        <motion.button
          whileTap={{ scale: 0.9 }}
          onClick={() => press('left')}
          className="absolute left-0 top-1/2 -translate-y-1/2 w-12 h-12 bg-white/10 rounded-full flex items-center justify-center"
        >
          <ChevronLeft className="text-white" />
        </motion.button>
        <motion.button
          whileTap={{ scale: 0.9 }}
          onClick={() => press('right')}
          className="absolute right-0 top-1/2 -translate-y-1/2 w-12 h-12 bg-white/10 rounded-full flex items-center justify-center"
        >
          <ChevronRight className="text-white" />
        </motion.button>
        <motion.button
          whileTap={{ scale: 0.9 }}
          onClick={() => press('select')}
          className="absolute inset-0 m-auto w-16 h-16 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center shadow-lg"
        >
          <div className="w-4 h-4 bg-white rounded-full" />
        </motion.button>
      </div>

      {/* Media Controls */}
      <div className="flex justify-center gap-4 mb-4">
        <RemoteBtn onClick={() => press('rewind')}><SkipBack size={18} /></RemoteBtn>
        <RemoteBtn onClick={() => press('play')} variant="accent"><Play size={18} /></RemoteBtn>
        <RemoteBtn onClick={() => press('fast_forward')}><SkipForward size={18} /></RemoteBtn>
      </div>

      {/* Volume */}
      <div className="flex justify-center gap-4">
        <RemoteBtn onClick={() => press('volume_down')}><Volume2 size={18} className="opacity-50" /></RemoteBtn>
        <RemoteBtn onClick={() => press('mute')}><VolumeX size={18} /></RemoteBtn>
        <RemoteBtn onClick={() => press('volume_up')}><Volume2 size={18} /></RemoteBtn>
      </div>
    </motion.div>
  );
};

// ==================== CHAT INTERFACE ====================
const ChatInterface = ({ refresh }: { refresh: () => void }) => {
  const [messages, setMessages] = useState<{ role: 'user' | 'ai'; text: string }[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const send = async () => {
    if (!input.trim()) return;
    const text = input;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', text }]);
    setLoading(true);

    try {
      const res = await api.sendChat(text, 'esp');
      setMessages(prev => [...prev, { role: 'ai', text: res.data.ai_text || 'Done.' }]);
    } catch {
      setMessages(prev => [...prev, { role: 'ai', text: 'Error connecting to AI.' }]);
    }
    setLoading(false);
    refresh();
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.3 }}
      className="bg-gradient-to-br from-emerald-900/30 to-teal-900/30 backdrop-blur-xl rounded-3xl p-6 border border-white/10 shadow-2xl flex flex-col h-80"
    >
      <h3 className="text-white font-semibold text-lg mb-4">NOVA Assistant</h3>

      <div className="flex-1 overflow-y-auto space-y-3 mb-4 pr-2 scrollbar-thin scrollbar-thumb-white/20">
        {messages.length === 0 && (
          <div className="text-center text-white/30 py-8">
            <p className="text-lg">👋 Hi there!</p>
            <p className="text-sm mt-1">Ask me anything...</p>
          </div>
        )}
        <AnimatePresence>
          {messages.map((m, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={cn(
                "max-w-[80%] p-3 rounded-2xl text-sm",
                m.role === 'user'
                  ? "ml-auto bg-gradient-to-r from-blue-500 to-blue-600 text-white"
                  : "bg-white/10 text-white/90"
              )}
            >
              {m.text}
            </motion.div>
          ))}
        </AnimatePresence>
        {loading && (
          <div className="bg-white/10 max-w-[50%] p-3 rounded-2xl">
            <div className="flex gap-1">
              <div className="w-2 h-2 bg-white/50 rounded-full animate-bounce" />
              <div className="w-2 h-2 bg-white/50 rounded-full animate-bounce delay-100" />
              <div className="w-2 h-2 bg-white/50 rounded-full animate-bounce delay-200" />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="flex gap-2">
        <input
          type="text"
          placeholder="Type a message..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          className="flex-1 bg-white/10 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-white/30 focus:outline-none focus:border-white/30"
        />
        <motion.button
          whileTap={{ scale: 0.9 }}
          onClick={send}
          className="w-12 h-12 bg-gradient-to-r from-emerald-500 to-teal-500 rounded-xl flex items-center justify-center"
        >
          <Send className="w-5 h-5 text-white" />
        </motion.button>
      </div>
    </motion.div>
  );
};

// ==================== MAIN APP ====================
function App() {
  const [data, setData] = useState<any>(null);

  const refresh = async () => {
    try {
      const d = await api.getStatus();
      setData(d);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 2000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen overflow-y-auto bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white p-4 pb-8">
      {/* Decorative Background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-blue-500/20 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-purple-500/20 rounded-full blur-3xl" />
      </div>

      <div className="relative z-10 max-w-md mx-auto space-y-4">
        {/* Header */}
        <motion.header
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center justify-between py-4"
        >
          <div>
            <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
              NOVA
            </h1>
            <p className="text-white/40 text-sm">Smart Home Control</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            <span className="text-white/50 text-sm">Online</span>
          </div>
        </motion.header>

        {/* Weather */}
        <WeatherCard data={data} />

        {/* Light Controls */}
        <LightControls status={data?.light} refresh={refresh} />

        {/* TV Remote */}
        <TVRemote refresh={refresh} />

        {/* Chat */}
        <ChatInterface refresh={refresh} />

        {/* Footer */}
        <p className="text-center text-white/20 text-xs pt-4">
          NOVA OS • Mejona Technology
        </p>
      </div>
    </div>
  );
}

export default App;
